# Metis beveiligingssandbox

Een offline Codespace voor lokale scans en automatische beveiligingstests van
Metis. Gebruik alleen synthetische fixtures en zelfgemaakte testdocumenten.

## Starten

1. Open de sandboxbranch in GitHub en kies **Code → Codespaces → Create codespace**.
   Heb je al een oudere sandbox gestart, kies dan **Rebuild Container** of maak
   een nieuwe Codespace: alleen bestanden bijwerken verandert het netwerk niet.
2. Wacht op de containerbuild. De build downloadt de Python-dependencies, Bandit
   en Semgrep. De editor draait in de `workspace`-container (met internet, nodig
   voor de Codespaces-agent). Tests en scans draaien in de aparte
   `runner`-container, die alleen het interne netwerk heeft. Vanuit de editor
   geef je opdrachten door met `scripts/sandbox_test.sh`; dat script legt een
   opdracht in `output/runtime/sandbox-runner/` die de runner uitvoert. Er is
   geen Docker-socket en geen docker-in-docker.
3. Controleer eerst de grens (in de runner):

   ```bash
   scripts/sandbox_test.sh check
   scripts/sandbox_test.sh probe   # DNS/HTTP naar buiten faalt, sandbox-db bereikbaar
   ```

   Het commando weigert externe/default IPv4- of IPv6-routes. Daarna moet een
   TCP-probe naar een publiek adres expliciet `network/host unreachable` melden.
   Een time-out is onvoldoende bewijs. Bij een fout: niet testen; controleer
   of de juiste containerconfiguratie daadwerkelijk draait.
4. Voer de beveiligingstests uit:

   ```bash
   scripts/sandbox_test.sh test
   ```

   De testdatabase moet bereikbaar zijn en de verwachte databasenaam hebben.
   Anders stopt het commando vóór pytest. Rapporten staan onder
   `output/runtime/security-sandbox/`. Overgeslagen tests blijven herkenbaar.
5. Voer de lokale scans uit:

   ```bash
   scripts/sandbox_test.sh scan
   ```

   Bandit en Semgrep schrijven JSON-rapporten in dezelfde runtime-map. Semgrep
   gebruikt uitsluitend de meegeleverde lokale regels, met metrics en
   versiecontrole uitgeschakeld. Bevindingen of toolfouten geven een niet-nul
   exitcode; controleer het rapport om die twee te onderscheiden. Een statisch
   patroon is een onderzoeksvraag, geen aangetoonde kwetsbaarheid.

Voor tests zonder PostgreSQL gebruik je `test --local`. Dit slaat alleen de
PostgreSQL-testgroep over; de netwerkcontrole blijft verplicht.

## Wat wordt gecontroleerd?

| Testgroep | Bewijs |
|---|---|
| URL-invoer en sessies | SSRF, redirects/DNS-rebinding, omvangslimieten, verlopen sessies en cookie-eigenschappen |
| Verwerkingsbevoegdheden | Afwijzing via HTTP, CLI, kernel en dispatcher; behoud van toestand bij afwijzing |
| Product API en MCP | Scopes, documentrechten, tokenvalidatie en leesgrenzen |
| Microsoft-aanmelding | Bestaande tests met synthetische identiteiten; geen echte Microsoft-login |
| PostgreSQL | API-credentials, accountintrekking en gelijktijdige workflowmutaties via bestaande tests |

De tests maken eigen accounts en bronfixtures. Er is geen doorgestuurde webpoort
of apart `serve`-commando. HTTP-scenario's draaien binnen de bestaande testclients
of lokale fixture-servers. De skill staat in
`.agents/skills/metis-vuln-discovery/SKILL.md`; een agent kan die lokaal lezen.
Installatie in de repository betekent niet automatisch installatie in ChatGPT.

## Grens en beperkingen

De `runner` en `sandbox-db` zijn uitsluitend aangesloten op één intern
Docker-netwerk (`172.30.254.0/24`), zonder gepubliceerde poorten. De runner heeft
geen Docker-socket, laat geen nieuwe privileges toe, krijgt geen
Linux-capabilities en heeft een alleen-lezen rootbestandssysteem (alleen de
repository-mount en tmpfs zijn schrijfbaar). De `workspace`-container (editor)
heeft wél internet en zit ook op het interne netwerk; voer daar geen
dynamische tests uit: `security_sandbox.py check` weigert daar terecht.
De runner voert alleen `check`, `probe`, `test`, `test --local`, `scan` en `rt` uit.
`rt` voert willekeurige pytest-bestanden uit die de workspace in
`output/runtime/sandbox-runner/rt/` zet: dit is onvertrouwde code. `rt` MOET
eerst `assert_isolated_network()` in dezelfde job passeren en draait met dezelfde
env-allowlist als `test` (sandbox-DSN, geen geërfde secrets). De jobmap is
schrijfbaar voor de geteste code zelf; de uitkomst (`.log`/`.exit`) van een
`rt`-job MAG NIET als onvervalsbaar bewijs gelden (zie open vraag over
control-bestanden in PR #605).
PostgreSQL is bereikbaar binnen dit netwerk. Zijn testgebruiker heeft ruime
rechten voor de bestaande schema-/triggertests; dit bewijst geen minimale
productiedatabaserechten. Een afwijkende `METIS_TEST_POSTGRES_DSN` wordt geweigerd.

De runner geeft testprocessen geen geërfde Azure-, Microsoft-, AI- of
GitHub-credentials. De editor/host kan nog Codespaces- en GitHub-toegang hebben;
het routebewijs geldt voor de Linux-netwerknamespace van de testcontainer.
Interne Docker-netwerken zijn geen bewijs van absolute isolatie van de host.
Dit is geen omgeving voor willekeurige malware of een container-escape-onderzoek.
Mount geen productiecredentials, bronbestanden of aanvullende netwerk/socket-mounts.

Tijdens de build is internet nodig voor images en pakketten. Na de build kunnen
scanners geen cloudregels, kwetsbaarheidsfeeds of agentdiensten ophalen. Daarom
is er geen Safety/cloud-audit of agent-CLI die een externe modeldienst nodig heeft.
Je kunt een agent buiten de testcontainer laten adviseren op de code; dynamische
uitvoering hoort uitsluitend binnen de gecontroleerde sandbox. De lokale
Semgrep-regels zijn een beperkte aanvulling op Bandit en handmatig codeonderzoek.

De sandbox bootst Azure-opslag, managed identity, echte Microsoft OAuth en
productie-TLS/proxyconfiguratie niet na. Docker/Codespaces-start en de echte
netwerkblokkade moeten op de Codespace worden geverifieerd; alleen configuratie-
inspectie of unit tests bewijzen dat niet. Voeg nooit een extern netwerk toe aan
de runner om alsnog PoC's te draaien.

Stop de Codespace via GitHub als je klaar bent. Een nieuwe Codespace geeft een
schone testomgeving. Het gebruik valt onder je GitHub-tegoed en eventuele
facturering. Geslaagde tests bewijzen de geteste scenario's op die codeversie,
niet dat Metis of de liveomgeving in algemene zin veilig is.
