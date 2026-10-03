Change class: A
Promise: PDF preparation uses the official Docling model pipeline, preserving immutable, source-bound extraction evidence in the existing recoverable Metis processing command.
Proof: Real PDF conversion, original-source highlights, semantic/review/publication contract regression, PostgreSQL atomic/restart/concurrency proof, and Azure packaging/resource gate.
Touches lifecycle invariants: yes
Rewrite risk: high

Explicit human assignment: this issue records the user's detailed implementation assignment in the current session; no merge/deploy/delete authorization.

Design before implementation
Conversion is stateless: input immutable PDF -> validated derived Metis fragments plus complete Docling JSON. It makes no domain decision or durable write. Existing ingest/reextract/retry changes WorkingRevision state, using kernel-owned processing_attempts and atomic object/envelope commit. Console stays non-authoritative.

Hard invariants: original bytes/hash remain primary; no silent parser fallback; no model download in a request; every admitted text item has valid page/box/offset evidence; OCR is marked derived, never claimed digital verbatim; a failed/expired/stale attempt cannot activate; extraction evidence and prepared objects activate atomically; no historical review mapping/backfill; published work and authorization/publication gates unchanged.
Assumptions: CPU Linux Python 3.12; actual Docling throughput/RSS on B1 unproven. Time/page/file/output/RSS caps are explicit policy limits, not quality claims.

Lifecycle entity/transition: existing SourceSnapshot + WorkingRevision preparation; captured/blocked -> reserved running -> complete activation/succeeded OR failed/interrupted retaining prior work.
Initial durable state: immutable captured source and previous object bundle.
Trigger/actor: existing authorized ingest/reextract/manual retry.
Exact durable end state: only current attempt atomically commits complete extracted evidence and existing semantic result; failure retains prior bundle.
Workflow/release/serving before/after: processing -> existing review readiness; release and serving registry unchanged.
Failure/restart/recovery: process terminated/reaped; safe error metadata; durable reservation survives restart and lease recovery; manual retry only.
Duplicate/concurrency: existing command id, create-if-absent, PostgreSQL row lock and object revision CAS; independent converter process never writes domain state.
Immutable entities: original source, published objects/releases/reviews.
Required black-box scenario: PDF upload -> true Docling -> semantic source fields/context -> original marking -> human review -> unchanged publication gates; failed conversion -> restart/retry and concurrent command proof.

Rewrite target: PDF extraction dependency and preparation bounds/evidence, not semantic or publication authority.
Why local patching insufficient: native blocks do not supply the requested structural model output; in-process timeout cannot kill hung native/model code.
Authority/writer/reader map: immutable source store; OperationsConsole ingest/reextract/retry and PostgreSQL override -> one existing workflow authority; semantic_transform/decision_graph, source_bound v2/v3, open_original and quality/export readers; source-layout and CLI comparison scripts. No new store/job authority.
Supported topologies: Linux single-worker file compatibility and PostgreSQL multi-worker kernel; disposable local converter process. Deployment preserves lean console by separate interpreter/environment rather than relaxing forbidden-package guards.
Persisted impact: additive versioned complete extraction record in existing processing evidence/envelope; no SQL migration, no content backfill.
Compatibility/staging: old source/evidence readable; add Docling adapter and real acceptance gate before runtime cutover; comparison-only old extractor retained until quality/runtime proof. Explicit deployment configuration, never failure-triggered fallback.
Rollback/recovery: stop new PDF preparation in compatible release, preserve extracted evidence and objects; do not deploy a binary unable to read new evidence. Reupload test sources explicitly; no deletes.
Cutover trigger: all real conversion, end-to-end, runtime/packaging gates; default cutover pending proof is not represented as done.
Cleanup criteria: remove old extraction implementation/comparison coexistence after real quality and deployment acceptance; no permanent dual path.
Blast radius: current unpublished preparation only; never accounts/database/publications.
Adversarial proof: page origin/numbering/charspan, mixed OCR, tables/multipage, omitted furniture, empty/partial conversion, model absence/offline, child hang/crash/parent death, duplicate/concurrent/stale attempt, commit failure, restart/rollback, alternate decision PDF callers.

No UI parser controls, home changes, paid external extraction, migrations of test reviews or production operations. The user explicitly requires real Docling PDF tests, not mock-only evidence. Local network restrictions currently block PyPI/model installation; those gates must stay visibly unproven until executable evidence exists.

Repository architecture decision / staged implementation (#499)
Base main 68a86851b8c630dfd27da6608e2f88d1dc2f4727, tree independently verified as 0c048b715734bfcfb088b8e034ab4b22e27e44f7. Local git snapshot has the identical tree; it is not represented as the upstream commit.

Actual official SDK selected: docling-slim[format-pdf,models-local,convert-core]==2.132.0, docling-core==2.99.0; supports Python 3.12 per official tagged pyproject. The actual DocumentConverter + PdfFormatOption + PdfPipelineOptions use local CPU layout and TableFormer, batch sizes 1, two threads, queue 2. This is not NativePdfPipeline, a custom extractor, Markdown export, VLM or remote service. Official sources: https://github.com/docling-project/docling/tree/v2.132.0 and https://docling-project.github.io/docling/concepts/docling_document/ and https://docling-project.github.io/docling/usage/advanced_options/.

Stateless conversion: immutable source bytes through anonymous descriptors -> disposable subprocess -> validated JSON/Metis source contract; no writes or domain decisions by Docling. The adapter consumes complete DoclingDocument, actual iteration order, page sizes/provenance, cell structure and relationships, original/derived text and cell OCR observations. Numeric offsets are Unicode code points in Docling.text; orig is retained separately. No claim that orig or text equals a verbatim digital PDF layer. TOPLEFT/BOTTOMLEFT is validated and translated to existing page_bbox points, 1-based pages. Mapping precision remains item/cell geometry, not glyph-precise highlights.

Durable state belongs to the kernel: existing processing_attempt reservation and source checks wrap true conversion and semantic preparation; atomic result/object/envelope activation under existing local lock or PostgreSQL transaction. Complete extraction JSON, accepted fragments, hashes/model identities/settings and exclusions become processing evidence only at that commit. Review/repair/source-catalog and decision graph verification consume accepted fragments, independent of the current SDK/configuration. Legacy snapshots use their explicitly historical native contract; there is no Docling-error fallback. Source-bound v2/v3, context evidence, admission, reviewers, publication/serving authority and UI remain unchanged. Decision vector geometry still uses PyMuPDF; Docling extraction does not consume native PyMuPDF text/line reconstruction.

Limits: Linux only; 64MiB input/output, 1000 pages, 1200-second conversion ceiling capped by remaining existing 1800-second attempt, one conversion per host file lock, two CPU threads and sampled 768MiB child RSS default. These are conservative ceilings/assumptions, not a measured capacity guarantee. RSS is sampled each 50ms, NOT a cgroup hard memory ceiling. Timeout/crash kill and reap process; Linux parent-death guard kills conversion if kernel parent dies. No OCR subprocesses or automated retry. Oversize, capacity busy, absent models, partial conversion, missing geometry/charspan or unresolved multipage table mapping fail explicitly. No truncation or synthetic evidence.

Digital PDF first slice only: OCR intentionally disabled. Scans without a usable digital layer fail closed. OCR engine packaging, per-cell OCR locator/text provenance and scan comparison must be completed in a successor acceptance step. No scanned-PDF quality claim.

Model/download policy: isolated conversion interpreter via METIS_DOCLING_PYTHON; explicit prefetched model directory via METIS_DOCLING_ARTIFACTS_PATH. scripts/prepare_docling_models.py is an online BUILD command, never application boot/request code. Immutable manifest records file SHA256; worker verifies files, records installed distribution versions and model/options identity, runs HF_HUB_OFFLINE/TRANSFORMERS_OFFLINE with remote services/plugins disabled. Build manifest must remain unchanged; new software/model build means a new extraction on explicit new preparation, never rewrite an accepted source reference. Pin/resolution of the entire transitively resolved environment and a reproducible Azure artifact remain acceptance work; Dockerfile.docling-acceptance captures installed versions, but does not itself establish an Azure production package.

Staging: METIS_PDF_EXTRACTOR is server technical configuration, no user-facing control. Unset = legacy-comparison; explicit docling = new uploads/reextract using actual converter, including PDF decision route. This intentional staged coexistence is temporary. Do NOT merge/activate until the genuine PDF and full chain, compatibility and Azure gates pass. Remove old new-upload routing and extraction heuristics after that proof; historical native source readers need explicit compatibility proof before deleting their dependency. PyMuPDF source rendering/marking and vector drawing evidence remain. New Docling results are never silently produced by the old extractor after a failure.

Runtime conflict: existing Azure ZIP and its tests forbid NumPy/SciPy/scikit-learn in lean console; B1 is referenced in packaging rules. Do not relax those checks. The isolated interpreter avoids dependency pollution but does not create RAM. No Azure SKU change, paid external service or separate worker service is authorized or created. Current ordinary ZIP remains the existing staged release; it does not provision the Docling interpreter/models. Dockerfile.docling-acceptance and dedicated workflow are acceptance packaging, not a deployable Metis Azure release. Actual build plus B1 time/RSS fit is an outstanding blocking gate. If real models exceed the host budget, runtime topology/resource choice must be resolved explicitly before production cutover.

Concrete proof status:
- Local adapter/supervisor and failed-ingest/restart/replay tests run; they supplement, not replace, genuine Docling evidence.
- Real Docling tests were explicitly invoked locally: fail because the required interpreter/models are not available. PyPI is unreachable under current network policy, and no PostgreSQL executable/DSN is available. Those checks are NOT PASS.
- Dedicated workflow installs the official SDK/models before tests and executes actual PDFs offline in an isolated interpreter, plus PostgreSQL chain. Its 4096MiB acceptance budget is deliberately not a B1 fit claim.
- Test scenarios currently include concrete text, exact original locator, model/SDK identity, columns, headings/DOEN/OVERWEEG, a drawn table and two-page structure, actual PDF upload -> controlled source-bound semantic provider -> review rejection -> restart -> unchanged immutable-storage/publication block. Actual successful publication, scans, document-wide gutter behavior, cross-page paragraphs, multipage table mapping, parent-loss proof under real Docling, post-conversion commit rollback and concurrent genuine-PDF PostgreSQL preparation remain unproven; do not describe the full promise as complete.
- Existing regression suite is evidence for staged compatibility, not new-route quality. The mandatory scripts/verify_architecture_invariants.py does not exist in this main; six tests in tests/test_architecture_invariants.py are the actual repository gate.

Available user-relevant sources found locally: Smetten (46 pages), Mantelzorg decision PDF (5 pages) and Continentie (86 pages). Their presence does not prove they are exactly the current three uploaded Metis sources; Eenzaamheid original not found. No genuine comparison on any of those sources could run without Docling/models. Existing baselines must not be presented as quality gain. compare_docling_extraction.py requires explicit human-selected expected passages and emits texts/locators/exclusions/metrics; counts are not used as quality evidence.

Reupload after accepted cutover: keep existing test records intact; upload each original as explicit new source/work, verify extraction finished and original highlighted passages, review the newly formed objects and context, then satisfy existing publication conditions. Never copy old reviews or infer object continuity from similar text. Any desired deletion of old test records is a separate user-authorized cleanup, not performed here.

Rollback: disable new PDF preparation or use the explicit legacy staged route for NEW work in a compatible reader release. Keep accepted Docling records/objects/reviews unchanged; their readers resolve stored evidence without the model runtime. Do not fall back during failed conversion, or delete/reset data. Never automatically deploy an old binary that re-extracts Docling source IDs. No production operations were performed.

Acceptance follow-up (2026-10-03, before adapter correction): the actual SDK 2.132.0
list-marker processor changes `ListItem.text` but leaves a full-item `charspan`
indexing `orig`. Mantelzorg has nine such items; treating all spans as indexes in
`text` was an incorrect adapter assumption. The translation will use `orig` only
for a single full-original span where the only removed prefix is the SDK-declared
list marker and whitespace. Preserve original geometry/span and record the text
field used per binding; never clamp ranges or infer alignment for arbitrary edits.
All other invalid spans continue to fail closed. This is a source-coordinate
translation, not a new extractor or a relaxation of source evidence requirements.

Model selection follow-up: real Heron acceptance failed on column order and on
Mantelzorg mixed-page geometry. An experiment with the official Egret-large preset
resolved those two fixtures without custom extraction. Select that official
preset for the next acceptance run and pin its downloaded repository commit,
along with the TableFormer repository commit. This changes only model extraction
metadata for new work; accepted source evidence stays immutable. Re-measure all
three sources; the prior Heron resource measurements are not Egret evidence.

Current evidence is tracked in `docling-acceptance-evidence.md` and
`docling-comparison-evidence.json`; earlier local-network/Heron-only proof notes
above are historical. The selected Egret model has genuine PDF evidence on all
three available sources. The current Azure capacity is unknown (user response),
so the staged production cutover remains deliberately blocked.

### Official backend acceptance follow-up

The default ThreadedDoclingParseDocumentBackend merges the two-column synthetic
fixture on GitHub before adapter translation. SDK, model and dependency hashes
match the local run; adding the same URW standard-font package alone did not fix
it. The exact lower-level cause is not established. Test the official Docling
PyPdfiumDocumentBackend with the same StandardPdfPipeline, Egret and TableFormer;
this is a fixed SDK backend selection, never a conditional fallback. Record the
backend class in immutable extraction settings. No kernel mutation, transaction,
review or publication boundary changes. Accept this selection only after the
unchanged column test, genuine PostgreSQL recovery/concurrency/rollback proof
and original-document locator comparison pass.

Rendering fonts are a build/runtime dependency, not a user setting. The build
records the installed Linux font inventory, verifies the required standard face
hash and refuses conversion if that inventory changes. The acceptance Docker
image installs URW fonts before model preparation. These checks identify a
runtime input; they do not prove the previous column failure was font-caused or
establish production Azure fitness.
