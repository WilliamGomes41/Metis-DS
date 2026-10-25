# Raad: bruikbaarheid en weergavetrouwheid

Change class: B
Promise: Raad meldt alleen een bruikbare hoofdpagina wanneer de taakbediening en bedoelde gegevens beschikbaar zijn, en de bestaande documentcontrole vergelijkt zichtbare inventaristekst met opgeslagen gegevens met begrensde diagnose.
Proof: Echte Chromium-proeven op de PostgreSQL-testconsole, geïsoleerde foutinjectie, revisie-/toegangsproeven en gelijkblijvende domeintoestand.
Touches lifecycle invariants: no
Rewrite risk: none

Rechtstreekse implementatieopdracht in de chat, 25 oktober 2026. Repositorywerk zonder merge of deployment. Begintoestand: schone branch `work`, commit `f133b860379ecd1ee3a1e8b52055a6afb830add1`. Er was geen GitHub-issue toegewezen. De expliciete implementatieopdracht is de autorisatie voor dit werk; er wordt geen issue- of deploymentautorisatie geclaimd.

## Onderzoek en gekozen structuur

De browserpaginacontrole in `assets/brand/care-companion.js` opent één verborgen sandboxframe tegelijk met de menselijke aanmelding. Zij schrijft alleen de laatste tabbladuitkomst in sessionStorage. Zij gebruikte HTTP-status, foutbanner, Raad-kop en scriptfouten, gevolgd door 1,5 seconde rust. Bruikbaarheid: gedeeltelijk; daadwerkelijke datagereedheid ontbrak. Toegangsweigering, verlopen sessie, in-flight hergebruik en herstel na herladen bestonden al.

De documentcontrole `src/view_check.py` -> `scripts/view_check.cjs` is een afzonderlijk begrensd browserproces met een documentcapability. `ViewCheckStore`/PostgreSQL blijven de enige taakautoriteit. `EvidenceStore`/private Azure blijven eigenaar van schermbewijs; geen nieuwe tabel of opslagfallback. Context/revisie/autorisatie worden voor, tijdens en na de controle opnieuw gecontroleerd. Vergelijking van identiteit, partitionering, links en bronselectie bestond; weergavetrouwheid van tekst en volgorde ontbrak. Bij browserfalen ontbrak compacte stap-/requestdiagnose.

Ontwikkeling/CI gebruikt de echte app met PostgreSQL en synthetische gegevens via `tests/browser_*`, los van beide productcontroles. `scripts/probe_section.cjs` correleerde navigatie al met `x-metis-request-id` en `x-metis-attempt-id`; de eerdere zichtbare-kopassertie bewees nog geen bruikbaarheid. Requestdiagnostiek en verwerkingstelemetrie blijven de bestaande eigenaren. Een waarneming dat een gegevensverzoek wacht is geen verklaring van een databaseoorzaak.

Twee ontwerpen zijn door dezelfde agent vergeleken: (1) afzonderlijke readinesscriteria kopiëren naar Raad en de externe probe; (2) één kleine zuivere DOM-waarneming in een brandasset, gebruikt door beide. Gekozen: (2), omdat dezelfde functie dezelfde vier uitkomsten kan onderbouwen zonder nieuwe request-, werkstatus- of diagnoseautoriteit. De bestaande documentworker blijft apart vanwege zijn documentrechten en revisiefence. Geen vervanging van lifecycle-, lees- of opslaggrenzen.

Aanroeppad: bestaande pagina-eigenaar rendert inhoud/laadtoestand -> `page-readiness.js` leest concreet DOM -> Raad of externe probe wacht begrensd -> bestaande resultaatpresentatie. Inzicht publiceert alleen de toestand van zijn eigen bestaande gegevensverzoek (pending/ready/partial/error), status en bestaande requestreferentie. Geen extra scan. De documentworker leest dezelfde bestaande passage-export en vergelijkt zichtbare `innerText`; geen objectvorming of betekenisreconstructie.

Mutaties: alleen bestaande operationele view-check-registratie, resultaat en toegestaan screenshotbewijs; geen bron-, kennisobject-, review- of publicatiegegevens. PostgreSQL-leases, deduplicatie, capability, revisiefences en Azure-retentiecontract blijven gelden. Sluiten/heropenen deelt de lopende controle; herladen toont de laatste uitslag. Oude sessionStorage-uitslagen zonder `task-ready-v2` worden niet als bruikbaarheidsbewijs hergebruikt.

## Gereedheidsvoorwaarden

| Hoofdpagina | Kleinste betekenisvolle voorwaarde |
| --- | --- |
| Mijn werk | Taaktegels met bruikbare navigatielink |
| Inleveren | Bestaand uploadformulier met bestandskeuze |
| Bronselectie | Documentkeuze plus documentstatuskaart of expliciete lege toestand |
| Review | Inventaris/taakkaart of expliciete lege toestand |
| Publicatie | Documentkaart of bestaande expliciete lege toestand |
| Documenten | Documentregel of expliciete lege toestand |
| Instellingen | Werkelijke beheernavigatie beschikbaar |
| Inzicht | Documenttabblad zichtbaar en bestaand documentenverzoek volledig geladen; gedeeltelijke metadata/diagnostiek slaagt niet |

Raad houdt maximaal 20 seconden per pagina en de bestaande 1,5 seconde observatieperiode aan; daarna concrete readinesswaarneming om de 100 ms, zonder netwerkpolling. Vier uitkomsten: bruikbaar, afwijking, niet vastgesteld, niet gecontroleerd wegens ontbrekende toegang. Een gedeeltelijke lege lijst is geen volledige lege toestand. Navigatie naar Inzicht kiest expliciet het documenttabblad. Requestreferenties linken naar de bestaande verzoekdiagnostiek; ontbrekende referenties blijven null.

## Weergavetrouwheid en diagnose

De inventariscontrole vergelijkt `content.clean_text`, de zichtbare bronlabelcontext `source_label_hint.label`, kennisregelvolgorde, identiteit, bronpartitionering en reviewlinks. Verwachting: bestaande revision-pinned passage-export. Vergelijking: zichtbare gerenderde tekst, na openen van bron-disclosures; verborgen tekst telt niet als waargenomen; uitsluitend ASCII HTML-witruimte wordt samengevouwen. Tekst, voorwaarden/uitzonderingen binnen die tekst, hoofdletters, Unicode en volgorde blijven betekenisvol. Een mismatch wordt geteld zonder broninhoud naar algemene diagnose te kopiëren.

Resultaat vermeldt gecontroleerde/ongecontroleerde object-ID’s, velddekking, normalisatie en grenzen. Afzonderlijk gestructureerde voorwaarden, uitzonderingen, bronlocators en contextrelaties die de inventaris niet toont worden niet gecertificeerd. Ook bronregelvolgorde tussen de verschillende bewust gegroepeerde bronsecties wordt niet gecertificeerd. Geen claim van klinische juistheid of volledige bronextractie.

Mislukking/onvolledigheid bewaart via het bestaande onderzoeksresultaat stap, verwachting, waarneming, verstreken tijd en maximaal 12 gegevensverzoeken plus 4 nog lopende of mislukte assetwaarnemingen met vaste route, toestand, HTTP-status en geldige bestaande request-ID. Geen URL-query, cookie, token, autorisatieheader, DOM of exceptionproza. Bij subprocessuitval resteert expliciete workerdiagnose; niet-waargenomen requests worden niet ingevuld. Een gewijzigde revisie maakt eerdere passes niet vastgesteld. Geen trace/HAR: de bestaande inrichting levert geen veilige redactieroute voor sessiehoudende traces; compacte diagnose en bestaand beschermd screenshotbewijs blijven de grens.

## Impeccable-audit en gerichte verbetering

`npx impeccable install` (CLI 4.7.0) kon de bundel vanaf impeccable.style niet ophalen. De officiële GitHub-bron is wel bereikbaar. Het pakket is met zijn eigen `link`-commando lokaal gekoppeld; gebruikte instructies: Impeccable 4.7.1, broncommit `658b4ce2942171ed5b3b3bec7e9d99456ba86e5e`. De pakketbestanden en lokale koppeling zijn geen productieafhankelijkheid en worden niet met Metis meegeleverd. `context` is eenmaal uitgevoerd; de bestaande code en Metis-brandtokens zijn de visuele autoriteit. Dit is een begrensde Operate-verfijning, geen herontwerp of nieuw dashboard.

De daadwerkelijke `reference/audit.md` is toegepast op de werkende oorspronkelijke interface: originele markup, JS en CSS van `f133b860` boven dezelfde geïsoleerde testapp. De echte Impeccable-detector draaide via een uitsluitend lokaal DevTools-kanaal; er zijn screenshots en geometrie-/contrastmetingen gemaakt vóór verdere ontwerpwijzigingen. Geen sessie-export, HAR of trace. `clarify`, `adapt` en `polish` sturen de vervolgaanpassingen; er wordt geen formele onafhankelijke `critique` geclaimd.

Implementatie-integriteit: **pass binnen Raad**. De uil, bestaande bediening, kleurvariabelen en huisstijl zijn productgebonden. De detector gaf zeven meldingen: vier waarschuwingen over merkpaars en één over de zwevende kaart zijn na contextcontrole geen reden om de huisstijl of het hulppaneel te vervangen; één laag-contrastmelding betreft de bestaande h1 buiten Raad; één advisory betreft een losse laatste regel. De externe h1 valt buiten deze wijziging.

| Auditdimensie | Baseline / 4 | Belangrijkste waarneming |
| --- | --- | --- |
| Toegankelijkheid | 3 | Goede contrasten en bestaande Escape/focus-terugkeer; de hele paneelinhoud was één live-regio |
| Performance | 3 | Geen zware UI-afhankelijkheid; verzoekhergebruik en begrenzing bestaan; geen gemeten latencybaseline |
| Thema’s | 4 | Merk-/thematokens; gemeten Raad-tekstcontrast licht 7,50–15,52 en donker 7,90–14,50 |
| Responsive | 2 | Sluiten 31,45×27,19 px; bij 844×390 en 200% tekstgrootte begon het paneel op y=-43 |
| Implementatie-integriteit | 3 | Herkenbaar productpatroon, maar twee concurrerende primaire acties en veel tegelijk zichtbare uitleg |
| Totaal | 15 / 20 | Good; gerichte correcties, geen vervanging van de bestaande visuele wereld |

Prioriteiten en uitgevoerde correcties:

- **P1, responsive:** het paneel moet ook met grote tekst in landschap binnen de viewport blijven. De hoogte houdt nu rekening met de uil, ondermarge en bestaande sessiewaarschuwing.
- **P2, bediening/hiërarchie:** één primaire controleactie per context; meldingstekst en technische controledetails achter native disclosures. De sluitknop is minimaal 44×44 px.
- **P2, toegankelijkheid:** semantische h2 voor Raad, zichtbare focus, gerichte statusregio’s en een busy-toestand bij het ophalen van de documentcontrolestatus. Geen live-regio over het hele paneel.
- **P2, betekenis van uitslagen:** de samenvatting telt bruikbaar, afwijking, niet vastgesteld en niet gecontroleerd afzonderlijk. Verlopen aanmelding wordt als niet gecontroleerd getoond; niet geopende vervolgpagina’s worden expliciet genoemd. Onvolledigheid krijgt een concrete vervolgstap.
- **P3, leesbaarheid:** bestaand woord-/regelomloopgedrag aangevuld met `text-wrap: pretty`; geen nieuwe lettertypen, kleuren of decoratieve animatie.

Geen P0 gevonden. Contrast- en toegankelijkheidsconclusies gelden voor de gemeten Raad-onderdelen; er is geen volledige WCAG-certificering of handmatige schermlezerproef geclaimd. Eindscore: 17/20 (3/3/4/3/4). De sluitknop meet 44×44 px; het paneel blijft in 844×390 bij 200% tekstgrootte binnen de viewport (y=32) en maakt in een kort scherm ruimte door de uil tijdens openen te verbergen. Toetsenbord, gesynthetiseerde Chromium-touch en behoud van foutstatus bij verminderde beweging zijn geverifieerd. De finale detector geeft vijf meldingen: drie over bewust behouden merkpaars, één over het bestaande niet-modale paneel en één bestaande h1 buiten Raad. De advisory over de losse laatste regel is verdwenen. Er zijn geen brede detector-ignores ingesteld.

## Verificatie

Codeonderzoek is onderscheiden van lokaal uitgevoerd gedrag; er is geen live productieproef gedaan.

- `scripts/test_postgres.sh` controleerde de bestaande lokale PostgreSQL-connectie vóór de consoletests. Beschikbaar: PostgreSQL 17.11; CI gebruikt 16. Dit is een expliciete omgevingsgrens, geen claim van een uitgevoerde PG16-proef.
- Eerste bestaande Chromium-paginaproef: 1 geslaagd; uitgebreidere proef (geladen gegevens, geldige lege lijst, gedeeltelijke lijst, vastlopend gegevensverzoek, roltoegang, verlopen sessie, sluiten/heropenen, domeinhash, mobiel/toetsenbord): 1 geslaagd in de gecombineerde run.
- Echte browserroute via aanvraag -> PostgreSQL-taak -> aparte browser -> beschermd bewijs: afzonderlijk herhaald met twee documentvormen en een bewust gewijzigde gerenderde tekst; ook de aanvullende proef met CSS-verborgen tekst is geslaagd. De foutinjectie vond de afwijking terwijl identiteit/aantallen gelijk bleven en behield een `/review`-requestreferentie.
- Revisie-/incidentset: 17 geslaagd, inclusief een echte objectrevisiewijziging tijdens de workercontrole. Eerdere passes worden `not_established` en er wordt geen screenshotbewijs geactiveerd.
- Karakterisatie: 38 geslaagd bij vastleggen; de 32 gewijzigde HTML-goldens zijn geïnspecteerd. Verschillen: CSS/JS-inhoudshashes, het readinessasset, de semantische Raad-heading en het verwijderen van de algemene live-regio. Geen domeinuitkomsten gewijzigd.
- Screenshots van desktopresultaat, mobiel paneel en toetsenbordfocus zijn visueel geïnspecteerd. Aanraakdoel, focus en viewportgrenzen zijn tevens met Chromium geverifieerd. Er is geen handmatige schermlezerproef uitgevoerd.

De volledige collectie wordt met de vier bestaande CI-partities uitgevoerd. De lokale omgeving gebruikt PostgreSQL 17; de canonieke CI vereist PostgreSQL 16. De uiteindelijke volledige-suite-uitslag wordt op de review-PR vastgelegd. Repository-preflight, releasecontrole op de daadwerkelijke diff, compileall, architectuurgrenzen, zes architectuur-invarianten en de change-contractvalidator zijn uitgevoerd en geslaagd. Testopslag en foutinjectie zijn uitsluitend geïsoleerd; geen productie- of Azure-mutatie.

Extra controlekosten zijn nog niet ten opzichte van een baseline gemeten. De uitbreiding hergebruikt de bestaande gegevensaanvragen en passage-export; readinesspolling leest alleen DOM, met maximaal 20 seconden per hoofdpagina. De extra scriptasset is cachebaar en wordt op inhoud geversioneerd. Dit is codebewijs van begrenzing, geen gemeten prestatie- of kostenclaim.

De GitHub CLI meldde ongeldige authenticatie; de gekoppelde GitHub-app heeft wel repositorytoegang en wordt gebruikt voor de reviewoverdracht. Geen issue, merge of deployment uitgevoerd. De review-PR benoemt de gebruikte Impeccable-bron en de PostgreSQL-versiegrens expliciet.

| Gevraagde acceptatie | Gericht bewijs |
| --- | --- |
| Gezonde pagina met gegevens | `tests/browser_deploy_check.cjs`: alle acht hoofdpagina’s voor de bevoegde gebruiker |
| Geldige lege toestand | Dezelfde browserproef: volledige lege documentenrespons slaagt |
| Paginaschil met hangend gegevensverzoek | Dezelfde browserproef: `pending` faalt na de begrensde wachttijd, verzoek blijft als pending beschreven |
| Onvolledig overzicht | Dezelfde browserproef: `metadata_partial` wordt niet als bruikbaar/leeg gemeld |
| Gewijzigde tekst of weggelaten voorwaarde | `tests/browser_view_check.cjs`: echte gerenderde tekstmutatie; `test_rendered_text_comparison_preserves_conditions_order_and_unicode`: voorwaarde/volgorde/Unicode |
| Ontbrekende toegang | Paginaproef met reviewer zonder publicatierol en bestaande HTTP-autorisatieproeven |
| Revisiewijziging tijdens onderzoek | `test_worker_activation_rechecks_authority_and_preserves_document[revision_change]`: echte PostgreSQL-objectwijziging tijdens de gesimuleerde browsertransportstap; echte context-/opslagfence, geen echte gelijktijdige gebruikersbrowser |
| Sluiten/heropenen zonder dubbele controle | Bestaande en uitgebreide echte Chromium-paginaproef |
| Geen domeinmutaties door controles | Domeinhash over alle authoritytabellen vóór/na beide browserroutes; operationele view-check-tabellen zijn daarvoor uitgezonderd |
| Desktop, mobiel en toetsenbord | Chromium-viewport-/focusasserties en visueel geïnspecteerde screenshots |


Omgevingsherstel tijdens verificatie: de volledige suite kon eerst niet verzamelen zonder de reeds in `requirements-dev.lock` vastgelegde PyYAML 6.0.3. Na installatie meldde een bestaande Tier-D SQL-proef dat `psql` niet in PATH stond; de reeds geïnstalleerde PostgreSQL-client is aan het testpad toegevoegd. De 23 eerder gefaalde controles slaagden daarna. Hiervoor is geen productcode aangepast en geen check overgeslagen.

De bredere regressies ontdekten dat een nieuwe request-ID in de Raad-markup bytegelijke leesoverzichten per verzoek verschillend maakte. De bestaande A02-test is rood gereproduceerd op uitsluitend die attributen. De injectie is verwijderd; bestaande responseheaders, foutbanners en het Inzicht-gegevensverzoek blijven de correlatiebronnen. Niet waarneembare navigatiereferenties blijven onbekend. De documentdiagnose bewaart daarnaast maximaal vier onvoltooide assetwaarnemingen als `/brand/*`, zonder bestandsnaam of query; zo wordt een nog ladend schermasset niet als databaseoorzaak uitgelegd.

De externe probe ondersteunt ook Mijn werk, Instellingen en Inzicht. De bestaande incidentprojectie accepteert daarvoor browserwaarnemingen; de scope van de producent van gedetailleerde fase-events is niet verbreed. Ontbrekende backend-events blijven expliciet onbekend. Dit schrijft geen extra request- of verwerkingstelemetrie.

## Definitieve verificatie en grenzen

De uiteindelijke gerichte set slaagt met **93 tests**, inclusief Chromium, PostgreSQL, HTML-goldens, echte tekst-/CSS-foutinjectie, toegang, revisie, diagnose, kopiëren en onveranderde domeintoestand. De laatste kopijwijziging voor aanmelden verandert alleen de uitleg; de content-hashverwijzing is afzonderlijk gecontroleerd.

De brede collectie is volledig uitgevoerd via de vier bestaande CI-partities: **5.898 unieke test-ID’s**, exact één keer geselecteerd en afgerond, 23 optionele skips en 3 xfails, **nul PostgreSQL-skips**. De eerste uitvoering had 17 failures. De geïntroduceerde HTML-request-ID-regressie is rood/groen gerepareerd. Na herhalingen en installatie van reeds vastgelegde testafhankelijkheden blijven twee transportproeven over. Beide falen ook op de ongewijzigde startcommit `f133b860` in een aparte worktree. Ze gebruiken connectlimieten van 0,2/0,3 seconde; één verse Python-import is hier op 0,556 seconde gemeten. De oorzaak wordt niet als een provider- of databaseprobleem gepresenteerd en de limieten zijn niet versoepeld. De volledige suite wordt daarom **niet als groen op de eind-head geclaimd**.

Lokaal: Python 3.13.5, PostgreSQL 17.11 en Chromium. CI met PostgreSQL 16 is nog nodig; de canonieke shard-merger vereist die versie en wordt niet omzeild. De volledige ruwe runs begonnen op een werkboom gebaseerd op `f133b860`; relevante correcties en de uiteindelijke presentatie zijn gericht opnieuw uitgevoerd. Zie `evidence/raad-usability-fidelity/verification.json` voor de collectiedigest, tellingen, gedekte velden en exacte bestandsdigests.

Repository-preflight, release-preflight op de daadwerkelijke wijziging, compilatie, architectuurgrenzen, architectuur-invarianten en change-contractvalidatie zijn bij de oplevering nogmaals geslaagd. Er is geen handmatige schermlezer- of fysieke-apparaatproef, live productiecontrole, Azure-mutatie, merge of deployment uitgevoerd. Extra controlekosten ten opzichte van een baseline zijn niet gemeten.

Na publicatie van de concept-PR is de branch zonder conflicten aangesloten op actuele hoofdbranch `78dff417`. De gecombineerde gerichte scope is opnieuw uitgevoerd: **48 + 51 = 99 tests geslaagd**, inclusief de zes architectuurinvarianten, echte Raad- en documentbrowsers, PostgreSQL en alle karakterisatiegoldens. De runtime-/testdigests zijn bijgewerkt voor die basis. Repository-, release-, compilatie-, architectuurgrens- en contractchecks zijn opnieuw geslaagd. De brede volledige suite is na deze hoofdbranchupdate niet herhaald.

## CI-herstel PR #849

CI-run `40219765267` weigerde de PR-beschrijving omdat `Promise`, `Proof` en `Touches lifecycle invariants` ontbraken. De lokale eerdere validatie had het contractbestand gecontroleerd, niet het GitHub-event met de PR-beschrijving. Daardoor werden de afhankelijke browser- en suitejobs overgeslagen en ontbraken hun artefacten. De drie velden zijn toegevoegd aan de PR-beschrijving. De ongewijzigde validator is met de daadwerkelijke PR-body via `GITHUB_EVENT_NAME=pull_request` en `GITHUB_EVENT_PATH` rood gereproduceerd (dezelfde drie fouten) en met de gecorrigeerde body groen uitgevoerd. Geen productcode, testverwachting of CI-gate is aangepast. Deze bewijscommit start een nieuwe synchronize-run met de gecorrigeerde PR-body; een herstart van het oude event zou de oude body kunnen behouden.

CI-run `40221418620` slaagde voor contract, architectuur, karakterisatie, beide preflights, browser en zes van acht suitepartities. Beide partitie-1-jobs faalden uitsluitend op `test_via_negativa_is_not_the_heading_of_researcher_rooms`: de test noemde de eerste h1/h2 in de volledige HTML ten onrechte de h1, waardoor de verborgen Raad-h2 als paginatitel werd gelezen. De echte paginatitel is ongewijzigd. De bestaande test is rood gereproduceerd op de echte PostgreSQL/HTTP-route en controleert nu alle h1-koppen als lijst, exact één met de vereiste titel. De bestaande controle op verboden tekst in alle h1/h2-koppen blijft behouden. De route en Raad-contractset slagen groen: 13 tests. Geen productiecode, schermkop, verborgen dialoogsemantiek of CI-gate is aangepast.
