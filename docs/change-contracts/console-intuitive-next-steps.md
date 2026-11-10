# Console: next steps where a screen is empty or asks too early

Change class: C
Promise: An empty Documenten list MOET link to Inleveren, and an empty Publiceren list MOET say when a document appears there and when publishing becomes possible. The document count MOET read "1 document" for exactly one result. The personal Review workboard MOET show one empty message, not two, when no review document is visible. Inleveren MOET ask for colleagues only after a review form that needs them is chosen, and MOET name how many to choose; the Ctrl hint MOET show only when two are needed. Instellingen MOET lose the label above its heading and MOET show its links in two columns from 900px. Accounts MOET offer the roles of an account as one labelled group of 44px choices and MOET keep the new-user form apart from the account list; the posted `roles` values MOGEN NIET change. Primary and secondary buttons MOETEN give a short press response that is absent under `prefers-reduced-motion`. Routes, form field names and values, permissions, review rules, the home tiles, the shared header and every existing stylesheet rule MOGEN NIET change.
Proof: `tests/test_console_intuitive_next_steps_v1.py`; the existing ingest, review workboard, documents and stylesheet tests; a browser pass of Inleveren (all four review options), Documenten, Review, Publiceren, Instellingen and Accounts at 1440px and at an emulated 390px viewport with no horizontal overflow.
Touches lifecycle invariants: no
Rewrite risk: none

Requested by William (2026-11-10): make the Metis UI more intuitive, using Impeccable together with the selected Emil Kowalski skills (`docs/agents/emil-design-skills.md`).

## Before / after

- **Documenten, empty:** "Lever eerst een document in." was plain text. It is now a link to `/ingest`.
- **Documenten, count:** "1 documenten" becomes "1 document".
- **Publiceren, empty:** "Nog geen documenten." gave no cause. It now says that an ingested document appears here and that publishing follows a finished review.
- **Review, empty:** "Op deze pagina heb je geen uitvoerbare beoordelingen." and "Geen aan jou toegewezen reviewdocumenten…" appeared under each other. The first now shows only when documents are visible but none is actionable.
- **Inleveren:** the colleague list was visible before any choice, labelled "Welke collega's (niet nodig bij Alleen ik)", always with the Ctrl hint. It now stays hidden until a choice needs it and is labelled "Kies een collega" or "Kies twee collega's". The server-rendered markup and field names are unchanged; only the page script decides visibility, so the form still works as before without JavaScript.
- **Instellingen:** the "Beheer" label above the heading repeated a section heading below it and is removed; seven full-width links become a two-column list on wide screens.
- **Accounts:** the role checkboxes were 13px boxes under a paragraph that repeated the button text, and the first account touched the new-user form. They are now a `Rollen` group using the same choice style as Inleveren, with a gap above the list. Saving a role change was checked in the browser.
- **Buttons:** `.btn-primary` and `.btn-secondary` scale to 0.97 for 120ms while pressed.

## Out of scope

The home tiles and their neutral, badge-free state (ROADMAP lock, #546), the shared header, colour tokens, the review card and decision form, Vorming and the annotation editor, and the multi-select control for colleagues, which existing browser and form tests address by name. The stylesheet is extended at its end only.

## Worst-case data

Documenten, Vorming, Publiceren, Accounts and the annotation start page were rendered with a 190-character title, a two-letter title and a 46-character display name at 1440px and an emulated 390px: titles and names wrap, nothing overflows. Two observations are left as they are because they are domain wording, not layout: Documenten labels a not-yet-started document `geblokkeerd` while Vorming says `nog niet gestart`, and Publiceren shows the same status twice.

## Not verified

Screens that need formed knowledge objects (review cards, source context, publication readiness with reviewed content) were not rendered with data: formation needs the model provider, which the local check did not have. Phone behavior was checked in an emulated viewport, not on a device.
