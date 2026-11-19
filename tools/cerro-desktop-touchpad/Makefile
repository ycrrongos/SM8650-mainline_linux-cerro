PKGS = cairo libdrm wayland-client
LEASE_XML ?= $(shell pkg-config --variable=pkgdatadir wayland-protocols)/staging/drm-lease/drm-lease-v1.xml
CFLAGS += -Wall -Wextra -Werror $(shell pkg-config --cflags $(PKGS))
LDLIBS += $(shell pkg-config --libs $(PKGS))

lease-panel: lease-panel.c drm-lease-protocol.c drm-lease-client.h
	$(CC) $(CFLAGS) $(LDFLAGS) lease-panel.c drm-lease-protocol.c $(LDLIBS) -o $@

drm-lease-client.h: $(LEASE_XML)
	wayland-scanner client-header $< $@

drm-lease-protocol.c: $(LEASE_XML)
	wayland-scanner private-code $< $@
