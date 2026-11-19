#!/usr/bin/env python3
"""Keep the stock Niri display paths and reserve DSI for a layer dashboard."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import time


PANEL = "DSI-1"
LAYER = "cerro-touchpad-dashboard"


def ipc(*args):
    return json.loads(subprocess.check_output(["niri", "msg", "--json", *args], text=True, timeout=2))


def action(*args):
    subprocess.run(["niri", "msg", "action", *args], check=True, timeout=2)


def position(output, x, y):
    subprocess.run(["niri", "msg", "output", output, "position", "set", str(x), str(y)],
                   check=True, timeout=2)


def stop(_signal, _frame):
    raise SystemExit(0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--external", default="DP-1")
    parser.add_argument("--seconds", type=int, default=0)
    parser.add_argument("--relay", action="store_true",
                        help="Start the installed system relay after the panel is ready")
    args = parser.parse_args()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, stop)
    runtime = Path(os.environ["XDG_RUNTIME_DIR"])
    with (runtime / "cerro-layer.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        run(args, runtime)


def run(args, runtime):
    outputs = ipc("outputs")
    phone = outputs.get(PANEL, {}).get("logical")
    external = outputs.get(args.external, {}).get("logical")
    if not phone or not external:
        raise SystemExit("Both the phone panel and external display must already be active.")

    source = Path(__file__).resolve().with_name("layer")
    readiness = runtime / "cerro-layer-ready"
    readiness.unlink(missing_ok=True)
    shell = subprocess.Popen(["qs", "-p", str(source)])
    separated = False
    try:
        deadline = time.monotonic() + 5
        while not any(entry["namespace"] == LAYER and entry["output"] == PANEL
                      for entry in ipc("layers")):
            if shell.poll() is not None or time.monotonic() > deadline:
                raise RuntimeError("The phone dashboard layer did not appear.")
            time.sleep(0.15)

        # Niri clips normal relative motion to the current output at gaps.
        position(PANEL, external["x"] + external["width"] + 8192, external["y"])
        separated = True
        position(args.external, external["x"], external["y"])
        layout = ipc("outputs")
        panel_rect = layout[PANEL]["logical"]
        external_rect = layout[args.external]["logical"]
        if panel_rect["x"] < external_rect["x"] + external_rect["width"] + 4096:
            raise RuntimeError("Niri did not retain a gap between outputs.")
        action("focus-monitor", args.external)
        readiness.touch()
        if args.relay:
            subprocess.run(["systemctl", "start", "cerro-layer-relay.service"],
                           check=True, timeout=5)
        print(f"Dashboard ready on {PANEL}, desktop focused on {args.external}", flush=True)
        deadline = time.monotonic() + args.seconds
        while shell.poll() is None and (not args.seconds or time.monotonic() < deadline):
            outputs = ipc("outputs")
            if not outputs.get(args.external, {}).get("logical"):
                break
            if not outputs.get(PANEL, {}).get("logical"):
                break
            readiness.touch()
            if args.relay and subprocess.run(
                ["systemctl", "is-active", "--quiet", "cerro-layer-relay.service"],
                timeout=2,
            ).returncode != 0:
                break
            workspaces = {ws["id"] for ws in ipc("workspaces") if ws["output"] == PANEL}
            for window in ipc("windows"):
                if window["workspace_id"] in workspaces:
                    action("move-window-to-monitor", "--id", str(window["id"]), args.external)
            if (ipc("focused-output") or {}).get("name") == PANEL:
                action("focus-monitor", args.external)
            time.sleep(0.35)
    finally:
        readiness.unlink(missing_ok=True)
        if shell.poll() is None:
            shell.terminate()
            shell.wait(timeout=3)
        if separated:
            position(PANEL, phone["x"], phone["y"])
            if ipc("outputs").get(args.external, {}).get("logical"):
                position(args.external, external["x"], external["y"])


if __name__ == "__main__":
    main()
