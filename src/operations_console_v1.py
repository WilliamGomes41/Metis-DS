"""Internal operations console MVP — knowledge-kernel surface for researchers.

Protocol v2.6/v2.8: ingest mailbox, family × class tree, named reviewers,
mandatory review return-loop, local G0 identity. Capture is not publication.
Local ``sources/private/`` is the G0 stand-in and is explicitly not production.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
from copy import deepcopy
from datetime import date, datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any, Callable, Iterable

from src.atomic_split_v1 import proposed_relations_for_units, split_meaning_units
from src.extract_html_v1 import extract as extract_html
from src.extract_pdf_v2 import extract as extract_pdf
from src.four_eyes_v1 import (
    mark_four_eyes_on_object,
    publish_authorization_contract,
    requires_four_eyes,
)
from src.g2_source_store import is_g2_locator
from src.integrity_kernel import compute_canonical_object_hash, sha256_bytes, stamp_canonical_hashes
from src.object_taxonomy_v1 import CLOSED_OBJECT_TYPES, extract_object_type, is_closed_confirmed_type
from src.open_original_v1 import OpenOriginalError, open_source_passage
from src.publish_authorization_v1 import invalidate_for_object, still_matches, tuple_record
from src.review_workflow_v3 import apply_reviews
from src.revision_workflow import bump_patch, create_revision
from src.semantic_transform_generic_v1 import transform as transform_generic
from src.serving_relations_v1 import confirm_relation_set, is_closed_relation_type


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_V12 = REPO_ROOT / "schemas" / "knowledge_object.schema.v1.2.json"
CONSOLE_VERSION = "operations-console-v1.0.0"
CAPTURED = "captured_not_published"
ALLOWED_ROLES = frozenset({"researcher", "reviewer", "publisher"})
ALLOWED_CLASSES = ("richtlijn", "handreiking", "artikel", "transcript", "podcast")
CLASS_ORDER = {
    "richtlijn": 4,
    "handreiking": 3,
    "artikel": 2,
    "transcript": 1,
    "podcast": 1,
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


class ConsoleError(ValueError):
    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        super().__init__(message or code)


UrlFetcher = Callable[[str], tuple[bytes, str, str]]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


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


def _atomic_write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def default_url_fetcher(url: str) -> tuple[bytes, str, str]:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ConsoleError("url_scheme_not_allowed")
    request = urllib.request.Request(url, method="GET", headers={"User-Agent": "vvn-operations-console/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = response.read()
            content_type = str(response.headers.get("Content-Type") or "")
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise ConsoleError("url_snapshot_failed") from exc
    filename = Path(parsed.path).name or "snapshot.bin"
    return data, content_type, filename


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
    meaning_units: list[dict[str, Any]] = []
    for fragment in fragments:
        text = (fragment.get("clean_text") or fragment.get("raw_text") or "").strip()
        if not text:
            continue
        object_type, proposed = extract_object_type(fragment)
        is_heading = object_type == "heading"
        units = split_meaning_units(text, is_heading=is_heading)
        for index, unit in enumerate(units, 1):
            fake = {**fragment, "clean_text": unit, "raw_text": unit}
            if not is_heading:
                # Keep section heading as structure, but do not let it equal the unit text.
                if fake.get("heading") == unit:
                    fake["heading"] = None
            unit_type, unit_proposed = extract_object_type(fake)
            if is_heading:
                unit_type, unit_proposed = "heading", "heading"
            suffix = f"-u{index:02d}" if len(units) > 1 else ""
            spec_item: dict[str, Any] = {
                "object_id": f"{document_id}-{fragment['fragment_id']}{suffix}",
                "object_type": unit_type,
                "text": unit,
                "clean_text": unit,
                "source_fragment_ids": [fragment["fragment_id"]],
                "section_path": fragment.get("section_path") or [],
                "heading": fragment.get("heading"),
                "review_track": "clinical",
                "relations": [],
                "confirmed_relations": [],
            }
            if unit_proposed:
                spec_item["proposed_object_type"] = unit_proposed
            meaning_units.append(spec_item)
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
        url_fetcher: UrlFetcher | None = None,
        schema_path: Path | None = None,
    ) -> None:
        self.root = Path(root)
        self.source_store = Path(source_store or self.root / "sources" / "private")
        self.runtime = Path(runtime or self.root / "output" / "runtime" / "operations-console")
        self.url_fetcher = url_fetcher or default_url_fetcher
        self.schema_path = Path(schema_path or SCHEMA_V12)
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
        self._bindings: dict[str, list[dict[str, Any]]] = self._load_map(self._bindings_path)  # type: ignore[assignment]
        if self._bindings_path.exists():
            loaded = json.loads(self._bindings_path.read_text(encoding="utf-8"))
            self._bindings = {key: list(value) for key, value in loaded.items()}
        else:
            self._bindings = {}

    def _load_map(self, path: Path) -> dict[str, dict[str, Any]]:
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def _save_accounts(self) -> None:
        _atomic_write(self._accounts_path, self._accounts)

    def _save_sessions(self) -> None:
        _atomic_write(self._sessions_path, self._sessions)

    def _save_envelopes(self) -> None:
        _atomic_write(self._envelopes_path, self._envelopes)

    def _save_bindings(self) -> None:
        _atomic_write(self._bindings_path, self._bindings)

    def _objects_path(self, snapshot_id: str) -> Path:
        return self._objects_dir / f"{snapshot_id}.jsonl"

    def _load_objects(self, snapshot_id: str) -> list[dict[str, Any]]:
        path = self._objects_path(snapshot_id)
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def _save_objects(self, snapshot_id: str, rows: list[dict[str, Any]]) -> None:
        path = self._objects_path(snapshot_id)
        path.write_text(
            "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
            encoding="utf-8",
        )

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
        }
        self._sessions[token] = session
        self._save_sessions()
        return dict(session)

    def session_account(self, token: str | None) -> dict[str, Any]:
        if not token or token not in self._sessions:
            raise ConsoleError("not_authenticated")
        account = self._account(self._sessions[token]["account_id"])
        return self._public_account(account)

    def logout(self, token: str | None) -> None:
        if token and token in self._sessions:
            del self._sessions[token]
            self._save_sessions()

    def list_reviewer_accounts(self) -> list[dict[str, Any]]:
        return [self._public_account(row) for row in self._accounts.values() if "reviewer" in row["roles"]]

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
        ingest = 0
        review = 0
        publish = 0
        tree = 0
        for envelope in self._envelopes.values():
            objects = self._load_objects(envelope["snapshot_id"])
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
            if "publisher" in roles and envelope.get("state") == CAPTURED:
                publish += 1
        if "reviewer" in roles:
            review = len(
                [
                    envelope
                    for envelope in self._envelopes.values()
                    if account_id in (envelope.get("named_reviewers") or [])
                    and any(
                        (row.get("governance") or {}).get("validation_status") == "needs_review"
                        for row in self._load_objects(envelope["snapshot_id"])
                    )
                ]
            )
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

    def object_review_bindings(self, snapshot_id: str) -> list[dict[str, Any]]:
        self._envelope(snapshot_id)
        current = {row["object_id"]: row for row in self.snapshot_objects(snapshot_id)}
        out = []
        for row in self._bindings.get(snapshot_id, []):
            item = dict(row)
            obj = current.get(item.get("object_id"))
            item["valid"] = bool(obj) and still_matches(item, obj)
            out.append(item)
        return out

    def confirm_object_type(
        self,
        *,
        actor_id: str,
        snapshot_id: str,
        object_id: str,
        confirmed_object_type: str,
    ) -> dict[str, Any]:
        reviewer = self._require_role(actor_id, "reviewer")
        if actor_id not in self._envelope(snapshot_id)["named_reviewers"]:
            raise ConsoleError("reviewer_not_named_on_snapshot")
        if not is_closed_confirmed_type(confirmed_object_type):
            raise ConsoleError("unknown_object_type")
        current = self.snapshot_objects(snapshot_id)
        target = next((row for row in current if row["object_id"] == object_id), None)
        if target is None:
            raise ConsoleError("unknown_object")
        if target.get("object_type") == "document":
            raise ConsoleError("unknown_object_type")
        self._require_open_original(snapshot_id, object_id)
        if target.get("confirmed_object_type") != confirmed_object_type:
            target["object_version"] = bump_patch(str(target.get("object_version") or "1.0"))
        target["confirmed_object_type"] = confirmed_object_type
        target["object_type"] = confirmed_object_type
        mark_four_eyes_on_object(target, confirmed_type=confirmed_object_type)
        stamp_canonical_hashes(target)
        history = [
            row
            for row in self._load_objects(snapshot_id)
            if not (row["object_id"] == object_id and row["object_version"] == target["object_version"])
        ]
        history.append(target)
        self._save_objects(snapshot_id, history)
        self._bindings[snapshot_id] = invalidate_for_object(self._bindings.get(snapshot_id, []), object_id)
        self._save_bindings()
        return deepcopy(target)

    def confirm_relations(
        self,
        *,
        actor_id: str,
        snapshot_id: str,
        object_id: str,
        relations: list[dict[str, Any]],
    ) -> dict[str, Any]:
        reviewer = self._require_role(actor_id, "reviewer")
        if actor_id not in self._envelope(snapshot_id)["named_reviewers"]:
            raise ConsoleError("reviewer_not_named_on_snapshot")
        current = self.snapshot_objects(snapshot_id)
        target = next((row for row in current if row["object_id"] == object_id), None)
        if target is None:
            raise ConsoleError("unknown_object")
        for row in relations:
            if not is_closed_relation_type(row.get("relation_type")):
                raise ConsoleError("unknown_relation_type")
        try:
            confirmed = confirm_relation_set(relations)
        except ValueError as exc:
            raise ConsoleError("unknown_relation_type") from exc
        if target.get("confirmed_relations") != confirmed:
            target["object_version"] = bump_patch(str(target.get("object_version") or "1.0"))
        target["confirmed_relations"] = confirmed
        stamp_canonical_hashes(target)
        history = [
            row
            for row in self._load_objects(snapshot_id)
            if not (row["object_id"] == object_id and row["object_version"] == target["object_version"])
        ]
        history.append(target)
        self._save_objects(snapshot_id, history)
        self._bindings[snapshot_id] = invalidate_for_object(self._bindings.get(snapshot_id, []), object_id)
        self._save_bindings()
        _ = reviewer
        return deepcopy(target)

    def open_source_passage(self, *, snapshot_id: str, object_id: str) -> dict[str, Any]:
        envelope = self._envelope(snapshot_id)
        target = next((row for row in self.snapshot_objects(snapshot_id) if row["object_id"] == object_id), None)
        if target is None:
            raise ConsoleError("unknown_object")
        freeze_path = Path(envelope["binary_path"])
        freeze_bytes = freeze_path.read_bytes() if freeze_path.exists() else None
        try:
            return open_source_passage(
                freeze_bytes=freeze_bytes,
                content_kind=envelope["content_kind"],
                locator=None,
                object_record=target,
            )
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
    ) -> dict[str, Any]:
        self._require_role(actor_id, "researcher")
        if ingest_kind not in {"new", "new_version"}:
            raise ConsoleError("invalid_ingest_kind")
        if class_ not in ALLOWED_CLASSES:
            raise ConsoleError("invalid_class")
        family_hook = family.strip()
        if not family_hook or not title.strip() or not version.strip():
            raise ConsoleError("ingest_fields_required")
        reviewers = self._resolve_named_reviewers(named_reviewers, actor_id)
        if url:
            data, fetched_type, fetched_name = self.url_fetcher(url)
            filename = filename or fetched_name
            content_type = content_type or fetched_type
        if data is None:
            raise ConsoleError("official_file_or_url_required")
        filename = filename or "source.bin"
        kind = classify_official_file(data, filename, content_type)
        if url and kind == "html":
            raise ConsoleError("live_url_html_not_allowed")
        digest = sha256_bytes(data)
        stored_dir = self.source_store / digest
        stored_dir.mkdir(parents=True, exist_ok=True)
        stored_path = stored_dir / Path(filename).name
        stored_path.write_bytes(data)
        locator = f"g0-local:sources/private/{digest}/{Path(filename).name}"
        snapshot_id = f"snap-{digest[:16]}-{uuid.uuid4().hex[:8]}"
        document_id = f"console-{_slug(family_hook)}-{_slug(title)}-{_slug(version)}-{digest[:8]}"
        source_id = f"src-{digest[:16]}"
        previous = None
        if ingest_kind == "new_version":
            if not replaces_snapshot_id:
                raise ConsoleError("replaces_snapshot_id_required")
            previous = self._envelope(replaces_snapshot_id)
        fragments = self._extract(kind, stored_path, document_id=document_id, source_id=source_id)
        spec = _spec_from_fragments(
            document_id=document_id,
            title=title.strip(),
            family=family_hook,
            class_=class_,
            fragments=fragments,
            content_kind=kind,
        )
        manifest = {
            "canonical_source": {
                "source_id": source_id,
                "title": title.strip(),
                "publisher": "V&VN",
                "source_url": live_url or url or "",
                "source_type": kind,
                "source_level": 1,
                "canonicality": "canonical",
                "source_checksum": digest,
                "checksum_algorithm": "sha256",
                "integrity_status": "verified",
                "publication_date": date or None,
                "version": version,
            }
        }
        objects = transform_generic(spec, manifest, fragments)
        object_diff = None
        if previous:
            object_diff = self._diff_objects(self.snapshot_objects(previous["snapshot_id"]), objects)
        envelope = {
            "snapshot_id": snapshot_id,
            "source_id": source_id,
            "document_id": document_id,
            "sha256": digest,
            "locator": locator,
            "binary_path": str(stored_path.resolve()),
            "immutable_storage_locator": None,
            "state": CAPTURED,
            "publication_eligibility": "blocked_pending_immutable_storage",
            "content_kind": kind,
            "ingest_kind": ingest_kind,
            "title": title.strip(),
            "version": version.strip(),
            "date": date,
            "live_url": live_url or url or "",
            "class": class_,
            "family": family_hook,
            "named_reviewers": reviewers,
            "uploader_account_id": actor_id,
            "review_passes": {},
            "is_live_capture": ingest_kind == "new",
            "replaces_snapshot_id": replaces_snapshot_id,
            "object_diff": object_diff,
            "clinical_rereview_required": False,
            "acquired_at": utc_now(),
            "console_version": CONSOLE_VERSION,
        }
        self._envelopes[snapshot_id] = envelope
        self._save_objects(snapshot_id, objects)
        self._save_envelopes()
        return self._receipt(envelope)

    def _extract(self, kind: str, path: Path, *, document_id: str, source_id: str) -> list[dict[str, Any]]:
        if kind == "html":
            return extract_html(path, document_id=document_id, source_id=source_id)
        return extract_pdf(path, document_id=document_id, source_id=source_id)

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
        return deepcopy(envelope)

    def snapshot_objects(self, snapshot_id: str, include_blocked: bool = False) -> list[dict[str, Any]]:
        self._envelope(snapshot_id)
        rows = self._load_objects(snapshot_id)
        if include_blocked:
            return deepcopy(rows)
        current: dict[str, dict[str, Any]] = {}
        for row in rows:
            current[row["object_id"]] = row
        return deepcopy(list(current.values()))

    def family_tree(self) -> dict[str, Any]:
        families: dict[str, dict[str, Any]] = {}
        for envelope in self._envelopes.values():
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
        family = new_family.strip()
        if not family:
            raise ConsoleError("family_required")
        envelope = self._envelope(snapshot_id)
        envelope["family"] = family
        envelope["clinical_rereview_required"] = False
        self._save_envelopes()
        return self._receipt(envelope)

    def promote_class(self, *, actor_id: str, snapshot_id: str, new_class: str) -> dict[str, Any]:
        self._require_role(actor_id, "reviewer")
        if new_class not in ALLOWED_CLASSES:
            raise ConsoleError("invalid_class")
        envelope = self._envelope(snapshot_id)
        if new_class == envelope["class"]:
            raise ConsoleError("class_unchanged")
        envelope["class"] = new_class
        envelope["clinical_rereview_required"] = True
        envelope["review_passes"] = {}
        rows = self._load_objects(snapshot_id)
        for row in rows:
            governance = row["governance"]
            governance["validation_status"] = "needs_review"
            governance["validated_by"] = None
            governance["validation_date"] = None
            governance["review_snapshot_hash"] = None
            governance["publication_status"] = "unpublished"
        self._save_objects(snapshot_id, rows)
        self._save_envelopes()
        self._bindings[snapshot_id] = invalidate_for_object(self._bindings.get(snapshot_id, []), "")
        self._bindings[snapshot_id] = [
            {**row, "valid": False} for row in self._bindings.get(snapshot_id, [])
        ]
        self._save_bindings()
        return self._receipt(envelope)

    def review_object(
        self,
        *,
        actor_id: str,
        snapshot_id: str,
        object_id: str,
        decision: str,
        comment: str | None = None,
        proposed_correction: str | None = None,
        confirmed_object_type: str | None = None,
    ) -> list[dict[str, Any]]:
        reviewer = self._require_role(actor_id, "reviewer")
        if _is_forbidden_identity(reviewer["username"]) or _is_forbidden_identity(reviewer["display_name"]):
            raise ConsoleError("forbidden_reviewer_identity")
        envelope = self._envelope(snapshot_id)
        if actor_id not in envelope["named_reviewers"]:
            raise ConsoleError("reviewer_not_named_on_snapshot")
        current = self.snapshot_objects(snapshot_id)
        target = next((row for row in current if row["object_id"] == object_id), None)
        if target is None:
            raise ConsoleError("unknown_object")
        confirmed = confirmed_object_type
        if not confirmed and target.get("confirmed_object_type"):
            confirmed = target["confirmed_object_type"]
        apply_type = bool(confirmed_object_type)
        if decision == "approve" or apply_type:
            self._require_open_original(snapshot_id, object_id)
        if decision == "approve":
            if not is_closed_confirmed_type(confirmed):
                raise ConsoleError("unknown_object_type")
            apply_type = True
        if apply_type and confirmed:
            if not is_closed_confirmed_type(confirmed):
                raise ConsoleError("unknown_object_type")
            if target.get("object_type") != "document":
                if target.get("confirmed_object_type") != confirmed:
                    target["object_version"] = bump_patch(str(target.get("object_version") or "1.0"))
                target["confirmed_object_type"] = confirmed
                target["object_type"] = confirmed
                mark_four_eyes_on_object(target, confirmed_type=confirmed)
                stamp_canonical_hashes(target)
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
        updated, report = apply_reviews(
            current,
            [payload],
            track=track,
            schema_path=self.schema_path,
            ledger_path=self._ledger_path,
        )
        if report["errors"]:
            raise ConsoleError("review_failed", json.dumps(report["errors"], ensure_ascii=False))
        history = [
            row
            for row in self._load_objects(snapshot_id)
            if not (row["object_id"] == object_id and row["object_version"] == target["object_version"])
        ]
        updated_target = next(row for row in updated if row["object_id"] == object_id)
        if confirmed and updated_target.get("object_type") != "document":
            updated_target["confirmed_object_type"] = confirmed
            updated_target["object_type"] = confirmed
            mark_four_eyes_on_object(updated_target, confirmed_type=confirmed)
            stamp_canonical_hashes(updated_target)
        history.append(updated_target)
        self._save_objects(snapshot_id, history)
        if decision == "approve":
            envelope["review_passes"][actor_id] = {"passed": True, "at": utc_now(), "object_id": object_id}
            self._save_envelopes()
            binding = tuple_record(
                object_id=object_id,
                object_version=updated_target["object_version"],
                canonical_object_hash=compute_canonical_object_hash(updated_target),
                confirmed_object_type=updated_target.get("confirmed_object_type"),
                reviewer=reviewer["username"],
                reviewer_id=actor_id,
                decision=decision,
            )
            rows = [
                item
                for item in self._bindings.get(snapshot_id, [])
                if not (item.get("object_id") == object_id and item.get("reviewer_id") == actor_id)
            ]
            rows.append(binding)
            self._bindings[snapshot_id] = rows
            self._save_bindings()
        else:
            self._bindings[snapshot_id] = invalidate_for_object(self._bindings.get(snapshot_id, []), object_id)
            self._save_bindings()
        return deepcopy(updated)

    def correct_object(
        self,
        *,
        actor_id: str,
        snapshot_id: str,
        object_id: str,
        patch: dict[str, Any],
    ) -> dict[str, Any]:
        account = self._account(actor_id)
        if "researcher" not in account["roles"] and "reviewer" not in account["roles"]:
            raise ConsoleError("correction_role_required")
        current = self.snapshot_objects(snapshot_id)
        target = next((row for row in current if row["object_id"] == object_id), None)
        if target is None:
            raise ConsoleError("unknown_object")
        revised = create_revision(
            target,
            patch,
            actor=account["username"],
            schema_path=self.schema_path,
            ledger=self._ledger_path,
        )
        if revised.get("object_type") not in {"document", "heading"}:
            revised["object_type"] = "unclassified"
        revised.pop("confirmed_object_type", None)
        stamp_canonical_hashes(revised)
        history = self._load_objects(snapshot_id)
        history.append(revised)
        self._save_objects(snapshot_id, history)
        envelope = self._envelope(snapshot_id)
        envelope["review_passes"] = {}
        envelope["clinical_rereview_required"] = True
        self._save_envelopes()
        self._bindings[snapshot_id] = invalidate_for_object(self._bindings.get(snapshot_id, []), object_id)
        self._save_bindings()
        return deepcopy(revised)

    def silently_edit_object(self, snapshot_id: str, object_id: str, _patch: dict[str, Any]) -> None:
        self._envelope(snapshot_id)
        raise ConsoleError("cannot_silently_mutate")

    def consider_publish(self, *, actor_id: str, snapshot_id: str) -> dict[str, Any]:
        self._require_role(actor_id, "publisher")
        envelope = self._envelope(snapshot_id)
        bindings = [row for row in self.object_review_bindings(snapshot_id) if row.get("valid") and row.get("decision") == "approve"]
        others = [
            row
            for row in bindings
            if row.get("reviewer_id") != envelope["uploader_account_id"]
        ]
        blockers: list[str] = []
        independence = bool(others)
        if not independence:
            blockers.append("second_named_reviewer_required")
        if not bindings:
            blockers.append("object_tuple_required")
        four_eyes_needed = False
        four_eyes_ok = True
        contracts = []
        for obj in self.snapshot_objects(snapshot_id):
            if obj.get("object_type") == "document":
                continue
            contract = publish_authorization_contract(
                obj=obj,
                bindings=bindings,
                uploader_id=envelope["uploader_account_id"],
                immutable_locator=envelope.get("immutable_storage_locator"),
                envelope_review_passes=envelope.get("review_passes"),
            )
            contracts.append(contract)
            if requires_four_eyes(obj):
                four_eyes_needed = True
                if not contract["four_eyes_satisfied"]:
                    four_eyes_ok = False
        if four_eyes_needed and not four_eyes_ok:
            blockers.append("four_eyes_required")
        if not is_g2_locator(envelope.get("immutable_storage_locator")):
            blockers.append("blocked_pending_immutable_locator")
        unique = list(dict.fromkeys(blockers))
        return {
            "snapshot_id": snapshot_id,
            "independence_satisfied": independence,
            "tuple_authorization": bool(bindings),
            "four_eyes_required": four_eyes_needed,
            "four_eyes_satisfied": four_eyes_ok if four_eyes_needed else True,
            "envelope_review_passes_authorizes": False,
            "publish_allowed": False,
            "state": envelope["state"],
            "blockers": unique,
            "g2": "BLOCKED",
            "object_contracts": contracts,
        }

    def publish(self, *, actor_id: str, snapshot_id: str) -> dict[str, Any]:
        considered = self.consider_publish(actor_id=actor_id, snapshot_id=snapshot_id)
        envelope = self._envelope(snapshot_id)
        return {
            "status": "BLOCKED",
            "state": envelope["state"],
            "snapshot_id": snapshot_id,
            "blockers": considered["blockers"] or ["blocked_pending_immutable_locator"],
            "g2": "BLOCKED",
            "cutover": False,
        }

    def live_snapshot(self, *, family: str, class_: str) -> dict[str, Any] | None:
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
    ) -> dict[str, Any]:
        document = self.resolve_document(title=title, version=version, family=family)
        return self.promote_class(
            actor_id=actor_id,
            snapshot_id=document["snapshot_id"],
            new_class=new_class,
        )

    def researcher_path(self) -> dict[str, Any]:
        return {
            "surface": "operations_console",
            "room": "ingest",
            "first_envelope_family": "continentie",
            "engineer_only_parallel_path": False,
            "product_api": "separate_machine_door",
        }
