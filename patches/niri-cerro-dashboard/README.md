# Niri v26.04 Cerro panel lease candidate

Base: upstream commit 8ed0da44d974c32c6877d2f4630c314da0717ecb.
Apply `0001-dsi-dashboard-lease.patch`, then use `cargo build --locked --release`
on Fedora ARM64 with Niri's build dependencies. Use a separate test session
with the candidate binary on PATH. Leave the standard login session available.

The patch adds the opt-in `dashboard-lease` child to output configuration.
Only DSI-1 can use it, and only while the same card has an enabled DP desktop
surface. The ordinary output disconnect path removes DSI from Niri's desktop.
The existing Smithay DRM lease path can then grant the connector, CRTC and
primary plane. On DP removal, DSI is withdrawn and matching active leases are
dropped before reconnecting the DSI desktop surface.

For a bounded validation of the lease and dashboard only, add the marker below
inside the **existing** matching DSI output block in the candidate session's
config, or add that block if it does not exist.

    output "DSI-1" {
        // cerro-dashboard-lease
    }

Build the client with Cairo, libdrm and Wayland client headers and
wayland-protocols. Run `python3 run-dashboard.py ~/.config/niri/config.kdl`
from the candidate session with Pillow, Cava and playerctl available.
The launcher restores the marker when stopped, when DP disconnects, or when
the renderer fails. Use the previously verified bounded root input relay only
after DSI scanout is confirmed. Automatic session and relay activation are
pending live validation.

Host checks: Niri cargo check and all 18 config tests passed, client built with
warnings as errors, Pillow rendered a 960×430 RGB PNG. No ARM64 lease modeset
or unplug transition has been tested. No candidate installed to device.
