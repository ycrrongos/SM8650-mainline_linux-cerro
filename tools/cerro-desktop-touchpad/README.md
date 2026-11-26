# Cerro desktop touchpad prototype

The Goodix touchscreen is a protocol B device. The relay grabs only that device,
keeps individual contact IDs and emits a libinput touchpad through uinput.
Niri handles gestures using its normal input settings. The default coordinate
rotation matches the landscape DSI transform tested on Cerro. The relay
requires a connected DP connector and releases the touchscreen on disconnect.

Fedora 45 with the current Cerro kernel needs a matching uinput module and
python3-evdev. Build against the exact maintained kernel and matching symbol
file, for example:

    make -C build/linux-7.2 ARCH=arm64 LLVM=1 M=drivers/input/misc CONFIG_INPUT_UINPUT=m uinput.ko

After loading that module, a bounded manual probe on a known Cerro device is:

    sudo systemd-run --unit=cerro-touchpad-probe --property=RuntimeMaxSec=90 \
      /usr/bin/python3 /path/to/relay.py /dev/input/by-path/platform-a90000.spi-cs-0-event

The separate Quickshell dashboard preview requires cava, playerctl and the
session's PulseAudio-compatible audio server. The preview is an ordinary window.
Run `qs -p /path/to/cerro-desktop-touchpad` within the session to view it.
Synchronized lyrics use local `.lrc` files under
`~/.local/share/cerro-touchpad/lyrics/` named `Artist - Title.lrc`. Track
metadata and playback position come from MPRIS.

## Integration limits

On Cerro, DSI and DP share the only DRM card. Niri's output-off removes DSI
from the desktop but also stops scanout. Niri v26.04 advertises
wp_drm_lease_device_v1 and offers only connectors with the kernel non-desktop
property. A complete implementation still needs compositor-side transition
and lease revocation, plus a dashboard renderer that accepts the leased DRM
file descriptor. Keep the original display layout until those paths exist.

## Verified on Fedora 45

- Dock to HDMI appears in Niri as DP-1 at 2560×1440.
- uinput loaded without reboot. libinput reported a 157×71 mm touchpad with
  pointer and gesture capabilities. Real touch produced pointer motion, click,
  hold and four-finger swipe. The user confirmed the gestures they tried.
- Simulated connector loss exited the guarded relay successfully.
- Quickshell loaded the preview and Niri listed its window. Cava emitted a
  32-band frame at idle. Active playback and lyrics have not been tested.

Fedora external display mode starts as a full-screen touchpad. With no USB or
Bluetooth keyboard, use the upper-right button to switch between touchpad and
full-screen keyboard. The **Cerro 触摸板** tray icon opens the saved speed slider
(50–200%, default 100%). The tray requires a StatusNotifier host, GTK 3 and
PyGObject. Install the update with `install-split-keyboard.sh`.
