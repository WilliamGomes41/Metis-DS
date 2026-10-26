# #859-B4 — Letterlijke bronaanvulling in Vorming

Class B. Rewrite risk: none. Ground op `main` `f0225f0fed180306e1c9f76678459ffa12011dca`.
Alleen de bestaande zelfstandige herstelhandeling verplaatst; geen lifecycle-,
opslag-, kandidaat- of reviewregel verandert. Dit is geen voltooiing van #859.

## Ground

De enige product-UI-aanroeper is de knop in
`operations_console_app._render_review_card`, met een externe form override naar
`POST /review/context/accept`. Die route blijft bestaan, inclusief de ondersteunde
rechtstreekse HTTP-ingang en Python-aanroepen van `accept_source_continuation`.
Er is geen afzonderlijke CLI-aanroeper gevonden (`rg` op command- en routenaam).

De bestaande bounded reader `review_passage_read_v1.read_review_passage` levert
de focal candidate, aangrenzende passages, bronbewijs en generation-token. Hij
controleert reviewerrol en named-reviewer-lidmaatschap. De POST authenticeert en
vertaalt dat token via `resolve_review_revision` naar de bestaande objectset-CAS.
De runtime-override `DeterministicRepairReviewConsole.accept_source_continuation`
opent `_atomic_snapshot_mutation`, controleert CAS en gebruikt `_allow_revise_write`.
De kernelmethode in `operations_console_v1` blijft de gezaghebbende operatie.

De kernel vereist een source-bound `sentence_continuation` met precies twee delen,
ongewijzigde doeltekst, de eerstvolgende niet-koppassage en letterlijke aansluiting
in geverifieerde bronpassages. Hij valideert semantische spans met de bestaande
enige materialiser `materialise_knowledge_candidates` en roept `correct_object`
aan met de vaste tekstpatch en `rereview_scope="object"`.
`ReviewClosureConsole` bewaakt de veranderbare werkversie; de closed-loop override
behoudt bronvalidatie. De PostgreSQL-runtime bezit/joint de bestaande store command,
rijvergrendeling, transactie en eventbuffer; correctie controleert bron, revisie,
mutability en bevoegdheden opnieuw voor de bestaande prepared commit.

Dezelfde kandidaat krijgt een nieuwe versie met voorgangerhistorie, bronmapping
en `needs_review`. Alleen diens reviewbinding vervalt. Onafhankelijke goedkeuringen,
document-reviewpasses, bronbytes/-identiteit en publicatievoorwaarden blijven gelijk.
Gepubliceerd werk is onveranderbaar. Bestaande stale fouten blijven HTTP 400;
er komt geen nieuwe conflictstatus of compensatieschrijver.

Stateful Class B overlay (bestaande overgang, geen nieuwe regels):

| Veld | Contract |
| --- | --- |
| Domain entity/aggregate | Bestaande snapshot en kandidaat met versiehistorie |
| Invariant(s) | Letterlijk brongebonden herstel, één schrijver, onveranderbare publicatie |
| Durable state before | Ongewijzigde kandidaat met actueel continuatievoorstel |
| Durable state after | Zelfde kandidaat-ID, nieuwe versie, voorganger, `needs_review` |
| Transaction boundary | Bestaande PostgreSQL store command: objecthistorie, bindinginvalidatie en ledger/events samen |
| Failure/recovery result | Bestaande rollback en refresh; geen gedeeltelijke correctie; herstart leest dezelfde PG-autoriteit |
| Duplicate execution / idempotency result | Herhaald token faalt CAS; actuele herhaling zonder voorstel faalt de kernelguard |
| Concurrency result | Eén schrijver wint de bestaande lock/CAS; stale schrijver wijzigt niets |
| Audit/evidence requirement | Bestaande `revision_created` en `quality_object_corrected`; geen tweede register |

## Sketch en Agree

Twee onafhankelijke read-only architectuurverkenningen vergeleken:

1. Een `task=continuation`-tak in de bestaande `render_context`, vóór de
   contextprojector en keuzelijsten. Eén bounded read, maar koppeling aan B1's
   draft/error-contract met een full-snapshot-pad.
2. Een eigen presentatiefunctie in hetzelfde `source_selection_ui_v1`-module,
   op dezelfde GET-route met `task=continuation`, rechtstreeks op dezelfde reader.
   Een kleine herhaling van paginachroom houdt de twee taken onafhankelijk.

Keuze: 2. Geen nieuwe reader, endpoint, adapter, opslag of generieke werkpleklaag.
De uitvoeringsopdracht autoriseert deze afgebakende implementatie. De architect-skill
is toegepast; diens aanvullende referentiebestand was niet leesbaar via skills.read.
De hoofdskill en beide onafhankelijke verkenningen waren wel beschikbaar.

## Implement: eigendom en context

| Onderdeel | Behouden | Verplaatst / verwijderd |
| --- | --- | --- |
| Review | Voorstel en letterlijk bronbewijs; inhoudelijke beoordeling | Acceptatieknop/form override verdwijnt, exacte link naar Vorming komt terug |
| Vorming | Bestaande GET `/source-selection` en bounded bronreader | Eén formulier voor bronaanvulling op `task=continuation` |
| Command | POST, commandnaam, actor, snapshot/object-identiteit, CAS en alle guards | Alleen succesnavigatie naar de eigenaar |
| Opslag/runtime | PostgreSQL/Azure, bestaande transacties, historie en bindings | Geen wijziging, kopie, cache of duurzame UI-status |

De owner-GET is zuiver lezen. De form bevat bestaande snapshot/object-ID,
generation-token en genormaliseerde `return_task`; dit laatste is uitsluitend
navigatiecontext. Geen nieuwe domeinvelden of kandidaatmaker. Na POST blijft de
gebruiker bij dezelfde kandidaat in Vorming, ziet de huidige tekst en kan exact
die passage opnieuw beoordelen. Een succesquery is alleen presentatietekst, geen
gezaghebbend herstelbewijs: de huidige opgeslagen kandidaat wordt opnieuw gelezen.
Zonder actueel voorstel, bron of veranderbare werkversie verschijnt geen editor.
Herhaling met hetzelfde token faalt via bestaande CAS en maakt geen extra revisie.

Deze bestaande standalone overgang vraagt geen ontkoppeling van de gecombineerde
inhoudelijke review/correctie in C1. Als dat alsnog nodig blijkt: stoppen en herscopen.

## Kleinste bewijs en Scrap

- Native PostgreSQL: Review heeft bewijs/link en geen oude submit; Vorming heeft
  het enige formulier op de bestaande route en een bounded revision-token.
- GET/refresh verandert geen historie, revisie of binding. Stale submit schrijft
  niets; succes behoudt ID/bron, maakt één versie en vraagt herbeoordeling.
- De bestaande restartproef behoudt onafhankelijke goedkeuringen en documentflags.
  Bevoegdheden, onveranderbaarheid en dubbele submit worden gericht gecontroleerd.
- Browser: Review → Vorming → bronbewijs → echte POST → zichtbaar resultaat →
  dezelfde Review-passage, op desktop en mobiel met toetsenbord en screenshots.
- Verwijder de oude bewerkbare ingang in dezelfde PR; behoud alle bestaande
  runtime-overrides en niet-UI-ingangen. Geen tijdelijke dubbele eigenaar.

Verificatie-uitkomsten en de exacte gecontroleerde head-SHA staan in de PR.
Geen merge, deployment of productiemutatie; opvolgende slice blijft afzonderlijk.
