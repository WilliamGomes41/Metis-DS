# Meerdere bronbereiken per annotatie-entry (#1014 / MET-58)

Status: ontwerpbesluit, 8 november 2026. Geen productimplementatie, merge of deployment. De volledige route staat in [de annotatiearchitectuur](../plans/human-annotation-architecture.md).

## Besluiten (ontwerpkeuze William, 8 november 2026)

Eén markeeractie in de eerste editor blijft binnen één stabiel blok van de gepinde extractie. De researcher kan daarna een tweede bereik uit een andere alinea aan **dezelfde** annotatie-entry koppelen. De alinea is geen grens voor een kennisobject: één inhoudelijke claim, met haar context, onderbouwing en herkomst, blijft de maatstaf van #986. Een expliciet GO voor de productcutover is hiermee niet gegeven.

## Domeincontract voor de bouwslice

- Een SourceRange bevat de exacte bron-/extractie-identiteit, blok-ID en begin/einde in de gevalideerde gepinde bloktekst. De opslag bewaart afzonderlijke bereiken en hun volgorde, rol en annotation-ID; geen canonieke vrije tekst uit de browser.
- Eén annotation-ID kan geordende kernbereiken uit meerdere blokken hebben. Doelgroep, voorwaarde, uitzondering, toelichting en onderbouwing zijn rolgebonden bronverwijzingen of bereikrelaties. Dezelfde onderbouwende passage mag aan meerdere claims zijn gekoppeld zonder kopiëren of zelf een KO te worden.
- Twee zelfstandig beoordeelbare of herzienbare claims zijn twee annotaties. Meerdere bereiken zijn geen vrijbrief om losse claims stil tot één zin samen te schrijven. De reviewer beoordeelt de betekenis van de samengestelde claim en de draagkracht van haar bewijs.
- Een drag over blokken wordt niet stil als één bereik opgeslagen. Bij een door extractie gesplitste zin kunnen delen apart worden aangewezen. Koppen, lijsten en tabellen krijgen hun structurele context; een verkeerde extractie vereist een opvolgversie en herankering, geen offsetgok.
- Conceptautosave, selectie gereed, overzicht, seal, materialisatie, ingestbeoordeling en publicatie behouden hun bestaande onderscheiden grenzen. Hetzelfde bereik bijwerken of hergebruiken verhoogt de juiste entry-/setgeneratie en maakt een stale overzicht ongeldig. Server-CAS en autorisatie zijn leidend.
- Voor correctie na bouw wordt de oorspronkelijke annotation-ID opnieuw geopend. Een nieuwe entry- en objectversie bindt de gewijzigde bereiken; alleen geraakte oordelen vervallen volgens bestaande hash-/afhankelijkheidsregels. Gepubliceerde versies blijven immutable.

## Alternatieven

| Vorm | Gevolg | Oordeel |
|---|---|---|
| Eén KO per alinea | Voorwaarde of uitzonderingspassage elders wordt afgesneden of tot onterechte zelfstandige KO gemaakt | Afgewezen als domeinregel |
| Eén vrije selectie over alle alinea's | Extractiegrenzen, koppen en provenance kunnen ongemerkt verdwijnen; precieze opslag wordt lastiger | Niet nodig voor de eerste editor |
| Meerdere exacte bereiken in één entry | Extra aanwijshandeling, maar expliciete rol, volgorde en bronbinding | Gekozen ontwerp |

## Implementatie- en bewijsgrens

Class A / rewrite risk high voor de toekomstige routewijziging; dit document wijzigt geen runtime. HA-2a bewaart bereik en rol duurzaam, HA-2b verzegelt de geordende set en bouwt via de enige materialiser. Bestaande ingestkeuze en reviewrechten veranderen niet. Bewijs vóór oplevering: Unicode/offsets, herhaalde tekst, twee kernalinea's, voorwaarde elders, gedeelde bewijsbron, gesplitste extractie, stale autosave/overzicht, herstart en gerichte reviewinvalidatie in native PostgreSQL en browser. Toegankelijke selectie zonder precieze muisdrag is onderdeel van de UI-acceptatie.

Open vóór implementatie: exacte human-proof-schema-/activatievariant, concrete bron/opdracht en onafhankelijk inhoudelijk referentiegeval, productie-inventaris en change contract voor de gehele cutover. Geen van deze proeven is door deze documentwijziging uitgevoerd.
