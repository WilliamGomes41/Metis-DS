# B6 — Groepsafhandeling van bronpassages (ontwerp ter goedkeuring)

Status: **GOEDGEKEURD (projectlead, 30 oktober 2026), inclusief keuze (a) in §3.7.** Bouwen volgt in de volgorde van §9.
GitHub: #933. Linear: MET-33 (onder MET-6).
Besluit: B6, opties 3 en 2 (projectlead, 30 oktober 2026). Besluit B is aangepast: onderbouwing loopt via groepsbevestiging per sectie.

Change class: A (het besluit over een bronpassage is lifecyclestatus van het object)
Rewrite risk: none (hergebruik van de bestaande opdracht per passage; geen vervanging van een gedeelde grens)

## 1. Probleem

Een document mag pas gepubliceerd worden als vier voorwaarden op nul staan (`publication_readiness_v1`):

1. open review;
2. onverantwoorde bronpassages (`SOURCE_PASSAGE_REVIEW_INCOMPLETE`);
3. open herstelwerk (`REVIEW_REPAIR_INCOMPLETE`);
4. onvolledige vorming.

Stand van Richtlijn Smetten na de meetrun (1.1.498, export van 30 oktober):

| Stapel | Aantal | Belangrijkste inhoud |
| --- | --- | --- |
| Bronpassages met `human_action = source_disposition` | 376 | Het model gaf als reden: metadata, structuur, navigatie of paginaopmaak (~275), en `unformed_meaning` / `uncertain_source_role` (~100). |
| Herstelwerk (geblokkeerde objecten) | 216 | Waarvan ~100 onderbouwing (Overwegingen, Literatuurconclusies, Rationale enz.). |
| Open vormingstaken | 9 | Waarvan 7 in onderbouwingssecties. |

Elk item vraagt nu een losse handeling. In totaal zijn dat honderden handelingen zonder inhoudelijke winst, waardoor publicatie praktisch onhaalbaar is.

## 2. Bestaand mechanisme (wordt hergebruikt, niet vervangen)

- **Losse bronrol-opdracht.** `source_context_review_v1` heeft de rollen `excluded`, `context` en `reset`. De opdracht:
  - controleert dat de actor een aangewezen reviewer is en dat het document niet gepubliceerd is;
  - is idempotent via `command_id` en `payload_hash` in de ledger;
  - controleert `expected_revision`;
  - schrijft per passage `metadata.source_role` (reviewer, tijd, reden, literal-hash, bron-SHA) en `passage_register = excluded_with_reason / used_as_context`;
  - kan worden teruggedraaid met `reset`.
- **Afsluiting.** `source_containers_v1.source_accountability` telt een passage met een definitieve dispositie (`definitive_review_disposition`, register `excluded_with_reason` / `used_as_context` en review afgerond) als `accounted`.
- **Voorbeeld van bundeling.** `proportionate_review_v1.batch_review_normal_risk` controleert eerst de hele selectie en voert daarna per object de bestaande `review_object` uit. Het gebruikt één vastgepinde revisie, één sectie en één type, met maximaal 20 objecten.
- **Vaste niet-kennisregels.** `source_containers_v1.metadata_reason` bevat gesloten regels over de hele passage. De code zegt: "never exclude by chapter location alone".

## 3. Ontwerp

### 3.1 Wat een groep is

Een groep is een **voorstel van het systeem**, geen opgeslagen toestand. Een groep wordt bij elke weergave opnieuw afgeleid uit de actuele stand:

- **sleutel:** document, sectiepad (`section_path`) en voorgestelde reden. De reden is:
  - voor een bronpassage de `reason` uit `source_accountability`;
  - voor onderbouwing: `onderbouwing`, voorgesteld op grond van een vaste lijst sectiekoppen (zie 3.4);
- **leden:**
  - bronpassages met `human_action = source_disposition`;
  - geblokkeerde objecten met `supported_object_missing` + `no_independent_claim` in een onderbouwingssectie;
- **maximale grootte:** 50 leden. Grotere groepen worden opgesplitst in volgorde van de bron.

Er komt geen nieuwe tabel of status voor groepen.

### 3.2 Wat de beoordelaar ziet

- Een overzicht per sectie met de voorgestelde groepen. Per groep: reden, aantal en de **volledige tekst van elk lid**.
- Per lid een vinkje "dit is wél kennis". Aangevinkte leden vallen buiten de groep en blijven gewoon in review of herstel.
- Eén knop per groep:
  - **"Bevestig: geen kennis"** (rol `excluded`, met de reden van de groep);
  - of, bij onderbouwing, **"Bevestig: onderbouwing"** (rol `excluded`, reden `onderbouwing`, en het passageregister `excluded_with_reason`). Onderbouwing wordt dus geen los kennisobject (besluit B).

### 3.3 Opdracht: `confirm_source_group`

Invoer:
- `actor_id`, `snapshot_id`, `expected_revision`, `command_id`;
- `role` (`excluded`), `reason` (groepsreden);
- `member_ids`: de lijst die de beoordelaar zag, minus de uitgevinkte leden;
- `members_hash`: een hash over (object_id, object_version, literal-hash) van elk getoond lid.

Volgorde, alles onder de bestaande `_store_write_lock`:
1. **Autorisatie.** De actor heeft de rol reviewer, is aangewezen op het document, en het document is niet gepubliceerd. Gelijk aan de losse opdracht.
2. **Idempotentie.** Een bekende `command_id` met dezelfde `payload_hash` geeft het eerdere resultaat terug. Met een andere payload volgt `source_group_command_conflict`.
3. **Actualiteit.**
   - Het document moet op `expected_revision` staan; anders `SNAPSHOT_OBJECT_WRITE_CONFLICT`.
   - De `members_hash` moet overeenkomen met de actuele leden; anders `source_group_members_changed`. De beoordelaar heeft dan iets anders bevestigd dan er nu staat.
4. **Voorcontrole van alle leden vóór de eerste schrijfactie.** Elk lid moet:
   - nog bestaan;
   - nog aan de groepssleutel voldoen;
   - geen relatie of rol hebben die de losse opdracht zou weigeren;
   - een open origineel hebben (`_require_open_original`);
   - geen goedgekeurd kennisobject zijn.

   Eén weigering laat de hele groep weigeren.
5. **Schrijven.** Per lid dezelfde wijziging als de losse opdracht met rol `excluded`. Alle leden gaan in **één opslagtransactie**: allemaal of niets.
6. **Audit.** Eén ledger-event `source_group_confirmed` met:
   - `command_id`, actor, tijd, reden en `members_hash`;
   - per lid: object-id, oude en nieuwe versie, en literal-hash.

   Elk lid draagt bovendien zijn eigen `source_role`-record met `command_id`.

Uitvoer: de bijgewerkte leden en de nieuwe revisie.

### 3.4 Onderbouwingssecties (voorstel, geen automatische uitsluiting)

Op een kop met een van de volgende namen (na normalisatie, als laatste deel van het sectiepad) stelt het systeem de groepsreden `onderbouwing` voor:
- Literatuurconclusies, Literatuursamenvatting;
- Zoeken en selecteren;
- Overwegingen, Van bewijs naar aanbeveling (overwegingen), Rationale;
- Voor- en nadelen van de interventie en de kwaliteit van het bewijs;
- Waarden en voorkeuren van patiënten (en hun naasten);
- Kosten (middelenbeslag), Aanvaardbaarheid, haalbaarheid en implementatie;
- Duurzaamheid, Gelijkheid.

Dit is alleen een **voorstel**. Uitsluiten gebeurt pas na bevestiging door een mens, dus de regel "never exclude by chapter location alone" blijft gelden.

### 3.5 Terugdraaien

Met "Groep terugdraaien" voert het systeem met een nieuwe `command_id` de bestaande rol `reset` uit voor alle leden van een eerdere `command_id`. Daarbij:
- worden de leden weer `not_yet_assessed`;
- komen ze weer in de stapels;
- worden ze niet verwijderd;
- blijft de audit van beide opdrachten bewaard.

Terugdraaien kan niet meer na publicatie. Het gepubliceerde werk blijft immutable.

### 3.6 Vaste niet-kennisregels (optie 3)

Er komen extra regels in `accounting_reason` (alleen bronverantwoording; de vorming blijft `metadata_reason` gebruiken), alleen over de **hele passage**. Elke regel krijgt:
- een positieve test;
- een negatieve test met een klinische zin die erop lijkt.

De kandidaten worden afgeleid uit de echte passages van deze bron, offline en buiten GitHub. Elke regel wordt afzonderlijk ter goedkeuring voorgelegd. Wat een regel afvangt, telt automatisch als verantwoord, zoals nu al het geval is.

### 3.7 Open vormingstaken

Een vormingstaak blijft open zolang een `pending_rejection` zijn bronbereik overlapt (`bounded_formation_v1.is_open`). Of een bevestigde groep die taken mag sluiten, is **nog niet vastgesteld**. Het vormingsbewijs en de bronafhandeling zijn nu gescheiden eigenaren.

Ontwerpkeuze vóór de bouw:
- (a) een bevestigde bronafhandeling over het hele bereik van een pending rejection telt als afgehandeld voor de vormingsvoltooiing;
- of (b) de vorming blijft open en de beoordelaar kiest expliciet "vorming afsluiten" voor die sectie.

**BESLOTEN: (a)** (projectlead, 30 oktober 2026). Dat is alleen toegestaan als de bevestigde passages het bereik volledig dekken, en het wordt vastgelegd met dezelfde `command_id`.

## 4. Domeininvarianten

- Geen kennisobject wordt goedgekeurd of gepubliceerd door een groepsbesluit. Uitsluitend de rol `excluded` (en `reset` om terug te draaien).
- Een classificatie van het model alleen sluit nooit een bronpassage af. Alleen een mens of een bewezen vaste regel doet dat.
- De bron blijft onveranderd. Spans, literal-hashes en provenance van elk lid blijven gelijk; alleen rol, passageregister en governancestatus veranderen, zoals in de losse opdracht.
- Gepubliceerde werkrevisies blijven onveranderbaar.
- De beoordelaar bevestigt exact wat hij zag (`members_hash`). Een wijziging tussen tonen en bevestigen leidt tot weigering.

## 5. Gedrag bij storingen

| Situatie | Uitkomst |
| --- | --- |
| Dubbele klik of nieuwe poging met dezelfde `command_id` | Hetzelfde resultaat; geen tweede wijziging. |
| Andere schrijver tussen tonen en bevestigen | `SNAPSHOT_OBJECT_WRITE_CONFLICT` of `source_group_members_changed`; niets gewijzigd. |
| Fout bij één lid in de voorcontrole | Hele groep geweigerd; niets gewijzigd. |
| Fout of herstart tijdens het schrijven | Eén transactie: alles of niets. Nieuwe poging met dezelfde `command_id` is veilig. |
| Twee beoordelaars tegelijk | De eerste wint. De tweede krijgt een revisieconflict en ziet de nieuwe stand. |

## 6. Bewijs (tests)

- Een groep met N leden geeft per lid **dezelfde** objecten (rol, register, governance) als N losse opdrachten. Alleen het groeps-event en de `command_id` verschillen.
- Na bevestiging tellen de leden als `accounted`, en verdwijnt onderbouwing uit `review_repair_duties`.
- Terugdraaien herstelt exact de stand van vóór de bevestiging, behalve de objectversies, die doorlopen.
- Weigeringen:
  - een niet-aangewezen reviewer;
  - een gepubliceerd document;
  - een verouderde revisie;
  - een gewijzigde `members_hash`;
  - een lid dat een goedgekeurd kennisobject is;
  - meer dan 50 leden;
  - een dubbele `command_id` met een andere payload.
- Native PostgreSQL:
  - gelijktijdige bevestiging door twee beoordelaars;
  - herstart tijdens het schrijven;
  - een schrijver tussen tonen en bevestigen.
- Een meting op Richtlijn Smetten: het aantal handmatige handelingen vóór en na.

## 7. Effect op publicatie

| Voorwaarde | Effect |
| --- | --- |
| Review | Geen. Kennis blijft per object beoordeeld. |
| Bronpassages | ~376 losse handelingen worden naar schatting 30–50 groepsbevestigingen, minus wat vaste regels automatisch afvangen. |
| Herstelwerk | ~100 stukken onderbouwing gaan via groepen. De rest (~116) blijft echt herstelwerk. |
| Vorming | Met keuze (a) sluiten 7 van de 9 open taken. |

## 8. Buiten scope

- Het automatisch accepteren van de classificatie van het model (optie 1, afgewezen).
- Onderbouwing koppelen aan een specifieke aanbeveling (optie C). Dat is pas aan de orde als MET-7 aantoont dat het nodig is.
- Groepsgoedkeuring van kennisobjecten.

## 9. Vervolg na goedkeuring

1. Vaste regels (3.6): per regel een kleine PR.
2. Groepsafhandeling: opdracht, schermen en tests, in één PR met change class A.
3. Keuze 3.7 vastleggen en bouwen.
4. Meten op Richtlijn Smetten.
