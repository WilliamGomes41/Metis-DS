Change class: B
Promise: De reeds goedgekeurde KO-2-reviewkaart en bon komen via een expliciete integratie-PR ook op main beschikbaar naast KO-3, zodat KO-4 op de werkelijke kaart en het bestaande assessmentcontract kan bouwen.
Proof: Behoud van beide parent trees buiten expliciete overlap; gerichte KO-2/KO-3 UI- en native browserproeven, karakterisatie en volledige CI op de gecombineerde branch.
Touches lifecycle invariants: no
Rewrite risk: none

## Aanleiding en opdracht
De operator geeft op 6 november opdracht KO-4 te bouwen met pstack. Bij controle blijkt #1001 (KO-2) op 10:37:50 UTC gemerged naar docs/review-card-receipt-agreements, nadat #999 die ontwerptak op 10:37:16 UTC al naar main had gemerged. Main9cd19ab7 bevat KO-3 maar niet KO-2. Deze noodzakelijke integratie verandert de afgesproken KO-2-functionaliteit niet. De oorspronkelijke KO-2-branch en zijn handoff blijven onaangeraakt. Geen merge/deployment geautoriseerd; alleen integratie-PR voor operatorreview.

## Bestaand mechanisme en begrensde wijziging
De KO-2-implementatie is exact76444a4c, opgenomen in docs-parent39ec95bd. Main9cd19ab7 bevat de KO-3-publicatiepagina en de externe testfixturefix640712b3. Maak een nieuwe branch vanaf main en merge uitsluitend de al gemergde KO-2-parenthistorie. Los overlap op in console.css met behoud van beide stijlen en in29karakterisatiebestanden met behoud van KO-2-HTML plus correcte gecombineerde stylesheetvingerafdruk. Geen nieuwe reviewvoorwaarden, domeinrecords, schrijvers, bronrolconsolidatie of wijzigingen aan #942.

Domain entity/aggregate: bestaande WorkingRevision en exacte reviewbinding uit de oorspronkelijke KO-2-implementatie; geen nieuw aggregate.
Invariant(s): ongewijzigde geautoriseerde reviewbesluiten, exacte objectversie/hash, atomaire opslag en bon uitsluitend na bevestigde commit; behoud KO-3-gates/registry.
Durable state before: bestaande PostgreSQL-workflow en canonieke publicaties op main; code van KO-2 nog niet aanwezig.
Durable state after: opslagvorm onveranderd; bestaande KO-2-commands beschikbaar zoals reeds gereviewd in #1001.
Transaction boundary: ongewijzigde review_command/workflow.write_bundle-grens uit KO-2.
Failure/recovery result: bestaande weigering/rollback/herstel uit KO-2/KO-3 blijft; deze integratie voert geen datawijziging uit.
Duplicate execution / idempotency result: bestaande commandidentiteit/exacte binding/CAS; geen nieuwe deduplicatie.
Concurrency result: bestaande native PostgreSQL-commandgrens en revisiecontrole; opnieuw aantonen op gecombineerde tree.
Audit/evidence requirement: bestaande review-/receipt-evidence; geen nieuw auditformaat. Treevergelijking en native browserbewijs tonen integratiepariteit.

## Scope en handoff
Alleen integratie van reeds goedgekeurde KO-2, plus noodzakelijke conflict- en golden-assetresolutie. KO-4 wordt apart gebouwd en op deze branch gestapeld. Programma #995 / MET-56 blijft In Progress. Broncontextdeel KO-4 wacht op #942. Geen runtime-infrastructuur of productieacties.

Part of MET-56.

