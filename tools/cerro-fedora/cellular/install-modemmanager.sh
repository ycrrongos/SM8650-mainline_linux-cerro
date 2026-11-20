#!/bin/sh
# Stage the verified daemon. Restart ModemManager separately after checking the device.
set -eu
candidate=${1:?usage: install-modemmanager.sh DAEMON SHA256}
hash=${2:?expected SHA256 required}
test "$(id -u)" = 0
test "$(rpm -q --qf '%{VERSION}' ModemManager)" = 1.24.2
printf '%s' "$hash" | grep -Eq '^[a-f0-9]{64}$'
printf '%s  %s\n' "$hash" "$candidate" | sha256sum -c -
dynamic=$(readelf -d "$candidate")
if printf '%s\n' "$dynamic" | grep -Eq '(RPATH|RUNPATH)'; then
    printf '%s\n' 'Remove the build-time library search path before installing.' >&2
    exit 1
fi
deps=$(ldd "$candidate")
if printf '%s\n' "$deps" | grep -q 'not found'; then
    printf '%s\n' "$deps" >&2
    exit 1
fi
vendor_release=$(rpm -q --qf '%{VERSION}-%{RELEASE}' ModemManager)
"$candidate" --version | grep -Fx "ModemManager $vendor_release.cerro5"

base=/usr/local/libexec/cerro-mm-fedora-r5
conf=/etc/systemd/system/ModemManager.service.d/zzzzzz-cerro-dsds-bearer-r5.conf
test ! -e "$conf"
install -d "$base" "$(dirname "$conf")"
install -m 0755 "$candidate" "$base/ModemManager"
printf '%s  %s\n' "$hash" "$base/ModemManager" | sha256sum -c -
printf '[Service]\nEnvironment=MM_CERRO_QMI_DDS=1\nExecStart=\nExecStart=%s/ModemManager\n' "$base" > "$conf"
if ! systemctl daemon-reload || ! systemd-analyze verify ModemManager.service; then
    rm -f "$conf"
    systemctl daemon-reload
    exit 1
fi
