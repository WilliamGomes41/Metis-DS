# #859-B afronden — herstel en graafvorming

Change class: B
Rewrite risk: none
Touches lifecycle invariants: no
Promise: Bestaande kandidaatcorrecties en graafbewerking worden alleen op Vorming aangeboden; Review beoordeelt bestaande voorstellen.
Proof: Echte PostgreSQL-/HTTP-/browserproeven bewijzen eigenaar, geen GET-writes, exact herstel, CAS, bevoegdheden, herstart en behoud van review-/publicatiegrenzen.

Ground: `main` `559ab4f05ef6a70689051dd4cf79444233bba1f3`, na #869.
B1–B4 zijn geïntegreerd. Deze slice rondt B af; C blijft apart en #859 blijft open.

## Ground → Sketch → Agree

C1 verbiedt het los opslaan van een revisiebesluit en later repareren. De actuele
`submit_review_resolution` is echter al een zelfstandig ondersteunde samengestelde
opdracht: voorafgaande Review-POST is geen preconditie. De preflight controleert
reviewer, toewijzing, object, reden en revisie. De bestaande opdracht blijft zelf
de interne revise/correctie/heropening atomair uitvoeren. Die interne audit is
geen nieuwe afzonderlijke beoordelingshandeling op Vorming. Er komt geen nieuwe
overgang, geen tussenstatus en geen afzonderlijke schrijver.

Twee onafhankelijke read-only architectuurverkenningen hebben dit getoetst:
agents `/root/b_final_candidate_a` en `/root/b_final_candidate_b`, met dezelfde
Ground-bronnen en afzonderlijke analysecontexten.

| Vorm | Afweging |
| --- | --- |
| A: complete bestaande resolve-opdracht naar Vorming; bestaande inhoudelijke bevestigingen in Review | Gekozen: behoudt één transactie, alle guards en ondersteunde callers |
| B: losse `correct_object`/`confirm_relations` inzetten of edit eerst naar Review doorsturen | Verworpen: andere precondities/invalidatie of onnodige doorstuurlaag; lost C1 niet op |

De opdracht autoriseert implementatie. Architect, domeinontwerp, contextbehoud en
risicogerichte verificatie worden toegepast. Aanvullende architect-referenties en
Linear-agentnotes waren niet toegankelijk; de hoofdskills, code en beide echte
verkenningen waren beschikbaar.

## Operaties, callers en eigenaars

| Handeling | Huidig → gewenst | Bestaande lees-/schrijfgrens en cleanup |
| --- | --- | --- |
| Exacte bronselectie, samenvoegen, onderbouwing, type/plaats/legacy-sterkte corrigeren | Review-kaart en structured exception → Vorming | GET `/source-selection?document=S&object=O&task=repair`; bestaande broncatalogus/`source_units` en documentkeuzes, bounded passage-read voor classificatie. Form direct naar bestaande POST `/review/resolve` → `ReviewClosureConsole.submit_review_resolution` → deterministic repair. Oude wijzigcontrols weg; exception gebruikt hetzelfde Vorming-formulier |
| Voorgesteld/huidig type, brongebonden richting/sterkte en voorgestelde relaties inhoudelijk bevestigen | Review → Review | Bestaande `/review` → `review_object` blijft eigenaar. Dit zijn bevestigingen binnen exacte review, geen zelfstandige correctiecommands. Geen nieuwe resolve-velden voor direction/strength_level/relations |
| Graafnodes/edges bewerken | Review-graaf → Vorming | Zelfde GET `/source-selection`, task=graph; bestaande envelope/object/evidence-read; bestaand POST `/review/decision-graph`, action=graph → `update_decision_graph`. Oude editor weg |
| Graafinterpretatie bevestigen en onafhankelijke passagebeoordeling | Review → Review | Zelfde POST action=confirm → `confirm_decision_graph`; `approve_second_review` blijft ongewijzigd |

Behoud directe Python-/HTTP-callers, probes en runtime-overrides. `StructuredRepairRequired`
blijft werken voor oude/niet-UI-aanroepers; zijn ongeschreven submission wordt alleen
in de ene Vorming-presentatie getoond. Historische repair-GETs navigeren/verklaren;
zij schrijven niets. Alle normale links/werkbord-/probleemcallers wijzen naar de eigenaar.

Niet elke bronselectie is bounded: bestaande merge/support-keuzes vereisen hun
documentset; bronselectie gebruikt de bestaande geverifieerde catalogus. Laad alleen
de gekozen variant en voeg geen bounded+full-fallback of tweede inventaris toe.

## Stateful Class B-overlay

| Veld | Bestaand contract, ongewijzigd |
| --- | --- |
| Aggregate | Snapshot, kandidaatversies/historie/bindings; bij graaf dezelfde brongebonden envelope |
| Invarianten | Exacte bron, bevoegde toegewezen reviewer, mutable werkversie, één materialiser, geen publicatie/approval door herstel |
| Voor → na | Resolve: bestaande kandidaat → gecorrigeerd voorstel `needs_review`; graaf: bestaande geverifieerde graaf → gewijzigde graaf volgens bestaande policy/invalidatie |
| Transactie | Resolve behoudt `_reprocessing_transaction` + `_atomic_snapshot_mutation`, source/CAS-recheck, prepared commit en audit; graaf behoudt eigen native commandtransactie |
| Fout/herstart | Bestaande rollback/refresh; PG/Azure blijven authority, geen gedeeltelijke repair of UI-compensatie |
| Duplicate/concurrent | Bestaande revisie/CAS en graaf-command-ID; stale writer schrijft niets, geen nieuwe idempotentieregels |
| Audit | Bestaande repair-spec/source evidence, revision/review/graph events; geen extra register |

ReviewClosure bewaakt immutable werk. Resolve behoudt alle vier repair-kindregels,
blocked-candidate-beperkingen en exacte bestaande bron-/merge-/supportgeschiktheid.
De PostgreSQL-storecommandcompositie en supported twee-workergrens veranderen niet.

## Contextcontract

| Gegeven | Producent → consument | Geldigheid / levensduur |
| --- | --- | --- |
| Snapshot/object/bron | Bestaande reader → formulier → command | Bestaande identiteit en bronhash, command hercontroleert |
| Verwachte revisie | Objectset of bounded generation → bestaande translator → resolve | Zelfde bestaande CAS; oude m2-callers behouden; stale niet stil verversen |
| Reden/selecties/discrepantie | Gebruiker/legacy exception → zelfde resolve-form | Alleen ongeschreven form state, verliesbaar, geen domeinwaarheid |
| Type/parent na correctie | Actuele opgeslagen kandidaat → Review-bevestiging | Actuele bevestigde type/parent gaat vóór oorspronkelijk voorstel; vervolgapproval mag correctie niet terugdraaien |
| Graafcommand-ID/revisie | Bestaand formulier → bestaande graph-command | Bestaande duplicate/conflictregels; navigatie geeft geen autorisatie |

## Implement → Scrap en bewijs

- Eén formulier per herstelvariant op Vorming, echte POST naar ongewijzigde owner;
  Review bevat alleen inhoudelijke bevestigingen en gerichte herstelverwijzing.
- Geen voorafgaande revise-write; bron-/merge-/support-/classificatieherstel sluit
  exact dezelfde bestaande transactie af. Ongeldige keuze/stale/onbevoegd/published
  wijzigt niets. Bewijs dat gecorrigeerd type/parent ook na daaropvolgende review blijft.
- Graafeditor alleen Vorming; graafbeoordeling alleen Review; bestaand command-ID,
  CAS, bronbewijs, refresh/herstart en publicatievoorwaarden behouden.
- Werkbord, bronproblemen, legacy exception/recovery en foutpresentatie actualiseren;
  oude actieve selectors, editvelden en imports verwijderen in dezelfde PR.
- Bestaande kernel-/rollback-/restartproeven hergebruiken, plus echte browser op
  desktop/mobiel/toetsenbord en volledige verplichte repositorychecks/CI.

Exacte gecontroleerde SHA, uitgevoerde checks en bewijsgrenzen komen in de PR.
Geen merge, deployment, productiemutatie of automatische C-doorstart.
