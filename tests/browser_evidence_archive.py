"""Export only action metadata from a pinned Playwright v8 library trace."""
import json
import math
from pathlib import Path
import re
import sys
import zipfile


CALL_ID = re.compile(r"call@[0-9]+")
PAGE_ID = re.compile(r"page@[0-9a-f]{32}")
CONTEXT_ID = re.compile(r"browser-context@[0-9a-f]{32}")
# These are protocol identifiers, never copied from action arguments or the page.
IDENTIFIER = re.compile(r"[A-Za-z][A-Za-z0-9]{0,49}")
TRACE_LIMIT = 25 * 1024 * 1024


def timestamp(event, field):
    value = event[field]
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError(field)
    return value


def identifier(event, field, pattern):
    value = event[field]
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise ValueError(field)
    return value


def safe_events(raw_events):
    first, *actions = raw_events.splitlines()
    context = json.loads(first)
    if (
        context["type"] != "context-options"
        or context["version"] != 8
        or context["playwrightVersion"] != "1.58.2"
        or context["browserName"] != "chromium"
    ):
        raise ValueError("unsupported trace format")
    yield {
        "type": "context-options",
        "version": 8,
        "origin": "library",
        "browserName": "chromium",
        "playwrightVersion": "1.58.2",
        "sdkLanguage": "javascript",
        "wallTime": timestamp(context, "wallTime"),
        "monotonicTime": timestamp(context, "monotonicTime"),
        "contextId": identifier(context, "contextId", CONTEXT_ID),
        "options": {},
    }
    for line in actions:
        event = json.loads(line)
        if event["type"] == "before":
            projected = {
                "type": "before",
                "callId": identifier(event, "callId", CALL_ID),
                "startTime": timestamp(event, "startTime"),
                "class": identifier(event, "class", IDENTIFIER),
                "method": identifier(event, "method", IDENTIFIER),
                "params": {},
            }
            if "pageId" in event:
                projected["pageId"] = identifier(event, "pageId", PAGE_ID)
            yield projected
        elif event["type"] == "after":
            projected = {
                "type": "after",
                "callId": identifier(event, "callId", CALL_ID),
                "endTime": timestamp(event, "endTime"),
            }
            if event.get("error"):
                projected["error"] = {"name": "Error", "message": "Browser action failed"}
            yield projected


def export_trace(source, target, limit=TRACE_LIMIT):
    try:
        if source.stat().st_size > limit:
            return "trace-too-large"
        with zipfile.ZipFile(source) as original:
            if sum(entry.file_size for entry in original.infolist()) > limit:
                return "trace-too-large"
            events = safe_events(original.read("trace.trace"))
            # Reconstruct the ZIP from projected events. Raw members, arguments, logs,
            # console messages, response bodies and stack sources are never copied.
            safe_trace = "\n".join(json.dumps(event) for event in events) + "\n"
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("trace.trace", safe_trace)
        if target.stat().st_size > limit:
            return "trace-too-large"
    except (OSError, ValueError, KeyError, TypeError, OverflowError, zipfile.BadZipFile):
        return "trace-unusable"
    return "ok"


if __name__ == "__main__":
    source_path, target_path = map(Path, sys.argv[1:3])
    maximum = int(sys.argv[3]) if len(sys.argv) == 4 else TRACE_LIMIT
    print(export_trace(source_path, target_path, maximum))
