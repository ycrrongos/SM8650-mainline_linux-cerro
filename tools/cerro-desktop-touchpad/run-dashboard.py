#!/usr/bin/env python3
"""Run the dashboard and restore Niri's DSI configuration on exit."""
import argparse
import fcntl
import os
from pathlib import Path
import re
import signal
import subprocess
import tempfile
import time


def stop(_signum, _frame):
    raise SystemExit(0)


def toggle(config, enable):
    inactive = "// cerro-dashboard-lease"
    active = "dashboard-lease // cerro-dashboard-lease"
    old, new = (inactive, active) if enable else (active, inactive)
    contents = config.read_text()
    candidate, count = re.subn(r"(?m)^([ \t]*)" + re.escape(old) + r"[ \t]*$",
                               lambda match: match[1] + new, contents)
    if count != 1:
        raise ValueError(f"Expected one {old!r} marker in {config}")
    with tempfile.NamedTemporaryFile(dir=config.parent, mode="w", delete=False) as temp:
        temp.write(candidate)
        path = Path(temp.name)
    try:
        subprocess.run(["niri", "validate", "-c", str(path)], check=True)
        if config.read_text() != contents:
            raise RuntimeError("Niri configuration changed during validation")
        path.chmod(config.stat().st_mode & 0o777)
        path.replace(config)
    finally:
        path.unlink(missing_ok=True)


def run(config, client, work):
    image = work / "dashboard.png"
    ready = work / "ready"
    producer = Path(__file__).resolve().with_name("dashboard-frame.py")
    connector = Path("/sys/class/drm/card0-DP-1/status")

    def connected():
        return connector.exists() and connector.read_text().strip() == "connected"

    if not connected():
        raise SystemExit("Connect the external display first")
    enabled = False
    frames = subprocess.Popen(["python3", str(producer), str(image)],
                              start_new_session=True)
    panel = None
    try:
        deadline = time.monotonic() + 5
        while not image.exists():
            if frames.poll() is not None or time.monotonic() > deadline:
                raise RuntimeError("Dashboard did not render a frame")
            time.sleep(0.05)
        toggle(config, True)
        enabled = True
        deadline = time.monotonic() + 4
        while connected() and frames.poll() is None:
            if not ready.exists() and time.monotonic() >= deadline:
                raise RuntimeError("DSI lease produced no modeset")
            if panel is None:
                panel = subprocess.Popen([str(client.resolve()), str(image), str(ready)],
                                         start_new_session=True)
            elif panel.poll() is not None:
                if ready.exists() or time.monotonic() >= deadline:
                    raise RuntimeError("DSI lease client exited")
                panel = None
            time.sleep(0.2)
    finally:
        try:
            if enabled:
                toggle(config, False)
        finally:
            for child in (panel, frames):
                if child and child.poll() is None:
                    os.killpg(child.pid, signal.SIGTERM)
                    child.wait(timeout=3)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("--lease-panel", type=Path,
                        default=Path(__file__).with_name("lease-panel"))
    args = parser.parse_args()
    runtime = Path(os.environ["XDG_RUNTIME_DIR"])
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, stop)
    with (runtime / "cerro-dashboard.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with tempfile.TemporaryDirectory(dir=runtime) as work:
            run(args.config, args.lease_panel, Path(work))


if __name__ == "__main__":
    main()
