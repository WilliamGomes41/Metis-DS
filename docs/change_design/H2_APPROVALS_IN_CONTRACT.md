# CHANGE_DESIGN: H2, goedkeuringen binnen het contract (herstelstap 2)

**Status:** ontwerp; implementatie staat STIL op OPENVRAAG-H2-1 tot en met H2-3 (zie §9).
**Basis:** main `4ac0b7b`. Bron: `/workspace/metis-ds-e2e/E2E-BUGREGISTER.md` (D-SEC-1, D-SEC-2, D-SEC-3, D-API-5, OPENVRAAG-B10), plus de besluiten van William van 14-10-2026 (via Metis, 20:48 CEST).
**Change class:** A (raakt de review- en publicatie-invarianten en de serving-autoriteit).
**Buiten scope:** de verwijderrechten (D-DEL-1 wacht op William), D-API-1 en D-API-2, D-PERF.

## 1. Besluiten van William (vast)
- **W1.** Bestaande documenten krijgen optie 3 (één andere reviewer) met four-eyes verplicht.
- **W2.** De uploader telt NOOIT als tweede oog.
- **W3.** De reviewoptie is vergrendeld zodra de review start. Een wijziging MOET de review herstarten.
- **W4.** Bestaande herstelde releases krijgen de herkomst "hersteld zonder geverifieerde review". Ze blijven met dat label zichtbaar voor Athena tot een nieuwe review; daarna verdwijnt het label. Nieuwe herstel- of CLI-items zonder geverifieerde review verschijnen NOOIT als geverifieerd.
- **W5.** De pilot-SQLite-CLI (`canonical_store.py`) wordt NOOIT voor publicatie gebruikt. Buiten een expliciete pilot- of dev-modus MOET de CLI fail-closed weigeren.
- **W6.** Four-eyes plus optie 1 wordt geweigerd. Dat is een expliciete weigering met test, gemarkeerd als OPENVRAAG-B10-1.

## 2. Datamodel
### 2.1 Reviewconfiguratie per document (envelope)
```json
"review_configuration": {
  "contract": "review-configuration-v1",
  "option": "uploader_sole" | "two_others" | "one_other",
  "four_eyes_required": true | false,
  "revision": 1,
  "locked_at": null | "<iso8601>",
  "chosen_by": "<uploader account_id>"
}
```
- De uploader MOET dit kiezen bij `ingest` (formulier plus kernelargument). Ontbreekt het, dan volgt NOOIT een stille default voor nieuwe documenten: de ingest weigert met `review_configuration_required`.
- **Validatie:**
  - `uploader_sole` + `four_eyes_required=true` → `review_configuration_four_eyes_uploader_sole_refused` (W6).
  - Een onbekende optie → `invalid_review_configuration`.
- **Backfill (W1)**, bij het laden van een envelope zonder het veld: lees `{"option":"one_other","four_eyes_required":true,"revision":0,"locked_at":<eerste reviewmoment of null>,"chosen_by":null}`.
  - Dit is een leesprojectie. Er is geen schrijvende migratie en daardoor geen datamutatie bij het booten (zie D-BOOT-1).
  - De eerste wijziging door de uploader schrijft `revision 1`.

### 2.2 Herkomst in het publicatieregister (Postgres)
- Nieuwe migratie `db/migrations/017_publication_review_provenance.sql`. Die is niet-destructief, alleen `ADD COLUMN ... DEFAULT`:
  - `review_provenance TEXT NOT NULL DEFAULT 'verified_review' CHECK (review_provenance IN ('verified_review','recovered_unverified'))`;
  - `review_provenance_changed_at TIMESTAMPTZ NULL`.
- De kolom komt op de release-rij (zie de tabel in `007_publication_registry_serving_authority.sql`).
- `persist_published_release(..., review_provenance=...)` is een verplicht argument zonder default, zodat elke schrijver kiest.
  - De normale publicatie MOET `verified_review` schrijven, en alleen na de contractpoort (§4).
  - De herstelroute en elk niet-geverifieerd pad MOETEN `recovered_unverified` schrijven, behalve als de herstelroute de volledige contractcontrole (§3.2) doorstaat.
- **Backfill van bestaande live herstelde releases (W4):** zie OPENVRAAG-H2-3.

## 3. Invarianten
- **I1 (D-SEC-1).** `record_authorization` MOET weigeren als:
  - `reviewer_is_agent(binding)` geldt;
  - de identiteit verboden is;
  - `reviewer_id` geen bestaand, niet-gepensioneerd menselijk account met de rol reviewer is.

  `tuple_record` krijgt een geverifieerd account-object en MAG NIET op vrije stringvelden vertrouwen.
- **I2 (D-SEC-2, herstel).** `legacy_canonical_recovery_v1` MOET `eligible_tuple_reviewers` en de reviewregel van §5 gebruiken. Een release met als enige approve een agent → `legacy_release_object_authorization_missing`.
- **I3 (W5).** De `canonical_store.py`-CLI start alleen bij `METIS_RUNTIME_MODE in {"pilot","dev"}`. Anders volgt exit 2 met `canonical_store_cli_disabled_outside_pilot`. Waar de CLI draait, MOET de vergelijking op `account_id` gebeuren (`validated_by_id`, `second_review.reviewer_id`). Objecten zonder ids worden geblokkeerd met `reviewer_account_id_missing`.
- **I4 (D-SEC-3).** Het besluit `publish_allowed` MOET in `publish_authorization_contract` vallen. `technical_publication_readiness` MAG NIET meer zelf contractblockers wegfilteren. De locatorcontrole blijft één expliciete, benoemde uitzondering in het contract zelf.
- **Guard-test:** elke blocker behalve de vaste locatorset maakt `publish_allowed` False.
- **I5.** Een AI- of agent-identiteit is NOOIT reviewer, in elk pad: review, herstel, CLI en import.
- **I6 (W2).** De uploader telt NOOIT als tweede oog.
- **I7 (W4).** De API MOET `review_provenance` per item meeleveren. `recovered_unverified` verschijnt NOOIT als geverifieerd.

## 4. Reviewregel (vervangt `four_eyes_v1.py:179–191`)
`review_satisfied(eligible, uploader_id, configuration)` werkt op approvers die al door het agentfilter zijn gegaan:

| optie | four_eyes_required=false | four_eyes_required=true |
|---|---|---|
| `uploader_sole` | de uploader heeft goedgekeurd | GEWEIGERD bij configuratie (W6) |
| `two_others` | ≥2 approvers ≠ uploader | ≥2 approvers ≠ uploader |
| `one_other` | ≥1 approver ≠ uploader | zie OPENVRAAG-H2-2 |

## 5. Toestandsovergangen (W3)
- `unlocked` → `locked`: bij de eerste reviewbinding of de eerste `review_passes`-schrijving. `locked_at` wordt gezet in dezelfde transactie.
- `change_review_configuration` op een vergrendeld document:
  - Alle bindings van het snapshot worden ongeldig (`invalidate_for_object` per object).
  - Er komt een ledger-event `review_restarted_configuration_changed`.
  - `locked_at` wordt null en `revision` gaat +1.
  - Het snapshot krijgt de status "in review" bij nul.
- Gepubliceerde documenten: NOOIT. De wijziging wordt geweigerd met `published_working_revision_immutable`.
- Herkomst `recovered_unverified` → `verified_review`: alleen bij een nieuwe publicatie van dezelfde logische release na een volledige contractcontrole. Het label verdwijnt dan en `review_provenance_changed_at` wordt gezet.

## 6. API-label
- `/v1/knowledge/{id}`, `/v1/retrieve` en `/v1/documents` leveren `review_provenance` mee. Bij `recovered_unverified` komt er ook `review_status_label: "hersteld zonder geverifieerde review"` bij.
- De answerability-gate MOET dit doorgeven en verbergt het NOOIT.

## 7. Tests (eerst rood, daarna groen)
| Aanval of regel | Test |
|---|---|
| D-SEC-1 | `record_authorization` met een agent-reviewer of een onbekend account-id → fout |
| RT1/RT2 (Lex) | Herstelmanifest met als enige approve een agent → `legacy_release_object_authorization_missing` |
| RT1b | Herstel met alleen een uploader-approve onder `one_other` → geweigerd |
| D-SEC-2 CLI | Pilot-modus: namen gelijk maar ids verschillend → geblokkeerd; ids ontbreken → `reviewer_account_id_missing` |
| W5 | CLI zonder `METIS_RUNTIME_MODE=pilot/dev` → exit 2 |
| RT3 / D-SEC-3 | Extra contractblocker plus geldige locator → `publish_allowed` False; guard op de filterset |
| W6 | `uploader_sole` + four-eyes → `review_configuration_four_eyes_uploader_sole_refused` |
| W1 | Envelope zonder configuratie → projectie `one_other` + four-eyes; geen schrijfactie |
| W2 | Four-eyes met uploader plus één ander onder `two_others` → niet voldaan |
| W3 | Configuratie wijzigen na de eerste binding → bindings ongeldig en ledger-event; daarna eist publiceren een nieuwe review |
| W4 | Hersteld item → API-label aanwezig; na een nieuwe review en publicatie → label weg |
| W4 nieuw | Herstel zonder geverifieerde review → registry `recovered_unverified`, NOOIT `verified_review` |
| Migratie | `017` op een bestaande tabel: rijen blijven, default `verified_review`, idempotent |

## 8. Proof-plan
De tests van §7, de volledige suite en de Postgres-tests met `METIS_TEST_POSTGRES_DSN` in de sandbox (#605). Op de box zijn die laatste ONBEWEZEN.

## 9. OPENVRAAG: besluiten die de implementatie blokkeren
- **OPENVRAAG-H2-1 (bestaand beleidsmodel).** Main heeft al een envelope-eigen reviewbeleid: `review_policy` (`explicit-review-v1` / `managed-review-v2`, `review_policy_v1.py`). Dat beleid kent een primary, `required`/`optional`-assignments en beheercommando's (`manage_review_participation`). In `publish_authorization_contract` (`four_eyes_v1.py:233–238`) vervangt het al de independence- en four-eyes-regel. Twee vragen:
  - Vervangt B10 dit beleid, ligt B10 eroverheen (beide MOETEN gelden), of wordt B10 een projectie ervan (bijvoorbeeld `uploader_sole` = primary uploader zonder required assignments)?
  - Wat gebeurt er met documenten die nu een managed beleid hebben?

  Dit is een duurzaam modelbesluit en staat niet in W1–W6.
- **OPENVRAAG-H2-2 (betekenis van four-eyes bij `one_other`).** Huidig gedrag (W1 noemt dit "current behaviour"): four-eyes = ≥2 approvers waarvan ≥1 niet de uploader (`four_eyes_v1.py:179–191`). Daarbij telt de uploader dus als **eerste** oog. Twee lezingen:
  - (a) De uploader telt als eerste oog: one_other+four-eyes = uploader + één ander. Dat is consistent met W1 en W2.
  - (b) Four-eyes eist twee ogen buiten de uploader: dan valt `one_other`+four-eyes samen met `two_others`, en dat wijkt af van het huidige gedrag.

  Daarnaast is onbeantwoord wat `four_eyes_required=false` doet bij een hoog-risico-object (dosering, leeftijdsgrens). Nu forceert `requires_four_eyes(obj)` dan four-eyes per object. Schakelt de documentkeuze die objectregel uit, of blijft four-eyes voor hoog-risico-objecten altijd verplicht?
- **OPENVRAAG-H2-3 (backfill van herstelde live releases).** Het register onderscheidt herstelde releases niet van normale: `recover_legacy_canonical_release` schrijft via hetzelfde `persist_published_release` zonder marker. Een migratie herkent ze daarom niet deterministisch zonder live data, en live data raak ik NOOIT aan. Opties:
  - (a) William levert een lijst van release-ids. De migratie markeert precies die.
  - (b) De migratie markeert elke actieve release `recovered_unverified` waarvan de bindings niet aan §4 voldoen. Dat vraagt een herberekening over de workflow-autoriteit tijdens de migratie.
  - (c) Alle releases van vóór de Postgres-cutover worden gemarkeerd, op basis van `published_at` < cutover-tijdstempel.

  Keuze nodig.
- **OPENVRAAG-B10-1 (W6).** Four-eyes plus `uploader_sole` wordt geweigerd. Of deze combinatie later toch toegestaan wordt, blijft open bij William.
