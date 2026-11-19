#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# Install files only. Does not launch the GUI/backend or write partitions.
set -eu
case "${1:-}" in
 ''|--switch-only) ;;
 *) printf '%s\n' 'Usage: install-linux.sh [--switch-only]' >&2; exit 2 ;;
esac
base=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
root=${DESTDIR:-}
prefix=$root/usr/local
install -d "$prefix/libexec/cerro-switch" "$prefix/bin" "$prefix/share/applications" "$root/usr/share/polkit-1/actions"
install -m755 "$base/switch-backend.sh" "$base/import-host-state.py" "$base/linux/system-switch.py" "$prefix/libexec/cerro-switch/"
install -m644 "$base/linux/org.cerro.SystemSwitch.desktop" "$prefix/share/applications/"
install -m644 "$base/linux/org.cerro.same-slot-switch.policy" "$root/usr/share/polkit-1/actions/"
cat > "$prefix/bin/cerro-system-switch" <<'EOF'
#!/bin/sh
exec python3 /usr/local/libexec/cerro-switch/system-switch.py "$@"
EOF
chmod 755 "$prefix/bin/cerro-system-switch"
if [ "${1:-}" != --switch-only ]; then
 sh "$base/install-desktop-success.sh"
fi
printf '%s\n' '系统切换入口已安装。打开应用可以预览并核对 Android 恢复计划。'
