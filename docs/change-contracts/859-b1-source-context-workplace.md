# Broncontext op Vorming — #859-B1

Change class: B
Promise: De toegewezen reviewer legt broncontext vast, wijzigt of heft deze op in Vorming; Review toont het bewijs en verwijst naar die ene editor.
Proof: Bestaande HTTP/PG-contextproeven plus browser → bestaande POST → PostgreSQL → refresh/herstart; Review bevat geen contextformulier of contextkiezer.
Touches lifecycle invariants: no
Rewrite risk: none

Part of #859, B1. Base: `64db9f6379bfe039bc0b003bcf46f684d4b5265f`
(actuele main, geïntegreerde #865). Geen merge/deploy/productiemutatie.

## Ground

Het ontwerp van #857 en de mapping F3 in [PR 1](domain-workplaces.md) blijven leidend.
De volgende B-belofte wordt gesplitst zoals #859 toestaat. Deze PR verplaatst
uitsluitend de bestaande `/review/source-context`-bediening, inclusief de rollen
label/context/excluded/reset. Batchbronuitsluiting (`/review/source-exclusions`),
koppen/relaties, bronvoortzetting en kandidaatherstel blijven hun verschillende
bestaande werkplek gebruiken tot latere B-slices. C1 blijft een expliciete
scopegrens: `review_object` en `submit_review_resolution` combineren beoordeling
en bewerking. Die operatie/transactie wordt hier niet gesplitst of uitgebreid.

Huidige route: `/review` objectdetail → `read_review_passage` (productie PG-read,
exacte objects/generation/bindings, bronvenster en contextkeuzes) →
`_source_context_panel`/`_passage_choices_html` → POST `/review/source-context` →
`resolve_review_revision` → runtime `confirm_source_context` →
`source_context_review_v1.confirm_source_context` → bestaande workflowcommit.
ReviewClosure bewaakt gepubliceerd werk; PostgreSQL-concurrency/CAS en
workflowtransactie blijven eigenaar. De console is alleen presentatie.

Gewenst: dezelfde panelen op de bestaande GET `/source-selection` met document,
object, context_target/context_mode, context_page/context_q. Review toont de
vastgelegde context en een gerichte Vorming-link. Historische editorparameters
op GET `/review` navigeren alleen. Succes en validatie-/stale foutrendering van
de bestaande POST landen eveneens in Vorming. Geen tweede reader/writer,
endpoint, redirect-POST, fallback of duurzame UI-status.

Callers: reviewobjectkaart, source-role-card, contextkiezer, aanpassen/verwijderen,
zoek-/pagineringlinks, POST-vervolg en foutpad, browserfixture en characterization.
Directe POST blijft ondersteund, met dezelfde velden en validatie. Directe Python
commands/tests gebruiken dezelfde kernel. Geen CLI- of dispatcherwijziging.
Productiecompositie/PG-mixins, source reconstruction scope en request-readcontext
blijven behouden. Geen runtime-override wordt vervangen.

## Domein en stateful Class B-overlay

- Domain entity/aggregate: bestaande ongepubliceerde WorkingRevision met
  versiegebonden bronobject en doelobjecten.
- Invariant(s): named reviewer; exacte bron; verplichte reden/broncontrole;
  dezelfde CAS; contextwijziging invalideert betrokken approvals; gepubliceerd
  werk immutable; geen kandidaatmaker of tweede probleemstatus.
- Durable state before: open revisie met bestaande bronrol/context en bindings.
- Durable state after: uitsluitend de reeds bestaande commanduitkomst;
  nieuwe objectversies/context/rol/register, herreview en audit zoals voorheen.
- Transaction boundary: bestaande workflowbundle en PG-documentlock/CAS omvatten
  objecten, bindings en events. Geen nieuwe transactie.
- Failure/recovery result: validatie/CAS/DB-fout laat de command atomair falen;
  draft is alleen verliesbare HTML; refresh/herstart leest bestaande PG-authority.
- Duplicate execution / idempotency result: dezelfde ID/payload geeft hetzelfde
  resultaat; ID met andere payload wordt geweigerd door bestaande command.
- Concurrency result: compact generation-token wordt via bestaande resolver
  naar actuele objectsetrevisie vertaald; stale/concurrent schrijver blijft conflict.
- Audit/evidence requirement: bestaande review_events en exacte bron-/doelversies;
  bronbytes, eerdere versies, kandidaatidentiteit en releases blijven onveranderd.

## Sketch → Agree

Gebruik: reviewer opent context vanuit een Review-passage → Vorming toont de
passage, letterlijke bron en bestaande contextkeuzes → bestaande POST → Vorming
met opgeslagen bewijs → gerichte terugkeer naar dezelfde Review-passage.
Bron/objectidentiteit en contextselectie blijven queryvelden, geen nieuwe state.

Twee alternatieven, beide door dezelfde auteur onderzocht:

| Vorm | Invarianten / ownership | Reads / API | Cleanup |
| --- | --- | --- | --- |
| Bestaande contextpanelen op Vorming; Review read-only | Bestaande command en grenzen intact | Bestaande bounded reader, dezelfde POST | Oude editor direct verwijderd |
| Hele Review-renderer onder Vorming monteren | Vermengt oordelen en editors, neemt C1 mee | Zelfde reader mogelijk | Tweede beoordelingsplek of domeinsplitsing nodig |

Gekozen eerste vorm. Presentatie krijgt een afzonderlijke renderfunctie, geen
domeinwrapper. `_source_context_panel` ondersteunt read-only bewijs; alleen
Vorming roept de bewerkbare variant aan. De bestaande gebonden readinputs
worden één keer gelezen; geen bronselectie-/probleemcollect naast dit detail.
Geen nieuwe datastructuur of abstractie nodig. Uitvoering is geautoriseerd;
Agree voegt geen goedkeuringspoort toe.

De architect-referentiebestanden candidate-brief/design-red-flags/rationale-template
zijn via hun skill-resources niet beschikbaar; de gelezen hoofdskill en bestaande
projectmapping zijn toegepast, geen onafhankelijke ontwerpreview geclaimd.

## Implement → Scrap en bewijs

Verplaats panel, keuzes, succes en fouten samen. Verwijder de oude bewerkbare
Review-call; behoud read-only context en bronopeners. Geen C1-veld verplaatsen.
Risicogerichte verificatie: contextdoelen mogen niet verdwijnen; stale/invalid
draft mag niet schrijven; een niet-toegewezen actor krijgt geen editor/command;
publicatieguards, duplicate, restart en bronbinding blijven bestaande proeven.
Browser bewijst desktop/mobiel, formulier zonder nesting, keyboard en terugkeer.
GET/zoeken/paginering schrijven niets. Bestaande PG-proeven blijven verplicht;
een skip telt nooit als groen.

Rollback: uitsluitend code/presentatie terugzetten met behoud van huidige
context-aware readers/commands en alle opgeslagen versies/events. Geen datareset
of herstel van oude approvals. #859 blijft open; B2/B3/C zijn niet uitgevoerd.

## Werkelijk uitgevoerde verificatie

Lokale controle op de gepubliceerde tree; exacte commit-SHA staat in de PR
(een commit kan zijn eigen SHA niet bevatten).

- Repositorypreflight, compileall src, architecture boundaries, change-contract
  validator, `git diff --check` en Node-syntaxcheck van de browserproef slagen.
- Release-control-preflight wordt na commit opnieuw tegen origin/main uitgevoerd,
  zodat de controle de gewijzigde paden werkelijk meeneemt.
- `scripts/test_postgres.sh` faalt vóór starten: psycopg ontbreekt; PG16 ontbreekt
  eveneens. Architectuurpytest, gerichte context-/passagepytest en `pytest -q`
  kunnen niet starten omdat pytest ontbreekt. Geen PG-skip als bewijs gebruikt.
- Installatie met zowel de geconfigureerde index als expliciete PyPI levert geen
  packages; git fetch faalt op onbereikbare shellproxy. GitHub-plugin levert
  remote bron/publicatie. Main-mergecommit is lokaal hash-gecontroleerd en heeft
  exact de bestaande PR #865-tree; geen onbekende productwijzigingen overgenomen.
- De werkelijke pure contextpanelrenderer is geïsoleerd uitgevoerd: bewerkbaar
  bevat dezelfde POST-formulieren; read-only bevat nul contextformulieren en
  de eigenaarlink. Dit is presentatiebewijs, geen HTTP/PG-acceptatie.
- Zeven characterization-goldens zijn gericht in alleen HTML bijgewerkt:
  vijf contextpanelen via de werkelijke pure renderer en twee inventarislinks.
  Geen duurzaam resultaat-/stateveld aangepast; volledige opname lokaal niet
  beschikbaar. GitHub moet de volledige vergelijking bewijzen.

Native/browser/characterization-CI op de nieuwe head is de vereiste vervolgstap.
Menselijke inhoudelijke acceptatie en gedrag in productie zijn niet vastgesteld.

## Herstel van de eerste CI-run

De run op `359eb2808cf3ab6fe8a5f7faf421e89df01cf176` faalde op drie
unieke HTTP-tests, twee characterization-cases en dezelfde browserproef in
zowel CI als source-processing-proof. De afsluitende suitejobs werden daardoor
ook rood. De opzettelijk rode autorisatie-mutatieproef in source-processing-proof
is geen nieuwe autorisatiefout; de normale native proeven daar slagen.

Oorzaken en begrensd herstel:

- Twee nieuwe negatieve HTML-asserties zagen de selector `data-review-form` in
  het gedeelde JavaScript aan voor een echt formulier. Controleer de bestaande
  HTML-parseruitkomst op daadwerkelijke formulieren (attribuut én action);
  ook de positieve Review-assertie is zo aangescherpt.
- De oudere HTTP-contextcommandproef opende de editor nog onder Review. Alleen
  de editor-GET verhuist in deze proef naar Vorming; de command en de
  read-only bewijscontrole op Review blijven gelijk.
- De browser las de oude URL direct na toetsenbord-Enter. Wacht op de verwachte
  navigatie, met dezelfde bestemming en alle bestaande UI-/opslagasserties.
- Twee goldens misten de tweede broncontextcaller: `Bronbesluit bekijken of
  wijzigen`. Pas uitsluitend die href aan naar de bestaande Vorming-pagina.

De werkelijke `_page`-renderer is geïsoleerd uitgevoerd: de oude substringtest
faalt ondanks nul reviewformulieren; de formulierparser slaagt en detecteert een
bewust toegevoegd concurrerend reviewformulier. Dit bewijst de assertiereparatie,
geen native HTTP-/PG-acceptatie. Lokaal blijven pytest/psycopg/PG16 ontbreken;
GitHub moet alle oorspronkelijke rode proeven op de herstelhead opnieuw uitvoeren.
Geen productcode, domeinregel, guard, writer of opslag gewijzigd voor dit herstel.
