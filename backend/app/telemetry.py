"""Real-time operating conditions feed.

A live telemetry simulator standing in for the plant historian / DCS tags.
Each asset has sensor channels with baselines, limits and (for the assets in
the failure narrative) an active fault trend, so the readings visibly drift
toward their alarm thresholds over time. Values are a deterministic function
of wall-clock time, so every poll returns a fresh, evolving reading without
storing any state — and a breach is a real threshold crossing, not a flag.
"""
from __future__ import annotations

import math
import time
import zlib

# channel: (label, unit, baseline, noise, low_limit, high_limit)
# A "faulted" channel simply has a baseline set near/just past its alarm limit,
# so live oscillation crosses the threshold intermittently — realistic, and
# bounded (no runaway drift). A slow long-period breathe adds a live trend.
SENSORS = {
    "P-101A": [
        ("Vibration (outboard)", "mm/s", 7.5, 0.6, None, 7.1),   # sitting past alarm
        ("Seal flush flow", "%", 58, 2.5, 60, None),            # below low limit
        ("Bearing temp", "°C", 84, 3.0, None, 95),              # elevated, warn band
        ("Discharge pressure", "barg", 42, 0.4, 38, 46),
    ],
    "P-101B": [
        ("Vibration (outboard)", "mm/s", 3.1, 0.3, None, 7.1),
        ("Seal flush flow", "%", 86, 2.5, 60, None),            # healthy, slowly drifting
        ("Bearing temp", "°C", 63, 1.2, None, 95),
    ],
    "E-104": [
        ("Crude outlet temp", "°C", 229, 1.6, 232, None),        # below 232 → fouling deviation
        ("Shell-side dP", "bar", 1.18, 0.08, None, 1.4),         # warn band
        ("Skin temp (south saddle)", "°C", 72, 1.2, None, 120),
    ],
    "V-302": [
        ("Level", "%", 62, 4.0, 20, 90),
        ("Pressure", "barg", 5.2, 0.2, None, 6.0),
    ],
    "C-201": [
        ("Column dP", "mbar", 352, 14, None, 480),
        ("Overhead wash rate", "m3/hr", 9.2, 0.5, 8.0, None),
    ],
}


def _channel_value(asset, ch, now):
    label, unit, base, noise, lo, hi = ch
    # zlib.crc32 (not the builtin hash()) — Python randomises str hashing per
    # process (PYTHONHASHSEED), so the previous hash()-based seed made every
    # reading shift on every restart despite the "deterministic function of
    # wall-clock time" claim below.
    seed = zlib.crc32((asset + label).encode()) % 100
    osc = noise * math.sin(now / 7.0 + seed)             # fast live oscillation
    jitter = noise * 0.4 * math.sin(now / 1.7 + seed)    # secondary jitter
    breathe = noise * 0.5 * math.sin(now / 90.0 + seed)  # slow bounded trend
    value = base + osc + jitter + breathe
    status = "ok"
    breach = None
    if hi is not None and value >= hi:
        status, breach = "high", f"{label} {value:.1f}{unit} ≥ limit {hi}{unit}"
    elif lo is not None and value <= lo:
        status, breach = "low", f"{label} {value:.1f}{unit} ≤ limit {lo}{unit}"
    elif hi is not None and value >= hi - noise * 2.5:
        status = "warn"
    elif lo is not None and value <= lo + noise * 2.5:
        status = "warn"
    return {
        "label": label, "unit": unit, "value": round(value, 1),
        "low": lo, "high": hi, "status": status, "breach": breach,
    }


def snapshot(tags: list[str] | None = None) -> dict:
    now = time.time()
    out = {}
    for asset, channels in SENSORS.items():
        if tags and asset not in tags:
            continue
        readings = [_channel_value(asset, ch, now) for ch in channels]
        worst = "ok"
        for r in readings:
            if r["status"] in ("high", "low"):
                worst = "breach"
            elif r["status"] == "warn" and worst == "ok":
                worst = "warn"
        out[asset] = {"asset": asset, "status": worst, "channels": readings,
                      "ts": time.strftime("%H:%M:%S")}
    return out


def active_breaches() -> list[dict]:
    """Threshold crossings right now — consumed by the alerts engine."""
    breaches = []
    for asset, data in snapshot().items():
        for r in data["channels"]:
            if r["breach"]:
                breaches.append({
                    "asset": asset, "channel": r["label"], "detail": r["breach"],
                    "severity": "high" if r["status"] in ("high", "low") else "medium",
                })
    return breaches
