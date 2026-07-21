"""Synthetic-scale benchmark.

Generates a large synthetic industrial corpus through the *real* ingestion and
extraction pipeline, builds the graph and lexical index over it, and measures
cold-build time, per-query latency and memory — turning the scalability story
into measured evidence. Results are cached per size.

The semantic (LSA) layer is intentionally skipped here: SVD does not scale to
tens of thousands of chunks — at production scale that signal moves to an
approximate-nearest-neighbour index. This benchmark measures the lexical +
graph core, which is what stays in-process as the corpus grows.
"""
from __future__ import annotations

import random
import time
import tracemalloc

from .graph import KnowledgeGraph
from .ingest import load_document
from .search import HybridIndex

_TAGS = ([f"P-{100 + i}" for i in range(80)] + [f"E-{100 + i}" for i in range(60)]
         + [f"V-{300 + i}" for i in range(40)] + [f"PSV-{1000 + i}" for i in range(80)]
         + [f"TK-{300 + i}" for i in range(30)])
_MODES = ["mechanical seal failure", "bearing failure", "cavitation", "fouling",
          "corrosion under insulation", "high vibration", "wax blockage", "overheating"]
_STDS = ["OISD-STD-132", "OISD-STD-128", "OISD-STD-105", "API 610", "ISO 10816"]
_TYPES = ["work_order", "inspection", "incident", "procedure", "datasheet"]
_PEOPLE = ["R. Sharma", "A. Verma", "S. Iyer", "M. Khan", "P. Nair"]

_CACHE: dict[int, dict] = {}

# A diverse sentence pool so the synthetic corpus resembles a real heterogeneous
# document set (varied vocabulary → realistic inverted-index selectivity),
# rather than a degenerate template that repeats the same words in every record.
_SENTENCES = [
    "{tag} exhibited {mode} during the {season} campaign.",
    "Root cause analysis attributed the event to {cause}.",
    "Governing standard {std} requires {interval}-monthly verification.",
    "Cross-reference {ref} documents the corrective action taken.",
    "Field measurements recorded {v} mm/s vibration against the {vl} alarm.",
    "Discharge pressure held at {p} barg with suction stable.",
    "Bearing housing temperature peaked at {t} degrees during turndown.",
    "Reviewed and approved by {person} following site inspection.",
    "The {mode} was consistent with prior findings on similar {family}.",
    "Recommended action: schedule intervention before the next {season} window.",
    "Lubrication analysis returned {wear} wear-metal indications.",
    "Thickness survey measured {mm} mm against a {rt} mm retirement limit.",
    "No secondary damage was observed on the coupling or seal faces.",
    "Operating conditions were within the {std} envelope prior to the event.",
    "A follow-up work order was raised under {ref} for parts procurement.",
    "The relief path and interlock chain were confirmed functional.",
    "Historian trends showed a gradual drift over the preceding {days} days.",
    "Material certificates and calibration records were verified as current.",
]
_CAUSES = ["degraded flush", "overdue lubrication", "process upset", "fouling ingress",
           "wash-rate reduction", "seal-support loss", "off-design flow", "insulation damage"]
_FAMILIES = ["centrifugal pumps", "shell-and-tube exchangers", "pressure vessels",
             "relief devices", "storage tanks"]
_SEASONS = ["monsoon", "winter", "summer", "turnaround"]


def _synth_docs(n: int) -> list:
    rng = random.Random(42)
    docs = []
    for i in range(n):
        tag = rng.choice(_TAGS)
        mode = rng.choice(_MODES)
        std = rng.choice(_STDS)
        typ = rng.choice(_TYPES)
        ref = f"WO-{2000 + rng.randint(0, 4000)}"
        person = rng.choice(_PEOPLE)
        ctx = dict(
            tag=tag, mode=mode, std=std, ref=ref, person=person,
            cause=rng.choice(_CAUSES), family=rng.choice(_FAMILIES), season=rng.choice(_SEASONS),
            interval=rng.choice([6, 12, 24]), v=rng.randint(2, 10), vl=rng.choice([7.1, 11.0]),
            p=rng.randint(3, 46), t=rng.randint(50, 110), wear=rng.choice(["low", "moderate", "elevated"]),
            mm=round(rng.uniform(9, 16), 1), rt=round(rng.uniform(8, 11), 1), days=rng.randint(7, 120),
        )
        # each record samples a different subset of sentences → diverse vocabulary
        picks = rng.sample(_SENTENCES, rng.randint(4, 7))
        body = " ".join(s.format(**ctx) for s in picks)
        meta = {
            "id": f"SYN-{i:05d}", "title": f"Synthetic {typ} record {i}", "type": typ,
            "date": f"20{rng.randint(18, 25)}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}",
            "equipment": tag, "failure_mode": mode, "author": person,
        }
        docs.append(load_document(meta, body, f"SYN-{i}"))
    return docs


def run(n: int = 5000, queries: int = 40) -> dict:
    if n in _CACHE:
        return _CACHE[n]
    rng = random.Random(7)
    tracemalloc.start()

    t_gen = time.perf_counter()
    docs = _synth_docs(n)
    gen_ms = (time.perf_counter() - t_gen) * 1000

    t_build = time.perf_counter()
    graph = KnowledgeGraph()
    graph.build(docs)
    index = HybridIndex()
    index.build(docs, graph, semantic=False)
    build_ms = (time.perf_counter() - t_build) * 1000

    qs = [f"{rng.choice(_TAGS)} {rng.choice(_MODES)}" for _ in range(queries)]
    lat = []
    for q in qs:
        t = time.perf_counter()
        index.query(q)
        lat.append((time.perf_counter() - t) * 1000)
    lat.sort()

    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    def pct(p):
        return round(lat[min(len(lat) - 1, int(len(lat) * p))], 2)

    result = {
        "n_docs": n,
        "n_chunks": len(index.chunks),
        "graph_nodes": len(graph.nodes),
        "graph_edges": len(graph.edges),
        "gen_ms": round(gen_ms, 1),
        "build_ms": round(build_ms, 1),
        "query_avg_ms": round(sum(lat) / len(lat), 2),
        "query_p50_ms": pct(0.50),
        "query_p95_ms": pct(0.95),
        "peak_mem_mb": round(peak / 1e6, 1),
        "queries_run": queries,
    }
    _CACHE[n] = result
    return result
