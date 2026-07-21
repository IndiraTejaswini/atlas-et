"""Knowledge graph construction, including P&ID-vision-derived connectivity."""
from app.graph import KnowledgeGraph
from app.ingest import load_document


def test_graph_has_document_and_equipment_nodes(built_graph):
    doc_nodes = [n for n in built_graph.nodes.values() if n["type"] == "document"]
    eq_nodes = [n for n in built_graph.nodes.values() if n["type"] == "equipment"]
    assert len(doc_nodes) >= 18
    assert any(n["label"] == "P-101A" for n in eq_nodes)


def test_shortest_path_finds_equipment_to_document(built_graph):
    path = built_graph.shortest_path("eq:P-101A", "doc:WO-2415", max_depth=3)
    assert path is not None
    assert path[0]["id"] == "eq:P-101A"
    assert path[-1]["id"] == "doc:WO-2415"


def test_subgraph_is_bounded_by_depth(built_graph):
    sub = built_graph.subgraph("eq:P-101A", depth=1)
    full_neighbors = built_graph.neighbors("eq:P-101A")
    node_ids = {n["id"] for n in sub["nodes"]}
    assert "eq:P-101A" in node_ids
    assert full_neighbors <= node_ids


def test_connected_to_edges_from_pid_digitisation():
    """Regression test for the vision-to-graph wiring: a document body
    containing 'A connected_to B' lines (as produced by
    vision.pid_to_document_body) must materialise as real connected_to
    edges — this is what makes the Drawings page's claim ('becomes a
    connected_to edge in the knowledge graph') actually true."""
    body = (
        "## Equipment tags detected\n- P-101A\n- E-104\n\n"
        "## Connections\n- P-101A connected_to E-104\n- E-104 connected_to C-201\n"
    )
    doc = load_document({"id": "DWG-TEST-CV", "type": "drawing", "equipment": "P-101A,E-104"},
                        body, fallback_id="DWG-TEST-CV")
    g = KnowledgeGraph()
    g.build([doc])
    connected_edges = {(e["source"], e["target"]) for (a, b, rel), e in g.edges.items() if rel == "connected_to"}
    assert ("eq:P-101A", "eq:E-104") in connected_edges
    assert ("eq:E-104", "eq:C-201") in connected_edges


def test_untagged_symbol_placeholders_do_not_become_edges():
    # Connections between unresolved symbols (vision.py falls back to
    # "symbol_N" when OCR can't bind a tag) must never leak into the graph
    # as nonsense nodes.
    body = "## Connections\n- symbol_0 connected_to symbol_2\n"
    doc = load_document({"id": "DWG-TEST-2", "type": "drawing"}, body, fallback_id="DWG-TEST-2")
    g = KnowledgeGraph()
    g.build([doc])
    assert not any(rel == "connected_to" for (a, b, rel) in g.edges)


def test_root_cause_clause_produces_typed_caused_by_edge():
    """Regression test for relationship extraction beyond co-occurrence: a
    'Root cause suspected to be waxing...' sentence must produce a directed
    fm:X --caused_by--> fm:Y edge, not just an undirected co-occurrence link,
    because the two failure modes never actually co-occur as document-level
    entities here — only one (seal failure) is the document's own
    failure_mode; the other (wax blockage) only appears inside the clause."""
    body = (
        "**Findings:** Seal face overheating due to degraded flush flow. "
        "Root cause suspected to be waxing of the Plan 32 line."
    )
    doc = load_document(
        {"id": "WO-TEST-RC", "type": "work_order", "equipment": "P-999",
         "failure_mode": "mechanical seal failure"},
        body, fallback_id="WO-TEST-RC",
    )
    g = KnowledgeGraph()
    g.build([doc])
    caused_by = {(e["source"], e["target"]) for (a, b, rel), e in g.edges.items() if rel == "caused_by"}
    assert ("fm:Mechanical seal failure", "fm:Wax blockage") in caused_by


def test_root_cause_clause_with_equipment_produces_root_cause_condition_edge():
    # extract_entities reads title+body text only, not frontmatter fields —
    # the failure mode word must actually appear in the body, same as every
    # real corpus document.
    body = "Cavitation was observed. Root cause suspected to be a blocked line downstream of MOV-118."
    doc = load_document(
        {"id": "WO-TEST-RC2", "type": "work_order", "equipment": "P-999",
         "failure_mode": "cavitation"},
        body, fallback_id="WO-TEST-RC2",
    )
    g = KnowledgeGraph()
    g.build([doc])
    edges = {(e["source"], e["target"]) for (a, b, rel), e in g.edges.items() if rel == "root_cause_condition"}
    assert ("fm:Cavitation", "eq:MOV-118") in edges


def test_no_cause_clause_no_extra_edges():
    doc = load_document(
        {"id": "WO-TEST-RC3", "type": "work_order", "equipment": "P-999",
         "failure_mode": "fouling"},
        "Routine inspection found no anomalies.", fallback_id="WO-TEST-RC3",
    )
    g = KnowledgeGraph()
    g.build([doc])
    assert not any(rel in ("caused_by", "root_cause_condition") for (a, b, rel) in g.edges)


# --- copy() — the property State.add_document()'s atomicity relies on ---

def test_copy_produces_an_equal_but_independent_graph(built_graph):
    copy = built_graph.copy()
    assert copy.nodes == built_graph.nodes
    assert copy.edges.keys() == built_graph.edges.keys()
    assert copy.adj == built_graph.adj
    assert copy is not built_graph
    assert copy.nodes is not built_graph.nodes


def test_mutating_the_copy_never_changes_the_original(corpus_docs):
    import copy as copy_module
    original = KnowledgeGraph()
    original.build(copy_module.deepcopy(corpus_docs))
    before_node_count = len(original.nodes)
    before_edge_count = len(original.edges)
    before_weight = original.nodes["eq:P-101A"]["weight"]

    duplicated = original.copy()
    extra_doc = load_document(
        {"id": "WO-EXTRA", "type": "work_order", "equipment": "P-101A", "failure_mode": "mechanical seal failure"},
        "P-101A seal failure observed again.", fallback_id="WO-EXTRA",
    )
    known_ids = {d.id for d in corpus_docs} | {"WO-EXTRA"}
    duplicated.add_document(extra_doc, known_ids)

    # The copy grew...
    assert len(duplicated.nodes) >= before_node_count
    assert "doc:WO-EXTRA" in duplicated.nodes
    assert duplicated.nodes["eq:P-101A"]["weight"] > before_weight
    # ...but the original must be completely untouched — this is the
    # property that lets main.py swap `self.graph = duplicated` only
    # after the mutation is fully done, so a concurrent reader of the
    # *original* reference never observes a half-updated graph.
    assert len(original.nodes) == before_node_count
    assert len(original.edges) == before_edge_count
    assert "doc:WO-EXTRA" not in original.nodes
    assert original.nodes["eq:P-101A"]["weight"] == before_weight


def test_add_document_creates_a_retroactive_edge_when_an_existing_doc_referenced_it_first():
    """The specific bug this fixes: an already-added document's text names
    a document id that hasn't arrived yet. When that document finally does
    arrive, the "references" edge must be created retroactively — it must
    not require re-scanning the old document's raw text (existing_docs
    supplies its *already-extracted* entities), and it must not silently
    stay missing forever."""
    old_doc = load_document(
        {"id": "INSP-999", "type": "inspection", "equipment": "E-999"},
        "Follow-up planned. See upcoming work order WO-8888 for the repair.",
        fallback_id="INSP-999",
    )
    g = KnowledgeGraph()
    g.build([old_doc])
    assert not any(rel == "references" for (a, b, rel) in g.edges)  # WO-8888 unknown yet

    new_doc = load_document(
        {"id": "WO-8888", "type": "work_order", "equipment": "E-999"},
        "Repair completed on E-999.", fallback_id="WO-8888",
    )
    known_ids = {"INSP-999", "WO-8888"}
    g.add_document(new_doc, known_ids, existing_docs=[old_doc])

    refs = {(e["source"], e["target"]) for (a, b, rel), e in g.edges.items() if rel == "references"}
    assert ("doc:INSP-999", "doc:WO-8888") in refs


def test_add_document_without_existing_docs_skips_the_backreference_check():
    """existing_docs is opt-in (build()'s own loop deliberately omits it —
    see add_document()'s docstring) — confirm omitting it just means no
    retroactive edge, not an error."""
    old_doc = load_document(
        {"id": "INSP-998", "type": "inspection"},
        "See upcoming work order WO-8887.", fallback_id="INSP-998",
    )
    g = KnowledgeGraph()
    g.build([old_doc])
    new_doc = load_document({"id": "WO-8887", "type": "work_order"}, "Repair done.", fallback_id="WO-8887")
    g.add_document(new_doc, {"INSP-998", "WO-8887"})  # no existing_docs
    assert not any(rel == "references" for (a, b, rel) in g.edges)


def test_mutating_a_copys_edge_docs_set_does_not_alias_the_original(corpus_docs):
    import copy as copy_module
    original = KnowledgeGraph()
    original.build(copy_module.deepcopy(corpus_docs))
    some_edge_key = next(iter(original.edges))
    original_docs_snapshot = set(original.edges[some_edge_key]["docs"])

    duplicated = original.copy()
    duplicated.edges[some_edge_key]["docs"].add("INJECTED-DOC-ID")

    assert "INJECTED-DOC-ID" not in original.edges[some_edge_key]["docs"]
    assert original.edges[some_edge_key]["docs"] == original_docs_snapshot
