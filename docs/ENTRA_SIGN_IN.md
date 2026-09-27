# Microsoft-aanmelding voor Metis — vastgelegd besluit (#434)

Status: implementatie in GitHub; Azure-configuratie en deployment volgen apart.

## Gebruikersbelofte en domein

Gebruikers melden zich aan met hun Microsoft-werkaccount. Er is geen nieuw
Metis-wachtwoord en geen open registratie. Entra bepaalt toegang en app-rollen;
Metis bewaart de vaste revieweridentiteit en kan toegang aanvullend blokkeren.
Een e-mailadres, weergavenaam of door de browser aangeleverde header bewijst nooit
welk bestaand account bij iemand hoort. De sleutel is `(tenant_id, object_id)`.
Bestaande account-ID's, reviewerbindingen, besluiten en publicaties veranderen niet.

Stateful Class B, rewrite risk high: de gedeelde authenticatiegrens wijzigt,
publicatie-/documentlifecycle niet. Het volledige contract staat in issue #434.

## Gedrag

- `METIS_CONSOLE_AUTH=local` (standaard): bestaand gedrag, ook vóór Azure-inrichting.
- `METIS_CONSOLE_AUTH=entra`: alleen Microsoft-aanmelding; oude wachtwoordroutes,
  accountaanmaak en lokale roltoekenning worden geweigerd, inclusief directe
  aanroepen van de bestaande consolemethoden. Bootstrapaccounts worden overgeslagen.
- Alleen de geconfigureerde tenant, client/audience, issuer en herkende app-rollen
  geven toegang. De gebruikelijke Entra-gastidentiteit in deze tenant kan ook werken.
- Eerste toegestane aanmelding maakt profiel, koppeling en sessie in één
  PostgreSQL-transactie. Bestaande koppelingen behouden hun account-ID.
- Rollen komen uit het gevalideerde ID-token: `Metis.Researcher`, `Metis.Reviewer`,
  `Metis.Publisher`. Andere rollen geven geen toegang. Bij een rolwijziging worden
  oudere sessies ingetrokken. De getoonde rollen zijn laatst waargenomen rollen.
- Een publisher kan via **Instellingen → Accounts** een andere gebruiker direct
  blokkeren. Elke volgende aanvraag controleert de blokkering in PostgreSQL.
  Eigen toegang blokkeren is uitgesloten om onbedoelde zelfuitsluiting te voorkomen.
  Opheffen van een blokkering geeft geen extra rol en herstelt geen oude sessie.
- De sessie is absoluut maximaal vijf minuten geldig (ook als de browsercookie
  langer wordt bewaard). Daarna is een nieuwe Microsoft-aanmelding vereist.
  Bij navigatie gaat dit automatisch en keer je terug naar de gevraagde Metis-pagina.
  Een bestaande Microsoft-SSO-sessie kan daarbij de wachtwoordstap overslaan.
  Onverwerkte POSTs worden nooit automatisch opnieuw uitgevoerd.
- Verwijderen van een Entra-toewijzing werkt bij de volgende autorisatie, onder
  voorbehoud van Microsofts propagatietijd. Entra kan onze bestaande sessie niet
  rechtstreeks intrekken. Gebruik **Toegang direct blokkeren** voor onmiddellijke
  afsluiting; dit is een noodstop, geen tweede systeem om toegang te verlenen.
- Logout trekt de lokale sessie in en opent de tenantspecifieke Microsoft-logout.

## Vertrouwensgrenzen, fouten en transacties

MSAL doet de authorization-code-flow met PKCE, state en nonce. Metis gebruikt
alleen de server-to-server uitgewisselde claims, geen browser-ID-token of
`X-MS-CLIENT-PRINCIPAL`-header. De callback is een GET met `response_mode=query`,
waardoor de bestaande Origin-controle voor wijzigingsverzoeken niet wordt uitgezet.
De redirect-URI komt uitsluitend uit `CONSOLE_PUBLIC_ORIGIN`, nooit uit Host-headers.

Een Secure/HttpOnly/SameSite=Lax `__Host-` cookie bindt de browser aan een
kortdurende flow in PostgreSQL. De flow wordt atomisch en eenmalig verbruikt vóór
externe tokenuitwisseling. Een fout betekent opnieuw beginnen. Verlopen flows
worden verwijderd bij een nieuwe aanvraag; maximaal 1.000 actieve flows beperken
opslag. De centrale identity-lock beschermt zeldzame mutaties en dubbel provisioneren.
Alle account-/rol-/sessieschrijfacties van een aanmelding delen één SQL-transactie.
Blokkering, auditbewijs en sessie-intrekking delen eveneens één transactie.

Bij ongeldige configuratie, ontbrekende migratie of onvolledige oude-accountkoppeling
start Entra-modus niet. Een storing geeft nooit lokale wachtwoordtoegang terug.
Geen refresh/access/ID-token wordt opgeslagen. Alleen tijdelijk het handshake-object
(inclusief PKCE-verifier), gehashte sessiesleutels en identiteitsmetadata. Handshake-
fouten tonen geen token, code, secret of ruwe Microsoft-fouttekst.

## Opslag, herstart en herstel

Migratie `012_console_entra_identity.sql` voegt drie tabellen toe:

| Tabel | Verantwoordelijkheid | Herstel |
|---|---|---|
| `workflow.entra_identities` | Unieke accountkoppeling, blokkering en wijzigingsbewijs | In volledige workflowbackup |
| `workflow.entra_sessions` | Bewijs dat een bestaande sessie via Entra is gemaakt | Niet terugzetten; opnieuw aanmelden |
| `workflow.entra_flows` | Tijdelijke eenmalige handshake | Niet terugzetten; opnieuw beginnen |

De bestaande `workflow.accounts` en `workflow.sessions` blijven de account- en
sessieopslag. Geen lokale JSON-bestanden of tweede accountstore. Geen nieuwe jobs.
Na gewone herstart blijft een nog geldige sessie maximaal de resterende vijf
minuten bruikbaar. Na backup/herstel is verse Microsoft-aanmelding verplicht.
Een backup met Entra-koppelingen mag niet zonder tabel 012 worden hersteld.
Oude backups zonder Entra-koppelingen blijven leesbaar; vóór activering moeten
alle bestaande accounts opnieuw expliciet gekoppeld en blokkeringen gecontroleerd
worden. Een rollback/herstel wordt offline uitgevoerd volgens het bestaande runbook.

## Later uitvoeren in Azure — nu niets gewijzigd

1. Maak een **single-tenant appregistratie** voor Metis in de V&VN-tenant.
   Voeg als **Web** redirect-URI toe: `https://metis.venvn.nl/auth/microsoft/callback`.
   Gebruik uitsluitend de werkelijke HTTPS-origin van de betreffende omgeving.
   Implicit grant hoeft niet aan. Metis vraagt geen Graph-brede lees-/schrijfrechten.
2. Definieer drie gebruikersrollen met exacte waarden `Metis.Researcher`,
   `Metis.Reviewer`, `Metis.Publisher`. Bij de bijbehorende **Bedrijfsapplicatie →
   Eigenschappen** zet je **Toewijzing vereist** op **Ja**. Wijs personen en rollen
   toe via **Gebruikers en groepen**. MFA/Conditional Access blijft V&VN-beleid.
   De application permission voor Azure-beheer is niet nodig.
3. Controleer samen met de beheerder de koppeling van **elk bestaand Metis-account**
   naar het Entra-object-ID van dezelfde persoon. Ook voor gasten wordt het object-ID
   in de V&VN-tenant gebruikt. Geen e-mailmatching. Houd bestaande namen/IDs intact.
4. Laat de DBA migratie 012 toepassen met de bestaande gecontroleerde migratietool
   `scripts/apply_workflow_postgres_migrations.py` (plan/digest vóór toepassen).
   Verleen de runtime de benodigde SELECT/INSERT/UPDATE/DELETE-rechten op deze drie
   tabellen. Geen DDL- of tenantbeheerrechten voor de applicatie.
5. Zet in **App Service vvn-metis-console → Omgevingsvariabelen**:

| Naam | Waarde |
|---|---|
| `METIS_CONSOLE_AUTH` | `entra` — pas als alle voorbereiding gereed is |
| `METIS_ENTRA_TENANT_ID` | Directory/tenant-ID van V&VN |
| `METIS_ENTRA_CLIENT_ID` | Application/client-ID van de appregistratie |
| `METIS_ENTRA_CLIENT_SECRET` | Secret **waarde**, bij voorkeur via Key Vault-reference |
| `CONSOLE_PUBLIC_ORIGIN` | `https://metis.venvn.nl` |
| `METIS_WORKFLOW_STORE` | `postgres` (bestaande identity-store) |
| `METIS_ENTRA_ACCOUNT_BINDINGS_JSON` | JSON-object: `{"<Entra-object-ID>":"<bestaand acc-ID>"}` |

De secret hoort nooit in GitHub, een ZIP of een gesprek. Koppelingen worden bij
start in één transactie gevalideerd/opgeslagen. Ontbrekende of tegenstrijdige
koppelingen blokkeren de omschakeling; herstel configuratie en start opnieuw.
Bij een lege database kan de eerste toegewezen Microsoft-gebruiker direct starten.

6. Voer de omschakeling uit met de console gestopt; laat geen oude lokale-loginworker
   naast een Entra-worker draaien. Start daarna de nieuwe configuratie.
   Test met twee verschillende echte gebruikers: toegestaan, niet toegewezen,
   verschillende rollen, logout, gast indien nodig, sessieverloop, directe blokkering,
   juiste historische reviewer-ID en herstart. Deze live tests blijven open tot Azure
   is ingericht. Stem eventuele bestaande App Service Authentication af: de app doet
   zelf OIDC en vertrouwt geen Easy Auth-header als alternatief.
7. Verwijder oude bootstrapwachtwoorden uit de App Service-configuratie na bewezen
   omschakeling. De code negeert ze in Entra-modus; productie wordt nu niet gewijzigd.

Rollback is een bewuste beheerhandeling: zet `METIS_CONSOLE_AUTH=local` terug,
herstart en controleer wie via de bestaande lokale wachtwoorden toegang heeft.
Blokkeringen van Entra gelden niet als lokale wachtwoordautorisatie; rollback is
dus geen automatische herstelactie. Oude lokale sessies zijn bij de cutover
ingetrokken; verwijder ook resterende sessies bij een bewuste rollback.

## Bewijs en resterende grens

`tests/test_console_entra_v1.py` controleert toelating, ontbrekende rechten,
verkeerde tenant/audience/issuer, browserbinding/state/replay, legacy-sessies,
rolwijziging, blokkering, concurrency, restart en herstel. De Microsoft-uitwisseling
wordt in applicatietests vervangen; aanvullende protocoltests oefenen echte MSAL
met gesimuleerde HTTP-responses. Native PostgreSQL in CI is vereist; een lokale
PostgreSQL-compatibele testserver is aanvullend, geen concurrencybewijs.

Officiële achtergrond:
- https://learn.microsoft.com/en-us/entra/identity-platform/howto-restrict-your-app-to-a-set-of-users
- https://learn.microsoft.com/en-us/entra/msal/python/getting-started/acquiring-tokens
- https://learn.microsoft.com/en-us/entra/identity/users/users-revoke-access

## Afzonderlijke adversariële review

De tweede reviewpass controleert de omzeilingen, niet alleen de happy path:

- Alle geïnstalleerde review-, audit-, herstel- en publicatieroutes gebruiken
  `console.session_account`; de vervangen grens geldt dus ook buiten het basisscherm.
- Lokale login, accountaanmaak, rolwijziging en bootstrap zijn alternatieve writers:
  geblokkeerd/overgeslagen in Entra-modus. Oude cookies missen de SQL-sessiemarker.
- Microsoft-headers en e-mailnamen leveren geen autoriteit. Tokens komen uitsluitend
  uit MSAL's uitwisseling met de geconfigureerde tenant. Geen publieke JWT-invoer.
- Twee gelijktijdige eerste aanmeldingen moeten dezelfde account-ID krijgen; een
  fout bij sessieschrijven moet account/koppeling/rolwijziging terugrollen.
- Blokkeren en aanmelding gebruiken dezelfde SQL-lock. Blokkering wint voor volgende
  aanvragen; eerder begonnen inhoudelijke transacties worden niet geannuleerd.
- Expiry wordt server-side gelezen, inclusief een absolute bovengrens; wijziging
  van de cookie of de opslagduur kan de vijf minuten niet verlengen.
- Restore bewaart koppeling, blokkering en bewijs, maar geen tijdelijke flows of
  Entra-sessiemarkers. Verkeerde tenant/ontbrekende schema/incomplete mapping faalt.
- Rollback is expliciet en offline: lokaal wachtwoordbeheer krijgt nooit door een
  Microsoft-/databasefout automatisch de autoriteit terug.
- De GET-callback gebruikt no-store/no-referrer en eenmalige browserbinding + PKCE.
  Azure/proxy access logging moet later querywaarden van deze callback redigeren:
  autorisatiecodes horen niet in gedeelde logs (ook al zijn ze kortdurend en gebonden).

Open acceptatie blijft echte Microsoft-/Azure-integratie: appregistratie, rolclaims,
MFA, gasten, beheerrechten, secretbeheer, logging en propagatie bij intrekking.
