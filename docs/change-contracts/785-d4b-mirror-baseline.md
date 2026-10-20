# D4b — pin PostgreSQL mirror access before D5 (#785)

Change class: C
Promise: The PostgreSQL mirror probe rejects every unreviewed owner/file/access/phase tuple and observes rename, deletion and metadata access as well as opens, on both complete console variants.
Proof: Native PostgreSQL 16 under Python 3.12 and 3.13; all fifteen control phases; negative controls for known-owner access in a new phase and denied mutations/metadata; guarded runs remain explicit expected failures until D5.
Touches lifecycle invariants: no
Rewrite risk: none

The product baseline is `629d63c5f2ba8781f7b2c1307e8011c6476b63e2`.
No product source changes belong to this prerequisite commit.
`tests/fixtures/pg_mirror_baseline_629d63c.json` retains the raw open modes;
read+write atomic temporary files are not silently converted to write.
The additional phases exercise the real `console_asgi.build_app` composition,
including startup migration/reconciliation, and unpublished document deletion.
Both Durable and Azure classes run with all four real PostgreSQL stores.
Immutable Blob bytes and semantic proposals use the established test fixtures;
no live Azure/model service is involved. Structured logging setup is isolated
from pytest's temporary capture streams; startup domain operations are real.

The exact tuple sets are deliberately pinned per Python version: pathlib on
3.12 performs additional stat calls that 3.13 does not. Both versions must keep
their complete expected sets, rather than accepting their union. This exposes
the path-based ledger registry's `_key` metadata access as another D5 surface.
Locks remain synchronization files; source bytes/caches are outside mirrors.

This is evidence preparation, not proof of mirror-free operation. The denied
run's blocked and unreached phases remain explicit in the JUnit property.
The independent database fixture creates/drops only its own disposable database.
Existing source/PG payloads and credentials never enter the mirror report.
