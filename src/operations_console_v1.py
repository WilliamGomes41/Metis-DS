"""Internal operations console MVP — knowledge-kernel surface for researchers.

Protocol v2.6/v2.8: ingest mailbox, family × class tree, named reviewers,
mandatory review return-loop, local G0 identity. Capture is not publication.
Azure deployments can bind exact source bytes to the G2 canonical Blob store;
local ``sources/private/`` remains the G0 stand-in for local development.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import secrets
import tempfile
import threading
import unicodedata
import uuid
import time
import zipfile
from contextlib import contextmanager, nullcontext, suppress
from contextvars import ContextVar
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator

from src.admission_gate_v1 import (
    GATE_BLOCKED,
    admission_of,
    apply_admission_gate,
    is_admission_blocked,
)
from src.candidate_eligibility_v1 import candidate_eligibility_of
from src.passage_register_v1 import apply_passage_register, apply_register_from_review
from src.review_cockpit_v1 import (
    SUITABILITY_VALUES,
    confirmable_proposed_type,
    found_under_path,
    map_eindoordeel,
    merge_heading_parent_relations,
    next_ordinary_object_id,
    resolve_found_under_parent,
    review_passage_record,
    review_passage_requested,
)
from src.atomic_split_v1 import proposed_relations_for_units
from src.beslisboom_path_v1 import (
    CLOSED_BOOM_TYPES,
    CLOSED_KLASSEN,
    boom_freeze_errors,
    boom_spec_from_fragments,
    extract_boom_fragments,
    is_confirmable_type_for_path,
    is_geen_actie_outcome,
    is_live_rest_sole_source,
    is_live_rest_url,
    map_geen_actie,
    outcome_review_errors,
    review_path_for_klasse,
    stamp_boom_flags,
)
from src.context_aware_split_v1 import split_context_aware_units
from src.extract_html_v1 import extract as extract_html
from src.extract_pdf_v2 import extract as extract_pdf
from src.four_eyes_v1 import (
    mark_four_eyes_on_object,
    publish_authorization_contract,
    requires_four_eyes,
)
from src.review_duty_v1 import SECOND_REVIEW, exact_current_approver_ids, review_duty_for, reviewer_route_for
from src.g2_source_store import G2SourceStoreError, ImmutableSourceStore, is_g2_locator
from src.integrity_kernel import compute_canonical_object_hash, schema_errors, sha256_bytes, stamp_canonical_hashes
from src.klasse_wijzigen_v1 import (
    DOCUMENT_CLASS_CHANGED_EVENT,
    is_cross_model_class_change,
    source_identity_fields,
)
from src.object_taxonomy_v1 import (
    is_closed_recommendation_strength,
    review_priority_rank,
)
from src.knowledge_relations_v1 import (
    CONFIRMED_FIELD as CONFIRMED_KNOWLEDGE_RELATIONS_FIELD,
    PROPOSED_FIELD as PROPOSED_KNOWLEDGE_RELATIONS_FIELD,
    STRUCTURAL_RELATION_TYPES,
    confirmed_knowledge_relations_of,
)
from src.knowledge_relation_review_v1 import (
    build_confirmed_relation_set,
    has_semantic_relation_review,
    legacy_confirmed_mirror,
    plan_semantic_relation_review,
    relation_review_evidence,
)
from src.recommendation_semantics_v1 import (
    CONFIRMED_FIELD as CONFIRMED_RECOMMENDATION_SEMANTICS_FIELD,
    LEGACY_CONFIRMED_FIELD as LEGACY_CONFIRMED_RECOMMENDATION_STRENGTH_FIELD,
    confirmed_recommendation_semantics_from_review,
    confirmed_recommendation_semantics_of,
    proposed_recommendation_semantics_of,
)
from src.open_original_v1 import OpenOriginalError, open_source_passage, researcher_visible_prose
from src.publish_authorization_v1 import record_authorization, invalidate_for_object, still_matches, tuple_record
from src.review_ledger import append_event, read_events
from src.review_interaction_v1 import validate_review_interaction_identity
from src.review_workflow_v3 import _apply_review_state
from src.revision_workflow import (bump_patch, create_revision, revise_object, current_revisions,
                                   validate_revision_write, knowledge_revision, reprocessed_history, lineage_evidence)
from src.retrieval.retrieval_projection_v2 import build_projection
from src.published_projection_v1 import atomic_replace_projection
from src.semantic_replay_v1 import SEMANTIC_REPLAY_SPEC_KEY
from src.quality_evidence_v1 import record_processing, review_evidence, instant as quality_instant
from src.semantic_transform_generic_v1 import transform as _transform_generic
from src.serving_relations_v1 import (
    binding_relations,
    confirm_relation_set,
    is_closed_relation_type,
)
from src.topic_identity_v1 import normalize_topic_label, topic_identity_key


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_V12 = REPO_ROOT / "schemas" / "knowledge_object.schema.v1.2.json"
SCHEMA_V13 = REPO_ROOT / "schemas" / "knowledge_object.schema.v1.3.json"
SCHEMA_V14 = REPO_ROOT / "schemas" / "knowledge_object.schema.v1.4.json"
CONSOLE_VERSION = "operations-console-v1.0.0"
SNAPSHOT_OBJECT_WRITE_CONFLICT = "snapshot_object_write_conflict"
CAPTURED = "captured_not_published"
PRE_REVIEW_BLOCKED = "blocked_pending_pre_review"
PUBLISHED_ENVELOPE_STATES = frozenset({"published", "superseded", "withdrawn"})
UNPUBLISHED_DELETE_EVENT = "unpublished_snapshot_deleted"
CLASS_CHANGE_HISTORY_DIRNAME = "class_change_history"
PUBLISHED_PROJECTION_FILENAME = "published_projection.jsonl"
PUBLICATION_PROTOCOL_VERSION = "4.0.0"
RELEASE_MANIFEST_DIRNAME = "release_manifests"
ALLOWED_DELETE_NEXT = frozenset({"/ingest", "/review", "/tree"})
ALLOWED_ROLES = frozenset({"researcher", "reviewer", "publisher"})
ALLOWED_CLASSES = CLOSED_KLASSEN
SOURCE_VERSION_RE = re.compile(r"^[0-9]+(\.[0-9]+)*$")
YEAR_AS_VERSION_RE = re.compile(r"^(19|20)\d{2}$")
ISO_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
NL_DATE_RE = re.compile(r"^(\d{2})-(\d{2})-(\d{4})$")
SAFE_PATH_TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$")
SNAPSHOT_ID_RE = re.compile(r"^snap-[0-9a-f]{16}-[0-9a-f]{8}$")
STORE_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
REVIEW_TYPE_NAMES = frozenset(
    {
        "unclassified",
        "heading",
        "definition",
        "explanation",
        "condition",
        "exception",
        "recommendation",
        "document",
        "path",
        "node",
        "outcome",
    }
)
CLASS_ORDER = {
    "richtlijn": 4,
    "handreiking": 3,
    "artikel": 2,
    "transcript": 1,
    "podcast": 1,
    "beslisboom": 0,
}
FORBIDDEN_REVIEWER_IDENTITIES = frozenset(
    {
        "ai",
        "grok bot",
        "grok",
        "metis",
        "implementation engineer",
        "auditor",
    }
)
WORD_TYPES = {
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
BOOM_MARKERS = (
    'data-kennisplatform-player="boom"',
    "kennisplatform-boom-player",
    'class="boom-player"',
    "articulate-rise",
    "storyline-player",
    "window.playerconfig",
)
PBKDF2_ROUNDS = 80_000
DEFAULT_SESSION_TTL_SECONDS = 12 * 60 * 60
SESSION_SAVE_RETRIES = 2


class ConsoleError(ValueError):
    def __init__(
        self,
        code: str,
        message: str | None = None,
        *,
        current_revision: str | None = None,
    ) -> None:
        self.code = code
        self.current_revision = current_revision
        super().__init__(message or code)


def transform_generic(spec, manifest, fragments):
    """Keep materialisation failures in the existing command error channel."""
    from src.knowledge_materialisation_v1 import MaterialisationError
    try:
        return _transform_generic(spec, manifest, fragments)
    except MaterialisationError as exc:
        error = ConsoleError("pre_review_llm_proposal_rejected", exc.code)
        error.validation_finding = deepcopy(exc.finding)
        error.pre_review_diagnostics = {"reason_code": exc.code}
        raise error from exc


UrlFetcher = Callable[[str], tuple[bytes, str, str]]


def _has_path_escape(value: str) -> bool:
    return (not value) or value in {".", ".."} or "/" in value or "\\" in value or ".." in value


def safe_path_token(value: str, *, pattern: re.Pattern[str] | None = None, code: str = "invalid_store_path") -> str:
    """Allowlist a single path component. Reject separators and ``..`` before any join."""
    raw = "" if value is None else str(value)
    if _has_path_escape(raw):
        raise ConsoleError(code)
    matched = (pattern or SAFE_PATH_TOKEN_RE).fullmatch(raw)
    if matched is None:
        raise ConsoleError(code)
    return matched.group(0)


def safe_store_filename(value: str) -> str:
    """Freeze upload name must be a single basename. ``Path.name`` is not enough (``..``)."""
    return safe_path_token(value, pattern=SAFE_PATH_TOKEN_RE, code="invalid_store_path")


def normalize_upload_filename(value: str | None) -> str:
    """Normalize browser names; keep stored names and path joins strictly validated."""
    raw = value or ""
    if ".." in raw:
        raise ConsoleError("invalid_store_path")
    basename = raw.replace("\\", "/").rsplit("/", 1)[-1]
    ascii_name = unicodedata.normalize("NFKD", basename).encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "-", ascii_name.strip())
    return safe_store_filename(normalized)


def safe_snapshot_id(snapshot_id: str) -> str:
    return safe_path_token(snapshot_id, pattern=SNAPSHOT_ID_RE, code="unknown_snapshot")


def safe_path_under(root: Path, *parts: str) -> Path:
    """Resolve ``root/parts`` and require the result to stay under ``root``."""
    if not parts:
        raise ConsoleError("invalid_store_path")
    resolved_root = Path(os.path.realpath(os.fspath(root)))
    tokens = [safe_path_token(part) for part in parts]
    joined = os.path.join(os.fspath(resolved_root), *tokens)
    resolved = Path(os.path.realpath(joined))
    root_s = os.fspath(resolved_root)
    resolved_s = os.fspath(resolved)
    if os.path.commonpath([root_s, resolved_s]) != root_s:
        raise ConsoleError("invalid_store_path")
    return resolved


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def utc_after(seconds: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def _parse_utc(value: str) -> datetime | None:
    raw = (value or "").strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def session_is_expired(session: dict[str, Any], *, now: datetime | None = None) -> bool:
    """Missing or unreadable expires_at is expired. Expiry field alone is not enough — callers MUST reject."""
    parsed = _parse_utc(str(session.get("expires_at") or ""))
    if parsed is None:
        return True
    current = now or datetime.now(timezone.utc)
    return current >= parsed


def normalize_ingest_source_date(value: str | None) -> str:
    """Persist freeze colofon/publicatiedatum as ISO YYYY-MM-DD.

    Screen locale may be DD-MM-YYYY. Stored bytes MUST be ISO, no time/tz.
    Empty is rejected. Today and ingest-click MUST NOT be substituted.
    """
    raw = "" if value is None else str(value)
    if not raw.strip():
        raise ConsoleError("source_date_required")
    if re.search(r"\s", raw):
        raw = raw.strip()
        if not raw:
            raise ConsoleError("source_date_required")
    iso = None
    if ISO_DATE_RE.fullmatch(raw):
        iso = raw
    else:
        matched = NL_DATE_RE.fullmatch(raw)
        if matched:
            day, month, year = matched.groups()
            iso = f"{year}-{month}-{day}"
    if iso is None:
        raise ConsoleError("invalid_source_date")
    try:
        parsed = date.fromisoformat(iso)
    except ValueError as exc:
        raise ConsoleError("invalid_source_date") from exc
    if parsed.isoformat() != iso:
        raise ConsoleError("invalid_source_date")
    return iso


def validate_ingest_source_version(value: str | None) -> str:
    """Require dotted non-negative integers. Reject year-as-version and spaces."""
    raw = "" if value is None else str(value)
    if not raw:
        raise ConsoleError("source_version_required")
    if re.search(r"\s", raw) or raw != raw.strip():
        raise ConsoleError("invalid_source_version")
    if YEAR_AS_VERSION_RE.fullmatch(raw) or not SOURCE_VERSION_RE.fullmatch(raw):
        raise ConsoleError("invalid_source_version")
    return raw


def _authoritative_review_type(obj: dict[str, Any]) -> str | None:
    confirmed = obj.get("confirmed_object_type")
    stored = obj.get("object_type")
    proposed = obj.get("proposed_object_type")
    if confirmed:
        return confirmed
    if stored and stored != "unclassified":
        return stored
    return proposed


def inferred_review_path(obj: dict[str, Any]) -> str:
    if (obj.get("metadata") or {}).get("decision_unit_construction"):
        return "boom"
    authoritative = _authoritative_review_type(obj)
    if authoritative in CLOSED_BOOM_TYPES or obj.get("proposed_object_type") in CLOSED_BOOM_TYPES:
        return "boom"
    return "richtlijn"


def review_lane(obj: dict[str, Any], review_path: str | None = None) -> str:
    """Queue routing from the first authoritative type. Not a speed switch.

    Confirmed type wins. Stored type wins over a stale proposal. Proposed
    type is used only when the object is still unclassified, so a human
    reclassification to recommendation cannot be batch-overwritten as heading.
    On the boom path, ``path`` is structure (fast) and never advice.
    """
    if obj.get("object_type") == "document":
        return "document"
    path = review_path or inferred_review_path(obj)
    authoritative = _authoritative_review_type(obj)
    if path == "boom":
        if authoritative == "path":
            return "fast"
        return "slow"
    if authoritative == "heading":
        return "fast"
    return "slow"


def review_row_title(obj: dict[str, Any], *, max_len: int = 160) -> str:
    """Freeze source sentence or real heading. MUST NOT use type name or kernel id."""
    content = obj.get("content") or {}
    text = re.sub(
        r"\s+",
        " ",
        str(content.get("clean_text") or content.get("raw_text") or ""),
    ).strip()
    if text and text.casefold() not in REVIEW_TYPE_NAMES and not text.startswith(("console-", "snap-")):
        snippet = text
    else:
        snippet = "Kennisobject"
    if len(snippet) > max_len:
        return snippet[: max_len - 1] + "…"
    return snippet


def review_card_sentence(obj: dict[str, Any]) -> str:
    """Open-card freeze sentence once. Full text; not truncated; not a type name."""
    return review_row_title(obj, max_len=10_000)


def review_row_status(obj: dict[str, Any]) -> str:
    """Short same-line status. waiting / classified / confirmed in onderzoekerstaal."""
    confirmed = obj.get("confirmed_object_type")
    status = (obj.get("governance") or {}).get("validation_status") or ""
    if status == "approved" or confirmed:
        if status == "approved":
            return "bevestigd"
        return "geclassificeerd"
    return "wacht"


def review_stacks(
    objects: Iterable[dict[str, Any]],
    review_path: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Koppen (fast heading) vs all slow content. Document rows are not stacks.

    The old Inhoud enumeration is every slow object, including leftover
    unclassified. Protocol v2.19 presents slow duty separately: use
    ``slow_review_duty`` for the researcher-required cards. On the boom
    path the fast stack is ``path`` structure.
    """
    rows = [obj for obj in objects if obj.get("object_type") != "document"]
    koppen = [obj for obj in rows if review_lane(obj, review_path=review_path) == "fast"]
    inhoud = [obj for obj in rows if review_lane(obj, review_path=review_path) != "fast"]
    return koppen, inhoud


_STRUCTURE_CONFIRMATION = ContextVar("metis_structure_confirmation", default=False)

SLOW_REVIEW_DUTY_TYPES = frozenset({"recommendation", "condition", "exception"})
SLOW_BOOM_DUTY_TYPES = frozenset({"node", "outcome"})


def is_slow_review_duty(obj: dict[str, Any], review_path: str | None = None, *, bindings=None, fragments=None) -> bool:
    """True for the researcher-required slow hand work (Protocol v2.19).

    Proposed or stored ``recommendation``, ``condition``, ``exception``, or
    any high-risk object. Headings stay in Koppen. Leftover unclassified is
    not this duty. MUST NOT auto-confirm types. MUST NOT treat leftover as
    light enough to skip four-eyes or to serve. On the boom path, ``node``
    and ``outcome`` are the duty types.
    """
    if obj.get("object_type") == "document":
        return False
    path = review_path or inferred_review_path(obj)
    if path != "boom" and not review_duty_for(
        obj, review_path=path, bindings=bindings, fragments=fragments
    ):
        return False
    if is_admission_blocked(obj, review_path=path):
        return False
    if review_lane(obj, review_path=path) == "fast":
        return False
    if requires_four_eyes(obj, confirmed_type=obj.get("confirmed_object_type") or None):
        return True
    duty_types = SLOW_BOOM_DUTY_TYPES if path == "boom" else SLOW_REVIEW_DUTY_TYPES
    confirmed = obj.get("confirmed_object_type")
    stored = obj.get("object_type")
    proposed = obj.get("proposed_object_type")
    if confirmed in duty_types:
        return True
    if stored in duty_types:
        return True
    if proposed in duty_types:
        return True
    return False


def slow_review_duty(
    objects: Iterable[dict[str, Any]],
    review_path: str | None = None,
    *, bindings=None, fragments=None,
) -> list[dict[str, Any]]:
    """Presented Inhoud cards: recommendation + condition/exception/high-risk."""
    bindings = tuple(bindings or ())
    fragments = tuple(fragments) if fragments is not None else None
    rows = [obj for obj in objects if is_slow_review_duty(obj, review_path=review_path, bindings=bindings, fragments=fragments)]
    return rows if review_path == "boom" else sorted(rows, key=review_priority_rank)


def remaining_unclassified(objects: Iterable[dict[str, Any]], *, bindings=None, fragments=None) -> list[dict[str, Any]]:
    """Leftover unclassified that MUST NOT be equal one-by-one duty cards.

    Stored objects remain. Presentation of duty is not deletion. Hiding
    stored fragments without a new extract remains forbidden.
    """
    rows = [obj for obj in objects if obj.get("object_type") != "document"]
    leftover: list[dict[str, Any]] = []
    for obj in rows:
        if is_slow_review_duty(obj, bindings=bindings, fragments=fragments) or review_lane(obj) == "fast":
            continue
        if obj.get("confirmed_object_type"):
            continue
        stored = obj.get("object_type")
        if stored and stored != "unclassified":
            continue
        leftover.append(obj)
    return leftover


def remaining_not_duty(objects: Iterable[dict[str, Any]], *, bindings=None, fragments=None) -> list[dict[str, Any]]:
    """Slow objects that are not the presented researcher duty."""
    rows = [obj for obj in objects if obj.get("object_type") != "document"]
    return [
        obj
        for obj in rows
        if review_lane(obj) != "fast" and not is_slow_review_duty(obj, bindings=bindings, fragments=fragments)
    ]


def _slug(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return text or "document"


def _normalize_identity(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().lower()


def _is_forbidden_identity(value: str) -> bool:
    return _normalize_identity(value) in FORBIDDEN_REVIEWER_IDENTITIES


def _hash_password(password: str, salt_hex: str | None = None) -> tuple[str, str]:
    salt = bytes.fromhex(salt_hex) if salt_hex else os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ROUNDS)
    return salt.hex(), digest.hex()


def _atomic_replace_bytes(path: Path, payload: bytes) -> None:
    """Write ``payload`` via a unique temp file in the same directory, then replace.

    MUST NOT use a shared fixed ``path.suffix + ".tmp"`` name (concurrent writers
    race). ``os.replace`` is atomic on the same filesystem; an interrupt during
    the temp write leaves the destination intact.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    os.close(fd)
    tmp = Path(tmp_name)
    try:
        tmp.write_bytes(payload)
        os.replace(tmp, path)
    except Exception:
        with suppress(OSError):
            tmp.unlink()
        raise


def _atomic_write(path: Path, payload: Any) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    _atomic_replace_bytes(path, text.encode("utf-8"))


def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    _atomic_replace_bytes(path, payload)


def _objects_jsonl_bytes(rows: list[dict[str, Any]]) -> bytes:
    return "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows).encode("utf-8")


def _file_revision(path: Path) -> str:
    if not path.exists():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def default_url_fetcher(url: str) -> tuple[bytes, str, str]:
    from src.ingest_limits_v1 import fetch_url_limited

    return fetch_url_limited(url)


def _is_word_bytes(data: bytes, filename: str, content_type: str | None) -> bool:
    name = Path(filename).name.lower()
    ctype = (content_type or "").split(";")[0].strip().lower()
    if name.endswith(".docx") or name.endswith(".doc") or ctype in WORD_TYPES:
        return True
    if data.startswith(b"\xd0\xcf\x11\xe0"):
        return True
    if data.startswith(b"PK"):
        try:
            with zipfile.ZipFile(BytesIO(data)) as archive:
                return any(item.startswith("word/") for item in archive.namelist())
        except zipfile.BadZipFile:
            return False
    return False


def _is_boom_player(data: bytes, filename: str) -> bool:
    name = Path(filename).name.lower()
    if name == "story.html":
        return True
    text = data.decode("utf-8", errors="replace").lower()
    return any(marker in text for marker in BOOM_MARKERS)


def classify_official_file(data: bytes, filename: str, content_type: str | None) -> str:
    if _is_word_bytes(data, filename, content_type):
        raise ConsoleError("word_not_first_wave")
    if _is_boom_player(data, filename):
        raise ConsoleError("story_html_boom_player_out_of_first_wave")
    name = Path(filename).name.lower()
    ctype = (content_type or "").split(";")[0].strip().lower()
    if name.endswith(".pdf") or data.startswith(b"%PDF") or ctype == "application/pdf":
        return "pdf"
    if (
        name.endswith(".html")
        or name.endswith(".htm")
        or ctype in {"text/html", "application/xhtml+xml"}
        or data.lstrip().lower().startswith(b"<!doctype html")
        or data.lstrip().lower().startswith(b"<html")
    ):
        return "html"
    raise ConsoleError("unsupported_official_file")


def _spec_from_fragments(
    *,
    document_id: str,
    title: str,
    family: str,
    class_: str,
    fragments: list[dict[str, Any]],
    content_kind: str,
) -> dict[str, Any]:
    objects: list[dict[str, Any]] = [
        {
            "object_id": f"{document_id}-document",
            "object_type": "document",
            "text": title,
            "review_track": "technical",
        }
    ]
    meaning_units = split_context_aware_units(fragments, document_id=document_id)
    proposed_relations_for_units(meaning_units)
    objects.extend(meaning_units)
    return {
        "spec_version": "console-ingest-1.0",
        "document_id": document_id,
        "object_version": "1.0",
        "target_group": [],
        "care_setting": [],
        "topic": [family, f"class:{class_}", f"source-kind:{content_kind}"],
        "objects": objects,
    }


class OperationsConsole:
    def __init__(
        self,
        *,
        root: Path,
        source_store: Path | None = None,
        runtime: Path | None = None,
        immutable_source_store: ImmutableSourceStore | None = None,
        url_fetcher: UrlFetcher | None = None,
        schema_path: Path | None = None,
    ) -> None:
        self.root = Path(root)
        self.source_store = Path(source_store or self.root / "sources" / "private")
        self.runtime = Path(runtime or self.root / "output" / "runtime" / "operations-console")
        self.immutable_source_store = immutable_source_store
        self.url_fetcher = url_fetcher or default_url_fetcher
        self.schema_path = Path(schema_path or SCHEMA_V14)
        self.source_store.mkdir(parents=True, exist_ok=True)
        self.runtime.mkdir(parents=True, exist_ok=True)
        self._accounts_path = self.runtime / "accounts.json"
        self._sessions_path = self.runtime / "sessions.json"
        self._envelopes_path = self.runtime / "envelopes.json"
        self._objects_dir = self.runtime / "objects"
        self._objects_dir.mkdir(parents=True, exist_ok=True)
        self._ledger_path = self.runtime / "review_ledger.jsonl"
        self._bindings_path = self.runtime / "publish_authorizations.json"
        self._accounts: dict[str, dict[str, Any]] = self._load_map(self._accounts_path)
        self._sessions: dict[str, dict[str, Any]] = self._load_map(self._sessions_path)
        self._envelopes: dict[str, dict[str, Any]] = self._load_map(self._envelopes_path)
        loaded_bindings = self._load_map(self._bindings_path)
        self._bindings: dict[str, list[dict[str, Any]]] = {
            key: list(value) for key, value in loaded_bindings.items()
        }
        self._objects_lock_guard = threading.Lock()
        self._objects_thread_locks: dict[str, threading.RLock] = {}
        self._objects_tls = threading.local()
        self._sessions_thread_lock = threading.RLock()
        self._store_thread_lock = threading.RLock()
        self._store_lock_depth = 0
        self._store_lock_handle: Any = None
        self._prepared_envelopes: dict[str, Any] | None = None
        self._prepared_bindings: dict[str, Any] | None = None

    def _startup_local_mirror_is_authority(self, path: Path) -> bool:
        return True

    def _load_map(self, path: Path) -> dict[str, dict[str, Any]]:
        if not self._startup_local_mirror_is_authority(path):
            return {}
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def _save_accounts(self) -> None:
        _atomic_write(self._accounts_path, self._accounts)

    def _save_sessions(self) -> None:
        _atomic_write(self._sessions_path, self._sessions)

    @contextmanager
    def _sessions_write_lock(self) -> Iterator[None]:
        lock_path = self._sessions_path.with_name(self._sessions_path.name + ".lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self._sessions_thread_lock:
            with open(lock_path, "a+b") as handle:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def _reload_sessions_locked(self) -> None:
        self._sessions = self._load_map(self._sessions_path)

    def _with_sessions(self, mutator: Callable[[dict[str, dict[str, Any]]], None]) -> None:
        last_error: OSError | None = None
        for _attempt in range(SESSION_SAVE_RETRIES):
            try:
                with self._sessions_write_lock():
                    self._reload_sessions_locked()
                    mutator(self._sessions)
                    self._save_sessions()
                return
            except OSError as exc:
                last_error = exc
        if last_error is not None:
            raise last_error

    @contextmanager
    def _store_write_lock(self) -> Iterator[None]:
        """Exclusive lock for one complete store transaction (shared maps + files).

        MUST NOT be held across ingest extract. Review POSTs take this only for
        the durable commit, not for heavy parse/transform. Re-entrant for
        ``_save_envelopes`` / ``_save_bindings`` called from ``_commit_prepared_store``.
        """
        lock_path = self.runtime / "store.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self._store_thread_lock:
            first = self._store_lock_depth == 0
            if first:
                handle = open(lock_path, "a+b")
                try:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                except Exception:
                    handle.close()
                    raise
                self._store_lock_handle = handle
            self._store_lock_depth += 1
            try:
                yield
            finally:
                self._store_lock_depth -= 1
                if first:
                    handle = self._store_lock_handle
                    self._store_lock_handle = None
                    if handle is not None:
                        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                        handle.close()

    def _rebase_snapshot_map(
        self,
        live: dict[str, Any],
        prepared: dict[str, Any],
        snapshot_id: str,
    ) -> dict[str, Any]:
        """Apply one snapshot's prepared entry onto the live map.

        A caller's full-map copy may be stale on other keys. Only this
        snapshot's record is published; other writers' committed keys stay.
        """
        merged = deepcopy(live)
        if snapshot_id in prepared:
            merged[snapshot_id] = deepcopy(prepared[snapshot_id])
        else:
            merged.pop(snapshot_id, None)
        return merged

    def _save_envelopes(self) -> None:
        with self._store_write_lock():
            payload = getattr(self, "_prepared_envelopes", None)
            _atomic_write(self._envelopes_path, self._envelopes if payload is None else payload)

    def _save_bindings(self) -> None:
        with self._store_write_lock():
            payload = getattr(self, "_prepared_bindings", None)
            _atomic_write(self._bindings_path, self._bindings if payload is None else payload)

    def _reload_store_locked(self) -> None:
        """Refresh shared publication inputs while the store lock is held."""
        self._envelopes = self._load_map(self._envelopes_path)
        loaded = self._load_map(self._bindings_path)
        self._bindings = {key: list(value) for key, value in loaded.items()}

    def _objects_path(self, snapshot_id: str) -> Path:
        if ".." in snapshot_id or "/" in snapshot_id or "\\" in snapshot_id:
            raise ConsoleError("unknown_snapshot")
        token = safe_snapshot_id(snapshot_id)
        return safe_path_under(self._objects_dir, f"{token}.jsonl")

    def _objects_thread_lock(self, snapshot_id: str) -> threading.RLock:
        with self._objects_lock_guard:
            lock = self._objects_thread_locks.get(snapshot_id)
            if lock is None:
                lock = threading.RLock()
                self._objects_thread_locks[snapshot_id] = lock
            return lock

    def _objects_expected_revs(self) -> dict[str, str]:
        revs = getattr(self._objects_tls, "expected", None)
        if revs is None:
            revs = {}
            self._objects_tls.expected = revs
        return revs

    @contextmanager
    def _objects_write_lock(self, snapshot_id: str) -> Iterator[None]:
        path = self._objects_path(snapshot_id)
        lock_path = path.with_name(path.name + ".lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self._objects_thread_lock(snapshot_id):
            with open(lock_path, "a+b") as handle:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def _load_objects(self, snapshot_id: str, *, remember: bool = True) -> list[dict[str, Any]]:
        if ".." in snapshot_id or "/" in snapshot_id or "\\" in snapshot_id:
            raise ConsoleError("unknown_snapshot")
        with self._objects_write_lock(snapshot_id):
            path = self._objects_path(snapshot_id)
            exists = path.exists()
            if not exists:
                text = ""
                rows: list[dict[str, Any]] = []
            else:
                text = path.read_text(encoding="utf-8")
                rows = [json.loads(line) for line in text.splitlines() if line.strip()]
            if remember:
                expected = self._objects_expected_revs()
                if snapshot_id not in expected:
                    expected[snapshot_id] = (
                        hashlib.sha256(text.encode("utf-8")).hexdigest()
                        if exists
                        else ""
                    )
            return rows

    def objects_revision(self, snapshot_id: str) -> str:
        """Current snapshot objects-file revision. Bound to the file, not TLS."""
        if ".." in snapshot_id or "/" in snapshot_id or "\\" in snapshot_id:
            raise ConsoleError("unknown_snapshot")
        return _file_revision(self._objects_path(snapshot_id))

    def _save_objects(
        self,
        snapshot_id: str,
        rows: list[dict[str, Any]],
        *,
        expected_revision: str | None = None,
    ) -> None:
        if ".." in snapshot_id or "/" in snapshot_id or "\\" in snapshot_id:
            raise ConsoleError("unknown_snapshot")
        with self._store_write_lock():
            self._reload_store_locked()
            self._guard_prepared_working_revision_mutation(
                envelopes=None, bindings=None, objects=(snapshot_id, rows), snapshot_id=snapshot_id)
            with self._objects_write_lock(snapshot_id):
                path = self._objects_path(snapshot_id)
                pinned = (
                    expected_revision
                    if expected_revision is not None
                    else self._objects_expected_revs().get(snapshot_id)
                )
                current_rev = _file_revision(path)
                if pinned is not None and current_rev != pinned:
                    raise ConsoleError(
                        SNAPSHOT_OBJECT_WRITE_CONFLICT,
                        current_revision=current_rev,
                    )
                # Already holding the file flock: do not reacquire via _load_objects.
                previous = ([json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
                             if line.strip()] if path.exists() else [])
                validate_revision_write(previous, rows, snapshot_id=snapshot_id)
                payload = _objects_jsonl_bytes(rows)
                _atomic_replace_bytes(path, payload)
                self._objects_expected_revs()[snapshot_id] = hashlib.sha256(payload).hexdigest()

    def _save_objects_pinned(
        self,
        snapshot_id: str,
        rows: list[dict[str, Any]],
        expected_revision: str | None = None,
    ) -> None:
        if expected_revision is None:
            self._save_objects(snapshot_id, rows)
            return
        self._save_objects(snapshot_id, rows, expected_revision=expected_revision)

    def refresh_objects_expected_revision(
        self,
        snapshot_id: str,
        revision: str | None = None,
    ) -> str:
        """Remember the current snapshot file revision so a retry can proceed."""
        if ".." in snapshot_id or "/" in snapshot_id or "\\" in snapshot_id:
            raise ConsoleError("unknown_snapshot")
        current = revision if revision else _file_revision(self._objects_path(snapshot_id))
        self._objects_expected_revs()[snapshot_id] = current
        return current

    def _rollback_store_files(
        self,
        *,
        objects_snapshot: tuple[str, bytes | None] | None = None,
        envelopes: dict[str, Any] | None = None,
        bindings: dict[str, Any] | None = None,
        ledger_size: int | None = None,
    ) -> None:
        if objects_snapshot is not None:
            snapshot_id, prior = objects_snapshot
            path = self._objects_path(snapshot_id)
            if prior is None:
                with suppress(OSError):
                    path.unlink()
            else:
                _atomic_replace_bytes(path, prior)
        if envelopes is not None:
            _atomic_write(self._envelopes_path, envelopes)
        if bindings is not None:
            _atomic_write(self._bindings_path, bindings)
        if ledger_size is not None and self._ledger_path.exists():
            current = self._ledger_path.stat().st_size
            if current > ledger_size:
                with self._ledger_path.open("r+b") as handle:
                    handle.truncate(ledger_size)

    def _require_mutable_working_revision(self, snapshot_id: str) -> None:
        """Published work is historical input, never current review work."""
        if snapshot_id and self.snapshot_is_published(snapshot_id):
            raise ConsoleError("published_working_revision_immutable")

    @staticmethod
    def _changed_snapshot_ids(
        current: dict[str, Any], prepared: dict[str, Any]
    ) -> set[str]:
        keys = set(current) | set(prepared)
        return {
            str(key)
            for key in keys
            if current.get(key) != prepared.get(key)
        }

    def _guard_prepared_working_revision_mutation(
        self,
        *,
        envelopes: dict[str, Any] | None,
        bindings: dict[str, Any] | None,
        objects: tuple[str, list[dict[str, Any]]] | None,
        snapshot_id: str | None,
    ) -> None:
        """Seal every curation commit, not only named Review entry points.

        File-backed and Azure-without-workflow-Postgres topologies otherwise let
        direct helpers such as ``confirm_object_type`` and ``confirm_relations``
        reach the generic commit boundary without passing through ``review_object``.
        """
        candidates: set[str] = set()
        if snapshot_id:
            candidates.add(str(snapshot_id))
        if objects is not None:
            candidates.add(str(objects[0]))
        if envelopes is not None:
            candidates.update(
                self._changed_snapshot_ids(
                    dict(getattr(self, "_envelopes", {})), envelopes
                )
            )
        if bindings is not None:
            candidates.update(
                self._changed_snapshot_ids(
                    dict(getattr(self, "_bindings", {})), bindings
                )
            )

        for candidate in sorted(value for value in candidates if value):
            try:
                self._require_mutable_working_revision(candidate)
            except ConsoleError as exc:
                # A brand-new ingest is not a mutation of an existing
                # WorkingRevision and may reach the commit boundary before the
                # envelope exists in the current store.
                if exc.code == "unknown_snapshot":
                    continue
                raise

    def _commit_prepared_store(
        self,
        *,
        envelopes: dict[str, Any] | None = None,
        bindings: dict[str, Any] | None = None,
        objects: tuple[str, list[dict[str, Any]]] | None = None,
        expected_revision: str | None = None,
        ledger_fn: Callable[[], None] | None = None,
        snapshot_id: str | None = None,
    ) -> None:
        """Write one complete store transaction, then publish in-process maps.

        Serializes objects/envelopes/bindings/ledger writes. Rebases shared
        maps so a stale full-map copy cannot clobber another writer's
        already-committed keys. Conflict or mid-write failure rolls back
        only files this transaction actually wrote.
        """
        with self._store_write_lock():
            self._reload_store_locked()
            sid = snapshot_id or (objects[0] if objects is not None else None)
            if envelopes is not None and sid:
                envelopes = self._rebase_snapshot_map(self._envelopes, envelopes, sid)
            if bindings is not None and sid:
                bindings = self._rebase_snapshot_map(self._bindings, bindings, sid)
            self._guard_prepared_working_revision_mutation(
                envelopes=envelopes, bindings=bindings, objects=objects, snapshot_id=snapshot_id)
            prior_envelopes = deepcopy(self._envelopes)
            prior_bindings = deepcopy(self._bindings)
            prior_objects: tuple[str, bytes | None] | None = None
            if objects is not None:
                path = self._objects_path(objects[0])
                prior_objects = (objects[0], path.read_bytes() if path.exists() else None)
            prior_ledger = self._ledger_path.stat().st_size if self._ledger_path.exists() else 0
            self._prepared_envelopes = envelopes
            self._prepared_bindings = bindings
            wrote_objects = False
            wrote_envelopes = False
            wrote_bindings = False
            wrote_ledger = False
            try:
                if objects is not None:
                    self._save_objects_pinned(
                        objects[0],
                        objects[1],
                        expected_revision,
                    )
                    wrote_objects = True
                if envelopes is not None:
                    self._save_envelopes()
                    wrote_envelopes = True
                if bindings is not None:
                    self._save_bindings()
                    wrote_bindings = True
                if ledger_fn is not None:
                    wrote_ledger = True
                    ledger_fn()
            except Exception:
                self._rollback_store_files(
                    objects_snapshot=prior_objects if wrote_objects else None,
                    envelopes=prior_envelopes if wrote_envelopes else None,
                    bindings=prior_bindings if wrote_bindings else None,
                    ledger_size=prior_ledger if wrote_ledger else None,
                )
                raise
            finally:
                self._prepared_envelopes = None
                self._prepared_bindings = None
            if envelopes is not None:
                self._envelopes = envelopes
            if bindings is not None:
                self._bindings = bindings

    def _account(self, account_id: str) -> dict[str, Any]:
        account = self._accounts.get(account_id)
        if not account:
            raise ConsoleError("unknown_account")
        return account

    def _require_role(self, account_id: str, role: str) -> dict[str, Any]:
        account = self._account(account_id)
        if role not in account["roles"]:
            raise ConsoleError(f"{role}_role_required")
        return account

    def _envelope(self, snapshot_id: str) -> dict[str, Any]:
        envelope = self._envelopes.get(snapshot_id)
        if not envelope:
            raise ConsoleError("unknown_snapshot")
        return envelope

    def create_account(
        self,
        username: str,
        password: str,
        roles: Iterable[str],
        display_name: str | None = None,
    ) -> dict[str, Any]:
        username = username.strip()
        display = (display_name or username).strip()
        if not username or not password:
            raise ConsoleError("account_fields_required")
        if _is_forbidden_identity(username) or _is_forbidden_identity(display):
            raise ConsoleError("forbidden_reviewer_identity")
        if any(row["username"] == username for row in self._accounts.values()):
            raise ConsoleError("username_already_exists")
        role_set = sorted(set(roles))
        if any(role not in ALLOWED_ROLES for role in role_set):
            raise ConsoleError("unknown_role")
        salt, digest = _hash_password(password)
        account_id = f"acc-{uuid.uuid4().hex[:12]}"
        record = {
            "account_id": account_id,
            "username": username,
            "display_name": display,
            "roles": role_set,
            "password_salt": salt,
            "password_hash": digest,
            "created_at": utc_now(),
        }
        self._accounts[account_id] = record
        self._save_accounts()
        return self._public_account(record)

    def public_signup(self, **_kwargs: Any) -> dict[str, Any]:
        raise ConsoleError("public_signup_forbidden")

    def _public_account(self, record: dict[str, Any]) -> dict[str, Any]:
        return {
            "account_id": record["account_id"],
            "username": record["username"],
            "display_name": record["display_name"],
            "roles": list(record["roles"]),
        }

    def authenticate(self, username: str, password: str) -> dict[str, Any]:
        record = next((row for row in self._accounts.values() if row["username"] == username), None)
        if not record:
            raise ConsoleError("invalid_credentials")
        _, digest = _hash_password(password, record["password_salt"])
        if not secrets.compare_digest(digest, record["password_hash"]):
            raise ConsoleError("invalid_credentials")
        token = secrets.token_hex(32)
        session = {
            "token": token,
            "account_id": record["account_id"],
            "username": record["username"],
            "roles": list(record["roles"]),
            "created_at": utc_now(),
            "expires_at": utc_after(DEFAULT_SESSION_TTL_SECONDS),
        }

        def add(sessions: dict[str, dict[str, Any]]) -> None:
            sessions[token] = session

        self._with_sessions(add)
        return dict(session)

    def session_account(self, token: str | None) -> dict[str, Any]:
        if not token:
            raise ConsoleError("not_authenticated")
        with self._sessions_write_lock():
            self._reload_sessions_locked()
            session = self._sessions.get(token)
            if not session or session_is_expired(session):
                raise ConsoleError("not_authenticated")
            account = self._account(session["account_id"])
            return self._public_account(account)

    def logout(self, token: str | None) -> None:
        if not token:
            return

        def remove(sessions: dict[str, dict[str, Any]]) -> None:
            sessions.pop(token, None)

        self._with_sessions(remove)

    def list_accounts(self) -> list[dict[str, Any]]:
        return [self._public_account(row) for row in self._accounts.values()]

    def list_reviewer_accounts(self) -> list[dict[str, Any]]:
        return [row for row in self.list_accounts() if "reviewer" in row["roles"]]

    def _resolve_named_reviewers(self, named_reviewers: list[str], uploader_id: str) -> list[str]:
        if not named_reviewers:
            raise ConsoleError("named_reviewers_required")
        resolved: list[str] = []
        for raw in named_reviewers:
            value = str(raw).strip()
            if _is_forbidden_identity(value):
                raise ConsoleError("forbidden_reviewer_identity")
            account = self._accounts.get(value) or next(
                (row for row in self._accounts.values() if row["username"] == value or row["display_name"] == value),
                None,
            )
            if account is None:
                raise ConsoleError("forbidden_reviewer_identity" if _is_forbidden_identity(value) else "unknown_reviewer")
            if _is_forbidden_identity(account["username"]) or _is_forbidden_identity(account["display_name"]):
                raise ConsoleError("forbidden_reviewer_identity")
            if "reviewer" not in account["roles"]:
                raise ConsoleError("named_reviewer_must_have_reviewer_role")
            resolved.append(account["account_id"])
        unique = list(dict.fromkeys(resolved))
        others = [account_id for account_id in unique if account_id != uploader_id]
        if not others:
            raise ConsoleError("uploader_cannot_be_sole_required_reviewer")
        return unique

    def manage_review_participation(self, **command: Any) -> dict[str, Any]:
        from src.review_participation_v1 import execute
        return execute(self, **command)

    def change_review_policy(self, **command: Any) -> dict[str, Any]:
        if self.snapshot_is_published(command["snapshot_id"]):
            raise ConsoleError("published_working_revision_immutable")
        raise ConsoleError("managed_participation_command_required")

    def update_decision_graph(self, **command: Any) -> dict[str, Any]:
        from src.decision_review_commands_v1 import execute
        return execute(self, action="graph", **command)

    def confirm_decision_graph(self, **command: Any) -> dict[str, Any]:
        from src.decision_review_commands_v1 import execute
        return execute(self, action="confirm", **command)

    def _validated_review_policy(self, value: dict[str, Any]) -> dict[str, Any]:
        from src.review_policy_v1 import validate_policy, participants
        try:
            policy = validate_policy(value)
        except ValueError as exc:
            raise ConsoleError(str(exc)) from exc
        for actor_id in participants(policy):
            account = self._require_role(actor_id, "reviewer")
            if account.get("retirement") or any(
                _is_forbidden_identity(str(account.get(key) or ""))
                for key in ("username", "display_name")
            ):
                raise ConsoleError("forbidden_reviewer_identity")
        return policy

    def create_managed_account(
        self,
        *,
        actor_id: str,
        username: str,
        password: str,
        roles: Iterable[str],
        display_name: str | None = None,
    ) -> dict[str, Any]:
        self._require_role(actor_id, "publisher")
        return self.create_account(username, password, roles, display_name=display_name)

    def assign_roles(self, *, actor_id: str, account_id: str, roles: Iterable[str]) -> dict[str, Any]:
        self._require_role(actor_id, "publisher")
        account = self._account(account_id)
        role_set = sorted(set(roles))
        if any(role not in ALLOWED_ROLES for role in role_set):
            raise ConsoleError("unknown_role")
        account["roles"] = role_set
        self._save_accounts()
        return self._public_account(account)

    def waiting_task_counts(self, account_id: str) -> dict[str, int]:
        account = self._account(account_id)
        roles = set(account["roles"])
        envelopes = self.list_envelopes()
        ingest = 0
        review = 0
        publish = 0
        tree = 0
        for envelope in envelopes:
            objects = self._load_objects(envelope["snapshot_id"], remember=False)
            statuses = {(row.get("governance") or {}).get("validation_status") for row in objects}
            if envelope.get("uploader_account_id") == account_id and statuses & {"revise", "rejected"}:
                ingest += 1
            if account_id in (envelope.get("named_reviewers") or []) and "reviewer" in roles:
                if "needs_review" in statuses or not objects:
                    review += 1
                elif objects and all(
                    (row.get("governance") or {}).get("validation_status") == "needs_review"
                    or row.get("object_type") == "document"
                    for row in objects
                ):
                    review += 1
                elif "needs_review" in statuses:
                    review += 1
            if envelope.get("clinical_rereview_required") and roles & {"researcher", "reviewer", "publisher"}:
                tree += 1
            if (
                "publisher" in roles
                and envelope.get("state") == CAPTURED
                and envelope.get("publication_eligibility") != PRE_REVIEW_BLOCKED
                and not self.snapshot_is_published(envelope["snapshot_id"])
            ):
                publish += 1
        if "reviewer" in roles:
            from src.review_duty_v1 import reviewer_route_counts
            from src.knowledge_path_v1 import is_structural_projection
            from src.publication_readiness_v1 import review_followup_queues
            review = 0
            for envelope in envelopes:
                sid = envelope["snapshot_id"]
                if account_id not in (envelope.get("named_reviewers") or []):
                    continue
                if envelope.get("publication_eligibility") == PRE_REVIEW_BLOCKED:
                    continue
                rows = self.snapshot_objects(sid)
                path = review_path_for_klasse(envelope["class"])
                bindings = self.object_review_bindings(sid)
                fragments = self.review_source_fragments(sid)
                routes = reviewer_route_counts(rows, review_path=path, reviewer_id=account_id,
                                               bindings=bindings, fragments=fragments)
                structure = path != "boom" and any(is_structural_projection(row)
                    and (row.get("governance") or {}).get("validation_status") != "approved"
                    for row in rows)
                followups = review_followup_queues(rows, review_path=path, bindings=bindings,
                                                  fragments=fragments)
                if routes["actionable_review_duties"] or structure or any(followups.values()):
                    review += 1
        if "publisher" not in roles:
            publish = 0
        if "researcher" not in roles:
            ingest = 0
        return {
            "ingest": ingest,
            "tree": tree,
            "review": review,
            "publish": publish,
            "accounts": 0,
        }

    def object_review_bindings(self, snapshot_id: str, *, objects=None) -> list[dict[str, Any]]:
        self._envelope(snapshot_id)
        current = {row["object_id"]: row for row in (self.snapshot_objects(snapshot_id) if objects is None else objects)}
        out = []
        for row in self._bindings.get(snapshot_id, []):
            item = dict(row)
            obj = current.get(item.get("object_id"))
            item["valid"] = bool(obj) and still_matches(item, obj)
            out.append(item)
        return out

    def _prepare_knowledge_revision(self, snapshot_id, previous, proposed, *, reason, actor):
        return revise_object(previous, proposed, snapshot_id=snapshot_id,
                             reason=reason, actor=actor)

    def _commit_knowledge_change(self, snapshot_id, previous, proposed, *, reason, actor, retain_revise=False):
        """Existing store transaction for repair metadata/provenance mutations."""
        revision = self.objects_revision(snapshot_id)
        updated = self._prepare_knowledge_revision(snapshot_id, previous, proposed, reason=reason, actor=actor)
        if retain_revise and proposed.get("governance", {}).get("validation_status") == "revise":
            updated["governance"]["validation_status"] = "revise"
        rows = self._load_objects(snapshot_id, remember=False)
        if updated["object_version"] == previous["object_version"]:
            rows = [updated if (row["object_id"], row["object_version"]) ==
                    (previous["object_id"], previous["object_version"]) else row for row in rows]
        else:
            rows.append(updated)
        bindings = deepcopy(self._bindings)
        bindings[snapshot_id] = invalidate_for_object(bindings.get(snapshot_id, []), previous["object_id"])
        self._commit_prepared_store(objects=(snapshot_id, rows), bindings=bindings,
                                    expected_revision=revision, snapshot_id=snapshot_id)
        return deepcopy(updated)

    def confirm_object_type(
        self,
        *,
        actor_id: str,
        snapshot_id: str,
        object_id: str,
        confirmed_object_type: str,
        expected_revision: str | None = None,
    ) -> dict[str, Any]:
        reviewer = self._require_role(actor_id, "reviewer")
        if actor_id not in self._envelope(snapshot_id)["named_reviewers"]:
            raise ConsoleError("reviewer_not_named_on_snapshot")
        review_path = review_path_for_klasse(self._envelope(snapshot_id)["class"])
        if not is_confirmable_type_for_path(confirmed_object_type, review_path):
            raise ConsoleError("unknown_object_type")
        current = self.snapshot_objects(snapshot_id, for_update=True)
        target = next((row for row in current if row["object_id"] == object_id), None)
        if target is None:
            raise ConsoleError("unknown_object")
        previous = deepcopy(target)
        if target.get("object_type") == "document":
            raise ConsoleError("unknown_object_type")
        if is_admission_blocked(target, review_path=review_path):
            raise ConsoleError("blocked_candidate_not_reviewable")
        self._require_open_original(snapshot_id, object_id)
        if target.get("confirmed_object_type") != confirmed_object_type:
            target["object_version"] = bump_patch(str(target.get("object_version") or "1.0"))
        target["confirmed_object_type"] = confirmed_object_type
        target["object_type"] = confirmed_object_type
        if confirmed_object_type not in {"recommendation", "outcome"}:
            target.pop("confirmed_recommendation_strength", None)
        if confirmed_object_type != "recommendation":
            target.pop(CONFIRMED_RECOMMENDATION_SEMANTICS_FIELD, None)
        mark_four_eyes_on_object(target, confirmed_type=confirmed_object_type)
        target = self._prepare_knowledge_revision(snapshot_id, previous, target,
            reason="type confirmation", actor=reviewer["username"])
        stamp_canonical_hashes(target)
        history = [
            row
            for row in self._load_objects(snapshot_id)
            if not (row["object_id"] == object_id and row["object_version"] == target["object_version"])
        ]
        history.append(target)
        new_bindings = deepcopy(self._bindings)
        new_bindings[snapshot_id] = invalidate_for_object(new_bindings.get(snapshot_id, []), object_id)
        self._commit_prepared_store(
            objects=(snapshot_id, history),
            bindings=new_bindings,
            expected_revision=expected_revision,
        )
        return deepcopy(target)

    def confirm_relations(
        self,
        *,
        actor_id: str,
        snapshot_id: str,
        object_id: str,
        relations: list[dict[str, Any]],
        expected_revision: str | None = None,
    ) -> dict[str, Any]:
        reviewer = self._require_role(actor_id, "reviewer")
        if actor_id not in self._envelope(snapshot_id)["named_reviewers"]:
            raise ConsoleError("reviewer_not_named_on_snapshot")
        current = self.snapshot_objects(snapshot_id, for_update=True)
        target, history, new_bindings = self._prepare_relation_confirmation(
            snapshot_id=snapshot_id, object_id=object_id, relations=relations, current=current, actor=reviewer["username"])
        self._commit_prepared_store(objects=(snapshot_id, history), bindings=new_bindings,
                                    expected_revision=expected_revision)
        return deepcopy(target)

    def _prepare_relation_confirmation(self, *, snapshot_id, object_id, relations, current, actor):
        """Existing relation validation prepares rows; the caller owns the commit."""
        target = next((deepcopy(row) for row in current if row["object_id"] == object_id), None)
        if target is None:
            raise ConsoleError("unknown_object")
        for row in relations:
            if not is_closed_relation_type(row.get("relation_type")):
                raise ConsoleError("unknown_relation_type")
        try:
            confirmed = confirm_relation_set(relations)
        except ValueError as exc:
            raise ConsoleError("unknown_relation_type") from exc
        from src.heading_parent_list_v1 import is_heading_object, parent_proposal_may_bind

        for row in confirmed:
            if row.get("relation_type") not in {"parent", "child"}:
                continue
            peer = next((item for item in current if item.get("object_id") == row.get("target_object_id")), None)
            if peer is None:
                continue
            if row["relation_type"] == "child":
                child, parent = target, peer
            else:
                child, parent = peer, target
            if is_heading_object(child) and is_heading_object(parent):
                if not parent_proposal_may_bind(child, parent, current):
                    raise ConsoleError("invalid_parent_structure")
        original_target = deepcopy(target)
        previous_relations = binding_relations(target)
        previous_child_relations = [
            row
            for row in previous_relations
            if row.get("relation_type") == "child"
        ]
        confirmed_parents = [
            row["target_object_id"]
            for row in confirmed
            if row.get("relation_type") == "child"
        ]
        if len(confirmed_parents) > 1:
            raise ConsoleError("multiple_parents_not_allowed")
        canonical_parent_changed = False
        if confirmed_parents:
            canonical_parent_changed = target.get("parent_object_id") != confirmed_parents[0]
            target["parent_object_id"] = confirmed_parents[0]
        elif previous_child_relations:
            canonical_parent_changed = target.get("parent_object_id") is not None
            target["parent_object_id"] = None
        if target.get("confirmed_relations") != confirmed or canonical_parent_changed:
            target["object_version"] = bump_patch(str(target.get("object_version") or "1.0"))
        target["confirmed_relations"] = confirmed
        target = self._prepare_knowledge_revision(snapshot_id, original_target, target,
            reason="relation confirmation", actor=actor)
        stamp_canonical_hashes(target)

        previous_children = {
            row["target_object_id"]
            for row in previous_relations
            if row.get("relation_type") == "parent"
        }
        confirmed_children = {
            row["target_object_id"]
            for row in confirmed
            if row.get("relation_type") == "parent"
        }
        peer_updates: list[dict[str, Any]] = []
        for child_id in previous_children | confirmed_children:
            peer = next((item for item in current if item.get("object_id") == child_id), None)
            if peer is None:
                continue
            if child_id in confirmed_children:
                desired_parent = object_id
            else:
                # Only undo the parent assignment that this relation created.
                # The child may have been re-parented independently since then.
                if peer.get("parent_object_id") != object_id:
                    continue
                desired_parent = None
            if peer.get("parent_object_id") == desired_parent:
                continue
            updated_peer = deepcopy(peer)
            updated_peer["parent_object_id"] = desired_parent
            updated_peer["object_version"] = bump_patch(
                str(updated_peer.get("object_version") or "1.0")
            )
            updated_peer = self._prepare_knowledge_revision(snapshot_id, peer, updated_peer,
                reason="parent relation confirmation", actor=actor)
            stamp_canonical_hashes(updated_peer)
            peer_updates.append(updated_peer)
        history = [
            row
            for row in self._load_objects(snapshot_id)
            if not (row["object_id"] == object_id and row["object_version"] == target["object_version"])
        ]
        history.append(target)
        history.extend(peer_updates)
        new_bindings = deepcopy(self._bindings)
        new_bindings[snapshot_id] = invalidate_for_object(new_bindings.get(snapshot_id, []), object_id)
        for peer in peer_updates:
            new_bindings[snapshot_id] = invalidate_for_object(
                new_bindings.get(snapshot_id, []), peer["object_id"]
            )
        return target, history, new_bindings

    def _source_cache_path(self, envelope: dict[str, Any]) -> Path:
        digest = safe_path_token(str(envelope["sha256"]), pattern=STORE_DIGEST_RE)
        filename = safe_store_filename(Path(str(envelope["binary_path"])).name)
        return safe_path_under(self.source_store, digest, filename)

    def _verified_source_bytes(self, envelope: dict[str, Any]) -> tuple[Path, bytes]:
        """Rebuild the configured cache from the existing immutable authority."""
        freeze_path = self._source_cache_path(envelope)
        try:
            freeze_bytes = freeze_path.read_bytes() if freeze_path.is_file() else None
        except OSError:
            freeze_bytes = None
        expected_digest = str(envelope["sha256"])
        if freeze_bytes is not None and sha256_bytes(freeze_bytes) != expected_digest:
            freeze_bytes = None
        immutable_locator = envelope.get("immutable_storage_locator")
        if freeze_bytes is None and immutable_locator and self.immutable_source_store is not None:
            try:
                freeze_bytes = self.immutable_source_store.load_verified(immutable_locator)
            except (G2SourceStoreError, ValueError) as exc:
                raise ConsoleError("immutable_source_recovery_failed") from exc
            if sha256_bytes(freeze_bytes) != expected_digest:
                raise ConsoleError("immutable_source_recovery_failed")
            _atomic_write_bytes(freeze_path, freeze_bytes)
        if freeze_bytes is None:
            raise ConsoleError("freeze_bytes_missing")
        return freeze_path, freeze_bytes

    def _assert_source_work_unchanged(self, envelope: dict[str, Any], revision: str, published_error: str) -> None:
        """Called under the existing store lock immediately before committing."""
        snapshot_id = envelope["snapshot_id"]
        if self.snapshot_is_published(snapshot_id):
            raise ConsoleError(published_error)
        from src.attempt_diagnostics_v1 import comparable_envelope
        if comparable_envelope(self._envelope(snapshot_id)) != comparable_envelope(envelope) or self.objects_revision(snapshot_id) != revision:
            raise ConsoleError(SNAPSHOT_OBJECT_WRITE_CONFLICT, current_revision=self.objects_revision(snapshot_id))

    def open_source_passage(
        self, *, snapshot_id: str, object_id: str, include_document: bool = False,
    ) -> dict[str, Any]:
        envelope = self._envelope(snapshot_id)
        target = next((row for row in self.snapshot_objects(snapshot_id) if row["object_id"] == object_id), None)
        if target is None:
            raise ConsoleError("unknown_object")
        _, freeze_bytes = self._verified_source_bytes(envelope)
        try:
            opened = open_source_passage(
                freeze_bytes=freeze_bytes,
                content_kind=envelope["content_kind"],
                locator=None,
                object_record=target,
                include_locators=include_document,
            )
            if include_document:
                opened.update(freeze_bytes=freeze_bytes, content_kind=envelope["content_kind"])
            return opened
        except OpenOriginalError as exc:
            raise ConsoleError(exc.code) from exc

    def _require_open_original(self, snapshot_id: str, object_id: str) -> dict[str, Any]:
        try:
            return self.open_source_passage(snapshot_id=snapshot_id, object_id=object_id)
        except ConsoleError as exc:
            if exc.code in {
                "source_locator_missing",
                "freeze_bytes_missing",
                "locator_kind_mismatch",
                "unsupported_locator",
            }:
                raise ConsoleError("open_original_required") from exc
            raise

    def ingest(
        self,
        *,
        actor_id: str,
        ingest_kind: str,
        title: str,
        version: str,
        date: str,
        live_url: str,
        class_: str,
        family: str,
        named_reviewers: list[str],
        filename: str | None = None,
        data: bytes | None = None,
        content_type: str | None = None,
        url: str | None = None,
        replaces_snapshot_id: str | None = None,
        review_policy: dict[str, Any] | None = None,
        source_status: str = "unknown",
        command_id: str | None = None,
        revision_reason: str = "",
    ) -> dict[str, Any]:
        self._require_role(actor_id, "researcher")
        if source_status not in {"unknown", "established", "draft"}:
            raise ConsoleError("invalid_source_status")
        if ingest_kind not in {"new", "new_version"}:
            raise ConsoleError("invalid_ingest_kind")
        if class_ not in ALLOWED_CLASSES:
            raise ConsoleError("invalid_class")
        with self._store_write_lock():
            self._reload_store_locked()
            family_hook = self.resolve_family_label(family, required_code="ingest_fields_required")
        if not title.strip():
            raise ConsoleError("ingest_fields_required")
        source_version = safe_path_token(
            validate_ingest_source_version(version),
            pattern=SOURCE_VERSION_RE,
            code="invalid_source_version",
        )
        source_date = safe_path_token(
            normalize_ingest_source_date(date),
            pattern=ISO_DATE_RE,
            code="invalid_source_date",
        )
        if review_policy is None:
            reviewers = self._resolve_named_reviewers(named_reviewers, actor_id)
        else:
            review_policy = self._validated_review_policy(review_policy)
            from src.review_policy_v1 import participants
            reviewers = participants(review_policy)
            if named_reviewers and set(named_reviewers) != set(reviewers):
                raise ConsoleError("review_policy_membership_conflict")
        review_path = review_path_for_klasse(class_)
        candidate_url = url or live_url or ""
        if review_path == "boom" and is_live_rest_url(candidate_url):
            if data is None or is_live_rest_sole_source(
                data=data or b"",
                live_url=candidate_url,
                filename=filename or "",
            ):
                raise ConsoleError("live_rest_not_sole_source")
        if url:
            data, fetched_type, fetched_name = self.url_fetcher(url)
            filename = filename or fetched_name
            content_type = content_type or fetched_type
        if data is None:
            raise ConsoleError("official_file_or_url_required")
        filename = normalize_upload_filename(filename)
        if review_path == "boom" and review_policy is not None and data.startswith(b"%PDF-"):
            kind = classify_official_file(data, filename, content_type)
        elif review_path == "boom":
            freeze_errors = boom_freeze_errors(
                data=data,
                filename=filename,
                live_url=live_url or url or "",
            )
            if "story_html_alone_insufficient" in freeze_errors:
                raise ConsoleError("story_html_alone_insufficient")
            if "live_rest_sole_source" in freeze_errors:
                raise ConsoleError("live_rest_not_sole_source")
            if freeze_errors:
                raise ConsoleError(freeze_errors[0])
            kind = "boom"
        elif review_policy is not None and not boom_freeze_errors(data=data, filename=filename, live_url=live_url or ""):
            kind = "boom"
        else:
            kind = classify_official_file(data, filename, content_type)
        if url and kind == "html":
            raise ConsoleError("live_url_html_not_allowed")
        digest = safe_path_token(sha256_bytes(data), pattern=STORE_DIGEST_RE)
        ingest_command = None
        if command_id is not None:
            if not command_id.strip() or len(command_id) > 128:
                raise ConsoleError("ingest_command_invalid")
            from src.integrity_kernel import stable_hash
            ingest_command = {"id": command_id, "actor_id": actor_id,
                "payload_hash": stable_hash({"digest": digest, "filename": filename, "kind": kind,
                    "title": title.strip(), "version": source_version, "date": source_date,
                    "class": class_, "family": family_hook, "reviewers": reviewers, "policy": review_policy,
                    "source_status": source_status, "live_url": live_url or url or "", "ingest_kind": ingest_kind,
                    "replaces_snapshot_id": replaces_snapshot_id, "revision_reason": revision_reason})}
            identity_hash = stable_hash({"actor_id": actor_id, "command_id": command_id})
            command_snapshot = f"snap-{identity_hash[:16]}-{identity_hash[16:24]}"
            self.list_envelopes()
            prior = self._envelopes.get(command_snapshot)
            if prior is not None:
                if prior.get("ingest_command") != ingest_command:
                    raise ConsoleError("ingest_command_conflict")
                return self._receipt(prior)
        immutable_locator = None
        if self.immutable_source_store is not None:
            try:
                immutable_locator = self.immutable_source_store.store_verified(
                    data=data,
                    sha256=digest,
                    filename=filename,
                )
            except (G2SourceStoreError, ValueError) as exc:
                raise ConsoleError("immutable_source_storage_failed") from exc
        stored_path = safe_path_under(self.source_store, digest, filename)
        stored_path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write_bytes(stored_path, data)
        locator = immutable_locator or f"g0-local:sources/private/{digest}/{filename}"
        snapshot_id = command_snapshot if ingest_command else f"snap-{digest[:16]}-{uuid.uuid4().hex[:8]}"
        document_id = f"console-{_slug(family_hook)}-{_slug(title)}-{_slug(source_version)}-{digest[:8]}"
        source_id = f"src-{digest[:16]}"
        previous = None
        if ingest_kind == "new_version":
            if not replaces_snapshot_id:
                raise ConsoleError("replaces_snapshot_id_required")
            previous = self._envelope(replaces_snapshot_id)
            if review_policy is not None and document_id == previous["document_id"]:
                document_id = f"{document_id}-revision-{snapshot_id[5:]}"

        envelope = {
            "snapshot_id": snapshot_id,
            "source_id": source_id,
            "document_id": document_id,
            "sha256": digest,
            "locator": locator,
            "binary_path": str(stored_path.resolve()),
            "immutable_storage_locator": immutable_locator,
            "state": CAPTURED,
            "publication_eligibility": (
                "eligible_for_transform_and_review"
                if immutable_locator
                else "blocked_pending_immutable_storage"
            ),
            "content_kind": kind,
            "ingest_kind": ingest_kind,
            "title": title.strip(),
            "version": source_version,
            "date": source_date,
            "live_url": live_url or url or "",
            "class": class_,
            "family": family_hook,
            "named_reviewers": reviewers,
            "uploader_account_id": actor_id,
            "source_declaration": {"status": source_status, "declared_by": actor_id, "declared_at": utc_now()},
            "review_passes": {},
            "is_live_capture": ingest_kind == "new",
            "replaces_snapshot_id": replaces_snapshot_id,
            "revision_reason": revision_reason,
            "object_diff": None,
            "clinical_rereview_required": False,
            "acquired_at": utc_now(),
            "console_version": CONSOLE_VERSION,
        }

        if ingest_command:
            envelope["ingest_command"] = ingest_command
        if review_policy is not None:
            envelope["review_policy"] = deepcopy(review_policy)
        attempt_id = None
        attempt_deadline = None
        initial_eligibility = envelope["publication_eligibility"]
        expected_revision = None
        if self._bounded_semantic_preparation(kind, class_):
            from src.processing_retry_v1 import reserve, now
            limits = self._processing_limits()
            attempt_deadline = time.monotonic() + limits.attempt
            with self._store_write_lock():
                self._reload_store_locked()
                prior = self._envelopes.get(snapshot_id)
                if prior is not None:
                    if ingest_command and prior.get("ingest_command") == ingest_command:
                        return self._receipt(prior)
                    raise ConsoleError("ingest_command_conflict")
                expected_revision = (self.workflow_document_store.revision_for_rows([])
                                     if getattr(self, "workflow_document_store", None) is not None else "")
                envelope["publication_eligibility"] = PRE_REVIEW_BLOCKED
                envelope["processing_blocker"] = "pre_review_llm_processing_in_progress"
                attempt, _ = reserve(envelope, command_id=uuid.uuid4().hex, actor_id=actor_id,
                    revision=expected_revision, clock=now(), limits=limits, kind="ingest")
                attempt_id = attempt["attempt_id"]
                try:
                    # Existing create-if-absent CAS/advisory lock also protects
                    # reservation when another runtime has a different file lock.
                    self._commit_prepared_store(envelopes={snapshot_id:envelope}, objects=(snapshot_id, []),
                                                expected_revision="", snapshot_id=snapshot_id)
                except ConsoleError:
                    self._reload_store_locked()
                    prior = self._envelopes.get(snapshot_id)
                    if ingest_command and prior and prior.get("ingest_command") == ingest_command:
                        return self._receipt(prior)
                    raise
                expected_revision = self.objects_revision(snapshot_id)
            expected_envelope = deepcopy(self._envelope(snapshot_id))
        with self._source_attempt_failure(snapshot_id, attempt_id):
            processing_started = quality_instant()
            try:
                fragments, spec = self._fragments_and_spec(
                    kind,
                    stored_path,
                    data=data,
                    document_id=document_id,
                    source_id=source_id,
                    title=title.strip(),
                    family=family_hook,
                    class_=class_,
                    formation_context={
                        "snapshot_id": snapshot_id,
                        "source_sha256": digest,
                        "semantic_replay": None,
                        "explicit_decision_graph": review_path == "boom" and review_policy is not None,
                        "model_call_limits": {key:attempt["limits"][key] for key in ("connect", "idle", "total", "attempt", "max_attempts")} if attempt_id else None,
                        "attempt_deadline": attempt_deadline,
                        "diagnostic_checkpoint": self._diagnostic_writer(snapshot_id, attempt_id),
                        "processing_reference": attempt.get("processing_reference") if attempt_id else None,
                    },
                )
            except ConsoleError as exc:
                if not exc.code.startswith(("pre_review_llm_", "docling_")):
                    raise
                if attempt_id:
                    self._record_processing_failure(snapshot_id, attempt_id, exc)
                    return self._receipt(self._envelope(snapshot_id))
                blocked_envelope = deepcopy(envelope)
                blocked_envelope["publication_eligibility"] = PRE_REVIEW_BLOCKED
                blocked_envelope["processing_blocker"] = exc.code
                record_processing(blocked_envelope, [], fragments=[], replay=None,
                                  started_at=processing_started, outcome="blocked", reason=exc.code)
                self._commit_prepared_store(
                    envelopes={snapshot_id: blocked_envelope},
                    snapshot_id=snapshot_id,
                )
                return self._receipt(blocked_envelope)

            replay_record = spec.pop(SEMANTIC_REPLAY_SPEC_KEY, None)
            if isinstance(replay_record, dict):
                envelope["semantic_replay"] = deepcopy(replay_record)

            manifest = {
                "canonical_source": {
                    "source_id": source_id,
                    "title": title.strip(),
                    "publisher": "V&VN",
                    "source_url": live_url or url or f"urn:vvn:freeze:{digest}",
                    "source_type": "interactive_tree" if kind == "boom" else kind,
                    "source_level": 1,
                    "canonicality": "canonical",
                    "source_checksum": digest,
                    "checksum_algorithm": "sha256",
                    "integrity_status": "verified",
                    "publication_date": source_date,
                    "version": source_version,
                }
            }
            objects = transform_generic(spec, manifest, fragments)
            if review_path == "boom":
                stamp_boom_flags(objects, fragments)
            else:
                objects = apply_admission_gate(
                    objects,
                    klasse=class_,
                    fragments=fragments,
                    document_version=source_version,
                    source_hash=digest,
                )
            objects = apply_passage_register(objects)
            if review_policy is not None:
                from src.review_policy_v1 import project_policy
                project_policy(objects, review_policy)
            if review_path == "boom" and review_policy is not None:
                from src.decision_graph_v1 import prepare_graph
                envelope.update(prepare_graph(stored_path, data, kind, fragments, objects, digest))
            if previous:
                envelope["object_diff"] = self._diff_objects(
                    self.snapshot_objects(previous["snapshot_id"]),
                    objects,
                )
            record_processing(envelope, objects, fragments=fragments, replay=replay_record,
                              started_at=processing_started)
            if attempt_id:
                envelope["quality_processing_runs"][-1]["attempt_id"] = attempt_id
                envelope["publication_eligibility"] = initial_eligibility
                envelope.pop("processing_blocker", None)
            prepared_envelopes = {snapshot_id: envelope}
            try:
                transaction = self._reprocessing_transaction(snapshot_id) if attempt_id else self._store_write_lock()
                with transaction:
                    if attempt_id:
                        from src.processing_retry_v1 import assert_active, finish, attach_transport, now
                        assert_active(self._envelope(snapshot_id), attempt_id, now())
                        if time.monotonic() >= attempt_deadline:
                            raise ConsoleError("processing_attempt_expired")
                        self._assert_source_work_unchanged(expected_envelope, expected_revision, "published_objects_must_not_be_rewritten")
                        self._require_role(actor_id, "researcher")
                        self._verified_source_bytes(expected_envelope)
                        assert_active(self._envelope(snapshot_id), attempt_id, now())
                        if time.monotonic() >= attempt_deadline:
                            raise ConsoleError("processing_attempt_expired")
                        from src.attempt_diagnostics_v1 import merge_diagnostics
                        merge_diagnostics(envelope, self._envelope(snapshot_id))
                        finish(envelope, attempt_id, state="succeeded")
                        attach_transport(next(a for a in envelope["processing_attempts"] if a["attempt_id"] == attempt_id),
                                         (replay_record or {}).get("provider_evidence", {}).get("transport", {}))
                    self._commit_prepared_store(
                        objects=(snapshot_id, objects), envelopes=prepared_envelopes,
                        expected_revision=expected_revision if attempt_id else "" if ingest_command else None,
                    )
            except ConsoleError:
                if not ingest_command or attempt_id:
                    raise
                self.list_envelopes()
                prior = self._envelopes.get(snapshot_id)
                if prior and prior.get("ingest_command") == ingest_command:
                    return self._receipt(prior)
                raise
            return self._receipt(envelope)

    def create_review_successor(self, **command: Any) -> dict[str, Any]:
        from src.decision_successor_v1 import execute
        return execute(self, **command)

    def _processing_limits(self):
        from src.bounded_model_call_v1 import ModelCallLimits
        reader = getattr(self, "_model_call_limits_reader", None)
        return reader() if reader is not None else ModelCallLimits()

    def _bounded_semantic_preparation(self, kind, class_):
        from src.docling_pdf_v1 import enabled
        if kind == "pdf" and enabled():
            return True
        from src.passage_formation_policy_v1 import DETERMINISTIC_MODE
        return (getattr(self, "_pre_review_semantic_bound", False) and kind in {"html", "pdf"}
                and class_ != "beslisboom" and self._passage_formation_mode_reader() != DETERMINISTIC_MODE)

    def processing_status(self, snapshot_id: str, *, actor_id: str | None = None) -> dict[str, Any]:
        from src.processing_retry_v1 import status
        if actor_id is not None:
            account = self._account(actor_id)
            if not {"researcher", "reviewer"}.intersection(account["roles"]):
                raise ConsoleError("researcher_role_required")
            if "researcher" not in account["roles"] and actor_id not in self._envelope(snapshot_id).get("named_reviewers", []):
                raise ConsoleError("reviewer_not_named_on_snapshot")
        result = status(self._envelope(snapshot_id), policy=self._processing_limits())
        if (self.snapshot_is_published(snapshot_id) or self.snapshot_objects(snapshot_id)
                or self._bindings.get(snapshot_id) or self._envelope(snapshot_id).get("review_passes")):
            result["retry_allowed"] = False
        from src.recoverable_formation_v1 import incomplete
        result["formation_incomplete"] = incomplete(self._envelope(snapshot_id), objects=self.snapshot_objects(snapshot_id))
        evidence = (self._envelope(snapshot_id).get("semantic_replay") or {}).get("provider_evidence") or {}
        result["formation_state"] = "pending" if result["formation_incomplete"] else "complete"
        if evidence.get("task_policy"):
            from src.bounded_formation_v1 import formation_progress as project_formation_progress
            result["formation_progress"] = deepcopy(
                evidence.get("formation_progress") or project_formation_progress(evidence)
            )
        else:
            result["formation_progress"] = {}
        result["resume_allowed"] = bool(self._can_resume_formation(snapshot_id)
            and result["state"] != "running"
            and (result["retry_attempts_used"] < result["max_attempts"] or result["recovery_available"])
            and result["reason_code"] not in {"processing_retry_cooldown", "processing_structural_limit"})
        return result

    def _can_resume_formation(self, snapshot_id):
        from src.recoverable_formation_v1 import incomplete, VERSION
        from src.source_context_review_v1 import ROLE_KEY, LINKS_KEY
        envelope = self._envelope(snapshot_id)
        contract = ((envelope.get("semantic_replay") or {}).get("identity") or {}).get("components", {}).get("semantic_contract_version", "")
        from src.bounded_formation_v1 import VERSION as TASK_VERSION
        return bool(incomplete(envelope) and VERSION in contract and TASK_VERSION in contract
            and not self.snapshot_is_published(snapshot_id)
            and not self.object_review_bindings(snapshot_id) and not envelope.get("review_passes")
            and not any(((row.get("governance") or {}).get("validation_status") not in {None, "needs_review"}
                     and not ((row.get("governance") or {}).get("validation_status") == "superseded"
                              and (lineage_evidence(row) or {}).get("reason") == "same-source candidate retirement"))
                or ROLE_KEY in (row.get("metadata") or {}) or LINKS_KEY in (row.get("metadata") or {})
                    or ((row.get("metadata") or {}).get("passage_register") or {}).get("source") == "review"
                for row in self.snapshot_objects(snapshot_id)))

    def resume_formation(self, *, actor_id, snapshot_id, command_id, expected_revision):
        """Resume open producer work; reviewed/published work requires successor."""
        from src.processing_retry_v1 import reserve, now
        limits = self._processing_limits()
        deadline = time.monotonic() + limits.attempt
        with self._reprocessing_transaction(snapshot_id):
            account = self._account(actor_id)
            envelope = deepcopy(self._envelope(snapshot_id))
            if not {"researcher", "reviewer"}.intersection(account["roles"]):
                raise ConsoleError("researcher_role_required")
            if "researcher" not in account["roles"] and actor_id not in envelope.get("named_reviewers", []):
                raise ConsoleError("reviewer_not_named_on_snapshot")
            duplicate = next((a for a in envelope.get("processing_attempts", []) if a["command_id"] == command_id), None)
            if duplicate is None:
                if not self._can_resume_formation(snapshot_id):
                    raise ConsoleError("pre_review_retry_existing_work")
                if self.objects_revision(snapshot_id) != expected_revision:
                    raise ConsoleError(SNAPSHOT_OBJECT_WRITE_CONFLICT, current_revision=self.objects_revision(snapshot_id))
            attempt, fresh = reserve(envelope, command_id=command_id, actor_id=actor_id,
                revision=expected_revision, clock=now(), limits=limits, kind="resume")
            self._commit_prepared_store(envelopes={snapshot_id: envelope}, snapshot_id=snapshot_id)
        if not fresh:
            if attempt["kind"] != "resume" or attempt["expected_revision"] != expected_revision:
                raise ConsoleError("processing_command_conflict")
            if attempt["state"] == "succeeded":
                return self._receipt(envelope)
            raise ConsoleError("processing_attempt_in_progress" if attempt["state"] == "running"
                               else attempt.get("error_code") or "processing_dependency_failed")
        return self._execute_source_attempt(actor_id=actor_id, snapshot_id=snapshot_id, attempt=attempt, deadline=deadline)

    @contextmanager
    def _reprocessing_transaction(self, snapshot_id: str) -> Iterator[None]:
        # Local single-worker compatibility uses the existing durable file boundary;
        # production PostgreSQL overrides this with its existing row transaction.
        with self._store_write_lock():
            self._reload_store_locked()
            self._envelope(snapshot_id)
            yield

    def _diagnostic_writer(self, snapshot_id, attempt_id):
        if not attempt_id:
            return None
        def write(phase, values):
            from src.processing_retry_v1 import assert_active, now
            from src.attempt_diagnostics_v1 import checkpoint
            with self._reprocessing_transaction(snapshot_id):
                current = deepcopy(self._envelope(snapshot_id))
                active = assert_active(current, attempt_id, now())
                checkpoint(active, phase, values)
                try:
                    self._commit_prepared_store(envelopes={snapshot_id: current}, snapshot_id=snapshot_id)
                except Exception as error:
                    raise ConsoleError("processing_diagnostic_write_failed") from error
        return write

    def authorize_processing_recovery(self, *, actor_id, snapshot_id, reason):
        """One grant per blocked snapshot; consumption belongs to reservation."""
        from src.processing_retry_v1 import now, expire_running, status as processing_retry_status
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 1000:
            raise ConsoleError("processing_recovery_reason_required")
        with self._reprocessing_transaction(snapshot_id):
            account = self._account(actor_id)
            if "publisher" not in account["roles"]:
                raise ConsoleError("publisher_role_required")
            envelope = deepcopy(self._envelope(snapshot_id))
            if actor_id not in envelope.get("named_reviewers", []) and actor_id != envelope.get("uploader_account_id"):
                raise ConsoleError("reviewer_not_named_on_snapshot")
            if self.snapshot_is_published(snapshot_id):
                raise ConsoleError("published_objects_must_not_be_rewritten")
            objects, revision = self.snapshot_objects_and_revision(snapshot_id, include_blocked=True)
            if (not self._can_resume_formation(snapshot_id)
                    and (envelope.get("publication_eligibility") != PRE_REVIEW_BLOCKED or objects
                         or self._bindings.get(snapshot_id) or envelope.get("review_passes"))):
                raise ConsoleError("pre_review_retry_existing_work")
            expire_running(envelope, now())
            attempts = envelope.get("processing_attempts") or []
            if attempts and attempts[-1].get("error_code") in {"pre_review_llm_input_limit_exceeded", "pre_review_llm_output_limit_exceeded"}:
                raise ConsoleError("processing_structural_limit")
            retry_policy = self._processing_limits()
            retry_status = processing_retry_status(envelope, policy=retry_policy)
            if retry_status["retry_attempts_used"] < retry_policy.max_attempts or any(a["state"] == "running" for a in attempts):
                raise ConsoleError("processing_recovery_not_required")
            if envelope.get("processing_recovery"):
                raise ConsoleError("processing_recovery_already_authorized")
            grant = {"authorization_id": "pra_" + uuid.uuid4().hex, "actor_id": actor_id,
                     "reason": reason.strip(), "authorized_at": now().isoformat(),
                     "source_hash": envelope["sha256"], "source_version": envelope["version"],
                     "revision": revision, "consumed_by": None}
            envelope["processing_recovery"] = grant
            self._commit_prepared_store(envelopes={snapshot_id: envelope}, snapshot_id=snapshot_id)
            return deepcopy(grant)

    def _record_processing_failure(self, snapshot_id, attempt_id, error):
        from src.processing_retry_v1 import KEY, finish
        with self._reprocessing_transaction(snapshot_id):
            current = deepcopy(self._envelope(snapshot_id))
            active = next(a for a in current[KEY] if a["attempt_id"] == attempt_id)
            if active["state"] == "running":
                finish(current, attempt_id, state="failed", error=error)
                if active.get("kind") == "ingest" and current.get("processing_blocker") == "pre_review_llm_processing_in_progress" and not self.snapshot_objects(snapshot_id):
                    current["processing_blocker"] = active["error_code"]
                    record_processing(current, [], fragments=[], replay=None, started_at=active["started_at"],
                                      outcome="blocked", reason=active["error_code"])
                self._commit_prepared_store(envelopes={snapshot_id:current}, snapshot_id=snapshot_id)

    @contextmanager
    def _source_attempt_failure(self, snapshot_id, attempt_id):
        try:
            yield
        except Exception as error:
            if attempt_id is not None:
                self._record_processing_failure(snapshot_id, attempt_id, error)
            raise

    def _execute_source_attempt(self, *, actor_id, snapshot_id, attempt, deadline):
        with self._source_attempt_failure(snapshot_id, attempt["attempt_id"]):
            return self.reextract_unpublished(actor_id=actor_id, snapshot_id=snapshot_id,
                 _attempt_id=attempt["attempt_id"], _attempt_deadline=deadline)

    def retry_pre_review(self, *, actor_id: str, snapshot_id: str, command_id: str) -> dict[str, Any]:
        """Retry an empty blocked source without losing evidence or prior work."""
        from src.processing_retry_v1 import KEY, reserve, now
        limits = self._processing_limits()
        deadline = time.monotonic() + limits.attempt
        with self._reprocessing_transaction(snapshot_id):
            account = self._account(actor_id)
            if not {"researcher", "reviewer"}.intersection(account["roles"]):
                raise ConsoleError("researcher_role_required")
            envelope = deepcopy(self._envelope(snapshot_id))
            if self.snapshot_is_published(snapshot_id):
                raise ConsoleError("published_objects_must_not_be_rewritten")
            objects, revision = self.snapshot_objects_and_revision(snapshot_id, include_blocked=True)
            duplicate = any(a["command_id"] == command_id for a in envelope.get(KEY, []))
            if not duplicate:
                if envelope.get("publication_eligibility") != PRE_REVIEW_BLOCKED:
                    raise ConsoleError("pre_review_reprocess_not_required")
                if objects or self._bindings.get(snapshot_id) or envelope.get("review_passes"):
                    raise ConsoleError("pre_review_retry_existing_work")
            attempt, fresh = reserve(envelope, command_id=command_id, actor_id=actor_id, revision=revision, clock=now(), limits=limits)
            self._commit_prepared_store(envelopes={snapshot_id: envelope}, snapshot_id=snapshot_id)
        if not fresh:
            if attempt["state"] == "succeeded":
                return self._receipt(envelope)
            if attempt["state"] == "running":
                raise ConsoleError("processing_attempt_in_progress")
            error = ConsoleError(attempt["error_code"], attempt.get("validation_code") or attempt["error_code"])
            error.pre_review_diagnostics = {"reference": attempt.get("processing_reference"), "reason_code": attempt.get("validation_code")}
            raise error
        return self._execute_source_attempt(actor_id=actor_id, snapshot_id=snapshot_id,
                                            attempt=attempt, deadline=deadline)

    def reextract_unpublished(self, *, actor_id: str, snapshot_id: str, _attempt_id: str | None = None, _attempt_deadline: float | None = None) -> dict[str, Any]:
        """Replace unpublished object identities with a new extract of the same freeze.

        Source hash stays. Published objects MUST NOT be rewritten. MUST NOT hide
        stored fragments in the UI without this extract.
        """
        account = self._account(actor_id)
        if "researcher" not in account["roles"] and "reviewer" not in account["roles"]:
            raise ConsoleError("researcher_role_required")
        envelope = self._envelope(snapshot_id)
        if _attempt_id is None and envelope.get("publication_eligibility") == PRE_REVIEW_BLOCKED:
            return self.retry_pre_review(actor_id=actor_id, snapshot_id=snapshot_id, command_id=uuid.uuid4().hex)
        _, expected_revision = self.snapshot_objects_and_revision(snapshot_id, include_blocked=True)
        if _attempt_id is not None:
            from src.processing_retry_v1 import assert_active, now
            attempt = assert_active(envelope, _attempt_id, now())
            if attempt["actor_id"] != actor_id or attempt["source_hash"] != envelope["sha256"]:
                raise ConsoleError("processing_command_conflict")
            if attempt["expected_revision"] != expected_revision:
                raise ConsoleError(SNAPSHOT_OBJECT_WRITE_CONFLICT, current_revision=expected_revision)
            if (attempt.get("kind", "retry") == "retry" and (envelope.get("publication_eligibility") != PRE_REVIEW_BLOCKED
                    or self.snapshot_objects(snapshot_id) or self._bindings.get(snapshot_id)
                    or envelope.get("review_passes"))):
                raise ConsoleError("pre_review_retry_existing_work")
        from src.source_context_review_v1 import ROLE_KEY, LINKS_KEY
        if (self._bindings.get(snapshot_id) or envelope.get("review_passes") or
                any(((row.get("governance") or {}).get("validation_status") not in {None, "needs_review"}
                     and not ((row.get("governance") or {}).get("validation_status") == "superseded"
                              and (lineage_evidence(row) or {}).get("reason") == "same-source candidate retirement"))
                    or ROLE_KEY in (row.get("metadata") or {}) or LINKS_KEY in (row.get("metadata") or {})
                    or ((row.get("metadata") or {}).get("passage_register") or {}).get("source") == "review"
                    for row in self.snapshot_objects(snapshot_id))):
            raise ConsoleError("pre_review_retry_existing_work")
        processing_started = quality_instant()
        if self.snapshot_is_published(snapshot_id):
            raise ConsoleError("published_objects_must_not_be_rewritten")
        if _attempt_id is None and self._bounded_semantic_preparation(envelope["content_kind"], envelope["class"]):
            from src.processing_retry_v1 import reserve, now
            limits = self._processing_limits()
            deadline = time.monotonic() + limits.attempt
            with self._reprocessing_transaction(snapshot_id):
                self._assert_source_work_unchanged(envelope, expected_revision, "published_objects_must_not_be_rewritten")
                reserved = deepcopy(envelope)
                attempt, _ = reserve(reserved, command_id=uuid.uuid4().hex, actor_id=actor_id,
                                     revision=expected_revision, clock=now(), limits=limits, kind="reextract")
                self._commit_prepared_store(envelopes={snapshot_id:reserved}, snapshot_id=snapshot_id)
            return self._execute_source_attempt(actor_id=actor_id, snapshot_id=snapshot_id, attempt=attempt, deadline=deadline)
        freeze_path, freeze_bytes = self._verified_source_bytes(envelope)
        fragments, spec = self._fragments_and_spec(
            envelope["content_kind"],
            freeze_path,
            data=freeze_bytes,
            document_id=envelope["document_id"],
            source_id=envelope["source_id"],
            title=envelope["title"],
            family=envelope["family"],
            class_=envelope["class"],
            formation_context={
                "snapshot_id": snapshot_id,
                "source_sha256": envelope["sha256"],
                "semantic_replay": deepcopy(envelope.get("semantic_replay")),
                "resume_formation": bool(_attempt_id and attempt.get("kind") == "resume"),
                "explicit_decision_graph": "decision_graph" in envelope,
                "model_call_limits": {key:attempt["limits"][key] for key in ("connect", "idle", "total", "attempt", "max_attempts")} if _attempt_id and attempt.get("limits") else None,
                "attempt_deadline": _attempt_deadline,
                "diagnostic_checkpoint": self._diagnostic_writer(snapshot_id, _attempt_id),
                "processing_reference": attempt.get("processing_reference") if _attempt_id else None,
            },
        )
        replay_record = spec.pop(SEMANTIC_REPLAY_SPEC_KEY, None)
        manifest = {
            "canonical_source": {
                "source_id": envelope["source_id"],
                "title": envelope["title"],
                "publisher": "V&VN",
                "source_url": envelope.get("live_url") or f"urn:vvn:freeze:{envelope['sha256']}",
                "source_type": "interactive_tree" if envelope["content_kind"] == "boom" else envelope["content_kind"],
                "source_level": 1,
                "canonicality": "canonical",
                "source_checksum": envelope["sha256"],
                "checksum_algorithm": "sha256",
                "integrity_status": "verified",
                "publication_date": envelope["date"],
                "version": envelope["version"],
            }
        }
        objects = transform_generic(spec, manifest, fragments)
        if envelope["class"] == "beslisboom":
            stamp_boom_flags(objects, fragments)
        else:
            objects = apply_admission_gate(
                objects,
                klasse=envelope["class"],
                fragments=fragments,
                document_version=envelope["version"],
                source_hash=envelope["sha256"],
            )
        objects = apply_passage_register(objects)
        prepared_envelope = deepcopy(envelope)
        if envelope.get("review_policy"):
            from src.review_policy_v1 import project_policy
            project_policy(objects, envelope["review_policy"])
        if _attempt_id is not None and attempt.get("kind") == "resume":
            from src.recoverable_formation_v1 import preserve_unchanged
            objects = preserve_unchanged(objects, self.snapshot_objects(snapshot_id))
        if review_path_for_klasse(envelope["class"]) != "boom":
            objects = reprocessed_history(self._load_objects(snapshot_id, remember=False), objects,
                                          snapshot_id=snapshot_id, actor=account["username"])
        if "decision_graph" in envelope:
            from src.decision_graph_v1 import prepare_graph
            prepared_envelope.update(prepare_graph(freeze_path, freeze_bytes, envelope["content_kind"], fragments, objects, envelope["sha256"]))
        if isinstance(replay_record, dict):
            prepared_envelope["semantic_replay"] = deepcopy(replay_record)
        prepared_envelope["review_passes"] = {}
        prepared_envelope["state"] = CAPTURED
        prepared_envelope["publication_eligibility"] = (
            "eligible_for_transform_and_review"
            if prepared_envelope.get("immutable_storage_locator")
            else "blocked_pending_immutable_storage"
        )
        prepared_envelope.pop("processing_blocker", None)
        record_processing(prepared_envelope, current_revisions(objects, snapshot_id=snapshot_id), fragments=fragments, replay=replay_record,
                          started_at=processing_started)
        if _attempt_id is not None:
            prepared_envelope["quality_processing_runs"][-1]["attempt_id"] = _attempt_id
        if _attempt_id is not None and attempt.get("kind", "retry") == "retry":
            if not any((obj.get("metadata") or {}).get("admission", {}).get("gate_result") == "allowed"
                       for obj in objects if obj.get("object_type") not in {"document", "heading"}):
                raise ConsoleError("pre_review_no_reviewable_candidates")
            successful_run = prepared_envelope["quality_processing_runs"][-1]
            successful_run["attempt_id"] = _attempt_id
        replaces_snapshot_id = str(prepared_envelope.get("replaces_snapshot_id") or "")
        if replaces_snapshot_id:
            prepared_envelope["object_diff"] = self._diff_objects(
                self.snapshot_objects(replaces_snapshot_id),
                objects,
            )
        transaction = self._reprocessing_transaction(snapshot_id) if _attempt_id is not None else self._store_write_lock()
        with transaction:
            self._reload_store_locked()
            if _attempt_id is not None:
                from src.processing_retry_v1 import assert_active, now
                active = assert_active(self._envelope(snapshot_id), _attempt_id, now())
                if active["actor_id"] != actor_id or active["source_hash"] != envelope["sha256"] or active.get("source_version", envelope["version"]) != envelope["version"]:
                    raise ConsoleError("processing_command_conflict")
                if _attempt_deadline is not None and time.monotonic() >= _attempt_deadline:
                    raise ConsoleError("processing_attempt_expired")
            self._assert_source_work_unchanged(envelope, expected_revision, "published_objects_must_not_be_rewritten")
            self._verified_source_bytes(envelope)
            account = self._account(actor_id)
            if not {"researcher", "reviewer"}.intersection(account["roles"]):
                raise ConsoleError("researcher_role_required")
            if _attempt_id is not None:
                from src.processing_retry_v1 import finish, attach_transport
                assert_active(self._envelope(snapshot_id), _attempt_id, now())
                if _attempt_deadline is not None and time.monotonic() >= _attempt_deadline:
                    raise ConsoleError("processing_attempt_expired")
                from src.attempt_diagnostics_v1 import merge_diagnostics
                merge_diagnostics(prepared_envelope, self._envelope(snapshot_id))
                finish(prepared_envelope, _attempt_id, state="succeeded")
                stored = next(a for a in prepared_envelope["processing_attempts"] if a["attempt_id"] == _attempt_id)
                if stored.get("kind") == "resume":
                    from src.bounded_formation_v1 import formation_progress, pending_source_extent
                    before_provider = (envelope.get("semantic_replay") or {}).get("provider_evidence") or {}
                    after_provider = (prepared_envelope.get("semantic_replay") or {}).get("provider_evidence") or {}
                    before_progress = before_provider.get("formation_progress") or formation_progress(before_provider)
                    after_progress = after_provider.get("formation_progress") or formation_progress(after_provider)
                    before_extent = pending_source_extent(before_provider)
                    after_extent = pending_source_extent(after_provider)
                    stored["formation_progress_made"] = bool(
                        after_progress.get("terminal_task_count", 0) > before_progress.get("terminal_task_count", 0)
                        or after_progress.get("pending_task_count", 0) < before_progress.get("pending_task_count", 0)
                        or after_extent["unknown_pending_count"] < before_extent["unknown_pending_count"]
                        or (
                            after_extent["unknown_pending_count"] == before_extent["unknown_pending_count"]
                            and after_extent["pending_source_char_count"] < before_extent["pending_source_char_count"]
                        )
                    )
                transport = (replay_record or {}).get("provider_evidence", {}).get("transport", {})
                if (replay_record or {}).get("semantic_execution") == "replay":
                    stored["replayed_call_id"] = transport.get("call_id")
                else:
                    attach_transport(stored, transport)
            self._commit_prepared_store(
                objects=(snapshot_id, objects),
                envelopes={snapshot_id: prepared_envelope},
                bindings={snapshot_id: []},
                expected_revision=expected_revision,
            )
        return self._receipt(prepared_envelope)

    def snapshot_is_published(self, snapshot_id: str) -> bool:
        """True when this snapshot is a published projection or has been published."""
        envelope = self._envelope(snapshot_id)
        if envelope.get("state") in PUBLISHED_ENVELOPE_STATES:
            return True
        if envelope.get("published") is True:
            return True
        rows = self._load_objects(snapshot_id, remember=False)
        if any((row.get("governance") or {}).get("publication_status") == "published" for row in rows):
            return True
        return self._snapshot_in_published_projection(snapshot_id)

    def _published_projection_path(self) -> Path:
        return self.runtime / PUBLISHED_PROJECTION_FILENAME

    def _snapshot_in_published_projection(self, snapshot_id: str) -> bool:
        path = self._published_projection_path()
        if not path.is_file():
            return False
        token = safe_snapshot_id(snapshot_id)
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("snapshot_id") == token:
                return True
            meta = row.get("metadata") or {}
            if meta.get("snapshot_id") == token:
                return True
        return False

    def _maybe_remove_unpublished_freeze_bytes(self, envelope: dict[str, Any]) -> bool:
        """Remove unshared unpublished source bytes from local cache and immutable storage.

        MUST NOT walk ``/home/data``. MUST NOT rmtree the source store.
        Published snapshots never reach this path.
        """
        digest = safe_path_token(str(envelope["sha256"]), pattern=STORE_DIGEST_RE)
        still_used = any(
            row.get("sha256") == digest and row.get("snapshot_id") != envelope["snapshot_id"]
            for row in self._envelopes.values()
        )
        if still_used:
            return False

        remote_removed = False
        locator = str(envelope.get("immutable_storage_locator") or "").strip()
        immutable = self.immutable_source_store
        if locator and immutable is not None:
            delete_verified = getattr(immutable, "delete_verified", None)
            if callable(delete_verified):
                try:
                    remote_removed = bool(delete_verified(locator))
                except G2SourceStoreError:
                    # Snapshot deletion must not become half-applied because external
                    # source cleanup failed. The orphan remains recoverable/operator-visible.
                    remote_removed = False

        filename = safe_store_filename(Path(str(envelope.get("binary_path") or "")).name)
        stored = safe_path_under(self.source_store, digest, filename)
        local_removed = False
        if stored.is_file():
            stored.unlink()
            local_removed = True
        parent = stored.parent
        try:
            if parent.is_dir() and parent != self.source_store.resolve() and not any(parent.iterdir()):
                parent.rmdir()
        except OSError:
            pass
        return local_removed or remote_removed

    def _delete_unpublished_snapshot_authority(self, snapshot_id: str) -> None:
        """Delete the workflow-authoritative snapshot when a durable authority is configured."""
        return None

    def delete_unpublished_snapshot(
        self,
        *,
        actor_id: str,
        snapshot_id: str,
        confirmed: bool = False,
        confirm_title: str = "",
    ) -> dict[str, Any]:
        """Remove one unpublished captured snapshot from the operations console.

        Whole snapshot only. MUST confirm. MUST type-to-confirm the exact title.
        MUST NOT delete a published projection.
        MUST NOT hide selected objects inside a freeze that stays in Review.
        Four-eyes is not required. Capture is not publication.
        """
        if ".." in snapshot_id or "/" in snapshot_id or "\\" in snapshot_id:
            raise ConsoleError("unknown_snapshot")
        token = safe_snapshot_id(snapshot_id)
        account = self._account(actor_id)
        if _is_forbidden_identity(account["username"]) or _is_forbidden_identity(account["display_name"]):
            raise ConsoleError("forbidden_reviewer_identity")
        roles = set(account["roles"])
        if "researcher" not in roles and "reviewer" not in roles:
            raise ConsoleError("unpublished_delete_role_required")
        if not confirmed:
            raise ConsoleError("delete_confirmation_required")
        with self._store_write_lock():
            self._reload_store_locked()
            envelope = deepcopy(self._envelope(token))
            result = self._delete_unpublished_snapshot_locked(
                actor_id=actor_id,
                token=token,
                account=account,
                confirm_title=confirm_title,
            )
            # Durable implementations commit before returning. Irreversible source
            # cleanup must never participate in the rollback-capable transition.
            try:
                result["freeze_bytes_removed"] = self._maybe_remove_unpublished_freeze_bytes(envelope)
            except OSError:
                # The document is already deleted; a cache cleanup failure must
                # not report a failed domain transition or resurrect the snapshot.
                result["freeze_bytes_removed"] = False
            return result

    def _delete_unpublished_snapshot_locked(
        self,
        *,
        actor_id: str,
        token: str,
        account: dict[str, Any],
        confirm_title: str,
    ) -> dict[str, Any]:
        envelope = self._envelope(token)
        if self.snapshot_is_published(token):
            raise ConsoleError("published_projection_must_not_be_deleted")
        title = str(envelope["title"])
        if confirm_title != title:
            raise ConsoleError("delete_title_confirmation_required")
        digest = str(envelope["sha256"])
        self._delete_unpublished_snapshot_authority(token)
        objects_path = self._objects_path(token)
        if objects_path.is_file():
            objects_path.unlink()
        self._envelopes.pop(token, None)
        self._bindings.pop(token, None)
        self._save_envelopes()
        self._save_bindings()
        append_event(
            self._ledger_path,
            event_type=UNPUBLISHED_DELETE_EVENT,
            object_id=token,
            object_version=str(envelope.get("version") or ""),
            actor=account["username"],
            details={
                "snapshot_id": token,
                "sha256": digest,
                "title": title,
                "actor_id": actor_id,
                "display_name": account["display_name"],
            },
        )
        return {
            "deleted": True,
            "snapshot_id": token,
            "sha256": digest,
            "title": title,
            "actor": account["username"],
            "freeze_bytes_removed": False,
            "four_eyes_required": False,
            "second_named_reviewer_required": False,
            "capture_is_publication": False,
            "g2": "BLOCKED",
        }

    def _extract(self, kind: str, path: Path, *, document_id: str, source_id: str, deadline=None) -> list[dict[str, Any]]:
        if kind == "html":
            return extract_html(path, document_id=document_id, source_id=source_id)
        if kind == "boom":
            return extract_boom_fragments(path.read_bytes(), document_id=document_id, source_id=source_id)
        from src.docling_pdf_v1 import enabled, extract as extract_docling
        from src.docling_contract_v1 import DoclingError
        try:
            return (extract_docling(path, document_id=document_id, source_id=source_id, deadline=deadline)
                    if enabled() else extract_pdf(path, document_id=document_id, source_id=source_id))
        except DoclingError as exc:
            raise ConsoleError(exc.code) from exc

    def _read_source_fragments(self, envelope, path):
        from src.docling_contract_v1 import stored_fragments
        retained = stored_fragments(envelope)
        if retained is not None:
            return retained
        args = {"document_id": envelope["document_id"], "source_id": envelope["source_id"]}
        if envelope["content_kind"] == "pdf":
            # Historical compatibility is selected by persisted provenance,
            # never by a failed Docling conversion or the current config.
            if envelope["class"] == "beslisboom":
                from src.decision_graph_v1 import pdf_fragments
                return pdf_fragments(path, **args, use_docling=False,
                                     construct_units=bool(envelope.get("decision_unit_contract")))
            return extract_pdf(path, **args)
        return self._extract(envelope["content_kind"], path, **args)

    def _require_resolved_candidate_source(self, envelope, target):
        """Validate against verified source without changing durable row bytes."""
        from src.knowledge_path_v1 import source_lineage_resolves
        try:
            source_path, _ = self._verified_source_bytes(envelope)
            fragments = self._read_source_fragments(envelope, source_path)
        except (ConsoleError, ValueError, OSError) as exc:
            raise ConsoleError("source_lineage_unavailable") from exc
        source = target.get("source") or {}
        if (source.get("source_checksum") != envelope["sha256"]
                or source.get("version") != envelope["version"]):
            raise ConsoleError("source_lineage_incomplete")
        if not source_lineage_resolves(target, fragments=fragments):
            raise ConsoleError("source_lineage_incomplete")
        return fragments

    def review_source_fragments(self, snapshot_id, *, envelope=None):
        """Call-local authoritative extraction for content-duty readers."""
        envelope = envelope if envelope is not None else self._envelope(snapshot_id)
        if review_path_for_klasse(envelope["class"]) == "boom":
            return None
        try:
            source_path, _ = self._verified_source_bytes(envelope)
            return self._read_source_fragments(envelope, source_path)
        except (ConsoleError, ValueError, OSError, KeyError):
            # A reader may show repair/disposition, never content authority.
            return None

    def _fragments_and_spec(
        self,
        kind: str,
        path: Path,
        *,
        data: bytes,
        document_id: str,
        source_id: str,
        title: str,
        family: str,
        class_: str,
        formation_context: dict[str, Any] | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        explicit_graph = bool((formation_context or {}).get("explicit_decision_graph"))
        retained_fragments = (formation_context or {}).get("retained_fragments")
        if kind == "pdf" and class_ == "beslisboom":
            from src.decision_graph_v1 import pdf_fragments
            try:
                fragments = (retained_fragments if retained_fragments is not None else
                             pdf_fragments(path, document_id=document_id, source_id=source_id,
                                           deadline=(formation_context or {}).get("attempt_deadline")))
            except Exception as exc:
                from src.docling_contract_v1 import DoclingError
                if isinstance(exc, DoclingError):
                    raise ConsoleError(exc.code) from exc
                raise ConsoleError("invalid_decision_pdf") from exc
            spec = boom_spec_from_fragments(document_id=document_id, title=title,
                                           family=family, class_=class_, fragments=fragments)
            from src.decision_unit_construction_v1 import construction_spec
            return fragments, construction_spec(spec, fragments)
        if kind == "boom":
            try:
                fragments = extract_boom_fragments(data, document_id=document_id, source_id=source_id)
            except ValueError as exc:
                raise ConsoleError("invalid_boom_freeze") from exc
            if explicit_graph and class_ == "beslisboom":
                from src.decision_bundles_v1 import split_bundles
                fragments = split_bundles(fragments)
            if class_ != "beslisboom":
                fragments = [{k: v for k, v in f.items() if k != "boom_kind"} for f in fragments]
                return fragments, _spec_from_fragments(document_id=document_id, title=title, family=family,
                    class_=class_, fragments=fragments, content_kind=kind)
            spec = boom_spec_from_fragments(
                document_id=document_id,
                title=title,
                family=family,
                class_=class_,
                fragments=fragments,
            )
            return fragments, spec
        from src.docling_pdf_v1 import enabled
        kwargs = {"deadline": (formation_context or {}).get("attempt_deadline")} if kind == "pdf" and enabled() else {}
        fragments = (retained_fragments if retained_fragments is not None else
                     self._extract(kind, path, document_id=document_id, source_id=source_id, **kwargs))
        spec = _spec_from_fragments(
            document_id=document_id,
            title=title,
            family=family,
            class_=class_,
            fragments=fragments,
            content_kind=kind,
        )
        return fragments, spec

    def _diff_objects(self, previous: list[dict[str, Any]], current: list[dict[str, Any]]) -> dict[str, Any]:
        def key(row: dict[str, Any]) -> str:
            return (row.get("content") or {}).get("clean_text") or ""

        prev = {key(row): compute_canonical_object_hash(row) for row in previous if row.get("object_type") != "document" and key(row)}
        curr = {key(row): compute_canonical_object_hash(row) for row in current if row.get("object_type") != "document" and key(row)}
        return {
            "added": sorted(text for text in curr if text not in prev),
            "removed": sorted(text for text in prev if text not in curr),
            "changed": sorted(text for text in curr if text in prev and curr[text] != prev[text]),
            "unchanged": sorted(text for text in curr if text in prev and curr[text] == prev[text]),
        }

    def _receipt(self, envelope: dict[str, Any]) -> dict[str, Any]:
        receipt = deepcopy(envelope)
        receipt.pop("semantic_replay", None)
        return receipt

    def snapshot_objects(
        self,
        snapshot_id: str,
        include_blocked: bool = False,
        *,
        for_update: bool = False,
    ) -> list[dict[str, Any]]:
        self._envelope(snapshot_id)
        rows = self._load_objects(snapshot_id, remember=for_update)
        if include_blocked:
            return deepcopy(rows)
        return deepcopy(current_revisions(rows, snapshot_id=snapshot_id))

    def snapshot_containers(self, snapshot_id: str) -> dict[str, Any]:
        """Typed knowledge/source access over the current atomic revision."""
        from src.source_containers_v1 import partition
        from src.beslisboom_path_v1 import review_path_for_klasse
        return partition(self.snapshot_objects(snapshot_id),
                         review_path=review_path_for_klasse(self._envelope(snapshot_id)["class"]),
                         bindings=self.object_review_bindings(snapshot_id),
                         fragments=self.review_source_fragments(snapshot_id))

    def snapshot_objects_and_revision(
        self,
        snapshot_id: str,
        include_blocked: bool = False,
    ) -> tuple[list[dict[str, Any]], str]:
        """Read snapshot objects and the form-bound revision from one file load.

        MUST NOT use ``threading.local`` as the GET→POST pin. The revision is
        the SHA-256 of the objects file bytes that produced these rows.
        """
        self._envelope(snapshot_id)
        with self._objects_write_lock(snapshot_id):
            path = self._objects_path(snapshot_id)
            exists = path.exists()
            if not exists:
                text = ""
                rows: list[dict[str, Any]] = []
            else:
                text = path.read_text(encoding="utf-8")
                rows = [json.loads(line) for line in text.splitlines() if line.strip()]
            revision = (
                hashlib.sha256(text.encode("utf-8")).hexdigest()
                if exists
                else ""
            )
        if include_blocked:
            return deepcopy(rows), revision
        return deepcopy(current_revisions(rows, snapshot_id=snapshot_id)), revision

    def resolve_family_label(self, value: str | None, *, required_code: str = "family_required") -> str:
        """Reuse the first stored spelling for an equivalent Onderwerp.

        The existing envelope family field remains the authority. Comparison
        is Unicode-normalized, whitespace-collapsed and case-insensitive so
        researcher input such as Delier, delier and DELIER does not create
        separate branches. A genuinely new subject keeps the cleaned spelling.
        """
        label = normalize_topic_label(value)
        if not label:
            raise ConsoleError(required_code)
        identity = topic_identity_key(label)
        matches = [
            row
            for row in self.list_envelopes()
            if topic_identity_key(str(row.get("family") or "")) == identity
        ]
        if not matches:
            return label
        first = min(
            matches,
            key=lambda row: (
                str(row.get("acquired_at") or "9999"),
                str(row.get("snapshot_id") or ""),
            ),
        )
        return normalize_topic_label(str(first.get("family") or label)) or label

    def family_tree(self) -> dict[str, Any]:
        families: dict[str, dict[str, Any]] = {}
        for envelope in self.list_envelopes():
            family = envelope["family"]
            bucket = families.setdefault(family, {"family": family, "children": []})
            bucket["children"].append(
                {
                    "snapshot_id": envelope["snapshot_id"],
                    "class": envelope["class"],
                    "title": envelope["title"],
                    "version": envelope["version"],
                    "family": family,
                    "status": envelope["state"],
                    "publication_eligibility": envelope.get("publication_eligibility", ""),
                    "sha256": envelope["sha256"],
                    "parent": family,
                    "is_live_capture": envelope["is_live_capture"],
                }
            )
        for bucket in families.values():
            bucket["children"].sort(key=lambda child: (CLASS_ORDER.get(child["class"], 0) * -1, child["title"]))
        return {"axis": "family × class", "stable": True, "families": families}

    def move_family(self, *, actor_id: str, snapshot_id: str, new_family: str) -> dict[str, Any]:
        account = self._account(actor_id)
        if "researcher" not in account["roles"] and "publisher" not in account["roles"]:
            raise ConsoleError("curator_role_required")
        with self._store_write_lock():
            self._reload_store_locked()
            family = self.resolve_family_label(new_family)
            envelope = deepcopy(self._envelope(snapshot_id))
            envelope["family"] = family
            envelope["clinical_rereview_required"] = False
            self._commit_prepared_store(
                envelopes={snapshot_id: envelope},
                snapshot_id=snapshot_id,
            )
        return self._receipt(envelope)

    def _class_change_history_dir(self) -> Path:
        path = self.runtime / CLASS_CHANGE_HISTORY_DIRNAME
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _class_change_manifest(self, envelope: dict[str, Any]) -> dict[str, Any]:
        return {
            "canonical_source": {
                "source_id": envelope["source_id"],
                "title": envelope["title"],
                "publisher": "V&VN",
                "source_url": envelope.get("live_url") or "",
                "source_type": "interactive_tree" if envelope["content_kind"] == "boom" else envelope["content_kind"],
                "source_level": 1,
                "canonicality": "canonical",
                "source_checksum": envelope["sha256"],
                "checksum_algorithm": "sha256",
                "integrity_status": "verified",
                "publication_date": envelope["date"],
                "version": envelope["version"],
            }
        }

    def _full_rereview_rows(self, rows: list[dict[str, Any]]) -> None:
        for row in current_revisions(rows):
            governance = row.setdefault("governance", {})
            governance["validation_status"] = "needs_review"
            governance["validated_by"] = None
            governance["validation_date"] = None
            governance["review_snapshot_hash"] = None
            governance["publication_status"] = "unpublished"

    def _invalidate_all_bindings(self, snapshot_id: str) -> None:
        self._bindings[snapshot_id] = invalidate_for_object(self._bindings.get(snapshot_id, []), "")
        self._bindings[snapshot_id] = [
            {**row, "valid": False} for row in self._bindings.get(snapshot_id, [])
        ]
        self._save_bindings()

    def _record_class_change_event(
        self,
        *,
        account: dict[str, Any],
        envelope: dict[str, Any],
        from_class: str,
        to_class: str,
        model: str,
    ) -> None:
        append_event(
            self._ledger_path,
            event_type=DOCUMENT_CLASS_CHANGED_EVENT,
            object_id=envelope["snapshot_id"],
            object_version=str(envelope.get("version") or ""),
            actor=account["username"],
            details={
                "snapshot_id": envelope["snapshot_id"],
                "sha256": envelope["sha256"],
                "title": envelope["title"],
                "from_class": from_class,
                "to_class": to_class,
                "actor_id": account["account_id"],
                "display_name": account["display_name"],
                "model": model,
            },
        )

    def _archive_prior_objects(
        self,
        *,
        snapshot_id: str,
        rows: list[dict[str, Any]],
        from_class: str,
        to_class: str,
    ) -> dict[str, Any]:
        token = safe_snapshot_id(snapshot_id)
        stamp = utc_now().replace(":", "").replace("-", "")
        filename = safe_store_filename(f"{token}-{stamp}.jsonl")
        dest = safe_path_under(self._class_change_history_dir(), filename)
        dest.write_text(
            "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
            encoding="utf-8",
        )
        return {
            "reason": DOCUMENT_CLASS_CHANGED_EVENT,
            "from_class": from_class,
            "to_class": to_class,
            "changed_at": utc_now(),
            "object_count": len(rows),
            "object_ids": [row.get("object_id") for row in rows],
            "history_file": filename,
        }

    def prior_object_audit_history(self, snapshot_id: str) -> list[dict[str, Any]]:
        envelope = self._envelope(snapshot_id)
        out: list[dict[str, Any]] = []
        for record in envelope.get("prior_processing_history") or []:
            objects: list[dict[str, Any]] = []
            filename = str(record.get("history_file") or "")
            if filename:
                path = safe_path_under(self._class_change_history_dir(), safe_store_filename(filename))
                if path.is_file():
                    objects = [
                        json.loads(line)
                        for line in path.read_text(encoding="utf-8").splitlines()
                        if line.strip()
                    ]
            out.append({**deepcopy(record), "objects": objects})
        return out

    def _reextract_objects_for_klasse(
        self,
        envelope: dict[str, Any],
        new_class: str,
        freeze_bytes: bytes,
    ) -> list[dict[str, Any]]:
        freeze_path = self._source_cache_path(envelope)
        if review_path_for_klasse(new_class) == "boom":
            errors = boom_freeze_errors(
                data=freeze_bytes,
                filename=freeze_path.name,
                live_url=envelope.get("live_url") or "",
            )
            if errors:
                raise ConsoleError(errors[0])
            fragments, spec = self._fragments_and_spec(
                "boom",
                freeze_path,
                data=freeze_bytes,
                document_id=envelope["document_id"],
                source_id=envelope["source_id"],
                title=envelope["title"],
                family=envelope["family"],
                class_=new_class,
            )
            objects = transform_generic(spec, self._class_change_manifest(envelope), fragments)
            stamp_boom_flags(objects, fragments)
            return objects
        if envelope["content_kind"] == "boom":
            try:
                fragments = extract_boom_fragments(
                    freeze_bytes,
                    document_id=envelope["document_id"],
                    source_id=envelope["source_id"],
                )
            except ValueError as exc:
                raise ConsoleError("invalid_boom_freeze") from exc
            fragments = [
                {key: value for key, value in fragment.items() if key != "boom_kind"}
                for fragment in fragments
            ]
            spec = _spec_from_fragments(
                document_id=envelope["document_id"],
                title=envelope["title"],
                family=envelope["family"],
                class_=new_class,
                fragments=fragments,
                content_kind=envelope["content_kind"],
            )
            objects = transform_generic(spec, self._class_change_manifest(envelope), fragments)
            return apply_passage_register(
                apply_admission_gate(
                    objects,
                    klasse=new_class,
                    fragments=fragments,
                    document_version=envelope["version"],
                    source_hash=envelope["sha256"],
                )
            )
        fragments, spec = self._fragments_and_spec(
            envelope["content_kind"],
            freeze_path,
            data=freeze_bytes,
            document_id=envelope["document_id"],
            source_id=envelope["source_id"],
            title=envelope["title"],
            family=envelope["family"],
            class_=new_class,
            formation_context={"retained_fragments": self._read_source_fragments(envelope, freeze_path)}
                              if envelope["content_kind"] == "pdf" else None,
        )
        objects = transform_generic(spec, self._class_change_manifest(envelope), fragments)
        return apply_passage_register(
            apply_admission_gate(
                objects,
                klasse=new_class,
                fragments=fragments,
                document_version=envelope["version"],
                source_hash=envelope["sha256"],
            )
        )

    def promote_class(
        self,
        *,
        actor_id: str,
        snapshot_id: str,
        new_class: str,
        reextract: bool = False,
    ) -> dict[str, Any]:
        account = self._require_role(actor_id, "reviewer")
        if new_class not in ALLOWED_CLASSES:
            raise ConsoleError("invalid_class")
        live = self._envelope(snapshot_id)
        if self.snapshot_is_published(snapshot_id):
            raise ConsoleError("published_class_change_blocked")
        from_class = live["class"]
        if new_class == from_class:
            raise ConsoleError("class_unchanged")
        if live.get("decision_graph") and is_cross_model_class_change(from_class, new_class):
            raise ConsoleError("decision_graph_class_change_requires_successor")
        identity_before = source_identity_fields(live)
        original_rows, expected_revision = self.snapshot_objects_and_revision(snapshot_id, include_blocked=True)
        _, freeze_bytes = self._verified_source_bytes(live)
        envelope = deepcopy(live)
        new_envelopes = deepcopy(self._envelopes)
        new_bindings = deepcopy(self._bindings)
        if is_cross_model_class_change(from_class, new_class):
            if any(knowledge_revision(row) for row in original_rows):
                raise ConsoleError("knowledge_class_change_requires_successor")
            if not reextract:
                raise ConsoleError("cross_model_direct_change_blocked")
            prior = deepcopy(original_rows)
            processing_started = quality_instant()
            new_objects = self._reextract_objects_for_klasse(envelope, new_class, freeze_bytes)
            record_processing(envelope, new_objects, fragments=[], replay=None,
                              started_at=processing_started)
            with self._store_write_lock():
                self._reload_store_locked()
                self._require_role(actor_id, "reviewer")
                self._assert_source_work_unchanged(live, expected_revision, "published_class_change_blocked")
                archived = self._archive_prior_objects(
                    snapshot_id=snapshot_id,
                    rows=prior,
                    from_class=from_class,
                    to_class=new_class,
                )
                envelope["class"] = new_class
                envelope["clinical_rereview_required"] = True
                envelope["review_passes"] = {}
                envelope["state"] = CAPTURED
                history = list(envelope.get("prior_processing_history") or [])
                history.append(archived)
                envelope["prior_processing_history"] = history
                self._full_rereview_rows(new_objects)
                new_envelopes[snapshot_id] = envelope
                new_bindings[snapshot_id] = []
                self._commit_prepared_store(
                    objects=(snapshot_id, new_objects),
                    envelopes=new_envelopes,
                    bindings=new_bindings,
                    expected_revision=expected_revision,
                    ledger_fn=lambda: self._record_class_change_event(
                        account=account,
                        envelope=envelope,
                        from_class=from_class,
                        to_class=new_class,
                        model="cross_model",
                    ),
                )
            receipt = self._receipt(envelope)
            if source_identity_fields(receipt) != identity_before:
                raise ConsoleError("source_identity_must_not_change")
            return receipt
        rows = deepcopy(original_rows)
        envelope["class"] = new_class
        envelope["clinical_rereview_required"] = True
        envelope["review_passes"] = {}
        self._full_rereview_rows(rows)
        new_envelopes[snapshot_id] = envelope
        new_bindings[snapshot_id] = invalidate_for_object(new_bindings.get(snapshot_id, []), "")
        new_bindings[snapshot_id] = [{**row, "valid": False} for row in new_bindings.get(snapshot_id, [])]
        with self._store_write_lock():
            self._reload_store_locked()
            self._require_role(actor_id, "reviewer")
            self._assert_source_work_unchanged(live, expected_revision, "published_class_change_blocked")
            self._commit_prepared_store(
                objects=(snapshot_id, rows),
                envelopes=new_envelopes,
                bindings=new_bindings,
                expected_revision=expected_revision,
                ledger_fn=lambda: self._record_class_change_event(
                    account=account,
                    envelope=envelope,
                    from_class=from_class,
                    to_class=new_class,
                    model="same_model",
                ),
            )
        receipt = self._receipt(envelope)
        if source_identity_fields(receipt) != identity_before:
            raise ConsoleError("source_identity_must_not_change")
        return receipt

    def next_review_object_id(self, snapshot_id: str, object_id: str) -> str:
        envelope = self._envelope(snapshot_id)
        review_path = review_path_for_klasse(envelope["class"])
        return next_ordinary_object_id(
            self.snapshot_objects(snapshot_id),
            object_id,
            review_path=review_path,
            bindings=self.object_review_bindings(snapshot_id),
            fragments=self.review_source_fragments(snapshot_id),
        )

    @contextmanager
    def _atomic_snapshot_mutation(self, snapshot_id: str) -> Iterator[None]:
        """Rollback object/binding/envelope writes together with ledger evidence."""
        with self._store_write_lock():
            self._reload_store_locked()
            self._require_mutable_working_revision(snapshot_id)
            path = self._objects_path(snapshot_id)
            prior_objects = path.read_bytes() if path.exists() else None
            prior_envelopes = deepcopy(self._envelopes)
            prior_bindings = deepcopy(self._bindings)
            prior_ledger = self._ledger_path.stat().st_size if self._ledger_path.exists() else 0
            try:
                yield
            except Exception as exc:
                if isinstance(exc, ConsoleError) and exc.code == SNAPSHOT_OBJECT_WRITE_CONFLICT:
                    # Prepared review made no writes. Preserve the competing winner.
                    self.refresh_objects_expected_revision(snapshot_id)
                    raise
                self._rollback_store_files(
                    objects_snapshot=(snapshot_id, prior_objects),
                    envelopes=prior_envelopes,
                    bindings=prior_bindings,
                    ledger_size=prior_ledger,
                )
                self._envelopes = prior_envelopes
                self._bindings = prior_bindings
                self.refresh_objects_expected_revision(snapshot_id)
                raise


    def review_object(
        self,
        *,
        actor_id: str,
        snapshot_id: str,
        object_id: str,
        decision: str = "",
        comment: str | None = None,
        proposed_correction: str | None = None,
        confirmed_object_type: str | None = None,
        recommendation_strength: str | None = None,
        recommendation_direction: str | None = None,
        recommendation_strength_level: str | None = None,
        relation_choices: Iterable[str] | None = None,
        relation_review_ack: bool = False,
        suitability: str | None = None,
        eindoordeel: str | None = None,
        documentpositie_action: str | None = None,
        found_under: str | None = None,
        parent_choice: str | None = None,
        type_action: str | None = None,
        expected_revision: str | None = None,
        interaction_evidence: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        with self._atomic_snapshot_mutation(snapshot_id):
            reviewer = self._require_role(actor_id, "reviewer")
            if _is_forbidden_identity(reviewer["username"]) or _is_forbidden_identity(reviewer["display_name"]):
                raise ConsoleError("forbidden_reviewer_identity")
            envelope = self._envelope(snapshot_id)
            if actor_id not in envelope["named_reviewers"]:
                raise ConsoleError("reviewer_not_named_on_snapshot")
            if interaction_evidence is not None:
                try:
                    validate_review_interaction_identity(
                        interaction_evidence,
                        read_events(self._ledger_path),
                    )
                except ValueError as exc:
                    raise ConsoleError(str(exc)) from exc
            mapped = map_eindoordeel(eindoordeel or "", decision)
            if mapped:
                decision = mapped
            if decision in {"revise", "reject"} and not str(comment or "").strip():
                raise ConsoleError("review_comment_required")
            rejecting = decision == "reject"
            if rejecting:
                confirmed_object_type = None
                recommendation_strength = None
                recommendation_direction = None
                recommendation_strength_level = None
                relation_choices = None
            current = self.snapshot_objects(snapshot_id, for_update=True)
            target = next((row for row in current if row["object_id"] == object_id), None)
            if target is None:
                raise ConsoleError("unknown_object")
            current_revision = self.objects_revision(snapshot_id)
            if expected_revision is not None:
                if current_revision != expected_revision:
                    raise ConsoleError(SNAPSHOT_OBJECT_WRITE_CONFLICT, current_revision=current_revision)
            from src.review_policy_v1 import object_policy
            policy = object_policy(target)
            if policy != envelope.get("review_policy"):
                raise ConsoleError("review_policy_projection_mismatch")
            if policy is not None and decision == "approve" and actor_id != policy["primary"]:
                raise ConsoleError("primary_review_required")
            quality_before = deepcopy(target)
            from src.source_context_review_v1 import role_of
            if decision == "approve" and role_of(target):
                raise ConsoleError("source_context_not_knowledge")
            if not rejecting and type_action == "dit_klopt" and not confirmed_object_type:
                confirmed_object_type = confirmable_proposed_type(target) or None
            parent_id = ""
            if not rejecting:
                parent_id = (parent_choice or "").strip()
                if not parent_id and documentpositie_action == "dit_klopt":
                    parent_id = resolve_found_under_parent(target, current)
            store_passage = review_passage_requested(
                suitability=suitability or "",
                eindoordeel=eindoordeel or "",
                type_action=type_action or "",
                documentpositie_action=documentpositie_action or "",
                found_under=found_under or "",
                parent_choice=parent_choice or "",
            )
            path_text = (found_under or "").strip()
            if store_passage and not path_text:
                path_text = found_under_path(target)
            if (eindoordeel or "").strip() and (suitability or "").strip() not in SUITABILITY_VALUES:
                raise ConsoleError("suitability_required")
            if decision not in {"approve", "revise", "reject", "later"}:
                raise ConsoleError("invalid_review_decision")
            confirmed = confirmed_object_type
            if not confirmed and target.get("confirmed_object_type"):
                confirmed = target["confirmed_object_type"]
            apply_type = bool(confirmed_object_type)
            review_path = review_path_for_klasse(envelope["class"])
            binding_authority = self.object_review_bindings(snapshot_id)
            from src.knowledge_path_v1 import content_reviewable, is_structural_projection
            from src.source_accountability_v1 import is_source_record
            source_fragments = None
            if review_path != "boom" and content_reviewable(target):
                source_fragments = self._require_resolved_candidate_source(envelope, target)
            from src.integrity_kernel import stable_hash
            relation_choices = tuple(relation_choices or ())
            command_hash = stable_hash({
                "decision": decision, "confirmed_object_type": confirmed_object_type,
                "recommendation_strength": recommendation_strength,
                "recommendation_direction": recommendation_direction,
                "recommendation_strength_level": recommendation_strength_level,
                "relation_choices": sorted(relation_choices or ()), "relation_review_ack": relation_review_ack,
                "suitability": suitability, "eindoordeel": eindoordeel,
                "documentpositie_action": documentpositie_action, "found_under": found_under,
                "parent_choice": parent_choice, "type_action": type_action,
                "comment": comment, "proposed_correction": proposed_correction,
            })
            current_duty = review_duty_for(target, review_path=review_path,
                                          bindings=binding_authority, fragments=source_fragments)
            route = reviewer_route_for(target, review_path=review_path, reviewer_id=actor_id,
                                       bindings=binding_authority, fragments=source_fragments)
            if review_path != "boom" and decision == "approve" and not current_duty:
                if any(
                    row.get("reviewer_id") == actor_id and row.get("decision") == "approve"
                    and row.get("review_command_hash") == command_hash and still_matches(row, target)
                    for row in binding_authority
                ):
                    # An exact semantic duplicate has no transition, audit or additional authority.
                    return deepcopy(current)
            review_domain = "content"
            if review_path != "boom":
                if is_structural_projection(target):
                    review_domain = "structure"
                    if decision == "approve" and not (
                        _STRUCTURE_CONFIRMATION.get() and str(confirmed_object_type or "") == "heading"
                    ):
                        raise ConsoleError("structure_confirmation_command_required")
                elif is_source_record(target):
                    review_domain = "source_disposition"
                    if decision == "approve" or apply_type:
                        raise ConsoleError("source_context_not_knowledge")
                elif not content_reviewable(target):
                    review_domain = "technical_repair"
                if decision == "approve" and review_domain != "structure":
                    if is_admission_blocked(target, review_path=review_path):
                        raise ConsoleError("blocked_candidate_not_reviewable")
                    if not current_duty:
                        raise ConsoleError("content_duty_required")
                if review_domain == "content" and (
                    not current_duty or not route or not route.get("actionable")
                ):
                    raise ConsoleError("content_duty_required")
            if (current_duty and current_duty.get("stage") == SECOND_REVIEW
                    and decision != "revise"):
                raise ConsoleError("second_review_command_required")
            if decision == "approve" or apply_type:
                if review_path != "boom" and content_reviewable(target):
                    self._require_resolved_candidate_source(envelope, target)
            if decision != "later":
                from src.source_accountability_v1 import is_source_record
                if is_source_record(target) and (decision == "approve" or apply_type):
                    raise ConsoleError("source_context_not_knowledge")
                if is_admission_blocked(target, review_path=review_path) and (
                    decision == "approve" or apply_type
                ):
                    raise ConsoleError("blocked_candidate_not_reviewable")
                if decision == "approve" or apply_type:
                    self._require_open_original(snapshot_id, object_id)
                if decision == "approve":
                    if not is_confirmable_type_for_path(confirmed, review_path):
                        raise ConsoleError("unknown_object_type")
                    apply_type = True
                if apply_type and confirmed and not is_confirmable_type_for_path(confirmed, review_path):
                    raise ConsoleError("unknown_object_type")
                if decision == "approve" and confirmed == "outcome":
                    errors = outcome_review_errors(target, peers=current)
                    if errors:
                        raise ConsoleError("outcome_review_failed", ",".join(errors))
                stamp_type = confirmed or target.get("confirmed_object_type") or target.get("object_type")
                strength_preview = (recommendation_strength or "").strip() or None
                direction_preview = (recommendation_direction or "").strip() or None
                strength_level_preview = (recommendation_strength_level or "").strip() or None
                has_new_recommendation_semantics = bool(
                    proposed_recommendation_semantics_of(target)
                    or confirmed_recommendation_semantics_of(target)
                    or direction_preview
                    or strength_level_preview
                )
                new_recommendation_semantics_mode = (
                    review_path != "boom"
                    and stamp_type == "recommendation"
                    and has_new_recommendation_semantics
                )
                if decision == "approve" and new_recommendation_semantics_mode:
                    existing_semantics = confirmed_recommendation_semantics_of(target)
                    effective_direction = direction_preview or str(existing_semantics.get("direction") or "")
                    if strength_level_preview:
                        effective_strength_level = strength_level_preview
                    elif existing_semantics.get("strength_status") == "not_stated":
                        effective_strength_level = "not_stated"
                    else:
                        effective_strength_level = str(existing_semantics.get("strength") or "")
                    try:
                        confirmed_recommendation_semantics_from_review(
                            target,
                            direction=effective_direction,
                            strength_choice=effective_strength_level,
                        )
                    except ValueError as exc:
                        raise ConsoleError(str(exc)) from exc
                    if strength_preview:
                        raise ConsoleError("legacy_recommendation_strength_not_allowed")
                if decision == "approve" and stamp_type == "outcome":
                    effective = strength_preview or target.get("confirmed_recommendation_strength")
                    if not effective and not is_geen_actie_outcome(
                        str((target.get("content") or {}).get("clean_text") or "")
                    ):
                        raise ConsoleError("outcome_strength_required")
                if strength_preview:
                    legacy_strength_allowed = (
                        stamp_type == "outcome"
                        or (stamp_type == "recommendation" and not new_recommendation_semantics_mode)
                    )
                    if legacy_strength_allowed:
                        if not is_closed_recommendation_strength(strength_preview):
                            raise ConsoleError("unknown_recommendation_strength")
                    else:
                        will_clear = apply_type and confirmed and target.get(
                            "confirmed_recommendation_strength"
                        )
                        if not will_clear:
                            raise ConsoleError("recommendation_strength_requires_recommendation")
            d4_relation_review = (
                decision == "approve"
                and review_path != "boom"
                and has_semantic_relation_review(target)
            )
            relation_plan: dict[str, Any] | None = None
            if d4_relation_review:
                if not relation_review_ack:
                    raise ConsoleError("knowledge_relation_review_required")
                try:
                    relation_plan = plan_semantic_relation_review(
                        target,
                        objects=current,
                        selected_choices=list(relation_choices or []),
                        source_type=str(
                            confirmed
                            or target.get("confirmed_object_type")
                            or target.get("proposed_object_type")
                            or target.get("object_type")
                            or ""
                        ),
                    )
                except ValueError as exc:
                    raise ConsoleError(str(exc)) from exc
            relation_history = None
            relation_bindings = None
            if parent_id and parent_id != object_id and not d4_relation_review:
                target, relation_history, relation_bindings = self._prepare_relation_confirmation(
                    snapshot_id=snapshot_id, object_id=object_id, current=current, actor=reviewer["username"],
                    relations=merge_heading_parent_relations(target.get("confirmed_relations"), parent_id))
                current = list({row["object_id"]: row for row in relation_history}.values())
            passage = (
                review_passage_record(
                    suitability=suitability or "",
                    eindoordeel=eindoordeel or "",
                    type_action=type_action or "",
                    documentpositie_action=documentpositie_action or "",
                    found_under=path_text,
                    parent_object_id=parent_id,
                )
                if store_passage
                else None
            )
            if decision == "later":
                saved = deepcopy(target)
                if passage:
                    metadata = saved.setdefault("metadata", {})
                    metadata["review_passage"] = passage
                    saved = apply_register_from_review(saved, suitability=suitability or "")
                saved = self._prepare_knowledge_revision(snapshot_id, target, saved,
                    reason="review context change", actor=reviewer["username"])
                history = [
                    row
                    for row in (relation_history if relation_history is not None else self._load_objects(snapshot_id))
                    if not (row["object_id"] == object_id and row["object_version"] == saved["object_version"])
                ]
                history.append(saved)
                self._commit_prepared_store(objects=(snapshot_id, history), bindings=relation_bindings,
                    expected_revision=current_revision, snapshot_id=snapshot_id)
                return deepcopy(self.snapshot_objects(snapshot_id))
            target = deepcopy(target)
            revision_predecessor = deepcopy(target)
            review_semantics_base_version = str(target.get("object_version") or "1.0")
            if apply_type and confirmed:
                if not is_confirmable_type_for_path(confirmed, review_path):
                    raise ConsoleError("unknown_object_type")
                if target.get("object_type") != "document":
                    if target.get("confirmed_object_type") != confirmed:
                        target["object_version"] = bump_patch(str(target.get("object_version") or "1.0"))
                    target["confirmed_object_type"] = confirmed
                    target["object_type"] = confirmed
                    if confirmed != "recommendation":
                        target.pop(CONFIRMED_RECOMMENDATION_SEMANTICS_FIELD, None)
                    mark_four_eyes_on_object(target, confirmed_type=confirmed)
                    stamp_canonical_hashes(target)
            if decision == "approve" and confirmed == "outcome":
                errors = outcome_review_errors(target, peers=current)
                if errors:
                    raise ConsoleError("outcome_review_failed", ",".join(errors))
            strength = (recommendation_strength or "").strip() or None
            stamp_type = confirmed or target.get("confirmed_object_type") or target.get("object_type")
            direction_choice = (recommendation_direction or "").strip()
            strength_level_choice = (recommendation_strength_level or "").strip()
            has_new_recommendation_semantics = bool(
                proposed_recommendation_semantics_of(target)
                or confirmed_recommendation_semantics_of(target)
                or direction_choice
                or strength_level_choice
            )
            new_recommendation_semantics_mode = (
                review_path != "boom"
                and stamp_type == "recommendation"
                and has_new_recommendation_semantics
            )
            confirmed_semantics: dict[str, Any] | None = None
            if decision == "approve" and new_recommendation_semantics_mode:
                existing_semantics = confirmed_recommendation_semantics_of(target)
                effective_direction = direction_choice or str(existing_semantics.get("direction") or "")
                if strength_level_choice:
                    effective_strength_level = strength_level_choice
                elif existing_semantics.get("strength_status") == "not_stated":
                    effective_strength_level = "not_stated"
                else:
                    effective_strength_level = str(existing_semantics.get("strength") or "")
                try:
                    confirmed_semantics = confirmed_recommendation_semantics_from_review(
                        target,
                        direction=effective_direction,
                        strength_choice=effective_strength_level,
                    )
                except ValueError as exc:
                    raise ConsoleError(str(exc)) from exc
                if target.get(CONFIRMED_RECOMMENDATION_SEMANTICS_FIELD) != confirmed_semantics:
                    if str(target.get("object_version") or "1.0") == review_semantics_base_version:
                        target["object_version"] = bump_patch(review_semantics_base_version)
                    target[CONFIRMED_RECOMMENDATION_SEMANTICS_FIELD] = confirmed_semantics
                target.pop(LEGACY_CONFIRMED_RECOMMENDATION_STRENGTH_FIELD, None)
                strength = None
                stamp_canonical_hashes(target)
            elif apply_type and confirmed != "recommendation":
                if target.get(CONFIRMED_RECOMMENDATION_SEMANTICS_FIELD):
                    if str(target.get("object_version") or "1.0") == review_semantics_base_version:
                        target["object_version"] = bump_patch(review_semantics_base_version)
                    target.pop(CONFIRMED_RECOMMENDATION_SEMANTICS_FIELD, None)
                    stamp_canonical_hashes(target)

            strength_allowed = (
                stamp_type == "outcome"
                or (stamp_type == "recommendation" and not new_recommendation_semantics_mode)
            )
            previous_strength = target.get("confirmed_recommendation_strength")
            if apply_type and confirmed and not strength_allowed and previous_strength:
                target.pop("confirmed_recommendation_strength", None)
                strength = None
                stamp_canonical_hashes(target)
            if not strength and decision == "approve" and stamp_type == "outcome":
                text = str((target.get("content") or {}).get("clean_text") or "")
                if is_geen_actie_outcome(text):
                    mapped = map_geen_actie(text)
                    strength = mapped["strength"]
                    target["no_action"] = True
                    metadata = target.setdefault("metadata", {})
                    metadata["no_action"] = True
            if decision == "approve" and stamp_type == "outcome":
                effective = strength or target.get("confirmed_recommendation_strength")
                if not effective:
                    raise ConsoleError("outcome_strength_required")
            if strength:
                if stamp_type not in {"recommendation", "outcome"}:
                    raise ConsoleError("recommendation_strength_requires_recommendation")
                if not is_closed_recommendation_strength(strength):
                    raise ConsoleError("unknown_recommendation_strength")
                if target.get("confirmed_recommendation_strength") != strength:
                    if not apply_type:
                        target["object_version"] = bump_patch(str(target.get("object_version") or "1.0"))
                    target["confirmed_recommendation_strength"] = strength
                    stamp_canonical_hashes(target)
            confirmed_relation_set: list[dict[str, Any]] | None = None
            if d4_relation_review and relation_plan is not None:
                structural: list[dict[str, Any]] = []
                if parent_id and parent_id != object_id:
                    parent = next(
                        (row for row in current if row.get("object_id") == parent_id),
                        None,
                    )
                    if parent is None:
                        raise ConsoleError("knowledge_relation_target_missing")
                    structural.append(
                        {
                            "relation_type": "child",
                            "target_object_id": parent_id,
                            "target_object_version": str(parent.get("object_version") or ""),
                        }
                    )
                else:
                    for row in confirmed_knowledge_relations_of(target):
                        if str(row.get("relation_type") or "") in STRUCTURAL_RELATION_TYPES:
                            peer = next(
                                (
                                    item
                                    for item in current
                                    if item.get("object_id") == row.get("target_object_id")
                                ),
                                None,
                            )
                            if peer is None or str(peer.get("object_version") or "") != str(
                                row.get("target_object_version") or ""
                            ):
                                raise ConsoleError("knowledge_relation_target_stale")
                            structural.append(row)
                    if not structural and target.get("parent_object_id"):
                        existing_parent_id = str(target.get("parent_object_id") or "")
                        peer = next(
                            (
                                item
                                for item in current
                                if item.get("object_id") == existing_parent_id
                            ),
                            None,
                        )
                        if peer is None:
                            raise ConsoleError("knowledge_relation_target_missing")
                        structural.append(
                            {
                                "relation_type": "child",
                                "target_object_id": existing_parent_id,
                                "target_object_version": str(peer.get("object_version") or ""),
                            }
                        )

                relation_state_change = bool(relation_plan.get("state_change_required"))
                desired_parent = (
                    parent_id
                    if parent_id
                    else str(target.get("parent_object_id") or "") or None
                )
                parent_state_change = target.get("parent_object_id") != desired_parent
                relation_mutation = relation_state_change or parent_state_change
                if (
                    relation_mutation
                    and str(target.get("object_version") or "1.0")
                    == review_semantics_base_version
                ):
                    target["object_version"] = bump_patch(review_semantics_base_version)
                final_source_version = str(target.get("object_version") or "1.0")
                try:
                    confirmed_relation_set = build_confirmed_relation_set(
                        relation_plan,
                        final_source_version=final_source_version,
                        structural_relations=structural,
                    )
                except ValueError as exc:
                    raise ConsoleError(str(exc)) from exc
                target[CONFIRMED_KNOWLEDGE_RELATIONS_FIELD] = confirmed_relation_set
                target["confirmed_relations"] = legacy_confirmed_mirror(
                    confirmed_relation_set
                )
                target["parent_object_id"] = desired_parent
                target.pop(PROPOSED_KNOWLEDGE_RELATIONS_FIELD, None)
                if relation_mutation:
                    metadata = target.setdefault("metadata", {})
                    metadata["knowledge_relation_review"] = relation_review_evidence(
                        relation_plan,
                        confirmed_relations=confirmed_relation_set,
                        reviewer_id=actor_id,
                        reviewer_username=reviewer["username"],
                        reviewed_at=utc_now(),
                        source_version_after=final_source_version,
                    )
                stamp_canonical_hashes(target)

            if passage:
                target.setdefault("metadata", {})["review_passage"] = dict(passage)
                target = apply_register_from_review(target, suitability=(
                    "geen_kenniseenheid" if rejecting else suitability or ""))
            target = self._prepare_knowledge_revision(snapshot_id, revision_predecessor, target,
                reason="review semantic confirmation/change", actor=reviewer["username"])
            if confirmed_relation_set is not None:
                confirmed_relation_set = deepcopy(target.get(CONFIRMED_KNOWLEDGE_RELATIONS_FIELD) or [])
            current = [target if row["object_id"] == object_id else row for row in current]
            track = target["governance"]["review_track"]
            payload = {
                "object_id": object_id,
                "decision": decision,
                "reviewer": reviewer["username"],
                "review_date": date.today().isoformat(),
                "reviewed_canonical_object_hash": compute_canonical_object_hash(target),
                "comment": comment or "",
                "proposed_correction": proposed_correction or "",
            }
            if interaction_evidence is not None and decision != "later":
                payload["review_interaction"] = deepcopy(interaction_evidence)
            interaction_atomic = interaction_evidence is not None and decision != "later"
            updated, report = _apply_review_state(
                current,
                [payload],
                track=track,
                schema_path=self.schema_path,
                ledger_path=None,
            )
            if report["errors"]:
                raise ConsoleError("review_failed", json.dumps(report["errors"], ensure_ascii=False))
            history = [
                row
                for row in (relation_history if relation_history is not None else self._load_objects(snapshot_id))
                if not (row["object_id"] == object_id and row["object_version"] == target["object_version"])
            ]
            updated_target = next(row for row in updated if row["object_id"] == object_id)
            passage_meta = dict(passage) if passage else {}
            if passage_meta:
                metadata = updated_target.setdefault("metadata", {})
                metadata["review_passage"] = passage_meta
                updated_target = apply_register_from_review(
                    updated_target,
                    suitability=(
                        "geen_kenniseenheid"
                        if rejecting
                        else suitability or ""
                    ),
                )
            if confirmed and updated_target.get("object_type") != "document":
                updated_target["confirmed_object_type"] = confirmed
                updated_target["object_type"] = confirmed
                mark_four_eyes_on_object(updated_target, confirmed_type=confirmed)
                stamp_canonical_hashes(updated_target)
            if target.get("confirmed_relations"):
                updated_target["confirmed_relations"] = target["confirmed_relations"]
            elif d4_relation_review:
                updated_target["confirmed_relations"] = []
            if confirmed_relation_set is not None:
                updated_target[CONFIRMED_KNOWLEDGE_RELATIONS_FIELD] = deepcopy(
                    confirmed_relation_set
                )
                updated_target.pop(PROPOSED_KNOWLEDGE_RELATIONS_FIELD, None)
                updated_target["parent_object_id"] = target.get("parent_object_id")
                relation_review = (target.get("metadata") or {}).get(
                    "knowledge_relation_review"
                )
                if isinstance(relation_review, dict):
                    metadata = updated_target.setdefault("metadata", {})
                    metadata["knowledge_relation_review"] = deepcopy(relation_review)
                stamp_canonical_hashes(updated_target)
            if confirmed_semantics is not None:
                updated_target[CONFIRMED_RECOMMENDATION_SEMANTICS_FIELD] = confirmed_semantics
                updated_target.pop(LEGACY_CONFIRMED_RECOMMENDATION_STRENGTH_FIELD, None)
                stamp_canonical_hashes(updated_target)
            elif apply_type and confirmed and confirmed != "recommendation":
                updated_target.pop(CONFIRMED_RECOMMENDATION_SEMANTICS_FIELD, None)
                stamp_canonical_hashes(updated_target)
            if strength:
                updated_target["confirmed_recommendation_strength"] = strength
                stamp_canonical_hashes(updated_target)
            elif apply_type and confirmed and confirmed not in {"recommendation", "outcome"}:
                updated_target.pop("confirmed_recommendation_strength", None)
                stamp_canonical_hashes(updated_target)
            if target.get("no_action"):
                updated_target["no_action"] = True
                metadata = updated_target.setdefault("metadata", {})
                metadata["no_action"] = True
                stamp_canonical_hashes(updated_target)
            updated_target["governance"]["review_snapshot_hash"] = compute_canonical_object_hash(updated_target)
            history.append(updated_target)
            new_envelopes = None
            new_bindings = deepcopy(relation_bindings if relation_bindings is not None else self._bindings)
            if decision == "approve":
                new_envelopes = deepcopy(self._envelopes)
                new_envelopes[snapshot_id] = deepcopy(envelope)
                new_envelopes[snapshot_id]["review_passes"] = dict(
                    new_envelopes[snapshot_id].get("review_passes") or {}
                )
                new_envelopes[snapshot_id]["review_passes"][actor_id] = {
                    "passed": True,
                    "at": utc_now(),
                    "object_id": object_id,
                }
                binding = tuple_record(
                    object_id=object_id,
                    object_version=updated_target["object_version"],
                    canonical_object_hash=compute_canonical_object_hash(updated_target),
                    confirmed_object_type=updated_target.get("confirmed_object_type"),
                    reviewer=reviewer["username"],
                    reviewer_id=actor_id,
                    decision=decision,
                )
                binding["review_domain"] = review_domain if review_path != "boom" else "decision_tree"
                binding["reviewed_at"] = utc_now()
                binding["review_command_hash"] = command_hash
                if passage_meta:
                    binding["suitability"] = passage_meta.get("suitability")
                    binding["eindoordeel"] = passage_meta.get("eindoordeel")
                    binding["documentpositie"] = passage_meta.get("documentpositie")
                # Retain historical exact tuples. Current authority matches only this tuple.
                rows = record_authorization(new_bindings.get(snapshot_id, []), binding)
                new_bindings[snapshot_id] = rows
            else:
                new_bindings[snapshot_id] = invalidate_for_object(
                    new_bindings.get(snapshot_id, []),
                    object_id,
                )
            ledger_fn = None
            if decision != "later":
                ledger_details = {
                    "review_snapshot_hash": compute_canonical_object_hash(updated_target),
                    "comment": str(comment or ""),
                    "proposed_correction": str(proposed_correction or ""),
                    "snapshot_id": snapshot_id,
                    "review_interaction": deepcopy(interaction_evidence),
                    "reviewer_id": actor_id,
                    "confirmed_object_type": updated_target.get("confirmed_object_type"),
                    "review_domain": review_domain,
                    "quality_evidence": review_evidence(envelope, quality_before, updated_target),
                }
                ledger_fn = lambda: append_event(
                    self._ledger_path,
                    event_type=(f"{track}_review_{decision}" if review_domain == "content"
                                else f"{review_domain}_{decision}"),
                    object_id=object_id,
                    object_version=str(updated_target.get("object_version") or ""),
                    actor=reviewer["username"],
                    details=ledger_details,
                )
            self._commit_prepared_store(
                objects=(snapshot_id, history),
                envelopes=new_envelopes,
                bindings=new_bindings,
                expected_revision=current_revision,
                snapshot_id=snapshot_id,
                ledger_fn=ledger_fn,
            )
            return deepcopy(updated)

    def approve_second_review(
        self,
        *,
        actor_id: str,
        snapshot_id: str,
        object_id: str,
        expected_revision: str | None = None,
        interaction_evidence: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Approve one exact current tuple as the independent second reviewer.

        This mutation does not change canonical knowledge content, object
        version or canonical hash. It only adds the second exact review
        authorization and updates the compatibility second_review mirror plus
        audit evidence in the same store transaction.
        """

        with self._atomic_snapshot_mutation(snapshot_id):
            reviewer = self._require_role(actor_id, "reviewer")
            if _is_forbidden_identity(reviewer["username"]) or _is_forbidden_identity(reviewer["display_name"]):
                raise ConsoleError("forbidden_reviewer_identity")
            envelope = self._envelope(snapshot_id)
            if actor_id not in set(envelope.get("named_reviewers") or []):
                raise ConsoleError("reviewer_not_named_on_snapshot")
            if interaction_evidence is not None:
                try:
                    validate_review_interaction_identity(
                        interaction_evidence,
                        read_events(self._ledger_path),
                    )
                except ValueError as exc:
                    raise ConsoleError(str(exc)) from exc

            objects, revision = self.snapshot_objects_and_revision(snapshot_id)
            if expected_revision is not None and revision != expected_revision:
                raise ConsoleError(
                    SNAPSHOT_OBJECT_WRITE_CONFLICT,
                    current_revision=revision,
                )
            target = next((row for row in objects if row.get("object_id") == object_id), None)
            if target is None:
                raise ConsoleError("unknown_object")
            review_path = review_path_for_klasse(envelope["class"])
            source_fragments = None
            if review_path != "boom":
                from src.knowledge_path_v1 import content_reviewable
                if not content_reviewable(target):
                    raise ConsoleError("content_duty_required")
                source_fragments = self._require_resolved_candidate_source(envelope, target)
            from src.review_policy_v1 import object_policy, required_reviewers
            policy = object_policy(target)
            if policy != envelope.get("review_policy"):
                raise ConsoleError("review_policy_projection_mismatch")
            if policy is None and not requires_four_eyes(
                target,
                confirmed_type=str(target.get("confirmed_object_type") or "") or None,
            ):
                raise ConsoleError("second_review_not_required")

            bindings = self.object_review_bindings(snapshot_id)
            approvers = exact_current_approver_ids(target, bindings)
            if policy is not None:
                if policy["primary"] not in approvers:
                    raise ConsoleError("first_review_required")
                if actor_id in approvers:
                    return deepcopy(target)
            elif len(approvers) >= 2:
                return deepcopy(target)
            if not approvers:
                raise ConsoleError("first_review_required")
            if actor_id in set(approvers):
                raise ConsoleError("independent_second_reviewer_required")
            if review_path != "boom":
                route = reviewer_route_for(target, review_path=review_path, reviewer_id=actor_id,
                                           bindings=bindings, fragments=source_fragments)
                if not route or route["stage"] != SECOND_REVIEW or not route["actionable"]:
                    raise ConsoleError("second_review_not_available")
            self._require_open_original(snapshot_id, object_id)

            canonical_hash = compute_canonical_object_hash(target)
            binding = tuple_record(
                object_id=object_id,
                object_version=str(target.get("object_version") or ""),
                canonical_object_hash=canonical_hash,
                confirmed_object_type=target.get("confirmed_object_type"),
                reviewer=reviewer["username"],
                reviewer_id=actor_id,
                decision="approve",
            )
            binding["review_domain"] = "content" if review_path != "boom" else "decision_tree"
            binding["reviewed_at"] = utc_now()
            new_bindings = deepcopy(self._bindings)
            rows = record_authorization(new_bindings.get(snapshot_id, []), binding)
            new_bindings[snapshot_id] = rows

            history = self._load_objects(snapshot_id)
            current_target = next(
                row for row in history
                if row.get("object_id") == object_id
                and row.get("object_version") == target.get("object_version")
            )
            governance = current_target.setdefault("governance", {})
            second = governance.setdefault("second_review", {})
            second.update(
                {
                    "required": True,
                    "status": "approved",
                    "reviewer": reviewer["username"],
                    "review_date": date.today().isoformat(),
                    "snapshot_hash": canonical_hash,
                }
            )

            self._commit_prepared_store(
                objects=(snapshot_id, history),
                bindings=new_bindings,
                expected_revision=revision,
                snapshot_id=snapshot_id,
                ledger_fn=lambda: append_event(
                    self._ledger_path,
                    event_type="second_review_approve",
                    object_id=object_id,
                    object_version=str(target.get("object_version") or ""),
                    actor=reviewer["username"],
                    details={
                        "snapshot_id": snapshot_id,
                        "canonical_object_hash": canonical_hash,
                        "confirmed_object_type": target.get("confirmed_object_type"),
                        "first_approver_ids": list(approvers),
                        "second_reviewer_id": actor_id,
                        **(
                            {
                                "review_interaction": deepcopy(interaction_evidence),
                            }
                            if interaction_evidence is not None
                            else {}
                        ),
                    },
                ),
            )
            return deepcopy(current_target)

    def confirm_source_context(self, **command: Any) -> dict[str, Any]:
        from src.source_context_review_v1 import confirm_source_context
        return confirm_source_context(self, **command)

    def batch_confirm_headings(
        self,
        *,
        actor_id: str,
        snapshot_id: str,
        object_ids: Iterable[str],
        expected_revision: str | None = None,
        interaction_evidence: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Fast-lane confirm of proposed headings as structure, not advice.

        MUST NOT bypass four-eyes when the object is high-risk or is later
        reclassified onto a high-risk type. Serving still requires confirmed
        closed types plus the published projection and G2 locator.
        """
        self._require_role(actor_id, "reviewer")
        ids = [str(object_id).strip() for object_id in object_ids if str(object_id).strip()]
        if not ids:
            raise ConsoleError("fast_lane_heading_required")
        review_path = review_path_for_klasse(self._envelope(snapshot_id)["class"])
        structure_type = "path" if review_path == "boom" else "heading"
        current = {row["object_id"]: row for row in self.snapshot_objects(snapshot_id)}
        bindings = self.object_review_bindings(snapshot_id)
        for object_id in ids:
            target = current.get(object_id)
            if target is None:
                raise ConsoleError("unknown_object")
            if review_path == "boom":
                route = reviewer_route_for(
                    target,
                    review_path=review_path,
                    reviewer_id=actor_id,
                    bindings=bindings,
                )
                acceptable = bool(
                    route
                    and route.get("actionable")
                    and route.get("canonical_task") == "structure"
                )
            else:
                from src.knowledge_path_v1 import is_structural_projection
                acceptable = (
                    review_lane(target, review_path=review_path) == "fast"
                    and is_structural_projection(target)
                )
            if not acceptable:
                raise ConsoleError("fast_lane_heading_required")
        updated: list[dict[str, Any]] = []
        pin = expected_revision
        for object_id in ids:
            token = _STRUCTURE_CONFIRMATION.set(review_path != "boom")
            try:
                rows = self.review_object(
                    actor_id=actor_id,
                    snapshot_id=snapshot_id,
                    object_id=object_id,
                    decision="approve",
                    confirmed_object_type=structure_type,
                    expected_revision=pin,
                    interaction_evidence=interaction_evidence,
                )
            finally:
                _STRUCTURE_CONFIRMATION.reset(token)
            if pin is not None:
                pin = self.objects_revision(snapshot_id)
            refreshed = next(row for row in rows if row["object_id"] == object_id)
            mark_four_eyes_on_object(refreshed, confirmed_type="heading")
            stamp_canonical_hashes(refreshed)
            updated.append(deepcopy(refreshed))
        return updated

    def correct_object(
        self,
        *,
        actor_id: str,
        snapshot_id: str,
        object_id: str,
        patch: dict[str, Any],
        additional_source_fragments: list[dict[str, Any]] | None = None,
        materialisation_decision: dict[str, Any] | None = None,
        rereview_scope: str = "document",
        expected_revision: str | None = None,
    ) -> dict[str, Any]:
        account = self._account(actor_id)
        if "researcher" not in account["roles"] and "reviewer" not in account["roles"]:
            raise ConsoleError("correction_role_required")
        if rereview_scope not in {"document", "object"}:
            raise ConsoleError("unknown_rereview_scope")
        if self.snapshot_is_published(snapshot_id):
            raise ConsoleError("published_working_revision_immutable")
        if "researcher" not in account["roles"] and actor_id not in self._envelope(snapshot_id)["named_reviewers"]:
            raise ConsoleError("reviewer_not_named_on_snapshot")
        current, revision = self.snapshot_objects_and_revision(snapshot_id)
        if expected_revision is not None and expected_revision != revision:
            raise ConsoleError(SNAPSHOT_OBJECT_WRITE_CONFLICT, current_revision=revision)
        target = next((row for row in current if row["object_id"] == object_id), None)
        if target is None:
            raise ConsoleError("unknown_object")
        revised = create_revision(
            target,
            patch,
            actor=account["username"],
            schema_path=self.schema_path,
            ledger=None,
            snapshot_id=snapshot_id,
        )
        if additional_source_fragments:
            provenance = revised.setdefault("provenance", {})
            refs = list(provenance.get("source_fragments") or [])
            known = {str(ref.get("raw_object_id") or "") for ref in refs}
            for ref in additional_source_fragments:
                raw_id = str(ref.get("raw_object_id") or "")
                if raw_id and raw_id not in known:
                    refs.append(deepcopy(ref))
                    known.add(raw_id)
            provenance["source_fragments"] = refs
            stamp_canonical_hashes(revised)
            errors = schema_errors(revised, self.schema_path)
            if errors:
                raise ConsoleError("revision_schema_invalid", " | ".join(errors))
        if revised.get("object_type") not in {"document", "heading"}:
            revised["object_type"] = "unclassified"
        revised.pop("confirmed_object_type", None)
        stamp_canonical_hashes(revised)
        envelope = self._envelope(snapshot_id)
        if review_path_for_klasse(envelope["class"]) != "boom":
            source_path, _ = self._verified_source_bytes(envelope)
            fragments = self._read_source_fragments(envelope, source_path)
            if materialisation_decision is not None:
                from src.knowledge_materialisation_v1 import materialise_knowledge_candidates, MaterialisationError
                try:
                    materialised = materialise_knowledge_candidates(
                        [materialisation_decision], document_id=envelope["document_id"], fragments=fragments
                    )[0]
                except MaterialisationError as exc:
                    raise ConsoleError("pre_review_llm_proposal_rejected", exc.code) from exc
                if revised["content"]["clean_text"] != materialised["clean_text"]:
                    raise ConsoleError("materialisation_text_mismatch")
                semantic = revised.setdefault("metadata", {}).setdefault("semantic_passage", {})
                semantic["spans"] = materialised["semantic_passage"]["spans"]
                semantic["source_mapping"] = materialised["semantic_passage"]["source_mapping"]
                from src.semantic_transform_generic_v1 import _fragment_ref
                raw_by_id = {row["fragment_id"]: row for row in fragments}
                revised["provenance"]["source_fragments"] = [
                    deepcopy(_fragment_ref(raw_by_id[fragment_id]))
                    for fragment_id in materialised["source_fragment_ids"]
                ]
                stamp_canonical_hashes(revised)
            peers = [
                revised if row.get("object_id") == object_id else row
                for row in current
            ]
            gated = apply_admission_gate(
                peers,
                klasse=envelope["class"],
                fragments=fragments,
                document_version=envelope["version"],
                source_hash=envelope["sha256"],
            )
            revised = next(row for row in gated if row["object_id"] == object_id)
            revised = apply_passage_register([revised])[0]
        else:
            from src.decision_unit_construction_v1 import KEY, apply_gate, rebuild_for_revision
            if (target.get("metadata") or {}).get(KEY):
                from src.decision_graph_v1 import pdf_fragments
                source_path, _ = self._verified_source_bytes(envelope)
                fragments = self._read_source_fragments(envelope, source_path)
                try:
                    rebuild_for_revision(target, revised, fragments)
                except ValueError as exc:
                    raise ConsoleError(str(exc)) from exc
                stamp_canonical_hashes(revised)
            peers = [revised if row.get("object_id") == object_id else row for row in current]
            apply_gate(peers, source_hash=envelope["sha256"], graph=envelope.get("decision_graph"),
                       inventory=envelope.get("decision_graph_evidence"))
            revised = apply_passage_register([revised])[0]
        history = self._load_objects(snapshot_id)
        history.append(revised)
        new_envelopes: dict[str, Any] | None = None
        if rereview_scope == "document":
            new_envelopes = deepcopy(self._envelopes)
            new_envelope = deepcopy(envelope)
            new_envelope["review_passes"] = {}
            new_envelope["clinical_rereview_required"] = True
            new_envelopes[snapshot_id] = new_envelope
        new_bindings = deepcopy(self._bindings)
        new_bindings[snapshot_id] = invalidate_for_object(new_bindings.get(snapshot_id, []), object_id)
        def record_correction():
            append_event(self._ledger_path, event_type="revision_created", object_id=object_id,
                         object_version=revised["object_version"], actor=account["username"],
                         details={"previous_object_version": target["object_version"],
                                  "revision_patch_hash": revised["provenance"]["revision_patch_hash"],
                                  "reason": patch["reason"]})
            append_event(self._ledger_path, event_type="quality_object_corrected", object_id=object_id,
                         object_version=revised["object_version"], actor=account["username"],
                         details={"snapshot_id": snapshot_id,
                                  "quality_evidence": review_evidence(envelope, target, revised)})
        with self._store_write_lock():
            try:
                transaction = (self._reprocessing_transaction(snapshot_id)
                               if getattr(self, "workflow_document_store", None) is not None
                               else nullcontext())
                with transaction:
                    self._reload_store_locked()
                    self._assert_source_work_unchanged(envelope, revision, "published_working_revision_immutable")
                    current_actor = self._account(actor_id)
                    if not {"researcher", "reviewer"}.intersection(current_actor["roles"]):
                        raise ConsoleError("correction_role_required")
                    if "researcher" not in current_actor["roles"] and actor_id not in self._envelope(snapshot_id)["named_reviewers"]:
                        raise ConsoleError("reviewer_not_named_on_snapshot")
                    self._commit_prepared_store(
                        objects=(snapshot_id, history),
                        envelopes=new_envelopes,
                        bindings=new_bindings,
                        snapshot_id=snapshot_id,
                        expected_revision=revision,
                        ledger_fn=record_correction,
                    )
            except Exception:
                self._reload_store_locked()
                remirror = getattr(self, "_remirror_review_runtime", None)
                if remirror is not None:
                    remirror()
                raise
        return deepcopy(revised)

    def accept_source_continuation(
        self,
        *,
        actor_id: str,
        snapshot_id: str,
        object_id: str,
        expected_revision: str | None = None,
    ) -> dict[str, Any]:
        """Create a reviewable revision from one literal adjacent continuation."""
        reviewer = self._require_role(actor_id, "reviewer")
        envelope = self._envelope(snapshot_id)
        if actor_id not in envelope["named_reviewers"]:
            raise ConsoleError("reviewer_not_named_on_snapshot")
        current = self.snapshot_objects(snapshot_id, for_update=True)
        index = next((i for i, row in enumerate(current) if row.get("object_id") == object_id), -1)
        if index < 0:
            raise ConsoleError("unknown_object")
        target = current[index]
        proposal = admission_of(target).get("expand_merge") or {}
        parts = list(proposal.get("parts") or [])
        if (
            proposal.get("kind") != "sentence_continuation"
            or not proposal.get("source_bound")
            or len(parts) != 2
        ):
            raise ConsoleError("source_continuation_not_available")
        neighbor = None
        for row in current[index + 1 :]:
            if row.get("object_type") == "document" or row.get("object_type") == "heading" or row.get("proposed_object_type") == "heading":
                continue
            neighbor = row
            break
        neighbor_text = re.sub(r"\s+", " ", str((neighbor or {}).get("content", {}).get("clean_text") or "")).strip()
        if neighbor is None or not neighbor_text.startswith(parts[1]):
            raise ConsoleError("source_continuation_changed")
        merged_text = re.sub(r"\s+", " ", str(proposal.get("merged_text") or "")).strip()
        target_text = re.sub(r"\s+", " ", str((target.get("content") or {}).get("clean_text") or "")).strip()
        if parts[0] != target_text or merged_text != f"{parts[0]} {parts[1]}":
            raise ConsoleError("source_continuation_changed")
        target_source = researcher_visible_prose(
            str(self.open_source_passage(snapshot_id=snapshot_id, object_id=object_id).get("passage") or "")
        )
        neighbor_source = researcher_visible_prose(
            str(self.open_source_passage(snapshot_id=snapshot_id, object_id=str(neighbor["object_id"])).get("passage") or "")
        )
        if parts[0] not in target_source or parts[1] not in neighbor_source:
            raise ConsoleError("source_continuation_not_literal")

        # Validate the expanded selection before writing review or revision evidence.
        from src.knowledge_materialisation_v1 import materialise_knowledge_candidates, MaterialisationError
        source_path, _ = self._verified_source_bytes(envelope)
        fragments = self._read_source_fragments(envelope, source_path)
        spans = deepcopy((target.get("metadata") or {}).get("semantic_passage", {}).get("spans") or [])
        following = deepcopy((neighbor.get("metadata") or {}).get("semantic_passage", {}).get("spans") or [])
        if not spans or len(following) != 1:
            raise ConsoleError("materialisation_span_invalid")
        following[0]["end"] -= len(neighbor_text) - len(parts[1])
        if (spans[-1]["block_id"] == following[0]["block_id"]
                and following[0]["start"] == spans[-1]["end"] + 1):
            spans[-1]["end"] = following[0]["end"]
        else:
            spans.extend(following)
        selection = {"decision_kind": "semantic_selection", "selection_origin": "proposal_selected",
                     "spans": spans, "source_text": merged_text}
        try:
            materialise_knowledge_candidates([selection], document_id=envelope["document_id"], fragments=fragments)
        except MaterialisationError as exc:
            raise ConsoleError("pre_review_llm_proposal_rejected", exc.code) from exc

        self.review_object(
            actor_id=actor_id,
            snapshot_id=snapshot_id,
            object_id=object_id,
            decision="revise",
            comment="Afgebroken zin aangevuld met direct aansluitende brontekst.",
            suitability="samenvoegen",
            eindoordeel="goedkeuren_na_correctie",
            expected_revision=expected_revision,
        )
        return self.correct_object(
            actor_id=reviewer["account_id"],
            snapshot_id=snapshot_id,
            object_id=object_id,
            patch={
                "reason": "Afgebroken zin aangevuld met direct aansluitende brontekst.",
                "operations": [
                    {"op": "set", "path": "content.clean_text", "value": merged_text},
                    {"op": "set", "path": "content.raw_text", "value": merged_text},
                ],
            },
            additional_source_fragments=list((neighbor.get("provenance") or {}).get("source_fragments") or []),
            materialisation_decision=selection,
            rereview_scope="object",
        )

    def silently_edit_object(self, snapshot_id: str, object_id: str, _patch: dict[str, Any]) -> None:
        self._envelope(snapshot_id)
        raise ConsoleError("cannot_silently_mutate")

    def consider_publish(self, *, actor_id: str, snapshot_id: str) -> dict[str, Any]:
        self._require_role(actor_id, "publisher")
        envelope = self._envelope(snapshot_id)
        if self.snapshot_is_published(snapshot_id):
            return {
                "snapshot_id": snapshot_id,
                "publish_allowed": False,
                "state": "published",
                "blockers": ["already_published"],
                "g2": "PASS",
                "publishable_object_ids": [],
                "publishable_object_count": 0,
            }
        if envelope.get("publication_eligibility") == PRE_REVIEW_BLOCKED:
            return {
                "snapshot_id": snapshot_id,
                "independence_satisfied": False,
                "tuple_authorization": False,
                "four_eyes_required": False,
                "four_eyes_satisfied": True,
                "envelope_review_passes_authorizes": False,
                "publish_allowed": False,
                "state": envelope["state"],
                "blockers": ["pre_review_processing_incomplete"],
                "g2": (
                    "PASS"
                    if is_g2_locator(envelope.get("immutable_storage_locator"))
                    else "BLOCKED"
                ),
                "object_contracts": [],
                "publishable_object_ids": [],
                "publishable_object_count": 0,
            }
        objects = self.snapshot_objects(snapshot_id)
        bindings = [
            row
            for row in self.object_review_bindings(snapshot_id)
            if row.get("valid") and row.get("decision") == "approve"
        ]
        from src.knowledge_path_v1 import is_structural_projection
        review_path = review_path_for_klasse(envelope["class"])
        approved_ids = {str(row.get("object_id") or "") for row in bindings}
        publishable = [
            obj
            for obj in objects
            if obj.get("object_type") != "document"
            and not is_structural_projection(obj)
            and str(obj.get("object_id") or "") in approved_ids
            and (obj.get("governance") or {}).get("validation_status") == "approved"
        ]
        others = [
            row
            for row in bindings
            if row.get("reviewer_id") != envelope["uploader_account_id"]
        ]
        blockers: list[str] = []
        from src.recoverable_formation_v1 import incomplete
        if incomplete(envelope, objects=objects):
            blockers.append("source_formation_incomplete")
        independence = bool(others)
        from src.review_policy_v1 import participants, object_policy, validate_policy
        policy = envelope.get("review_policy")
        if policy is not None:
            try:
                from src.review_policy_v1 import required_reviewers
                policy = validate_policy(policy)
                from src.review_policy_v1 import archived_required
                if archived_required(policy):
                    blockers.append("archived_required_review_unfilled")
                for reviewer_id in required_reviewers(policy):
                    account = self._require_role(reviewer_id, "reviewer")
                    if account.get("retirement") or _is_forbidden_identity(account["username"]):
                        raise ConsoleError("invalid_review_policy")
                if set(envelope["named_reviewers"]) != set(participants(policy)):
                    blockers.append("review_policy_membership_conflict")
                if any(object_policy(obj) != policy for obj in objects):
                    blockers.append("review_policy_projection_mismatch")
            except (ValueError, ConsoleError):
                blockers.append("invalid_review_policy")
            independence = True
        from src.decision_graph_v1 import publication_issues
        blockers.extend(publication_issues(envelope, objects))
        if any((o.get("metadata") or {}).get("decision_graph_contract") for o in objects) and "decision_graph" not in envelope:
            blockers.append("decision_graph_missing")
        try:
            from src.decision_graph_v1 import verify_source_evidence
            verify_source_evidence(self, envelope)
        except (ValueError, OSError):
            blockers.append("decision_graph_source_evidence_mismatch")
        from src.source_context_review_v1 import context_issues
        if context_issues(self.snapshot_objects(snapshot_id)):
            blockers.append("source_context_review_incomplete")
        if not independence:
            blockers.append("second_named_reviewer_required")
        if not bindings:
            blockers.append("object_tuple_required")
        four_eyes_needed = False
        four_eyes_ok = True
        contracts = []
        fragments = None
        if review_path != "boom" and publishable:
            try:
                source_path, _ = self._verified_source_bytes(envelope)
                fragments = self._read_source_fragments(envelope, source_path)
            except (ConsoleError, ValueError, OSError):
                blockers.append("source_lineage_unavailable")
        for obj in publishable:
            if obj.get("object_type") == "document":
                continue
            contract = publish_authorization_contract(
                obj=obj,
                bindings=bindings,
                uploader_id=envelope["uploader_account_id"],
                immutable_locator=envelope.get("immutable_storage_locator"),
                envelope_review_passes=envelope.get("review_passes"),
                review_path=review_path,
                fragments=fragments,
            )
            contracts.append(contract)
            blockers.extend(
                code
                for code in contract["blockers"]
                if code != "blocked_pending_immutable_locator"
            )
            if requires_four_eyes(obj):
                four_eyes_needed = True
                if not contract["four_eyes_satisfied"]:
                    four_eyes_ok = False
        if four_eyes_needed and not four_eyes_ok:
            blockers.append("four_eyes_required")
        locator = envelope.get("immutable_storage_locator")
        if not is_g2_locator(locator):
            blockers.append("blocked_pending_immutable_locator")
        elif self.immutable_source_store is None:
            blockers.append("g2_source_store_unavailable")
        else:
            try:
                source_bytes = self.immutable_source_store.load_verified(str(locator))
                if sha256_bytes(source_bytes) != str(envelope.get("sha256") or ""):
                    blockers.append("g2_source_checksum_mismatch")
            except (G2SourceStoreError, ValueError):
                blockers.append("g2_source_verification_failed")
        if any(schema_errors(obj, self.schema_path) for obj in publishable):
            blockers.append("prepublication_schema_invalid")
        unique = list(dict.fromkeys(blockers))
        g2_pass = not any(
            code
            in {
                "blocked_pending_immutable_locator",
                "g2_source_store_unavailable",
                "g2_source_checksum_mismatch",
                "g2_source_verification_failed",
            }
            for code in unique
        )
        return {
            "snapshot_id": snapshot_id,
            "independence_satisfied": independence,
            "tuple_authorization": bool(contracts) and all(c["tuple_authorization"] for c in contracts),
            "four_eyes_required": four_eyes_needed,
            "four_eyes_satisfied": four_eyes_ok if four_eyes_needed else True,
            "envelope_review_passes_authorizes": False,
            "publish_allowed": not unique and bool(publishable),
            "state": envelope["state"],
            "blockers": unique,
            "g2": "PASS" if g2_pass else "BLOCKED",
            "object_contracts": contracts,
            "publishable_object_ids": [obj["object_id"] for obj in publishable],
            "publishable_object_count": len(publishable),
        }

    def publish(self, *, actor_id: str, snapshot_id: str) -> dict[str, Any]:
        with self._store_write_lock():
            documents = getattr(self, "workflow_document_store", None)
            reviews = getattr(self, "workflow_review_store", None)
            if documents is not None and reviews is not None:
                from src.workflows.workflow_transaction_v1 import workflow_transaction
                # Context review and publication share this snapshot barrier.
                # Keep it through the canonical decision and derived writes.
                with workflow_transaction(reviews) as connection:
                    connection.execute("SELECT snapshot_id FROM workflow.documents WHERE snapshot_id=%s FOR UPDATE",
                                       (snapshot_id,))
                    self._reload_store_locked()
                    return self._publish_locked(actor_id=actor_id, snapshot_id=snapshot_id)
            self._reload_store_locked()
            return self._publish_locked(actor_id=actor_id, snapshot_id=snapshot_id)

    def _publish_locked(self, *, actor_id: str, snapshot_id: str) -> dict[str, Any]:
        considered = self.consider_publish(actor_id=actor_id, snapshot_id=snapshot_id)
        envelope = self._envelope(snapshot_id)
        if not considered.get("publish_allowed"):
            return {
                "status": "BLOCKED",
                "state": envelope["state"],
                "snapshot_id": snapshot_id,
                "blockers": considered.get("blockers") or ["object_tuple_required"],
                "g2": considered.get("g2", "BLOCKED"),
                "cutover": False,
            }

        account = self._require_role(actor_id, "publisher")
        publish_ids = set(considered["publishable_object_ids"])
        objects = [
            obj
            for obj in self.snapshot_objects(snapshot_id)
            if obj.get("object_id") in publish_ids
        ]
        published_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        release_id = f"release-{uuid.uuid4().hex}"
        release_version = f"{envelope['version']}-{release_id[-8:]}"
        publication = {
            "release_id": release_id,
            "release_version": release_version,
            "published_at": published_at,
        }
        projected, blocked = build_projection(
            [{"knowledge_object": deepcopy(obj), "publication": publication} for obj in objects]
        )
        if blocked:
            return {
                "status": "BLOCKED",
                "state": envelope["state"],
                "snapshot_id": snapshot_id,
                "blockers": ["prepublication_projection_failed"],
                "projection_errors": blocked,
                "g2": "PASS",
                "cutover": False,
            }
        for row in projected:
            row.setdefault("metadata", {})["snapshot_id"] = snapshot_id

        projection_path = self._published_projection_path()
        previous_projection = projection_path.read_bytes() if projection_path.exists() else None
        existing_projection = []
        if previous_projection:
            existing_projection = [
                json.loads(line)
                for line in previous_projection.decode("utf-8").splitlines()
                if line.strip()
            ]
        published_object_ids = {
            str((row.get("metadata") or {}).get("object_id") or "") for row in projected
        }
        next_projection = [
            row
            for row in existing_projection
            if str((row.get("metadata") or {}).get("object_id") or "")
            not in published_object_ids
        ] + projected
        manifest = {
            "release_id": release_id,
            "release_version": release_version,
            "release_owner": account["username"],
            "published_at": published_at,
            "protocol_version": PUBLICATION_PROTOCOL_VERSION,
            "snapshot_id": snapshot_id,
            "source_sha256": envelope["sha256"],
            "immutable_storage_locator": envelope["immutable_storage_locator"],
            "objects": [
                {
                    "object_id": obj["object_id"],
                    "object_version": obj["object_version"],
                    "canonical_object_hash": (obj.get("provenance") or {}).get("canonical_object_hash"),
                    "content_hash": (obj.get("provenance") or {}).get("content_hash"),
                    "confirmed_object_type": obj.get("confirmed_object_type"),
                }
                for obj in objects
            ],
        }
        if "decision_graph" in envelope:
            from src.decision_graph_v1 import release_graph
            manifest["decision_graph_release"] = release_graph(envelope, self.snapshot_objects(snapshot_id))
        manifest_path = self.runtime / RELEASE_MANIFEST_DIRNAME / f"{release_id}.json"
        ledger_size = self._ledger_path.stat().st_size if self._ledger_path.exists() else 0
        previous_envelopes = self._envelopes_path.read_bytes() if self._envelopes_path.exists() else None
        try:
            _atomic_write(manifest_path, manifest)
            atomic_replace_projection(projection_path, next_projection)
            published_envelope = deepcopy(envelope)
            published_envelope.update(
                {
                    "state": "published",
                    "published": True,
                    "release_id": release_id,
                    "release_version": release_version,
                    "published_at": published_at,
                    "published_by": account["username"],
                }
            )
            self._envelopes[snapshot_id] = published_envelope
            _atomic_write(self._envelopes_path, self._envelopes)
            append_event(
                self._ledger_path,
                event_type="release_published",
                object_id=snapshot_id,
                object_version=str(envelope["version"]),
                actor=account["username"],
                details={
                    "release_id": release_id,
                    "release_version": release_version,
                    "published_object_ids": sorted(publish_ids),
                    "source_sha256": envelope["sha256"],
                },
            )
        except Exception:
            if previous_projection is None:
                with suppress(OSError):
                    projection_path.unlink()
            else:
                _atomic_replace_bytes(projection_path, previous_projection)
            if previous_envelopes is None:
                with suppress(OSError):
                    self._envelopes_path.unlink()
            else:
                _atomic_replace_bytes(self._envelopes_path, previous_envelopes)
            self._envelopes = self._load_map(self._envelopes_path)
            with suppress(OSError):
                manifest_path.unlink()
            if self._ledger_path.exists() and self._ledger_path.stat().st_size > ledger_size:
                with self._ledger_path.open("r+b") as handle:
                    handle.truncate(ledger_size)
            raise
        return {
            "status": "PASS",
            "state": "published",
            "snapshot_id": snapshot_id,
            "release_id": release_id,
            "release_version": release_version,
            "published_items": len(objects),
            "g2": "PASS",
            "cutover": True,
        }

    def live_snapshot(self, *, family: str, class_: str) -> dict[str, Any] | None:
        self.list_envelopes()
        live = [
            envelope
            for envelope in self._envelopes.values()
            if envelope["family"] == family and envelope["class"] == class_ and envelope.get("is_live_capture")
        ]
        if not live:
            return None
        live.sort(key=lambda row: row["acquired_at"])
        return self._receipt(live[-1])

    def select_for_question(self, *, family: str, asked_class: str) -> list[dict[str, Any]]:
        self.list_envelopes()
        if asked_class not in ALLOWED_CLASSES:
            raise ConsoleError("invalid_class")
        matching = [
            envelope
            for envelope in self._envelopes.values()
            if envelope["family"] == family and envelope["class"] == asked_class
        ]
        heavier_present = any(
            CLASS_ORDER[envelope["class"]] > CLASS_ORDER[asked_class]
            for envelope in self._envelopes.values()
            if envelope["family"] == family
        )
        if not matching and heavier_present:
            return []
        # Never fill a heavier asked class with a lighter sibling.
        out: list[dict[str, Any]] = []
        for envelope in matching:
            for obj in self.snapshot_objects(envelope["snapshot_id"]):
                out.append(
                    {
                        "snapshot_id": envelope["snapshot_id"],
                        "object_id": obj["object_id"],
                        "class": envelope["class"],
                        "family": envelope["family"],
                        "sha256": envelope["sha256"],
                    }
                )
        return out

    def list_envelopes(self) -> list[dict[str, Any]]:
        return [self._receipt(row) for row in self._envelopes.values()]

    def resolve_document(self, *, title: str, version: str, family: str) -> dict[str, Any]:
        """Map researcher-visible document identity onto the kernel snapshot."""
        self.list_envelopes()
        wanted = (title.strip(), version.strip(), family.strip())
        matches = [
            row
            for row in self._envelopes.values()
            if (row["title"], row["version"], row["family"]) == wanted
        ]
        if not matches:
            raise ConsoleError("unknown_document")
        if len(matches) > 1:
            raise ConsoleError("document_not_unique")
        return self._receipt(matches[0])

    def move_family_document(
        self,
        *,
        actor_id: str,
        title: str,
        version: str,
        family: str,
        new_family: str,
    ) -> dict[str, Any]:
        document = self.resolve_document(title=title, version=version, family=family)
        return self.move_family(
            actor_id=actor_id,
            snapshot_id=document["snapshot_id"],
            new_family=new_family,
        )

    def promote_class_document(
        self,
        *,
        actor_id: str,
        title: str,
        version: str,
        family: str,
        new_class: str,
        reextract: bool = False,
    ) -> dict[str, Any]:
        document = self.resolve_document(title=title, version=version, family=family)
        return self.promote_class(
            actor_id=actor_id,
            snapshot_id=document["snapshot_id"],
            new_class=new_class,
            reextract=reextract,
        )

    def researcher_path(self) -> dict[str, Any]:
        return {
            "surface": "operations_console",
            "room": "ingest",
            "first_envelope_family": "continentie",
            "engineer_only_parallel_path": False,
            "product_api": "separate_machine_door",
        }
