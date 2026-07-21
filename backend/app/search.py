"""Hybrid retrieval: BM25 lexical index + knowledge-graph boosting.

BM25 is hand-rolled (no dependency) over document chunks. At query time,
entities detected in the query are resolved against the graph; chunks from
documents linked to those entities (directly, or one hop away through a
shared failure mode) receive a multiplicative boost. This is what lets
"why does P-101A keep failing" surface the OEM manual and the handover
memo even when they never use the word "failing".
"""
from __future__ import annotations

import math
import re
from collections import Counter, defaultdict

from .extract import extract_entities

# Concept synonyms so a query written in plain engineering English can still
# reach the graph. Without this, graph expansion only fires when the user
# already knows the exact tag — which is precisely the case where they least
# need help. Measured impact is reported by the evaluation harness.
CONCEPT_SYNONYMS = {
    "fm:Mechanical seal failure": ["seal", "seals", "gland", "sealing", "mechanical seal"],
    "fm:Bearing failure": ["bearing", "bearings"],
    "fm:High vibration": ["vibration", "vibrating", "shaking"],
    "fm:Cavitation": ["cavitation", "cavitating", "suction loss"],
    "fm:Fouling": ["fouling", "fouled", "heat transfer", "performance", "duty", "deposit"],
    "fm:Wax blockage": ["wax", "waxy", "choking", "choked", "blockage", "blocked",
                        "plugged", "plugging", "restricted", "small-bore"],
    "fm:Corrosion under insulation": ["corrosion", "corroded", "insulation", "wall loss",
                                      "thinning", "wet insulation"],
    "fm:Overheating": ["overheating", "overheated", "hot", "temperature rise"],
    "fm:Erosion": ["erosion", "eroded"],
}

# Equipment-class words → the tag prefixes they refer to.
CLASS_HINTS = {
    "pump": "P-", "pumps": "P-", "charge pump": "P-",
    "exchanger": "E-", "preheat": "E-", "heat transfer": "E-", "bundle": "E-",
    "column": "C-", "tower": "C-", "distillation": "C-",
    "vessel": "V-", "accumulator": "V-", "drum": "V-",
    "tank": "TK-", "storage": "TK-",
    "relief valve": "PSV-", "psv": "PSV-", "safety valve": "PSV-",
}

STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "is", "are", "was",
    "were", "be", "with", "at", "by", "from", "as", "it", "its", "this", "that",
    "what", "why", "how", "when", "which", "who", "does", "do", "did", "can", "we",
    "our", "have", "has", "had", "not", "no", "if", "than", "then", "there", "their",
    "keep", "keeps", "about", "into", "any", "all", "per", "via",
}

TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9./-]*")


def tokenize(text: str) -> list[str]:
    return [t for t in TOKEN_RE.findall(text.lower()) if t not in STOPWORDS and len(t) > 1]


def _proximity_bonus(tokens: list[str], query_terms: list[str], window: int = 8) -> float:
    """Reward chunks where multiple *distinct* query terms cluster close
    together — a real IR reranking signal (the same idea as Elasticsearch
    span-near / Solr proximity boosting): terms appearing within a few tokens
    of each other are much more likely discussing the same specific point
    than the same terms scattered across an otherwise-unrelated chunk."""
    qset = set(query_terms)
    positions: dict[str, list[int]] = defaultdict(list)
    for idx, tok in enumerate(tokens):
        if tok in qset:
            positions[tok].append(idx)
    matched_terms = [t for t in positions if positions[t]]
    if len(matched_terms) < 2:
        return 0.0
    flat = sorted((pos, term) for term in matched_terms for pos in positions[term])
    best = 0
    for i in range(len(flat)):
        seen = set()
        for j in range(i, len(flat)):
            if flat[j][0] - flat[i][0] > window:
                break
            seen.add(flat[j][1])
        best = max(best, len(seen))
    return 0.15 * best


def rerank(query_terms: list[str], matched_entities: list[dict],
          candidates: list[tuple[float, int]], chunk_tokens: list[Counter],
          chunks: list, top_n: int) -> list[tuple[float, int]]:
    """Second-stage reranker over the first-stage shortlist.

    First-stage scoring (BM25 + semantic + graph boosts) is deliberately
    cheap per-candidate so it can run over every chunk touching a query term.
    Reranking inverts that trade-off on purpose: it only ever looks at the
    ~30 chunks that already made the shortlist, so it can afford signals that
    would be too expensive to compute corpus-wide — exact bigram/phrase
    overlap, full query-term coverage *within this one chunk*, entity-label
    density, and term-proximity clustering (see `_proximity_bonus`).

    This is a lexical/positional reranker, not a neural cross-encoder — a
    trained cross-encoder would need a model dependency and GPU/CPU inference
    cost this system's design deliberately avoids everywhere else (see
    ARCHITECTURE.md §8's entity-recognition reasoning, which is the same
    trade-off). Calling it a "cross-encoder" would just be the same kind of
    overclaim the "agent" naming was — so it isn't called that.
    """
    if not candidates:
        return []
    entity_labels = [e["label"].lower() for e in matched_entities]
    qset = set(query_terms)
    bigrams = {f"{a} {b}" for a, b in zip(query_terms, query_terms[1:])}
    out = []
    for base_score, i in candidates:
        tokens = list(chunk_tokens[i].elements())
        text_low = chunks[i].text.lower()
        coverage = len(qset & set(tokens)) / len(qset) if qset else 0.0
        bigram_hits = sum(1 for bg in bigrams if bg in text_low)
        entity_hits = sum(text_low.count(lbl) for lbl in entity_labels)
        fine_score = (
            base_score
            + 0.5 * coverage
            + 0.8 * bigram_hits
            + 0.3 * min(entity_hits, 5)
            + _proximity_bonus(tokens, query_terms)
        )
        out.append((fine_score, i))
    out.sort(key=lambda x: -x[0])
    return out[:top_n]


class HybridIndex:
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.chunks = []
        self.doc_freq: Counter = Counter()
        self.chunk_tokens: list[Counter] = []
        self.chunk_len: list[int] = []
        self.avg_len = 1.0
        self.docs_by_id = {}
        self.graph = None

    def build(self, docs: list, graph, semantic: bool = True):
        self.chunks, self.chunk_tokens, self.chunk_len = [], [], []
        self.doc_freq = Counter()
        self.postings = defaultdict(list)      # term -> [(chunk_idx, tf)] inverted index
        self.doc_chunk_idx = defaultdict(list)  # doc_id -> [chunk_idx]
        self.docs_by_id = {d.id: d for d in docs}
        self.graph = graph
        for doc in docs:
            for chunk in doc.chunks:
                tokens = Counter(tokenize(chunk.text))
                i = len(self.chunks)
                self.chunks.append(chunk)
                self.chunk_tokens.append(tokens)
                self.chunk_len.append(sum(tokens.values()))
                self.doc_chunk_idx[chunk.doc_id].append(i)
                for term, tf in tokens.items():
                    self.doc_freq[term] += 1
                    self.postings[term].append((i, tf))
        n = max(len(self.chunks), 1)
        self.avg_len = sum(self.chunk_len) / n if self.chunks else 1.0
        self._idf = {
            t: math.log(1 + (n - df + 0.5) / (df + 0.5)) for t, df in self.doc_freq.items()
        }
        # Third retrieval signal: LSA semantic embeddings (skipped for large
        # synthetic benchmarks — that path measures the scalable lexical core).
        self.semantic = None
        if semantic:
            from .embeddings import SemanticIndex
            self.semantic = SemanticIndex()
            self.semantic.build(self.chunks)

    def copy(self) -> "HybridIndex":
        """Fresh containers for everything add_document() mutates in
        place — chunks/chunk_tokens/chunk_len (appended to), doc_freq/
        postings/doc_chunk_idx (values mutated), docs_by_id (keys added)
        — so mutating the copy can never alias back into this index.
        Requires build() to have already run at least once (postings/_idf/
        semantic don't exist before that — same precondition every other
        query-time method here already has).

        `semantic` is the one field shared by reference rather than
        copied: it's FAISS-backed, and a FAISS index is an inherently
        mutable C++ object with no cheap copy, so that one signal doesn't
        get the same atomicity guarantee the lexical/graph layers do here
        — a documented, narrower trade-off, not an oversight. See
        main.py's State.add_document() for how this is used.
        """
        new = HybridIndex(self.k1, self.b)
        new.chunks = list(self.chunks)
        new.chunk_tokens = list(self.chunk_tokens)
        new.chunk_len = list(self.chunk_len)
        new.doc_freq = Counter(self.doc_freq)
        new.postings = defaultdict(list, {t: list(v) for t, v in self.postings.items()})
        new.doc_chunk_idx = defaultdict(list, {d: list(v) for d, v in self.doc_chunk_idx.items()})
        new.docs_by_id = dict(self.docs_by_id)
        new.avg_len = self.avg_len
        new._idf = dict(self._idf)
        new.graph = self.graph
        new.semantic = self.semantic
        return new

    def add_document(self, doc, graph) -> None:
        """Incrementally fold one more document into this already-built
        index, without re-tokenising any existing chunk — the fix for the
        "full rebuild on every ingest" bottleneck (ARCHITECTURE.md §10/§12):
        at large corpus size, re-parsing every existing document's text on
        every single upload is what stops working, not the aggregate
        bookkeeping below.

        `avg_len` and `_idf` are recomputed over the *whole* corpus's stats
        every call, because both are genuinely corpus-wide quantities (IDF
        depends on every document's frequency for every term) — but that
        recomputation is O(vocabulary size) / O(chunk count), not
        O(chunk count × avg tokens per chunk), which is the tokenisation
        work a full rebuild would otherwise redo for chunks that didn't
        change. That's the actual saving, stated precisely rather than
        claimed as "O(1) incremental," which this deliberately is not.

        The semantic layer is projected through the *existing* fitted LSA
        basis (embeddings.py: SemanticIndex.add_chunks — no SVD refit),
        unless it was never fitted yet (corpus was too small at the last
        full build), in which case it's fit now — cheap, since that only
        happens while the corpus is still small.
        """
        self.graph = graph
        self.docs_by_id[doc.id] = doc
        new_chunks = doc.chunks
        for chunk in new_chunks:
            tokens = Counter(tokenize(chunk.text))
            i = len(self.chunks)
            self.chunks.append(chunk)
            self.chunk_tokens.append(tokens)
            self.chunk_len.append(sum(tokens.values()))
            self.doc_chunk_idx[chunk.doc_id].append(i)
            for term, tf in tokens.items():
                self.doc_freq[term] += 1
                self.postings[term].append((i, tf))
        n = max(len(self.chunks), 1)
        self.avg_len = sum(self.chunk_len) / n if self.chunks else 1.0
        self._idf = {
            t: math.log(1 + (n - df + 0.5) / (df + 0.5)) for t, df in self.doc_freq.items()
        }
        if self.semantic is not None:
            if self.semantic.ready:
                self.semantic.add_chunks(new_chunks)
            else:
                self.semantic.build(self.chunks)

    def _resolve_concepts(self, text: str) -> dict[str, set]:
        """Map plain-English concept words onto graph nodes → candidate docs."""
        low = text.lower()
        out: dict[str, set] = {}
        for node_id, words in CONCEPT_SYNONYMS.items():
            if node_id in self.graph.nodes and any(w in low for w in words):
                out[node_id] = self.graph.docs_linked_to_entity(node_id)
        for word, prefix in CLASS_HINTS.items():
            if word not in low:
                continue
            for nid, node in self.graph.nodes.items():
                if node["type"] == "equipment" and node["label"].startswith(prefix):
                    out.setdefault(nid, set()).update(self.graph.docs_linked_to_entity(nid))
        return out

    def _bm25(self, query_terms: list[str], i: int) -> float:
        score, tokens, length = 0.0, self.chunk_tokens[i], self.chunk_len[i]
        for term in query_terms:
            tf = tokens.get(term, 0)
            if not tf:
                continue
            idf = self._idf.get(term, 0.0)
            score += idf * tf * (self.k1 + 1) / (
                tf + self.k1 * (1 - self.b + self.b * length / self.avg_len)
            )
        return score

    def _allowed_doc_ids(self, doc_types=None, date_from=None, date_to=None):
        """Resolve the metadata filter (doc type set / ISO date range) to a
        concrete set of document ids once per query, so every candidate-
        generation stage below can do a single O(1) set-membership check
        instead of re-evaluating the filter per chunk. None means
        unfiltered — the common case stays exactly as cheap as before this
        existed."""
        if not (doc_types or date_from or date_to):
            return None
        allowed = set()
        for doc_id, doc in self.docs_by_id.items():
            if doc_types and doc.type not in doc_types:
                continue
            if date_from and (not doc.date or doc.date < date_from):
                continue
            if date_to and (not doc.date or doc.date > date_to):
                continue
            allowed.add(doc_id)
        return allowed

    def query(self, text: str, top_k: int = 8, use_graph: bool = True,
              use_semantic: bool = True, use_rerank: bool = True,
              doc_types: set[str] | None = None,
              date_from: str | None = None, date_to: str | None = None) -> dict:
        """Retrieve. `use_graph`/`use_semantic`/`use_rerank` exist so the
        evaluation harness can ablate each signal and measure what it
        actually contributes. `doc_types`/`date_from`/`date_to` are the
        metadata filter: when given, every stage below (lexical, semantic,
        graph) only considers chunks belonging to a document that matches —
        a genuine pre-filter, not a post-hoc trim of the final ranked list,
        so a filtered query never loses a slot in the top-k to a document
        that was going to be excluded anyway."""
        query_terms = tokenize(text)
        query_entities = extract_entities(text)
        allowed_docs = self._allowed_doc_ids(doc_types, date_from, date_to)

        # Graph expansion: docs directly linked to query entities, and docs one
        # hop away through the failure modes those entities exhibit.
        direct_docs, expanded_docs = set(), set()
        matched_entities = []
        for etype, prefix in (("equipment", "eq:"), ("standard", "std:"),
                              ("failure_mode", "fm:"), ("person", "person:"),
                              ("docref", "doc:")):
            for name in query_entities.get(etype, {}):
                node_id = f"{prefix}{name}"
                if node_id in self.graph.nodes:
                    matched_entities.append({"id": node_id, "type": etype, "label": name})
                    direct_docs |= self.graph.docs_linked_to_entity(node_id)
                    for neighbor in self.graph.neighbors(node_id):
                        if neighbor.startswith("fm:"):
                            expanded_docs |= self.graph.docs_linked_to_entity(neighbor)

        # Concept-level resolution: a query in plain English names no tag, so
        # resolve failure-mode and equipment-class words onto graph nodes too.
        # Flagged `inferred` so the trace never implies an exact tag match.
        exact_ids = {m["id"] for m in matched_entities}
        for node_id, concept_docs in self._resolve_concepts(text).items():
            if node_id in exact_ids or node_id not in self.graph.nodes:
                continue
            matched_entities.append({
                "id": node_id, "type": node_id.split(":", 1)[0],
                "label": self.graph.nodes[node_id]["label"], "inferred": True,
            })
            expanded_docs |= concept_docs
        expanded_docs -= direct_docs
        if not use_graph:
            direct_docs, expanded_docs = set(), set()

        # Semantic (LSA) signal via approximate nearest-neighbour search
        # (embeddings.py's FAISS HNSW index) — O(log n) over a bounded
        # candidate set, not a dense O(n) scan of every chunk. This is the
        # actual query-time cost profile an ANN index exists to give you;
        # search only ranks the chunks the index returns, never all of them.
        semantic_hits = (self.semantic.top_k(text, k=50)
                         if use_semantic and self.semantic and self.semantic.ready else [])
        semantic_scores = dict(semantic_hits)
        semantic_top = None
        if semantic_hits:
            best_i, best_score = semantic_hits[0]
            if best_score > 0.25:
                semantic_top = {
                    "doc_id": self.chunks[best_i].doc_id,
                    "score": round(best_score, 3),
                    "lexical_miss": self._bm25(query_terms, best_i) == 0,
                }

        # Candidate generation via the inverted index: only chunks that match a
        # query term (term-at-a-time BM25 accumulation), plus chunks pulled in
        # by the graph or a semantic hit. O(postings) not O(all chunks).
        cand: dict[int, float] = {}
        for term in query_terms:
            idf = self._idf.get(term)
            if not idf:
                continue
            for i, tf in self.postings.get(term, ()):
                if allowed_docs is not None and self.chunks[i].doc_id not in allowed_docs:
                    continue
                length = self.chunk_len[i]
                cand[i] = cand.get(i, 0.0) + idf * tf * (self.k1 + 1) / (
                    tf + self.k1 * (1 - self.b + self.b * length / self.avg_len)
                )
        for i, s in semantic_scores.items():
            if s > 0 and (allowed_docs is None or self.chunks[i].doc_id in allowed_docs):
                cand[i] = cand.get(i, 0.0) + 1.7 * float(s)
        filtered_direct = direct_docs if allowed_docs is None else direct_docs & allowed_docs
        filtered_expanded = expanded_docs if allowed_docs is None else expanded_docs & allowed_docs
        for doc_id in filtered_direct | filtered_expanded:
            for i in self.doc_chunk_idx.get(doc_id, ()):
                cand.setdefault(i, 0.0)

        scored = []
        for i, base in cand.items():
            s = base
            doc_id = self.chunks[i].doc_id
            if doc_id in direct_docs:
                s = s * 1.35 + 0.6
            elif doc_id in expanded_docs:
                s = s * 1.15 + 0.2
            if s > 0:
                sem = round(semantic_scores.get(i, 0.0), 3)
                scored.append((s, i, sem))
        scored.sort(key=lambda x: -x[0])

        # Second-stage rerank over the shortlist only (see search.rerank docstring
        # for why this is a lexical/positional reranker, not a neural cross-encoder).
        if use_rerank and scored:
            sem_by_i = {i: sem for _, i, sem in scored}
            shortlist_n = max(top_k * 4, 30)
            shortlist = [(s, i) for s, i, _ in scored[:shortlist_n]]
            reranked = rerank(query_terms, matched_entities, shortlist,
                              self.chunk_tokens, self.chunks, top_n=len(shortlist))
            scored = [(s, i, sem_by_i[i]) for s, i in reranked] + scored[shortlist_n:]

        # Keep at most 2 chunks per document so citations span sources
        per_doc = defaultdict(int)
        hits = []
        for s, i, sem in scored:
            chunk = self.chunks[i]
            if per_doc[chunk.doc_id] >= 2:
                continue
            per_doc[chunk.doc_id] += 1
            hits.append({"score": round(s, 3), "semantic": sem, "chunk": chunk})
            if len(hits) >= top_k:
                break

        return {
            "hits": hits,
            "query_terms": query_terms,
            "matched_entities": matched_entities,
            "graph_direct_docs": sorted(direct_docs),
            "graph_expanded_docs": sorted(expanded_docs),
            "semantic_dims": self.semantic.k if self.semantic and self.semantic.ready else 0,
            "semantic_top": semantic_top,
        }
