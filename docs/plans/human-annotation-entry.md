# Human annotation entry repair (#1017)

Class B. Rewrite risk: none.

Promise: uploading a new prose source leads to human annotation, without asking
the uploader to start AI formation. A fresh prose source opened through Vorming
offers the same annotation action. Decision trees retain their existing route.

Existing mechanism and authority: POST /ingest calls receive_source, which stores
the source and chosen review configuration without starting processing. Its
redirect currently opens /source-selection, whose primary Starten form invokes
AI processing; annotation is a secondary link. The existing /annotations GET is
read-only; explicit POST /annotations/source owns preparation and source pinning.

Change only the upload redirect and the fresh prose action in
source_selection_ui_v1.install. Reuse annotation preparation, selection, build,
review and publication operations unchanged. No new durable state or authority;
GET/reload must not create attempts or take ownership. Existing running work,
candidate sets, reviewer policy, published work and decision trees stay under
their existing contracts. No automatic takeover or production cleanup.

Proof: native PostgreSQL HTTP upload must land on the annotation opening action,
including after reload and reopening via Vorming; no processing attempt, object,
or annotation set exists before explicit preparation. The existing complete HTTP
chain covers save, restart, build, review and publication. Exercise upload and
annotation save/resume in Chromium at desktop and mobile widths. Check the tree
counterexample and relevant existing ingestion/formation tests.
