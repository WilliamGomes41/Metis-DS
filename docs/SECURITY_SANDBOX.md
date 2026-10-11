# Metis beveiligingssandbox

Een aparte Codespace voor beveiligingstests op de huidige Metis-code. Er worden
geen productiegegevens, Azure-resources of bestaande accounts gebruikt.

## Starten

1. Open de sandboxbranch in GitHub en kies **Code → Codespaces → Create codespace**.
2. Wacht tot de installatie klaar is.
3. Start de beveiligingstests in de terminal:

   ```bash
   .venv/bin/python scripts/security_sandbox.py test
   ```

   Dit gebruikt uitsluitend de meegeleverde testdatabase. Is die niet bereikbaar,
   dan stopt het commando vóór de tests. Rapporten staan onder
   `output/runtime/security-sandbox/`. Een mislukte test blijft een mislukte test.

4. Start de webomgeving voor handmatige tests:

   ```bash
   .venv/bin/python scripts/security_sandbox.py serve
   ```

   Open de getoonde HTTPS-link. Het startcommando zet poort 8000 expliciet op
   **Private** en stopt als dat niet lukt. Controleer dit ook in het tabblad
   **Ports**. Andere poorten worden niet automatisch doorgestuurd.

5. Bekijk de vier willekeurig aangemaakte testwachtwoorden:

   ```bash
   cat output/runtime/security-sandbox/accounts.json
   ```

   Er zijn twee onderzoekers, één reviewer en één publisher, ieder met één rol.
   Test bijvoorbeeld toegang tot elkaars documenten, verwerking door een reviewer,
   verlopen sessies en handelingen zonder aanmelding. Gebruik alleen zelfgemaakte
   testdocumenten. De bestaande tests maken daarnaast hun eigen synthetische fixtures.

## Wat wordt gecontroleerd?

| Testgroep | Bewijs |
|---|---|
| URL-invoer en sessies | SSRF, redirects/DNS-rebinding, omvangslimieten, verlopen sessies en cookie-eigenschappen |
| Verwerkingsbevoegdheden | Afwijzing via HTTP, CLI, kernel en dispatcher; behoud van toestand bij afwijzing |
| Product API en MCP | Scopes, documentrechten, tokenvalidatie en leesgrenzen |
| Microsoft-aanmelding | Bestaande contracttests met synthetische identiteiten; geen echte Microsoft-login |
| PostgreSQL | API-credentials, accountintrekking en gelijktijdige workflowmutaties via bestaande tests |

De database draait op een intern Docker-netwerk, zonder gepubliceerde databasepoort.
De testgebruiker heeft ruime rechten omdat de bestaande tests schema's en triggers
aanmaken. Dit zijn geen productiecredentials of een bewijs voor minimale databaserechten.
Het testcommando weigert een afwijkende `METIS_TEST_POSTGRES_DSN`.

De webomgeving gebruikt de bestaande lokale console-opslag. PostgreSQL wordt in
de automatische tests gebruikt. Deze sandbox bootst dus niet de volledige
Azure-opslag, managed identity, Microsoft OAuth, TLS-proxy of productieconfiguratie na.
De applicatie krijgt geen overgenomen database-, Azure-, Microsoft- of AI-credentials.
De ontwikkelterminal zelf behoudt de gebruikelijke Codespaces-toegang tot GitHub;
dit is geen omgeving om willekeurige malware te isoleren. Uitgaand internet voor
de ontwikkelcontainer blijft beschikbaar. Testdoelen zijn uitsluitend deze sandbox.

## Zonder database, stoppen en opnieuw beginnen

Voor alleen lokale contracttests:

```bash
.venv/bin/python scripts/security_sandbox.py test --local
```

Dit levert geen PostgreSQL-bewijs. `Ctrl+C` stopt de webserver. Stop de Codespace
via GitHub als je klaar bent; verwijderen verwijdert ook de sandbox en zijn
testgegevens. Begin met een nieuwe Codespace voor een volledig schone testomgeving.
Codespaces-gebruik valt onder je eigen GitHub-tegoed en eventuele facturering.

Geslaagde tests betekenen dat de geteste scenario's op deze codeversie slagen.
Ze zijn geen algemene verklaring dat Metis of de liveomgeving veilig is.
