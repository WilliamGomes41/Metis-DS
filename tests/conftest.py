"""HTTPS test origin so Secure login cookies are sent by TestClient."""

from __future__ import annotations

from starlette.testclient import TestClient

_orig_init = TestClient.__init__


def _https_init(self, app, base_url: str = "https://testserver", **kwargs):  # type: ignore[no-untyped-def]
    _orig_init(self, app, base_url=base_url, **kwargs)


TestClient.__init__ = _https_init  # type: ignore[method-assign]
