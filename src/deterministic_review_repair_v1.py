"""Deterministic Review repair between human feedback and re-review.

A reviewer never writes canonical replacement text here. A revise decision is
only committed together with one executable repair specification, and the
result is a new ``needs_review`` proposal (or a repaired relation graph).
Source text is rebuilt from the verified frozen source through the existing
extractors. No LLM and no second workflow store are introduced.
"""
from __future__ import annotations

import html
import re
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import quote

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from src.closed_review_loop_v1 import ClosedLoopReviewConsole
from src.integrity_kernel import schema_errors, sha256_bytes, stable_hash, stamp_canonical_hashes
from src.operations_console_v1 import ConsoleError, OperationsConsole, SNAPSHOT_OBJECT_WRITE_CONFLICT
from src.publish_authorization_v1 import invalidate_for_object
from src.review_cockpit_v1 import map_eindoordeel
from src.serving_relations_v1 import binding_relations


REPAIR_SOURCE_UNITS = "source_units"
REPAIR_MERGE_OBJECTS = "merge_objects"
REPAIR_SUPPORT_RELATION = "support_relation"
REPAIR_CLASSIFICATION = "classification"
_REPAIR_KINDS = frozenset(
    {
        REPAIR_SOURCE_UNITS,
        REPAIR_MERGE_OBJECTS,
        REPAIR_SUPPORT_RELATION,
        REPAIR_CLASSIFICATION,
    }
)
_ALLOW_REVISE_WRITE: ContextVar[bool] = ContextVar(
    "metis_allow_revise_write", default=False
)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=(?:[\"'“”‘’(\[])?[A-ZÀ-ÖØ-Þ0-9])")


def _norm(value: str) -> str:
    return " ".join(str(value or "").split())


def _esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def _review_url(snapshot_id: str, object_id: str) -> str:
    return (
        f"/review?document={quote(snapshot_id, safe='')}"
        f"&object={quote(object_id, safe='')}"
    )


def _hidden(name: str, value: Any) -> str:
    return f'<input type="hidden" name="{_esc(name)}" value="{_esc(value)}">'


class StructuredRepairRequired(ConsoleError):
    """Internal control-flow signal: no review state has been written yet."""

    def __init__(self, submission: dict[str, Any]) -> None:
        self.submission = deepcopy(submission)
        super().__init__("structured_repair_required")


@contextmanager
def _allow_revise_write() -> Iterator[None]:
    token = _ALLOW_REVISE_WRITE.set(True)
    try:
        yield
    finally:
        _ALLOW_REVISE_WRITE.reset(token)


class DeterministicRepairReviewConsole(ClosedLoopReviewConsole):
    """Closed-loop console where revise cannot remain as abandoned normal work."""

    def _preflight_structured_repair(self, submission: dict[str, Any]) -> None:
        actor_id = str(submission.get("actor_id") or "")
        snapshot_id = str(submission.get("snapshot_id") or "")
        object_id = str(submission.get("object_id") or "")
        expected_revision = str(submission.get("expected_revision") or "")
        reviewer = self._require_role(actor_id, "reviewer")
        envelope = self._envelope(snapshot_id)
        if actor_id not in (envelope.get("named_reviewers") or []):
            raise ConsoleError("reviewer_not_named_on_snapshot")
        if not object_id or self._current_object(snapshot_id, object_id) is None:
            raise ConsoleError("unknown_object")
        if not str(submission.get("comment") or "").strip():
            raise ConsoleError("review_comment_required")
        if expected_revision and self.objects_revision(snapshot_id) != expected_revision:
            raise ConsoleError(
                SNAPSHOT_OBJECT_WRITE_CONFLICT,
                current_revision=self.objects_revision(snapshot_id),
            )
        _ = reviewer

    def review_object(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        if args or _ALLOW_REVISE_WRITE.get():
            return super().review_object(*args, **kwargs)
        decision = map_eindoordeel(
            str(kwargs.get("eindoordeel") or ""),
            str(kwargs.get("decision") or ""),
        )
        suitability = str(kwargs.get("suitability") or "").strip()
        if decision != "revise" or not suitability:
            return super().review_object(**kwargs)
        submission = {
            "actor_id": str(kwargs.get("actor_id") or ""),
            "snapshot_id": str(kwargs.get("snapshot_id") or ""),
            "object_id": str(kwargs.get("object_id") or ""),
            "expected_revision": str(kwargs.get("expected_revision") or ""),
            "comment": str(kwargs.get("comment") or "").strip(),
            "proposed_correction": str(kwargs.get("proposed_correction") or "").strip(),
            "confirmed_object_type": str(kwargs.get("confirmed_object_type") or ""),
            "recommendation_strength": str(kwargs.get("recommendation_strength") or ""),
            "suitability": suitability,
            "eindoordeel": str(kwargs.get("eindoordeel") or "goedkeuren_na_correctie"),
            "documentpositie_action": str(kwargs.get("documentpositie_action") or ""),
            "found_under": str(kwargs.get("found_under") or ""),
            "parent_choice": str(kwargs.get("parent_choice") or ""),
            "type_action": str(kwargs.get("type_action") or ""),
        }
        self._preflight_structured_repair(submission)
        raise StructuredRepairRequired(submission)

    def accept_source_continuation(self, **kwargs: Any) -> dict[str, Any]:
        snapshot_id = str(kwargs.get("snapshot_id") or "")
        expected_revision = str(kwargs.get("expected_revision") or "")
        with self._atomic_snapshot_mutation(snapshot_id):
            if expected_revision and self.objects_revision(snapshot_id) != expected_revision:
                raise ConsoleError(
                    SNAPSHOT_OBJECT_WRITE_CONFLICT,
                    current_revision=self.objects_revision(snapshot_id),
                )
            with _allow_revise_write():
                return super().accept_source_continuation(**kwargs)

    def source_fragment_catalog(
        self, *, snapshot_id: str, object_id: str
    ) -> list[dict[str, Any]]:
        """Re-extract source fragments from the verified frozen source, read-only."""
        envelope = self._envelope(snapshot_id)
        self._require_open_original(snapshot_id, object_id)
        freeze_path = Path(str(envelope.get("binary_path") or ""))
        if not freeze_path.is_file():
            raise ConsoleError("freeze_bytes_missing")
        freeze_bytes = freeze_path.read_bytes()
        if sha256_bytes(freeze_bytes) != str(envelope.get("sha256") or ""):
            raise ConsoleError("freeze_bytes_missing")
        fragments, _spec = self._fragments_and_spec(
            str(envelope["content_kind"]),
            freeze_path,
            data=freeze_bytes,
            document_id=str(envelope["document_id"]),
            source_id=str(envelope["source_id"]),
            title=str(envelope["title"]),
            family=str(envelope["family"]),
            class_=str(envelope["class"]),
        )
        catalog: list[dict[str, Any]] = []
        for index, fragment in enumerate(fragments):
            fragment_id = str(fragment.get("fragment_id") or "")
            text = _norm(
                str(fragment.get("clean_text") or fragment.get("raw_text") or "")
            )
            locator = deepcopy(fragment.get("source_locator") or {})
            if not fragment_id or not text or not locator.get("locator_value"):
                continue
            heading = _norm(str(fragment.get("heading") or ""))
            catalog.append(
                {
                    "fragment_id": fragment_id,
                    "fragment_hash": str(fragment.get("fragment_hash") or ""),
                    "text": text,
                    "section_path": [
                        str(item) for item in (fragment.get("section_path") or [])
                    ],
                    "heading": heading,
                    "is_heading": bool(heading and heading == text),
                    "sequence": int(fragment.get("sequence") or index + 1),
                    "source_page": fragment.get("source_page"),
                    "bbox": deepcopy(fragment.get("bbox")),
                    "source_locator": locator,
                    "catalog_index": index,
                }
            )
        by_id = {row["fragment_id"]: row for row in catalog}
        current = self._current_object(snapshot_id, object_id)
        for ref in (current.get("provenance") or {}).get("source_fragments") or []:
            raw_id = str(ref.get("raw_object_id") or "")
            expected_hash = str(ref.get("raw_content_hash") or "")
            row = by_id.get(raw_id)
            if row is None:
                raise ConsoleError("repair_source_fragment_missing")
            if expected_hash and row.get("fragment_hash") != expected_hash:
                raise ConsoleError("repair_source_fragment_changed")
        return catalog

    def source_units(
        self, *, snapshot_id: str, object_id: str
    ) -> list[dict[str, Any]]:
        """Closed, deterministic selectable spans derived from frozen fragments."""
        units: list[dict[str, Any]] = []
        for fragment in self.source_fragment_catalog(
            snapshot_id=snapshot_id, object_id=object_id
        ):
            if fragment["is_heading"]:
                continue
            text = str(fragment["text"])
            sentences = [part.strip() for part in _SENTENCE_SPLIT_RE.split(text) if part.strip()]
            if len(sentences) <= 1:
                sentences = [text]
            for unit_index, sentence in enumerate(sentences):
                units.append(
                    {
                        "unit_id": f"{fragment['fragment_id']}::s{unit_index + 1}",
                        "fragment_id": fragment["fragment_id"],
                        "fragment_hash": fragment["fragment_hash"],
                        "text": sentence,
                        "section_path": deepcopy(fragment["section_path"]),
                        "sequence": fragment["sequence"],
                        "catalog_index": fragment["catalog_index"],
                        "unit_index": unit_index,
                        "source_page": fragment["source_page"],
                        "bbox": deepcopy(fragment["bbox"]),
                        "source_locator": deepcopy(fragment["source_locator"]),
                    }
                )
        return units

    @staticmethod
    def _fragment_ref(unit: dict[str, Any]) -> dict[str, Any]:
        return {
            "raw_object_id": unit["fragment_id"],
            "page": unit.get("source_page"),
            "raw_content_hash": unit.get("fragment_hash"),
            "bbox": deepcopy(unit.get("bbox")),
            "coordinate_status": (
                "available" if unit.get("bbox") is not None else "not_applicable"
            ),
            "source_locator": deepcopy(unit["source_locator"]),
        }

    def _selected_source_material(
        self,
        *,
        snapshot_id: str,
        object_id: str,
        unit_ids: list[str],
        units: list[dict[str, Any]],
    ) -> tuple[str, list[dict[str, Any]], list[str]]:
        chosen_ids = list(dict.fromkeys(str(item).strip() for item in unit_ids if str(item).strip()))
        if not chosen_ids:
            raise ConsoleError("repair_source_units_required")
        by_id = {row["unit_id"]: row for row in units}
        if any(unit_id not in by_id for unit_id in chosen_ids):
            raise ConsoleError("repair_source_unit_unknown")
        chosen = [by_id[unit_id] for unit_id in chosen_ids]
        chosen.sort(key=lambda row: (row["catalog_index"], row["unit_index"]))

        content_positions = {
            fragment_id: index
            for index, fragment_id in enumerate(
                dict.fromkeys(row["fragment_id"] for row in units)
            )
        }
        fragment_ids = list(dict.fromkeys(row["fragment_id"] for row in chosen))
        positions = sorted(content_positions[fragment_id] for fragment_id in fragment_ids)
        if positions and positions != list(range(positions[0], positions[-1] + 1)):
            raise ConsoleError("repair_source_units_must_be_contiguous")
        for fragment_id in fragment_ids:
            indexes = sorted(
                row["unit_index"] for row in chosen if row["fragment_id"] == fragment_id
            )
            if indexes != list(range(indexes[0], indexes[-1] + 1)):
                raise ConsoleError("repair_source_units_must_be_contiguous")

        text = _norm(" ".join(str(row["text"]) for row in chosen))
        if not text:
            raise ConsoleError("repair_source_units_required")
        refs_by_id: dict[str, dict[str, Any]] = {}
        for row in chosen:
            refs_by_id.setdefault(row["fragment_id"], self._fragment_ref(row))
        return text, list(refs_by_id.values()), [row["unit_id"] for row in chosen]

    def _finalize_source_provenance(
        self,
        *,
        snapshot_id: str,
        object_id: str,
        source_refs: list[dict[str, Any]],
        repair_spec: dict[str, Any],
    ) -> dict[str, Any]:
        revision = self.objects_revision(snapshot_id)
        rows = deepcopy(self._load_objects(snapshot_id, remember=False))
        live = self._current_object(snapshot_id, object_id)
        version = str(live.get("object_version") or "")
        updated: dict[str, Any] | None = None
        for index in range(len(rows) - 1, -1, -1):
            row = rows[index]
            if row.get("object_id") != object_id or str(row.get("object_version") or "") != version:
                continue
            row = deepcopy(row)
            provenance = row.setdefault("provenance", {})
            provenance["source_fragments"] = deepcopy(source_refs)
            provenance["revision_patch_hash"] = stable_hash(repair_spec)
            stamp_canonical_hashes(row)
            errors = schema_errors(row, self.schema_path)
            if errors:
                raise ConsoleError("revision_schema_invalid", " | ".join(errors))
            rows[index] = row
            updated = row
            break
        if updated is None:
            raise ConsoleError("unknown_object")
        self._commit_prepared_store(
            objects=(snapshot_id, rows), expected_revision=revision
        )
        return deepcopy(updated)

    def _source_repair(
        self,
        *,
        actor_id: str,
        snapshot_id: str,
        object_id: str,
        comment: str,
        unit_ids: list[str],
        units: list[dict[str, Any]],
    ) -> dict[str, Any]:
        text, source_refs, normalized_ids = self._selected_source_material(
            snapshot_id=snapshot_id,
            object_id=object_id,
            unit_ids=unit_ids,
            units=units,
        )
        repair_spec = {
            "repair_kind": REPAIR_SOURCE_UNITS,
            "source_unit_ids": normalized_ids,
            "source_fragment_ids": [ref["raw_object_id"] for ref in source_refs],
            "text": text,
        }
        revised = OperationsConsole.correct_object(
            self,
            actor_id=actor_id,
            snapshot_id=snapshot_id,
            object_id=object_id,
            patch={
                "reason": comment,
                "operations": [
                    {"op": "set", "path": "content.clean_text", "value": text},
                    {"op": "set", "path": "content.raw_text", "value": text},
                ],
            },
            additional_source_fragments=source_refs,
        )
        revised = self._finalize_source_provenance(
            snapshot_id=snapshot_id,
            object_id=object_id,
            source_refs=source_refs,
            repair_spec=repair_spec,
        )
        revised = self._clear_pending_review_metadata(
            snapshot_id=snapshot_id, object_id=object_id
        )
        self._append_audit_evidence(
            actor_id=actor_id,
            snapshot_id=snapshot_id,
            target=revised,
            decision="repair_source_units",
            original_suitability="source_units",
            final_disposition="needs_review",
            comment=comment,
            proposed_correction="",
        )
        return revised

    def _verified_object_source_position(
        self,
        obj: dict[str, Any],
        catalog_by_id: dict[str, dict[str, Any]],
    ) -> int:
        positions: list[int] = []
        source_texts: list[str] = []
        for ref in (obj.get("provenance") or {}).get("source_fragments") or []:
            raw_id = str(ref.get("raw_object_id") or "")
            row = catalog_by_id.get(raw_id)
            if row is None:
                raise ConsoleError("repair_source_fragment_missing")
            expected_hash = str(ref.get("raw_content_hash") or "")
            if expected_hash and row.get("fragment_hash") != expected_hash:
                raise ConsoleError("repair_source_fragment_changed")
            positions.append(int(row["catalog_index"]))
            source_texts.append(str(row["text"]))
        if not positions:
            raise ConsoleError("repair_source_fragment_missing")
        object_text = _norm(str((obj.get("content") or {}).get("clean_text") or ""))
        if object_text and object_text not in _norm(" ".join(source_texts)):
            raise ConsoleError("merge_target_not_source_bound")
        return min(positions)

    def _supersede_merge_targets(
        self,
        *,
        snapshot_id: str,
        target_ids: list[str],
        superseded_by: str,
    ) -> None:
        if not target_ids:
            return
        revision = self.objects_revision(snapshot_id)
        current = {row["object_id"]: row for row in self.snapshot_objects(snapshot_id)}
        versions = {
            object_id: str(current[object_id].get("object_version") or "")
            for object_id in target_ids
            if object_id in current
        }
        rows = deepcopy(self._load_objects(snapshot_id, remember=False))
        for index, row in enumerate(rows):
            object_id = str(row.get("object_id") or "")
            if object_id not in versions or str(row.get("object_version") or "") != versions[object_id]:
                continue
            updated = deepcopy(row)
            governance = updated.setdefault("governance", {})
            governance["validation_status"] = "superseded"
            governance["publication_status"] = "unpublished"
            governance["superseded_by"] = superseded_by
            stamp_canonical_hashes(updated)
            errors = schema_errors(updated, self.schema_path)
            if errors:
                raise ConsoleError("revision_schema_invalid", " | ".join(errors))
            rows[index] = updated
        bindings = deepcopy(self._bindings)
        for object_id in target_ids:
            bindings[snapshot_id] = invalidate_for_object(
                bindings.get(snapshot_id, []), object_id
            )
        self._commit_prepared_store(
            objects=(snapshot_id, rows),
            bindings=bindings,
            expected_revision=revision,
        )

    def _merge_repair(
        self,
        *,
        actor_id: str,
        snapshot_id: str,
        object_id: str,
        comment: str,
        merge_object_ids: list[str],
        catalog: list[dict[str, Any]],
    ) -> dict[str, Any]:
        target_ids = list(
            dict.fromkeys(
                str(item).strip()
                for item in merge_object_ids
                if str(item).strip() and str(item).strip() != object_id
            )
        )
        if not target_ids:
            raise ConsoleError("merge_target_required")
        current = {row["object_id"]: row for row in self.snapshot_objects(snapshot_id)}
        primary = current.get(object_id)
        if primary is None:
            raise ConsoleError("unknown_object")
        selected = [primary]
        for target_id in target_ids:
            target = current.get(target_id)
            if target is None or target.get("object_type") in {"document", "heading"}:
                raise ConsoleError("merge_target_not_repairable")
            governance = target.get("governance") or {}
            if governance.get("validation_status") in {"approved", "rejected", "superseded"}:
                raise ConsoleError("merge_target_not_repairable")
            if governance.get("publication_status") == "published":
                raise ConsoleError("merge_target_not_repairable")
            if binding_relations(target):
                raise ConsoleError("merge_target_has_confirmed_relations")
            selected.append(target)
        sections = {
            tuple((row.get("structure") or {}).get("section_path") or []) for row in selected
        }
        if len(sections) != 1:
            raise ConsoleError("merge_target_mixed_section")

        catalog_by_id = {row["fragment_id"]: row for row in catalog}
        selected.sort(
            key=lambda row: self._verified_object_source_position(row, catalog_by_id)
        )
        merged_text = _norm(
            " ".join(
                str((row.get("content") or {}).get("clean_text") or "")
                for row in selected
            )
        )
        refs_by_id: dict[str, dict[str, Any]] = {}
        for row in selected:
            for ref in (row.get("provenance") or {}).get("source_fragments") or []:
                raw_id = str(ref.get("raw_object_id") or "")
                source = catalog_by_id.get(raw_id)
                if source is None:
                    raise ConsoleError("repair_source_fragment_missing")
                refs_by_id.setdefault(
                    raw_id,
                    {
                        "raw_object_id": raw_id,
                        "page": source.get("source_page"),
                        "raw_content_hash": source.get("fragment_hash"),
                        "bbox": deepcopy(source.get("bbox")),
                        "coordinate_status": (
                            "available" if source.get("bbox") is not None else "not_applicable"
                        ),
                        "source_locator": deepcopy(source["source_locator"]),
                    },
                )
        source_refs = list(refs_by_id.values())
        sequence_values = [
            int((row.get("structure") or {}).get("sequence") or 0)
            for row in selected
            if (row.get("structure") or {}).get("sequence") is not None
        ]
        operations: list[dict[str, Any]] = [
            {"op": "set", "path": "content.clean_text", "value": merged_text},
            {"op": "set", "path": "content.raw_text", "value": merged_text},
        ]
        if sequence_values:
            operations.append(
                {"op": "set", "path": "structure.sequence", "value": min(sequence_values)}
            )
        repaired = OperationsConsole.correct_object(
            self,
            actor_id=actor_id,
            snapshot_id=snapshot_id,
            object_id=object_id,
            patch={"reason": comment, "operations": operations},
            additional_source_fragments=source_refs,
        )
        repaired = self._finalize_source_provenance(
            snapshot_id=snapshot_id,
            object_id=object_id,
            source_refs=source_refs,
            repair_spec={
                "repair_kind": REPAIR_MERGE_OBJECTS,
                "merge_object_ids": target_ids,
                "merged_text": merged_text,
            },
        )
        repaired = self._clear_pending_review_metadata(
            snapshot_id=snapshot_id, object_id=object_id
        )
        self._supersede_merge_targets(
            snapshot_id=snapshot_id,
            target_ids=target_ids,
            superseded_by=object_id,
        )
        self._append_audit_evidence(
            actor_id=actor_id,
            snapshot_id=snapshot_id,
            target=repaired,
            decision="repair_merge_objects",
            original_suitability="samenvoegen",
            final_disposition="needs_review",
            comment=comment,
            proposed_correction="",
        )
        return self._current_object(snapshot_id, object_id)

    def _classification_repair(
        self,
        *,
        actor_id: str,
        snapshot_id: str,
        object_id: str,
        submission: dict[str, Any],
    ) -> dict[str, Any]:
        type_change = (
            submission.get("type_action") == "type_wijzigen"
            and bool(submission.get("confirmed_object_type"))
        )
        position_change = (
            submission.get("documentpositie_action") == "andere_kop"
            and bool(submission.get("parent_choice"))
        )
        if not (type_change or position_change or submission.get("recommendation_strength")):
            raise ConsoleError("classification_repair_requires_change")
        self._reopen_for_review(snapshot_id, {object_id})
        repaired = self._clear_pending_review_metadata(
            snapshot_id=snapshot_id, object_id=object_id
        )
        self._append_audit_evidence(
            actor_id=actor_id,
            snapshot_id=snapshot_id,
            target=repaired,
            decision="repair_classification",
            original_suitability=str(submission.get("suitability") or ""),
            final_disposition="needs_review",
            comment=str(submission.get("comment") or ""),
            proposed_correction="",
        )
        return repaired

    def submit_review_resolution(
        self,
        *,
        actor_id: str,
        snapshot_id: str,
        object_id: str,
        expected_revision: str,
        suitability: str,
        comment: str,
        repair_kind: str,
        source_unit_ids: list[str] | None = None,
        merge_object_ids: list[str] | None = None,
        claim_object_id: str = "",
        proposed_correction: str = "",
        confirmed_object_type: str = "",
        recommendation_strength: str = "",
        documentpositie_action: str = "",
        found_under: str = "",
        parent_choice: str = "",
        type_action: str = "",
    ) -> dict[str, Any]:
        """Atomically commit human revise + deterministic repair + re-review state."""
        if repair_kind not in _REPAIR_KINDS:
            raise ConsoleError("unknown_repair_kind")
        submission = {
            "actor_id": actor_id,
            "snapshot_id": snapshot_id,
            "object_id": object_id,
            "expected_revision": expected_revision,
            "comment": comment.strip(),
            "proposed_correction": proposed_correction.strip(),
            "confirmed_object_type": confirmed_object_type.strip(),
            "recommendation_strength": recommendation_strength.strip(),
            "suitability": suitability.strip(),
            "eindoordeel": "goedkeuren_na_correctie",
            "documentpositie_action": documentpositie_action.strip(),
            "found_under": found_under.strip(),
            "parent_choice": parent_choice.strip(),
            "type_action": type_action.strip(),
        }
        self._preflight_structured_repair(submission)
        expected_kind = self.repair_kind_for_submission(submission)
        if repair_kind != expected_kind:
            raise ConsoleError("repair_kind_mismatch")

        source_units: list[dict[str, Any]] = []
        catalog: list[dict[str, Any]] = []
        if repair_kind == REPAIR_SOURCE_UNITS:
            source_units = self.source_units(snapshot_id=snapshot_id, object_id=object_id)
        elif repair_kind == REPAIR_MERGE_OBJECTS:
            catalog = self.source_fragment_catalog(
                snapshot_id=snapshot_id, object_id=object_id
            )

        with self._atomic_snapshot_mutation(snapshot_id):
            if self.objects_revision(snapshot_id) != expected_revision:
                raise ConsoleError(
                    SNAPSHOT_OBJECT_WRITE_CONFLICT,
                    current_revision=self.objects_revision(snapshot_id),
                )
            with _allow_revise_write():
                super().review_object(
                    actor_id=actor_id,
                    snapshot_id=snapshot_id,
                    object_id=object_id,
                    decision="revise",
                    comment=comment.strip(),
                    proposed_correction=proposed_correction.strip(),
                    confirmed_object_type=confirmed_object_type.strip() or None,
                    recommendation_strength=recommendation_strength.strip() or None,
                    suitability=suitability.strip(),
                    eindoordeel="goedkeuren_na_correctie",
                    documentpositie_action=documentpositie_action.strip() or None,
                    found_under=found_under.strip() or None,
                    parent_choice=parent_choice.strip() or None,
                    type_action=type_action.strip() or None,
                    expected_revision=expected_revision,
                )

            if repair_kind == REPAIR_SOURCE_UNITS:
                repaired = self._source_repair(
                    actor_id=actor_id,
                    snapshot_id=snapshot_id,
                    object_id=object_id,
                    comment=comment.strip(),
                    unit_ids=list(source_unit_ids or []),
                    units=source_units,
                )
            elif repair_kind == REPAIR_MERGE_OBJECTS:
                repaired = self._merge_repair(
                    actor_id=actor_id,
                    snapshot_id=snapshot_id,
                    object_id=object_id,
                    comment=comment.strip(),
                    merge_object_ids=list(merge_object_ids or []),
                    catalog=catalog,
                )
            elif repair_kind == REPAIR_SUPPORT_RELATION:
                if not claim_object_id.strip():
                    raise ConsoleError("support_target_required")
                self.resolve_support_relation(
                    actor_id=actor_id,
                    snapshot_id=snapshot_id,
                    support_object_id=object_id,
                    claim_object_id=claim_object_id.strip(),
                    expected_revision=self.objects_revision(snapshot_id),
                )
                repaired = self._current_object(snapshot_id, object_id)
            else:
                repaired = self._classification_repair(
                    actor_id=actor_id,
                    snapshot_id=snapshot_id,
                    object_id=object_id,
                    submission=submission,
                )

            final_status = str((repaired.get("governance") or {}).get("validation_status") or "")
            if final_status == "revise":
                raise ConsoleError("repair_did_not_close_revise")
            if final_status != "needs_review":
                raise ConsoleError("repair_must_reopen_review")
            return deepcopy(repaired)

    @staticmethod
    def repair_kind_for_submission(submission: dict[str, Any]) -> str:
        suitability = str(submission.get("suitability") or "")
        if suitability == "samenvoegen":
            return REPAIR_MERGE_OBJECTS
        if suitability == "alleen_onderbouwing":
            return REPAIR_SUPPORT_RELATION
        if suitability == "ja" and (
            submission.get("type_action") == "type_wijzigen"
            or submission.get("documentpositie_action") == "andere_kop"
            or bool(submission.get("recommendation_strength"))
        ):
            return REPAIR_CLASSIFICATION
        return REPAIR_SOURCE_UNITS


def install_deterministic_review_repair_routes(
    app: FastAPI, console: DeterministicRepairReviewConsole
) -> None:
    """Add the pre-write repair specification step and atomic resolve POST."""

    def account_for(request: Request) -> dict[str, Any]:
        return console.session_account(request.cookies.get("console_session"))

    def chrome(request: Request, body: str) -> str:
        from src.operations_console_app import _help, _nav, _page

        account = account_for(request)
        return _page(
            f"{_nav(account, 'review', console.waiting_task_counts(account['account_id']))}"
            f"<section class='room'>{body}</section>{_help(room='review')}",
            title="Review — reparatie specificeren — V&amp;VN Data Services",
        )

    def common_fields(submission: dict[str, Any], repair_kind: str) -> str:
        values = {
            "snapshot_id": submission.get("snapshot_id"),
            "object_id": submission.get("object_id"),
            "snapshot_revision": submission.get("expected_revision"),
            "suitability": submission.get("suitability"),
            "comment": submission.get("comment"),
            "proposed_correction": submission.get("proposed_correction"),
            "confirmed_object_type": submission.get("confirmed_object_type"),
            "recommendation_strength": submission.get("recommendation_strength"),
            "documentpositie_action": submission.get("documentpositie_action"),
            "found_under": submission.get("found_under"),
            "parent_choice": submission.get("parent_choice"),
            "type_action": submission.get("type_action"),
            "repair_kind": repair_kind,
        }
        return "".join(_hidden(name, value) for name, value in values.items())

    def source_units_form(submission: dict[str, Any]) -> str:
        snapshot_id = str(submission["snapshot_id"])
        object_id = str(submission["object_id"])
        current = console._current_object(snapshot_id, object_id)
        current_text = str((current.get("content") or {}).get("clean_text") or "")
        units = console.source_units(snapshot_id=snapshot_id, object_id=object_id)
        options: list[str] = []
        for unit in units:
            path = " › ".join(unit.get("section_path") or [])
            label = f"{path + ' — ' if path else ''}{unit['text']}"
            options.append(
                f'<option value="{_esc(unit["unit_id"])}">{_esc(label[:500])}</option>'
            )
        if not options:
            raise ConsoleError("repair_source_units_required")
        return (
            "<h2>Kies de exacte bronpassage voor het nieuwe voorstel</h2>"
            f"<p><strong>Huidig kennisobject:</strong> {_esc(current_text)}</p>"
            "<p>Selecteer één of meer aaneengesloten bronzinnen. Metis bouwt de nieuwe "
            "tekst uitsluitend uit deze geselecteerde bronzinnen.</p>"
            '<label>Bronzinnen<select name="source_unit_ids" multiple size="14" required>'
            + "".join(options)
            + "</select></label>"
        )

    def merge_form(submission: dict[str, Any]) -> str:
        snapshot_id = str(submission["snapshot_id"])
        object_id = str(submission["object_id"])
        current = console._current_object(snapshot_id, object_id)
        section = tuple((current.get("structure") or {}).get("section_path") or [])
        options: list[str] = []
        for row in console.snapshot_objects(snapshot_id):
            row_id = str(row.get("object_id") or "")
            if not row_id or row_id == object_id or row.get("object_type") in {"document", "heading"}:
                continue
            if tuple((row.get("structure") or {}).get("section_path") or []) != section:
                continue
            governance = row.get("governance") or {}
            if governance.get("validation_status") in {"approved", "rejected", "superseded"}:
                continue
            if governance.get("publication_status") == "published" or binding_relations(row):
                continue
            text = str((row.get("content") or {}).get("clean_text") or row_id)
            options.append(
                '<label class="check">'
                f'<input type="checkbox" name="merge_object_ids" value="{_esc(row_id)}"> '
                f'{_esc(text[:500])}</label>'
            )
        if not options:
            raise ConsoleError("merge_target_required")
        return (
            "<h2>Kies de passage(s) die bij dit kennisobject horen</h2>"
            "<p>Metis combineert de brongebonden tekst in bronvolgorde. De opgenomen "
            "oude kennisobjecten worden daarna <code>superseded</code>.</p>"
            + "".join(options)
        )

    def support_form(submission: dict[str, Any]) -> str:
        snapshot_id = str(submission["snapshot_id"])
        object_id = str(submission["object_id"])
        options: list[str] = []
        for row in console.snapshot_objects(snapshot_id):
            row_id = str(row.get("object_id") or "")
            if not row_id or row_id == object_id or row.get("object_type") == "document":
                continue
            if (row.get("governance") or {}).get("validation_status") in {"rejected", "superseded"}:
                continue
            text = str((row.get("content") or {}).get("clean_text") or row_id)
            options.append(
                f'<option value="{_esc(row_id)}">{_esc(text[:500])}</option>'
            )
        if not options:
            raise ConsoleError("support_target_required")
        return (
            "<h2>Kies welk kennisobject door deze passage wordt onderbouwd</h2>"
            '<label>Ondersteund kennisobject<select name="claim_object_id" required>'
            + "".join(options)
            + "</select></label>"
        )

    async def structured_repair_handler(
        request: Request, exc: StructuredRepairRequired
    ) -> HTMLResponse:
        account = account_for(request)
        submission = exc.submission
        if str(submission.get("actor_id") or "") != str(account.get("account_id") or ""):
            raise ConsoleError("correction_role_required")
        repair_kind = console.repair_kind_for_submission(submission)
        if repair_kind == REPAIR_SOURCE_UNITS:
            action = source_units_form(submission)
        elif repair_kind == REPAIR_MERGE_OBJECTS:
            action = merge_form(submission)
        elif repair_kind == REPAIR_SUPPORT_RELATION:
            action = support_form(submission)
        else:
            action = (
                "<h2>Bevestig de gekozen type- of plaatsingscorrectie</h2>"
                "<p>Metis past alleen de al gekozen structurele correctie toe en zet "
                "het gewijzigde object daarna opnieuw in Review.</p>"
            )
        note = str(submission.get("proposed_correction") or "")
        note_html = (
            "<p class='field-help'><strong>Opmerking uit het oude vrije tekstveld:</strong> "
            f"{_esc(note)}<br>Deze tekst wordt alleen als review-evidence bewaard en nooit "
            "als canonieke kennis overgenomen.</p>"
            if note
            else ""
        )
        body = (
            "<p><a href='" + _esc(_review_url(str(submission["snapshot_id"]), str(submission["object_id"]))) + "'>← Terug naar Review</a></p>"
            "<h1>Correctie specificeren</h1>"
            "<p class='lead'>Er is nog niets gewijzigd. Deze stap bepaalt de uitvoerbare, "
            "brongebonden reparatie. Pas daarna worden review en nieuwe versie samen opgeslagen.</p>"
            f"<p><strong>Reden:</strong> {_esc(submission.get('comment'))}</p>"
            + note_html
            + '<form method="post" action="/review/resolve">'
            + common_fields(submission, repair_kind)
            + action
            + '<button class="btn-primary" type="submit">Maak nieuw voorstel en zet opnieuw in Review</button>'
            + "</form>"
        )
        return HTMLResponse(chrome(request, body), status_code=200)

    app.add_exception_handler(StructuredRepairRequired, structured_repair_handler)

    @app.post("/review/resolve")
    def resolve_review(
        request: Request,
        snapshot_id: str = Form(...),
        object_id: str = Form(...),
        snapshot_revision: str = Form(...),
        suitability: str = Form(...),
        comment: str = Form(...),
        repair_kind: str = Form(...),
        source_unit_ids: list[str] = Form(default=[]),
        merge_object_ids: list[str] = Form(default=[]),
        claim_object_id: str = Form(""),
        proposed_correction: str = Form(""),
        confirmed_object_type: str = Form(""),
        recommendation_strength: str = Form(""),
        documentpositie_action: str = Form(""),
        found_under: str = Form(""),
        parent_choice: str = Form(""),
        type_action: str = Form(""),
    ) -> RedirectResponse:
        account = account_for(request)
        console.submit_review_resolution(
            actor_id=account["account_id"],
            snapshot_id=snapshot_id,
            object_id=object_id,
            expected_revision=snapshot_revision.strip(),
            suitability=suitability,
            comment=comment,
            repair_kind=repair_kind,
            source_unit_ids=list(source_unit_ids or []),
            merge_object_ids=list(merge_object_ids or []),
            claim_object_id=claim_object_id,
            proposed_correction=proposed_correction,
            confirmed_object_type=confirmed_object_type,
            recommendation_strength=recommendation_strength,
            documentpositie_action=documentpositie_action,
            found_under=found_under,
            parent_choice=parent_choice,
            type_action=type_action,
        )
        return RedirectResponse(_review_url(snapshot_id, object_id), status_code=303)
