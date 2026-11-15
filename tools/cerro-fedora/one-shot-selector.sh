# A one-shot request on the outer Linux filesystem selects Fedora once.
# Consume it before switch_root so a failed first boot returns to Debian.
if [ -f /sysroot/cerro-boot-fedora-once ]; then
  if rm -f /sysroot/cerro-boot-fedora-once; then
    sync
    if [ -f /sysroot/fedora-kde-root/.cerro-native-fedora ] && \
       [ -x /sysroot/fedora-kde-root/cerro-sd-prep ] && \
       [ -x /sysroot/fedora-kde-root/usr/lib/systemd/systemd ]; then
      mkdir -p /fedoraroot
      if mount --bind /sysroot/fedora-kde-root /fedoraroot; then
        log 'cerro-fedora: one-shot root selected'
        exec switch_root /fedoraroot /cerro-sd-prep
        log 'cerro-fedora: switch_root failed; falling back to Debian'
      else
        log 'cerro-fedora: bind mount failed; falling back to Debian'
      fi
    else
      log 'cerro-fedora: incomplete root; falling back to Debian'
    fi
  else
    log 'cerro-fedora: could not consume request; keeping Debian'
  fi
fi
