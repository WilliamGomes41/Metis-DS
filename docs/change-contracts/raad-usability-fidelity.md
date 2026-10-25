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

Mislukking/onvolledigheid bewaart via het bestaande onderzoeksresultaat stap, verwachting, waarneming, verstreken tijd en maximaal 12 verzoekwaarnemingen met vaste route, toestand, HTTP-status en geldige bestaande request-ID. Geen URL-query, cookie, token, autorisatieheader, DOM of exceptionproza. Bij subprocessuitval resteert expliciete workerdiagnose; niet-waargenomen requests worden niet ingevuld. Een gewijzigde revisie maakt eerdere passes niet vastgesteld. Geen trace/HAR: de bestaande inrichting levert geen veilige redactieroute voor sessiehoudende traces; compacte diagnose en bestaand beschermd screenshotbewijs blijven de grens.

## Impeccable en bediening

Impeccable is niet aangetroffen in de beschikbare sessiecatalogus en toegankelijke lokale pakket-/skilllocaties. Er is dus **geen Impeccable-audit uitgevoerd** en de visuele wijzigingen mogen zo niet worden gepresenteerd. Zelfstandig uitvoerbare functionele verbeteringen zijn wel uitgevoerd. Bij eigen inspectie van de werkende Chromium-interface bleek het paneel veel informatie en meerdere primaire acties te combineren. Daarom staan technische controledetails en meldingstekst achter native disclosures, blijft één controleactie primair per context, krijgt de sluitknop een aanraakdoel van 44 px en krijgen interactieve elementen zichtbare focus. Het gehele paneel is geen live-regio meer; voortgang blijft een gerichte statusregio. Bestaande uil, kleurvariabelen en huisstijl blijven behouden. De screenshots moeten afzonderlijk worden geïnspecteerd; dit vervangt geen ontbrekende pakketaudit.

## Verificatie

Codeonderzoek is onderscheiden van lokaal uitgevoerd gedrag; er is geen live productieproef gedaan.

- `scripts/test_postgres.sh` controleerde de bestaande lokale PostgreSQL-connectie vóór de consoletests. Beschikbaar: PostgreSQL 17.11; CI gebruikt 16. Dit is een expliciete omgevingsgrens, geen claim van een uitgevoerde PG16-proef.
- Eerste bestaande Chromium-paginaproef: 1 geslaagd; uitgebreidere proef (geladen gegevens, geldige lege lijst, gedeeltelijke lijst, vastlopend gegevensverzoek, roltoegang, verlopen sessie, sluiten/heropenen, domeinhash, mobiel/toetsenbord): 1 geslaagd in de gecombineerde run.
- Echte browserroute via aanvraag -> PostgreSQL-taak -> aparte browser -> beschermd bewijs: afzonderlijk herhaald met twee documentvormen en een bewust gewijzigde gerenderde tekst; ook de aanvullende proef met CSS-verborgen tekst is geslaagd. De foutinjectie vond de afwijking terwijl identiteit/aantallen gelijk bleven en behield een `/review`-requestreferentie.
- Revisie-/incidentset: 17 geslaagd, inclusief een echte objectrevisiewijziging tijdens de workercontrole. Eerdere passes worden `not_established` en er wordt geen screenshotbewijs geactiveerd.
- Karakterisatie: 38 geslaagd bij vastleggen; de 32 gewijzigde HTML-goldens zijn geïnspecteerd. Verschillen: CSS/JS-inhoudshashes, het readinessasset, lege requestreferentie in deze offline fixtures en het verwijderen van de algemene live-regio. Geen domeinuitkomsten gewijzigd.
- Screenshots van desktopresultaat, mobiel paneel en toetsenbordfocus zijn visueel geïnspecteerd. Aanraakdoel, focus en viewportgrenzen zijn tevens met Chromium geverifieerd. Er is geen handmatige schermlezerproef uitgevoerd.

De volledige collectie wordt met de vier bestaande CI-partities uitgevoerd. De lokale omgeving gebruikt PostgreSQL 17; de canonieke CI vereist PostgreSQL 16. De uiteindelijke volledige-suite-uitslag wordt op de review-PR vastgelegd. Repository-preflight, releasecontrole op de daadwerkelijke diff, compileall, architectuurgrenzen, zes architectuur-invarianten en de change-contractvalidator zijn uitgevoerd en geslaagd. Testopslag en foutinjectie zijn uitsluitend geïsoleerd; geen productie- of Azure-mutatie.

Extra controlekosten zijn nog niet ten opzichte van een baseline gemeten. De uitbreiding hergebruikt de bestaande gegevensaanvragen en passage-export; readinesspolling leest alleen DOM, met maximaal 20 seconden per hoofdpagina. De extra scriptasset is cachebaar en wordt op inhoud geversioneerd. Dit is codebewijs van begrenzing, geen gemeten prestatie- of kostenclaim.

De GitHub CLI meldde ongeldige authenticatie; de gekoppelde GitHub-app heeft wel repositorytoegang en wordt gebruikt voor de reviewoverdracht. Geen issue, merge of deployment uitgevoerd. De concept-PR benoemt ontbrekend Impeccable en de PostgreSQL-versiegrens expliciet.

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
