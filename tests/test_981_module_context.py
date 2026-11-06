"""#981: a recommendation task consults its own source module, never a namesake.

Context is chosen from structural section paths: no heading-text match across
modules, no candidate range turned into context or vice versa, and an oversized
module stays an explicit task error instead of being truncated.

# release-control-evidence: scope/belofte kwaliteit metrics
# release-control-evidence: opslag stale recovery version-compat
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from src.vorming.bounded_formation_v1 import MAX_CONTEXT_CHARS, document_title_path, module_of, tasks_for

TITLE = ("Smetten",)  # the parser-recorded document title path (#997)


def block(bid, text, path, heading=None, position=0):
    return {"block_id": bid, "text": text, "section_path": path, "heading": heading, "position": position}


def guideline():
    """Two modules with the same sub-headings, as Docling emits them (heading in its own path)."""
    m1, m2 = "Module 1: Risicofactoren", "Module 2: Preventieve maatregelen"
    return [
        block("m1", m1, [m1], heading=m1),
        block("m1-rec-h", "Aanbevelingen", [m1, "Aanbevelingen"], heading="Aanbevelingen"),
        block("m1-rec", "Breng bij iedere patiënt de risicofactoren voor smetten in kaart.", [m1, "Aanbevelingen"]),
        block("m1-rat-h", "Rationale", [m1, "Rationale"], heading="Rationale"),
        block("m1-rat", "De werkgroep weegt zweten en overgewicht als belangrijkste factoren.", [m1, "Rationale"]),
        block("m1-ow", "Kosten zijn laag; de patiëntvoorkeur weegt zwaar.", [m1, "Overwegingen"]),
        block("m1-bg", "Smetten ontstaat in huidplooien.", [m1, "Achtergrond"]),
        block("m2", m2, [m2], heading=m2),
        block("m2-rec-h", "Aanbevelingen", [m2, "Aanbevelingen"], heading="Aanbevelingen"),
        block("m2-rec", "Houd de huidplooien droog.", [m2, "Aanbevelingen"]),
        block("m2-rat", "Vocht verhoogt het risico.", [m2, "Rationale"]),
    ]


def _task(tasks, block_id):
    return next(t for t in tasks if block_id in {b["block_id"] for b in t["source_blocks"]})


def _context(task):
    return {b["block_id"] for b in task["evidence_blocks"]}


def test_recommendation_task_sees_rationale_and_considerations_of_its_own_module():
    blocks = guideline()
    task = _task(tasks_for(blocks, blocks), "m1-rec")
    assert {"m1-rat", "m1-rat-h", "m1-ow"} <= _context(task)
    # Context only: the module's other ranges are not candidates of this task.
    assert {s["block_id"] for s in task["target_spans"]} <= {"m1-rec-h", "m1-rec"}


def test_namesake_heading_from_another_module_is_not_context():
    blocks = guideline()
    tasks = tasks_for(blocks, blocks)
    assert not {"m2-rec-h", "m2-rec", "m2-rat", "m2"} & _context(_task(tasks, "m1-rec"))
    assert not {"m1-rec-h", "m1-rat-h", "m1"} & _context(_task(tasks, "m2-rec"))


def test_ancestor_headings_are_context_by_structure():
    blocks = guideline()
    assert "m1" in _context(_task(tasks_for(blocks, blocks), "m1-rec"))


def test_descriptive_task_keeps_its_own_section_only():
    # Without a possible recommendation the module is not sent along: bounded request size.
    blocks = guideline()
    context = _context(_task(tasks_for(blocks, blocks), "m1-bg"))
    assert not {"m1-rat", "m1-ow", "m1-rec"} & context
    assert "m1" in context


def test_document_title_level_is_not_a_module():
    # Older parsers put the document title first; the module is the level below the shared root.
    blocks = [dict(b, section_path=["Smetten", *b["section_path"]]) for b in guideline()]
    context = _context(_task(tasks_for(blocks, blocks, title_path=TITLE), "m1-rec"))
    assert {"m1-rat", "m1-ow"} <= context
    assert not {"m2-rat", "m2-rec"} & context


def test_flat_source_does_not_pull_in_the_whole_document():
    blocks = [block("rec", "Gebruik geen zalf.", ["Aanbevelingen"]),
              block("other", "Over de werkgroep.", ["Verantwoording"])]
    assert "other" not in _context(_task(tasks_for(blocks, blocks), "rec"))


def test_explicit_reference_to_another_module_stays_traceable():
    blocks = guideline() + [block("t2", "Tabel 2. Huidplooien", ["Bijlagen", "Tabel 2"]),
                            block("t2-row", "Liezen en oksels", ["Bijlagen", "Tabel 2"])]
    blocks[2] = dict(blocks[2], text=blocks[2]["text"] + " Zie Tabel 2.")
    assert {"t2", "t2-row"} <= _context(_task(tasks_for(blocks, blocks), "m1-rec"))


def test_oversized_module_context_is_an_explicit_error_without_truncation():
    blocks = guideline()
    long = "x" * (MAX_CONTEXT_CHARS + 1)
    blocks[4] = dict(blocks[4], text=long)
    task = _task(tasks_for(blocks, blocks), "m1-rec")
    assert task["error_code"] == "source_task_context_limit_exceeded"
    assert next(b for b in task["evidence_blocks"] if b["block_id"] == "m1-rat")["text"] == long


def test_untitled_single_module_is_its_own_module():
    # #997: without a recorded title the first path level is the module, so a single
    # untitled module ([module, Aanbevelingen]) keeps its Rationale and considerations.
    blocks = [b for b in guideline() if b["section_path"][0].startswith("Module 1")]
    context = _context(_task(tasks_for(blocks, blocks), "m1-rec"))
    assert {"m1-rat", "m1-ow"} <= context


def test_recommendation_directly_under_a_titled_module_stays_in_that_module():
    blocks = [dict(b, section_path=["Smetten", *b["section_path"]]) for b in guideline()]
    blocks.append(block("m1-direct", "Overweeg altijd de huidplooien.", ["Smetten", "Module 1: Risicofactoren"]))
    context = _context(_task(tasks_for(blocks, blocks, title_path=TITLE), "m1-direct"))
    assert "m1-rat" in context
    assert not {"m2-rat", "m2-rec"} & context


def test_unsectioned_preface_does_not_erase_the_document_root():
    # Codex on #994: content before the first heading has section_path [] in the HTML extractor.
    blocks = [block("preface", "Deze richtlijn is bedoeld voor verpleegkundigen.", [])]
    blocks += [dict(b, section_path=["Smetten", *b["section_path"]]) for b in guideline()]
    context = _context(_task(tasks_for(blocks, blocks, title_path=TITLE), "m1-rec"))
    assert {"m1-rat", "m1-ow"} <= context
    assert not {"m2-rat", "m2-rec"} & context


def test_titled_module_without_subsections_still_separates_modules():
    # Codex on #994: one module with subsections, another with text directly under its heading.
    m1, m2 = "Module 1: Risicofactoren", "Module 2: Preventieve maatregelen"
    blocks = [dict(b, section_path=["Smetten", *b["section_path"]]) for b in guideline()
              if b["section_path"][0] == m1]
    blocks += [block("m2", m2, ["Smetten", m2], heading=m2),
               block("m2-rec", "Houd de huidplooien droog.", ["Smetten", m2]),
               block("m2-txt", "Vocht verhoogt het risico.", ["Smetten", m2])]
    context = _context(_task(tasks_for(blocks, blocks, title_path=TITLE), "m1-rec"))
    assert {"m1-rat", "m1-ow"} <= context
    assert not {"m2", "m2-rec", "m2-txt"} & context


def test_titled_document_with_only_flat_modules_does_not_leak():
    # Codex on #994: every module holds its text directly under [title, module].
    m1, m2 = "Module 1: Risicofactoren", "Module 2: Preventieve maatregelen"
    blocks = [block("t", "Smetten", ["Smetten"], heading="Smetten"),
              block("m1", m1, ["Smetten", m1], heading=m1),
              block("m1-rec", "Breng bij iedere patiënt de risicofactoren voor smetten in kaart.", ["Smetten", m1]),
              block("m2", m2, ["Smetten", m2], heading=m2),
              block("m2-rec", "Houd de huidplooien droog.", ["Smetten", m2])]
    context = _context(_task(tasks_for(blocks, blocks, title_path=TITLE), "m1-rec"))
    assert not {"m2", "m2-rec"} & context


def test_top_level_appendix_peer_does_not_erase_the_title_root():
    # Codex on #994: [Guideline, Module ...] plus a sectioned top-level [Bijlagen] peer.
    blocks = [dict(b, section_path=["Smetten", *b["section_path"]]) for b in guideline()]
    blocks += [block("bijl", "Bijlage 1. Zoekverantwoording", ["Bijlagen"], heading="Bijlagen"),
               block("bijl-txt", "De zoekactie liep tot 2024.", ["Bijlagen"])]
    context = _context(_task(tasks_for(blocks, blocks, title_path=TITLE), "m1-rec"))
    assert {"m1-rat", "m1-ow"} <= context
    assert not {"m2", "m2-rec", "m2-rat", "bijl", "bijl-txt"} & context


def test_titled_document_with_normative_appendix_peer_does_not_leak():
    # #997: a top-level appendix with a normative-looking sentence beside a titled
    # guideline is its own section; the recorded title keeps the modules apart.
    blocks = [dict(b, section_path=["Smetten", *b["section_path"]]) for b in guideline()]
    blocks += [block("bijl", "Bijlagen", ["Bijlagen"], heading="Bijlagen"),
               block("bijl-rec", "Gebruik deze zoekstrategie voor elke herziening.", ["Bijlagen"])]
    context = _context(_task(tasks_for(blocks, blocks, title_path=TITLE), "m1-rec"))
    assert {"m1-rat", "m1-ow"} <= context
    assert not {"m2", "m2-rec", "m2-rat", "bijl", "bijl-rec"} & context


def _html(path, tag, ordinal):
    return {"section_path": list(path), "source_locator": {"locator_type": "web_line_range",
            "locator_value": f"lines:1-1;{tag}:{ordinal}"}}


def test_document_title_comes_from_the_single_html_h1():
    fragments = [_html(["Smetten"], "h1", 1), _html(["Smetten", "Module 1"], "h2", 1),
                 _html(["Smetten", "Module 1"], "p", 1)]
    assert document_title_path(fragments) == ("Smetten",)


def test_several_h1_headings_are_sections_not_a_title():
    fragments = [_html(["Module 1"], "h1", 1), _html(["Module 2"], "h1", 2)]
    assert document_title_path(fragments) == ()


def test_pdf_fragments_have_no_title_path():
    fragments = [{"section_path": ["Smetten"], "source_locator": {"locator_type": "page_bbox",
                  "locator_value": "page:1;bbox:0,0,1,1"}}]
    assert document_title_path(fragments) == ()


def test_module_of_follows_the_title():
    assert module_of(["Smetten", "Module 1", "Aanbevelingen"], TITLE) == ("Smetten", "Module 1")
    assert module_of(["Smetten"], TITLE) is None
    assert module_of(["Bijlagen"], TITLE) == ("Bijlagen",)
    assert module_of(["Module 1", "Aanbevelingen"]) == ("Module 1",)
    assert module_of([]) is None


def test_formation_passes_the_parser_title_to_task_planning(monkeypatch):
    # #997: execute derives the title from the parser record. In production the
    # content fragments have the headings, including the <h1>, filtered out
    # (_content_fragments), so the title must come from the evidence fragments.
    from src.vorming import bounded_formation_v1 as bf
    from src.vorming.bounded_model_call_v1 import ModelCallLimits
    from src.vorming.pre_review_semantic_v1 import _content_fragments, _evidence_fragments
    from src.vorming.semantic_passage_v1 import semantic_source_blocks
    from tests.test_recommendation_context_v3 import source
    rows = [("Smetten", ["Smetten"], "h1", "Smetten"), ("Module 1", ["Smetten", "Module 1"], "h2", "Module 1"),
            ("Gebruik geen zalf", ["Smetten", "Module 1"], "p", None)]
    fragments = [dict(source(t)[0], fragment_id=str(i), fragment_hash=str(i), section_path=path, heading=heading,
                      object_type="heading" if heading else source(t)[0].get("object_type"),
                      source_locator={"locator_type": "web_line_range", "locator_value": f"lines:{i}-{i};{tag}:{i}"})
                 for i, (t, path, tag, heading) in enumerate(rows)]
    content, evidence = _content_fragments(fragments), _evidence_fragments(fragments)
    assert not any(f.get("heading") == "Smetten" for f in content)  # the production filter drops the title
    blocks = semantic_source_blocks(content)
    seen = []
    real = bf.tasks_for
    monkeypatch.setattr(bf, "tasks_for", lambda *a, **k: seen.append(k.get("title_path")) or real(*a, **k))
    bf.execute(blocks=blocks, evidence_blocks=semantic_source_blocks(evidence),
               validator_input={"fragments": content, "document_id": "test", "evidence_fragments": evidence,
                                "allowed_candidate_block_ids": [b["block_id"] for b in blocks], "field_contract_v3": True},
               provider=lambda **k: None, limits=ModelCallLimits(total=0))
    assert seen == [("Smetten",)]
