#!/usr/bin/env python3
"""Prepare one cached, dimmed and blurred copy of the current wallpaper."""
import hashlib
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from PIL import Image, ImageEnhance, ImageFilter, ImageOps


def main():
    home = Path.home()
    state = Path(os.environ.get("XDG_STATE_HOME", home / ".local/state"))
    cache = Path(os.environ.get("XDG_CACHE_HOME", home / ".cache")) / "cerro-touchpad"
    wallpaper = state / "caelestia/wallpaper"
    candidates = [wallpaper / "current"]
    try:
        candidates.append(Path((wallpaper / "path.txt").read_text().strip()).expanduser())
    except OSError:
        pass
    candidates.append(Path.home() / ".config/quickshell/caelestia/assets/wallpaper.webp")
    for candidate in candidates:
        if not candidate.is_file():
            continue
        stat = candidate.stat()
        key = hashlib.sha256(f"{candidate.resolve()}:{stat.st_mtime_ns}:v2".encode()).hexdigest()[:16]
        target = cache / f"wallpaper-{key}.jpg"
        if not target.exists():
            cache.mkdir(parents=True, exist_ok=True)
            try:
                with Image.open(candidate) as original:
                    image = ImageOps.fit(ImageOps.exif_transpose(original).convert("RGB"), (800, 360))
                image = ImageEnhance.Brightness(image.filter(ImageFilter.GaussianBlur(3.5))).enhance(0.36)
                with NamedTemporaryFile(dir=cache, delete=False) as file:
                    temporary = Path(file.name)
                    image.save(file, format="JPEG", quality=83)
                temporary.replace(target)
            except (OSError, ValueError):
                continue
        print(target.as_uri())
        return


if __name__ == "__main__":
    main()
