# Console headings: readable contrast

Change class: C
Promise: In light mode, h1 and h2 on work pages that used the brand Water MOETEN use #237f99, a darker shade of Water with 4.6:1 contrast on white. Before this change the brand Water (#45AAC7) gave 2.7:1, which is below WCAG AA for large text. The landing page heading (`.home-room h1`) and the login card heading MOETEN keep the brand Water. Headings that already have their own readable colour (the Review room headings in text ink, the Over Metis section headings in Paars) MOETEN keep it. Dark mode keeps its current Water tint. Brand tokens, buttons, borders and surfaces MOGEN NIET change.
Proof: `tests/test_console_heading_contrast_v1.py`; the impeccable detector no longer reports low-contrast headings on Inleveren, Documenten, Instellingen and Accounts, and still reports only the deliberately kept landing heading.
Touches lifecycle invariants: no
Rewrite risk: none

Decided by William (2026-10-23) on the question "Mogen paginakoppen een donkerdere tint van het Water-blauw krijgen?": "Donkerder blauw voor koppen".

The rules are appended as overrides at the end of `console.css`, so the original stylesheet section stays byte-identical.
