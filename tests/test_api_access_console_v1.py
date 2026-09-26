from pathlib import Path

from fastapi.testclient import TestClient

from src.api_access_v1 import ProvisionedConsumer
from src.operations_console_app import create_console_app
from src.operations_console_v1 import OperationsConsole


class FakeAccessStore:
    def __init__(self):
        self.calls = []
        self.rows = []
        self.secret = "metis_live_cred_test.once-only-secret"

    def list_consumers(self):
        return list(self.rows)

    def provision_consumer(self, **kwargs):
        self.calls.append(dict(kwargs))
        self.rows.append(
            {
                "tenant_id": "ten_test",
                "tenant_name": kwargs["tenant_name"],
                "tenant_state": "ACTIVE",
                "application_id": "app_test",
                "application_name": kwargs["application_name"],
                "environment": kwargs["environment"],
                "application_state": "ACTIVE",
                "active_credentials": 1,
            }
        )
        return ProvisionedConsumer(
            tenant_id="ten_test",
            application_id="app_test",
            credential_id="cred_test",
            credential=self.secret,
        )


def _console(tmp_path: Path) -> OperationsConsole:
    console = OperationsConsole(
        root=tmp_path,
        source_store=tmp_path / "sources" / "private",
        runtime=tmp_path / "output" / "runtime" / "operations-console",
    )
    console.create_account(
        username="publisher.carla",
        password="publisher-secret",
        roles=("publisher",),
        display_name="Carla Publisher",
    )
    console.create_account(
        username="researcher.rik",
        password="researcher-secret",
        roles=("researcher",),
        display_name="Rik Researcher",
    )
    return console


def _logged_in_client(console, store, username, password):
    client = TestClient(create_console_app(console, api_access_store=store))
    response = client.post(
        "/login",
        data={"username": username, "password": password},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return client


def _provision_payload():
    return {
        "tenant_name": "Hospital A",
        "tenant_content_scope": "RESOURCE_SET",
        "tenant_document_ids": "doc-a\ndoc-b",
        "tenant_scopes": ["retrieve", "documents:read"],
        "tenant_requests_per_minute": "200",
        "tenant_max_top_k": "10",
        "application_name": "Hospital A EPD",
        "environment": "PRODUCTION",
        "application_content_scope": "RESOURCE_SET",
        "application_document_ids": "doc-a",
        "application_scopes": ["retrieve"],
        "application_requests_per_minute": "100",
        "application_max_top_k": "5",
    }


def test_settings_exposes_api_access_as_first_class_settings_room(tmp_path):
    store = FakeAccessStore()
    client = _logged_in_client(
        _console(tmp_path),
        store,
        "publisher.carla",
        "publisher-secret",
    )
    response = client.get("/settings")
    assert response.status_code == 200
    assert 'href="/settings/api-access"' in response.text
    assert "API Access" in response.text


def test_publisher_can_provision_consumer_and_secret_is_only_in_issue_response(tmp_path):
    store = FakeAccessStore()
    client = _logged_in_client(
        _console(tmp_path),
        store,
        "publisher.carla",
        "publisher-secret",
    )

    issued = client.post("/settings/api-access/provision", data=_provision_payload())
    assert issued.status_code == 200
    assert issued.headers["cache-control"] == "no-store"
    assert store.secret in issued.text
    assert "na deze pagina niet opnieuw getoond" in issued.text
    assert len(store.calls) == 1
    assert store.calls[0]["tenant_document_ids"] == ["doc-a", "doc-b"]
    assert store.calls[0]["application_document_ids"] == ["doc-a"]

    listing = client.get("/settings/api-access")
    assert listing.status_code == 200
    assert "Hospital A EPD" in listing.text
    assert store.secret not in listing.text


def test_non_publisher_cannot_provision_api_access(tmp_path):
    store = FakeAccessStore()
    client = _logged_in_client(
        _console(tmp_path),
        store,
        "researcher.rik",
        "researcher-secret",
    )
    response = client.post("/settings/api-access/provision", data=_provision_payload())
    assert response.status_code == 403
    assert store.calls == []
