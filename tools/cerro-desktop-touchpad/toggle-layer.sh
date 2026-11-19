#!/bin/sh
set -eu
unit=cerro-touchpad-dashboard.service
if systemctl --user is-active --quiet "$unit"; then
    exec systemctl --user stop "$unit"
fi
exec systemctl --user start "$unit"
