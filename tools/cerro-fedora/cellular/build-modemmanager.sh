#!/bin/sh
# Build the Cerro DSDS fix for Fedora's ModemManager 1.24.2 userspace.
set -eu
archive=$(realpath "${1:?usage: build-modemmanager.sh UPSTREAM_TAR NEW_WORK_DIRECTORY}")
work=${2:?new work directory required}
base=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
patch_dir=$base/patches/cellular-qmi-primary-slot-c1
version=$(rpm -q --qf '%{VERSION}' ModemManager)
test "$version" = 1.24.2
printf '%s  %s\n' fbc75adcc0d7b0565f256e7ff4e8872b0a37c4413ff576665f7470932d9c1b68 "$archive" | sha256sum -c -
mkdir "$work"
cd "$work"
tar xf "$archive"
source_dir=ModemManager-1.24.2
git -C "$source_dir" apply "$patch_dir/0001-qmi-select-primary-logical-slot-on-dsds.patch" \
    "$base/tools/cerro-fedora/cellular/0001-mm-netlink-keep-completion-callback.patch" \
    "$base/tools/cerro-fedora/cellular/0002-mm-count-multiplexed-bearers-in-cleanup.patch" \
    "$base/tools/cerro-fedora/cellular/0003-mm-reprobe-qrtr-on-resume.patch" \
    "$base/tools/cerro-fedora/cellular/0004-mm-bind-wds-to-cerro-default-data-subscription.patch"
python3 "$patch_dir/test-primary-slot.py" "$source_dir/src/mm-shared-qmi.c"
meson setup out "$source_dir" --prefix=/usr --libdir=lib64 --sbindir=sbin \
    -Dintrospection=false -Dvapi=false -Dgtk_doc=false -Dman=false \
    -Dbash_completion=false -Dudevdir=/usr/lib/udev \
    -Dsystemdsystemunitdir=/usr/lib/systemd/system -Ddbus_policy_dir=/usr/share/dbus-1/system.d \
    -Dqrtr=true -Dqmi=true -Dmbim=true -Dpolkit=permissive \
    "-Ddist_version=\"$(rpm -q --qf '%{VERSION}-%{RELEASE}' ModemManager).cerro5\""
ninja -C out -j "${JOBS:-4}" src/ModemManager
cp out/src/ModemManager ModemManager
patchelf --remove-rpath ModemManager
sha256sum ModemManager
