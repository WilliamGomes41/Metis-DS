# Afzonderlijke adversarialreview van #474 in #471

Deze review is na de implementatie uitgevoerd vanuit bypass-, concurrency- en
herstelrisico's. Het is een agentreview, geen menselijke inhoudelijke
referentiebeoordeling of echte modelproef.

| Aanval op de belofte | Bevinding en uitkomst | Concreet bewijs |
|---|---|---|
| Alleen HTTP beschermt autorisatie | Ook het directe command controleert reviewerrol, named reviewer en bronbeschikbaarheid. | Onbevoegde actor en directe commandtest. |
| Oude cache overschrijft een andere reviewer | De snapshotrij wordt vóór herladen vergrendeld; objects_revision is verplicht. Geen authority-restore vanuit oude cache. | Native stale-worker- en commit-failuretest. |
| Deferred PostgreSQL-commitfout laat half besluit achter | Objecten, bindings en event lenen dezelfde workflowtransactie. Bij rollback worden mirrors uit authority herbouwd. | Native deferred trigger; exact vóór/na en restart. |
| Publicatie en broncontextwijziging kruisen elkaar | Gevonden: publicatie had niet dezelfde rijbarrière. Hersteld in de bestaande publish-entrypoint vóór authority-read. | Native race in beide volgordes: context eerst -> BLOCKED; publicatie eerst -> immutable. |
| Foutieve bronrol kan niet worden teruggedraaid | Gevonden: een bevestigde rol kon alleen een andere niet-kennisrol worden. Expliciet reset-command toegevoegd vóór verdere code, onder hetzelfde contract. | Bron en oude doelen opnieuw needs_review; geen eerdere approval hersteld; oude versies aanwezig. |
| Label toch als kennis publiceren via andere reader | Directe approve wordt geweigerd voor iedere opgeslagen bronrol. Gepubliceerde retrieval weigert ook zulke objecten; tweede review vereist bestaande actuele approval. | Directe approvegrens en retrievaltest; producer/readercontrole. |
| Context bij gewijzigde tekst wordt ten onrechte definitief | Validator vergelijkt literal identity, sourceversie/hash, doel-ID, exacte tekst en bronposities. Closure blijft open bij ontbrekende of stale koppelingen. | Gewijzigde doeltekst; unresolved closure. |
| Oude publicatie heropent door nieuw beleid | Broncontextcommand volgt bestaande published guard; geen startup/backfill. | Native publicatie/restart/policy/opvolger/intrekkingproef. |
| CSV of MCP reconstrueert een besluit | Beide projecteren bestaande JSONB objectmetadata; reverse targets zijn afgeleid. Modelcalls blijven buiten MCP. | Gelijke context-export/passagedata en native MCP-read. |
| Gepubliceerde labeltekst raakt bij serving verloren | Exacte context is opgenomen in de canonieke doelpassage en retrieval; geen afzonderlijke source-role serving-set. | Native Product API en canonieke retrieval na publicatie. |
| Bestandcompatibiliteit wordt tweede authority | File-backed console gebruikt bestaande atomic store bundle; productie gebruikt workflow PostgreSQL. Er is geen nieuwe relation-store. | File-restart/idempotentie en native varianten. |
| Rollback naar oude validator accepteert nieuwe context | Oude validators begrijpen de nieuwe metadata niet. Geen veilige semantische downgrade geclaimd: stop nieuwe contextcuratie/publicatie, behoud JSONB/audit, hervat na re-upgrade. | Expliciete rollbackgrens in contract; geen destructieve migratie. |

De native proeven worden pas als uitgevoerd geteld wanneer GitHub CI op het
exacte definitieve PR-head slaagt, met PostgreSQL 16 en beide Python-matrices.
Lokale skips tellen niet als native bewijs. De actuele run en aantallen staan in
de PR; deze review vervangt CI niet.

Onopgelost buiten deze technische review: daadwerkelijke selectiedekking op
Eenzaamheid. De historische input is exact gereconstrueerd, maar zonder echte
modelcall en menselijke referentie is een inhoudelijke PASS niet bewezen. Het
read-only controlescript en formulierbereiding staan in
`docs/EENZAAMHEID_SEMANTIC_ACCEPTANCE.md`. #471 blijft daarom concept tot deze
acceptatie is afgerond. Geen deploymentpakket wordt als eindrelease aangemerkt.
