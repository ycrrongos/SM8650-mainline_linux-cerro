#!/bin/sh
# Enable the native SIM2 data path after installing the matching daemon and controller.
set -eu
apn=${1:?usage: install-native-sim2.sh SIM2_APN}
test "$(id -u)" = 0
systemctl show ModemManager.service -p Environment --value | grep -qw MM_CERRO_QMI_DDS=1
grep -Fq 'def apply_native_data_slot(' /usr/local/libexec/cerro-cellular-c1/cellular_daemon.py

profile=cerro-sim2-gsm
if nmcli -g connection.type connection show "$profile" >/dev/null 2>&1; then
    test "$(nmcli -g connection.type connection show "$profile")" = gsm
else
    nmcli connection add type gsm ifname '*' con-name "$profile" apn "$apn" \
        gsm.auto-config no connection.autoconnect no ipv4.method auto ipv6.method disabled
fi

dropin=/etc/systemd/system/cerro-cellular-c1.service.d/70-native-sim2.conf
install -d "$(dirname "$dropin")"
printf '[Service]\nEnvironment=CERRO_NATIVE_SIM2=1\n' > "$dropin"
systemctl daemon-reload
systemd-analyze verify cerro-cellular-c1.service
