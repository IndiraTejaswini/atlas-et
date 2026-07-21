"""OCR for scanned forms and image-only PDFs.

Uses RapidOCR (ONNX, pure-pip, no system binary, offline CPU). The recognition
call runs in an **isolated subprocess** (`app.ocr_worker`): native ML runtimes
can hard-fault, and a fault must never take down the API server — the parent
just sees a non-zero exit code and degrades to "no text extracted".

If the engine isn't installed the functions report that cleanly rather than
failing — the same optional-capability pattern as Claude synthesis.
"""
from __future__ import annotations

import importlib.util
import io
import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path

logger = logging.getLogger("atlas.ocr")

_BACKEND_DIR = Path(__file__).resolve().parent.parent
_TIMEOUT_S = 180


def available() -> bool:
    """True if the OCR engine is installed (does not load the models)."""
    return all(importlib.util.find_spec(m) is not None
               for m in ("rapidocr_onnxruntime", "PIL", "numpy"))


def _run_worker(image_path: str, as_json: bool = False) -> str:
    cmd = [sys.executable, "-m", "app.ocr_worker", image_path]
    if as_json:
        cmd.append("--json")
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=_TIMEOUT_S,
                              cwd=str(_BACKEND_DIR))
    except subprocess.TimeoutExpired:
        logger.warning("OCR worker timed out after %ss on %s", _TIMEOUT_S, image_path)
        return ""
    except OSError:
        logger.warning("OCR worker failed to start", exc_info=True)
        return ""
    if proc.returncode != 0:
        logger.warning("OCR worker exited %s: %s", proc.returncode,
                       proc.stderr.decode("utf-8", errors="replace")[:500])
        return ""
    return proc.stdout.decode("utf-8", errors="replace").strip()


def ocr_image_bytes(data: bytes, suffix: str = ".png") -> str:
    if not available():
        return ""
    fd, path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        return _run_worker(path)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def ocr_image_boxes(data: bytes, suffix: str = ".png") -> list[dict]:
    """OCR an image and return [{text, cx, cy, box}] so callers can bind text
    to regions of a drawing spatially. One engine load, one pass."""
    if not available():
        return []
    import json as _json

    fd, path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        raw = _run_worker(path, as_json=True)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
    if not raw:
        return []
    try:
        return _json.loads(raw)
    except ValueError:
        return []


def ocr_pdf_pages(data: bytes, max_pages: int = 5) -> str:
    """Extract embedded images from an image-only PDF and OCR them."""
    if not available():
        return ""
    try:
        from pypdf import PdfReader
    except Exception:
        return ""
    try:
        reader = PdfReader(io.BytesIO(data))
    except Exception:
        return ""
    out = []
    for i, page in enumerate(reader.pages[:max_pages]):
        try:
            images = list(getattr(page, "images", []))
        except Exception:
            images = []
        for img in images:
            text = ocr_image_bytes(img.data, suffix=".png")
            if text.strip():
                out.append(f"## Page {i + 1} (OCR)\n\n{text}")
    return "\n\n".join(out)
