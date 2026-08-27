# V&VN Data Services Protocol v2.4 — Product, Distribution and External Use

**Status:** Approved for project use  
**Protocol delta version:** 2.4.0  
**Approval date:** 2026-08-27  
**Approved by:** Project owner  
**Extends:** Protocol v2.3.0  
**Normative language:** MUST, MUST NOT, SHOULD, SHOULD NOT and MAY are normative requirements

## 1. Purpose

Protocol v2.4 defines what V&VN Data Services (DS) is as a product, which outputs it may supply, how external parties may use those outputs and where V&VN DS responsibility ends.

Protocol v2.2.0, v2.3.0 and this delta jointly form normative baseline v2.4.0. Where requirements conflict, the stricter fail-closed requirement applies.

## 2. Product model and repository boundary

The canonical product remains the versioned and approved knowledge layer. V&VN DS comprises:

1. **Validated knowledge objects:** modular, versioned, source-traceable guideline content with publication state and controlled metadata.
2. **Knowledge service / Product API:** a versioned machine-readable interface that supplies only entitled, active and published knowledge and exposes answerability, abstention and provenance.
3. **Internal inspection tooling:** read-only tooling for authorized review, verification and operations. Inspection is not a product frontend.

A reference application MAY consume the Product API to demonstrate safe use, but it is a separate consuming product with its own repository, owner, protocol scope, validation and release decision. A chatbot, end-user frontend, EPD/ECD integration, generation layer or clinical decision system MUST NOT be represented as part of V&VN DS merely because it consumes DS output.

## 3. Use-mode classification

Every consuming implementation MUST declare exactly one highest applicable use mode before onboarding or release.

| Mode | Description | DS MVP status |
|---|---|---|
| U1 Source navigation | Contextual link or pointer to the relevant canonical source/location | In scope |
| U2 Knowledge response | Retrieval or presentation of validated knowledge objects with provenance and abstention | In scope |
| U3 Deterministic decision rule | Explicit IF-THEN logic derived from guideline content | Outside MVP; separate approval required |
| U4 Patient-specific recommendation | Combines DS knowledge with individual patient/client data | Outside MVP |
| U5 Predictive or trained model | Learns or predicts from clinical data or uses guideline content as training material | Outside MVP |

A consumer MUST NOT present U1 or U2 output as U3–U5 functionality. Moving to a higher mode is a new product and responsibility decision, not a UI change.

## 4. MVP boundaries

The first V&VN DS MVP is limited to U1 and U2.

The MVP:

- MUST provide stable object identifiers, source version and resolvable provenance;
- MUST preserve the distinction between retrieval and answerability;
- MUST abstain when evidence is absent, incomplete, conflicting, out of scope or context-dependent beyond available evidence;
- MUST NOT generate or infer patient-specific recommendations;
- MUST NOT silently convert narrative considerations into deterministic decision rules;
- MUST NOT use general model knowledge to fill an evidence gap;
- MUST NOT require a hosted LLM or model-training route;
- MUST NOT process patient records as part of the DS knowledge service.

## 5. External-use contract

Before an external consumer receives non-fixture DS content, an approved machine-readable consumer registration and legal/organizational use agreement MUST define:

- consumer and accountable owner;
- declared use mode and intended users;
- API/schema version and environments;
- allowed content, purpose and presentation;
- attribution and canonical-source linking;
- authentication, authorization and data classifications;
- caching, retention and refresh policy;
- update, supersession and withdrawal handling;
- incident, error and misuse reporting;
- monitoring and audit evidence;
- prohibited transformations and claims;
- termination and data-deletion duties where applicable.

Technical access MUST NOT be treated as permission to:

- use V&VN content as model-training or fine-tuning data;
- create or market a V&VN-approved decision rule;
- imply V&VN certification, endorsement or conformity;
- remove provenance, version, status, warnings or abstention;
- continue serving superseded or withdrawn content;
- combine DS output with patient data without a separately approved U4 scope.

Whether and under what licence external reuse is legally permitted remains a separate legal decision. DS technical conformance MUST NOT be represented as legal permission.

## 6. Responsibilities

| Actor | Minimum responsibility |
|---|---|
| V&VN guideline owner | Source guideline meaning, formal status and authoritative changes |
| V&VN DS | Source integrity, deterministic transformation, knowledge-object lineage, review state, publication, withdrawal feed, API contract and auditability |
| Consuming supplier/developer | Correct integration, declared use mode, presentation, local security, context handling, update processing and compliance with the external-use contract |
| Care organization | Local governance, implementation, access, training, monitoring, incident response and fitness for the care process |
| Care professional | Professional assessment and decision-making within applicable law and professional standards |

V&VN DS MUST NOT accept responsibility for an external consumer's undisclosed transformations, patient-context logic, model behavior or failure to process updates. This boundary MUST NOT be used to waive responsibility for DS defects within the DS-controlled layer.

## 7. Interoperability and consumer readiness

Published knowledge objects and external API contracts MUST support:

- stable identifiers and explicit schema/API versions;
- status values for active, superseded, withdrawn and blocked content;
- source title, version, location and canonical link;
- audience, population, setting and applicability metadata where reviewed and available;
- machine-readable change and withdrawal events or an equivalent polling contract;
- deterministic contract tests for required fields and status behavior.

Terminology mappings such as SNOMED CT MAY be added only as separately versioned and reviewed mappings. A terminology code MUST NOT create a clinical decision rule by implication.

## 8. Change, notification and withdrawal lifecycle

For every source or canonical-knowledge change, DS MUST support the chain:

`new source snapshot -> integrity verification -> deterministic diff -> impact classification -> required review -> new publication decision -> consumer notification -> supersession or withdrawal of prior version`

External consumers MUST acknowledge or demonstrably process changes and emergency withdrawals within a governance-defined service level before external pilot release. Withdrawal MUST remain fail closed as required by Protocol v2.2.

## 9. Reference application and partner pilot

A reference application is optional and separate from DS. It MAY demonstrate U1 or U2 only after the applicable DS gates pass. It MUST consume the same published Product API available to the declared consumer class and MUST NOT bypass DS gates through local fixtures in a pilot claim.

The first external integration pilot SHOULD be limited to:

- one guideline or explicitly bounded source set;
- one declared U1/U2 use case;
- one care organization;
- one supplier or development partner;
- one defined user group;
- pre-agreed safety, usability, update and withdrawal criteria.

U3–U5 functionality requires a new protocol decision, legal and clinical assessment, responsibility model, acceptance plan and the applicable C3–C6 review.

## 10. Training-data prohibition

V&VN DS content MUST NOT be offered or described as general model-training data within the MVP. Retrieval of current published knowledge is not model training. A future training or fine-tuning proposal requires explicit approval covering rights, version propagation, provenance, deletion/withdrawal limitations, evaluation, model behavior and responsibility.

A model MUST NOT be described as automatically learning guideline updates merely because a source changed.

## 11. Gates and change impact

Before the first external consumer is onboarded:

- G0 for the target environment MUST pass;
- G2–G6 applicable to the released scope MUST pass;
- GD-04 through GD-07 MUST be resolved where their deadlines apply;
- the external-use contract, consumer registration, update/withdrawal test and responsibility assignment MUST pass;
- legal and privacy/security review MUST be recorded.

This protocol-only change introduces no runtime route and is a governance/documentation change. Any implementation of its requirements MUST be classified by behavior, including at least C3 for canonical metadata, C4 for retrieval/answerability, C5 for external access/publication/withdrawal and C6 for generation.

## 12. Approval effect

Approval of v2.4 establishes the product, distribution and external-use boundaries. It does not:

- publish a source or knowledge object;
- authorize an external consumer;
- grant a content licence;
- approve expenditure or Azure provisioning;
- add a frontend, chatbot, model or EPD/ECD integration;
- convert any blocked gate to pass;
- authorize U3–U5.

The immutable checksum and authoritative merge commit MUST be recorded after merge in the protocol approval manifest.
