"""D2a.1/D2a.2 machine-readable processing diagnostics exports.

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

from copy import deepcopy
import csv
import io
import json

from fastapi.testclient import TestClient

from src.integrity_kernel import stamp_canonical_hashes
from src.operations_console_app import create_console_app
from src.operations_console_v1 import OperationsConsole
from src.processing_diagnostics_v1 import (
    processing_diagnostic_rows,
    processing_diagnostics,
)


PASSWORD = "d2a1-secret"


def _system(tmp_path):
    console = OperationsConsole(
        root=tmp_path,
        source_store=tmp_path / "sources" / "private",
        runtime=tmp_path / "runtime",
    )
    researcher = console.create_account(
        username="researcher.d2a1",
        password=PASSWORD,
        roles=("researcher",),
    )
    reviewer = console.create_account(
        username="reviewer.d2a1",
        password=PASSWORD,
        roles=("reviewer",),
    )
    other = console.create_account(
        username="reviewer.other",
        password=PASSWORD,
        roles=("reviewer",),
    )
    publisher = console.create_account(
        username="publisher.d2a1",
        password=PASSWORD,
        roles=("publisher",),
    )
    receipt = console.ingest(
        actor_id=researcher["account_id"],
        filename="diagnostics.html",
        data=(
            b"<html><body><h1>Richtlijn</h1>"
            b"<p>Bespreek passende ondersteuning met de client.</p>"
            b"<p>Leg de gemaakte afspraken vast.</p>"
            b"</body></html>"
        ),
        content_type="text/html",
        ingest_kind="new",
        title="Diagnostiek",
        version="1.0",
        date="2026-09-24",
        live_url="",
        class_="richtlijn",
        family="diagnostiek",
        named_reviewers=[reviewer["account_id"]],
    )
    snapshot_id = str(receipt["snapshot_id"])
    rows = console._load_objects(snapshot_id)
    target = next(
        row
        for row in rows
        if row.get("object_type") not in {"document", "heading"}
        and row.get("proposed_object_type") != "heading"
    )
    target.setdefault("metadata", {})["admission"] = {
        "gate_result": "blocked",
        "reason_codes": [
            "incomplete_sentence",
            "recommendation_evidence_missing",
        ],
        "proposed_type": "recommendation",
        "section_role": "primary",
        "section_path": ["Richtlijn", "Aanbevelingen"],
    }
    target["proposed_object_type"] = "recommendation"
    target["metadata"]["passage_formation"] = {
        "strategy": "semantic",
        "reason": "semantic_free_text_required",
    }
    target["metadata"]["semantic_passage"] = {
        "selection_origin": "proposal_selected",
        "source_bound": True,
    }
    stamp_canonical_hashes(target)
    for row in rows:
        if row is target:
            continue
        if row.get("object_type") in {"document", "heading"} or row.get("proposed_object_type") == "heading":
            continue
        metadata = row.setdefault("metadata", {})
        metadata["admission"] = {
            "gate_result": "allowed",
            "reason_codes": [],
            "proposed_type": str(row.get("proposed_object_type") or "explanation"),
            "section_role": "regular",
            "section_path": ["Richtlijn"],
        }
        stamp_canonical_hashes(row)
    console._save_objects(snapshot_id, rows)
    return console, reviewer, other, publisher, snapshot_id


def _client(console: OperationsConsole) -> TestClient:
    return TestClient(
        create_console_app(console),
        base_url="https://testserver",
        raise_server_exceptions=False,
    )


def _login(client: TestClient, username: str) -> None:
    response = client.post(
        "/login",
        data={"username": username, "password": PASSWORD},
        follow_redirects=False,
    )
    assert response.status_code == 303


def test_export_matches_pure_projection_and_does_not_mutate_state(tmp_path) -> None:
    console, _reviewer, _other, _publisher, snapshot_id = _system(tmp_path)
    client = _client(console)
    _login(client, "reviewer.d2a1")

    before_objects = deepcopy(console.snapshot_objects(snapshot_id))
    before_envelope = deepcopy(console._envelope(snapshot_id))
    before_bindings = deepcopy(console.object_review_bindings(snapshot_id))
    before_revision = console.objects_revision(snapshot_id)
    expected = processing_diagnostics(before_objects)

    response = client.get(
        f"/review/processing-diagnostics?document={snapshot_id}"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["snapshot_id"] == snapshot_id
    assert payload["title"] == "Diagnostiek"
    assert payload["version"] == "1.0"
    assert payload["objects_revision"] == before_revision
    assert payload["diagnostics"] == expected
    assert payload["diagnostics"]["blocked_candidate_count"] == 1
    assert payload["diagnostics"]["issue_occurrence_count"] == 2

    assert console.snapshot_objects(snapshot_id) == before_objects
    assert console._envelope(snapshot_id) == before_envelope
    assert console.object_review_bindings(snapshot_id) == before_bindings
    assert console.objects_revision(snapshot_id) == before_revision


def test_detail_export_preserves_candidate_combinations_and_does_not_mutate_state(tmp_path) -> None:
    console, _reviewer, _other, _publisher, snapshot_id = _system(tmp_path)
    client = _client(console)
    _login(client, "reviewer.d2a1")

    before_objects = deepcopy(console.snapshot_objects(snapshot_id))
    before_envelope = deepcopy(console._envelope(snapshot_id))
    before_bindings = deepcopy(console.object_review_bindings(snapshot_id))
    before_revision = console.objects_revision(snapshot_id)
    expected = processing_diagnostic_rows(before_objects)

    response = client.get(
        f"/review/processing-diagnostics-detail?document={snapshot_id}"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["snapshot_id"] == snapshot_id
    assert payload["title"] == "Diagnostiek"
    assert payload["version"] == "1.0"
    assert payload["objects_revision"] == before_revision
    assert payload["rows"] == expected
    assert len(payload["rows"]) == 1

    row = payload["rows"][0]
    assert row["object_id"]
    assert row["candidate_text"]
    assert row["reason_codes"] == [
        "incomplete_sentence",
        "recommendation_evidence_missing",
    ]
    assert row["families"] == [
        "unit_completeness",
        "semantic_contract",
    ]
    assert row["proposed_type"] == "recommendation"
    assert row["section_role"] == "primary"
    assert row["section_path"] == ["Richtlijn", "Aanbevelingen"]
    assert row["formation_strategy"] == "semantic"
    assert row["formation_reason"] == "semantic_free_text_required"
    assert row["selection_origin"] == "proposal_selected"

    assert console.snapshot_objects(snapshot_id) == before_objects
    assert console._envelope(snapshot_id) == before_envelope
    assert console.object_review_bindings(snapshot_id) == before_bindings
    assert console.objects_revision(snapshot_id) == before_revision


def test_export_requires_authentication_reviewer_role_and_assignment(tmp_path) -> None:
    console, _reviewer, _other, _publisher, snapshot_id = _system(tmp_path)
    paths = (
        "/settings/technical",
        "/review/passages-export",
        "/review/processing-evidence-export",
        "/review/processing-diagnostics",
        "/review/processing-diagnostics-detail",
    )

    for path in paths:
        anonymous = _client(console)
        response = anonymous.get(f"{path}?document={snapshot_id}")
        assert response.status_code == 401
        assert "not_authenticated" in response.text

        publisher_client = _client(console)
        _login(publisher_client, "publisher.d2a1")
        response = publisher_client.get(f"{path}?document={snapshot_id}")
        assert response.status_code == 403
        assert "reviewer_role_required" in response.text

        other_client = _client(console)
        _login(other_client, "reviewer.other")
        response = other_client.get(f"{path}?document={snapshot_id}")
        assert response.status_code == 400
        assert "reviewer_not_named_on_snapshot" in response.text


def test_export_unknown_snapshot_fails_and_control_page_links_to_export(tmp_path) -> None:
    console, _reviewer, _other, _publisher, snapshot_id = _system(tmp_path)
    client = _client(console)
    _login(client, "reviewer.d2a1")

    for path in (
        "/settings/technical",
        "/review/passages-export",
        "/review/processing-evidence-export",
        "/review/processing-diagnostics",
        "/review/processing-diagnostics-detail",
    ):
        missing = client.get(f"{path}?document=snap-does-not-exist")
        assert missing.status_code == 400
        assert "unknown_snapshot" in missing.text

    control = client.get(f"/settings/technical/exports?document={snapshot_id}")
    assert control.status_code == 200
    assert (
        f'href="/review/processing-diagnostics?document={snapshot_id}"'
        in control.text
    )
    assert "Diagnostiek (JSON)" in control.text
    assert (
        f'href="/review/processing-diagnostics-detail?document={snapshot_id}"'
        in control.text
    )
    assert "Detaildiagnostiek (JSON)" in control.text


def test_all_passages_export_includes_every_current_passage_and_evidence(tmp_path):
    console, _, _, _, snapshot_id = _system(tmp_path)
    client = _client(console)
    _login(client, "reviewer.d2a1")
    objects = deepcopy(console.snapshot_objects(snapshot_id))
    envelope = deepcopy(console._envelope(snapshot_id))
    bindings = deepcopy(console.object_review_bindings(snapshot_id))
    expected = [obj for obj in objects if obj["object_type"] != "document"]
    url = f"/review/passages-export?document={snapshot_id}"
    response = client.get(url)
    assert response.status_code == 200
    assert "attachment;" in response.headers["content-disposition"]
    assert response.headers["cache-control"] == "no-store"
    payload = response.json()
    assert payload["passage_count"] == len(expected)
    assert [row["object_id"] for row in payload["rows"]] == [obj["object_id"] for obj in expected]
    assert any(row["object_type"] == "heading" for row in payload["rows"])
    assert any(row["gate_result"] == "blocked" for row in payload["rows"])
    for row, obj in zip(payload["rows"], expected):
        assert row["admission"] == obj.get("metadata", {}).get("admission", {})
        assert row["source"] == obj.get("source", {})
    csv_response = client.get(url + "&format=csv")
    assert csv_response.status_code == 200
    assert csv_response.content.startswith(b"\xef\xbb\xbf")
    exported = list(csv.DictReader(io.StringIO(csv_response.content.decode("utf-8-sig"))))
    assert len(exported) == len(expected)
    assert [row["candidate_text"] for row in exported] == [row["candidate_text"] for row in payload["rows"]]
    assert json.loads(exported[0]["admission"]) == payload["rows"][0]["admission"]
    assert client.get(url + "&format=xml").status_code == 400
    page = client.get(f"/settings/technical/exports?document={snapshot_id}")
    assert "Bronpassages:" in page.text
    assert "&amp;format=csv" in page.text
    assert "&amp;format=json" in page.text
    assert console.snapshot_objects(snapshot_id) == objects
    assert console._envelope(snapshot_id) == envelope
    assert console.object_review_bindings(snapshot_id) == bindings


def test_source_label_guidance_http_and_export_preserve_review_state(tmp_path):
    console, _, _, _, sid = _system(tmp_path)
    # Reproduce an already stored standalone label from the reported PDF run.
    objects = console._load_objects(sid)
    target = next(o for o in objects if (o.get('metadata') or {}).get('admission', {}).get('gate_result') == 'blocked')
    target['content']['clean_text'] = target['content']['raw_text'] = 'DOEN'
    target['metadata']['admission']['candidate_text'] = 'DOEN'
    target['metadata']['admission']['source_text_exact'] = 'DOEN'
    stamp_canonical_hashes(target)
    console._save_objects(sid, objects)
    client = _client(console)
    _login(client, 'reviewer.d2a1')
    before = deepcopy(console.snapshot_objects(sid, include_blocked=True))
    revision = console.objects_revision(sid)
    target = next(o for o in before if (o.get('content') or {}).get('clean_text') == 'DOEN')
    page = client.get(f'/review?document={sid}&task=inventory')
    assert page.status_code == 200
    assert 'Mogelijk bronlabel' in page.text
    detail = client.get(f'/review?document={sid}&object={target["object_id"]}&task=repair')
    assert detail.status_code == 200
    assert 'De koppeling en betekenis zijn hiermee niet bevestigd.' in detail.text
    response = client.get(f'/review/passages-export?document={sid}&format=csv')
    assert response.status_code == 200
    rows = list(csv.DictReader(io.StringIO(response.content.decode('utf-8-sig'))))
    row = next(r for r in rows if r['object_id'] == target['object_id'])
    hint = json.loads(row['source_label_hint'])
    assert hint['status'] == 'possible_source_label'
    assert hint['basis'] == 'derived_from_current_text_not_a_review_decision'
    assert row['candidate_text'] == 'DOEN'
    assert len(rows) == sum(o['object_type'] != 'document' for o in before)
    assert console.snapshot_objects(sid, include_blocked=True) == before
    assert console.objects_revision(sid) == revision


def test_label_shape_is_only_a_hint_and_not_a_short_text_filter():
    from src.source_label_hint_v1 import source_label_hint
    for text in ('DOEN', ' NIET\nDOEN ', 'Niveau 3', 'niveau 4'):
        obj = {'content': {'clean_text': text}}
        before = deepcopy(obj)
        assert source_label_hint(obj)['status'] == 'possible_source_label'
        assert obj == before
    for text in ('Doen wat nodig is.', 'Niet doen bij koorts.', 'Niveau 3 is bereikt.', 'Pijn', 'Ja', 'Niveau 5', ''):
        assert source_label_hint({'content': {'clean_text': text}}) == {}


def test_csv_preserves_quotes_newlines_unicode_and_neutralizes_formulas():
    from src.processing_diagnostics_v1 import passage_export_csv
    texts = ['Zeg "nee",\nook bij ouderen: één.', '=HYPERLINK("bad")', '  +SUM(1,2)', '@SUM(1)', '\tformula']
    exported = list(csv.DictReader(io.StringIO(passage_export_csv([
        {"candidate_text": text} for text in texts
    ]).lstrip('\ufeff'))))
    assert exported[0]["candidate_text"] == texts[0]
    assert [row["candidate_text"] for row in exported[1:]] == ["'" + text for text in texts[1:]]


def test_processing_evidence_download_preserves_recorded_and_missing_evidence(tmp_path, monkeypatch):
    from zipfile import ZipFile
    from src.processing_evidence_export_v1 import SCHEMAS

    console, _, _, _, snapshot_id = _system(tmp_path)
    envelope = console._envelope(snapshot_id)
    envelope["semantic_replay"] = {
        "proposal_hash": "proposal-1", "validation": "passed",
        "semantic_execution": "replay", "origin_execution": "inference",
        "identity": {"components": {"model_id": "recorded-model", "prompt_hash": "original-prompt"}},
        "proposal": {"objects": [{"spans": [{"block_id": "block-1", "start": 0, "end": 8}]}]},
    }
    objects = console.snapshot_objects(snapshot_id)
    target = next(o for o in objects if o.get("proposed_object_type") == "recommendation")
    target["metadata"]["semantic_passage"] = {
        "selection_origin": "coverage_remainder", "spans": [{"block_id": "block-1", "start": 0, "end": 8}],
    }
    target["metadata"]["admission"]["context_scan"] = {
        "necessary_context_disposition": "include", "expand_merge": {"performed": False},
    }
    target["metadata"]["admission"]["type_evidence_spans"] = []
    target["content"]["clean_text"] = '=HYPERLINK("bad")\nEen, "zin".'
    stamp_canonical_hashes(target)
    console._save_objects(snapshot_id, objects)
    envelope["private_configuration"] = "must-not-be-exported"
    before = deepcopy((console.snapshot_objects(snapshot_id), envelope, console.object_review_bindings(snapshot_id)))
    monkeypatch.setattr(console, "_extract", lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not reextract")))
    client = _client(console)
    _login(client, "reviewer.d2a1")
    response = client.get(f"/review/processing-evidence-export?document={snapshot_id}")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["content-type"] == "application/zip"
    assert "attachment;" in response.headers["content-disposition"]
    with ZipFile(io.BytesIO(response.content)) as archive:
        assert set(archive.namelist()) == {"manifest.csv", "revision.csv", "README.txt", *(name + ".csv" for name in SCHEMAS)}
        def rows(name):
            data = archive.read(name + ".csv")
            assert data.startswith(b"\xef\xbb\xbf")
            return list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"))))
        manifest = {r["dataset"]: r for r in rows("manifest")}
        assert manifest["model_calls.csv"]["availability"] == "not_recorded"
        assert manifest["object_events.csv"]["availability"] == "not_exported"
        assert rows("model_calls") == []
        proposal = rows("semantic_proposals")[0]
        assert json.loads(proposal["proposal"]) == envelope["semantic_replay"]["proposal"]
        assert "not_raw_response" in proposal["evidence_kind"]
        selected = next(r for r in rows("coverage") if r["object_id"] == target["object_id"])
        assert selected["start"] == "0"
        assert selected["selection_origin"] == "coverage_remainder"
        assert selected["model_decision_status"] == "not_recorded"
        fields = {r["field"]: r for r in rows("proposal_fields") if r["object_id"] == target["object_id"]}
        assert fields["type_evidence_spans"]["value"] == "[]"
        assert fields["type_evidence_spans"]["value_status"] == "recorded"
        assert fields["recommended_action"]["value_status"] == "not_recorded"
        context = next(r for r in rows("context_evidence") if r["object_id"] == target["object_id"])
        assert json.loads(context["context_scan"])["expand_merge"]["performed"] is False
        source = next(r for r in rows("source_stages") if r["object_id"] == target["object_id"] and r["stage"] == "current_object_clean_text")
        assert source["text"] == "'" + target["content"]["clean_text"]
        assert all("must-not-be-exported" not in archive.read(name).decode("utf-8-sig") for name in archive.namelist())
    assert (console.snapshot_objects(snapshot_id), console._envelope(snapshot_id), console.object_review_bindings(snapshot_id)) == before
    page = client.get(f"/settings/technical/exports?document={snapshot_id}")
    assert f'/review/processing-evidence-export?document={snapshot_id}' in page.text


def test_processing_evidence_empty_history_has_headers_and_honest_availability():
    from zipfile import ZipFile
    from src.processing_evidence_export_v1 import processing_evidence_tables, processing_evidence_zip
    kwargs = dict(snapshot_id="snapshot", revision="rev", envelope={}, objects=[])
    tables, manifest = processing_evidence_tables(**kwargs)
    assert all(not values for values in tables.values())
    assert next(r for r in manifest if r["dataset"] == "runs.csv")["availability"] == "not_recorded"
    _, recorded = processing_evidence_tables(**{**kwargs, "envelope": {"quality_processing_runs": []}})
    assert next(r for r in recorded if r["dataset"] == "runs.csv")["availability"] == "recorded"
    with ZipFile(io.BytesIO(processing_evidence_zip(**kwargs))) as archive:
        assert "call_id" in archive.read("model_calls.csv").decode("utf-8-sig")


def test_long_revision_is_stored_once_and_resolvable_for_every_dataset():
    from zipfile import ZipFile
    from hashlib import sha256
    from src.processing_evidence_export_v1 import processing_evidence_zip, processing_evidence_tables, VERSION
    revision = 'm2.' + 'A' * 51000
    envelope = {'quality_processing_runs': [{'run_id': 'run-1', 'candidates': [
        {'object_id': f'object-{i}', 'object_version': '1.0'} for i in range(300)]}]}
    tables, projected = processing_evidence_tables(snapshot_id='snap-compact', revision=revision,
                                                   envelope=envelope, objects=[])
    assert all(r['schema_version'] == 'processing-evidence-export-v7' for r in projected)
    assert tables['run_candidates'][0]['objects_revision'] == revision
    payload = processing_evidence_zip(snapshot_id='snap-compact', revision=revision,
                                      envelope=envelope, objects=[])
    with ZipFile(io.BytesIO(payload)) as archive:
        assert sum(info.file_size for info in archive.infolist()) < 150000
        revision_id = 'sha256:' + sha256(revision.encode()).hexdigest()
        counts = {}
        for name in archive.namelist():
            if not name.endswith('.csv'):
                continue
            rows = list(csv.DictReader(io.StringIO(archive.read(name).decode('utf-8-sig'))))
            counts[name] = len(rows)
            for row in rows:
                assert row['revision_id'] == revision_id
                assert row['snapshot_id'] == 'snap-compact'
                if name == 'revision.csv':
                    assert row['objects_revision'] == revision
                else:
                    assert 'objects_revision' not in row
        manifest = list(csv.DictReader(io.StringIO(archive.read('manifest.csv').decode('utf-8-sig'))))
        assert all(int(r['row_count']) == counts[r['dataset']] for r in manifest)
        assert all(r['schema_version'] == VERSION for r in manifest)


def test_technical_management_collects_tools_and_keeps_repair_actionable(tmp_path):
    console, _, _, _, snapshot_id = _system(tmp_path)
    client = _client(console)
    _login(client, "reviewer.d2a1")
    settings = client.get("/settings")
    assert 'href="/settings/technical"' in settings.text
    assert 'href="/audit"' not in settings.text
    assert 'href="/settings/llm"' not in settings.text
    hub = client.get("/settings/technical")
    assert hub.status_code == 200
    for target in ["/settings/llm", "/settings/api-access", "/audit", "/audit/semantic-safety", "/settings/quality/compare"]:
        assert f'href="{target}"' in hub.text
    assert snapshot_id in hub.text
    repair = client.get(f"/review?document={snapshot_id}&task=repair")
    assert "Bekijk bronpassage" in repair.text
    assert "Technische diagnose en exports" in repair.text
    assert "Signalen per diagnostische familie" not in repair.text
    assert "Exporteer detaildiagnostiek" not in repair.text
    other = _client(console)
    _login(other, "reviewer.other")
    assert snapshot_id not in other.get("/settings/technical").text
