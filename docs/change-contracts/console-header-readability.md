# Console header: one readable line

Change class: C
Promise: The shared console header MOET on screens of 1360px and wider show the brand, all room links including Uitloggen, the theme toggle and the account on one line. Below that width the room links MOETEN take their own full row instead of wrapping half-way. The account MOET show the display name first and the roles on a smaller second line. The theme toggle MOET be a 44px icon button with the existing aria-label, `aria-pressed` and a `title` that names the next mode. Colours, routes, the `<nav class="rooms">` markup, permissions and the landing page content MOGEN NIET change.
Proof: `tests/test_console_header_readability_v1.py`; the review-room characterization goldens re-recorded with only the stylesheet hash, the theme toggle and the account markup changed; screenshots at 1440, 1360, 1280, 1024, 800 and 390px.
Touches lifecycle invariants: no
Rewrite risk: none

Requested by William (2026-10-23): "De rest is eigenlijk suboptimaal, niet intuitief niet altijd leesvriendelijk … doe pagina voor pagina om leesbaarheid quality of life te verbeteren." The header appears on every page, so it goes first.

## Before / after

- **Before:** at 1440px the room links wrapped onto a second line (Instellingen and Uitloggen under the others) because the "Donkere modus" text button and the one-line "Naam · rollen: a, b, c" account text took the room. Rooms had no hover or keyboard-focus style.
- **After:** the toggle is a moon/sun icon, the account is two short lines, and room links get a hover tint and the existing red focus ring. Between 861px and 1359px the links sit on a full second row; the existing 860px and 560px rules are unchanged.

## Out of scope

Page bodies, colour tokens, the landing tiles and the login page. Those follow per page in later changes.
