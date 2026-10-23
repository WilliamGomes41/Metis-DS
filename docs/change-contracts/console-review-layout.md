# Review room: space and hierarchy

Change class: C
Promise: The Review room MOET use one spacing scale (`--space-1` to `--space-8`): tight inside a group, generous between groups. The document bar MOET be neutral; Rood MOET NIET mark a document that is simply in review, and warning banners MOETEN use the alert colours. Group counts MOETEN sit as a badge beside their label. The passage under review MOET read as body text (1.25rem, text colour, at most 65ch), and the decision questions MOETEN form one rail without a card per question, with click areas of at least 44px. The duplicate "Uitleg bij deze taak" link on task screens MOET be hidden. The workboard filters MOETEN sit on one row in one block, empty lists MOETEN show an empty-state line, and the read-only trajectory page MOET sit in the room layout with one block per part. In dark mode the highlighted source text MOET stay readable. Copy, questions, form fields, routes, review rules and stored data MOGEN NIET change.
Proof: `tests/test_console_review_layout_v1.py`; the existing review and participation tests; the characterization goldens re-recorded (stylesheet hash, the filter-form class and the empty-state lines); impeccable critique before (21/40) and after; screenshots at 1440 and 390px approved by William before the PR.
Touches lifecycle invariants: no
Rewrite risk: none

Requested by William (2026-10-23): "alles is op elkaar, weinig heeft echt ruimte". Definition of done agreed in the project thread after the impeccable critique of the Review room. The mode-specific questions (heading review) and the contradicting status follow in a separate change, because they alter review behaviour.

CSS is appended as overrides at the end of `console.css`.
