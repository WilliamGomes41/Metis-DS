"""The operator inventory never reads or prints source content or filenames."""
import json
from unittest.mock import patch

from scripts.storage_boundary_inventory import inventory


def test_local_copies_are_counted_without_reading_or_exposing_content(tmp_path):
    sources = tmp_path / "sources"
    runtime = tmp_path / "runtime"
    sources.mkdir()
    runtime.mkdir()
    (sources / "private-document.pdf").write_text("PRIVATE SOURCE TEXT")
    (runtime / "nested").mkdir()
    (runtime / "nested" / "private-review.json").write_text("PRIVATE REVIEW")
    (runtime / "escape").symlink_to(sources, target_is_directory=True)

    with patch("builtins.open", side_effect=AssertionError("content read")):
        report = inventory({"CONSOLE_SOURCE_STORE": str(sources), "CONSOLE_RUNTIME": str(runtime)})

    assert report["status"] == "FINDINGS"
    assert [item["entries"] for item in report["surfaces"]] == [1, 2]
    output = json.dumps(report)
    assert "PRIVATE" not in output
    assert str(tmp_path) not in output
    assert "private-document" not in output
    assert report["production_compliance_proven"] is False


def test_no_observed_files_remains_incomplete(tmp_path):
    report = inventory({"CONSOLE_SOURCE_STORE": str(tmp_path / "missing-source"),
                        "CONSOLE_RUNTIME": str(tmp_path / "missing-runtime")})
    assert report["status"] == "INCOMPLETE"
    assert all(item["entries"] == 0 for item in report["surfaces"])
    assert "per_command_backup_destination" in report["unverified"]
    assert report["production_compliance_proven"] is False
