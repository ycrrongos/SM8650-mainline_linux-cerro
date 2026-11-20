# Cerro Spacebar secondary SIM reception

On Cerro Fedora, ModemManager exposes the primary SIM to Spacebar. The Cerro
cellular service binds its separate WMS client to each subscription. This patch
lets the Spacebar daemon import incoming SIM2 SMS through the existing
owner-only `/run/cerro-cellular/control.sock` API. The stock UI and ModemManager
primary-SIM path are used for conversations, notifications and the primary
subscription. Select the sending SIM in **SIM 与短信**.

The patch is based on KDE Spacebar v6.8.3, commit
`f342ea3ecbb524b19470a9c74ddbf61ee925f520`. Apply it to that checkout and build
the `spacebar-daemon` target in a Fedora ARM64 environment with Spacebar's build
dependencies, including `protobuf-devel` and `abseil-cpp-devel` for Fedora's
libphonenumber headers.

```sh
git apply /path/to/0001-import-cerro-secondary-sim-sms.patch
cmake -S . -B out -G Ninja -DBUILD_TESTING=OFF -DCMAKE_BUILD_TYPE=Release
cmake --build out --target spacebar-daemon
ldd -r out/bin/spacebar-daemon
```

Run the daemon as the desktop user. Install it in
`~/.local/libexec/cerro-spacebar-daemon` and copy Fedora's
`/etc/xdg/autostart/org.kde.spacebar.daemon.desktop` to `~/.config/autostart/`,
with `Exec=` set to the absolute path of the new daemon. Reload the user systemd
manager and restart the Spacebar autostart service. To restore the stock
daemon, remove the user autostart override, then reload the user manager and
restart that service.

The importer leaves modem storage intact. It records imported identities in
its own user settings and uses stable IDs for retry after interruption.
Duplicate imports are skipped across daemon restarts. It waits for complete
multipart text and leaves MMS handling to the upstream daemon.
