# Meerdere bronbereiken per annotatie-entry (#1014 / MET-58)

Status: ontwerpbesluit, 8 november 2026. Geen productimplementatie, merge of deployment. De volledige route staat in [de annotatiearchitectuur](../plans/human-annotation-architecture.md).

## Besluiten (ontwerpkeuze William, 8 november 2026)

Eén markeeractie in de eerste editor blijft binnen één stabiel blok van de gepinde extractie. De researcher kan daarna een tweede bereik uit een andere alinea aan **dezelfde** annotatie-entry koppelen. De alinea is geen grens voor een kennisobject: één inhoudelijke claim, met haar context, onderbouwing en herkomst, blijft de maatstaf van #986. Een expliciet GO voor de productcutover is hiermee niet gegeven.

## Domeincontract voor de bouwslice

- Een logisch SourceAnchor bevat de exacte SourceSnapshot-/extractie-identiteit met hash, stabiele blok-ID, begin inclusief/einde exclusief in genormaliseerde Unicode-codepoints en de normalisatieversie. Een begrensde exacte quote plus prefix/suffix kan als controlegetuige worden gebruikt waar de rechten dat toelaten; de gepinde bron blijft autoriteit. De server reconstrueert tekst uit die bron, nooit uit vrije browsertekst. De precieze tabelvorm blijft een HA-2-besluit.
- Eén annotation-ID kan geordende kernankers uit meerdere blokken hebben. Doelgroep, voorwaarde, uitzondering, toelichting en onderbouwing zijn aparte RoleLinks tussen deze entry en een bronanker; rol, volgorde en betekenisverplichting horen bij de koppeling. Essentiële context moet in kandidaat-, review- en hergebruikweergave meekomen. Dezelfde onderbouwende passage mag aan meerdere claims zijn gekoppeld zonder opnieuw aanwijzen of zelf een KO te worden. #986 blijft eigenaar van de inhoudelijke en fysieke KO-grens.
- Twee zelfstandig beoordeelbare of herzienbare claims zijn twee annotaties. Meerdere bereiken zijn geen vrijbrief om losse claims stil tot één zin samen te schrijven. De reviewer beoordeelt de betekenis van de samengestelde claim en de draagkracht van haar bewijs.
- Een drag over blokken wordt niet stil als één bereik opgeslagen. Bij een door extractie gesplitste zin kunnen delen apart worden aangewezen. Koppen, lijsten en tabellen krijgen hun structurele context. JavaScript UTF-16-offsets worden niet als Unicode-codepoints doorgegeven zonder expliciete conversie; test emoji, samengestelde tekens en logische tekstvolgorde. Twee identieke passages op verschillende geldige posities mogen elk worden aangewezen. Bij een ongeldige positie wordt niet stil een van de quote-matches gekozen; opslag geeft een gerichte mismatch- of herankeringsbevinding. Een verkeerde of gewijzigde extractie vereist een expliciete opvolgversie en door een mens bevestigde herankering, geen offsetgok of fuzzy tekstmatch.
- Conceptautosave, selectie gereed, overzicht, seal, materialisatie, ingestbeoordeling en publicatie behouden hun bestaande onderscheiden grenzen. Hetzelfde bereik bijwerken of hergebruiken verhoogt de juiste entry-/setgeneratie en maakt een stale overzicht ongeldig. Server-CAS en autorisatie zijn leidend.
- Voor correctie na bouw wordt de oorspronkelijke annotation-ID opnieuw geopend. Een nieuwe entry- en objectversie bindt de gewijzigde bereiken; alleen geraakte oordelen vervallen volgens bestaande hash-/afhankelijkheidsregels. Gepubliceerde versies blijven immutable.

## W3C-grens en gebruik

Het [Web Annotation Data Model](https://www.w3.org/TR/annotation-model/) levert begrippen voor `SpecificResource`, `Selector`, `State`, `motivation` en herkomst. Die inspireren een afgeleide export, niet de duurzame Metis-autoriteit. W3C `TextPositionSelector` alleen is kwetsbaar bij bronwijzigingen; `TextQuoteSelector` met prefix/suffix kan een controlegetuige zijn, maar is bij herhaalde tekst op zichzelf niet uniek en kan gebruiksrechten raken. W3C `rights`-metadata is geen toestemming om gelicentieerde brontekst te exporteren.

Een gewone W3C-annotatie met meerdere targets relateert haar body aan elk target **afzonderlijk**. De niet-normatieve W3C-bijlage bespreekt een `Composite`/`List` voor passages die samen nodig zijn. Metis bewaart de geordende kerngroep en de rolgebonden relaties daarom in een eigen intern contract; een eventuele W3C-projectie gebruikt gedocumenteerde uitbreidingen of afzonderlijke annotaties en mag de samenhang niet vervlakken. Geen claim van W3C-conformiteit zonder aparte mapping- en conformanceproef. De W3C-`RangeSelector` laat selectie over interne grenzen toe; één markeeractie per blok is alleen de eerste UX-keuze en wordt met researchers getoetst.

De editor toont direct de geselecteerde tekst met bronkop/versie, laat ‘nog een kernbereik’ of een rol kiezen en biedt ‘open in bron’, verwijderen en herkoppelen. Toets toetsenbord en touch naast muisselectie. Bij ‘selectie gereed’ ziet de researcher de complete claim met alle essentiële context. Opgeslagen ankers, rolrelaties en versies zijn een voorwaarde voor bouwen; annotatie blijft geen reviewbesluit.

## Alternatieven

| Vorm | Gevolg | Oordeel |
|---|---|---|
| Eén KO per alinea | Voorwaarde of uitzonderingspassage elders wordt afgesneden of tot onterechte zelfstandige KO gemaakt | Afgewezen als domeinregel |
| Eén vrije selectie over alle alinea's | Extractiegrenzen, koppen en provenance kunnen ongemerkt verdwijnen; precieze opslag wordt lastiger | Niet nodig voor de eerste editor |
| Meerdere exacte bereiken in één entry | Extra aanwijshandeling, maar expliciete rol, volgorde en bronbinding | Gekozen ontwerp |

## Implementatie- en bewijsgrens

Class A / rewrite risk high voor de toekomstige routewijziging; dit document wijzigt geen runtime. HA-2a bewaart bereik en rol duurzaam, HA-2b verzegelt de geordende set en bouwt via de enige materialiser. Bestaande ingestkeuze en reviewrechten veranderen niet. Bewijs vóór oplevering: Unicode-codepoints/UTF-16, normalisatie en graphemegrens, dubbele quote met verschillende vindplaats, twee kernalinea's, voorwaarde elders, gedeelde bewijsbron met verschillende rol, gesplitste extractie, bronopvolger/herankering, stale autosave/overzicht, herstart en gerichte reviewinvalidatie in native PostgreSQL en browser. Test dat een eventuele export gezamenlijke kern en essentiële context niet als onafhankelijk toepasbare targets presenteert en geen ongeautoriseerde bronquote verspreidt. Toegankelijke selectie zonder precieze muisdrag is onderdeel van de UI-acceptatie.

Open vóór implementatie: exacte human-proof-schema-/activatievariant, concrete normalisatie- en ankerrepresentatie, rechten voor quotegetuigen/export, bron/opdracht en onafhankelijk inhoudelijk referentiegeval, productie-inventaris en change contract voor de gehele cutover. Geen van deze proeven is door deze documentwijziging uitgevoerd.
