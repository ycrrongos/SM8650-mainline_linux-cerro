# Invisible external pointer in Niri on Cerro

When pointer input works but DP does not visibly show the cursor, inspect the
active DRM CRTC and plane state first. In the observed configuration, DP-1
used a separate 512×512 cursor framebuffer and Niri had no cursor hide rule.

The reversible Niri workaround is to composite the cursor into the main
frame. Add the following to the existing `debug` block, or create one:

```kdl
debug {
    disable-cursor-plane
}
```

Run `niri validate` before deploying. Hot reload was observed on Niri 26.04:
the dedicated plane was detached, both display connectors stayed active,
and the touchpad and dashboard services stayed up. Visual confirmation is
pending. Restore the previous Niri config to reverse it.
