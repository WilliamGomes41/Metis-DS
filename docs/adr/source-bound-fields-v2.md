# Brongebonden veldbewijs v2 — additieve eerste slice (#455)

Change class: B. Rewrite risk: high. Status: implemented, opt-in; no production cutover.

## Besluit

Behoud één passagevormingsmechanisme. Voeg aan de bestaande semantische uitvoer uitsluitend een gesloten `field_evidence`-object toe: een bronbereik binnen de geselecteerde kandidaat of null met `not_stated`, `uncertain` of `not_applicable`. Metis reconstrueert de veldtekst zelf. Hetzelfde typecontract wordt gebruikt voor velddefinities en toelating.

Gebruik `METIS_PASSAGE_FORMATION_MODE=semantic-source-bound-v2` voor de nieuwe voorbereiding. De bestaande modes, default en beslisboomroute blijven bestaan. De broncontractvalidator en generieke transformatie controleren de evidence; v2-toelating gebruikt die waarden en slaat de oude regex-invulling over. Een aanbeveling met exact veldbewijs vereist in v2 niet daarnaast een regex-advieswoord. Dit is een bewust versiegebonden wijziging in voorsteltoelating, geen menselijke bevestiging of publicatiebesluit.

## Eigenaarschap en grenzen

Objectmetadata blijft onderdeel van de bestaande WorkingRevision-opslag. Geen nieuwe store, lifecycle, serving authority of achtergrondjob. Bestaande snapshot/autorisatie/commit/concurrency-paden blijven leidend. De duurzame writes lopen via bestaande objectset-commits. Invalid proposal faalt vóór toepassing. Een binding aan kandidaattekst en voorgesteld type voorkomt ongemerkt hergebruik na correctie. Replay bindt v2-prompt, schema en contractversie; v1 kan niet als v2 worden afgespeeld.

ASGI en CLI gebruiken de bestaande routebinding. Rechtstreekse oude klassetransformatie blijft legacy en wordt niet als v2 gepresenteerd. Menselijke repair, kopvorming, beslisboom en vergelijkingsbaselines blijven ondersteund. Lokale en PostgreSQL-opslag ontvangen dezelfde additieve metadata; database/adapters zijn niet gewijzigd. Een echte PostgreSQL/production end-to-end proef is hiermee niet geclaimd.

## Eerste slice versus volledig plan

Deze PR implementeert het brongebonden veldcontract, opt-in verwerking, versiegebonden toelating, leesbare veldweergave en export. Het volledige plan staat in METIS_SOURCE_BOUND_IMPLEMENTATION_PLAN.md.

Nog open: veldbewijs buiten de kernpassage/contextrelaties, expliciete bereikdekking, opgeslagen ruwe modelaanroepen, structurele producent met volledig v2-contract, koppeling klasseconversie naar één dispatcher, losse broncatalogus, omvangoptimalisatie van de export, menselijke referentiemeting en decommission. De oude routes zijn frozen, niet uitgeschakeld.

De huidige v2-veldselectie is bewust beperkt tot één exact bereik binnen één geselecteerd span. Vereist bewijs buiten die selectie blijft ontbrekend; er wordt niets verzonnen. Subject/predicate en typegebonden velden blijven de bestaande domeineisen. Die eisen mogen niet als bijwerking van deze wijziging worden versoepeld.

## Herstel en rollback

Schakel opt-in uit voor nieuwe verwerking met de huidige, v2-lezende release. Bewaar v2-objecten en reviewevidence. Deploy geen oude binary op v2-resultaten zonder compatibiliteitsbewijs. Geen historische backfill, dual-write, automatische herclassificatie of destructieve migratie.

## Validatie

Gerichte tests dekken pipeline, persist/restart, replay, ontbrekende evidence, vrije tekst, onbekende/out-of-range spans, extra velden en stale correctie. Bestaande v1-tests blijven geldig. Dit bewijst technische contractaansluiting; brongetrouwe velden zijn nog geen bewijs van correcte betekenis. Menselijke inhoudelijke vergelijking uit G4 blijft nodig vóór cutover.

## Afzonderlijke adversariële controle

Na de implementatie is het contract langs de volgende omwegen gecontroleerd:

| Aanval of afwijking | Bevinding en bewijs |
|---|---|
| Rechtstreeks aanroepen van de generieke transformatie met gewijzigde tekst en opnieuw berekende hash | Aangescherpt: de transformatie reconstrueert geselecteerde tekst opnieuw uit bronblokken; extra tekst en te lange offsets worden geweigerd. Regressietest opgenomen. |
| Correctie van kandidaattekst/type of verwijderen van v2-evidence | Oude veldwaarden worden eerst gewist; stale/ontbrekend bewijs blokkeert toelating. Geen heuristische reparatie. |
| Terugval op regex-invulling | Test maakt de legacy-verrijker onbruikbaar en bewijst dat v2 hem niet aanroept. V1 blijft zijn eigen contract gebruiken. |
| Dubbele uitvoering of v2-replay onder v1 | Consoleproef bewijst persist/restart en replay zonder tweede modelcall; contractwisseling veroorzaakt een nieuwe call en weigert een verkeerd gevormd voorstel. De vorige objectset blijft beschikbaar. |
| Alternatieve writers en runtime | ASGI/CLI gebruiken de bestaande binding; directe klasseconversie blijft expliciet legacy. Lokale objectopslag is getest; PostgreSQL-adapter en atomische commit/concurrency-grenzen zijn niet gewijzigd. Geen live PostgreSQL-bewijs geclaimd. |
| Tweede authority of gedeeltelijke cutover | Evidence blijft objectmetadata binnen dezelfde WorkingRevision. Legacyregister is beschrijvend en geen runtimebeslisser. Nieuwe verwerking blijft opt-in; gepubliceerde objecten worden niet gemigreerd. |
| Rollback en herstel | Opt-in uitschakelen met de v2-lezende release. Historische v2-evidence blijft behouden; terugrollen naar een oude binary is niet bewezen en is geen ondersteund herstelpad voor v2-resultaten. |

Resterende onzekerheid: een letterlijk bronbereik kan semantisch verkeerd toegewezen zijn. Dit contract voorkomt vrije veldtekst, maar vervangt menselijke review en de vergelijkingsmeting vóór productiecutover niet.

## Uitbreiding broncontext (2026-10-02)

De opdracht voor betrouwbare kennisobjecten vervangt de eerdere opt-in-default voor nieuwe runtime-proza: v2 is primair. Expliciete legacyconfiguratie blijft leesbaar; beslisbomen blijven structureel. `source-bound-context-v1` voegt alleen exacte contextspans, rollen en gesloten unresolved redenen toe. Admission `source-context-admission-v2` controleert daadwerkelijke realisatie onafhankelijk van scanflags. Geen backfill, SQL-migratie, herreview of wijziging van publicatiehashes. Zie docs/change-contracts/knowledge-context-foundation.md voor invariant-, transactie- en herstelbewijs.

## Versioned successor (#496)

The v2 core-only and mandatory actor/scope admission requirements are explicitly reopened by #496. The additive v3 successor and its staged acceptance/rollback contract are specified in [recommendation-context-v3](../change-contracts/recommendation-context-v3.md). V2 records retain v2 semantics; the default remains v2 pending the live-provider and durable acceptance gates.
