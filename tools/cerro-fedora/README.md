# Fedora on Cerro (host preparation)

This directory prepares a **one-shot Fedora root selector** for an existing Cerro Linux boot image. It does not flash a phone or replace Android/Debian. See the project boot and dual-boot notes before deployment.

## Inputs

- A fresh, complete 96 MiB readback of the **currently active Linux boot partition**, with its SHA-256. The selector builder refuses a digest mismatch.
- A separately staged Fedora ARM64 root at `/fedora-kde-root` on the existing outer Linux filesystem. It must contain `.cerro-native-fedora`, `cerro-sd-prep`, and `/usr/lib/systemd/systemd`.
- The corresponding kernel modules and firmware for the boot image. A generic Fedora kernel or device tree is not a Cerro replacement.
- For transparent FEX launch, merge `patches/fedora-binfmt-c1.fragment` into the matching Cerro kernel config and build through `tools/cerro-build-boot.sh`. A standalone `binfmt_misc.ko` cannot supply the `init_binfmt_misc` symbol missing from a kernel built with the option unset.

## Build

```sh
python3 tools/cerro-fedora/make-one-shot-boot.py \
  build/dualboot/current-active-slot-boot-readback.img \
  '<sha256-of-that-readback>' \
  build/dualboot/linux-fedora-once-candidate.img
```

The builder keeps the v2 boot header, 127-byte stub ramdisk, DTB and all bytes outside the embedded gzip initramfs member unchanged. It verifies the rewritten cpio and shell syntax. It uses `libdeflate-gzip -12` to fit within the existing member slot. A successful build is **not** evidence of an ABL-accepted or usable phone boot.

## First boot gate

After the Fedora root and matching boot have been installed and read back, create `/cerro-boot-fedora-once` on the **outer** Linux filesystem. The initramfs consumes the marker before trying Fedora, so a later forced restart returns to Debian. Confirm the active slot and preserve the inactive Android boot/dtbo cache. Observe the complete boot, USB/SSH and desktop; do not mark Fedora complete from a systemd service or an empty error log.

FEX requires a 4 KiB page kernel and `CONFIG_BINFMT_MISC=y` for transparent x86 program launch. Fedora's `x86-emulation` group alone does not install the FEX runtime/rootfs in the Fedora 45 container baseline; install the signed FEX packages and test an actual x86 program.

## SMS on KDE

Fedora provides Plasma Mobile's Spacebar as the `spacebar` package. Install it
with `dnf install spacebar` and open **Spacebar** from the launcher. Its daemon
starts through the packaged desktop autostart entry. For the current session
it can also be started as the logged-in user with `/usr/libexec/spacebar-daemon`.
Spacebar uses the modem and message storage exported by ModemManager. The
separate **SIM 与短信** app provides Cerro's physical SIM selection for data and
direct per-card SMS access.
