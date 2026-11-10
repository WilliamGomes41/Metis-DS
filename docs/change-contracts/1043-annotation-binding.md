# Eén contextbinding zonder tweede tekstselectie

Change class: B
Rewrite risk: none
Promise: een geselecteerde voorwaarde wordt met één expliciete actie zowel als
contextbereik als passend betekenisveld bij dezelfde annotatie bewaard.
Touches lifecycle invariants: no
Proof: echte Chromium-route over native PostgreSQL, inclusief herladen,
essentiële keuze en ongewijzigde bronposities; gerichte bestaande regressies.

Uitvoering: [GitHub #1043](https://github.com/WilliamGomes41/Metis-DS/issues/1043)
en [MET-67](https://linear.app/metis-phoenix/issue/MET-67/1043-begeleide-annotatie-context-en-betekenisveld-in-een-handeling),
op expliciete opdracht van William. Ontwerp:
[begeleide annotatiewerkplek](../architecture/annotation-workplace-guided.md).

Bestaande route: de editor voegt een contextbereik toe en vraagt daarna een
afzonderlijke selectie om een betekenisveld te binden. `annotations.save` is
reeds de enige schrijver van revisie/head/generation/receipt. De slice verandert
de constructie en presentatie van die bestaande opdracht, geen opslagcontract,
reviewbeleid of publicatievoorwaarde.

De pure clienttaakmodule bundelt rol en veld waar de bestaande contracten een
eenduidige mapping toestaan. Servermetadata komt uit bestaande veld-/rolowners.
Een ingevuld afwijkend veld of een kernmarker wordt niet stil overschreven.
Herstel van een essentieel verband behoudt de oorspronkelijke relationship_id.

De eerste bronpassage is niet standaard geselecteerd. De hoofdactie noemt het
doel en vereist aangewezen tekst. Een nieuwe contextbinding vereist een lokale
expliciete essentialiteitskeuze; bestaande false-data wordt niet als bewezen
beantwoording hervertaald. Opgeslagen pending_range blijft het bestaande
herstelpunt en wordt geen wizardstatus. Onderbouwing-NA wordt niet ingevuld.

Dezelfde complete selectie gaat via dezelfde autosave naar POST /annotations/api.
Bij fouten blijven lokaal werk en exacte retry-opdracht bestaan. De kernel
bewaart de versie en bestaande correctiegevolgen atomair of helemaal niet;
revision/generation/objectfrontier blijven concurrente writes begrenzen.

| Risico | Beslissend bewijs | Grens |
| --- | --- | --- |
| Context opgeslagen zonder veld | Browser koppelt voorwaarde eenmaal; API-read en reload tonen hetzelfde contextbereik en condition_span | Geen menselijke inhoudsacceptatie |
| Titel of stil standaardantwoord gebruikt | Editor begint zonder selectie; een nieuwe contextkoppeling wacht op expliciete keuze | Oude API blijft bestaande bool-semantiek behouden |
| Veld of essentiële historie verloren | Pure taakproeven voor bestaand ander veld, kernmarker en herankering van dezelfde verplichting | Geen nieuwe autoriteitsregel |
| Bestaande annotatiebediening stuk | Bestaande native invoer-/reviewtests en volledige browserannotatieproef | Volledige driestappeninterface volgt later |

Nog buiten deze slice: per-annotatiecheckquery, volledige conflictvergelijking,
verdere begeleide stappen, gebruikerstest en deployment. Geen nieuwe kandidaatmaker,
database, duurzame vraagstatus of animatie-/UI-framework. Herclassificeer vóór
verdere code als een bestaande lifecycle-/writegrens toch gewijzigd moet worden.
