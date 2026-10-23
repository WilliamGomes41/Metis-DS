"""Run the release settings preflight and image build dry run as an operator would.

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SECRET = "sk-test-not-printed"
READY = {
    "METIS_PASSAGE_FORMATION_MODE": "semantic-source-bound-v3",
    "METIS_LLM_API_KEY": SECRET,
    "METIS_LLM_MODEL": "fixture-model",
    "METIS_PDF_EXTRACTOR": "docling",
    "CONSOLE_IMMUTABLE_SOURCE_STORE": "azure",
}


def run_preflight(settings, raw=None):
    rows = raw if raw is not None else json.dumps(
        [{"name": name, "value": value, "slotSetting": False} for name, value in settings.items()])
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/release_settings_preflight.py")],
        input=rows, capture_output=True, text=True, cwd=ROOT, check=False,
    )
    assert SECRET not in result.stdout + result.stderr
    return result.returncode, json.loads(result.stdout)


def test_ready_settings_pass_and_hide_the_key():
    code, result = run_preflight(READY)
    assert code == 0
    assert result["status"] == "ready"
    assert result["passage_formation_mode"] == "semantic-source-bound-v3"
    assert result["METIS_LLM_API_KEY"] == "present"


def test_retired_deterministic_mode_blocks_the_release():
    code, result = run_preflight({**READY, "METIS_PASSAGE_FORMATION_MODE": "deterministic-v1"})
    assert code == 2
    assert result["blocking"] == ["passage_formation_mode_retired"]
    assert result["passage_formation_mode"] == "deterministic-v1"


def test_unset_mode_reads_as_the_runtime_default():
    settings = {name: value for name, value in READY.items() if name != "METIS_PASSAGE_FORMATION_MODE"}
    code, result = run_preflight(settings)
    assert code == 0
    assert result["passage_formation_mode"] == "semantic-source-bound-v2"
    assert result["passage_formation_mode_explicit"] is False


@pytest.mark.parametrize("change, finding", [
    ({"METIS_PASSAGE_FORMATION_MODE": "freeform"}, "passage_formation_mode_invalid"),
    ({"METIS_LLM_API_KEY": ""}, "llm_api_key_missing"),
    ({"METIS_LLM_MODEL": " "}, "llm_model_missing"),
    ({"METIS_PDF_EXTRACTOR": "pymupdf"}, "docling_route_invalid"),
    ({"CONSOLE_IMMUTABLE_SOURCE_STORE": "file"}, "azure_blob_source_store_required_in_azure"),
])
def test_each_runtime_refusal_blocks_the_release(change, finding):
    code, result = run_preflight({**READY, **change})
    assert code == 2
    assert result["blocking"] == [finding]


def test_view_check_off_needs_no_view_check_settings():
    code, result = run_preflight(READY)
    assert code == 0
    assert result["view_check"] == "off"


@pytest.mark.parametrize("change, findings", [
    ({"METIS_VIEW_CHECK_ORIGIN": "https://metis.example", "METIS_VIEW_CHECK_EVIDENCE_CONTAINER": "view-evidence"}, []),
    ({"METIS_VIEW_CHECK_ORIGIN": "http://metis.example", "METIS_VIEW_CHECK_EVIDENCE_CONTAINER": "view-evidence"},
     ["view_check_origin_invalid"]),
    ({"METIS_VIEW_CHECK_ORIGIN": "https://metis.example/console", "METIS_VIEW_CHECK_EVIDENCE_CONTAINER": "view-evidence"},
     ["view_check_origin_invalid"]),
    ({"METIS_VIEW_CHECK_ORIGIN": "https://metis.example"}, ["view_check_evidence_container_invalid"]),
    ({"METIS_VIEW_CHECK_ORIGIN": "https://metis.example", "METIS_VIEW_CHECK_EVIDENCE_CONTAINER": "canonical-sources",
      "G2_BLOB_CONTAINER": "canonical-sources"}, ["view_check_evidence_container_invalid"]),
])
def test_enabled_view_check_settings_match_its_startup_refusals(change, findings):
    code, result = run_preflight({**READY, **change})
    assert code == (2 if findings else 0)
    assert result["blocking"] == findings
    assert result["view_check"] == "enabled"


@pytest.mark.parametrize("raw", ["not json", "{}", "[{\"value\": \"x\"}]"])
def test_unreadable_settings_fail_closed(raw):
    code, result = run_preflight({}, raw=raw)
    assert code == 1
    assert result["status"] == "unreadable"


def test_image_build_dry_run_refuses_a_commit_outside_main(tmp_path):
    script = ROOT / "scripts/build_azure_release_image.sh"
    missing = subprocess.run(["bash", str(script), "--registry", "acr"], capture_output=True, text=True, check=False)
    assert missing.returncode == 2
    assert "release_image_registry_and_repository_required" in missing.stderr
    short = subprocess.run(["bash", str(script), "--registry", "acr", "--repository", "metis", "--commit", "abc", "--dry-run"],
                           capture_output=True, text=True, cwd=ROOT, check=False)
    assert short.returncode == 2
    assert "release_image_commit_must_be_full_sha" in short.stderr
