#!/usr/bin/env python3
"""Build chainradar.icns on macOS from the existing .ico (CI uses iconutil)."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ICO = ROOT / "web3_radar" / "resources" / "chainradar.ico"
ICNS = ROOT / "web3_radar" / "resources" / "chainradar.icns"
ICONSET = ROOT / "build" / "ChainRadar.iconset"


def _largest_frame(img: Image.Image) -> Image.Image:
    frames: list[Image.Image] = []
    n = getattr(img, "n_frames", 1)
    for i in range(n):
        try:
            img.seek(i)
        except EOFError:
            break
        frames.append(img.copy())
    if not frames:
        frames = [img.copy()]
    best = max(frames, key=lambda im: im.size[0] * im.size[1])
    return best.convert("RGBA")


def main() -> int:
    if sys.platform != "darwin":
        print("skip icns: not macOS")
        return 0
    if not ICO.is_file():
        print("missing", ICO)
        return 1
    if not shutil.which("iconutil"):
        print("iconutil not found; PyInstaller will fall back to .ico")
        return 0
    src = _largest_frame(Image.open(ICO))
    if ICONSET.exists():
        shutil.rmtree(ICONSET)
    ICONSET.mkdir(parents=True, exist_ok=True)
    for size in (16, 32, 64, 128, 256, 512, 1024):
        resized = src.resize((size, size), Image.Resampling.LANCZOS)
        resized.save(ICONSET / f"icon_{size}x{size}.png")
        if size >= 32:
            resized.save(ICONSET / f"icon_{size // 2}x{size // 2}@2x.png")
    subprocess.check_call(["iconutil", "-c", "icns", str(ICONSET), "-o", str(ICNS)])
    print("wrote", ICNS, "size", ICNS.stat().st_size)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
