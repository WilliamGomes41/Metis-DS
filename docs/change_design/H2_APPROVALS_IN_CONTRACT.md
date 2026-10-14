# CHANGE_DESIGN: H2, goedkeuringen binnen het contract (herstelstap 2)

**Status:** ontwerp. H2-1 tot en met H2-3 en D-DEL-1 zijn beantwoord (14-10-2026, 20:51 en 20:52 CEST). H2-4 is beantwoord (20:58 CEST). Het onafhankelijke deel staat in PR 2a (#623). H2-5 en H2-6 zijn beantwoord (21:51 CEST). PR 2b staat STIL op OPENVRAAG-H2-7 (zie §12).
**Basis:** main `4ac0b7b`. Bron: `/workspace/metis-ds-e2e/E2E-BUGREGISTER.md` (D-SEC-1, D-SEC-2, D-SEC-3, D-API-5, OPENVRAAG-B10), plus de besluiten van William van 14-10-2026 (via Metis, 20:48 CEST).
**Change class:** A (raakt de review- en publicatie-invarianten en de serving-autoriteit).
**Buiten scope:** D-API-1 en D-API-2, D-PERF. D-DEL-1 valt binnen scope (zie §10).
**Rewrite risk:** high. `review_configuration` vervangt `review_policy_v1` in 15 src-modules en 22 testbestanden.

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
  - `review_provenance TEXT NOT NULL DEFAULT 'pending_verification' CHECK (review_provenance IN ('pending_verification','verified_review','recovered_unverified'))`;
  - Bestaande en nieuwe rijen krijgen `pending_verification`. Een release MOET NOOIT `verified_review` krijgen voor een controle (OPENVRAAG-624-P1, optie A, William 15-10-2026).
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
- Bij `pending_verification` MOET de API de release NOOIT als geverifieerd tonen. OPENVRAAG-624-P1-LABEL: de tekst van `review_status_label` voor `pending_verification`.
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
| Migratie | `017` op een bestaande tabel: rijen blijven, default `pending_verification`, NOOIT `verified_review` voor een controle, idempotent |

## 8. Proof-plan
De tests van §7, de volledige suite en de Postgres-tests met `METIS_TEST_POSTGRES_DSN` in de sandbox (#605). Op de box zijn die laatste ONBEWEZEN.

## 9. Besluiten en open punten
- **H2-1 (beantwoord).** `review_configuration` VERVANGT `review_policy_v1`. Bestaande beleidsregels worden één keer gemigreerd naar de best passende optie. De mapping (deterministisch; `k` = het aantal required reviewers dat niet de uploader is, inclusief een primary die niet de uploader is):
  - primary = uploader en `k=0` → `uploader_sole`, four-eyes uit;
  - `k=1` → `one_other`, four-eyes aan;
  - `k=2` → `two_others`;
  - elk ander geval (`k>2`, `minimum_required>2`, archived-required, een ongeldig beleid) → `needs_choice`.

  Bij `needs_choice` MOET het document opnieuw een optie kiezen. Publicatie blijft fail-closed met `review_configuration_choice_required`.
- **H2-2 (beantwoord).** `one_other` + four-eyes: de uploader is het eerste oog en de andere reviewer het tweede. Twee niet-uploaders voldoen ook. De uploader telt NOOIT als tweede oog. Hoog-risico-objecten (`requires_four_eyes(obj)`) eisen four-eyes ALTIJD, ook bij `four_eyes_required=false`. Bij `uploader_sole` met een hoog-risico-object is publicatie daarom geblokkeerd met `four_eyes_required`.
- **H2-3 (beantwoord, optie b).** Migratie `017` voegt de kolommen toe. Een eenmalig, idempotent herclassificatiecommando (`scripts/publication_review_provenance_backfill.py`) controleert elke actieve release opnieuw tegen §4 en de workflow-bindings, Het MOET geslaagde releases van `pending_verification` promoveren naar `verified_review` en gefaalde releases op `recovered_unverified` zetten. Een release MAG NIET op `verified_review` komen zonder die controle (OPENVRAAG-624-P1, optie A). Het commando kent een plan-modus (alleen lezen) en een execute-modus met `--confirm-count`. Het draait NOOIT automatisch bij boot. Alleen Argos voert het uit op live, na GO van William.
- **OPENVRAAG-B10-1.** Four-eyes + `uploader_sole` wordt geweigerd (W6).
- **H2-4 (beantwoord).**
  - (a) Beslisbomen volgen dezelfde `review_configuration`: één reviewregel voor alle documenttypen.
  - (b) De uploader MOET specifieke reviewers benoemen (`review_configuration.reviewers`). Alleen hun goedkeuringen tellen, plus de uploader als eerste oog waar §4 dat toelaat.
  - (c) Optionele deelnemers blijven als `review_configuration.readers` en tellen NOOIT mee.

## 10. D-DEL-1: verwijderen van een ongepubliceerd document (beantwoord, binnen scope)
- **Regel.** Een ongepubliceerd document MOET verwijderbaar zijn door:
  - een account met de rol `publisher`;
  - de uploader (`envelope["uploader_account_id"]`).

  Elke andere rol of elk ander account MAG NIET verwijderen en krijgt `unpublished_delete_not_permitted`. Het verwijderen van gepubliceerde documenten blijft ongewijzigd: dat wordt geweigerd.
- **Plek.** `delete_unpublished_snapshot` (`operations_console_v1.py:2613+`; de rolcheck staat nu op `:2605–2607` en eist researcher of reviewer). Ook `_can_delete_unpublished` in `operations_console_app.py:1320` MOET dezelfde regel volgen (de UI-knop).
- **Tests (eerst rood, daarna groen):**
  - publisher-delete slaagt (nu: geweigerd, omdat de publisher geen researcher of reviewer is);
  - uploader-delete slaagt;
  - een andere researcher of een reviewer die niet de uploader is → geweigerd (nu: verwijderd).

## 11. Uitvoering: gesplitst in PR 2a en PR 2b
- **PR 2a (#623, branch `fix/approvals-independent`):** D-DEL-1, D-SEC-1, D-SEC-2 (herstel en CLI) en D-SEC-3. Daarin verandert de reviewregel NIET.
- **PR 2b (deze branch, gestapeld op 2a):** `review_configuration`, migratie `017`, het backfill-commando, beslisbomen, benoemde reviewers en lezers.

### OPENVRAAG-H2-5 (nieuw, blokkeert 2b): de rol "primary" bij beslisbomen
`review_policy.primary` is meer dan een reviewer. Bij beslisbomen bepaalt die rol:
- wie de graph opbouwt en bevestigt; de andere reviewers "beoordelen mee" (`decision_review_ui_v1.py:140`, `decision_graph_v1.py:294–334`);
- wie een opvolgende versie (successor) MOET registreren (`decision_successor_v1.py:7–14`, `review_policy_owner_required`).

Daarnaast schakelt de aanwezigheid van `review_policy` de expliciete beslisboommodus in (`source_preparation_context_v1.py:126`, `operations_console_v1.py:2467`).

B10 kent geen primary. Wie heeft deze rol onder `review_configuration`?
- (a) altijd de uploader;
- (b) de eerste benoemde reviewer;
- (c) een apart veld `graph_owner`, gekozen door de uploader.

En wat schakelt de beslisboommodus in: `class == "beslisboom"` alleen?

### OPENVRAAG-H2-6 (nieuw, blokkeert 2b): projecties in gehashte objecten
Bestaande objecten dragen het beleid in `metadata.review_policy` of `governance.review_policy`. Dat telt mee in `canonical_object_hash`, en daar hangen alle review-bindings aan. Twee opties:
- **Voorstel (niet-destructief):** de bestaande projectie blijft als inerte historische metadata in het object, zodat hash en bindings ongewijzigd blijven. Alleen de envelope-`review_configuration` is nog autoriteit. Nieuwe objecten krijgen geen beleidsprojectie meer.
- **Alternatief:** de projectie wordt verwijderd. Dan wijzigen alle hashes en vervallen alle bestaande goedkeuringen op documenten met een beleid. Dat staat gelijk aan een volledige her-review, en W3 dekt dat alleen bij een wijziging van de optie.

Besluit nodig: geldt het voorstel?

### H2-5 (beantwoord)
De uploader is de eigenaar en bevestiger van de beslisboom-graph en registreert opvolgende versies. De beslisboommodus MOET uitsluitend volgen uit `class == "beslisboom"`, en NOOIT uit de aanwezigheid van een beleid.

### H2-6 (beantwoord, voorstel aangenomen)
Het bestaande `review_policy` blijft inerte historie in de bestaande hashes, zodat goedkeuringen geldig blijven. Alleen de envelope-`review_configuration` beslist. Nieuwe objecten krijgen de policy NOOIT meer gekopieerd.

## 12. OPENVRAAG-H2-7 (nieuw, blokkeert 2b): W1 is strijdig met het huidige gedrag
W1 zegt: bestaande documenten krijgen optie 3 met four-eyes **verplicht**, "which is current behaviour". Op main (`c7a9959`) eist four-eyes echter alleen een **hoog-risico-object** (`requires_four_eyes(obj)`: exception, `risk_level=high`, risicovelden). Een gewoon object publiceert vandaag met één goedkeuring van een benoemde reviewer die niet de uploader is.
- **Bewijs:** `tests/test_vsa_publish_readiness_ui_v1.py::_complete_review` keurt één object goed door `reviewer.bert` (niet de uploader). Het document is daarna `ready`; die test is groen op main.
- **Gevolg van de letterlijke lezing (four-eyes aan voor elk object):**
  - elk bestaand document heeft dan voor elk gewoon object ook de goedkeuring van de uploader of van een tweede reviewer nodig;
  - de backfill van H2-3 labelt dan elke actieve release met één reviewer als `recovered_unverified`.

  Dat is geen voortzetting van het huidige gedrag.
- **Twee lezingen:**
  - (a) **Huidig gedrag exact (voorstel):** de backfill-default is `one_other` met `four_eyes_required=false`. Hoog-risico-objecten eisen four-eyes ALTIJD (H2-2). Dit reproduceert main exact. Nieuwe documenten kiezen de vlag zelf.
  - (b) **Letterlijk W1:** de default is `four_eyes_required=true` voor elk object. Bestaande documenten en releases met één reviewer worden dan geblokkeerd of gelabeld.

Besluit nodig: (a) of (b).

**Uitvoeringsnoot (ingest-default, ter bevestiging bij hetzelfde besluit).** Honderden bestaande tests en scripts roepen de kernel-`ingest` aan zonder keuze. Voorstel: het HTTP-uploadformulier MOET de keuze afdwingen (de uploader MOET kiezen). De kernel-`ingest` zonder `review_configuration` krijgt dezelfde default als de backfill (W1, volgens de gekozen lezing), met `source: "legacy_default"`, zichtbaar in het document. Dit wijkt af van §2.1 ("ingest weigert zonder keuze").
