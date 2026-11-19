#!/usr/bin/env python3
"""Generate atomic landscape dashboard snapshots for the DRM lease client."""
import argparse
from datetime import datetime
from pathlib import Path
import subprocess
import threading
import time

from PIL import Image, ImageDraw, ImageFont

from telemetry import read_stats

WIDTH, HEIGHT = 960, 430


class Spectrum:
    def __init__(self, config):
        self.bands = [0] * 32
        self.cava = subprocess.Popen(
            ["cava", "-p", str(config)], stdout=subprocess.PIPE, text=True,
        )
        threading.Thread(target=self.read, daemon=True).start()

    def read(self):
        for line in self.cava.stdout:
            try:
                values = [int(value) for value in line.strip().strip(";").split(";")]
            except ValueError:
                continue
            if len(values) == 32:
                self.bands = [max(0, min(1000, value)) for value in values]


def draw_frame(stats, bands, fonts):
    image = Image.new("RGB", (WIDTH, HEIGHT), "#10141d")
    draw = ImageDraw.Draw(image)

    def line(text, y, size, color):
        font = fonts[size]
        while len(text) > 1 and draw.textlength(text, font=font) > WIDTH - 96:
            text = text[:-2] + "…"
            if text == "…":
                break
        draw.text((48, y), text, font=font, fill=color)

    line(datetime.now().strftime("%H:%M   ·   %m/%d"), 32, 58, "#e1e8fd")
    line(f"SM8650  ·  LOAD {stats['load']}  ·  RAM {stats['ram']}/{stats['total']} GiB"
         f"  ·  BAT {stats['battery']}%", 117, 22, "#a8b4ce")
    line(stats["title"] or "未播放音乐", 167, 34, "#e1e8fd")
    line(stats["artist"], 219, 22, "#a8b4ce")
    for index, value in enumerate(bands):
        x = 48 + index * 27
        height = max(3, round(value * 78 / 1000))
        draw.rounded_rectangle((x, 340 - height, x + 18, 340), radius=4, fill="#9fbaff")
    line(stats["lyric"] or "暂无同步歌词", 366, 25, "#c4d5ff")
    return image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--font", default=subprocess.check_output(
        ["fc-match", "-f", "%{file}", "Noto Sans CJK SC"], text=True))
    args = parser.parse_args()
    fonts = {size: ImageFont.truetype(args.font, size) for size in (22, 25, 34, 58)}
    temporary = args.image.with_suffix(".png.tmp")
    spectrum = None if args.once else Spectrum(Path(__file__).with_name("cava.conf"))
    try:
        updated = 0.0
        while True:
            now = time.monotonic()
            if now >= updated:
                stats = read_stats()
                updated = now + 1
            bands = spectrum.bands if spectrum else [0] * 32
            draw_frame(stats, bands, fonts).save(temporary, format="PNG")
            temporary.replace(args.image)
            if args.once:
                return
            time.sleep(1 / 16)
    finally:
        if spectrum:
            spectrum.cava.terminate()
            spectrum.cava.wait()
        temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
