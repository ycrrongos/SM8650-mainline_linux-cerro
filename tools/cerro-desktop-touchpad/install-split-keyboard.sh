#!/bin/sh
# Install the split keyboard on a Fedora phone with the Niri dashboard installed.
set -eu
src=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
dashboard=${1:-"$HOME/.local/src/cerro-dsi/client"}
relay=/usr/local/libexec/cerro-touchpad
unit=/etc/systemd/system/cerro-layer-relay.service

if [ ! -f "$dashboard/layer-mode.py" ] || [ ! -f "$relay/relay.py" ] || [ ! -f "$unit" ]; then
    echo "Install the existing Cerro Niri touchpad dashboard and relay first." >&2
    exit 1
fi

mkdir -p "${XDG_STATE_HOME:-$HOME/.local/state}"
backup=$(mktemp -d "${XDG_STATE_HOME:-$HOME/.local/state}/cerro-touchpad.XXXXXX") || exit 1
cp "$dashboard/layer/shell.qml" "$dashboard/ripple-stream.py" "$backup/"
cp "$relay/relay.py" "$unit" "$backup/"
echo "Previous files saved to $backup"

sudo -v
# New modules are in place before either component begins using them.
sudo install -m 0644 "$src/keyboard.py" "$relay/keyboard.py"
install -m 0644 "$src/layer/KeyboardGrid.qml" "$dashboard/layer/KeyboardGrid.qml"
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
