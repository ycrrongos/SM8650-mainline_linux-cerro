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

## Native microphone and duplex

Install the verified TX AMIC topology from the maintained Cerro audio build
as a firmware override at
`/usr/lib/firmware/updates/qcom/sm8650/SM8650-CERRO-tplg.bin`.
The original embedded topology remains the fallback. After reboot verify
the `MultiMedia2 Mixer TX_CODEC_DMA_TX_3` control exists before installing
the Fedora HiFi profile under `/usr/share/alsa/ucm2/Qualcomm/sm8650/CERRO/`.

The microphone route belongs in the HiFi verb enable sequence because
PipeWire ACP probes the capture PCM before enabling individual UCM devices.
Fedora was tested with a simultaneous speaker playback stream and microphone
capture stream. Both hardware PCMs ran and the capture had nonzero samples.

A separate boot after installing both camera and interconnect changes showed
the camera service completing its first probe and all four cpufreq policies.

## Cellular profile

Cerro's primary SIM uses a standard NetworkManager GSM connection. Install
Fedora's `mobile-broadband-provider-info` and allow NetworkManager to select
the provider APN. The current deployment's profile is named
`cerro-sim1-cmnet` for compatibility with Cerro's data selector.

```sh
sudo dnf install mobile-broadband-provider-info
sudo nmcli connection modify cerro-sim1-cmnet \
  gsm.apn "" gsm.auto-config yes ipv6.method auto ipv6.may-fail yes
```

Reactivate the profile to apply it. On the validated SIM1 both IPv4 and IPv6
HTTPS worked with requests explicitly bound to the cellular link. Carrier
profiles may require an explicitly supplied APN.

SIM2 also uses a standard NM GSM profile on the validated Fedora setup.
Install the matching Cerro ModemManager and cellular controller, then run
`tools/cerro-fedora/cellular/install-native-sim2.sh SIM2_APN`. Supply the
secondary carrier's APN explicitly: the modem's exported primary SIM is
still SIM1 on this DSDS firmware, so NM's primary-SIM APN lookup can pick
the wrong provider. The installed SIM2 profile disables IPv6 after a
dual-stack test failed to establish reliable IPv6 traffic, and SIM1
keeps optional IPv6. SIM1 IPv6 worked in a warm test, but the modem refused
the IPv6 session after a reboot with SIM2 selected followed by a switch to
SIM1. NetworkManager kept the IPv4 connection.

Use **SIM 与短信** to select either data SIM or to close data. The coordinator
sets the modem's default data subscription before activating the GSM
profile. ModemManager binds the WDS client after mux setup and verifies
the subscription readback before dialing. NetworkManager applies IP
configuration from the resulting Bearer. The SIM2 profile is saved with
autoconnect off and only enables it for the running session after the
coordinator has confirmed DDS, preventing a cold-start dial before selection.
A reboot with SIM2 selected restored an actual working SIM2 IPv4 connection
on the first service start.
Spacebar retains the separate secondary-SIM SMS compatibility layer.

The Cerro ModemManager build refreshes `InitialEpsBearerSettings` from the
modem's current attach PDN when a WDS bearer comes up. An attach profile is
separate from the APN used by the NetworkManager data connection. A warm
SIM1 → SIM2 → SIM1 regression test passed IPv4 traffic on all three legs.
Cold-boot attach profile changes still need independent validation. The modem
continued to reject SIM1 IPv6 with QMI reason 2/210 after the profile refresh.
