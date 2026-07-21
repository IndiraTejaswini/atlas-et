"""Compliance intelligence: maps regulatory requirements against what the
documents actually say, and computes gap status from dates found *in* the
documents — nothing is hardcoded to a status.

Every check below scans documents by *type and content shape* (a table row,
a "Next inspection due:" line, a `review_due` frontmatter field, an "— OPEN"
action item) rather than by literal document id. Point this at a different
plant's corpus — different ids, different specific dates — and the same
checks still fire wherever the same shapes appear, instead of only ever
finding the six documents this seed corpus happens to use.
"""
from __future__ import annotations

import logging
import re
from datetime import date, datetime

logger = logging.getLogger("atlas.compliance")

DATE_RE = r"(\d{4}-\d{2}-\d{2})"


def _parse(d: str) -> date | None:
    try:
        return datetime.strptime(d.strip(), "%Y-%m-%d").date()
    except (ValueError, AttributeError):
        return None


def _status_from_due(due: date | None, today: date, warn_days: int = 45):
    if due is None:
        return "no_evidence", None
    delta = (due - today).days
    if delta < 0:
        return "gap", -delta      # overdue by N days
    if delta <= warn_days:
        return "due_soon", delta  # due in N days
    return "compliant", delta


def _primary_equipment(doc) -> list[str]:
    return [t.strip() for t in doc.meta.get("equipment", "").split(",") if t.strip()]


def _consequence_ref(target_id: str, docs: list) -> tuple[str, str] | None:
    """Find an incident/near-miss document that names `target_id` alongside
    language suggesting it was a contributing factor — discovered per-document
    instead of asserted for one specific id."""
    pattern = re.compile(r"stale|root cause|out-of-date|contributing factor", re.I)
    for d in docs:
        if d.type == "incident" and target_id in d.body and pattern.search(d.body):
            return d.id, d.title
    return None


def evaluate(docs: list, today: date | None = None) -> dict:
    today = today or date.today()
    findings = []

    def add(check_id, title, standard, severity, status, detail, evidence, equipment=None):
        findings.append({
            "id": check_id, "title": title, "standard": standard, "severity": severity,
            "status": status, "detail": detail, "evidence": evidence,
            "equipment": equipment or [],
        })

    # --- PSV test intervals (OISD-STD-132), from any relief-valve register
    # table — a `| PSV-nnnn | protects | ... | last | due |` row in any doc.
    psv_row_re = re.compile(
        r"\|\s*(PSV-\d+)\s*\|\s*([^|]+)\|[^|]*\|\s*" + DATE_RE + r"\s*\|\s*" + DATE_RE
    )
    for doc in docs:
        for row in psv_row_re.finditer(doc.body):
            tag, protects, last, due = row.group(1), row.group(2).strip(), row.group(3), row.group(4)
            status, days = _status_from_due(_parse(due), today)
            detail = {
                "gap": f"Test overdue by {days} days (last tested {last}). Protects {protects}.",
                "due_soon": f"Test due in {days} days ({due}). Protects {protects}.",
                "compliant": f"Tested {last}; next due {due}.",
            }.get(status, "No test record found.")
            add(f"psv-{tag}", f"{tag} relief valve test", "OISD-STD-132",
                "critical" if status == "gap" else "high", status, detail, [doc.id], [tag])

    # --- Statutory pressure-vessel inspection (Factories Act Sec 31 /
    # OISD-STD-128), from any "<TAG> external statutory inspection ... due
    # YYYY-MM" sentence in any document — tag and doc are both parsed, not
    # bound to a specific one.
    statutory_re = re.compile(
        r"\b([A-Z]{1,4}-\d{2,4}[A-Z]?)\s+external statutory inspection.*?due (\d{4}-\d{2})"
    )
    for doc in docs:
        for m in statutory_re.finditer(doc.body):
            tag, ym = m.group(1), m.group(2)
            due = _parse(ym + "-01")
            status, days = _status_from_due(due, today)
            detail = (f"Statutory external inspection was due {ym}"
                      + (f" — overdue by {days} days." if status == "gap" else "."))
            reg_docs = [d.id for d in docs if d.type == "regulatory" and tag in d.entities.get("equipment", {})]
            add(f"statutory-{tag}", f"{tag} statutory pressure vessel inspection",
                "Factories Act Sec 31 / OISD-STD-128", "high", status, detail,
                sorted({doc.id, *reg_docs}), [tag])

    # --- SOP / procedure review currency (OISD-STD-105: 3-yearly review),
    # from frontmatter — already generic; only the "this stale procedure
    # already caused an incident" consequence note is discovered per-doc
    # below instead of naming one specific SOP.
    for doc in docs:
        if doc.type == "procedure" and doc.meta.get("review_due"):
            due = _parse(doc.meta["review_due"])
            status, days = _status_from_due(due, today)
            consequence, evidence_extra = "", []
            if status == "gap":
                ref = _consequence_ref(doc.id, docs)
                if ref:
                    consequence = f" Near-miss/incident {ref[0]} cites the stale procedure as a contributing factor."
                    evidence_extra = [ref[0]]
            detail = {
                "gap": f"3-yearly review overdue by {days} days (due {doc.meta['review_due']}).{consequence}",
                "due_soon": f"Review due in {days} days.",
                "compliant": f"Current (Rev {doc.meta.get('rev', '?')}); next review {doc.meta['review_due']}.",
            }.get(status, "")
            add(f"review-{doc.id}", f"{doc.id} periodic review", "OISD-STD-105",
                "high" if status == "gap" else "medium", status, detail, [doc.id] + evidence_extra)

    # --- Re-inspection follow-up (OISD-STD-128 CUI / general), from any
    # inspection document's "Next inspection due: <date>" line — the
    # equipment tag, wall-thickness figures and linked work order are all
    # parsed per-document rather than naming E-104/INSP-088 specifically.
    for doc in docs:
        if doc.type != "inspection":
            continue
        m = re.search(r"Next inspection due:\s*" + DATE_RE, doc.body)
        if not m:
            continue
        due = _parse(m.group(1))
        status, days = _status_from_due(due, today)
        tags = _primary_equipment(doc)
        label = tags[0] if tags else doc.id
        extra = []
        wall = re.search(r"minimum recorded (\d+(?:\.\d+)?)\s*mm", doc.body, re.I)
        retire = re.search(r"[Rr]etirement thickness[^.\d]*(\d+(?:\.\d+)?)\s*mm", doc.body)
        rate = re.search(r"corrosion rate estimated (\d+(?:\.\d+)?)\s*mm/yr", doc.body, re.I)
        if wall:
            extra.append(f"min wall {wall.group(1)} mm")
        if retire:
            extra.append(f"retirement {retire.group(1)} mm")
        if rate:
            extra.append(f"est. corrosion {rate.group(1)} mm/yr")
        tail = f" ({'; '.join(extra)})" if extra else ""
        detail = (f"{label} follow-up inspection "
                  + (f"overdue by {days} days" if status == "gap" else f"due in {days} days")
                  + f".{tail}")
        related_wo = [d.id for d in docs if d.type == "work_order" and tags and set(tags) & set(d.entities.get("equipment", {}))]
        add(f"reinspect-{doc.id}", f"{label} re-inspection", "OISD-STD-128", "high", status, detail,
            sorted({doc.id, *related_wo[:1]}), tags)

    # --- Recurring drill / rehearsed-response currency (e.g. confined space
    # mock rescue, annual), from any procedure's "drill conducted <date>"
    # line — governing standard is read from the document's own extracted
    # standard references, not asserted.
    for doc in docs:
        m = re.search(r"drill conducted\s*" + DATE_RE, doc.body)
        if not m:
            continue
        last = _parse(m.group(1))
        due = date(last.year + 1, last.month, last.day) if last else None
        status, days = _status_from_due(due, today)
        detail = (f"Annual mock rescue drill last held {last}; "
                  + (f"next due in {days} days." if status != "gap" else f"overdue by {days} days."))
        standards = list(doc.entities.get("standard", {}))
        standard_label = next((s for s in standards if "Factories Act" in s), next(iter(standards), "Safety procedure"))
        add(f"drill-{doc.id}", f"{doc.id} mock rescue drill", standard_label, "medium", status, detail, [doc.id])

    # --- Open corrective actions, from any incident/near-miss report with a
    # "N. <action> — OPEN" line — every incident-type document is scanned,
    # not a fixed pair of ids.
    for doc in docs:
        if doc.type != "incident":
            continue
        open_actions = re.findall(r"\d\.\s+([^\n]+?)\s+—\s+OPEN", doc.body)
        if open_actions:
            add(f"actions-{doc.id}", f"{doc.id} open corrective actions",
                "Incident management", "medium", "gap",
                f"{len(open_actions)} action(s) still open: " + "; ".join(a.strip('* ') for a in open_actions),
                [doc.id])

    # --- Requirements named in a regulatory index but never evidenced by an
    # operational record — parsed from any `type: regulatory` document's
    # bullet points. The title/detail text is quoted verbatim from the
    # regulatory document, not authored.
    #
    # Dedup against checks above is deliberately conservative: a bullet is
    # skipped only when its standard code is the *sole* subject of a check
    # that already produced a real dated status (compliant/gap/due_soon) —
    # e.g. OISD-STD-132 only ever means "PSV test", so once the PSV check
    # has run, the OISD-STD-132 bullet is genuinely redundant. OISD-STD-105
    # is deliberately never auto-suppressed: the regulatory text bundles two
    # distinct sub-requirements under it (3-yearly procedure review AND
    # quarterly permit audit) and only the review has a dedicated check —
    # collapsing on the code alone would silently hide the un-evidenced one.
    # When in doubt this reports a requirement that's arguably already
    # covered, rather than risk hiding one that is not — the safer failure
    # mode for a compliance tool.
    # Matches both "Section 31" (as written in the regulatory index) and the
    # abbreviated "Sec 31" (as written in finding["standard"] fields above) —
    # normalised to the same canonical form so the two vocabularies compare
    # correctly.
    CODE_RE = re.compile(r"OISD-STD-\d+|OISD-GDN-\d+|Sec(?:tion)?\.?\s?(\d+)")
    NEVER_COLLAPSE = {"OISD-STD-105"}

    def _codes(text: str) -> set[str]:
        found = set()
        for m in CODE_RE.finditer(text or ""):
            found.add(f"Factories Act Sec {m.group(1)}" if m.group(1) else m.group(0))
        return found

    evaluated_codes = set()
    for f in findings:
        if f["status"] != "no_evidence":
            evaluated_codes |= (_codes(f["standard"]) - NEVER_COLLAPSE)

    bullet_re = re.compile(r"^\s*-\s+(?:\*\*([^*]+)\*\*:?\s*)?(.+)$")
    seen_titles = set()
    for doc in docs:
        if doc.type != "regulatory":
            continue
        for line in doc.body.splitlines():
            m = bullet_re.match(line)
            if not m:
                continue
            bold, rest = m.group(1), m.group(2).strip()
            bold = bold.strip(" *:—-") if bold else None
            title = (bold or rest.split(":")[0].split(".")[0]).strip(" *:—-")
            if not title or title in seen_titles:
                continue
            if _codes(bold or title) & evaluated_codes:
                continue
            seen_titles.add(title)
            add(f"reg-{re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')[:40]}",
                title, bold or "Regulatory index", "medium", "no_evidence",
                f"Identified in {doc.id} but no evidence records exist in the corpus: {rest}"[:280],
                [doc.id])

    counts = {"compliant": 0, "due_soon": 0, "gap": 0, "no_evidence": 0}
    for f in findings:
        counts[f["status"]] = counts.get(f["status"], 0) + 1
    total = len(findings) or 1
    score = round(100 * (counts["compliant"] + 0.5 * counts["due_soon"]) / total)
    order = {"gap": 0, "no_evidence": 1, "due_soon": 2, "compliant": 3}
    sev_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    findings.sort(key=lambda f: (order[f["status"]], sev_order[f["severity"]]))
    logger.info("compliance evaluated: score=%d%% total=%d gap=%d due_soon=%d no_evidence=%d compliant=%d",
               score, len(findings), counts["gap"], counts["due_soon"], counts["no_evidence"], counts["compliant"])
    return {"score": score, "counts": counts, "total_checks": len(findings),
            "as_of": today.isoformat(), "findings": findings}
