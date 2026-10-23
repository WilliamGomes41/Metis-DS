# Bronselectie: readable document card

Change class: C
Promise: The Bronselectie document picker MOET use a labelled select with a console-style "Document selecteren" button beside it. Each document card MOET show file, source version and size on one line, with the size in bytes, kB or MB in Dutch notation. The status line MOET stand out as a label. The processing estimate MOET be one sentence without repeating "Onvoldoende". Starten or Hervatten, Naar Review and Bekijk diagnose MOETEN sit in one action row. What the buttons and links do, the progress refresh, `POST /source-selection/start`, the projection and the kernel MOGEN NIET change.
Proof: `tests/test_console_source_selection_readability_v1.py` and the existing Bronselectie tests (`tests/test_availability_repair.py`, `tests/test_source_selection_progress_action.py`); screenshots at 1440 and 390px approved by William before the PR.
Touches lifecycle invariants: no
Rewrite risk: none

Requested by William (2026-10-23), page-by-page readability series; definition of done agreed in the project thread before implementation. Follows `console-ingest-readability.md`.

CSS is appended as overrides at the end of `console.css`.
