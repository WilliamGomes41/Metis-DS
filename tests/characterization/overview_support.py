"""Offline fixtures for the review overview: real formation, synthetic identities, no credentials."""
from copy import deepcopy

from src.source_accountability_v1 import CONTAINERS_VERSION, VERSION as LEGACY_VERSION

from .support import REVIEWER, command, console_at

SOURCE_HTML = (b"<!doctype html><html><body><h1>Voorbeeld</h1><p>Versie: 1</p>"
               b"<p>Een waarneming is een beschrijving.</p><p>Overleg met de patient over de wens.</p></body></html>")
TREE = (b'{"kind": "beslisboom-freeze", "paths": [{"id": "p", "text": "Bespreek de situatie"}], '
        b'"nodes": [{"id": "n", "text": "Is er een vraag?"}], '
        b'"outcomes": [{"id": "o", "text": "Maak een afspraak.", "applies_if": ["n"]}]}')
LEGACY_TEXT = "Versie: 1"
OPEN_TEXT = "Overleg met de patient over de wens."


def select_with_sources(console):
    """One semantic candidate plus a V1 metadata and a V2 unresolved source record.

    Every row travels through the real deterministic creator and the real
    coverage-remainder builder; only the offline proposal is fixed.
    """
    from src.integrity_kernel import stable_hash
    from src.knowledge_materialisation_v1 import materialise_knowledge_candidates
    from src.semantic_passage_v1 import (_coverage_remainders, _reconstructed_blocks,
                                         semantic_source_blocks, semantic_units_from_proposal)
    original = console._fragments_and_spec

    def prepare(*args, **kwargs):
        fragments, spec = original(*args, **kwargs)
        blocks = semantic_source_blocks(fragments)
        block = next(b for b in blocks if "Een waarneming" in b["text"])
        proposal = {"objects": [{"spans": [{"block_id": block["block_id"], "start": 0, "end": len(block["text"])}],
                                  "proposed_object_type": "definition"}], "relations": [], "abstain_reason": None}
        units = semantic_units_from_proposal(fragments, document_id=kwargs["document_id"], proposal=proposal)
        candidates = materialise_knowledge_candidates(units, document_id=kwargs["document_id"], fragments=fragments)
        for row in candidates:
            row["semantic_passage"].update(formation_mode="semantic-source-bound-v1", model="offline-selection",
                source_blocks_hash=stable_hash(blocks), proposal_hash=stable_hash(proposal))
        reconstructed = _reconstructed_blocks(list(fragments))
        sources = []
        for text, version, role in ((LEGACY_TEXT, LEGACY_VERSION, ("metadata", "document_metadata")),
                                    (OPEN_TEXT, CONTAINERS_VERSION, None)):
            pair = next(p for p in reconstructed if p[0]["text"] == text)
            assessments = ([{"span": {"block_id": pair[0]["block_id"], "start": 0, "end": len(text)},
                             "role": role[0], "reason": role[1]}] if role else None)
            sources += [unit for _, unit in _coverage_remainders(
                [pair], document_id=kwargs["document_id"], selected_ranges_by_block={},
                assessments=assessments, source_version=version)]
        spec["objects"] = ([r for r in spec["objects"] if r.get("object_type") in {"document", "heading"}]
                           + candidates + sources)
        return fragments, spec
    console._fragments_and_spec = prepare


def guideline_document(tmp_path, *, production_console):
    console = console_at(tmp_path, production_console=production_console)
    select_with_sources(console)
    sid = console.ingest(**command(data=SOURCE_HTML))["snapshot_id"]
    return console, sid, deepcopy(console._accounts[REVIEWER])


def tree_document(tmp_path, *, production_console):
    console = console_at(tmp_path, production_console=production_console)
    sid = console.ingest(**command(class_="beslisboom", data=TREE, filename="tree.json",
                                   content_type="application/json"))["snapshot_id"]
    return console, sid, deepcopy(console._accounts[REVIEWER])


def native_summary(console, sid, **counts):
    """The shape `review_workboard_summaries` returns on the native PostgreSQL path."""
    base = {"heading_total": 0, "heading_pending": 0, "individual_total": 0, "individual_pending": 0,
            "normal_passages": 0, "normal_batches": 0, "blocked_count": 0, "closure_gap_count": 0,
            "actionable_structure_duties": 0, "actionable_contextual_duties": 0, "actionable_batch_duties": 0,
            "actionable_second_review_duties": 0, "waiting_for_reviewer_duties": 0, "contextual_review_duties": 0}
    return {"envelope": deepcopy(console._envelope(sid)), **base, **counts}


def install_native_summaries(monkeypatch, console, sid, summary):
    """Fake summary reader; no PostgreSQL and no workflow-store code is touched."""
    import src.review_workboard_v1 as board
    calls = []
    original = board._projected_document_dashboard

    def spy(*args, **kwargs):
        calls.append(kwargs.get("snapshot_id"))
        return original(*args, **kwargs)

    monkeypatch.setattr(console, "review_workboard_summaries",
                        lambda account_id, snapshot_id=None, **kw: {sid: deepcopy(summary)}, raising=False)
    monkeypatch.setattr(board, "_projected_document_dashboard", spy)
    return calls
