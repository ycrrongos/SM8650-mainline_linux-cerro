# Fedora hardware bring-up on Cerro

Fedora on the existing Linux filesystem uses a subdirectory root. The stock
Fedora disk image's root expansion recipe does not apply in this layout.
Remove only the image template from repart configuration, retain a backup,
and verify `systemd-repart --dry-run=yes` reports no changes.

The CPU OPP paths depend on the EPSS L3 interconnect provider. Match
`icc-osm-l3.ko` to the booted kernel and install it in its module tree.
After depmod, the platform modalias resolves to the module. The live test
bound the EPSS provider and exposed four CPU frequency policies.

The working Cerro playback route requires the board's ALSA UCM profile.
With the same-device Debian speaker profile installed, Fedora PipeWire
exposed a native HiFi speaker sink. A silent test stream advanced the real
ALSA PCM hardware pointer. Microphone routing requires additional controls.

Use the existing camera board startup recipe and the device's own
calibration. Verify the numbered media device nodes and allow the active
seat access to the camera DMA heaps. With the Cerro libcamera build, the
main and front cameras both produced RGB frames at approximately 30 fps as
a normal user. This test did not assess picture quality.

Zram and zsmalloc require a matching kernel built with that configuration.
A standalone zsmalloc module cannot add the missing kernel zone-stat counter.
