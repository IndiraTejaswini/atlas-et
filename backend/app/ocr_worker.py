"""Isolated OCR worker process.

Run as `python -m app.ocr_worker <image-path> [--json]`.
  default : prints recognised text to stdout
  --json  : prints JSON [{text, cx, cy, box}] so callers can bind text to
            regions of a drawing spatially.

Lives in its own process so a native onnxruntime fault can never take down the
API server — the parent simply sees a non-zero exit code.
"""
import json
import sys


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    as_json = "--json" in sys.argv
    if not args:
        return 2
    try:
        import numpy as np
        from PIL import Image
        from rapidocr_onnxruntime import RapidOCR
    except Exception:
        return 3
    try:
        engine = RapidOCR()
        img = Image.open(args[0]).convert("RGB")
        result, _ = engine(np.array(img))
        result = result or []
        if as_json:
            out = []
            for item in result:
                box, text = item[0], item[1]
                xs = [float(p[0]) for p in box]
                ys = [float(p[1]) for p in box]
                out.append({
                    "text": text,
                    "cx": sum(xs) / len(xs),
                    "cy": sum(ys) / len(ys),
                    "box": [min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)],
                })
            sys.stdout.write(json.dumps(out))
        else:
            sys.stdout.write("\n".join(item[1] for item in result))
    except Exception:
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
