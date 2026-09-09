# V&VN Data Services Protocol v2.34 — G2 publication activation

**Status:** Approved for project use  
**Protocol delta version:** 2.34.0  
**Approval date:** 2026-09-09  
**Approved by:** Project owner  
**Extends:** Protocol v2.33.0  
**Highest change class:** C5 publication/security  
**Normative language:** MUST, MUST NOT, SHOULD, SHOULD NOT and MAY are normative requirements

## 1. Owner decision

The project owner explicitly authorizes removal of the unconditional G2/publication blockade. This delta SUPERSEDES only earlier statements that G2 and `publish()` MUST remain unconditionally BLOCKED.

Publication is not generally open. It becomes conditionally available per snapshot and MUST remain fail-closed unless every requirement below passes at the moment of publication.

## 2. Mandatory publication gate

A snapshot MAY be published only when:

1. the actor has the `publisher` role and explicitly confirms the publication action;
2. at least one non-document knowledge object has a current `approve` review binding to its exact object ID, version, canonical hash, confirmed type, reviewer and decision;
3. required independent review and high-risk four-eyes checks pass;
4. every selected object is approved and schema-valid;
5. the immutable locator is a valid G2 Azure Blob locator;
6. the configured immutable source store can read the blob at publication time;
7. SHA-256 of those authoritative bytes equals the source hash in the captured envelope;
8. the derived retrieval projection can be built without blocked records.

An app setting, locator-shaped string, UI choice, envelope-level review flag or storage permission alone MUST NOT produce G2 PASS.

## 3. Atomic cutover and evidence

Successful publication MUST create an immutable release manifest containing release identity, protocol version, source identity and exact published object identities/hashes. The published projection MUST be replaced atomically and an append-only `release_published` event MUST identify the publisher and release.

The snapshot MUST be durably marked published only as part of the successful cutover. A failed cutover MUST restore the preceding projection and envelope state and MUST remove its incomplete manifest and ledger append. Repeating publication of an already published snapshot MUST fail closed.

The published projection remains derived and read-only. Canonical knowledge objects and frozen source bytes MUST NOT be silently rewritten by publication.

## 4. Operator surface

The Publiceren room MUST show one of three states in ordinary language:

- blocked, with the actionable reason;
- ready, with the number of reviewed knowledge objects and an explicit confirmation control;
- published, with no remaining publication-task badge for that snapshot.

The action is a separate publisher decision after review. Review approval itself MUST NOT publish.

## 5. Unchanged controls

Protocol v2.33 object-level human review, passage disposition, v2.13 four-eyes, v2.11 exact freeze bytes/locators, v2.12 derived projection, closed taxonomy and all withdrawal/supersession obligations remain in force. This delta does not activate the external Product API, create a nurse-facing UI, add an LLM, or authorize broad production rollout.
