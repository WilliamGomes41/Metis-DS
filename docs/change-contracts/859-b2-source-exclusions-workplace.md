# Gezamenlijk bronbesluit in Vorming — #859-B2

Change class: B
Promise: Een toegewezen reviewer sluit geschikte bronregels met één gemotiveerd bronbesluit uit op Vorming; Review bevat geen tweede uitsluitformulier.
Proof: Browser/HTTP → bestaande POST → echte PostgreSQL → refresh/herstart, met behouden metadata-geschiktheid, rechten, revisie, idempotentie en rollback.
Touches lifecycle invariants: no
Rewrite risk: none

Part of #859, uitsluitend B2. Base **c59355c1e6f1a7dde7f2535f037657af6cd6485e**
is actuele main en bevat gemergde #866. Geen merge/deploy/productiemutatie.

## Ground

Deze slice vervolgt F3 uit [het overdrachtscontract](domain-workplaces.md).
B1 heeft individuele broncontext, inclusief excluded/reset, al naar Vorming
verplaatst. Hier verhuist uitsluitend de andere bestaande operatie:
`confirm_source_exclusions`. Dit is een exact metadata-/structuurbesluit, geen
algemene batchafhandeling van inhoudelijke bronpassages.

Huidig: Review inventory/disposition → `_render_review_room` → bestaande
`snapshot_objects_and_revision`, `_review_bindings`, `review_source_fragments` →
`_review_inventory` → POST `/review/source-exclusions` →
`source_context_review_v1.confirm_source_exclusions`. Dat laatste controleert
named reviewer, publicatie-immutability, command-ID/payload, objectsetrevisie,
exacte bron/open-original en uitsluitend voorgestelde metadata/structuur zonder
bestaande rol/context of bevestigde kennis. Het commit objectversies, register,
bindinginvalidatie en event via de bestaande workflowbundle.

Dezelfde huidige objects en bronverantwoording zijn nodig voor de documentbrede
selectie. Dit is de bestaande expliciete documenttaak, geen terugval van de
bounded individuele contextlezer uit B1. PostgreSQL-mixins, request-readcontext,
source reconstruction scope, `_commit_prepared_store` en de workflowtransactie
blijven hun bestaande eigenaren. Geen reader/writer/endpoint wordt toegevoegd.

Gewenst: bestaande GET `/source-selection?document=S&task=disposition` rendert
dezelfde broninventaris en hetzelfde formulier. Het objectdetail uit B1 blijft
voorrang houden als `object` aanwezig is. De overzichts-/probleemkaart en
Review-inventaris verwijzen naar de enige editor. Review houdt bronstatus en
bronopeners; metadata-selectievakjes en uitsluitformulier verdwijnen daar.
Na POST volgt Vorming. Bestaande generieke fout-/conflictuitkomsten blijven
behouden; geen nieuwe draftopslag of domeinuitkomst.

Callers: `_render_review_index` en `_review_inventory` voor inventory/disposition,
Vorming-documentkaart, POST-vervolg, bestaande HTTP/native bronverantwoordingtests,
de browserbroncontextfixture en de twee overzichtsgoldens. Directe POST en Python
command blijven ondersteund. Geen CLI, dispatcher of runtime-override verandert.
Historische inventory/disposition-GETs blijven read-only nodig voor gemengde
kennis-/bronstatus; gerichte links openen Vorming. Niet-verplaatste C1-handelingen
worden niet via een algemene redirect meegenomen.

## Domein en stateful Class B-overlay

- Domain entity/aggregate: bestaande WorkingRevision met exacte bronrecords.
- Invariant(s): alleen named reviewer; metadata/structuur zoals bestaande command
  toestaat; exacte bron en open-original; verplicht reden/broncontrole/command-ID/
  objectsetrevisie; geen kennisgoedkeuring, nieuwe kandidaat of publicatierecht.
- Durable state before: open ongepubliceerde revisie met onbevestigde bronrecords.
- Durable state after: dezelfde bestaande commanduitkomst: nieuwe versies met
  excluded_with_reason, invalidatie en audit; niet-geselecteerde kennis/bron gelijk.
- Transaction boundary: bestaande `_store_write_lock`, workflowtransactie,
  PG-documentrijlock, CAS en `_commit_prepared_store` voor versies/bindings/event.
- Failure/recovery result: geweigerd/stale/DB-fout geen gedeeltelijk bronbesluit;
  herstart leest bestaande PG-authority. Geen reset of nieuwe herstelstatus.
- Duplicate execution / idempotency result: bestaande ID/payload herhaalt resultaat;
  afwijkende payload met dezelfde ID wordt geweigerd.
- Concurrency result: command bewaakt objectsetrevisie onder bestaande transactie;
  gelijktijdige schrijver maakt verouderde opdracht conflict.
- Audit/evidence requirement: bestaand source_exclusions_confirmed-event met
  actor/reden/payloadhash/exacte versies. Bronbytes, bronhash, kandidaatidentiteit,
  oude versies, releases en serving blijven onveranderd.

## Sketch → Agree

Gebruik: reviewer opent Bronverantwoording vanuit Vorming of de read-only
Review-inventaris → controleert bron en geschikte selectie → dezelfde POST →
Vorming toont de opgeslagen afhandeling → Review blijft bereikbaar voor kennis.
De bestaande shapes snapshot_id/source_object_ids/snapshot_revision/command_id/
reason/source_checked volstaan. Geen nieuwe datastructuur of infrastructuur.

Twee vormen, beide door dezelfde auteur getoetst aan #857:

| Vorm | Invarianten / leespatroon | Caller en cleanup |
| --- | --- | --- |
| Bestaande inventarisrenderer met bronweergave en expliciete editoptie | Dezelfde projectie en documentread; dezelfde command | Eén formulier op Vorming, Review direct read-only |
| Nieuw bronbatchpaneel met eigen selectie-/geschiktheidsprojectie | Risico op tweede afleiding en gemiste bron-/versiegrenzen | Parallelle renderer en regels; verworpen |

Gekozen eerste vorm: twee presentatieopties onderscheiden bronweergave van
bewerkbare uitsluiting; defaults maken Review read-only. Alleen de bestaande
Vorming-GET leest en rendert de editor, met dezelfde bron-/bindingsinput als
voorheen. Gepubliceerd werk krijgt alleen weergave, de commandguard blijft
ongewijzigd. Geen nieuwe algemene workspace-/tasklaag. Agree volgt de expliciete
uitvoeringsopdracht; geen extra goedkeuringspoort.

De architect-referentiebestanden konden ook deze run niet via hun opgegeven
skill-resource worden gelezen; de hoofdskill en bestaande projectmapping zijn
wel gelezen. Geen onafhankelijke review of subagents geclaimd.

## Implement → Scrap en verificatie

Verplaats formulier, bronselectievakjes en POST-vervolg samen. Behoud de enige
POST-route en command. Verwijder oude actieve Review-inputs in dezelfde PR.
De bestaande metadata-/structuurgeschiktheid en niet-geselecteerde inhoudelijke
passage blijven door echte commandtests bewaakt. Native tests voor stale,
concurrent schrijver, DB-rollback, duplicate, rechten en herstart blijven intact.
Pas HTTP/browsertests aan op de eigenaar plus afwezige oude editor, geen
negatieve substringasserties op gedeeld JavaScript. GET/refresh blijven zonder
schrijfeffect. Vergelijk dezelfde readercalls vóór/na in de nieuwe HTTP-proef.

Rollback: code/presentatie terugzetten bij dezelfde huidige command en readers;
geen datareset, oude approval herstellen of bron-/auditgeschiedenis terugschrijven.
Nog buiten B2: koppen/relaties, bronvoortzetting, graafeditor en gekoppeld
kandidaatherstel C1; daarna C. #859/#857 blijven open.

## Werkelijk bewijs

Dezelfde bestaande source-usage-projectie groepeert ook handmatig afgehandelde
legacyrecords als afgehandeld. Zo verschijnen opgeslagen uitsluitingen bij
refresh niet onder “Brongebruik nog te bepalen”; er is geen tweede statusafleiding.

De werkelijke inventarisrenderer is geïsoleerd met dezelfde metadata- en
inhoudelijke bronfixture op base en wijziging uitgevoerd: Review-formulier 1→0,
Vorming precies één formulier met uitsluitend hetzelfde metadata-ID; gepubliceerde
weergave zonder formulier. Invoer bleef gelijk. Dit is renderer-/projectiebewijs,
geen HTTP-/PostgreSQL-acceptatie. Twee goldens zijn alleen in hun HTML veranderd:
het oude formulier/vakje is vervangen door bronweergave en de eigenaarlink.

Voor consoletests is eerst `scripts/test_postgres.sh` uitgevoerd; die kan niet
starten omdat psycopg ontbreekt. PG16/pytest zijn lokaal eveneens niet beschikbaar.
Shellproxy is nog onbereikbaar voor git fetch; de GitHub-plugin levert remote
bron/publicatie. De main-mergecommit is lokaal hash-gecontroleerd en heeft dezelfde
tree als de geïntegreerde #866. Skill-referenties en Linear get_agent_context
zijn geadverteerd maar niet beschikbaar; geen verzonnen context toegepast.

Verplichte statische checks en werkelijk gestarte/geblokkeerde runtimechecks
worden bij oplevering met exacte head en resultaten in de PR vastgelegd.
Geen productie-/inhoudelijke gebruikersacceptatie uit synthetische proeven afleiden.

## Eerste CI-diagnose

Head `8febdd955034aabd462e8a4a613fb5bfa3e02756` faalde op de nieuwe
HTTP-stale-assertie (400 ontvangen, 409 verwacht) en horizontale overflow in de
nieuwe browserfixture; dezelfde browsercase faalde ook in source-processing-proof.
Characterization, de statische gates en de normale native source-processing-
proeven (12 + 158) slagen. De vroege rode autorisatieproef in die workflow is
de verplichte historische mutatieproef.

De batch-POST heeft altijd de generieke ConsoleError-afhandeling gebruikt:
die retourneert 400 bij snapshot_object_write_conflict. De test respecteert die
bestaande HTTP-uitkomst en controleert nu expliciet de conflictmelding plus
ongewijzigde objecten en events. Geen domein-/API-regel aangepast om 409 te maken.
De werkelijke statusselectie uit de handler is lokaal geïsoleerd uitgevoerd: 400.

Chromium is lokaal beschikbaar; de sandbox blokkeert zijn sockets. De lokale,
netwerkloze markup-/CSS-proef is daarna via de goedgekeurde executorroute
uitgevoerd op de bestaande inventarisgolden: geen overflow op 1440 en 390 px.
Dat is geen reproductie van de afwijkende runtimefixture. De bestaande strenge
browserassertie rapporteert daarom voortaan stadium, breedte en de concrete
overlopende DOM-elementen. Layoutoorzaak en browserherstel zijn op dit moment
nog niet bewezen; de vervolguitvoering wordt in de PR vastgelegd.

## Vastgestelde layoutoorzaak en herstel

De tussentijdse run op `48b92e327716b9e2d3c2e635a7aadda54c01defd` wijst
exact één overlopend element aan: de kennisvoorstel-anchor `review-row-title`
in Review-inventory. Op 390 px is die anchor in CI 601 px breed. De globale
titelstijl gebruikt nowrap; de bestaande wrapregel voor review-section bereikt
de inventaris niet. De korte titel uit de golden maskeerde die situatie.

Met dezelfde lange titel als CI in de bestaande inventarismarkup is de lokale
Chromium-assertie rood op de oude stylesheet: 533 px inhoud bij 390 px viewport.
Na de beperkte regel `.review-passage-inventory .review-row-title` met normal
white-space en overflow-wrap anywhere is diezelfde assertie groen op 390 en
1440 px. De fontmetrics verschillen per omgeving; beide tonen dezelfde nowrap-
fout. Geen overflow hidden, afkappen of afgezwakte breedteassertie toegevoegd.

De 32 bestaande HTML-goldens krijgen uitsluitend de nieuwe contenthash van de
stylesheet in hun bestaande asset-URL. Geen andere JSON-velden veranderen.
De concrete DOM-diagnose blijft bij de browserassertie, zodat een terugval de
precieze rij en breedte meldt. Volledige native/browser/CI-acceptatie van de
herstelhead en exacte SHA worden na afloop in de PR vastgelegd.
