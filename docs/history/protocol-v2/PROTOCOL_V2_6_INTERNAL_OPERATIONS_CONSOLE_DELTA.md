# V&VN Data Services Protocol v2.6 — Internal Operations Console

**Status:** Approved for project use  
**Protocol delta version:** 2.6.0  
**Approval date:** 2026-08-28  
**Approved by:** Project owner  
**Extends:** Protocol v2.5.0  
**Highest change class:** C5 (identity/access) spanning C3 (review/publish loop)  
**Normative language:** MUST, MUST NOT, SHOULD, SHOULD NOT and MAY are normative requirements

## 1. Purpose

Protocol v2.6 places an **internal operations console** explicitly in V&VN Data Services scope. The console is a human surface over the knowledge kernel for guideline researchers and reviewers. It is not a care-app frontend, not a chatbot, not an EPD/ECD UI, and not a public website.

Protocol v2.2.0, v2.3.0, v2.4.0, v2.5.0 and this delta jointly form normative baseline v2.6.0. This delta is a **scoped supersession** of the v2.4 reading that there is **no product frontend in this repository**. Where this delta and earlier protocol text conflict on that repository-boundary point, this delta governs. For all other requirements, the stricter fail-closed requirement applies.

This protocol-only change authorizes scope. It does not implement UI or product code. Do not claim the console exists in code.

## 2. What remains forbidden in this repository

The following MUST NOT live in this repository, and MUST NOT be represented as part of V&VN DS merely because they might consume DS output:

- a care-app frontend;
- a chatbot as a product surface;
- an EPD/ECD UI;
- a public website.

A reference application remains a separate consuming product under Protocol v2.4. Chat is not a room in this console. Any chat is a later consumer of the Product API only, under G7/C6 and U1/U2. A chatbot MUST NOT be added to the console as a fifth room or as a substitute for ingest, review, publish or analytics.

## 3. What this repository MAY contain

An **internal operations console** MAY live in this repository, or in a tightly bound package in the same product, as a human surface over the knowledge kernel.

The four rooms are not four buttons for one person. They are distinct operational rooms with distinct acts and, where identity is in force, distinct authorized roles.

## 4. Architecture

V&VN Data Services comprises, with this delta:

1. **Validated knowledge objects:** modular, versioned, source-traceable guideline content with publication state and controlled metadata (unchanged kernel).
2. **Immutable source store:** captured official source bytes and linked extras, addressed by SHA-256 and locator, not published by capture alone.
3. **Internal operations console:** an intuitive console for guideline researchers and reviewers. This is the human door over the kernel.
4. **Knowledge service / Product API:** a versioned machine-readable interface that supplies only entitled, active and published knowledge. The Product API remains a separate machine door for apps. Console users MUST NOT treat the console as the Product API.
5. **Internal inspection tooling:** the existing read-only inspection layer remains inspection. It is not the operations console and is not a care-app frontend.

Frontend of the console: human rooms for ingest, review, publish and later analytics.

Backend of the console: the immutable source store plus canonical knowledge objects. Console ingest, review and publish MUST operate on that kernel. They MUST NOT silently mutate published truth.

## 5. Four rooms

### 5.1 Ingest (mailbox)

Ingest is the mailbox. The guideline research team submits official HTML/PDF and linked extras (metadata, annexes).

- Envelope in, receipt out. The receipt MUST include SHA-256, locator, and a captured-not-published state.
- Engineers MUST NOT submit sources through this room.
- At ingest the researcher MUST select reviewers. Selecting reviewers at ingest requires identity.
- Capture is not publication. A captured snapshot MUST remain unpublished until the publish room authorizes it.

### 5.2 Review

Review replaces Excel. The reviewer works on the exact snapshot’s objects.

The return loop is mandatory:

- reject or correction MUST create a new object version or block the old one;
- review MUST NEVER silently mutate published truth.

Independence / uploader rule:

- The uploader MAY also be a reviewer.
- The uploader MUST NOT be the only required reviewer on that snapshot.
- Publish stays BLOCKED until at least one other named reviewer has passed the same snapshot.
- This MUST be enforced in the console (accounts), not as a social rule.

### 5.3 Publish

Publish is a separate authorized act on a reviewed snapshot. After publish, the Product API may serve those objects. Publish is not the same click as ingest.

### 5.4 Analytics

Analytics is last, after real traffic. It MAY report ingest counts, review bounce-backs, abstains and retrieval misses.

Analytics MUST NOT expose raw source bytes or confidential review notes. Analytics MUST NOT be used to tune Holdout B. Do not build analytics first.

## 6. Identity

Accounts and roles are required when the console is implemented. At least the following roles MUST exist:

- researcher;
- reviewer;
- publisher.

No shared login for review or publish. This is internal identity, not public signup.

Selecting reviewers at ingest requires identity. This delta records identity as a required console capability. It does not by itself close G8 or provision Azure AD. Implementation and provider remain subject to G0 for the target environment.

AI, Grok Bot, Metis, the Implementation engineer and the Auditor MUST NOT count as required reviewers, MUST NOT approve, and MUST NOT publish.

Named human reviewers remain unstaffed. This delta does not invent names. Console identity is how those humans will later log in.

## 7. Console MVP order

Do not build analytics first.

1. **Console MVP:** ingest + review-loop.
2. **Third room:** publish. Publish is a small third room after the review-loop exists.
3. **Analytics:** only after real traffic.

Console ingest requires an immutable store:

- Azure Blob when G0 Azure DEV PASSes;
- local `sources/private/` substitute is allowed for G0 Local and is explicitly not production.

Console work MUST NOT replace Fase 2. ROADMAP MUST place console implementation after bron 2 storage is at least capturable (bytes + hash + locator path), not instead of Fase 2.

## 8. Unchanged fail-closed rules

The following rules remain mandatory and are not relaxed by this delta:

- Canonical source binaries (HTML, PDF and other official source bytes) MUST NOT be committed to Git.
- Secrets, API keys, passwords, certificates and private keys MUST NOT be committed.
- `config/tenants.v1.json` MUST remain an empty tenant list in the repository.
- Confidential review artefacts MUST NOT be committed.
- Runtime databases and local runtime state MUST NOT be committed.
- GD-03 remains ESTABLISHED as written. This delta does not reopen GD-03.
- Holdout B MUST NOT be tuned from console analytics or any other operational metric.

`.gitignore` already covers the source, secret, tenant, review and runtime classes and MUST be kept.

## 9. Change class and review

This is a protocol version change, not a silent C0 documentation edit. The change class is a new product/architecture surface + identity + review route. Treat the highest class as **C5** (identity/access) spanning C3 (review/publish loop).

This delta is owner-approved. Named C5 reviewers are not yet staffed. Retrospective independent technical and security/operations review remains due, using the same pattern as Protocol v2.5 / PR #16 (and HANDOFF.md for PR #4 and PR #5).

Any later implementation of the console, identity provider, review enforcement or publish authorization remains separately classified, including at least C5 spanning C3.

## 10. Gates and approval effect

Approval of v2.6 establishes the internal operations console as authorized DS scope. It does not:

- implement the console, any room, or any account;
- claim that the console exists in code;
- select an identity vendor or provision Azure AD;
- convert G0 Azure DEV, G7 or G8 to PASS;
- skip Fase 2 or substitute console work for bron 2 durable storage;
- publish a source or knowledge object;
- authorize an external consumer;
- add a care-app frontend, chatbot, EPD/ECD UI or public website;
- put chat in the console;
- authorize source binaries, secrets or confidential review artefacts in Git;
- close GD-01, GD-02, GD-04, GD-05, GD-06 or GD-07;
- reopen or alter GD-03;
- staff named human reviewers.

The immutable checksum and authoritative merge commit MUST be recorded after merge in the protocol approval manifest.
