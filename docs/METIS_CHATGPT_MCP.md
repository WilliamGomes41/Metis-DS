# Metis rechtstreeks lezen vanuit ChatGPT

Issue #460. Class B. Rewrite risk: none. Geen nieuwe database of domeinmutaties.

## Wat wordt geleverd

De bestaande console biedt `/mcp` en **Instellingen → ChatGPT-koppeling**.
Negen benoemde leesfuncties ontsluiten documenten, passages/bronbewijs, verwerking,
reviewhistorie, versieverschillen, publicatieregister en technische bronaanwezigheid.
Geen SQL, shell, willekeurige URL, download/repair, modelaanroep, review- of publiceercommando.
De Product API en bestaande sessie-/CSRF-grens blijven ongewijzigd.

Standaard uit. Installeren van de code alleen maakt nog geen werkende verbinding.
De status ‘Geconfigureerd’ bewijst geen geslaagde OAuth-/ChatGPT-verbinding.

De gedelegeerde scope heet `Metis.Read2`. Een bestaande app-rol `Metis.Read`
blijft een afzonderlijke rol en wordt niet hernoemd. Deploy eerst de code die
`Metis.Read2` ondersteunt; oudere builds vragen en accepteren nog `Metis.Read`.
Deze scopewijziging vereist geen databasemigratie.

## Eenmalige inrichting door de beheerder

1. Configureer eerst de bestaande Entra-aanmelding volgens `docs/ENTRA_SIGN_IN.md`.
   Deze gebruikt de bestaande PostgreSQL-accounts, Entra-koppelingen en blokkades.
   Lokale wachtwoorden/cookies worden niet geaccepteerd op MCP. De MCP-ingang
   maakt geen accounts of sessies aan: gebruikers moeten eerst in Metis inloggen.
2. Gebruik een single-tenant Entra API-appregistratie (de console-app kan ook dienen
   als API-resource). Stel `requestedAccessTokenVersion` in op **2**. Exposeer
   `api://<API-app-ID>/Metis.Read2` als **delegated permission** en houd de bestaande
   app-rollen `Metis.Researcher`, `Metis.Reviewer`, `Metis.Publisher` aan. Zorg dat
   gebruikers/groepen de passende rollen op deze resource toegewezen krijgen.
3. Registreer een aparte vertrouwelijke OAuth-client voor ChatGPT in dezelfde tenant.
   Geef deze de gedelegeerde API-permissie uit stap 2 en verleen de benodigde consent.
   Gebruik de **exacte redirect-URI die de ChatGPT-koppelingsconfiguratie toont**.
   Configureer de client-ID en het clientgeheim in ChatGPT, niet in prompts of broncode.
   Zorg voor authorization-code/PKCE en refresh-toegang (`offline_access`) waar de
   ChatGPT OAuth-configuratie dit vraagt. Entra verzorgt consent, codes en refresh tokens.
   Metis implementeert geen eigen autorisatieserver of dynamische clientregistratie.
4. Zet bij de bestaande consoledeployment:

   ```text
   METIS_MCP_ENABLED=1
   METIS_MCP_AUDIENCE=<API-app-ID uit stap 2>
   METIS_MCP_CLIENT_ID=<OAuth-client-ID uit stap 3>
   ```

   Gebruik het bestaande vaste HTTPS-origin van de console. Wijzig geen bestaande
   client-ID/secret voor console-login om de ChatGPT-client te configureren.
   Herstart de app. Secrets worden niet op de instellingenpagina weergegeven.
5. Open **Instellingen → ChatGPT-koppeling**. Kopieer het MCP-adres. Voeg in de
   ChatGPT-webwerkruimte een eigen MCP-app toe, met OAuth en de vooraf geregistreerde
   client. De beheerder moet hiervoor de vereiste werkruimterechten hebben.
   Metis publiceert resource metadata op `/.well-known/oauth-protected-resource/mcp`;
   deze verwijst naar de tenantspecifieke Entra v2-issuer en de volledige API-scope.
6. Verbind, scan de tools en test met een toegewezen document. Test ook een andere
   gebruiker zonder toegang. Publiceer de app pas na deze controle in de werkruimte.

De exacte organisatie-/consent- en ChatGPT-inrichting moet op de echte tenant worden
getest. Deze repositorywijziging voert die externe handelingen niet uit.

## Toegang en gegevens

- Iedere aanvraag valideert RS256-handtekening, issuer, tenant, audience, tijd,
  gedelegeerde `Metis.Read2` scope en de toegestane OAuth-client (`azp`). ID tokens,
  app-only tokens, Product API-sleutels en consolecookies geven geen MCP-toegang.
- Het bestaande account moet gekoppeld en niet geblokkeerd zijn. Effectieve rollen
  zijn de doorsnede van tokenrollen en de huidige opgeslagen accountrollen. Verlaagde
  rechten en blokkades worden op de volgende aanvraag toegepast; nieuwe rollen
  vereisen zo nodig een nieuw token/aanmelding.
- Documenten: eigen uploader met researcher-rol, benoemde reviewer met reviewer-rol,
  of publisher. Beide documenten bij een vergelijking worden afzonderlijk getoetst.
- Technische systeem-/opslaggegevens zijn alleen voor publishers.
- Broninhoud, reviewersnamen en toelichtingen worden bij een gerichte aanvraag naar
  ChatGPT verzonden. Operationele secrets en interne opslaglocators worden weggelaten.
  Gewone documenttekst wordt als brondata behandeld, niet als instructie.
- Tabellen `runs`, `semantic_proposals`, `proposal_fields`, `validation_findings`,
  `coverage`, `context_evidence`, `lineage` enz. komen uit dezelfde projector als de
  verwerkingsexport. Niet vastgelegde modelaanroepen blijven ontbrekend.

## Interpretatie

Iedere documentlezing noemt snapshot-ID, bronhash, ophaaltijd en (bij objectlezing)
objects_revision. Een vergelijking bevat beide revisies; dit is geen transactie over
twee documenten. Bij wijziging van een envelope tijdens de objectlezing wordt opnieuw
lezen gevraagd. Paginering is offset/limit (maximaal 50); vergelijk de revisies tussen
pagina's en begin opnieuw als ze verschillen. Zoekresultaten zijn een actuele lijst,
geen bevroren inventaris.

Publicatiegegevens onderscheiden opgeslagen workflowstatus van actieve regels uit het
publicatieregister. Geen preflight, verificatie, herstel of nieuwe publicatiebeslissing.
Opslagcontrole leest uitsluitend blob-properties. `present` bewijst geen inhoudelijke
integriteit; `unavailable` is niet hetzelfde als `absent`. Voor verwijderde documenten
kan een publisher een vastgelegde verwijdergebeurtenis lezen; zonder bronlocator is
fysieke verwijdering daarna niet controleerbaar via deze functie.

## Transport en begrenzing

Stateless JSON Streamable HTTP met stabiele protocolversies 2025-03-26, 2025-06-18 en
2025-11-25. POST voor JSON-RPC; notifications leveren 202 zonder tooluitvoering.
GET/SSE en DELETE/sessies worden niet aangeboden (405); initialize onderhandelt een
ondersteunde versie. Geen session-ID of achtergrondverbinding nodig.

Requests maximaal 16 KiB; toolresultaten maximaal 250 kB vóór MCP-verpakking. Te grote
resultaten geven een expliciete fout met verzoek tot kleinere pagina/objectfilter;
geen stille tekstafkapping. Per worker 300 ingress-aanvragen/minuut en 60 per account.
Dit vervangt geen distributed gateway-rate-limiting. Bestaande stores kunnen intern
een volledige objectset/ledger lezen; paginering begrenst de respons, niet alle DB-I/O.
Responses hebben `Cache-Control: no-store`. De exacte `/mcp`-route gebruikt uitsluitend
bearer-authenticatie en een eigen Origin-controle; overige console-POSTs behouden CSRF.

## Proef en rollback

Vraag in ChatGPT: ‘Zoek Eenzaamheid, lees runs en semantic_proposals en controleer het
vastgelegde verwerkingscontract. Lees daarna proposal_fields van een passage.’
Vergelijk met de bestaande verwerkingsexport. Controleer dat objectrevisies, reviews
en publicaties niet wijzigen. Controleer 401 zonder token, 403 bij een geblokkeerde
identiteit, geen toegang tot niet-toegewezen documenten, en publisher-grenzen.

Uitschakelen: `METIS_MCP_ENABLED=0` en herstart. Daarna retourneert de ingang 503.
Verwijder desgewenst de ChatGPT-app/consent. Geen migratie, backfill of gegevensreset.

Referenties:
- https://developers.openai.com/plugins/build/auth
- https://developers.openai.com/plugins/deploy/connect-chatgpt
- https://modelcontextprotocol.io/specification/2025-11-25/basic/transports
- https://learn.microsoft.com/entra/identity-platform/access-tokens
