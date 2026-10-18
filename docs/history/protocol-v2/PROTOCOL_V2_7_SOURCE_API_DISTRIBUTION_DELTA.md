# V&VN Data Services Protocol v2.7 — First-wave Source, Retrieve-and-Abstain API, and Distribution

**Status:** Approved for project use  
**Protocol delta version:** 2.7.0  
**Approval date:** 2026-08-28  
**Approved by:** Project owner  
**Extends:** Protocol v2.6.0  
**Highest change class:** C5 (identity/access / publication / entitlement) spanning C3 (source/review/publish loop)  
**Normative language:** MUST, MUST NOT, SHOULD, SHOULD NOT and MAY are normative requirements

## 1. Purpose

Protocol v2.7 records the owner-approved design grilling of 2026-08-28. It adds first-wave source, object-level retrieve-and-abstain API, distribution and later-analytics rules to V&VN Data Services.

Protocol v2.2.0, v2.3.0, v2.4.0, v2.5.0, v2.6.0 and this delta jointly form normative baseline v2.7.0. All Protocol v2.6 console rules remain in force. This protocol-only change does not implement UI or product code. Do not claim the console exists in code.

This delta is a **scoped supersession** of Protocol v2.4 §10 ("V&VN DS content MUST NOT be offered or described as general model-training data within the MVP") only as specified in section 5. Where this delta and earlier protocol text conflict on that training-licence point, this delta governs. For all other requirements, the stricter fail-closed requirement applies.

## 2. Unchanged v2.6 console rules

The internal operations console remains authorized DS scope and remains unbuilt. Every rule in Protocol v2.6.0 remains mandatory, including:

- four rooms that are not four buttons for one person: ingest (mailbox), review (mandatory return loop; the uploader MAY also be a reviewer and MUST NOT be the only required reviewer), publish (a separate authorized act), analytics last;
- identity (researcher, reviewer, publisher); no shared login for review or publish; internal identity, not public signup;
- chat is not a room in this console;
- a care-app frontend, a chatbot as a product surface, an EPD/ECD UI and a public website MUST NOT live in this repository;
- console work MUST NOT replace Fase 2; console implementation starts after bron 2 storage is at least capturable (bytes + hash + locator path), not instead of Fase 2.

Do not skip Fase 2 bron 2 storage. The console remains approved-not-built. The next concrete task remains bron 2 storage.

## 3. First-wave source

First-wave official files MUST be the HTML page and the PDF only.

- kennisplatform `story.html` boom players MUST be out of the first wave.
- The official file MUST be the kennisplatform freeze, not a living Word document.
- Ingest MUST accept a file upload or a URL.
- A URL MUST be snapshotted to exact bytes immediately at ingest. Capture is not publication.
- The console source tree MUST present one trunk guideline plus hashed branch documents. This is researcher UX only. It MUST NOT be a nurse decision tree.
- A new guideline version MUST create a new snapshot and an object-level differential comparison. The old release MUST stay live until cutover publish.

Linked extras (metadata, annexes) remain as in Protocol v2.6. They are not first-wave official files.

## 4. Product API

The Product API MUST retrieve at object level only.

- Unpublished branch objects MUST abstain even if the trunk is published.
- A `supported` result MUST carry V and VN labels.
- DS MUST NOT generate prose.
- abstain MUST be a closed sentence catalog maintained in the console and reviewed like a tiny guideline.
- No LLM in the MVP. A hosted LLM MUST NOT be required or introduced for the MVP Product API or console.
- Tenant means who MAY call the API.
- The Product API MUST serve all published V and VN objects to an entitled tenant.
- DS MUST NOT store hospital protocols, adoption lists, or patient data.

Object-level retrieve is not a nurse decision tree and is not prose generation. Similarity remains not answerability.

## 5. Distribution

The DS asset is live curation.

- The default product MUST be a live retrieve-and-abstain subscription.
- Training MAY exist only as a second licence, and only if the client still calls DS at question time to check published status.
- The first paying subscriber MUST be a Dutch EPD/ECD.
- Hospital or university LLM bots MAY subscribe the same way. DS MUST NOT build those bots.

A live retrieve-and-abstain subscription is not permission to train. Technical access remains never automatically a licence, V&VN approval or permission for model training. The second training licence is the only training route this delta permits, and it still requires a live published-status check at question time.

DS does not build EPD/ECD software, hospital bots or university bots. Those consumers MAY call the Product API under the same retrieve-and-abstain subscription.

## 6. Analytics later

Analytics remains last, after real traffic, as in Protocol v2.6.

When analytics is built it MAY report which objects were asked.

Care-impact research is out of DS. DS MUST NOT perform care-impact research.

DS MUST NOT be federated learning.

Analytics MUST NOT expose raw source bytes or confidential review notes. Analytics MUST NOT be used to tune Holdout B. Do not build analytics first.

## 7. Unchanged fail-closed rules

The following rules remain mandatory and are not relaxed by this delta:

- Canonical source binaries (HTML, PDF and other official source bytes) MUST NOT be committed to Git.
- Secrets, API keys, passwords, certificates and private keys MUST NOT be committed.
- `config/tenants.v1.json` MUST remain an empty tenant list in the repository.
- Confidential review artefacts MUST NOT be committed.
- Runtime databases and local runtime state MUST NOT be committed.
- GD-03 remains ESTABLISHED as written. This delta does not reopen GD-03.
- Holdout B MUST NOT be tuned from console analytics or any other operational metric.
- AI, Grok Bot, Metis, the Implementation engineer and the Auditor MUST NOT count as required reviewers, MUST NOT approve, and MUST NOT publish.

`.gitignore` already covers the source, secret, tenant, review and runtime classes and MUST be kept.

G1 technical protection remains ON. The authoritative remote remains public under Protocol v2.5 during the declared MVP period. G0 Azure DEV remains BLOCKED. No Vercel, Neon, or LLM vendor.

## 8. Change class and review

This is a protocol version change, not a silent C0 documentation edit. The change class is source/review/publish plus publication, entitlement and API access. Treat the highest class as **C5** (identity/access / publication / entitlement) spanning C3 (source/review/publish loop).

This delta is owner-approved. Named C5 reviewers are not yet staffed. Retrospective independent technical and security/operations review remains due, using the same pattern as Protocol v2.6 / PR #18, Protocol v2.5 / PR #16 (and HANDOFF.md for PR #4 and PR #5).

Any later implementation of first-wave source capture, object-level retrieve, unpublished-branch abstain, the abstain sentence catalog, tenant entitlement, a training licence or analytics remains separately classified, including at least C5 spanning C3.

## 9. Gates and approval effect

Approval of v2.7 establishes the first-wave source, retrieve-and-abstain API and distribution rules. It does not:

- implement the console, any room, any account, or any Product API behaviour change;
- claim that the console exists in code;
- skip Fase 2 or substitute console work for bron 2 durable storage;
- select an identity vendor, provision Azure AD, or convert G0 Azure DEV, G7 or G8 to PASS;
- introduce Vercel, Neon or an LLM vendor;
- publish a source or knowledge object;
- authorize an external consumer or onboard the first paying subscriber;
- add a care-app frontend, chatbot, EPD/ECD UI or public website;
- put chat in the console;
- store hospital protocols, adoption lists or patient data;
- authorize source binaries, secrets or confidential review artefacts in Git;
- close GD-01, GD-02, GD-04, GD-05, GD-06 or GD-07;
- reopen or alter GD-03;
- staff named human reviewers.

The immutable checksum and authoritative merge commit MUST be recorded after merge in the protocol approval manifest.
