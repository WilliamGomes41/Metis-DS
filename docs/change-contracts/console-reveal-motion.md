# Console: short reveal motion on five occasional state changes

Change class: C
Promise: Five state changes MOETEN appear with a one-shot reveal of at most 240ms that animates opacity and transform only: an opened Documenten row (its content, not its summary), the companion panel when a person opens it, the session warning, the conditional fields on Inleveren (colleagues, four-eyes, existing document) and the "Publicatie voltooid" notice. Under `prefers-reduced-motion: reduce` each MOET reduce to a 150ms fade. A companion panel restored on page load MAG NIET animate. Review cards, the decision form, the annotation editor, navigation and the theme switch MOGEN NIET gain motion. Markup, routes, field names, focus order and every existing stylesheet rule MOGEN NIET change.
Proof: `tests/test_console_reveal_motion_v1.py`; a browser pass that read the running animation of each of the five elements with and without reduced motion, and confirmed a restored companion panel runs none; the review goldens re-recorded with only asset hashes changed.
Touches lifecycle invariants: no
Rewrite risk: none

Requested by William (2026-11-10) after a read-only `find-animation-opportunities` sweep (see `docs/agents/emil-design-skills.md`): the five accepted rows are implemented, the rejected ones stay still.

## Accepted

| Place | Purpose | Frequency | Motion |
| --- | --- | --- | --- |
| Documenten row content | Preventing a jarring change | Occasional | opacity and `translateY(-4px)`, 160ms |
| Companion panel, opened by a person | Spatial consistency | Occasional | opacity and `scale(0.96)` from the bottom-right corner, 160ms |
| Session warning | Preventing a jarring change | Rare | opacity and `translateY(8px)`, 200ms |
| Inleveren conditional fields | Preventing a jarring change | Occasional | opacity, 150ms |
| "Publicatie voltooid" | The one rare moment that earns a beat | Rare | opacity and `translateY(-6px)`, 240ms |

All use `cubic-bezier(0.23, 1, 0.32, 1)`. Closing and hiding stay instant. No height is animated. The companion script sets `data-reveal` only when a person opens the panel, so the panel that the stored preference reopens on every page load stays still.

## Rejected

- Review card and decision form: used tens to hundreds of times a day.
- Annotation editor: reading work; motion competes with the source text.
- Navigation between rooms and the theme switch: must be immediate.
- Hold-to-confirm on document deletion: typing the title already prevents slips.
- A staggered entrance of the home tiles: seen at every sign-in, and that screen is locked.

## Not verified

Feel was judged from the running animations' names and durations and from still frames, not on a device or by a person watching it.
