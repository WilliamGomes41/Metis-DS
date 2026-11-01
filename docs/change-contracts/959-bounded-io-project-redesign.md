# Begrensd lezen en schrijven — projectontwerp en bewijsverdeling

Change class: C (projectontwerp/documentatie; geen runtime- of governancewijziging).
Promise: Eén GitHub-projectcontract ordent begrensde domeinopdrachten, onderlinge blokkering en gedeeld acceptatiebewijs zonder dubbele werkpakketten.
Proof: Wederzijdse links naar #959, #729, #942, #952, #953 en #931; overeenkomende Linear-indeling en expliciete fasecriteria.
Touches lifecycle invariants: no (dit document); de beschreven implementatie blijft Class A / Rewrite risk high.
Rewrite risk: none (dit document).
Status: ontwerp op gebruikersopdracht van 1 november 2026; geen productimplementatie, merge, deploy of productieacceptatie.

## 1. Gezag en besluit

Projectmap: [#959](https://github.com/WilliamGomes41/Metis-DS/issues/959).
Voortgang: [P-MET-5](https://linear.app/metis-phoenix/project/metis-begrensd-lezen-en-schrijven-294f84133c6b), parent MET-45.
Voorganger: [architectuurvoorstel cfcd4665](https://github.com/WilliamGomes41/Metis-DS/blob/cfcd4665b26d9e3946b6938030353cd24d37d2dd/docs/architecture/bounded-domain-operations-proposal.md).

**Besluit projectontwerp:** behoud de architectuurrichting; herontwerp uitvoering en acceptatie. Eén lokale domeinhandeling verwerkt haar geraakte gegevens en noodzakelijke dependencies. Documentbrede beoordeling blijft expliciet waar het domein die vereist. Vergroot de toets van één document naar systeemgroei en gelijktijdige verzoeken.

GitHub bevat scope, domeincontracten, besluiten en bewijs. Linear vat voortgang samen. Dit document vervangt de eerdere driedelige organisatorische fasering van P-MET-5, niet de runtime-/lifecyclecontracten van de bestaande issues. De toestemming om dit project te herontwerpen is geen impliciet GO om het goedgekeurde D1 te vervangen.

## 2. Gronding en bewijsgrens

Codebasis: main 5a1ec16d08c60c7179952be4c643639d8c24da31.

Vastgesteld in de broncode:
- de generieke writer leest objecthistories ook bij metadata-only writes en gebruikt volledig factonderhoud bij een aangeboden objectset;
- broncommands verrichten bronwerk, ledgerlezing en globale bindings-/documentreloads binnen de buitenste lock;
- de storelock is runtimebreed; aanvullende PostgreSQL-autorisatie-/ledgerlocks hebben hun eigen bereik;
- de losse reviewroute gebruikt al gerichte histories en delta-commit; niet alle routes zijn even breed;
- vorming voert taken opeenvolgend uit; provider_seconds omvat meer dan netwerk-/modeltijd.

Uitgevoerde verkenning: vier pure timingtests passed; een proef met de exacte storelockmethode bevestigde wachten door een tweede eigenaar en het voortbestaan van de buitenste lock na de geneste exit. Een gecontroleerde providertimingproef telde checkpointtijd bij transport_seconds wanneer een checkpoint was meegegeven; de bounded productieprovider geeft checkpoint=None door. Dit laatste is geen aangetoonde actuele productieoorzaak.

Er is geen native PostgreSQL-/HTTP-/productienulmeting uitgevoerd voor dit herontwerp. De vier tests bewijzen timingvelden, geen volledige tijdstoerekening of latency-SLO. De verkennende proeven zijn geen releasebewijs. Historische 70s/11min-incidenten of eerdere codeheads zijn geen actuele baseline.

## 3. Domein en duurzame verantwoordelijkheid

| Begrip | Eigenaar | Grens |
|---|---|---|
| SourceSnapshot en bronbytes | Bestaande immutable bronopslag/Azure Blob | Onveranderlijke bron; externe I/O buiten de SQL-commit |
| WorkingRevision | Bestaande workflowkernel/PostgreSQL | Actuele curatorstate en consistente mutatie |
| Objecthistorie, bindings en audit | Bestaande document-/reviewowners | Geraakte gegevens atomair; geen verdwenen historie of menselijk werk |
| Reviewfacts | Bestaande factowner | Afgeleide intrinsieke inputs; geen zelfstandige goedkeuring of publicatieauthority |
| Vormingsbewijs en archieven | FormationTaskStore en bestaande compacte inputrecords | Exacte bron-/contractbinding; geen gewone GET-hydratatie van archieven |
| Accounts, bevoegdheden en sessies | Bestaande identityowner | Autorisatiemoment en sessieaanmaak onderscheiden |
| PublicationRelease en serving | Bestaande canonieke store/register | Bestaande immutable release- en actieve-servingregels |

Reads en presentatie zijn stateless; mutaties en autorisatieovergangen stateful. HTTP-consolecontext is verliesbaar. OperationsConsole is backendorkestratie, geen frontendauthority. Geen nieuwe database, candidate-creator, lifecycle-status of parallelle transactieowner.

## 4. Bestaande invarianten en voorgestelde kostencontracten

Bestaande lifecycle-/revision-/publicatiecontracten blijven normatief. Zij vereisen bronbinding, actuele bevoegdheden volgens het bestaande autorisatiecontract, behoud van historie, atomaire mutaties en immutable releases.

Het projectontwerp concretiseert de kostenbelofte:
1. Een lokale mutatie schrijft uitsluitend gewijzigde object-/binding-/factrecords en vereiste audit/counters. Een technisch noodzakelijke bredere dependency moet expliciet bewezen worden.
2. Zuivere metadata zonder objectsetpreconditie vraagt geen volledige objectpayloadlezing; oude compatibiliteitstokens behouden hun betekenis tot expliciete migratie.
3. Onafhankelijke document-/event-/bindinggroei veroorzaakt geen onnodige volledige scan/copy in een lokale opdracht.
4. Geen zwaar bron-/providerwerk binnen de werkelijke buitenste schrijflock.
5. Mutaties van dezelfde werkrevisie behouden hun noodzakelijke consistentie. Onafhankelijke opdrachten mogen niet door onnodig lang gedeeld werk worden opgehouden.
6. Kortdurende globale bescherming blijft toegestaan als de domein-/auditreden, lockvolgorde en gemeten kosten expliciet zijn. Er is geen universele eis van nul wachttijd of volledige paralleliteit.

De bestaande validatie onder lock, revocationregels, idempotentievarianten, herstel en publicatievoorwaarden mogen niet worden verwijderd om een kostenproef groen te krijgen.

## 5. Drie onafhankelijke meetassen

| As | Wat varieert | Wat gelijk blijft | Wat de proef onthult |
|---|---|---|---|
| Doel-document | Onafhankelijke objecten/versies en archiefomvang binnen hetzelfde document | Gewijzigde objecten, benodigde histories/dependencies en opdracht | Documentbrede reads, copies, tokenbouw of factwrites |
| Overige systeemdata | Andere documenten en hun bindings/events/archieven | Het gehele doel-document en de opdracht | Globale reloads en volledige ledger-/bindingscans |
| Gelijktijdige verzoeken | Tweede mutatie, gewone GET en signin tijdens de eerste opdracht | Bronnen, datasets en opdrachtvarianten | Gedeelde store-/SQL-/account-/identitylocks en verzoekwachtrijen |

Start voor de bestaande MET-36-schaaleis met ten minste 1.500 objectversies, daarna gecontroleerd vergroten. Gebruik een bronbatch én losse bronopdracht; de gerichte losse review is een tegencontrole. Bron/modeltaakinhoud niet veranderen tussen voor/na-metingen.

Meet per echte POST→commit→redirect→GET: SQL-/storecalls, opgehaalde/geschreven bytes, object-/binding-/factwrites, triggerwerk, bronwerk en duur. Meet buitenste lock hold en wait afzonderlijk en koppel wachtende verzoeken aan hun daadwerkelijke blocker. Processlot, advisoryslot en rijsloot zijn verschillende oorzaken.

Inclusieve geneste tijden overlappen en worden niet opgeteld tot één fictieve totale duur. Een korte innerlijke savepoint- of helperduur bewijst geen korte buitenste transactie.

Gebruik bestaande acceptatiebudgetten. Waar een numerieke grens ontbreekt: leg vóór de interventie dataset, omgeving, herhalingen en grens vast in de uitvoerings-PR. Geen verzonnen productie-p95, nieuwe timeoutverhoging of achteraf gekozen grens.

## 6. Vier opleverfasen

### Fase 1 — Nulmeting en dependencies

Owner: MET-36/#729; MET-43/#952 specificeert relevante actuele dependencies.

Lever één getelde native gebruikersroute plus de drie schaalassen. Inventariseer alle buitenste lock-/transactieowners, scope van mutable maps en benodigde globale audit-/autorisatiebescherming. Maak onderscheid tussen gemeten fout, breed werk en nog onbewezen risico.

Gereed: versiegebonden actuele baseline, falsificerende proef voor de werkelijk geraakte route, dependency-/lockkaart en onveranderde domeinuitkomsten. Geen oude head of helpertest als vervanging.

### Fase 2 — Eén lokaal bronbesluit volledig begrenzen

Owner: MET-36/#729. MET-35/#942 levert bronrolconsolidatie alleen waar die aantoonbaar nodig is voor de geraakte slice; geen algemene blokkade op een refactor.

Bereid broninput buiten de buitenste lock voor. Onder de beschermde commit worden actuele bronpins, actor, status, bindings/beleid/deelnemers en de bestaande preconditievariant getoetst. Lees benodigde histories en schrijf objectdelta, bindingdelta, geraakte facts en audit atomair. Houd benodigde factgeldigheid bij dezelfde commit; geen asynchrone approved-cache.

Gereed: dezelfde eindinhoud, historie en toegestane conflicten, begrensde I/O langs alle relevante schaalassen, echte rollback bij fout na een deelwrite. Vervolgens overige bestaande bron-/review-/metadata-routes incrementeel omzetten.

### Fase 3 — Onderlinge blokkering en aanmelden

Owner: MET-36/#729; afhankelijkheid-/autorisatiesemantiek wordt met MET-43/#952 getoetst.

Neem eerst de gedeelde mutable-mapafhankelijkheid weg of beperk haar veilig; verwijder daarna pas onnodige globale locking. Bewijs wat daadwerkelijk wacht: onafhankelijke documentmutatie, gewone GET, dezelfde reviewer signin en andere gebruiker signin. Leesverzoeken zijn niet automatisch storelockgebruikers.

Toets D1 aan de goedgekeurde eis: pensionering weigert de volgende opdracht. FOR KEY SHARE/NO KEY UPDATE-compatibiliteit alleen bewijst geen schending daarvan. Gewone sessieaanmaak en echte rechtenwijziging worden afzonderlijk getest. Een sterkere garantie tijdens een reeds lopende commit of een andere techniek vereist een expliciet domeinbesluit in het MET-36-contract.

Gereed: native concurrentiebewijs, begrensde gedeelde bescherming, correcte rechtenwijziging/retirement, geen verloren update of deadlock door gewijzigde lockvolgorde.

### Fase 4 — Gedeeld eindbewijs en cleanup

Owner voor eindacceptatie: MET-44/#953; MET-43/#952 voor actuele command/publicatie-integratie. MET-36 en MET-35 leveren hun eigen bewijs aan dezelfde keten.

Bewijs passage openen→besluit opslaan→redirect→opnieuw openen→volledige beoordeling→juiste publicatie-uitkomst. Behoud bestaande v1 plus werkende v2, opvolgerpublicatie, intrekking, nieuw proces en backup/recovery. Verwijder vervangen actieve calls na bewezen vervanging; behoud noodzakelijke historische compatibiliteit. Runtimecompositiediagrammen volgen de werkelijk geïmplementeerde compositie.

Gereed: één gedeeld dossier op exacte code-/bron-/layoutversies; vereiste CI/native checks, adversariële review en waar nodig afzonderlijk geautoriseerde deploy plus productiebevestiging. MET-38 sluit niet door projectregistratie of alleen merge.

## 7. Concrete overdracht tussen #729 en #952

| Overdracht | Leverancier | Ontvanger en bewijs |
|---|---|---|
| Geselecteerde bron-/proofpin, objecthistories en objectdelta | #729 via bestaande kernelowners | #952 controleert exacte dependencydekking |
| Relevante bindings, deelnemers/beleid, actor en preconditievariant | Semantiek bij #952; gerichte toegang bij bestaande owners | #729 gebruikt dezelfde beschermde checks; geen universele generationclaim |
| Atomaire object-/binding-/fact-/auditcommit | Bestaande workflowtransactie, gerichte capability in #729 | #952 bewijst fault injection, stale inputs en publicatierace |
| Kosten- en wachtbewijs | #729 | #953 neemt exact hetzelfde versiegebonden bewijs over |

#952 hoeft niet volledig Done te zijn vóór onafhankelijk baselineonderzoek of veilige bestaande mutatieslices. De geraakte dependency-/atomiciteitsvoorwaarden moeten wel vóór merge van die concrete slice gespecificeerd en bewezen zijn. Geen projectbrede blokkade of cyclische afhankelijkheid toevoegen.

Falen vóór commit geeft rollback. Een verloren response na commit volgt de bestaande receipt-/idempotentievariant. Canonieke publicatie gevolgd door een mislukte workflowprojectie blijft het bestaande reconciliatiepad; geen fictieve rollback of herstel uit oude proceskopieën.

## 8. Wat buiten dit project blijft

Providerparallelisme, modelkeuze, promptkwaliteit, taakgrootte en verbetering van modelvoorstellen blijven MET-31/#931 en de bestaande vormingseigenaren. Aanroepen, provider_seconds, transport_seconds, validatie en checkpoints worden daar afzonderlijk gemeten. Providerduur is geen zuivere serverwachttijd; de supervised transport omvat ook lokaal proces-/netwerk-/responsewerk.

Binnen dit project geldt uitsluitend dat providerwerk geen langdurige document-/globale schrijflock vasthoudt. Vorming versnellen is geen algemene blocker voor oplevering. MET-37 behoudt het historiegroei-/retentieonderzoek na D2; geen ongevraagde historieopruiming.

## 9. Gefaseerde overgang en herstel

Rewrite target van uitvoering: gedeelde read-/object-/fact-/autorisatiegrens; geen nieuwe authority. Ondersteun beide bestaande PostgreSQL FastBadge-composities en bestaande lokale/Azure bronadapter. Geen nieuwe multi-hostgarantie.

Expand: gerichte capability bij bestaande owners toevoegen. Migrate: callers per domeinhandeling met parity- en tegenproeven omzetten. Contract: brede mutatie-/reloadfallback voor omgezette routes afsluiten. Als een noodzakelijke dependency toch documentbreed is, benoem die en classificeer de operatie expliciet als documentopdracht.

Normale delta's behouden bestaande opslagidentiteiten en versies. Eventuele schemawijziging vereist eigen migration-/backupcontract. Bestaande compacte opslaglayout moet leesbaar blijven voor de gekozen rollbackbinary. Rollback is geen terugkeer naar een incompatibele oude binary.

Blast radius en tegenproeven: corrupte/ontbrekende bronproof, bindings-only/policy-/actorwijziging, fault tussen writes, twee reviewers, publicatierace, herstart, D2-superseded historie, alternatieve ingress en oude writers. Worst-case weigering/conflict mag geen stille wijziging van menselijk werk of serving opleveren.

## 10. Prioriteit en eerstvolgende stap

P-MET-5 blijft High; MET-36 blijft Urgent. De urgente leesincidentketen MET-42/43/44 loopt door. Nieuwe functies die dezelfde bottleneck belasten volgen op het gerichte herstel. Geen einddatum of berekend kritisch pad zonder duur-/resourcegegevens.

**Eerstvolgende uitvoering:** lever onder #729/MET-36 de native baseline van één bronuitsluiting met gelijktijdige mutatie op een ander document, GET en signin, en de drie schaalassen. Dit document start die coding-run niet.

Gebruikersopdracht: herontwerp vastleggen, inclusief GitHub als onmisbare bron bij cruciale stappen. Technische D1-wijziging, implementatie, merge, deploy en productiecutover volgen hun bestaande afzonderlijke contracten.
