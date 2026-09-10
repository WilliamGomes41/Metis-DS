"""Write-only LLM credential storage for the Audit room.

The user-facing LLM API key is encrypted at rest with a deployment-provided
master key. This module is Audit-only and has no dependency on the Metis kernel.
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Mapping

from cryptography.fernet import Fernet, InvalidToken

from src.operations_console_v1 import ConsoleError, _atomic_write


AUDIT_SECRET_MASTER_KEY_ENV = "METIS_AUDIT_SECRET_KEY"
_SECRET_FILENAME = "llm_api_key.json"
_WRITE_LOCK = threading.Lock()


class AuditLLMSecretStore:
    """Persist one encrypted Audit LLM API key without exposing it to the UI."""

    def __init__(
        self,
        runtime: Path,
        *,
        environ: Mapping[str, str] | None = None,
    ) -> None:
        self.root = Path(runtime) / "audit_secrets"
        self.path = self.root / _SECRET_FILENAME
        self.environ = environ if environ is not None else os.environ

    def _fernet(self) -> Fernet:
        raw = str(self.environ.get(AUDIT_SECRET_MASTER_KEY_ENV, "") or "").strip()
        if not raw:
            raise ConsoleError("audit_secret_store_unavailable")
        try:
            return Fernet(raw.encode("ascii"))
        except (ValueError, UnicodeEncodeError) as exc:
            raise ConsoleError("audit_secret_store_unavailable") from exc

    def status(self) -> dict[str, bool]:
        try:
            self._fernet()
        except ConsoleError:
            return {"available": False, "configured": False}
        return {"available": True, "configured": self.path.is_file()}

    def set_api_key(self, value: str) -> None:
        api_key = str(value or "").strip()
        if not api_key:
            raise ConsoleError("audit_llm_api_key_required")
        if len(api_key) > 4096:
            raise ConsoleError("audit_llm_api_key_too_long")
        fernet = self._fernet()
        payload = {
            "schema_version": 1,
            "ciphertext": fernet.encrypt(api_key.encode("utf-8")).decode("ascii"),
        }
        with _WRITE_LOCK:
            self.root.mkdir(parents=True, exist_ok=True)
            _atomic_write(self.path, payload)
            self.path.chmod(0o600)

    def clear_api_key(self) -> None:
        self._fernet()
        with _WRITE_LOCK:
            try:
                self.path.unlink()
            except FileNotFoundError:
                pass

    def read_api_key(self) -> str:
        """Return the secret for the future Audit-only model caller, never for rendering."""
        fernet = self._fernet()
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            ciphertext = str(payload["ciphertext"])
            plaintext = fernet.decrypt(ciphertext.encode("ascii"))
            return plaintext.decode("utf-8")
        except FileNotFoundError as exc:
            raise ConsoleError("audit_llm_api_key_missing") from exc
        except (OSError, KeyError, TypeError, ValueError, UnicodeError, InvalidToken, json.JSONDecodeError) as exc:
            raise ConsoleError("audit_llm_secret_corrupt") from exc
