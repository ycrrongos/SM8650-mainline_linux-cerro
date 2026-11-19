# Stock Niri dashboard mode

The Quickshell overlay is targeted only at DSI-1 and renders through Niri's
ordinary output path. It ignores pointer and keyboard input. The controller
focuses DP, places DSI across a logical gap to stop normal relative pointer
motion, and moves application windows found on DSI back to DP. Both outputs
stay visible to Wayland clients. Explicit compositor shortcuts can briefly
switch focus before the guard reacts.

From a session with both outputs active, run the sibling controller with
`--seconds 90` for an overlay-only test. With the matching uinput module,
python3-evdev and a locally installed privileged relay service, pass
`--relay` to enable the touchpad too. The service reads only the Goodix
input, exits when DP disconnects or when the dashboard heartbeat goes stale,
and must run an administrator-owned copy of relay.py. The sample unit assumes
UID 1000 and the Cerro device and module paths used by Fedora. Normal input
returns when the relay exits. No unit should be enabled at boot.

The dashboard uses an MPRIS player, local timed LRC files, Cava for the
audio spectrum and live battery, memory and load data. See the parent README
for the lyric file location.
