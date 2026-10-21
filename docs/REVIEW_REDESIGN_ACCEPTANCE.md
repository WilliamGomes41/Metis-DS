# Review vanuit domeinlogica

Implementatieprogramma: #422, #424, #426, #428, #430 en #431.
Deze wijziging is voor GitHub/main; deployment is niet geautoriseerd.

## Betekenis van het werk

Een bronpassage blijft vindbaar totdat haar gebruik expliciet is afgehandeld.
Een typevoorstel, bronindeling, inhoudelijk besluit en onafhankelijke tweede
beoordeling zijn verschillende controles. Een hoofdstuk is geen semantisch
cluster. Een selectie is geen gezamenlijk kennisobject.

| Gebruikershandeling | Domeinbetekenis | Bestaande autoriteit |
|---|---|---|
| Documentindeling controleren | Positie/kop in de bron vaststellen | Structuurbeoordeling |
| Passage afzonderlijk beoordelen | Inhoud, type, gebruik en expliciete relaties controleren | Objectversie en reviewbinding |
| Passages selecteren en bevestigen | Geschikte passages afzonderlijk goedkeuren met één selectie | Bestaande batchcriteria en per-object binding |
| Gebruik van bronpassage bepalen | Kennis, context, onderbouwing of gemotiveerde uitsluiting bepalen | Definitieve passageafhandeling |
| Tweede beoordeling | Andere bevoegde reviewer controleert dezelfde versie | Versie/hash/type-gebonden reviewbinding |
| Technisch herstel | Brongebonden correctie maken en opnieuw beoordelen | Bestaande reparatieopdracht en nieuwe werkversie |

## Dashboard en werkruimte

Het dashboard toont voortgang, een eerstvolgende beschikbare handeling, open
werk, wachten op een andere reviewer en één technische-controleroute. Het
volledige passage-overzicht blijft bereikbaar, ook als geen beoordeling voor de
huidige reviewer beschikbaar is. Passageaantallen en aantallen handelingen mogen
niet worden opgeteld. Geen beschikbare handeling betekent niet publicatiegereed.

De individuele lijst groepeert alleen op opgeslagen bronpad. Werkelijke
inkomende/uitgaande relaties worden apart getoond met hun voorstel/bevestiging
en versiecontrole. Ook gerelateerde passages buiten de actuele werklijst worden
gevonden. Een ontbrekende of verouderde relatie blijft zichtbaar als waarschuwing.

Een type heet expliciet voorstel totdat het bevestigd is. De correctielink opent
de bestaande classificatiekeuze. Er wordt geen nieuwe automatische classifier of
inhoudelijke clustering geïntroduceerd. Een groep met één passage opent de gewone
beoordeling. Meerdere geselecteerde passages worden in de runtime binnen de
bestaande gezamenlijke opslagtransactie afgehandeld.

Een geblokkeerde passage biedt geen goedkeuring. Bij reparatie wordt niet eerst
haar geblokkeerde type bevestigd. De gebruiker specificeert de correctie; de
bestaande reparatieroute maakt een nieuw voorstel uit de oorspronkelijke bron.
Die nieuwe versie moet opnieuw beoordeeld worden.

## Opslag en lifecycle

Geen nieuwe opslag, achtergrondtaak, migratie of alternatieve waarheid is nodig.
In de PostgreSQL-runtime blijven werkobjecten, reviewbindingen en auditgegevens in
de bestaande workflowstores. Bronbestanden blijven in de immutable bronstore;
publicaties en actieve uitlevering blijven bij canonical store en registry.
Lokale Console-bestanden blijven herstelbare projecties in die runtime.

De selectie gebruikt de bestaande snapshottransactie. Een fout in een volgend
besluit rolt de geselecteerde besluiten en bewijs terug. De lokale compatibility-
uitvoering heeft haar bestaande rollback bij afgevangen fouten; PostgreSQL heeft
ook de database-transactie. Dit introduceert geen nieuwe crashgarantie voor de
lokale bestandsuitvoering.

## Acceptatiebewijs

| Belofte | Bewijs in tests |
|---|---|
| Iedere passage vindbaar, herstel niet dubbel | `test_review_task_dashboard.py` |
| Voorstel versus bevestigd type en correctielink | `test_v233_product_proportionate_review.py`, `test_v233_review_audit_regressions.py` |
| Werkelijke relaties inclusief verouderde versie | `test_d5_2_review_context.py` |
| Selectie faalt geheel of slaagt geheel, herstart/replay | `test_closed_review_loop_v1.py`, `test_review_batch_atomic_postgres.py` |
| Geblokkeerde broncorrectie via HTTP, geen impliciete goedkeuring | `test_review_closure_v1.py` (lokaal en PostgreSQL) |
| Andere reviewer en actuele versie vereist | `test_d5_3b_review_routing_cutover.py` |
| Publicatie, opvolging, intrekking en volledig herstel | `test_lifecycle_withdrawal_recovery_v1.py` |
| Gepubliceerd werk blijft onveranderlijk | `test_published_working_revision_immutable_v1.py`, `test_published_working_revision_immutable_2b_postgres.py` |

De native PostgreSQL-lifecycleproef verwijdert alle oorspronkelijke lokale
Console-bestanden en herstelt workflow, canonical/registry, bronbestanden en
archiefbewijs. Het passage-overzicht moet vóór en na herstel gelijk zijn;
ingetrokken of vervangen releases mogen niet terugkeren in de Product API.

Volledige CI op Python 3.12 en 3.13 met PostgreSQL 16 is de mergevoorwaarde.
De oorspronkelijke productiecasus (343/5 en later 338 vervolgpassages) is hiermee
niet live gereproduceerd. Een synthetische dekkingstest vervangt geen controle
van dat concrete document na een later, afzonderlijk geautoriseerd deploymoment.
