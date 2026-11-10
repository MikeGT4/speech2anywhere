# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations

import math

from PIL import Image, ImageDraw

INK = (29, 29, 27, 255)
GREEN = (47, 168, 79, 255)
WHITE = (255, 255, 255, 255)

SPIKES = 9
VALLEY = 0.70
CORNER_SHARE = 0.56
SOLO_SHARE = 22.4 / 24
EDGE_SHARE = 0.045
ARROW_HEAD = 0.22
ARROW_STEM = 0.13
CANVAS = 512


def _star(cx: float, cy: float, radius: float) -> list[tuple[float, float]]:
    points = []
    for i in range(2 * SPIKES):
        r = radius if i % 2 == 0 else radius * VALLEY
        angle = -math.pi / 2 + i * math.pi / SPIKES
        points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    return points


def _render(size: int, centre: float, dia: float) -> Image.Image:
    edge = dia * EDGE_SHARE / CORNER_SHARE
    head = dia * ARROW_HEAD
    stem = dia * ARROW_STEM
    canvas = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    pen = ImageDraw.Draw(canvas)
    pen.polygon(_star(centre, centre, dia / 2), fill=INK)
    pen.polygon(_star(centre, centre, dia / 2 - edge), fill=GREEN)
    pen.polygon(
        [
            (centre, centre - 1.25 * head),
            (centre + 1.05 * head, centre - 0.05 * head),
            (centre - 1.05 * head, centre - 0.05 * head),
        ],
        fill=WHITE,
    )
    pen.rectangle(
        (centre - stem / 2, centre - 0.15 * head, centre + stem / 2, centre + 1.15 * head),
        fill=WHITE,
    )
    return canvas.resize((size, size), Image.Resampling.LANCZOS)


def corner(size: int) -> Image.Image:
    dia = CANVAS * CORNER_SHARE
    return _render(size, CANVAS - dia / 2, dia)


def solo(size: int) -> Image.Image:
    return _render(size, CANVAS / 2, CANVAS * SOLO_SHARE)
