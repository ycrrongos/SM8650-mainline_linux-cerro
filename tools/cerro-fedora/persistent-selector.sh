# Select Fedora by default. An explicit recovery marker bypasses it.
if [ ! -e /sysroot/cerro-boot-debian ] && \
   [ -f /sysroot/fedora-kde-root/.cerro-native-fedora ] && \
   [ -x /sysroot/fedora-kde-root/cerro-sd-prep ] && \
   [ -x /sysroot/fedora-kde-root/usr/lib/systemd/systemd ]; then
    mkdir -p /fedoraroot
    if mount --bind /sysroot/fedora-kde-root /fedoraroot; then
        log 'cerro-fedora: default root selected'
        exec switch_root /fedoraroot /cerro-sd-prep
    fi
fi
