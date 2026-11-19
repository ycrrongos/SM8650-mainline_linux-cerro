#!/usr/bin/env python3
"""Return dashboard data as JSON, using the active MPRIS player."""
import bisect
import json
import re
import subprocess
from pathlib import Path


def command(*args):
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=2)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def lyrics(title, artist, position):
    name = f"{artist} - {title}"
    if not title or "/" in name:
        return ""
    path = Path.home() / ".local/share/cerro-touchpad/lyrics" / (name + ".lrc")
    if not path.is_file():
        return ""
    lines = []
    for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        stamps = list(re.finditer(r"\[(\d+):(\d+(?:\.\d+)?)\]", line))
        if stamps:
            text = line[stamps[-1].end():].strip()
            lines.extend((int(stamp[1]) * 60 + float(stamp[2]), text)
                         for stamp in stamps)
    lines.sort()
    index = bisect.bisect_right([start for start, _ in lines], position) - 1
    return lines[index][1] if index >= 0 else ""


def read_stats():
    mem = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        key, value = line.split(":", 1)
        mem[key] = int(value.split()[0])
    battery = Path("/sys/class/power_supply/qcom-battmgr-bat/capacity")
    title = command("playerctl", "metadata", "xesam:title")
    artist = command("playerctl", "metadata", "xesam:artist")
    position = float(command("playerctl", "position") or 0)
    return {
        "load": Path("/proc/loadavg").read_text().split()[0],
        "ram": round((mem["MemTotal"] - mem["MemAvailable"]) / 1048576, 1),
        "total": round(mem["MemTotal"] / 1048576, 1),
        "battery": battery.read_text().strip() if battery.exists() else "—",
        "title": title, "artist": artist, "lyric": lyrics(title, artist, position),
    }


if __name__ == "__main__":
    print(json.dumps(read_stats()))
