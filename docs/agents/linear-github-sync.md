# Permanente GitHub–Linear-bewaking bedienen

Eigendom: repository `WilliamGomes41/Metis-DS`, team MET. Opdracht:
[GitHub #963](https://github.com/WilliamGomes41/Metis-DS/issues/963), MET-47.
Deze bestanden blijven in GitHub wanneer een chat wordt verwijderd. **Een open
PR is nog geen actieve workflow.**

## Wat werkelijk automatisch gaat

Na activering leest GitHub Actions alle pagina's van de repository-PR's en de
expliciet gekoppelde GitHub-issues/comments. Per binding leest hij het bestaande
MET-issue en alle commentpagina's. Hij maakt of wijzigt één comment met marker
`metis-github-linear-sync-v1`. Bij gelijke betekenisvolle feiten schrijft hij
niets. Bij een gedeeltelijk mislukte run blijft de al geschreven projectie
staan; een volgende run leest eerst terug en maakt geen blinde duplicate.

De bronnen tonen GitHub-open/closed, PR-open/closed/merged, exacte head en de
laatste expliciete overdracht van een OWNER/MEMBER/COLLABORATOR. CI-, deployment-
en gebruikersacceptatie worden niet verzonnen of zelfstandig goedgekeurd.
De aanwezigheid van JSON of een digest bewijst geen inhoudelijke correctheid.

De werkkeuze en alle bestuurlijke issue-/projectvelden blijven menselijk
eigendom. Een expliciet resterend werkpakket op een actuele PR-head naast Done
geeft een falende run; een open GitHub-issue op zichzelf is geen bewijs van een
onterechte Linear-status. Handmatig beoordeling en eventuele correctie blijven
nodig. De worker bevat geen issueUpdate-/projectmutaties.

## Activeren — eenmalig door repositorybeheerder

1. Review en merge de implementatie-PR via de bestaande menselijke mergepoort.
   Het ontwerp alleen is geen activering.
2. Maak een beperkte Linear-API-sleutel voor de integratie-identiteit: leesrecht
   op MET en schrijfrecht voor de noodzakelijke comments. Geef die identiteit
   geen onnodige toegang tot andere teams. Sla de waarde uitsluitend op als
   repositorysecret `LINEAR_API_KEY` in GitHub **Settings → Secrets and variables
   → Actions**. Niet in chat, issues, bestanden of workflowlogs plakken.
3. Controleer GitHub Actions-toegang. Het ingebouwde `GITHUB_TOKEN` heeft alleen
   `contents: read`, `issues: read` en `pull-requests: read`; GitHub-write of
   productiesleutels zijn niet nodig. Het token voor ChatGPT's connector is niet
   beschikbaar in GitHub Actions en wordt niet geëxporteerd.
4. Open **Actions → GitHub Linear sync → Run workflow**, op main. Bij ontbrekende
   sleutel of API-fout moet de job rood worden; groen zonder verbinding is niet
   toegestaan. Bekijk elke afwijking vóór verdergaan. De workflow moet al op main
   staan voordat events of de periodieke controle een blijvende voorziening zijn.
5. Lees de gemaakte comments in Linear terug. Noteer de echte run-URL en main-SHA
   op #963/MET-47; controleer minstens één open werkpakket en één gemergde
   deelslice. Een tweede ongewijzigde run moet nul changes tonen en exact één
   eigen comment behouden. Controleer dat status/werkkeuze/eigenaar behouden zijn.
6. Maak **handoff-contract** (workflow **GitHub Linear sync**) een vereiste PR-check in de
   bestaande branch ruleset, als menselijke review dat passend vindt. Zonder
   vereiste branchcheck is een rode check zichtbaar, maar geen bewezen
   onomzeilbare mergeblokkade. Bestaande vereiste checks niet vervangen.
7. Schakel pas na deze geverifieerde live run de tijdelijke ChatGPT-taak
   **Bewaak GitHub en Linear** uit. Dit voorkomt dubbele primaire bewaking en
   afhankelijkheid van een chat. Publiceer geen geheime sleutel als bewijs.

De workflow reageert op PR-/issue-/commentgebeurtenissen en heeft een herstelrun
op minuut 17 van ieder uur. GitHub bepaalt uitvoering en wachtrijen; dit is geen
realtime- of ononderbroken-servicegarantie. Bekijk Actions-notificaties en
runhistorie voor falen of uitgeschakelde schedules.

## Nieuwe koppeling en overdracht

Voeg uitsluitend een unieke eigen GitHub-opdracht en het bestaande Linear-ID toe
aan `config/linear_github_sync.v1.json`. De configuratie bevat alleen identiteit;
geen prioriteit, status of volgende stap. `--check-config` weigert dubbele en
vreemde team-/repositorykoppelingen. De aanvankelijke 37 koppelingen zijn op het
bestaande bord gegrond. MET-9/10/11/12 delen register #877, MET-37 heeft een
D2-trigger zonder unieke eigen GitHub-opdracht, en MET-38 is een incident naast
de bestaande uitvoeringsissues: zij worden niet als tweede owner voor dezelfde
GitHub-opdracht gekoppeld. Maak daarvoor geen duplicaatwerk alleen om een lijst
volledig te laten lijken.

Gebruik het compacte PR-blok uit de canonieke
[handoff-afspraken](linear-github-handoff.md). Een repositorycollaborator kan een
nieuwe expliciete overdracht ook als GitHub-issuecomment vastleggen; de nieuwste
geldige collaboratorcomment gaat vóór een oudere PR-overdracht. Losse comments
van onbekende publieke deelnemers bepalen geen volgende stap. Historische
machineblokken met een oude head zijn geen actuele voltooiingsbeslissing.

## Veiligheid en herstel

De privileged job checkt **uitsluitend main** uit en voert geen code van een PR
uit, ook niet bij pull_request_target. Eventtekst wordt niet in shellcommando's
geïnterpoleerd. De PR-testjob krijgt geen Linear-secret. De integratie volgt geen
HTTP-redirects met autorisatieheaders en toont geen ruwe API-foutbody's.

Eén Actions-concurrencygroep serialiseert eigen runs. Externe schrijvers kunnen
nog tegelijk werken; de worker herleest vóór iedere wijziging en stopt bij
zichtbaar conflict. Er is geen atomische compare-and-swap of cross-service
transactie. Een wissel van Linear-integratie-identiteit vereist beoordeling van
het eigendom van bestaande synchronisatiecomments; die worden niet stil gekaapt.

Bij falen: bekijk het veilige foutbericht en het bron-/doelissue, herstel
toegang of mapping, en voer opnieuw uit. Bij meerdere eigen markers: bepaal
handmatig de geldige comment, verwijder alleen het bewezen duplicaat en herhaal.
Nooit productiesleutels resetten of werkpakketten sluiten om een job groen te maken.

Terugdraaien: schakel deze workflow uit in Actions of revert de implementatie
via normale review. Een revert wijzigt geen productiedata of werkpakketstatus.
Bestaande comments zijn historische projecties en kunnen zichtbaar blijven;
verwijder geen menselijk werk of handoffs. Hervat alleen een tijdelijke controle
wanneer die toegang en werking opnieuw zijn aangetoond.

## Bewijsgrens bij oplevering

De lokale tests gebruiken gesimuleerde GitHub-/Linear-transporten en controleren
de werkelijke mutatiesurface, paginering, idempotentie en afwijzing. Zij bewijzen
geen live Linear-API-autorisatie of draaiende GitHub-scheduler. De uitvoering met
de echte sleutel, teruggelezen comments en tweede nulwijzigingsrun is nog vereist.
