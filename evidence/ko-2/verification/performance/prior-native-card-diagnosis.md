# Native initial-card failure: bounded display read

Observed p95:40.834→46.271ms, delta5.437ms. The10% allowance is4.0834ms, leaving1.3536ms to remove. This does not prove a linear counterfactual for one optimized request; it identifies the required margin before a later justified verification.

The extra connection/query is **source display**, not publication authority. The canonical guard remains required at src/review/ko_review_page_v1.py:189, but src/workflows/workflow_badge_counts_postgres_v1.py:704 uses the current request's already captured canonical batch set by src/documents/document_status_ui_v1.py:126. No separate publication SQL executes under review_render in these samples. This corrects my earlier generic attribution in the acceptance report.

Actual caller chain:

- src/operations_console_app.py:3465 delegates focused KO to render_review_page.
- src/review/ko_review_page_v1.py:42 calls read_document_context for its source panel.
- src/review/ko_document_context_ui_v1.py:19 calls FormationTaskStore.read_review_document_context(envelope,obj,source=inputs.fragments).
- src/workflows/review_source_records_v1.py:204 reuses the exact sealed ReadSource root/ordinals and verifies source/extraction identity.
- When the root is scoped, line230 opens another physical workflow connection; lines231–238 select missing raw headings and immediate neighbors. Lines239–244 independently verify member hashes, raw payload hash, fragment identity; lines246–248 require complete immediate raw ordinals. Return is display-only ReviewDocumentContext at252.

This is one legitimate bounded source-display query and one avoidable extra connection. It reads original raw context rather than loading or reconstructing all blocks. The display rows must remain separate from the exact review/source closure.

| Median native card phase | Baseline ms | HEAD ms |
|---|---:|---:|
| All db_connect |8.609|10.060|
| All db_execute |17.503|19.110|
| Source read records |4.779|5.044|
| Source read db_connect |1.481|1.456|
| Source read db_execute |2.225|2.293|
| Source hydrate |0.251|0.226|
| Render db_connect |0|1.362|
| Render db_execute |0|1.191|
| Render db_fetch |0|0.036|
| Render inclusive |1.043|4.377|

Source-read call counts are unchanged:one read_records call, one connection, seven SQL executions, one hydrate call. HEAD adds exactly one connection/query in review_render,6/21→7/22overall. At the failing HEAD round5/sample3:render connect2.265+execute1.578+fetch.040=3.883ms of5.671ms inclusive render. Its1.783ms exclusive render includes HTML and pure checks. These are wall-phase observations, not CPU profiles, and overlapping inclusive totals must not be added. There is no observed large-source hydration regression in this card path. Payloads remain bounded:initial card p95 JSON33,436→35,436bytes(+5.98%); exactly2,000bytes in that failing sample belong to the display query, and closure-read JSON/validator semantics stay separate.

## Two bounded shapes

**A — recommended first: capture the same display raw rows while the existing immutable source-read connection is open.** Keep the exact SQL predicate/returned bytes and all validators. Supply the focal display identity explicitly from read_review_passage at src/review/review_passage_read_v1.py:306, through the prepared-source read, so the record reader can capture headings/neighbors before its existing source connection closes at src/workflows/review_source_records_v1.py:358. Source raw closure and ordinals are already captured at350–354; resolve the display focal IDs from the same target block/member inputs. Store the extra rows in a typed display-only capture separate from normal fragments/blocks; validate root identity/member hashes/ordinal completeness after closing the connection, then pass the validated display value through ReviewPassageInputs to the renderer. The renderer consumes it without I/O. Preserve the current explicit context-expansion route. Commands and other source callers request no display capture and keep their current behavior. This removes only one physical connection, retaining the same query, payload and source checks. Median connection cost1.362ms is close to the1.354ms margin, so do not promise acceptance from that estimate; actual failing sample connection cost2.265ms shows it is the right measured limiter.

**B — combine the display raw capture into an existing selected-source SQL result, with separate typed projections.** Return closure rows and bounded display rows in separate result fields from the existing selected raw read at src/workflows/review_source_records_v1.py:350. Retain exact focal block/member reference derivation and separate independent raw/member validation; never union display neighbors into ReadSource.raw or its block closure. This can remove both the extra connection and its SQL round trip, potentially covering more of the observed2.589ms median or3.883ms maximum display database work. It is more invasive: closure discovery can iterate, so display projection must be attached exactly once after the focal member IDs are known; avoid repeating or serializing the same display payload per closure row. It changes result decoding and requires more equivalence evidence thanA. Use only ifA's measured saving is insufficient or implementation is naturally simpler under the current source capture owner.

Do not widen an outer workflow transaction around the current render/source validation. That would move unrelated file/byte validation and computation into the bounded read transaction. Do not add display fragments to the source closure, skip hashes, remove canonical publication guards, or introduce a process cache. Required tests for either shape:unchanged review closure identities/block membership; original heading and immediate neighbor texts; nonmatching source/extraction/member/raw hashes fail closed; missing raw ordinal fail closed; source unavailable disables approve; no DB reads from renderer; published/new-working-revision guards retain canonical authority; first-card JSON stays under the existing10% cap.

No product writes, new probes, protocol changes or reruns were performed for this diagnosis. Native whole p95 passed9.22%, while median increased14.86%; both remain reported in RESULT.md.
