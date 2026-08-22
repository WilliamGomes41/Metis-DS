# V&VN Data Services Protocol v2.2 — Lifecycle, Provenance and Acceptance Hardening

**Status:** Approved for project use
**Protocol version:** 2.2.0
**Approval date:** 2026-08-22
**Approved by:** Project owner
**Supersedes:** no earlier protocol; this document extends protocol v2.0 and the v2.1 Answerability/Evidence Gate
**Normative language:** MUST, MUST NOT, SHOULD, SHOULD NOT and MAY are normative requirements

## 1. Purpose

Protocol v2.2 closes lifecycle and assurance gaps exposed during development of V&VN Data Services. It adds enforceable rules for:

1. authoritative repositories, builds and releases;
2. separation of source material, fixtures, development data and independent acceptance data;
3. acquisition and identity of canonical binary and web sources;
4. formal answerability and independent acceptance;
5. change impact, schema evolution, withdrawal and downstream invalidation.

Protocol v2.2 does not weaken any v2.0 or v2.1 safety requirement. Where requirements conflict, the stricter fail-closed requirement applies.

## 2. Unchanged foundational rules

The following rules remain mandatory:

- The canonical product is the versioned and approved knowledge layer, not a chatbot, embedding index or generated answer.
- Canonical objects, publication state, retrieval projections and generated answers are separate layers.
- Approved is not published.
- Only active published objects MAY enter a production retrieval corpus.
- Retrieval similarity is not evidence of answerability.
- Unsupported, incomplete or conflicting evidence MUST result in abstention.
- AI MAY propose mappings or metadata but MUST NOT directly approve or publish canonical knowledge.
- Missing source integrity, missing required review or an unresolved conflict MUST fail closed.
- Development results MUST NOT be represented as independent acceptance.
- Holdout A remains a historical failed acceptance and MUST NOT be used for tuning or a renewed independence claim.

## 3. Conformance model

A system conforms to protocol v2.2 only when all applicable gates in section 13 pass. Conformance MUST be reported per layer; a pass in one layer MUST NOT be used to imply a pass in another.

Required status values are:

- `PASS`: all applicable requirements are demonstrably satisfied;
- `BLOCKED`: progression is intentionally prevented because required evidence is absent;
- `FAIL`: evidence shows that a requirement is not satisfied;
- `NOT_EVALUATED`: the gate has not yet been executed;
- `NOT_APPLICABLE`: the gate is outside the declared scope, with a recorded justification.

`BLOCKED` is a valid safe state. It MUST NOT be converted to `PASS` through manual assertion or model knowledge.

## 4. Authoritative repository and software supply chain

### 4.1 Source of truth

- One private remote repository MUST be designated as the authoritative software repository.
- The repository identifier, default branch and hosting organization MUST be recorded in the technical manifest.
- The protected default branch is the authoritative code baseline after v2.2 activation.
- Chat attachments, extracted archives, local worktrees and generated bundles MUST be treated as working copies unless their checksum is linked to an authoritative release.
- If two working copies differ, neither copy MAY silently overwrite the authoritative branch. The difference MUST be inspected and resolved through review.

### 4.2 Change control

- Changes to the protected default branch MUST enter through a reviewed pull request.
- Direct pushes to the protected default branch MUST be disabled, except for a documented break-glass recovery procedure.
- Required CI checks MUST pass before merge.
- At least one reviewer other than the author SHOULD approve code that affects canonical transforms, integrity, review, publication, answerability or access control.
- A pull request MUST identify the affected protocol layers and the required revalidation class from section 10.

### 4.3 Reproducible dependencies and builds

- Runtime and test dependencies MUST be explicitly version-pinned.
- Optional dependencies that alter validation behavior MUST be explicitly pinned; environmental availability MUST NOT determine validation semantics.
- CI MUST perform installation from the committed lockfiles in a clean environment.
- CI MUST execute repository preflight, compilation, architecture-invariant tests and the full test suite.
- A release artefact MUST be traceable to an immutable commit SHA and MUST include a checksum.
- Production images SHOULD be immutable and SHOULD expose the commit SHA, protocol version and build identifier.

### 4.4 Architecture-invariant CI

CI MUST fail if any of the following invariants disappears or becomes ineffective:

- Product API responses distinguish supported retrieval from abstention and expose answerability status.
- Candidate retrieval cannot bypass the Answerability/Evidence Gate.
- Retrieval projections retain structured logic required for numeric and rule-based evidence checks.
- source manifests retain stable `source_id` values.
- HTML or other non-page provenance retains a stable source locator.
- source integrity remains fail closed when exact bytes or a verified checksum are absent.
- fixture mode remains explicitly marked and cannot be mistaken for a real published corpus.

## 5. Data and evidence classes

Every dataset or artefact MUST be assigned exactly one primary class.

| Class | Purpose | Mutability | Permitted evidence claim |
|---|---|---|---|
| Canonical source | Official source content | Immutable after registration | Source integrity |
| Raw extraction | Deterministic representation of a source | New version on change | Extraction traceability |
| Canonical knowledge | Reviewed semantic truth layer | New object version on change | Approved knowledge |
| Test fixture | Deterministic software testing | Reviewed code change only | Software behavior only |
| Development set | Design, tuning and calibration | Versioned and mutable | Development performance only |
| Independent holdout | Locked acceptance evaluation | Immutable after lock | Independent performance |
| Runtime output | Operational result, cache, log or database | Mutable | No baseline or acceptance claim |
| Confidential review artefact | Reviewer input and audit evidence | Controlled and immutable | Review evidence only |

### 5.1 Storage boundaries

- Tests MUST NOT depend on mutable runtime-output paths.
- Safe test fixtures MUST live in a stable fixture directory and MUST state their origin and limitations.
- Runtime outputs, secrets, caches, source binaries and confidential review artefacts MUST NOT be committed to the software repository.
- Independent holdouts MAY be committed only when access classification permits it and the lock metadata does not expose confidential or personally identifiable information.
- A fixture derived from unverified source material MUST NOT be described as canonical or publication eligible.

### 5.2 Dataset identity

Development sets and holdouts MUST record:

- stable dataset ID and version;
- scope and source coverage;
- creator and creation date;
- content checksum;
- intended use;
- prohibited use;
- contamination status;
- applicable protocol and engine version.

## 6. Canonical source acquisition and identity

### 6.1 Common requirements

A canonical source registration MUST contain:

- stable `source_id`;
- publisher and title;
- declared source version and publication date when available;
- source type and canonicality;
- acquisition timestamp in UTC;
- acquisition method;
- exact stored byte length;
- SHA-256 computed by the trusted pipeline over the stored bytes;
- immutable storage locator;
- content type and filename or equivalent object identity;
- integrity status and publication eligibility.

A URL without captured and hashed bytes is not sufficient proof of source identity.

### 6.2 PDF, XML and other binary sources

- The exact source bytes MUST be captured before canonical extraction.
- SHA-256 MUST be recomputed from the stored bytes during verification.
- A checksum supplied in metadata but not recomputed by the trusted pipeline MUST NOT establish `verified` integrity.
- Extraction coordinates MUST use the native source coordinate system where available.

### 6.3 HTML and mutable web sources

For HTML, the acquisition record MUST additionally contain:

- requested URL and final URL after redirects;
- HTTP status;
- response content type and character encoding;
- exact response-body bytes;
- redirect chain when present;
- retrieval timestamp;
- rendering mode: raw response, rendered DOM export or official generated document;
- capture-tool name and version.

The chosen rendering mode MUST be declared before extraction. Raw HTML, rendered DOM and an official generated PDF are distinct source representations and MUST have distinct checksums. One representation MUST NOT silently inherit the canonical status of another.

Scripts, styles, advertisements or navigation MAY be excluded from semantic extraction, but their exclusion MUST NOT alter the registered source checksum. Extraction rules determine what is interpreted; source registration preserves what was acquired.

### 6.4 Source change and differential review

- A changed checksum creates a new source version or source snapshot.
- A new snapshot MUST trigger deterministic re-extraction and object-level differential comparison.
- Unchanged canonical object hashes MAY retain review evidence if the review policy and schema version remain compatible.
- Changed clinical meaning, structured logic, provenance or risk fields MUST trigger the applicable review again.
- The prior source and knowledge versions MUST remain auditable.

## 7. Answerability/Evidence contract

### 7.1 Separation from retrieval

The required execution chain is:

`query -> query specification -> candidate retrieval -> evidence evaluation -> answerability decision -> supported results or abstention`

- Retrieval components MAY rank candidates but MUST NOT declare a query answerable.
- The answerability component MUST evaluate explicit evidence requirements against published canonical knowledge.
- Only `supported` evidence MAY be supplied to a future answer-generation layer.

### 7.2 Query specification

The query specification SHOULD include, where applicable:

- subject;
- intent;
- required concepts;
- requested relations;
- numeric constraints;
- required output type;
- population or patient context;
- temporal or version context.

Parsing uncertainty that affects the evidence requirement MUST result in abstention or an explicit clarification flow; it MUST NOT be resolved through unsupported inference.

### 7.3 Decision states

The answerability decision MUST use at least:

- `supported`;
- `insufficient_evidence`;
- `conflicting_evidence`.

An implementation MAY add more detailed states, but they MUST map unambiguously to supported or abstain behavior.

### 7.4 Required reason codes

Abstention MUST expose a stable reason code. The controlled vocabulary MUST include at least:

- `empty_published_corpus`;
- `required_concept_not_present`;
- `required_relation_not_present`;
- `structured_constraint_mismatch`;
- `patient_specific_context_not_available`;
- `conflicting_evidence`;
- `below_confidence_threshold`;
- `version_context_not_satisfied`.

### 7.5 Evidence sufficiency

- Subject overlap without the requested relation is insufficient evidence.
- A numeric candidate with a mismatching field, operator, threshold, unit or score is insufficient evidence.
- Evidence from different objects MAY be combined only through an explicit compatible evidence cluster.
- Every supporting object in a cluster MUST be active, published, entitled and source-traceable.
- Conflicting active evidence MUST result in `conflicting_evidence` and abstention until resolved.
- Similarity score MUST NOT override a failed evidence requirement.

## 8. Independent acceptance

### 8.1 Dataset independence

- An independent holdout MUST be locked and hashed before evaluation.
- Persons or systems tuning retrieval or answerability MUST NOT inspect holdout labels or use holdout results to change the evaluated engine.
- Any engine or threshold change made in response to holdout results contaminates that holdout for renewed independence claims.
- Specification-only corrections MAY be made only when query text, intended behavior and engine configuration remain unchanged; every correction MUST be versioned and justified.
- After contamination, a new independent holdout is required.

### 8.2 Required composition

An independent acceptance set MUST include:

- answerable and unanswerable queries;
- lexical variations and paraphrases;
- concept-overlap no-answer cases;
- relation-mismatch cases;
- numeric and operator-confusion cases where the source contains structured logic;
- context and population mismatches;
- version or supersession cases where applicable;
- clinically high-risk questions proportionate to the release scope.

No-answer cases MUST be designed to test plausible false support, not only unrelated out-of-domain questions.

### 8.3 Metrics and reporting

At minimum, acceptance MUST report:

- False Answer Rate with numerator and denominator;
- correct abstention rate;
- answerable-query support rate;
- expected-object hit rate and object recall at the declared `top_k`;
- results stratified by risk and false-positive class;
- exact engine, configuration, source release and dataset checksums.

The pilot safety target remains FAR = 0% on independent no-answer data. A reported 0% MUST always include the number of no-answer cases and a confidence interval. It MUST NOT be described as proof that the true FAR is zero.

### 8.4 Minimum sample decision

The exact minimum sample size is a governance decision and MUST be fixed before holdout B is created. Until fixed, the following technical recommendation applies:

- at least 50 no-answer cases;
- at least 50 answerable cases;
- coverage of every applicable false-positive class;
- at least 20 high-risk structured or clinical decision cases when the released scope contains such knowledge.

Smaller pilots MAY be reported as exploratory evidence but MUST NOT open the independent acceptance gate.

## 9. Schema and API evolution

- Every schema and external API contract MUST have an explicit version.
- Existing schema files MUST NOT be mutated after use in a release; a changed contract requires a new version.
- Breaking and non-breaking changes MUST be identified in the pull request and release notes.
- Migration MUST be deterministic, testable and auditable.
- Migration that changes canonical meaning, structured logic, provenance, risk or source identity MUST create a new canonical object version and trigger impact review.
- A purely representational migration MAY retain clinical review only when object meaning and the exact review snapshot remain demonstrably equivalent.
- Supported API versions and deprecation dates MUST be published to consumers.
- Contract tests MUST protect required fields including answerability, reason codes, source metadata and knowledge object IDs.

## 10. Change-impact and revalidation classes

Every material change MUST be assigned the highest applicable class.

| Class | Example | Mandatory revalidation |
|---|---|---|
| C0 Documentation | Typo with no normative or behavioral effect | Documentation review |
| C1 Software-internal | Refactor with byte-identical outputs | CI, invariant tests, full regression |
| C2 Extraction/projection | Extractor, locator or retrieval projection change | C1 plus deterministic regeneration and object/projection diff |
| C3 Canonical/review | Schema, semantic transform, canonical hash or review logic change | C2 plus affected clinical/technical review and publication gate |
| C4 Retrieval/answerability | Ranking, embeddings, thresholds, query parser or evidence rules | C1 plus development evaluation and a new independent holdout before acceptance claim |
| C5 Publication/security | Eligibility, release, entitlement, withdrawal or identity change | C1 plus authorization, negative security tests and operational rollback verification |
| C6 Generation | Answer/RAG prompt, model, claim validator or evidence assembly change | C4 plus claim-level generation acceptance and safety evaluation |

If a change spans classes, all requirements of the highest class and all relevant lower classes apply.

## 11. Publication, withdrawal and downstream invalidation

### 11.1 Publication

- Publication MUST reference immutable canonical object versions and an immutable release manifest.
- The release manifest MUST record release ID, release version, owner, timestamp, included objects, source checksums and protocol version.
- Publication MUST NOT mutate canonical object content.
- Retrieval indexes MUST be derived only from the active publication registry.

### 11.2 Emergency unpublish

- An authorized release owner MUST be able to remove an object or release from external visibility without deleting canonical history.
- Emergency unpublish MUST be auditable and MUST record actor, time, reason and affected consumers or tenants.
- Production targets MUST define and test a maximum withdrawal time before go-live.
- A break-glass unpublish MAY use one authorized actor when delay creates greater clinical risk; retrospective second-person review MUST then occur within a governance-defined interval.

### 11.3 Downstream invalidation

Withdrawal MUST invalidate or rebuild, as applicable:

- retrieval projections;
- lexical, vector and hybrid indexes;
- API and edge caches;
- generated evidence caches;
- consumer update feeds.

Automated verification MUST demonstrate that withdrawn objects are no longer returned. Republishing requires a new release decision; it MUST NOT happen automatically when infrastructure recovers.

## 12. Future Answer/RAG layer

An Answer/RAG layer remains optional and separate from the Knowledge API. Before it can be accepted:

- independent retrieval and answerability acceptance MUST pass;
- generation MUST receive only evidence marked `supported`;
- every clinical claim MUST map to one or more supporting knowledge object IDs;
- numeric values, units, operators, negations and conditions MUST be validated against structured evidence;
- the model MUST NOT use general model knowledge to fill a V&VN evidence gap;
- unsupported or partially supported output MUST be blocked or converted to abstention;
- source citations MUST identify source version and location;
- model, prompt, claim-validator and evidence-assembly versions MUST be logged;
- query logging MUST comply with privacy and retention rules.

Changing the model or claim-validation logic is a C6 change.

## 13. Protocol v2.2 gates

### Gate G1 — Repository baseline

PASS requires:

- authoritative private remote recorded;
- protected default branch;
- pull-request workflow;
- required CI checks;
- clean lockfile installation;
- release and commit traceability.

### Gate G2 — Source integrity

PASS per source requires exact acquired bytes, trusted-pipeline SHA-256, immutable storage identity and valid provenance. A URL or reconstructed content alone is insufficient.

### Gate G3 — Canonical transform and review

PASS requires deterministic extraction/transform, resolvable lineage, schema validity, required clinical/technical review and second review for high-risk objects.

### Gate G4 — Publication eligibility

PASS requires G2 and G3, an authorized release decision and successful fail-closed prepublication checks.

### Gate G5 — Retrieval and answerability development

PASS requires invariant tests, declared development metrics, false-positive-class coverage and explicit separation of retrieval from answerability.

### Gate G6 — Independent acceptance

PASS requires a locked uncontaminated holdout, predeclared acceptance criteria, complete metric reporting and FAR meeting the governance-approved target.

### Gate G7 — Answer/RAG acceptance

PASS requires G6 plus claim-level evidence validation, citation correctness, unsupported-claim blocking and generation safety evaluation.

### Gate G8 — Production readiness

PASS requires production identity and tenant isolation, secret management, audit and privacy controls, monitoring, tested emergency withdrawal, backup/recovery and an approved operational owner.

No later gate MAY pass while a required earlier gate is `BLOCKED`, `FAIL` or `NOT_EVALUATED`.

## 14. Required assurance record

Each release candidate MUST produce a machine-readable or equivalent immutable assurance record containing:

- protocol version;
- commit SHA and build ID;
- dependency-lock checksum;
- source IDs and checksums;
- schema and transform versions;
- canonical release ID;
- review status summary;
- CI and invariant-test results;
- retrieval and answerability configuration hashes;
- development dataset IDs;
- independent holdout ID and lock checksum when applicable;
- gate status with evidence references;
- unresolved blockers and risk acceptance, if any.

An assurance record describes evidence; it MUST NOT override a failed or blocked gate.

## 15. Current project mapping at approval

| Gate | Current status | Reason |
|---|---|---|
| G1 Repository baseline | BLOCKED — temporary control accepted | `WilliamGomes41/VENVN-DS` with default branch `main` is the authoritative private remote and Step 12C was squash-merged as commit `1b7c068504432dc9799bf7364b264ef772851b00`. Until an appropriate V&VN GitHub Team or Enterprise organization is available, changes MUST use feature branches, pull requests and successful CI; direct changes to `main` are procedurally prohibited but not technically blocked. G1 cannot become PASS under this exception. |
| G2 Source 1 integrity | BLOCKED | Exact canonical PDF bytes not verified by trusted-pipeline SHA-256 |
| G2 Source 2 integrity | BLOCKED | Exact official HTML/PDF representation not acquired and hashed |
| G3 Source 1 review | PASS with source-integrity dependency | Clinical and second review complete; publication still blocked by G2 |
| G3 Source 2 review | NOT_EVALUATED | Canonical transform and clinical review not started |
| G4 Publication eligibility | BLOCKED | Source-integrity gates are blocked |
| G5 Development retrieval/answerability | PASS | Development FAR 0%; not independent evidence |
| G6 Independent acceptance | NOT_EVALUATED | Holdout A remains historical FAIL; holdout B not created |
| G7 Answer/RAG acceptance | BLOCKED | G6 has not passed |
| G8 Production readiness | NOT_EVALUATED | Azure DEV and operational controls not established |

## 16. Governance decision register

Approval of v2.2 establishes the framework but does not silently choose operational policy. The project owner owns the following decisions and MUST record each value before the stated gate. A missed deadline blocks that gate.

| ID | Decision | Owner | Required specialist input | Deadline gate | Status |
|---|---|---|---|---|---|
| GD-01 | Minimum independent holdout size and required high-risk composition | Project owner | Clinical governance and evaluation lead | Before Holdout B is created or exposed to the evaluated team | OPEN |
| GD-02 | Statistical reporting method and confidence level for FAR | Project owner | Evaluation/statistics reviewer | Before Holdout B acceptance criteria are frozen | OPEN |
| GD-03 | Required reviewer count for C3–C6 pull requests | Project owner | Technical and clinical governance | Before the next C3, C4, C5 or C6 change is merged | OPEN |
| GD-04 | Maximum emergency-withdrawal time and retrospective break-glass review interval | Project owner | Clinical safety and operations | Before Azure DEV is opened to external pilot users | OPEN |
| GD-05 | Supported API deprecation period | Project owner | Product/API owner | Before the first external API consumer is onboarded | OPEN |
| GD-06 | Retention periods for acquisition records, audit logs, usage logs and confidential review evidence | Project owner | Privacy, security and records management | Before Azure DEV processes external pilot traffic | OPEN |
| GD-07 | Named operational owner for production releases and emergency withdrawal | Project owner | V&VN service ownership | Before any external pilot release is authorized | OPEN |

## 17. Approval record

Protocol v2.2.0 was approved by the project owner on 2026-08-22 for use in the V&VN Data Services project. Technical implementation remains governed by the fail-closed gates in section 13.

- The decisions in section 16 have a named owner and gate-based deadline.
- Approval does not convert any `BLOCKED`, `FAIL` or `NOT_EVALUATED` gate to `PASS`.
- Clinical, privacy/security and operational approval remain required where their applicable gate or decision deadline states so.
- The immutable checksum and repository commit SHA MUST be recorded in the protocol approval manifest after merge to the authoritative `main` branch.
