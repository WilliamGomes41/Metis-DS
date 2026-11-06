# #1000 — KO-2 reviewkaart en bon

Change class: B
Promise: De reviewer beoordeelt met leesbare documentcontext en krijgt na opslag een bon die de eigen opgeslagen handeling en inhoudelijke samenhang toont.
Proof: Gerichte PostgreSQL-/HTTP-regressies, bestaande karakterisatie en browserproeven bij het exacte PR-hoofd.
Touches lifecycle invariants: no
Rewrite risk: none

## Ground

`review_workboard_v1.review_get` selecteert de bestaande geautoriseerde passage; `read_review_passage` levert één samenhangend venster met koppen, afhankelijkheden, bindingen en immutable bron. `_render_review_card` post de bestaande verplichte geschiktheid-, kop-, type-, sterkte- en relatie-invoer. `review_post` roept de bestaande reviewopdracht aan en navigeert daarna naar de volgende passage. KO-2 wijzigt deze validators en opslagautoriteiten niet.

De bronfragmenten in een passagevenster zijn begrensd. Alleen de expliciete volledige-bronleesroute mag als volledige sectie worden gepresenteerd. De bron-koppenstructuur moet uit de bronrepresentatie komen; actuele KO-koppen zijn geen vervanging voor een oorspronkelijke inhoudsopgave.

`workflow_review_store.read_review_command_events(..., interaction_id=..., include_pending=False)` leest bestaand duurzaam interactiebewijs. De exacte objectinhoud is identificeerbaar met de opgeslagen versie/hash en `review_command_histories`. Een event met alleen een precommand-contextmanifest bewijst geen postcommand antwoorden. Later beoordelen kan geen duurzaam event opleveren; dan verschijnt geen succesvolle-opslagbon.

## Sketch en keuze

Twee structurele alternatieven zijn op dezelfde code onderzocht met de beschikbare agents, allen op hetzelfde geërfde model; dit is geen consensus van verschillende modellen.

| Vorm | Eigendom en kosten | Oordeel |
| --- | --- | --- |
| Bestaande redirect/GET met exacte bestaande interactiereferentie | Bestaande commands blijven eigenaar; GET lost uitsluitend duurzaam bewijs op, met expliciete uitkomst als historische samenhang niet oplosbaar is. Heropenen en herstart gebruiken dezelfde bron. | Gekozen; kleinste aansluiting op bestaande navigatie. |
| Een apart ontvangstbewijs in sessie of nieuwe tabel | Extra opslag-/autoriteitsgrens; sessies verliezen bewijs bij herstart of kunnen een latere toestand verwisselen; tabel vraagt eigen levenscyclus. | Verworpen; niet nodig en strijdig met het goedgekeurde ontwerp. |

Publieke presentatievormen zijn een read-only `SavedReviewReceipt` met exact event, object en bewezen context, en een broncontextweergave van één immutable snapshot. Caller gebruik: POST voltooit bestaande command, redirect draagt de bestaande interaction-id, GET controleert huidige deelname en eigenaar van het event vóór renderen. Deze navigatiereferentie verleent geen bevoegdheid.

## Implementatie en bewijslast

De drie hoofdvragen groeperen de bestaande vereiste invoer. Geen extra goedkeuring, universele tweede reviewer of nieuwe kerneltransitie. De bon vermeldt alleen bewezen eigen keuzes; ontbrekende antwoorden worden niet tot Ja aangevuld. Een latere wijziging wordt niet stil als de opgeslagen uitkomst getoond.

Blokkerende eerste stap is het vaststellen van bron-/eventeigenaren. Eén code-eigenaar verzorgt de gekoppelde renderer, POST en GET, zodat gedeelde bestanden geen gelijktijdige schrijvers hebben. Onafhankelijke grounding en verificatie lezen dezelfde patch. De kleinste veilige decompositie is bron-/kaartprojectie, bonprojectie en navigatie, gevolgd door HTTP-/browserbewijs. Geen schema- of migratiewerk hoort hierbij.

## Verificatiestatus

Uitvoering en exacte resultaten worden bij de PR vastgelegd. Deze ontwerptekst is geen verklaring dat runtime, browserproef of productieacceptatie al geslaagd is.

## Uitwerking van de bewijsgrenzen

De opgeslagen bon gebruikt uitsluitend canonieke inhoud uit de exacte historische tuple. Mutable admission-, register- en governanceprojecties worden via `canonical_object_payload` weggelaten, zodat een latere governancewijziging bij hetzelfde hash niet op de oude bon verschijnt. Het event bewijst de eigen handeling; drie historische Ja-antwoorden worden niet gereconstrueerd uit een huidige status. Bij een eerste akkoord is de tekst daarom dat een eventueel vereiste tweede beoordeling hierdoor niet is afgerond. De actuele vervolgbeoordelingen blijven in het bestaande overzicht staan.

De aanvullende display-reader in `ReviewSourceRecords` vraagt de originele heading-fragmenten en alleen directe bronburen op uit dezelfde sealed root. Hij geeft expliciete display-fragmentreferenties door aan de bestaande hash-/membershipvalidatie. Dit verandert geen bestaande reviewsourceaanroep, opnamecriterium of closure. Ontbrekende of corrupte broncontext krijgt een expliciete melding en de oorspronkelijke-bronroute, geen gefabriceerde structuur.

De werkbordkaarten betreffen documenten. Hun documentwerkstatus wordt niet vervangen door een KO-status. De kennisvoorstelrijen en beide detailkaarten gebruiken de KO-1-afleiding; de bestaande finale-statushelper gebruikt `FINAL_VALIDATION_STATUSES`.

Gerichte lokale controles: zes nieuwe PostgreSQL-/HTTP-proeven voor opgeslagen resultaat/herstart, onbekende of verwisselde interactie, stale save, read-only sectie-uitbreiding, originele volledige koppen met begrensde bronburen en uitsluiting van later admissionbewijs. Samen met bestaande passage/source/commandproeven zijn 55 tests geslaagd op lokaal PostgreSQL 17. CI gebruikt PostgreSQL 16. De 35 karakterisatieproeven zijn bijgewerkt voor de goedgekeurde presentatie; ongewijzigde pagina's verschillen alleen in de stylesheet-cacheversie. Routekarakterisatie krijgt de extra read-only sectieroute. De opzettelijke reviewmutatie blijft een afzonderlijke check.

De bon onderscheidt de historische eigen handeling van de **actuele reviewtoestand en versie**. Die actuele status wordt met `derive_ko_state` afgeleid uit de reeds gelezen huidige revisie en één bestaande, op dit object begrensde bindingread in hetzelfde leesvenster. Dit is geen historische status of publicatiebewijs. Daardoor blijven ook gewijzigde managed reviewverplichtingen zichtbaar zonder ze terug te projecteren op de eerdere handeling.
