"""Unified knowledge graph built from extracted entities.

Nodes: documents, equipment, standards, people, failure modes.
Edges carry a relation and provenance (which documents established them).
Stored as adjacency dicts — the corpus is small enough that O(V+E)
traversal beats any index, and the whole graph serializes to JSON
for the frontend force layout.
"""
from __future__ import annotations

import re
from collections import defaultdict

from .extract import extract_entities

# Emitted into a digitised-drawing document's body by vision.pid_to_document_body()
# for every line the CV pipeline resolved between two equipment symbols — this
# is what turns P&ID connectivity into real graph edges instead of a response
# the frontend displays once and discards.
CONNECTED_RE = re.compile(r"\b([A-Z]{1,4}-\d{2,4}[A-Z]?)\s+connected_to\s+([A-Z]{1,4}-\d{2,4}[A-Z]?)\b")

# Typed cause/effect relations, parsed from "root cause ... / due to ... /
# caused by ..." clauses. Everything else in this graph is co-occurrence
# (two entities mentioned in the same document → linked); this is the one
# relation type that captures *directionality* — X caused Y, not just "X and
# Y both appear in this document" — by running the entity extractor a second
# time on just the captured clause and linking what it finds back to the
# document's own failure mode(s).
CAUSE_RE = re.compile(
    r"root cause(?:\s+(?:is|was|suspected to be))?\s*:?\s*([^.\n]{5,200})"
    r"|due to\s+([^.\n]{5,200})"
    r"|caused by\s+([^.\n]{5,200})",
    re.I,
)


class KnowledgeGraph:
    def __init__(self):
        self.nodes: dict[str, dict] = {}
        self.edges: dict[tuple, dict] = {}
        self.adj: dict[str, set] = defaultdict(set)

    def copy(self) -> "KnowledgeGraph":
        """One level deep — a fresh outer dict/set per container, and a
        fresh dict/set for every node/edge's own mutable attributes (each
        node's "weight", each edge's "docs" set and "count" all get
        mutated in place by _node/_edge) — so mutating the copy can never
        alias back into this graph. Used by main.py's incremental
        State.add_document(): copy (cheap — dict/set copying, O(V+E)),
        mutate the copy with the one new document, then swap the
        reference, which is what preserves "a concurrent reader never
        observes a half-updated graph" without paying for a full rebuild
        from document text."""
        new = KnowledgeGraph()
        new.nodes = {nid: dict(attrs) for nid, attrs in self.nodes.items()}
        new.edges = {key: {**e, "docs": set(e["docs"])} for key, e in self.edges.items()}
        new.adj = defaultdict(set, {k: set(v) for k, v in self.adj.items()})
        return new

    def _node(self, node_id: str, node_type: str, label: str | None = None) -> dict:
        node = self.nodes.setdefault(
            node_id, {"id": node_id, "type": node_type, "label": label or node_id, "weight": 0}
        )
        node["weight"] += 1
        return node

    def _edge(self, a: str, b: str, relation: str, source_doc: str):
        key = (a, b, relation)
        edge = self.edges.setdefault(
            key, {"source": a, "target": b, "relation": relation, "docs": set(), "count": 0}
        )
        edge["docs"].add(source_doc)
        edge["count"] += 1
        self.adj[a].add(b)
        self.adj[b].add(a)

    def build(self, docs: list):
        known_ids = {d.id for d in docs}
        for doc in docs:
            self.add_document(doc, known_ids)

    def add_document(self, doc, known_ids: set, existing_docs: list | None = None) -> None:
        """Fold one document's entities into this graph. Nodes/edges are
        purely additive (setdefault + weight/count increments — see _node/
        _edge above), so calling this once per document on the same graph
        object, one document at a time, produces exactly the same final
        graph as build() does for the whole set in one pass.

        `existing_docs`, when given, also catches the reverse case a naive
        one-document-at-a-time add would miss: an *already-added* document
        whose text happens to name this new document's id (an inspection
        report that already says "see upcoming work order WO-2734" before
        WO-2734 was ingested, say) gets its "references" edge to this
        document created retroactively, right now, instead of never. This
        was found by testing the empty-corpus-built-up-incrementally case
        directly (tests/test_state_incremental.py), not assumed safe —
        that test asserted equivalence with a full rebuild, found real
        missing edges, and this is the fix, not a note that it's missing.
        Cheap: it reads each existing document's *already-extracted*
        `entities["docref"]` (a dict lookup — docref extraction itself
        isn't gated by known_ids, only edge creation is), never its raw
        text, so no re-tokenising or re-scanning happens here.

        `build()`'s own per-document loop passes only `known_ids` (the
        full set from the start), not `existing_docs` — every reference in
        that case, forward or backward, is already resolved correctly by
        `known_ids` alone, so the extra check would be redundant there.
        `main.py`'s State.add_document() is what actually needs
        `existing_docs`, for a live single-document ingest.
        """
        doc_node_id = f"doc:{doc.id}"
        self._node(doc_node_id, "document", doc.id)
        self.nodes[doc_node_id].update(
            {"doc_type": doc.type, "title": doc.title, "date": doc.date}
        )
        for tag, n in doc.entities.get("equipment", {}).items():
            self._node(f"eq:{tag}", "equipment", tag)
            self._edge(doc_node_id, f"eq:{tag}", "mentions", doc.id)
        for std, n in doc.entities.get("standard", {}).items():
            self._node(f"std:{std}", "standard", std)
            self._edge(doc_node_id, f"std:{std}", "cites", doc.id)
        for person, n in doc.entities.get("person", {}).items():
            self._node(f"person:{person}", "person", person)
            self._edge(doc_node_id, f"person:{person}", "involves", doc.id)
        for mode, n in doc.entities.get("failure_mode", {}).items():
            self._node(f"fm:{mode}", "failure_mode", mode)
            self._edge(doc_node_id, f"fm:{mode}", "describes", doc.id)
        for ref in doc.entities.get("docref", {}):
            if ref in known_ids and ref != doc.id:
                self._node(f"doc:{ref}", "document", ref)
                self._edge(doc_node_id, f"doc:{ref}", "references", doc.id)
        if existing_docs:
            for other in existing_docs:
                if other.id != doc.id and doc.id in other.entities.get("docref", {}):
                    # `doc` is the reference *target* here, same as the
                    # `f"doc:{ref}"` node in the forward loop just above —
                    # so it's `doc`'s weight that gets the extra touch, not
                    # `other`'s (which already has whatever weight it
                    # legitimately earned when it was added; `other`
                    # referencing something is never what bumps `other`'s
                    # own weight, only what bumps the thing it references).
                    self._node(doc_node_id, "document", doc.id)
                    self._edge(f"doc:{other.id}", doc_node_id, "references", other.id)
        # Equipment <-> failure mode links (co-occurrence within a doc)
        fm = doc.entities.get("failure_mode", {})
        primary_eq = doc.meta.get("equipment", "").split(",")[0].strip() if doc.meta else ""
        if primary_eq and fm:
            for mode in fm:
                self._node(f"eq:{primary_eq}", "equipment", primary_eq)
                self._node(f"fm:{mode}", "failure_mode", mode)
                self._edge(f"eq:{primary_eq}", f"fm:{mode}", "exhibits", doc.id)
        # Equipment <-> equipment connectivity, as digitised by the P&ID
        # vision pipeline (vision.parse_pid -> pid_to_document_body).
        for a, b in CONNECTED_RE.findall(doc.body):
            self._node(f"eq:{a}", "equipment", a)
            self._node(f"eq:{b}", "equipment", b)
            self._edge(f"eq:{a}", f"eq:{b}", "connected_to", doc.id)
        # Typed cause/effect relations: parse "root cause / due to / caused
        # by" clauses and link this document's failure mode(s) to whatever
        # equipment or failure mode the clause itself names — a directed
        # relation extracted from the sentence, not just "these two things
        # were mentioned somewhere in the same document."
        if fm:
            for match in CAUSE_RE.finditer(doc.body):
                clause = next(g for g in match.groups() if g)
                clause_entities = extract_entities(clause)
                for tag in clause_entities.get("equipment", {}):
                    for mode in fm:
                        self._node(f"fm:{mode}", "failure_mode", mode)
                        self._node(f"eq:{tag}", "equipment", tag)
                        self._edge(f"fm:{mode}", f"eq:{tag}", "root_cause_condition", doc.id)
                for cause_mode in clause_entities.get("failure_mode", {}):
                    for mode in fm:
                        if cause_mode == mode:
                            continue
                        self._node(f"fm:{mode}", "failure_mode", mode)
                        self._node(f"fm:{cause_mode}", "failure_mode", cause_mode)
                        self._edge(f"fm:{mode}", f"fm:{cause_mode}", "caused_by", doc.id)

    def neighbors(self, node_id: str) -> set:
        return self.adj.get(node_id, set())

    def shortest_path(self, start: str, goal: str, max_depth: int = 3) -> list | None:
        """BFS shortest path start→goal, returned as [{id,label,type}, …].
        Powers the copilot's "why this source surfaced" explanation."""
        if start not in self.adj or goal not in self.nodes:
            return None
        if start == goal:
            return [self._node_brief(start)]
        seen = {start}
        frontier = [[start]]
        for _ in range(max_depth):
            nxt = []
            for path in frontier:
                for nb in self.adj.get(path[-1], ()):
                    if nb in seen:
                        continue
                    new_path = path + [nb]
                    if nb == goal:
                        return [self._node_brief(n) for n in new_path]
                    seen.add(nb)
                    nxt.append(new_path)
            frontier = nxt
            if not frontier:
                break
        return None

    def _node_brief(self, node_id: str) -> dict:
        n = self.nodes.get(node_id, {})
        return {"id": node_id, "label": n.get("label", node_id), "type": n.get("type", "")}

    def relation_between(self, a: str, b: str) -> str:
        for (x, y, rel) in self.edges:
            if (x == a and y == b) or (x == b and y == a):
                return rel
        return "linked"

    def docs_linked_to_entity(self, entity_node_id: str) -> set[str]:
        return {
            n.removeprefix("doc:")
            for n in self.adj.get(entity_node_id, set())
            if n.startswith("doc:")
        }

    def to_json(self) -> dict:
        return {
            "nodes": list(self.nodes.values()),
            "edges": [
                {**e, "docs": sorted(e["docs"])} for e in self.edges.values()
            ],
        }

    def subgraph(self, focus_id: str, depth: int = 2) -> dict:
        """BFS out from a focus node; returns the induced subgraph."""
        keep = {focus_id}
        frontier = {focus_id}
        for _ in range(depth):
            nxt = set()
            for n in frontier:
                nxt |= self.adj.get(n, set())
            frontier = nxt - keep
            keep |= nxt
        return {
            "nodes": [n for nid, n in self.nodes.items() if nid in keep],
            "edges": [
                {**e, "docs": sorted(e["docs"])}
                for (a, b, _), e in self.edges.items()
                if a in keep and b in keep
            ],
        }
