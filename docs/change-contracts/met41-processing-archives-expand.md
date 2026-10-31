# MET-41 / #950 — additieve archiefopslag, eerste increment

Change class: A
Promise: De bestaande FormationTaskStore kan één replayrecord of kwaliteitsrun exact en onveranderlijk archiveren, adresseren en na procesherstart teruglezen, zonder operationele documentgegevens te wijzigen.
Proof: Native PostgreSQL-proeven voor exacte inhoud, bronbinding, idempotentie/concurrentie, SQL-immutability, rollback, procesherstart en begrensde metadatareads bij onafhankelijke archiefgroei.
Touches lifecycle invariants: yes
Rewrite risk: high

Gebruikersopdracht: “Start alvast 41”, 31 oktober 2026. Dit increment hoort bij
#950/MET-41 en bouwt op het ontwerp van [MET-40](met40-formation-evidence-context.md),
PR #954. Het is de expand-fase, geen afronding van #950 of productiecutover.

## Bestaand gedrag en begrenzing

`FormationTaskStore` bezit al preparation, checkpoints, taskresultaten en source
records. `_write_envelope_locked` en `get_envelope` bewaren/lezen replay en
kwaliteitsgeschiedenis nog inline; TaskCheckpointWriter heeft claimfencing.
De nieuwe API blijft bij diezelfde store en heeft nog geen runtimecaller.
Zij bewaart **diagnostische provenance**, geen gevalideerd activatiebewijs.
Een hash of archiefrecord bewijst geen domeinvalidatie, complete findingdekking,
reviewclosure of publicatierecht. Bestaande `assert_activation`, evaluator,
kandidaatmaker en publicatieauthority blijven leidend.

Fasen: bestaande grens onderzocht; twee opslagvormen vergeleken; keuze toegepast
binnen de opdracht; implementatie en native bewijs in dit increment; geen
architectuurvervanging nodig tenzij het bewijs een onveilige grens aantoont.

## Gebruik, vorm en alternatief

```python
prepared = tasks.prepare_processing_archive(
    envelope, kind='quality_processing_run', record_key=run['run_id'], payload=run,
    observed_revision=observed_objectset_revision)
ref = tasks.retain_processing_archive(prepared)  # eigen korte transactie
ref = tasks.processing_archive_header(envelope, kind='quality_processing_run',
                                     record_key=run['run_id'])  # geen payload
run = tasks.read_processing_archive(ref, envelope=envelope)  # expliciet archief
```

De twee vormen, ontwikkeld binnen hetzelfde model:

- **Gekozen:** snapshot-owned records met unieke `(snapshot, kind, record_key)`,
  exacte bron-/lineagebinding, inhoudshash en één complete JSON-payload per
  record. Een run is al de natuurlijke eenheid; replay blijft exact inclusief
  provideruitvoer en oorspronkelijke onvolledigheidsbevindingen.
- **Afgewezen:** globale content-addressed blobpool met losse membership- en
  retentieroots. Die vraagt nieuw eigenaarschap/GC en extra manifestcoördinatie
  zonder noodzaak voor deze twee bestaande archieftypen. Inhoudshashes dienen
  hier corruptiedetectie; ze vervangen de oorspronkelijke recordidentiteit niet.

De gekozen vorm past bij exacte run/replay-lookups, conflicteert bij hergebruikte
identiteit met andere inhoud en heeft één documentcascade. Metadata bevat geen
lijst met alle historische referenties. Een archiefrecord heeft geen losse leden;
complete formation-proof-memberdekking is een afzonderlijk volgend increment.

Het oorspronkelijke objectsetrevisiontoken blijft compleet bewaard als opaque
historische provenance, ook als het een grote m2-token is. Alleen zijn hash staat
in de kleine header; het token is geen nieuwe actuele activatiepreconditie. De
payload bewaart canoniek JSON als tekst: JSONB-normalisatie van bijvoorbeeld
`1e20` zou de exact oorspronkelijke inhoudshash veranderen.

## Eigenaarschap en context

| Gegeven | Producent → consument | Eigenaar / levensduur / regel |
| --- | --- | --- |
| SourceIdentity + LogicalDocument + WorkingRevision | bestaande envelope → archive writer/reader | Bestaande workflowdocuments; exact gebonden, geen afleiding uit titel of versie |
| kind + record_key | bestaande verwerking/expliciete migratie → exacte lookup | Replayrecord of kwaliteitsrun; herhaalde identiteit met andere inhoud is conflict |
| payload | vertrouwde kernelwriter → expliciete historie/export | Exact JSON met vaste layout/hash; geen algemene semantische goedkeuring |
| archive reference | writer → expliciete reader | Vaste kleine scalarreferentie; ontbrekend, corrupt en incompatibel afzonderlijk |
| bevoegdheid/claim/revisie | bestaande commandowner → toekomstige runtime-integratie | Deze opslagadapter verleent geen rechten of activatie; geen HTTP-ingang |

Voorbereiding en serialisatie gebeuren vóór de eigen opslagtransactie. Een
workflowtransactie als buitenste scope wordt geweigerd. De opslagwrite neemt
alleen een gedeelde documentlock om bronbinding en cascade te beschermen; zij
leest geen envelope, objectset, taskhistorie of andere archieven. SQL bewaakt
identiteit bij insert, verbiedt UPDATE/DELETE/TRUNCATE en laat alleen verwijdering
via de bestaande volledige documentcascade toe. Een beheerder die triggers
uitschakelt valt buiten dit bestaande trusted-writermodel; readers detecteren
gewijzigde payload/hashbinding, geen kwaadwillende beheerder die alles herschrijft.

## Lifecyclecontract van dit increment

Lifecycle entity: Bestaande SourceSnapshot/WorkingRevision met diagnostische verwerkinghistorie.
Lifecycle transition: Eén exact brongebonden archiefrecord duurzaam toevoegen; geen activatie of lifecycle-statuswijziging.
Initial durable state: Bestaande geldige workflowdocumentrij, oorspronkelijke inline historie en eventueel eerdere archieven.
Trigger: Expliciete vertrouwde kernelcall; runtime-integratie en migratiecallers volgen later binnen #950/#953.
Authorization: Geen nieuwe publieke ingang; bestaande geautoriseerde commandowner moet bij integratie bevoegdheid/claim toetsen. De opslagadapter is geen rechtenbewijs.
Validation: Gesloten archieftype, niet-lege begrensde recordidentiteit, complete bestaande source/lineagebinding, JSON-integriteit en bestaande documentidentiteit bij commit.
Mutable entities: Alleen nieuwe archiefrij; geen bestaande rij wordt gewijzigd.
Immutable entities: Bestaande bron, objecten, review, gepubliceerde revisies/releases en elk behouden archiefrecord.
Workflow state before: Bestaande workflowtoestand.
Workflow state after: Identiek; geen completionstatus of documentpin.
Release state before: Bestaande published/superseded/withdrawn release of geen release.
Release state after: Identiek; archive is geen canonical publication write.
Serving state before: Alleen publicatieregister bepaalt actieve set.
Serving state after: Identiek, ook na herstart.
Expected API result: Kleine exacte archiefreferentie, exact payload bij expliciete read, of expliciet conflict/bron-/layout-/integriteitsprobleem; nog geen HTTP/APIwijziging.
Expected UI result: Bestaande UI ongewijzigd; geen productverbetering claimen.
Failure result: Een fout vóór commit laat geen record achter; een gecommitte record blijft exact herbruikbaar. Document en eerdere historie blijven intact.
Restart result: Nieuw proces leest hetzelfde gecommitte record zonder vorming, reconstructie of GET-write.
Recovery result: Zelfde key+inhoud is idempotent; andere inhoud geeft conflict. Geen reset, delete of automatische herstelwriter.
Legacy-data result: Zonder archief is headerlookup None; een expliciete pin zonder rij is missing; onbekende layout en corruptie zijn fouten. Inline origineel blijft leidend.
Required black-box scenario: Bestaande productiecompositie met document → archiveer bekende run/replay → onafhankelijk nieuw Pythonproces leest exacte inhoud → mislukte tweede write verandert origineel/objects/review/release/serving niet.
Explicit non-goals: Activatiebewijs/seal-membermodel, pinning, inline-verwijdering, runtimecutover, bronextractie opnieuw opslaan, automatische migratie, nieuwe retention/GC, deployment of een gerepareerd Review-incident claimen.

Rewrite target: Eerste additieve archiefbewaargrens binnen de bestaande FormationTaskStore; volledige #950 blijft het grotere doel.
Why local patching is insufficient: Inline JSON-projectie of timeoutverhoging scheidt historische groei niet fysiek van operationele opslag; een afzonderlijke bewaareenheid is noodzakelijk vóór omschakeling.
Current authority/writer/reader map: FormationTaskStore bezit de nieuwe archieven; huidige envelope en TaskCheckpointWriter blijven operationeel leidend. Nieuwe helper heeft uitsluitend expliciete adaptercalls, geen constructor-, GET-, trigger- of fallbackcaller. De volledige bestaande inventaris staat in MET-40 §16.
Supported runtime topologies: Beide bestaande FastBadge CompleteWorkflow PostgreSQL-composities, lokale/Azure bronadapter; onafhankelijke processen over dezelfde database.
Persisted-state impact: Eén nieuwe snapshot-owned tabel en constraints/triggers/index; geen documentenbackfill, nieuwe referentiekolom of vervanging van bestaande gegevens.
Compatibility/migration plan: Alleen expand. Geen dual-write of bestaande datarewrite. Dezelfde migratie kan herhaald worden. Geautoriseerde runtime-integratie, voorbereiden/pariteit, CAS-pin en cutover blijven volgende increments van #950–#953.
Rollback/recovery plan: Vorige binary blijft bestaand werk lezen; nieuwe ongebruikte tabel hoeft niet verwijderd te worden. Archive writes kunnen exact herhaald worden; bestaande inline gegevens en bewijs blijven behouden. Geen destructieve downmigration.
Cutover trigger: In dit increment geen cutover; pas volledige proof-, writer-, reader-, migratie- en native gebruikersflowdekking uit #950–#953 kan die rechtvaardigen.
Cleanup/decommission criteria: Geen cleanup in expand. Verwijderen van inline historie of oude code pas na volledige pariteit, compatibele rollback en native bewijs. Geen archive GC geïntroduceerd.
Failure blast radius: De expliciete archiefcall kan falen; geen object-, review-, bron-, document-, release- of servingwijziging door dit increment.
Adversarial proof matrix: Alternatieve SQL-update/delete/truncate/bronwissel, forged prepared/reference, gelijktijdige gelijke/afwijkende write, transactiefout vóór commit, nieuw proces na commit, onbekende layout/missing/corrupt, beide productiecomposities en onafhankelijke archiefgroei.

## Open acceptatie voor geheel MET-41

Dit increment voldoet niet aan de volledige #950-belofte. Nog noodzakelijk:
complete gevalideerde formation-proof met immutable resultaatversies en alle
findings/bronbasis; voorbereiding buiten lock aan de echte callergrens;
geautoriseerde atomische referentiepin; alle variantadapters; operationele
read/write-integratie zonder hydratatie of triggerrewrite; native stale/rechten/
claim-, pinrollback- en echte groeiproeven op die actieve route. MET-42–44 blijven
hun eigen scope. MET-41 blijft open en de dependency op MET-40 blijft bestaan.

## Uitgevoerde review en verificatie

MET-40/PR #954 is tijdens deze uitvoering door de maintainer gemerged in
`main` (`8f7b891bdf887664ab6c07cf93b49459f2174c00`). De werkbasis heeft exact
zijn tree; deze PR kan rechtstreeks op main worden beoordeeld.

Een afzonderlijke read-only review op hetzelfde model vond drie te herstellen
punten: een ten onrechte begrensd revisiontoken, een onvolledige voorbeeldcall
en ontbrekende JSON-validatie bij directe SQL-insert/teruglezen. Alle drie zijn
hersteld en van native tegenproeven voorzien. De vervolginspectie vond voor
dit begrensde expand-increment geen resterende materiële fout. Dit is geen
cross-modelconsensus en vervangt geen runtimebewijs.

Werkelijk uitgevoerd op PostgreSQL 16, na `scripts/test_postgres.sh`:

- **61 gerichte tests geslaagd**: 24 archiefgevallen op beide bestaande
  productiecomposities, migratie-/runtimeprivilegecontroles en bestaande
  architectuur-, contract-, task-, source-, disposition- en gepubliceerde
  immutabilityproeven. De Azurevariant vervangt Blob/modeltransport via de
  bestaande testfactory; geen live Azure/providerclaim.
- Exacte oorspronkelijke replay en kwaliteitsrun, JSON-types/numerieke waarden,
  volledige native objectsetrevision, onbekende layout/missing/corruptie,
  verkeerde bron en niet-canonieke SQL-inserts getest.
- Echte concurrerende dubbele/afwijkende writes, division-by-zero tijdens
  de opslagtransactie, nieuw zelfstandig Pythonproces na commit, ongewijzigde
  document/objectstaat en toegestane volledige documentcascade getest.
- Smalle runtimegrants SELECT/INSERT op het archief werken; UPDATE/DELETE/TRUNCATE
  via directe SQL worden geweigerd. Migratie tweemaal toegepast zonder verlies.
- Mutatiecontrole in twee wegwerpdatabases: uitsluitend UPDATE-bescherming uit
  de triggerfunctie verwijderd. De beslissende bestaande test faalt op beide
  composities met “DID NOT RAISE”; productbestanden zijn niet gemuteerd.
- Change-contractvalidator, repositorypreflight, architectuurgrenzen, compileall,
  release-controlpreflight en whitespacecontrole geslaagd.

Eén metadata-lookup vóór/na 24 afzonderlijke archieven met elk circa 1 MiB
payload (synthetische lokale proef, geen Smetten-reproductie):

| Compositie | Archiefrecords | Query's | JSON-waarde-bytes | Alle gemeten tekst/JSON-waarde-bytes | Execute ms | Fetch ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Lokale bronadapter | 1 → 25 | 1 → 1 | 387 → 387 | 636 → 636 | 1,16 → 1,42 | 0,056 → 0,058 |
| Azure-bronadapterfixture | 1 → 25 | 1 → 1 | 387 → 387 | 636 → 636 | 1,46 → 1,29 | 0,049 → 0,048 |

De referentie is 236 bytes in beide gevallen. Dit meet de geselecteerde database-
waarden, niet TCP/protocoloverhead. Tijden zijn enkele lokale metingen, geen SLA
of p95. TEXT-loaderinstrumentatie telt ook een eventuele archiefpayload; alleen
JSON-bytes tellen zou de gekozen TEXT-opslag onvoldoende controleren.

De volledige suite is **niet groen verklaard**: een run is na 74 geslaagde
bestaande tests onderbroken om reviewbevindingen te verwerken. Daarna is de
bovenstaande gerichte suite op de definitieve productcode uitgevoerd. Volledige
suite/CI, browser, actieve-envelopekosten, activatiepin-/lockduurmetingen en
productieacceptatie blijven open. Geen productie- of gedeelde database gemigreerd,
geen bestaande historie opgeschoond en geen merge/deploy uitgevoerd door de agent.
