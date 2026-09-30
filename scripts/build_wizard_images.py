from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SIDE_W, SIDE_H = 164, 314
SMALL_W, SMALL_H = 55, 58

BG_DARK = (28, 28, 28)
BG_LIGHT = (255, 255, 255)
ACCENT_YELLOW = (255, 209, 71)
TEXT_PRIMARY = (255, 255, 255)
TEXT_SECONDARY = (180, 180, 180)
TEXT_TERTIARY = (110, 110, 110)


def _load_branded_icon() -> Image.Image:
    repo_root = Path(__file__).resolve().parents[1]
    ico = repo_root / "assets" / "icon-branded.ico"
    if not ico.exists():
        raise FileNotFoundError(f"Missing {ico} -- run scripts/regenerate_branded_icon.py first")
    img = Image.open(ico)
    sizes = img.info.get("sizes")
    if sizes:
        largest = max(sizes, key=lambda s: s[0] * s[1])
        try:
            from PIL import IcoImagePlugin  # type: ignore[import-untyped]
            with open(ico, "rb") as fh:
                ico_img = IcoImagePlugin.IcoFile(fh)
                img = ico_img.getimage(largest)
                img.load()
        except (ImportError, AttributeError, OSError):
            img.load()
    return img.convert("RGBA")


def _try_load_font(size: int, *, bold: bool = False):
    candidates = [
        "C:\\Windows\\Fonts\\segoeui.ttf" if not bold else "C:\\Windows\\Fonts\\segoeuib.ttf",
        "/mnt/c/Windows/Fonts/segoeui.ttf"
        if not bold
        else "/mnt/c/Windows/Fonts/segoeuib.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def _draw_centered_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    y: int,
    width: int,
    font,
    color: tuple[int, int, int],
) -> None:
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    x = (width - text_w) // 2
    draw.text((x, y), text, fill=color, font=font)


def build_side_image(out_path: Path) -> None:
    canvas = Image.new("RGB", (SIDE_W, SIDE_H), BG_DARK)
    draw = ImageDraw.Draw(canvas)

    icon = _load_branded_icon()
    icon_size = 88
    icon_resized = icon.resize((icon_size, icon_size), Image.Resampling.LANCZOS)
    icon_x = (SIDE_W - icon_size) // 2
    icon_y = 38
    canvas.paste(icon_resized, (icon_x, icon_y), icon_resized)

    mark_path = Path(__file__).resolve().parents[1] / "assets" / "brand" / "speech2anywhere-wortmarke-dunkel.png"
    mark = Image.open(mark_path).convert("RGBA")
    mark_w = SIDE_W - 16
    mark = mark.resize((mark_w, round(mark.height * mark_w / mark.width)), Image.Resampling.LANCZOS)
    canvas.paste(mark, ((SIDE_W - mark_w) // 2, icon_y + icon_size + 16), mark)

    subtitle_font = _try_load_font(11)
    line1 = "Taste halten,"
    line2 = "sprechen, fertig."
    _draw_centered_text(draw, line1, icon_y + icon_size + 56, SIDE_W, subtitle_font, TEXT_SECONDARY)
    _draw_centered_text(draw, line2, icon_y + icon_size + 72, SIDE_W, subtitle_font, TEXT_SECONDARY)

    footer_font = _try_load_font(9)
    _draw_centered_text(draw, "digitalroots", SIDE_H - 22, SIDE_W, footer_font, TEXT_TERTIARY)

    canvas.convert("RGB").save(out_path, "BMP")
    print(f"wrote {out_path} ({SIDE_W}x{SIDE_H} px, {out_path.stat().st_size:,} bytes)")


def build_small_image(out_path: Path) -> None:
    canvas = Image.new("RGB", (SMALL_W, SMALL_H), BG_LIGHT)

    icon = _load_branded_icon()
    icon_size = min(SMALL_W, SMALL_H) - 8
    icon_resized = icon.resize((icon_size, icon_size), Image.Resampling.LANCZOS)
    icon_x = (SMALL_W - icon_size) // 2
    icon_y = (SMALL_H - icon_size) // 2
    canvas.paste(icon_resized, (icon_x, icon_y), icon_resized)

    canvas.convert("RGB").save(out_path, "BMP")
    print(f"wrote {out_path} ({SMALL_W}x{SMALL_H} px, {out_path.stat().st_size:,} bytes)")


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    assets = repo_root / "assets"
    assets.mkdir(parents=True, exist_ok=True)

    build_side_image(assets / "wizard-side.bmp")
    build_small_image(assets / "wizard-small.bmp")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
