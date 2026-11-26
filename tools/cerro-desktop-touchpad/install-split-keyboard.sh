#!/bin/sh
# Install the external touchpad and keyboard modes on a Fedora phone with the Niri dashboard installed.
set -eu
src=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
dashboard=${1:-"$HOME/.local/src/cerro-dsi/client"}
relay=/usr/local/libexec/cerro-touchpad
unit=/etc/systemd/system/cerro-layer-relay.service

if [ ! -f "$dashboard/layer-mode.py" ] || [ ! -f "$relay/relay.py" ] || [ ! -f "$unit" ]; then
    echo "Install the existing Cerro Niri touchpad dashboard and relay first." >&2
    exit 1
fi

if ! /usr/bin/python3 -c 'import gi; gi.require_version("Gtk", "3.0"); from gi.repository import Gtk'; then
    echo "Install the Fedora python3-gobject and gtk3 packages for the speed tray." >&2
    exit 1
fi

mkdir -p "${XDG_STATE_HOME:-$HOME/.local/state}"
backup=$(mktemp -d "${XDG_STATE_HOME:-$HOME/.local/state}/cerro-touchpad.XXXXXX") || exit 1
cp "$dashboard/layer/shell.qml" "$dashboard/ripple-stream.py" "$dashboard/layer-mode.py" "$backup/"
for path in "$dashboard/layer/KeyboardGrid.qml" "$dashboard/tray.py" "$relay/keyboard.py"; do
    if [ -f "$path" ]; then cp "$path" "$backup/"; fi
done
cp "$relay/relay.py" "$unit" "$backup/"
echo "Previous files saved to $backup"

sudo -v
# New modules are in place before either component begins using them.
sudo install -m 0644 "$src/keyboard.py" "$relay/keyboard.py"
install -m 0644 "$src/layer/KeyboardGrid.qml" "$dashboard/layer/KeyboardGrid.qml"
install -m 0644 "$src/tray.py" "$src/layer-mode.py" "$dashboard/"
install -m 0644 "$src/ripple-stream.py" "$dashboard/ripple-stream.py"
install -m 0644 "$src/layer/shell.qml" "$dashboard/layer/shell.qml"
sudo install -m 0644 "$src/relay.py" "$relay/relay.py"
sudo install -m 0644 "$src/cerro-layer-relay.service" "$unit"
sudo systemctl daemon-reload
if systemctl --user is-active --quiet cerro-touchpad-dashboard.service; then
    systemctl --user stop cerro-touchpad-dashboard.service
    sudo systemctl stop cerro-layer-relay.service
    systemctl --user start cerro-touchpad-dashboard.service
fi
