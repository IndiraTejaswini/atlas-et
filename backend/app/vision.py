"""Computer vision for P&ID parsing and drawing digitisation.

Classical CV pipeline (OpenCV) that turns an engineering drawing image into
structured, graph-ready data — not just OCR'd text:

  1. Binarise and denoise the drawing.
  2. **Instrument bubbles** — Hough circle detection (P&ID instruments are drawn
     as circles/balloons).
  3. **Equipment symbols** — contour analysis filtered to rectangle-like shapes
     of plausible size (vessels, exchangers, pumps drawn as boxes).
  4. **Process lines** — probabilistic Hough transform for the piping runs.
  5. **Tag OCR** — crop each detected symbol's neighbourhood and OCR it, so a
     tag is bound to the symbol it labels rather than floating in a text blob.
  6. **Connectivity** — a line whose endpoints land near two symbols becomes a
     `connected_to` relation, giving real drawing topology.

Output feeds the knowledge graph as equipment nodes plus connectivity edges,
and an annotated overlay image is returned so the detection is visible.

Classical CV (not a trained detector) is a deliberate choice: it needs no
annotated P&ID training corpus, runs on CPU in milliseconds, and is fully
inspectable — every detection can be explained geometrically.
"""
from __future__ import annotations

import base64
import logging
import math

logger = logging.getLogger("atlas.vision")

_AVAILABLE = None


def available() -> bool:
    global _AVAILABLE
    if _AVAILABLE is None:
        try:
            import cv2  # noqa: F401
            import numpy  # noqa: F401
            _AVAILABLE = True
        except Exception:
            logger.info("OpenCV not importable — P&ID vision endpoints will report unavailable", exc_info=True)
            _AVAILABLE = False
    return _AVAILABLE


def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


MAX_PIXELS = 40_000_000  # ~40MP: generous for a scanned drawing, bounds a decompression-bomb image


def parse_pid(data: bytes, ocr_tags: bool = True) -> dict:
    """Detect symbols, lines and tags in a P&ID image."""
    if not available():
        return {"error": "OpenCV not installed", "symbols": [], "lines": [], "connections": []}

    import cv2
    import numpy as np

    arr = np.frombuffer(data, np.uint8)
    # Read dimensions only first — cv2.imdecode has no built-in decompression-
    # bomb guard (unlike PIL's default MAX_IMAGE_PIXELS), so a small,
    # highly-compressed file could otherwise force a huge allocation before
    # we get a chance to reject it.
    header = cv2.imdecode(arr, cv2.IMREAD_REDUCED_COLOR_8) if len(arr) else None
    if header is not None:
        est_h, est_w = header.shape[0] * 8, header.shape[1] * 8
        if est_h * est_w > MAX_PIXELS:
            return {"error": f"Image too large ({est_w}x{est_h} est.) — max {MAX_PIXELS:,} px",
                    "symbols": [], "lines": [], "connections": []}
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return {"error": "Unreadable image", "symbols": [], "lines": [], "connections": []}
    h, w = img.shape[:2]
    if h * w > MAX_PIXELS:
        return {"error": f"Image too large ({w}x{h}) — max {MAX_PIXELS:,} px",
                "symbols": [], "lines": [], "connections": []}
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    binary = cv2.adaptiveThreshold(blur, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                                   cv2.THRESH_BINARY_INV, 25, 10)

    symbols = []

    # --- 1. Instrument bubbles (circles) ---
    circles = cv2.HoughCircles(blur, cv2.HOUGH_GRADIENT, dp=1.2, minDist=40,
                               param1=100, param2=32,
                               minRadius=int(min(h, w) * 0.012),
                               maxRadius=int(min(h, w) * 0.06))
    if circles is not None:
        # OpenCV 4 returns (1, N, 3); OpenCV 5 returns (N, 3) — normalise both.
        for c in np.asarray(circles).reshape(-1, 3):
            x, y, r = int(round(c[0])), int(round(c[1])), int(round(c[2]))
            symbols.append({"kind": "instrument", "shape": "circle",
                            "cx": x, "cy": y, "r": r,
                            "bbox": [x - r, y - r, 2 * r, 2 * r]})

    # --- 2. Equipment symbols (rectangle-like contours) ---
    # RETR_LIST (not RETR_EXTERNAL): equipment boxes are nested inside the
    # drawing's border frame, so outermost-only retrieval would miss them all.
    contours, _ = cv2.findContours(binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    img_area = h * w
    seen_boxes = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < img_area * 0.0015 or area > img_area * 0.25:
            continue
        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.035 * peri, True)
        if len(approx) < 4 or len(approx) > 6:
            continue
        x, y, bw, bh = cv2.boundingRect(approx)
        aspect = bw / float(bh) if bh else 0
        if not (0.25 <= aspect <= 4.5):
            continue
        rect_fill = area / float(bw * bh) if bw * bh else 0
        if rect_fill < 0.55:            # reject ragged blobs / text clusters
            continue
        cx, cy = x + bw // 2, y + bh // 2
        if any(s["kind"] == "instrument" and _dist((cx, cy), (s["cx"], s["cy"])) < s["r"] * 1.5
               for s in symbols):
            continue
        # RETR_LIST yields both the inner and outer edge of a drawn outline —
        # collapse near-duplicate boxes to one symbol.
        if any(_dist((cx, cy), (pcx, pcy)) < 20 and abs(bw - pbw) < 25 and abs(bh - pbh) < 25
               for pcx, pcy, pbw, pbh in seen_boxes):
            continue
        seen_boxes.append((cx, cy, bw, bh))
        symbols.append({"kind": "equipment", "shape": "rect",
                        "cx": cx, "cy": cy, "r": max(bw, bh) // 2,
                        "bbox": [x, y, bw, bh]})

    # --- 3. Process lines ---
    edges = cv2.Canny(gray, 60, 160, apertureSize=3)
    raw_lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=60,
                                minLineLength=int(min(h, w) * 0.10), maxLineGap=12)
    lines = []
    if raw_lines is not None:
        # OpenCV 4 returns (N, 1, 4); OpenCV 5 returns (N, 4) — normalise both.
        for l in np.asarray(raw_lines).reshape(-1, 4):
            x1, y1, x2, y2 = (int(v) for v in l)
            ang = abs(math.degrees(math.atan2(y2 - y1, x2 - x1))) % 180
            # keep orthogonal runs (P&ID piping is drawn axis-aligned)
            if min(ang, abs(ang - 90), abs(ang - 180)) > 8:
                continue
            # drop segments that merely trace a symbol's own border
            mid = ((x1 + x2) / 2, (y1 + y2) / 2)
            if any(_inside(mid, s["bbox"], pad=2) for s in symbols if s["shape"] == "rect"):
                continue
            lines.append({"x1": x1, "y1": y1, "x2": x2, "y2": y2})
    lines = _dedupe_lines(lines)

    # --- 4. Tag OCR: ONE full-image pass, then bind each text box to the
    #        nearest symbol spatially (one engine load, not one per symbol).
    ocr_boxes = []
    if ocr_tags and symbols:
        from . import ocr as ocr_mod
        if ocr_mod.available():
            ok, enc = cv2.imencode(".png", img)
            if ok:
                ocr_boxes = ocr_mod.ocr_image_boxes(enc.tobytes())
            for tb in ocr_boxes:
                tag = _pick_tag(tb.get("text", ""))
                if not tag:
                    continue
                idx = _nearest_symbol((tb["cx"], tb["cy"]), symbols, max_frac=2.4)
                if idx is not None and not symbols[idx].get("tag"):
                    symbols[idx]["tag"] = tag
                    symbols[idx]["ocr_text"] = " ".join(tb["text"].split())[:80]

    # --- 5. Connectivity: line endpoints landing near two symbols ---
    connections = []
    for ln in lines:
        a = _nearest_symbol((ln["x1"], ln["y1"]), symbols)
        b = _nearest_symbol((ln["x2"], ln["y2"]), symbols)
        if a is not None and b is not None and a != b:
            pair = tuple(sorted((a, b)))
            if not any(c["pair"] == list(pair) for c in connections):
                connections.append({
                    "pair": list(pair),
                    "from": symbols[pair[0]].get("tag") or f"symbol_{pair[0]}",
                    "to": symbols[pair[1]].get("tag") or f"symbol_{pair[1]}",
                })

    overlay = _render_overlay(img, symbols, lines)
    return {
        "width": w, "height": h,
        "symbols": symbols,
        "lines": lines,
        "connections": connections,
        "tags_found": sorted({s["tag"] for s in symbols if s.get("tag")}),
        "ocr_text_boxes": len(ocr_boxes),
        "counts": {
            "instruments": len([s for s in symbols if s["kind"] == "instrument"]),
            "equipment": len([s for s in symbols if s["kind"] == "equipment"]),
            "lines": len(lines),
            "connections": len(connections),
            "tagged_symbols": len([s for s in symbols if s.get("tag")]),
        },
        "overlay_png_b64": overlay,
    }


def pid_to_document_body(result: dict, source: str) -> str:
    """Render a parse_pid() result as a markdown document body so its tags and
    connectivity flow through the normal ingestion pipeline — entity
    extraction picks up the equipment tags, and graph.build() turns each
    "A connected_to B" line into a real connected_to edge (see graph.py) —
    exactly like any other document, rather than a response the frontend
    displays once and discards."""
    tags = result.get("tags_found") or []
    conns = result.get("connections") or []
    counts = result.get("counts", {})
    lines = [
        f"Computer-vision digitisation of `{source}`: {counts.get('equipment', 0)} equipment "
        f"symbols, {counts.get('instruments', 0)} instrument balloons, {counts.get('lines', 0)} "
        f"process lines detected; {counts.get('tagged_symbols', 0)} symbols matched to a tag by OCR.",
        "",
        "## Equipment tags detected",
        "\n".join(f"- {t}" for t in tags) if tags else "*(none recognised)*",
        "",
        "## Connections",
        "\n".join(f"- {c['from']} connected_to {c['to']}" for c in conns)
        if conns else "*(no connectivity inferred)*",
    ]
    return "\n".join(lines)


def _inside(pt, bbox, pad=0):
    x, y, bw, bh = bbox
    return (x + pad) <= pt[0] <= (x + bw - pad) and (y + pad) <= pt[1] <= (y + bh - pad)


def _dedupe_lines(lines, tol=12):
    kept = []
    for ln in lines:
        dup = False
        for k in kept:
            if (_dist((ln["x1"], ln["y1"]), (k["x1"], k["y1"])) < tol
                    and _dist((ln["x2"], ln["y2"]), (k["x2"], k["y2"])) < tol):
                dup = True
                break
        if not dup:
            kept.append(ln)
    return kept


def _crop_region(img, s, h, w):
    x, y, bw, bh = s["bbox"]
    pad = int(max(bw, bh) * 0.45) + 8
    x0, y0 = max(0, x - pad), max(0, y - pad)
    x1, y1 = min(w, x + bw + pad), min(h, y + bh + pad)
    if x1 - x0 < 10 or y1 - y0 < 10:
        return None
    return img[y0:y1, x0:x1]


_TAG_PATTERNS = __import__("re").compile(
    r"\b(?:PSV|MOV|TK|CML|HX|[PEVCKIFLT])-?\s?\d{2,4}[A-Z]?\b", __import__("re").I)


def _pick_tag(text: str):
    if not text:
        return None
    m = _TAG_PATTERNS.search(text.replace("\n", " "))
    if not m:
        return None
    return m.group(0).upper().replace(" ", "").replace("--", "-")


def _nearest_symbol(pt, symbols, max_frac=1.9):
    best, best_d = None, None
    for i, s in enumerate(symbols):
        d = _dist(pt, (s["cx"], s["cy"]))
        if d <= max(s["r"] * max_frac, 26) and (best_d is None or d < best_d):
            best, best_d = i, d
    return best


def _render_overlay(img, symbols, lines) -> str:
    import cv2

    out = img.copy()
    for ln in lines:
        cv2.line(out, (ln["x1"], ln["y1"]), (ln["x2"], ln["y2"]), (219, 120, 42), 2)
    for s in symbols:
        x, y, bw, bh = s["bbox"]
        color = (52, 104, 235) if s["kind"] == "instrument" else (42, 163, 12)
        if s["shape"] == "circle":
            cv2.circle(out, (s["cx"], s["cy"]), s["r"], color, 2)
        else:
            cv2.rectangle(out, (x, y), (x + bw, y + bh), color, 2)
        if s.get("tag"):
            cv2.putText(out, s["tag"], (x, max(14, y - 6)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2, cv2.LINE_AA)
    ok, buf = cv2.imencode(".png", out)
    return base64.b64encode(buf.tobytes()).decode() if ok else ""
