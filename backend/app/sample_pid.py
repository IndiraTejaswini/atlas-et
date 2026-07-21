"""Generates a representative P&ID drawing for the vision demo.

Draws Unit 300's crude charge circuit in conventional P&ID style — equipment as
labelled rectangles, instruments as balloons, orthogonal process lines — so the
CV pipeline can be demonstrated (and tested) without shipping a licensed
engineering drawing. Uploaded real P&IDs go through the identical pipeline.
"""
from __future__ import annotations

import io

W, H = 1400, 820

EQUIPMENT = [
    ("P-101A", 120, 470, 170, 110),
    ("P-101B", 120, 640, 170, 110),
    ("E-104", 470, 250, 220, 130),
    ("C-201", 850, 170, 150, 330),
    ("V-302", 1130, 200, 180, 120),
    ("TK-305", 1130, 560, 190, 130),
]

INSTRUMENTS = [
    ("PI-101", 330, 430), ("FI-118", 330, 600), ("TI-104", 600, 180),
    ("LI-302", 1090, 150), ("PSV-1104", 1230, 120), ("TI-201", 800, 120),
]

LINES = [
    (290, 525, 470, 525), (290, 695, 470, 695),        # pumps → header
    (470, 525, 470, 380),                                # header up to exchanger
    (690, 315, 850, 315),                                # exchanger → column
    (925, 170, 925, 120), (925, 120, 1220, 120),         # column overhead
    (1220, 120, 1220, 200),                              # to accumulator
    (1310, 260, 1360, 260), (1225, 320, 1225, 560),      # accumulator → tank
    (1000, 400, 1130, 400), (1130, 400, 1130, 560),      # column bottoms → tank
]


def render_png() -> bytes:
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)

    # title block
    d.rectangle([20, 20, W - 20, H - 20], outline="black", width=2)
    d.text((40, 34), "P&ID  UNIT 300 - CRUDE DISTILLATION   DWG-300-001  REV 4", fill="black")

    # process lines first (so symbols sit on top)
    for x1, y1, x2, y2 in LINES:
        d.line([x1, y1, x2, y2], fill="black", width=3)

    # equipment as labelled rectangles
    for tag, x, y, w, h in EQUIPMENT:
        d.rectangle([x, y, x + w, y + h], outline="black", width=3, fill="white")
        d.text((x + 12, y + h // 2 - 6), tag, fill="black")

    # instrument balloons
    for tag, cx, cy in INSTRUMENTS:
        r = 34
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline="black", width=3, fill="white")
        d.text((cx - 28, cy - 6), tag, fill="black")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
