"""Named-key audit trail for mutating actions.

Not a full per-user identity system — API keys remain shared secrets per
role (see main.py's RBAC), not individual accounts with their own
credentials. What this closes is the narrower, honestly-scoped gap: nothing
previously recorded *which* configured key did *what*, *when*. Give a key
an optional display name in ATLAS_API_KEYS ("key:role:name") and every
mutating action it takes — ingest, alert ack/unack, webhook test — is
written here with that name attached; an unnamed key still gets logged,
identified by a short masked prefix rather than either the raw secret or an
indistinguishable "operator" for every caller.

Persisted as JSON Lines (append-only, one action per line) — the natural
shape for an audit log, and simpler to reason about under concurrent writes
than rewriting a single JSON array on every action.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path

logger = logging.getLogger("atlas.audit")

_LOG_PATH = Path(__file__).resolve().parent.parent / "data" / "audit_log.jsonl"
_MAX_RETURNED = 500  # GET /api/audit's cap — an operational tail view, not a paginated export
_lock = threading.Lock()


def log_action(actor: str, role: str, action: str, detail: str = "") -> None:
    """Append one audit entry. Best-effort — a disk problem here must not
    fail the action being audited (same "log and continue" pattern as
    alerts.py's ack/dispatch stores); the action already happened by the
    time this is called."""
    entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "actor": actor, "role": role, "action": action, "detail": detail,
    }
    try:
        with _lock:
            _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
    except OSError:
        logger.warning("could not write audit log entry (non-fatal): %s", entry, exc_info=True)


def recent(limit: int = 200) -> list[dict]:
    """Most-recent-first tail of the audit log."""
    limit = max(1, min(limit, _MAX_RETURNED))
    try:
        if not _LOG_PATH.exists():
            return []
        lines = _LOG_PATH.read_text(encoding="utf-8").splitlines()
    except OSError:
        logger.warning("could not read audit log (non-fatal)", exc_info=True)
        return []
    out = []
    for line in reversed(lines[-_MAX_RETURNED:]):
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
        if len(out) >= limit:
            break
    return out
