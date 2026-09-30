"""Full-source highlights follow frozen positions, including repeated prose."""

import hashlib

import pytest

from src.open_original_v1 import (
    OpenOriginalError,
    document_visible_prose,
    full_document_segments,
)


def _locator(value: str) -> dict[str, str]:
    return {"locator_type": "web_line_range", "locator_value": value}


def _byte_locator(source: bytes, passage: bytes, *, last: bool = False) -> dict[str, str]:
    start = source.rindex(passage) if last else source.index(passage)
    return _locator(f"bytes:{start}-{start + len(passage)}")


def _marked(segments: list[tuple[str, bool]]) -> str:
    return "".join(text for text, marked in segments if marked)


@pytest.mark.parametrize("use_bytes", [True, False])
def test_duplicate_html_highlights_only_the_located_occurrence(use_bytes):
    paragraph = b"<p>Same <strong>source</strong> passage.</p>"
    source = b"<h1>Document</h1>\n" + paragraph + b"\n" + paragraph + b"\n<p>After.</p>"
    before = hashlib.sha256(source).digest()
    locator = _byte_locator(source, paragraph, last=True) if use_bytes else _locator("lines:3-3")

    segments = full_document_segments(source, "html", locator)

    assert segments == [
        ("Document\nSame source passage.\n", False),
        ("Same source passage.", True),
        ("\nAfter.", False),
    ]
    assert "".join(text for text, _ in segments) == document_visible_prose(source, "html")
    assert hashlib.sha256(source).digest() == before


def test_byte_locator_precedes_stale_lines_and_counts_utf8_bytes():
    source = "<p>één 😊</p>\n<p>advies café advies</p>".encode()
    locator = _byte_locator(source, b"advies", last=True)
    locator["locator_value"] = "lines:1-1;" + locator["locator_value"]
    assert full_document_segments(source, "html", locator) == [
        ("één 😊\nadvies café ", False), ("advies", True)
    ]


def test_range_crossing_tags_and_entities_keeps_exact_visible_boundary():
    source = b"<p>Before A&amp;<em>B</em> &#x43; after</p>"
    selected = b"A&amp;<em>B</em> &#x43;"
    assert full_document_segments(source, "html", _byte_locator(source, selected)) == [
        ("Before ", False), ("A&B C", True), (" after", False)
    ]


def test_range_ending_inside_a_tag_marks_only_covered_visible_text():
    source = b"<p>Before <em>target</em> after</p>"
    selected = b"em>target</e"
    assert _marked(full_document_segments(source, "html", _byte_locator(source, selected))) == "target"


@pytest.mark.parametrize("entity,visible", [(b"&amp;", "&"), (b"&#38;", "&"), (b"&#x26;", "&"), (b"&NotEqualTilde;", "≂̸")])
def test_complete_entities_have_source_provenance(entity, visible):
    source = b"<p>" + entity + b" and " + entity + b"</p>"
    assert full_document_segments(source, "html", _byte_locator(source, entity, last=True)) == [
        (visible + " and ", False), (visible, True)
    ]


def test_partial_entity_does_not_falsely_highlight_a_complete_character():
    source = b"<p>First &amp; second &amp;.</p>"
    segments = full_document_segments(source, "html", _byte_locator(source, b"amp", last=True))
    assert segments == [("First & second &.", False)]


@pytest.mark.parametrize("newline", [b"\n", b"\r\n", b"\r"])
def test_line_locator_uses_original_lines_not_projected_paragraphs(newline):
    source = newline.join([b"<section>", b"<p>Repeat</p>", b"<p>Repeat</p>", b"</section>"])
    assert full_document_segments(source, "html", _locator("lines:3-3")) == [
        ("Repeat\n", False), ("Repeat", True)
    ]


@pytest.mark.parametrize("tag", ["script", "style", "noscript"])
def test_hidden_source_is_never_mapped_to_identical_visible_text(tag):
    source = f"<{tag}>Repeated text</{tag}><p>Repeated text</p>".encode()
    segments = full_document_segments(source, "html", _byte_locator(source, b"Repeated text"))
    assert segments == [("Repeated text", False)]


def test_unsafe_html_is_plain_prose_and_never_includes_attributes_or_scripts():
    source = b'<p onclick="danger()">Read <img src=x onerror="danger()">this &lt;tag&gt;.</p><script>danger()</script>'
    segments = full_document_segments(source, "html", _byte_locator(source, source))
    assert segments == [("Read this <tag>.", True)]
    assert "".join(text for text, _ in segments) == document_visible_prose(source, "html")


@pytest.mark.parametrize("kind", ["json", "boom"])
@pytest.mark.parametrize("use_bytes", [True, False])
def test_json_and_boom_preserve_raw_text_and_locate_exact_duplicate(kind, use_bytes):
    source = b'{\n  "first": "<script>same</script>",\n  "second": "<script>same</script>"\n}\n'
    locator = _byte_locator(source, b"same", last=True) if use_bytes else _locator("lines:3-3")
    segments = full_document_segments(source, kind, locator)
    assert "".join(text for text, _ in segments) == source.decode()
    assert _marked(segments) == ("same" if use_bytes else '  "second": "<script>same</script>"\n')
    assert segments[0][1] is False


@pytest.mark.parametrize("value", ["lines:0-1", "lines:2-1", "lines:x-1", "lines:1-99", "bytes:0-999", "bytes:2-2", "bytes:x-3", "page:1"])
def test_invalid_locators_fail_closed(value):
    with pytest.raises(OpenOriginalError, match="unsupported_locator"):
        full_document_segments(b"<p>Text</p>", "html", _locator(value))


def test_utf8_byte_boundary_inside_character_fails_closed():
    with pytest.raises(OpenOriginalError, match="unsupported_locator"):
        full_document_segments("<p>é</p>".encode(), "html", _locator("bytes:4-5"))


@pytest.mark.parametrize("source", [
    b"<div>  A\t B <span>C</span>\n D </div><p>E<br>F</p>",
    b"<table><tr><td>A</td><td>B</td></tr></table>",
    b"<p>A &amp B &unknown; C &notit; D &#38 E &nbsp; F</p>",
    b"<!-- Hidden --><p> A </p><style>hidden</style><p>B</p>",
])
def test_projection_keeps_existing_document_visible_prose_behavior(source):
    segments = full_document_segments(source, "html", _byte_locator(source, source))
    assert "".join(text for text, _ in segments) == document_visible_prose(source, "html")


def test_malformed_entity_keeps_full_prose_without_uncertain_highlighting():
    source = b"<p>&#invalid; Repeated</p><p>&#invalid; Repeated</p>"
    segments = full_document_segments(source, "html", _byte_locator(source, b"Repeated", last=True))
    assert segments == [(document_visible_prose(source, "html"), False)]


def test_invalid_utf8_fails_with_an_explicit_locator_error():
    with pytest.raises(OpenOriginalError, match="unsupported_locator"):
        full_document_segments(b"<p>\xff</p>", "html", _locator("lines:1"))


def test_missing_or_wrong_locator_kind_is_explicit():
    with pytest.raises(OpenOriginalError, match="source_locator_missing"):
        full_document_segments(b"text", "html", {})
    with pytest.raises(OpenOriginalError, match="unsupported_locator"):
        full_document_segments(b"text", "html", {"locator_type": "page_bbox", "locator_value": "page:1"})
    with pytest.raises(OpenOriginalError, match="locator_kind_mismatch"):
        full_document_segments(b"text", "pdf", _locator("lines:1"))


@pytest.mark.parametrize("last_text", ["First", "Third"])
def test_multiple_html_locators_mark_disjoint_occurrences_once(last_text):
    source = f"<p>First</p><p>Middle</p><p>{last_text}</p>".encode()
    locators = [_byte_locator(source, b"First"), _byte_locator(source, last_text.encode(), last=True)]
    assert full_document_segments(source, "html", locators) == [
        ("First", True), ("\nMiddle\n", False), (last_text, True)
    ]


@pytest.mark.parametrize("kind", ["html", "json"])
def test_overlapping_adjacent_and_duplicate_ranges_are_merged(kind):
    source = b"<p>abcdefghij</p>" if kind == "html" else b'"abcdefghij"'
    locators = [_byte_locator(source, part) for part in [b"def", b"abcde", b"gh", b"def"]]
    segments = full_document_segments(source, kind, locators)
    expected = [("abcdefgh", True), ("ij", False)] if kind == "html" else [
        ('"', False), ("abcdefgh", True), ('ij"', False)
    ]
    assert segments == expected
    assert "".join(text for text, _ in segments) == document_visible_prose(source, kind)


def test_multiple_json_locators_preserve_disjoint_duplicate_occurrences():
    source = b'{"first": "same", "middle": "same", "last": "same"}'
    segments = full_document_segments(source, "json", [
        _byte_locator(source, b"same"), _byte_locator(source, b"same", last=True)
    ])
    assert segments == [('{"first": "', False), ("same", True),
                        ('", "middle": "same", "last": "', False), ("same", True), ('"}', False)]


def test_extractor_ordinals_locate_same_line_duplicates_and_skip_chrome(tmp_path):
    from src.extract_html_v1 import extract

    source = b'<nav class="site-nav"><p>Repeated</p></nav><p>Repeated</p><p></p><p>Repeated</p><footer><p>Repeated</p></footer>'
    path = tmp_path / "source.html"
    path.write_bytes(source)
    rows = extract(path, document_id="doc", source_id="source")
    assert [row["source_locator"]["locator_value"] for row in rows] == ["lines:1-1;p:1", "lines:1-1;p:3"]
    assert full_document_segments(source, "html", rows[-1]["source_locator"]) == [
        ("Repeated\nRepeated\n", False), ("Repeated", True), ("\nRepeated", False)
    ]


@pytest.mark.parametrize("newline", [b"\n", b"\r\n", b"\r"])
def test_extracted_multiline_ordinals_map_back_to_original_freeze(tmp_path, newline):
    from src.extract_html_v1 import extract

    source = newline.join([b"<p>First</p>", b"<p>Second</p>", b"<p>Third</p>"])
    path = tmp_path / "source.html"
    path.write_bytes(source)
    rows = extract(path, document_id="doc", source_id="source")
    segments = full_document_segments(source, "html", [rows[0]["source_locator"], rows[2]["source_locator"]])
    assert segments == [("First", True), ("\nSecond\n", False), ("Third", True)]


@pytest.mark.parametrize("value", ["lines:1-1;p:9", "lines:2-2;p:1", "lines:1-1;p:bad", "lines:1-1;div:1"])
def test_unresolvable_ordinal_never_marks_a_broad_line(value):
    source = b"<p>First</p><p>Second</p>\n<p>Third</p>"
    segments = full_document_segments(source, "html", _locator(value))
    assert segments == [("First\nSecond\nThird", False)]


def test_byte_span_precedes_unresolvable_ordinal():
    source = b"<p>First</p><p>Second</p>"
    locator = _byte_locator(source, b"Second")
    locator["locator_value"] = "lines:1-1;p:99;" + locator["locator_value"]
    assert full_document_segments(source, "html", locator) == [("First\n", False), ("Second", True)]


def test_one_unresolved_fragment_makes_highlight_uncertainty_explicit():
    source = b"<p>First</p><p>Second</p>"
    assert full_document_segments(source, "html", [
        _byte_locator(source, b"First"), _locator("lines:1-1;p:99")
    ]) == [("First\nSecond", False)]
