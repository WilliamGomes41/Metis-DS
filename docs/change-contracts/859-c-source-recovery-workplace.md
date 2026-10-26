# #859-C — pagina-afhandeling en herstelautorisatie op Vorming

Change class: B
Rewrite risk: none
Touches lifecycle invariants: no
Promise: Pagina-afhandeling en bevoegde herstelautorisatie zijn uitsluitend bewerkbaar op Vorming; Inzicht verklaart en toont bewijs.
Proof: Native PostgreSQL/HTTP en browser bewijzen de bestaande commands, rechten, bronbinding, duplicate/herstart, geen GET-writes en geen grantconsumptie door autoriseren.

## Ground

Basis main: `96b22c16c6aacc554d64ccf75971595a5d549000`, na #870.
Deze run realiseert alleen C van #859; A en B zijn gemerged. Geen #860,
merge, deployment, productiemutatie of automatische doorstart.

| Bestaande handeling | Huidige → gewenste werkplek | Bestaande eigenaar / opslag |
| --- | --- | --- |
| Pagina zonder kennisinhoud verantwoorden | Inzicht-document → geselecteerd document op Vorming, `#paginas` | POST `/inzicht/document/pagina-verantwoorden` → `OperationsConsole.account_source_page`; append-only `source_page_accountings` in bestaande envelope |
| Eén extra herstelpoging autoriseren | Inzicht-document → geselecteerd document op Vorming, `#processing-recovery` | POST `/tree/processing-recovery` → `authorize_processing_recovery`; bestaande `processing_recovery` in envelope |
| Diagnose, findings en vastgelegde verantwoordingen | Inzicht → Inzicht, alleen lezen | Bestaande document-/attemptlezing; geen nieuwe reader of status |

Vorming heeft in zijn geselecteerde detail na `collect` de volledige request-envelope en
`formation_problems_v1.collect(...)[processing]`. Hergebruik deze invoer zonder
extra statuslezing. De compacte lijstrow bevat niet alle attemptdiagnostiek;
gebruik de al door `collect` geladen volledige envelope via dezelfde `_envelope`. De bestaande paginaweergave verhuist naar
`source_selection_ui_v1` als pure renderer: read-only standaard, expliciet
bewerkbaar uitsluitend bij Vorming. Inzicht gebruikt dezelfde read-only weergave.
Beide POSTs blijven direct hun huidige command aanroepen. Foutpresentatie gebruikt
dezelfde pure formulierweergave met tijdelijke escaped invoer; geen duurzame UI-status.

Callers: samengestelde production-app (`build_console_app` en navigation simplify),
deze twee formulieren, gerichte pagina-/cap-acties in `formation_problems_v1`,
historische directe HTTP-POSTs, directe Python-commands,
native diagnostiek-/extractorproeven en scripts. De commands hebben geen eigen
runtimeoverride; `_reprocessing_transaction` en prepared commit worden wel door
de bestaande PostgreSQL-productionruntime geleverd. Alle blijven behouden.

## Sketch → Agree

Twee echte onafhankelijke read-only verkenningen: `/root/c_design_a` en
`/root/c_design_b`. Gedeelde architectreferenties en Linear-agentnotes konden
niet via de provider worden gelezen; hoofdskills en repositorycontracten wel.

| Vorm | Rechten / leespatroon / locality / bewijs |
| --- | --- |
| A: gerichte `task=source-recovery`-pagina vóór de documentprojectie | Focus bij fouten, maar herhaalt lees-/toegangsopbouw en vraagt een bijzondere ontvangstcontext voor publisher-only; extra presentatie-ingang niet nodig |
| B: bestaande geselecteerde documentkaart met pure formuliercompositie | Gekozen: hergebruikt bestaande envelope/status, één bewerkbare werkplek, lokale cleanup; POST-fouten gebruiken dezelfde formulieren |

**Bewezen asymmetrie behouden:** een aangewezen publisher-only actor mag via de
bestaande command herstel autoriseren, maar niet `processing_status(actor_id=...)`
of bronselectie gebruiken (`test_separate_publisher_recovery_requires_current_authority`).
Geen nieuwe processing-readrechten en geen `actor_id=None`-omweg. Deze ondersteunde
niet-UI-POST behoudt zijn bestaande terugkeer naar read-only Inzicht; normale
formuliercallers keren terug naar Vorming. Dit is een expliciete
presentatiecompatibiliteit, geen tweede editor of command.

Implementatie is expliciet opgedragen; geen extra goedkeuringscheckpoint.

## Bestaande stateful Class B-grens

| Veld | Pagina-afhandeling | Herstelautorisatie |
| --- | --- | --- |
| Aggregate | Snapshot/envelope, actuele laatste poging | Zelfde snapshot/envelope en pogingen |
| Vóór → na | Laatste poging failed/PAGES_UNRESOLVED, geen kandidaten → één accounting met actuele pagina/reasons/hash/poging/actor | Cap bereikt, niet actief, bestaande pre-review/resumegrens → één ongebruikte grant met bronhash/versie/revisie |
| Rechten/invarianten | Bestaande bronselectieautorisatie, unpublished, categorie, notitie 10–500 tekens, actuele finding | Actuele publisher én uploader/aangewezen; unpublished; geen structurele limiet; bestaand werk beschermd |
| Transactie | Bestaande `_reprocessing_transaction` met actuele herlezing en `_commit_prepared_store` | Zelfde bestaande documenttransactie en commit |
| Duplicate/concurrent | Bestaand documentrijslot; dezelfde pagina/reasons/hash weigert duplicate | Eén grant; tweede opdracht weigert; alleen bestaande reservering consumeert |
| Fout/herstart | Geen gedeeltelijke write; bestaande PostgreSQL-feiten opnieuw lezen | Geen poging starten, geen grant consumeren; grant blijft bij herstart |
| Audit/bewijs | Bestaand accountingrecord en attemptdiagnostiek | Bestaand grantrecord; geen extra auditregister |

Er komt geen client-CAS bij deze formulieren. Accounting post alleen
snapshot/page/category/note; het command bindt onder transactie de **actuele**
finding en bronhash. Een gewijzigde finding op dezelfde pagina is onder het
bestaande contract geen extra stale-tokenconflict. C verandert die regel niet.

Context: snapshot-ID uit bestaande link/formulier; actor uit actuele sessie;
bronhash/reasons/poging en grantrevisie uitsluitend uit de commandherlezing.
Notitie/reden blijven vluchtige formuliervelden tot de bestaande write slaagt.
Ontbrekende/ongeldige context faalt volgens dezelfde domeinregels.

## Implement → Scrap en bewijs

- Verplaats beide bestaande forms; verwijder Inzicht-mutatiecontrols meteen.
  Diagnoseanchors blijven bewijs met gerichte Vorming-links. GET start/sluit niets.
- Native HTTP/accounting: geldige POST en restart, exacte bron/finding,
  duplicate, foutieve pagina/categorie/notitie, outsider en gevormde bron.
- Native grant: juiste rol/toewijzing en publisher-only directe caller,
  duplicate/structurele limiet/actieve poging, restart; pogingen en consumptie
  veranderen niet door autoriseren of navigatie. Hergebruik bestaande
  concurrent-consumptionproef voor de expliciete vervolgreservering.
- Echte browser breed/smal/toetsenbord: Inzicht → eigenaar → bestaande POST →
  refresh/herstart; grant en Start/Hervatten blijven afzonderlijke handelingen.
- Vergelijk domeincommands en opslagoverrides met de basis; verplichte checks en
  volledige actuele CI. Exacte SHA/resultaten/bewijsgrenzen komen in de PR.

Geen nieuw framework, reader/writer, endpoint, register, cache of opslag.
Als een domein-/lifecycle-/gedeelde grens moet veranderen: stop en herscope.
Rollback betreft presentatie/links samen; bestaande accountings/grants blijven.
