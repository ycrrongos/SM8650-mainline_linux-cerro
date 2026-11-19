// Render a Cairo PNG snapshot to the DSI connector through a Wayland DRM lease.
#define _POSIX_C_SOURCE 200809L
#include <cairo.h>
#include <errno.h>
#include <poll.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>
#include <wayland-client.h>
#include <xf86drm.h>
#include <xf86drmMode.h>
#include "drm-lease-client.h"

static struct wp_drm_lease_device_v1 *device;
static struct wp_drm_lease_connector_v1 *panel;
static uint32_t panel_id;
static int lease_fd = -1;
static bool done, withdrawn;

static void connector_name(void *data, struct wp_drm_lease_connector_v1 *connector,
                           const char *name)
{
    (void)data;
    if (strcmp(name, "DSI-1") == 0)
        panel = connector;
}
static void connector_description(void *data, struct wp_drm_lease_connector_v1 *connector,
                                  const char *description)
{
    (void)data; (void)connector; (void)description;
}
static void connector_id(void *data, struct wp_drm_lease_connector_v1 *connector,
                         uint32_t id)
{
    (void)data;
    if (connector == panel)
        panel_id = id;
}
static void connector_done(void *data, struct wp_drm_lease_connector_v1 *connector)
{
    (void)data; (void)connector;
}
static void connector_withdrawn(void *data, struct wp_drm_lease_connector_v1 *connector)
{
    (void)data;
    if (connector == panel)
        withdrawn = true;
    wp_drm_lease_connector_v1_destroy(connector);
}
static const struct wp_drm_lease_connector_v1_listener connector_listener = {
    connector_name, connector_description, connector_id, connector_done, connector_withdrawn
};

static void device_fd(void *data, struct wp_drm_lease_device_v1 *obj, int fd)
{
    (void)data; (void)obj;
    close(fd);
}
static void device_connector(void *data, struct wp_drm_lease_device_v1 *obj,
                             struct wp_drm_lease_connector_v1 *connector)
{
    (void)data; (void)obj;
    wp_drm_lease_connector_v1_add_listener(connector, &connector_listener, NULL);
}
static void device_done(void *data, struct wp_drm_lease_device_v1 *obj)
{
    (void)data; (void)obj;
    done = true;
}
static void device_released(void *data, struct wp_drm_lease_device_v1 *obj)
{
    (void)data;
    wp_drm_lease_device_v1_destroy(obj);
    withdrawn = true;
}
static const struct wp_drm_lease_device_v1_listener device_listener = {
    device_fd, device_connector, device_done, device_released
};

static void global(void *data, struct wl_registry *registry, uint32_t id,
                   const char *interface, uint32_t version)
{
    (void)data; (void)version;
    if (!device && strcmp(interface, wp_drm_lease_device_v1_interface.name) == 0) {
        device = wl_registry_bind(registry, id, &wp_drm_lease_device_v1_interface, 1);
        wp_drm_lease_device_v1_add_listener(device, &device_listener, NULL);
    }
}
static void global_remove(void *data, struct wl_registry *registry, uint32_t id)
{
    (void)data; (void)registry; (void)id;
}
static const struct wl_registry_listener registry_listener = {global, global_remove};

static void lease_granted(void *data, struct wp_drm_lease_v1 *lease, int fd)
{
    (void)data; (void)lease;
    lease_fd = fd;
}
static void lease_finished(void *data, struct wp_drm_lease_v1 *lease)
{
    (void)data; (void)lease;
    withdrawn = true;
}
static const struct wp_drm_lease_v1_listener lease_listener = {lease_granted, lease_finished};

static int scanout(const char *image, const char *ready_path, struct wl_display *display)
{
    drmModeRes *res = drmModeGetResources(lease_fd);
    drmModeConnector *conn = drmModeGetConnector(lease_fd, panel_id);
    if (!res || res->count_crtcs != 1 || !conn || conn->count_modes < 1) {
        fprintf(stderr, "Expected an exclusive CRTC and DSI modes on leased fd\n");
        return 1;
    }
    drmModeModeInfo mode = conn->modes[0];
    for (int i = 0; i < conn->count_modes; ++i)
        if (conn->modes[i].vrefresh == 60) {
            mode = conn->modes[i];
            break;
        }

    struct drm_mode_create_dumb buffer = {
        .width = mode.hdisplay, .height = mode.vdisplay, .bpp = 32
    };
    if (drmIoctl(lease_fd, DRM_IOCTL_MODE_CREATE_DUMB, &buffer) < 0) {
        perror("CREATE_DUMB");
        return 1;
    }
    uint32_t fb;
    struct drm_mode_map_dumb map = {.handle = buffer.handle};
    if (drmModeAddFB(lease_fd, buffer.width, buffer.height, 24, 32, buffer.pitch,
                     buffer.handle, &fb) < 0 ||
        drmIoctl(lease_fd, DRM_IOCTL_MODE_MAP_DUMB, &map) < 0) {
        perror("prepare framebuffer");
        return 1;
    }
    unsigned char *pixels = mmap(NULL, buffer.size, PROT_READ | PROT_WRITE,
                                 MAP_SHARED, lease_fd, map.offset);
    if (pixels == MAP_FAILED) {
        perror("mmap framebuffer");
        return 1;
    }
    memset(pixels, 0, buffer.size);
    int rc = drmModeSetCrtc(lease_fd, res->crtcs[0], fb, 0, 0, &panel_id, 1, &mode);
    if (rc < 0) {
        perror("DRM lease modeset");
        return 1;
    }

    cairo_surface_t *surface = cairo_image_surface_create_for_data(
        pixels, CAIRO_FORMAT_RGB24, buffer.width, buffer.height, buffer.pitch);
    cairo_t *cr = cairo_create(surface);
    fprintf(stderr, "DSI lease modeset: %ux%u\n", buffer.width, buffer.height);
    FILE *ready = fopen(ready_path, "w");
    if (!ready) {
        perror("dashboard readiness file");
        return 1;
    }
    fclose(ready);
    while (!withdrawn) {
        cairo_surface_t *frame = cairo_image_surface_create_from_png(image);
        if (cairo_surface_status(frame) == CAIRO_STATUS_SUCCESS) {
            cairo_save(cr);
            /* The portrait panel is used counterclockwise in touchpad mode. */
            cairo_translate(cr, 0, buffer.height);
            cairo_rotate(cr, -1.5707963267948966);
            cairo_scale(cr, (double)buffer.height / cairo_image_surface_get_width(frame),
                        (double)buffer.width / cairo_image_surface_get_height(frame));
            cairo_set_source_surface(cr, frame, 0, 0);
            cairo_paint(cr);
            cairo_restore(cr);
            cairo_surface_flush(surface);
        }
        cairo_surface_destroy(frame);
        struct pollfd pfd = {.fd = wl_display_get_fd(display), .events = POLLIN};
        int ready = poll(&pfd, 1, 42);
        if ((ready < 0 && errno != EINTR) ||
            (ready > 0 && wl_display_dispatch(display) < 0))
            break;
    }
    cairo_destroy(cr);
    cairo_surface_destroy(surface);
    munmap(pixels, buffer.size);
    drmModeFreeConnector(conn);
    drmModeFreeResources(res);
    return 0;
}

int main(int argc, char **argv)
{
    if (argc != 3) {
        fprintf(stderr, "Usage: %s DASHBOARD.png READY_FILE\n", argv[0]);
        return 2;
    }
    struct wl_display *display = wl_display_connect(NULL);
    if (!display) {
        perror("Wayland display");
        return 1;
    }
    struct wl_registry *registry = wl_display_get_registry(display);
    wl_registry_add_listener(registry, &registry_listener, NULL);
    if (wl_display_roundtrip(display) < 0 || !device ||
        wl_display_roundtrip(display) < 0 || !done || !panel || !panel_id || withdrawn) {
        fprintf(stderr, "Niri is not offering a DSI-1 DRM lease\n");
        wl_display_disconnect(display);
        return 1;
    }
    struct wp_drm_lease_request_v1 *request = wp_drm_lease_device_v1_create_lease_request(device);
    wp_drm_lease_request_v1_request_connector(request, panel);
    struct wp_drm_lease_v1 *lease = wp_drm_lease_request_v1_submit(request);
    wp_drm_lease_v1_add_listener(lease, &lease_listener, NULL);
    while (lease_fd < 0 && !withdrawn)
        if (wl_display_dispatch(display) < 0)
            break;
    int rc = lease_fd < 0 ? 1 : scanout(argv[1], argv[2], display);
    wp_drm_lease_v1_destroy(lease);
    wl_display_flush(display);
    wl_display_disconnect(display);
    if (lease_fd >= 0)
        close(lease_fd);
    return rc;
}
