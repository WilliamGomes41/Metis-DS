"""Synthetic identities and real local persistence; no authentication material."""
import hashlib
import json
from copy import deepcopy
from pathlib import Path

from src.operations_console_v1 import ConsoleError, OperationsConsole

HTML = b"<!doctype html><html><body><h1>Voorbeeld</h1><p>Een waarneming is een beschrijving.</p></body></html>"
ACTOR, REVIEWER, OTHER = "author", "reviewer", "other"


def console_at(root, cls=OperationsConsole):
    console = cls(root=root, source_store=root / "sources", runtime=root / "runtime")
    console._accounts = {
        key: {"account_id": key, "username": key, "display_name": key.title(), "roles": roles}
        for key, roles in ((ACTOR, ["researcher", "reviewer"]),
                           (REVIEWER, ["reviewer"]), (OTHER, ["reviewer"]))
    }
    console._save_accounts()
    return console


def select_literal(console, proposed_type="definition"):
    """Offline selection through the real deterministic candidate creator."""
    from src.integrity_kernel import stable_hash
    from src.semantic_passage_v1 import semantic_source_blocks, semantic_units_from_proposal
    from src.knowledge_materialisation_v1 import materialise_knowledge_candidates
    original = console._fragments_and_spec

    def prepare(*args, **kwargs):
        fragments, spec = original(*args, **kwargs)
        blocks = semantic_source_blocks(fragments)
        block = next(b for b in blocks if "Een waarneming" in b["text"])
        proposal = {"objects": [{"spans": [{"block_id": block["block_id"], "start": 0, "end": len(block["text"])}],
                                  "proposed_object_type": proposed_type}], "relations": [], "abstain_reason": None}
        units = semantic_units_from_proposal(fragments, document_id=kwargs["document_id"], proposal=proposal)
        candidates = materialise_knowledge_candidates(units, document_id=kwargs["document_id"], fragments=fragments)
        for row in candidates:
            row["semantic_passage"].update(formation_mode="semantic-source-bound-v1", model="offline-selection",
                source_blocks_hash=stable_hash(blocks), proposal_hash=stable_hash(proposal))
        spec["objects"] = [r for r in spec["objects"] if r.get("object_type") in {"document", "heading"}] + candidates
        return fragments, spec
    console._fragments_and_spec = prepare


def command(**changes):
    return dict(actor_id=ACTOR, ingest_kind="new", title="Voorbeeld & bron", version="1.0",
                date="2026-10-17", live_url="", class_="richtlijn", family="fixture",
                named_reviewers=[REVIEWER], filename="source.html", data=HTML,
                content_type="text/html", **{}) | changes


def policy(primary=REVIEWER, required=(), optional=()):
    return {"contract": "explicit-review-v1", "revision": 1, "primary": primary,
            "assignments": [{"reviewer_id": key, "participation": kind}
                            for kind, keys in (("required", required), ("optional", optional)) for key in keys]}


def choice(option="one_other", reviewers=None, four_eyes=False, readers=()):
    return dict(option=option, reviewers=[REVIEWER] if reviewers is None else reviewers,
                four_eyes_required=four_eyes, readers=list(readers))


def observe(console, operation):
    try:
        outcome = {"return": operation()}
    except ConsoleError as error:
        outcome = {"error": error.code}
    files = {}
    for path in sorted(console.root.rglob("*")):
        if not path.is_file() or path.name.startswith(".") or path.suffix == ".lock":
            continue
        raw = path.read_bytes()
        try:
            value = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            if path.suffix == ".jsonl":
                value = [json.loads(line) for line in raw.decode().splitlines() if line]
            else:
                value = {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
        files[str(path.relative_to(console.root))] = value
    return {"outcome": outcome, "envelopes": deepcopy(console._envelopes), "files": files}
