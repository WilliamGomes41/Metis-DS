# #859-A — Eén Vorming-werkplek voor starten, hervatten en problemen

Change class: B
Promise: De gebruiker vindt voortgang, de bestaande start-/hervatbediening en verwerkingsproblemen op één Vorming-werkplek zonder tweede actief formulier.
Proof: Native PostgreSQL HTTP-proeven voor één formulier, read-only bookmarks, gerenderde hervatopdracht, stale/duplicate/unauthorized en refresh/herstart; bestaande browserproef en begrensde reads. Werkelijk uitgevoerd bewijs staat afzonderlijk hieronder en in de PR.
Touches lifecycle invariants: no
Rewrite risk: none

Part of [#859](https://github.com/WilliamGomes41/Metis-DS/issues/859), uitsluitend
deel A / PR 2 uit [#857](https://github.com/WilliamGomes41/Metis-DS/issues/857).
Basis: `728b6a9d582819392ee0c2b3d6253ce0857428e3`, de gecontroleerde merge
van PR #864. Het [routecontract](domain-workplaces.md) blijft de mapping voor
het hele project; de historische URL-namen zijn geen reden nieuwe routes te maken.

## Ground → Sketch → Agree

De bestaande GET `/source-selection` bezit voortgang, compacte documentselectie
en een POST-formulier naar `/source-selection/start`. De aparte probleemkamer
bezat een tweede formulier naar dezelfde route. `formation_problems_v1.collect`
leest afgeleid bewijs, geen zelfstandige probleemtoestand. De dispatcher en de
bestaande kernelcommandketen blijven de uitvoerders; PostgreSQL en Azure blijven
de eigenaren van respectievelijk werk en immutable bron.

De twee vormen uit #857 zijn door dezelfde auteur aan deze slice getoetst:

| Vorm | Routes/ownership | Reads en concurrency | Cutover |
| --- | --- | --- | --- |
| Nieuwe `/formation`-route met adapters | Extra route/doorstuurlaag, verworpen | Vergroot de callchain en kan controles dupliceren | Vereist een extra compatibiliteitslaag |
| Bestaande `/source-selection` verdiepen, gekozen | Zelfde GET/POST/commandowner; één werkplek | Overzicht blijft compact; probleemdetails uitsluitend voor het gekozen document | Oud probleemscherm wordt een read-only bookmarkredirect, tweede formulier/menu-ingang verdwijnen |

De gecombineerde geselecteerde GET leest `collect` eenmaal en geeft zijn
reeds berekende `processing` aan de bestaande `source_selection_v1.projection`.
Die projectie autoriseert nog steeds zelf en leest haar bestaande objectinputs;
alleen de herhaalde `processing_status`/diepe volledigheidscontrole vervalt.
Dit is verliesbare invoer binnen hetzelfde verzoek, geen cache, nieuwe reader
of commandinvoer. Bestaande callers zonder deze invoer berekenen hun status
ongewijzigd. Er verandert geen gedeelde lees-/schrijfautoriteit.

Gebruik: document openen op `/source-selection?document=S`, probleemdetails op
dezelfde pagina, expliciet Starten/Hervatten via de bestaande POST. Een oude
`/formation-problems?document=S&offset=N`-bookmark navigeert naar dezelfde
snapshot/offset. Een gewone GET start, annuleert of sluit niets. De bestaande
herstel-/bronlinks bij bevindingen blijven bereikbaar; Inzicht blijft optionele
verdieping. De expliciete gebruikersopdracht autoriseert deze implementatie;
Agree is geen claim van onafhankelijk inhoudelijk akkoord.

## Domein en ongewijzigde commandtransactie

De presentatie is stateless, met uitsluitend geselecteerd document/offset in
de URL. De bestaande start-/hervatopdracht is stateful:

| Bestaande overlay | Ongewijzigd contract |
| --- | --- |
| Domain entity/aggregate | SourceSnapshot/WorkingRevision en de bestaande processing attempt |
| Invariants | Exacte bron-/snapshot-/kandidaatidentiteit, rechten, revisie, reviewbescherming, retry/deadline/claim en publicatiegrenzen uit #857 en de bestaande owners |
| Durable state before | Ongevormde of gedeeltelijke bron waarvoor de bestaande kernel starten/hervatten toestaat |
| Durable state after | Bestaande reservering, daarna bestaande uitvoering en geldige activatie of bestaande fout-/partial toestand |
| Transaction boundary | `reserve_source_selection` → `reserve_selection` → bestaande `_reprocessing_transaction`/CAS; dispatcher-notificatie na commit is een hint; activatie behoudt haar eigen bestaande transactie |
| Failure/recovery result | Bestaande fouten en behouden bron/taakresultaten; herstart hervindt pending pogingen via bestaande dispatcher; geen nieuwe herstelwaarheid |
| Duplicate execution / idempotency result | Zelfde command-ID/actor/bron/revisie hergebruikt bestaande poging; conflicterende invoer behoudt de bestaande weigering |
| Concurrency result | Bestaande documenttransactie, command-CAS en workerclaims; geen browserlock of nieuw synchronisatieprotocol |
| Audit/evidence requirement | Bestaande actor, bronhash/-versie, poging, command-ID, resultaten en reviewbindings blijven behouden |

De wijziging voegt geen domeinovergang toe en wijzigt geen commandbody, bronbytes,
kandidaatmaker, reviewbinding, publicatievoorwaarde of serving-authority. De
gecombineerde review-/repairbotsing C1 uit het routecontract blijft buiten A.

## Implement → Scrap

- Bestaande voortgang en probleemrenderer samengebracht onder Vorming; één
  start-/hervatformulier met bestaande document/revisie/command-ID-invoer.
- Dubbel formulier in `_formation_problems_html`, oude probleemdocumentkiezer
  en tweede menu-ingang verwijderd. Het oude GET-pad behoudt alleen
  geauthenticeerde bookmarknavigatie; documenttoegang controleert de eigenaar-GET.
- Mijn werk, navigatie, ingest-uitleg, documentvervolg, Review-waarschuwing en
  Inzicht-link verwijzen naar Vorming. De bestaande POST en CLI/dispatcher blijven
  dezelfde owner gebruiken. Geen nieuwe API, store, schema of runtimeconfiguratie.
- Raad observeert de probleemdetails op de al geopende documentpagina en herhaalt
  die GET niet. Zijn bestaande read-capabilitygrens blijft intact. Oude
  allowlists behouden het read-only bookmarkpad als compatibiliteit.
- Bestaande browserchecks zijn naar de ene werkplek overgezet. De 34 gewijzigde
  characterization-goldens bevatten alleen aangepaste HTML: menunaam, verwijderde
  tweede navlink, gerichte link en ingest-uitleg. Dit is een gerichte tekstuele
  aanpassing van de verwachte presentatie, geen lokaal opnieuw opgenomen browserbewijs.

Na A blijven bronbestemming/context/structuur/kandidaateditors in Review tot B;
pagina-afhandeling en herstelautorisatie blijven in Inzicht tot C. Deze
verschillende handelingen zijn nog niet overgezet. #859 is dus niet gereed;
deze PR sluit #859 of #857 niet. Er is geen automatische doorstart naar B.

Rollback zet alleen presentatie/callers terug naar één vorige werkplek, met
behoud van de huidige #848-v2-activatiereader/writer. Geen objecten, grants,
taakresultaten, revisies of reviewbindings terugschrijven/resetten.

## Bewijs en grenzen

`tests/test_formation_workplace.py` gebruikt de bestaande echte productiecompositie
en native PG-fixture. Het toetst overzicht zonder start, één formulier op detail,
de read-only redirect met dezelfde snapshot/offset, één statusberekening,
ongewijzigde duurzame toestand bij navigatie, partial bevindingen en behoud van
de eerste kandidaat bij hervatten via het werkelijke gerenderde formulier na
herstart. Stale en duplicate POSTs behouden de bestaande commanduitkomst.
De bestaande onbevoegde probleemtest toetst nu ook POST-weigering zonder write.
De bestaande `test_source_selection_read_cost.py` blijft de at-most-one
envelope/objectread en isolatie van reads/commands bewaken. Geen guards verzwakt.

Werkelijk lokaal: compileall, architectuurgrenzen, de bestaande stdlib
referentiecontrole van het routecontract en JavaScript-syntaxcontroles slagen.
Een geïsoleerde uitvoering van de werkelijke pure probleemrenderfuncties vergelijkt
de basis en wijziging: duplicaatformulier 1 → 0; alle 201 synthetische meldingen
blijven uniek bereikbaar over drie pagina's, zonder mutatie van de invoer.
Dat is uitsluitend rendererbewijs, geen HTTP-/PostgreSQL-/browserbewijs.

`scripts/test_postgres.sh` en de gerichte native testaanroep zijn geprobeerd:
psycopg/PostgreSQL 16 en pytest ontbreken. Installatie van pytest en de bestaande
testdependencies uit PyPI kon geen pakketten verkrijgen. Daarom zijn de native
proeven, browserproeven en volledige pytest-suite lokaal niet uitgevoerd.
De PR rapporteert alle laatste verplichte controles op de exacte head en vraagt
CI om het ontbrekende runtimebewijs; geen skip of oudere CI als groen bewijs.
Geen claim van volledige acceptatie of productiegedrag. Geen merge/deploy of
productiemutatie in deze run.
