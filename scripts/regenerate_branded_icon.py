from __future__ import annotations
from pathlib import Path
from PIL import Image

ICO_SIZES = [16, 20, 24, 32, 40, 48, 64, 128, 256]

ASSETS = Path(__file__).resolve().parent.parent / "assets"
SRC = ASSETS / "brand" / "speech2anywhere-logo-1024.png"
TARGETS = [ASSETS / "icon-branded.ico", ASSETS / "icon.ico"]


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"Brand logo not found: {SRC}")

    master = Image.open(SRC).convert("RGBA")
    frames = [master.resize((s, s), Image.Resampling.LANCZOS) for s in sorted(ICO_SIZES, reverse=True)]
    for dst in TARGETS:
        frames[0].save(
            dst, format="ICO", sizes=[(s, s) for s in ICO_SIZES], append_images=frames[1:],
        )
        print(f"OK {dst} ({dst.stat().st_size / 1024:.1f} KB, {len(frames)} sizes)")


if __name__ == "__main__":
    main()
