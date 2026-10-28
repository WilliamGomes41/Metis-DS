"""B23 richtlijn-vormingscontract: fail-first golden tests (Smetten).

Bron: docs/specs/RICHTLIJN-VORMINGSCONTRACT.md in WilliamGomes41/Metis @ 9e87fed.
Brontekst: Conceptrichtlijn Smetten v1 (2026-07); paginaverwijzingen per fixture.
Referentieset: tests/fixtures/smetten-reference.json.

Deze tests MOETEN falen op huidige main (xfail strict). Ze raken de
formatielogica en check-uitkomsten NIET aan; die zijn van Forge.
Asserties zijn inhoudelijk; een vast objectaantal is NOOIT het criterium (RL-F3-04).
Deze tests zijn alleen fail-first; ze zijn NOOIT acceptatiebewijs. De referentieset
heeft status 'validated by William (recommendations), 2026-10-15': dat dekt de lijst van
19 aanbevelingen; de OPENVRAAG-items vallen NIET onder die validatie en blijven open.
Elke brontekst-literal MOET letterlijk uit de PDF komen (pagina per literal);
test_every_literal_is_verbatim_in_pdftotext bewaakt dat.

OPENVRAAG-B23-T1: het contract noemt nog geen veldnaam voor passage-disposities
(RL-F1-03/-04). `excluded_with_reason` wordt daarom voorlopig overal in spec en
rijen gezocht; de assertie MOET versmallen tot het veld dat Forge benoemt.

# release-control-evidence: scope/belofte
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from src.vorming.admission_gate_v1 import apply_admission_gate
from src.operations_console_v1 import ConsoleError
from src.vorming.pre_review_semantic_v1 import semantic_spec_from_fragments
from src.vorming.semantic_transform_generic_v1 import transform
from src.vorming.source_bound_fields_v3 import FIELDS

MODES = ["semantic-source-bound-v3"]  # deterministic-v1 was removed in Protocol 4.3.0
XFAIL = pytest.mark.xfail(strict=True, reason="B23 nog niet geïmplementeerd op main (Forge)")
REFERENCE = json.loads((Path(__file__).parent / "fixtures" / "smetten-reference.json").read_text())

M1 = "Module 1: Risicofactoren"
# p14, kop "Achtergrond" (inleiding van module 1).
INTRO = ("Hoewel preventieve maatregelen ter voorkoming van smetten eenvoudig van aard kunnen zijn, "
         "worden ze in de praktijk niet altijd (tijdig) ingezet. Een belangrijk knelpunt in de praktijk is dat "
         "het voor verzorgenden, verpleegkundigen, en verpleegkundig specialisten niet altijd duidelijk is bij "
         "welke patiënten een verhoogd risico bestaat op het ontstaan van smetten.")
# p18, Aanbevelingen + stempel.
REC = "Breng bij iedere patiënt de risicofactoren voor smetten in kaart, om te bepalen of preventieve maatregelen nodig zijn."
STAMP = "Sterk – voor"
# p18, voorwaarde/toelichting buiten de aanbevelingstekst (letterlijke kopregel van de lijst).
CONDITION = "De risicofactoren zijn:"
# p18, Rationale (overwegingen).
CONSIDERATION = ("Het vroegtijdig herkennen van risicofactoren maakt gerichte preventieve maatregelen mogelijk.")
# p41, module 4 "nat" groep 2: zwakke aanbeveling; doelgroep staat alleen in de groepskop.
WEAK = "Overweeg een zinkoxidesmeersel FNA"
WEAK_STAMP = "Zwak – voor"


def frag(fid, text, path, page, **extra):
    return {"fragment_id": fid, "fragment_hash": f"{fid}-hash", "raw_text": text, "clean_text": text,
            "section_path": path, "source_locator": {"locator_type": "page_bbox",
            "locator_value": f"page:{page};bbox:0,0,1,1"}, **extra}


def module1():
    return [
        frag("m1-heading", M1, [M1], 14, object_type="heading"),
        frag("m1-intro", INTRO, [M1, "Achtergrond"], 14),
        frag("m1-overweging", CONSIDERATION, [M1, "Van bewijs naar aanbeveling (overwegingen)", "Rationale"], 18),
        frag("m1-rec", REC, [M1, "Aanbevelingen"], 18),
        frag("m1-stamp", STAMP, [M1, "Aanbevelingen"], 18),
        frag("m1-condition", CONDITION, [M1, "Aanbevelingen"], 18),
    ]


def weak_without_target_group():
    return [frag("m4-weak", WEAK, ["Module 4", "Aanbevelingen"], 41),
            frag("m4-weak-stamp", WEAK_STAMP, ["Module 4", "Aanbevelingen"], 41)]


_LABEL = re.compile(r"^(Sterk|Zwak) – (voor|tegen)$")


def _maximal_provider(_url, _headers, payload, _timeout):
    """Adversarial AI: wijst elk aangeboden bronblok aan als aanbeveling.

    Het contract MOET de inleiding, overwegingen en voorwaarden toch correct
    vormen; de AI wijst alleen spans aan (RL-F2-01).
    """
    data = json.loads(payload["input"][1]["content"])
    if data.get("selection_targets"):
        body = {"objects": [], "relations": [], "abstain_reason": "uncertain"}
    else:
        evidence = [*data["source_blocks"], *data.get("evidence_blocks", [])]
        objects = []
        for block in data["source_blocks"]:
            text = block["text"]
            if _LABEL.match(text.strip()):
                continue
            ref = lambda lit, owner=block: {"block_id": owner["block_id"], "literal": lit, "occurrence": None}
            fields = {f: {"span": None, "missing_reason": "not_applicable"} for f in FIELDS}
            fields["subject_span"] = fields["actor_span"] = {"span": None, "missing_reason": "not_stated"}
            for f, lit in {"predicate_span": text.split()[0], "type_evidence_spans": text.split()[0],
                           "recommended_action": text, "action_object_or_goal": text.split()[-1],
                           "recommendation_evidence_span": text}.items():
                fields[f] = {"span": ref(lit), "missing_reason": None}
            stamp = next((b for b in evidence if _LABEL.match(b["text"].strip())), None)
            m = _LABEL.match(stamp["text"].strip()) if stamp else None
            objects.append({"spans": [ref(text)], "proposed_object_type": "recommendation",
                "recommendation_semantics": {
                    "direction": "against" if (m and m.group(2) == "tegen") or " geen " in f" {text} " else "for",
                    "direction_evidence": ref(text),
                    "strength": ("strong" if m.group(1) == "Sterk" else "weak") if m else None,
                    "strength_status": "explicit" if m else "not_stated",
                    "strength_evidence": ref(stamp["text"].strip(), stamp) if m else None},
                "field_evidence": fields, "context_evidence": []})
        body = {"objects": objects, "relations": [], "abstain_reason": None}
    return {"status": "completed", "output": [{"type": "message", "content": [
        {"type": "output_text", "text": json.dumps(body)}]}]}


def form(mode, fragments):
    """Vorm via de echte productiepaden per modus; geen eigen formatielogica."""
    spec = semantic_spec_from_fragments(document_id="smetten", title="Smetten", family="smetten",
        class_="richtlijn", fragments=fragments, content_kind="pdf", api_key="test", model="test",
        post_json=_maximal_provider, field_contract_v3=True)
    manifest = {"canonical_source": {"source_id": "smetten", "title": "Smetten", "source_type": "pdf",
        "source_url": "test", "source_level": "national", "canonicality": "canonical",
        "integrity_status": "verified", "source_checksum": "a" * 64, "version": "1"}}
    rows = transform(spec, manifest, fragments)
    rows = apply_admission_gate(rows, klasse="richtlijn", fragments=fragments, document_version="1",
                                source_hash="a" * 64)
    return spec, rows


def _strings(value):
    if isinstance(value, dict):
        for k, v in value.items():
            yield str(k)
            yield from _strings(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            yield from _strings(v)
    elif value is not None:
        yield str(value)


def _text(row):
    return (row.get("content") or {}).get("clean_text") or row.get("text") or ""


def knowledge_objects(rows):
    return [r for r in rows if r.get("object_type") not in {"document", "heading"}]


def _from_fragment(row, fid):
    return fid in set(_strings(row.get("source") or {})) | set(_strings(row.get("metadata") or {}))


def admitted(row):
    return ((row.get("metadata") or {}).get("admission") or {}).get("gate_result") == "allowed"


EXCERPTS = json.loads((Path(__file__).parent / "fixtures" / "smetten-pdftotext-excerpts.json").read_text())
LITERALS = [(INTRO, 14), (REC, 18), (STAMP, 18), (CONDITION, 18), (CONSIDERATION, 18), (WEAK, 41), (WEAK_STAMP, 41)]


def _norm(text):
    return " ".join(text.split())


@pytest.mark.parametrize("literal,page", LITERALS)
def test_every_literal_is_verbatim_in_pdftotext(literal, page):
    """Niet-xfail: elke literal staat letterlijk (op witruimte na) in pdftotext van zijn pagina."""
    assert _norm(literal) in _norm(EXCERPTS["pages"][str(page)])
    pdf = os.environ.get("METIS_SMETTEN_PDF")
    if pdf and shutil.which("pdftotext"):
        live = subprocess.run(["pdftotext", "-f", str(page), "-l", str(page), pdf, "-"],
                              capture_output=True, text=True, check=True).stdout
        assert _norm(literal) in _norm(live)


def test_reference_fixture_is_content_complete():
    """Niet-xfail sanity: de referentie bevat de gebruikte brontekst letterlijk."""
    texts = [r["text"] for m in REFERENCE["modules"] for r in m["recs"]]
    assert REC in texts and WEAK in texts
    assert REFERENCE["inleiding"]["objects"] == 0
    assert REFERENCE["status"] == "validated by William (recommendations), 2026-10-15"
    assert "OPENVRAAG" in REFERENCE["validation"]["not_covered"]


@XFAIL
@pytest.mark.parametrize("mode", MODES)
def test_rl_f1_04_intro_yields_no_objects_and_is_excluded_with_reason(mode):
    spec, rows = form(mode, module1())
    from_intro = [r for r in knowledge_objects(rows) if _from_fragment(r, "m1-intro") or INTRO[:60] in _text(r)]
    assert from_intro == [], [_text(r)[:80] for r in from_intro]
    dispositions = [d for d in _walk_dicts([spec, rows]) if "m1-intro" in set(_strings(d))
                    and "excluded_with_reason" in set(_strings(d))]
    assert dispositions, "inleiding MOET excluded_with_reason krijgen (RL-F1-04)"


def _walk_dicts(value):
    if isinstance(value, dict):
        yield value
        for v in value.values():
            yield from _walk_dicts(v)
    elif isinstance(value, list):
        for v in value:
            yield from _walk_dicts(v)


@XFAIL
@pytest.mark.parametrize("mode", MODES)
def test_order_recommendation_then_consideration_then_condition(mode):
    _, rows = form(mode, module1())
    objects = knowledge_objects(rows)
    recs = [r for r in objects if REC in _text(r)]
    assert recs, "stap 1: de aanbeveling MOET als object terugkomen"
    rec = recs[0]
    sem = rec.get("proposed_recommendation_semantics") or (rec.get("metadata") or {}).get("recommendation_semantics") or {}
    assert sem.get("direction") == "for" and sem.get("strength") == "strong", sem
    # Stap 2: overweging NOOIT zelfstandig, MOET als toelichting aan de aanbeveling hangen.
    standalone = [r for r in objects if r is not rec and (CONSIDERATION in _text(r) or _from_fragment(r, "m1-overweging"))]
    assert standalone == [], "overweging MAG NIET een zelfstandig object zijn (RL-F2-08)"
    assert "m1-overweging" in set(_strings(rec)), "overweging MOET via passagereferentie aan de aanbeveling hangen (RL-F2-09)"
    # Stap 3: voorwaarde buiten de tekst MOET een veld van de aanbeveling zijn, met letterlijke tekst + eigen referentie.
    cond_objects = [r for r in objects if r is not rec and CONDITION in _text(r)]
    assert cond_objects == [], "voorwaarde MAG NIET een apart object worden (RL-F2-12)"
    rec_strings = set(_strings(rec))
    assert "m1-condition" in rec_strings and any(CONDITION in s for s in rec_strings), "RL-F2-16"


@XFAIL
@pytest.mark.parametrize("mode", MODES)
def test_weak_recommendation_without_target_group_is_rejected(mode):
    try:
        _, rows = form(mode, weak_without_target_group())
    except ConsoleError as exc:
        assert "target_group" in str(exc) or "doelgroep" in str(exc), exc
        return
    weak = [r for r in knowledge_objects(rows) if WEAK in _text(r)]
    assert weak, "de zwakke aanbeveling MOET zichtbaar blijven (afgewezen, niet verdwenen)"
    for row in weak:
        admission = (row.get("metadata") or {}).get("admission") or {}
        assert not admitted(row), "zwakke aanbeveling zonder doelgroep MOET afgewezen worden (RL-F2-07)"
        assert any("target_group" in c for c in admission.get("reason_codes") or []), admission
