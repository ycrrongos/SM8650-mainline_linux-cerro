#!/usr/bin/env python3
"""Expose the relay's bounded datagrams as lines for Quickshell."""
import fcntl
import os
from pathlib import Path
import signal
import socket


def main():
    path = Path(os.environ["XDG_RUNTIME_DIR"]) / os.environ.get("CERRO_RIPPLE_SOCKET", "cerro-ripple.sock")
    signal.signal(signal.SIGTERM, lambda *_: quit_stream())
    with path.with_suffix(".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        path.unlink(missing_ok=True)
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as receiver:
                receiver.bind(str(path))
                path.chmod(0o600)
                while True:
                    try:
                        x, y = map(float, receiver.recv(64).split())
                    except ValueError:
                        continue
                    if 0 <= x <= 1 and 0 <= y <= 1:
                        print(x, y, flush=True)
        finally:
            path.unlink(missing_ok=True)


def quit_stream():
    raise SystemExit(0)


if __name__ == "__main__":
    main()
