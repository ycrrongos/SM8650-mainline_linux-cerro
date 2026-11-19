#!/usr/bin/env bash
set -euo pipefail

archive=$(realpath "${1:?Usage: install-niri-rime-ice.sh /path/to/rime-ice.tar.gz}")
config_root=${XDG_CONFIG_HOME:-"$HOME/.config"}
data_root=${XDG_DATA_HOME:-"$HOME/.local/share"}
niri_config=$config_root/niri/config.kdl
ime_config=$config_root/cerro-niri-ime
ime_data=$data_root/cerro-niri-ime
rime_dir=$ime_data/fcitx5/rime
unit=cerro-niri-fcitx5.service
unit_file=$config_root/systemd/user/$unit
startup='spawn-at-startup "systemctl" "--user" "start" "cerro-niri-fcitx5.service"'

systemctl --user is-active --quiet niri.service
test -f "$niri_config"
command -v fcitx5 >/dev/null
if test "$config_root" != "$HOME/.config" || test "$data_root" != "$HOME/.local/share"; then
    echo 'This installer uses the standard XDG directories.' >&2
    exit 1
fi

candidate=$(mktemp "${niri_config}.XXXXXX")
staging=$(mktemp -d)
trap 'rm -f "$candidate"; rm -rf "$staging"' EXIT
cp -p "$niri_config" "$candidate"
if ! grep -Fxq "$startup" "$candidate"; then
    printf '\n%s\n' "$startup" >> "$candidate"
fi
if ! grep -Fq '// Cerro Niri input environment' "$candidate"; then
    if grep -Eq '^environment([[:space:]]|\{)' "$candidate"; then
        echo 'Merge the Rime settings into the existing Niri environment block first.' >&2
        exit 1
    fi
    cat >> "$candidate" <<'KDL'

// Cerro Niri input environment
environment {
    GTK_IM_MODULE null
    QT_IM_MODULE null
    QT_IM_MODULES null
    XMODIFIERS "@im=fcitx"
}
KDL
fi
niri validate -c "$candidate"

install -d "$ime_config/fcitx5" "$rime_dir" "$(dirname "$unit_file")"
if ! test -f "$rime_dir/rime_ice.schema.yaml"; then
    tar --extract --gzip --file "$archive" --directory "$staging" --strip-components=1 --no-same-permissions
    test -f "$staging/rime_ice.schema.yaml"
    test -f "$staging/cn_dicts/base.dict.yaml"
    test -d "$staging/lua"
    cp -a "$staging"/. "$rime_dir/"
fi
if ! test -f "$rime_dir/default.custom.yaml"; then
    cat > "$rime_dir/default.custom.yaml" <<'RIME'
patch:
  schema_list:
    - schema: rime_ice
RIME
fi
if ! test -f "$ime_config/fcitx5/profile"; then
    cat > "$ime_config/fcitx5/profile" <<'PROFILE'
[Groups/0]
Name=Niri
Default Layout=us
DefaultIM=rime

[Groups/0/Items/0]
Name=keyboard-us

[Groups/0/Items/1]
Name=rime

[GroupOrder]
0=Niri
PROFILE
fi
cat > "$unit_file" <<'UNIT'
[Unit]
Description=Fcitx5 with Rime Ice for the Niri session
BindsTo=niri.service
After=niri.service
ConditionEnvironment=XDG_CURRENT_DESKTOP=niri
ConditionEnvironment=WAYLAND_DISPLAY

[Service]
Environment=XDG_CONFIG_HOME=%h/.config/cerro-niri-ime
Environment=XDG_DATA_HOME=%h/.local/share/cerro-niri-ime
UnsetEnvironment=GTK_IM_MODULE QT_IM_MODULE QT_IM_MODULES XMODIFIERS
ExecStart=/usr/bin/fcitx5 -D
UNIT
systemd-analyze --user verify "$unit_file"
if test -f "$config_root/systemd/user/caelestia-niri.service"; then
    shell_dropin="$config_root/systemd/user/caelestia-niri.service.d"
    install -d "$shell_dropin"
    cat > "$shell_dropin/cerro-input-method.conf" <<'SHELL_UNIT'
[Service]
Environment=XMODIFIERS=@im=fcitx
UnsetEnvironment=GTK_IM_MODULE QT_IM_MODULE QT_IM_MODULES
SHELL_UNIT
fi
if ! cmp -s "$candidate" "$niri_config"; then
    if ! test -f "${niri_config}.before-rime-ice"; then
        cp -p "$niri_config" "${niri_config}.before-rime-ice"
    fi
    mv "$candidate" "$niri_config"
fi
systemctl --user daemon-reload
systemctl --user restart "$unit"
systemctl --user is-active "$unit"
