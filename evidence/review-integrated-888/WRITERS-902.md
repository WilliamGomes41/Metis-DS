# MET-23 — schrijfroutes, afhankelijkheden en locks

Change class: C. Rewrite risk: none. Touches lifecycle invariants: no.
Belofte: de bestaande schrijfgrenzen aanwijzen als invoer voor MET-24/#903;
geen productiegedrag wijzigen en geen volledige concurrencydekking claimen.

## Basis en oordeel

Codebasis: `5d96b7041ad8c8f982f1faf6d2defdb204f8433a`.
Onderzoek: broncode, statische callerzoekactie/AST-scan en statische C3-resolutie
van beide productiecomposities. Dit is geen nieuwe runtimeproef. Eerder uitgevoerd
native bewijs: [run 40772073475](https://github.com/WilliamGomes41/Metis-DS/actions/runs/40772073475),
artifact `review-post-902` 12853960099, negen tests zonder fouten of skips op PG16.15.

Het doelobject is geen universele transactiegrens. Gewone approval kan lokaal
blijven, maar relaties kunnen peerobjecten wijzigen, broncontext raakt oude én
nieuwe doelen, en deelnamebeleid projecteert over de huidige documentobjecten.
Een begrensde command moet de bestaande domeinoperatie verdiepen en per variant
zijn lees-, schrijf- en invalidatieset afleiden. Een passage-GET is geen bewijs
voor die sets. Er is bovendien een verschil in bestaande lockvolgordes dat vóór
cutover een gerichte native proef vereist.

Architectuurfase: Ground uitgevoerd; geen nieuw ontwerp of productie-implementatie
in deze inventaris. De bestaande keuze voor verdieping van `review_object` blijft
staan. Alternatieve ontwerpen en migratie worden hier niet opnieuw beslist.

## Authorities en daadwerkelijke dispatch

`console_asgi.py` kiest de FastBadge CompleteWorkflow-console met lokale of
Azure-bronadapter. Beide erven dezelfde review-/document-/identitymixins.
Statische C3-resolutie geeft voor reviewgedrag achtereenvolgens
`ReviewClosureConsole.review_object` → `DeterministicRepairReviewConsole.review_object`
→ `ClosedLoopReviewConsole.review_object` → `OperationsConsole.review_object`.
Voor commits gaat de reviewmixin vóór de documentmixin; identity leest PostgreSQL.
Dit is gecontroleerde bronresolutie, geen nieuwe runtime-/MRO-acceptatietest.

| Gegeven | Authority / eigenaar | Betekenis voor begrenzen |
| --- | --- | --- |
| Objectversies en volgorde | `workflow.document_objects`; `revision_workflow.current_revisions/validate_revision_write` | Bewaar betrokken voorgangers, legacy occurrence/position en immutable historie; niet hoogste semver kiezen. |
| Reviewbevoegdheid en deelname | `workflow.accounts`, documentreviewers/envelopebeleid; identitymixin en reviewpolicy | Rollen, retirement, named reviewer en beleidsprojectie zijn aparte inputs. |
| Exacte approvals | `workflow.publish_authorizations`; `publish_authorization_v1` | Exact tuple/hash/type/actor en geldigheid; geen envelopevinkje als vervanging. |
| Reviewaudit | `workflow.review_events`; reviewstore/ledger | Bestaande globale hashketen behouden; requestwerkbuffer is geen authority. |
| Publicatie/immutability | canonieke publicatiestore/registry; durable publication owner | Documentbarrière en bestaande canonieke releasecontrole behouden. |
| Bron en vorming | immutable bron, extraction/formationcontracten; bestaande vormingseigenaren | Bronidentiteit pinnen; verwerking/activatie niet vervangen door een reviewcache. |

## Schrijfroutes en noodzakelijke sets

Onderstaande sets beschrijven de aangetroffen domeinwerking, niet de huidige
I/O: de store leest en herschrijft nu nog volledige documentsets. De volledige
set benodigde validators kan per variant groter zijn dan de geschreven set.

| Route / concrete eigenaar | Lees-/beslissingsafhankelijkheden | Schrijven / invalidatie |
| --- | --- | --- |
| `/review` → `review_object` (`operations_console_app.py:5599`, `operations_console_v1.py:2909`) | Actor/named reviewer, envelopebeleid, doel/current duty, exacte bindings, bronlocators, parent-/relatiekeuzes en relevante peers | Opvolgerversie/doelgovernance, passage/register, eventuele peers, bindingrecord of invalidatie, review_passes en audit. |
| Mixinvoorbewerking (`review_closure_v1`, `deterministic_review_repair_v1`, `closed_review_loop_v1`) | Mutability; suitability/disposition; inkomende supportrelatie; herstelcontext | Revise/reject kunnen na gedelegeerde review extra heropening/herstelmetadata en audit schrijven. Alleen de basismethode vervangen mist dit gedrag. |
| `approve_second_review` (`operations_console_v1.py:3550`) | Actuele exacte eerste approvers, onafhankelijkheid/tweede reviewer, policy/four-eyes, bron, huidig token | Tweede binding, compatibility second_review mirror en audit. Canonieke kennisinhoud/tuple blijven volgens bestaand contract gelijk; dezelfde store schrijft toch historie mee. |
| `batch_confirm_headings` (`operations_console_v1.py:3696`) | Ontdubbelde volledige batch, actuele rol, named reviewer, headinggeschiktheid, revisie, publicatie | Eén atomaire batch met gedelegeerde review per lid. Geen gedeeltelijk geslaagde batch na fout. |
| `confirm_object_type`, `confirm_relations`, `_prepare_relation_confirmation` (`operations_console_v1.py:1097–1263`) | Doel, bron, oude/nieuwe relaties, oude/nieuwe kinderen, parentstructuur | Type of relatie-opvolger; gewijzigde kinderen krijgen eigen opvolger/parent; bindings voor doel én gewijzigde peers ongeldig. Niet iedere relationele dependency hoeft zelf geschreven te worden. |
| `confirm_source_context` incl. reset/excluded (`review/source_context_review_v1.py:231`) | Bronobject, gekozen doelen én alle bestaande gebruikers van die broncontext, exacte literal/source-identiteiten, huidige bron en toelating/register | Bronrol plus gewijzigde toegevoegde/behouden/verwijderde doelcontexten, opvolgerversies, needs_review/four-eyes reset, bindings voor alle gewijzigde IDs en audit. Alleen nieuwe targets ophalen mist verwijderde oude targets. |
| `confirm_source_exclusions` (`review/source_context_review_v1.py:31`) | Hele expliciete batch, exacte bronrecords/geschiktheid en revision | Bestaande atomaire bronuitsluiting, register/governance en bindings/audit; geen kennisapproval. |
| Correctie/repair (`correct_object`, `_commit_knowledge_change`, `_supersede_merge_targets`, `submit_review_resolution`) | Bronunits of merge-/supporttargets, revision, huidige lineage en betrokken context | Bestaande opvolgers, heropening/supersession, bindings en audit. Merge is bewust meer dan één object. |
| Deelname (`review_participation_v1.execute`) | Actor/replacementaccounts, policy, alle huidige beleidsprojecties en bestaande approvals/graphreviews | Envelope/named reviewers/policyhistory, documentopvolger, governanceprojecties en geretireerde bindings/graphreviews. Dit is geen onafhankelijk passagebesluit. |
| Beslisgraph (`decision_review_commands_v1.execute`) | Exacte graph/source evidence, policy, nodes/routes, reviewtarget en oude graphhash | Envelopegraph, betrokken graph-/objectprojecties, bindings en commandaudit. Eigen command-ID/payloadcontract. |
| Vorming/resume/recovery/reextract | `source_selection_v1`, `source_processing_dispatch_v1`, `source_preparation_context_v1`, `formation_task_store_v1`, console-verwerkingscommands | Attempt/task/context/envelope en activatie/objectset; blijft concurrerende writer en mag niet door bounded Review worden overschreven. |
| Familie/klasse en opvolger | `move_family`, `promote_class`, `decision_successor_v1` | Metadata of bredere herreview; opvolgerregistratie/activatie bewaakt ook parentrevision/policy/source. Geen universele één-document-één-rij-aanname. |
| Rollen/retirement | `workflow_identity_postgres_v1.update_roles/assign_roles`; `account_retirement_v1` | Accounts/sessies wijzigen zonder documentgeneratie; approveridentity moet actueel geldig blijven. |
| Publicatie/reconciliatie | `OperationsConsole.publish`, durable publication owner, `_apply_release_state` | Canonieke release/servingauthority en afgeleide envelopeprojectie; sealed historie is geen gewone reviewwrite. |

Zoekcontrole: AST-scan van calls naar `_commit_prepared_store`, `_save_objects`,
`write_bundle`, `replace_snapshot_bindings`, `update_roles`, gevolgd door lezen
van genoemde eigenaren en hun callers. Dit detecteert geen willekeurige dynamische
dispatch of alle directe SQL; tabel is dus geen automatisch volledigheidsbewijs.

## Drie preconditions; twee soorten closure

| Grens | Huidig contract | Niet veralgemenen tot |
| --- | --- | --- |
| Passageformulier | `resolve_review_revision`: documentrevision + object_generation vergelijken in eigen read snapshot, daarna historie naar bestaand commandtoken | Volledige autorisatie-/bindingsversie of direct storage-merge-token. |
| Reviewcommand | `review_object`: strikte gelijkheid expected_revision/current_revision binnen command | Disjuncte wijzigingen automatisch samenvoegen. |
| Objectstore | `PostgresConcurrentWorkflowDocumentStore._merge_objects/write_bundle`: bestaande objectset-merge en lineagevalidatie | HTTP-stale-formulieren alsnog accepteren. |

Migration 021 verhoogt object_generation bij objectrijmutaties uitsluitend voor
processing_storage_version=1. `replace_snapshot_bindings` vergrendelt de documentrij
maar verhoogt hier geen documentcounter; `update_roles` schrijft accounts. Tokens
alleen dekken deze twee veranderlijke inputs niet. Native rolproef bevestigt dat.

Expliciete invalidatie (`invalidate_for_object`) zet opgeslagen bindings ongeldig.
Afgeleide geldigheid (`still_matches`, context- en publicatieclosure) toetst exacte
tuples en broncontext. Die zijn niet onderling uitwisselbaar: context kan ongeldig
worden doordat een ander bronobject verandert. De toekomstige inventory/proef moet
dan het gedrag van betrokken gebruikers en de uiteindelijke publicatiebeslissing
vastleggen; een gelijk doelobject of GET-contextset bewijst dat niet.

`read_review_passage` volgt inkomende/uitgaande edges, broncontext en structurele
keuzes in een read snapshot. Dat pakket is bruikbaar als weergavebewijs. Het bewijst
niet dat alle oude targets, herstelwrites of beleidsinvalidaties daarin zitten.

## Transactie en aangetroffen lockvolgordes

`_store_write_lock` is een RLock plus flock op `runtime/store.lock`. Alleen processen
die hetzelfde lockbestand delen worden daardoor geserialiseerd. Dat is geen
bewezen databasebrede lock tussen aparte hosts/runtimepaden.
`workflow_transaction` bindt deelnemers aan één native verbinding; geneste
deelnemers gebruiken savepoints. Na rollback worden processmaps alleen herlezen.

| Route | Aangetroffen volgorde / scope | Bron |
| --- | --- | --- |
| Gewone review met gewijzigde bindings | Storelock → outer commandtransaction/reload → authorization advisory lock → documentrij → bindingvervanging → audit/documentwrites; ledgerbuffer wordt vóór outer commit geflusht | `workflow_review_cutover_v1._store_command/_persist_binding_changes`; `workflow_documents_cutover_v1._commit_prepared_store`; `workflow_review_postgres_v1.replace_snapshot_bindings` |
| Headingbatch | Storelock → native transaction → authorization advisory lock → documentrij → leden | `workflow_documents_cutover_v1._heading_batch_mutation:1083` |
| Broncontext/exclusions | Storelock → native transaction → documentrij → later authorization advisory lock bij bindingcommit | `source_context_review_v1:63,244,393` |
| Deelname/graph/verwerkingscommand met lock_row | Storelock → outer commandtransaction → documentrij vóór reload → eventuele binding-/ledgerlocks bij commit | `workflow_review_cutover_v1._store_command`; deelname-/graphowners |
| Publicatie | Storelock → native workflowtransaction → documentrij → readiness/canonieke publicatie/afgeleide writes | `operations_console_v1.publish:4305` |
| Accountlezing/-wijziging | Gewone `_account(current=False)` is SELECT zonder rowlock; current=True gebruikt FOR SHARE; UPDATE/retirement locks accounts apart | `workflow_identity_postgres_v1:144,193,307`; `account_retirement_v1:23` |
| Store/restore | write_bundle locks document en controleert releasehistorie; nieuwe documentidentiteit heeft extra advisory lock; volledige bindingrestore heeft globale authorizationlock | `workflow_document_concurrency_v1:307`; `workflow_review_postgres_v1.replace_bindings` |
| Reviewledger | Globale ledger advisory lock en laatste eventrij FOR UPDATE; buffered flush controleert de keten en weigert een gewijzigde voorganger met workflow_review_chain_conflict | `workflow_review_postgres_v1.append_event/buffered/_flush_buffer` |

**Bevinding:** authorization→document en document→authorization bestaan beide.
Bij een echte bindingdelta en aparte storelocks is een cyclus mogelijk: review houdt authorization en wacht
op document; context houdt document en wacht op authorization. De lokale flock
kan dat in één runtime serialiseren. De bekende batchproef bewijst alleen de
batch/single-volgorde. Er is hier geen native context/single-deadlock gereproduceerd
en geen productieoorzaak vastgesteld. Niet stil een nieuwe lockorde invoeren in
deze Class C-inventaris; eerst bestaand gedrag via gerichte concurrentie bewijzen.

## Bewijsstatus en eerstvolgende controles

| Claim | Bewijs | Open vóór bounded cutover |
| --- | --- | --- |
| Rolwijziging na formulier | Native 403, gelijke generatie/domeintoestand; rolherstel laat oorspronkelijke formulier slagen | Intrekking ná command-autorisatie maar vóór commit; gewoon role-read is geen gehalten accountlock. |
| Nieuwe broncontext na approval | Native generatie 17→33, needs_review, binding ongeldig, oud formulier409, context zichtbaar | Verwijderen/verplaatsen naar andere targets; bronopvolger en inkomende gebruikers; context/single-race. |
| Atomaire individuele review | Native binding-INSERT/COMMIT-fouten rollen historie/bindings/audit/generatie terug; heropbouw en retry slagen | Varianten tweede review/batch/repair en publicatierace afzonderlijk. |
| Consistente batch/single-lockorde | Bestaande test `test_native_batch_and_single_review_use_consistent_lock_order` observeert advisory-wait | Niet uitbreiden tot context, deelname of iedere hosttopologie zonder proef. |
| Behouden retrybetekenis | Approval-form retry409 en command-specifieke semantische duplicatepaden aanwezig | Reject/revise/later/second/batch eigen oracles; `interaction_id` is geen universele deduplicatie. |
| Begrensde kosten | Nog geen bounded writer geïmplementeerd | Vast doel/dependencies bij groei onafhankelijke historie; rows/bytes, execute/fetch, lock-wait/hold en vooraf afgesproken budgetten. |

Eerstvolgende bewijsstap: context/single-review-lockproef met twee onafhankelijke
productiecomposities/runtimepaden en native verbindingen, begrensde deadlines en
veilige waitcategorieën; leg zowel succes als echte databaseweigering vast. Behoud
daarbij domeintoestand/rollback en publiceer geen ruwe SQL/parameters. Daarna
binding-only en oude/nieuwe contextgebruikers plus beslissingsspecifieke retries.
MET-23 blijft open; MET-24 blijft afhankelijk van het resterende meet-/inputcontract.
