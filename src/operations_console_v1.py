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

from src.extract_html_v1 import extract as extract_html
from src.extract_pdf_v2 import extract as extract_pdf
from src.integrity_kernel import compute_canonical_object_hash, sha256_bytes
from src.review_workflow_v3 import apply_reviews
from src.revision_workflow import create_revision
from src.semantic_transform_generic_v1 import transform as transform_generic


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
    for fragment in fragments:
        text = (fragment.get("clean_text") or fragment.get("raw_text") or "").strip()
        if not text:
            continue
        object_type = "section" if fragment.get("heading") else "recommendation"
        objects.append(
            {
                "object_id": f"{document_id}-{fragment['fragment_id']}",
                "object_type": object_type,
                "text": text,
                "clean_text": text,
                "source_fragment_ids": [fragment["fragment_id"]],
                "section_path": fragment.get("section_path") or [],
                "heading": fragment.get("heading"),
                "review_track": "clinical",
            }
        )
    return {
        "spec_version": "console-ingest-1.0",
        "document_id": document_id,
        "object_version": "1.0",
        "target_group": [],
        "care_setting": [],
        "topic": [family, f"class-weight:{content_kind}"],
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
        self._accounts: dict[str, dict[str, Any]] = self._load_map(self._accounts_path)
        self._sessions: dict[str, dict[str, Any]] = self._load_map(self._sessions_path)
        self._envelopes: dict[str, dict[str, Any]] = self._load_map(self._envelopes_path)

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
        history.append(updated_target)
        self._save_objects(snapshot_id, history)
        if decision == "approve":
            envelope["review_passes"][actor_id] = {"passed": True, "at": utc_now(), "object_id": object_id}
            self._save_envelopes()
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
        history = self._load_objects(snapshot_id)
        history.append(revised)
        self._save_objects(snapshot_id, history)
        envelope = self._envelope(snapshot_id)
        envelope["review_passes"] = {}
        envelope["clinical_rereview_required"] = True
        self._save_envelopes()
        return deepcopy(revised)

    def silently_edit_object(self, snapshot_id: str, object_id: str, _patch: dict[str, Any]) -> None:
        self._envelope(snapshot_id)
        raise ConsoleError("cannot_silently_mutate")

    def consider_publish(self, *, actor_id: str, snapshot_id: str) -> dict[str, Any]:
        self._require_role(actor_id, "publisher")
        envelope = self._envelope(snapshot_id)
        others = [
            reviewer_id
            for reviewer_id in envelope["named_reviewers"]
            if reviewer_id != envelope["uploader_account_id"]
            and (envelope.get("review_passes") or {}).get(reviewer_id, {}).get("passed")
        ]
        blockers: list[str] = []
        independence = bool(others)
        if not independence:
            blockers.append("second_named_reviewer_required")
        if not envelope.get("immutable_storage_locator"):
            blockers.append("blocked_pending_immutable_locator")
        return {
            "snapshot_id": snapshot_id,
            "independence_satisfied": independence,
            "publish_allowed": False,
            "state": envelope["state"],
            "blockers": blockers,
            "g2": "BLOCKED",
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

    def researcher_path(self) -> dict[str, Any]:
        return {
            "surface": "operations_console",
            "room": "ingest",
            "first_envelope_family": "continentie",
            "engineer_only_parallel_path": False,
            "product_api": "separate_machine_door",
        }
