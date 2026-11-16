# #1091 / MET-106 — selectiebegeleiding in de bestaande annotatiekaart

Change class: B
Promise: De medewerker krijgt bij bronselectie korte uitleg en contrastvoorbeelden om één afzonderlijk te beoordelen uitspraak met noodzakelijke context te onderscheiden van andere broninhoud.
Proof: Bestaande browserroute met toetsenbordhulp, controle op ongewijzigde opgeslagen annotaties en desktop-/mobiele weergave; gerichte annotatie- en materialisatietests.
Touches lifecycle invariants: no
Rewrite risk: none

## Besluiten en scope

GO gebruiker, 16 november 2026: “Pak dit op en start implementatie”, met verwijzing
naar #1091, ontwerp in PR #1092 en MET-106. Dit verzoek autoriseert deze minimale
UI-slice ondanks de oudere design-only-status en ontbrekend ready-for-agent-label.
Geen merge of deployment. De gebruikersproef uit het ontwerp is niet uitgevoerd;
dit is geen bewijs van kwaliteitswinst of volledige gebruikersacceptatie.

Ontwerpbron: `docs/ko-selection-guidance-1091` op
`dd843e3a9561f10f6f853a09ea07f45e7471333a`, PR #1092.
Implementatiebasis: main `9245b3bfe8d0bd7338a77bd67afce8d51fd5d53d`.

## Gebruik en bestaande werking

1. De medewerker opent de bron: de bestaande introductie legt de inhoudelijke
   selectie uit voordat tekst is aangewezen.
2. De medewerker wijst brontekst aan en opent `?` bij Uitspraak: uitleg over
   betekenisgrenzen, contrasterende fictieve voorbeelden en omgaan met twijfel.
3. Bij Hoort erbij of Onderbouwing opent dezelfde bestaande hulp de uitleg over
   noodzakelijke context of bewijs. Sluiten en opnieuw openen wijzigt geen selectie.

`human_annotation_ui_v1.py` rendert de bronroute en introductie;
`human_annotation_editor.js::renderRows` projecteert `HELP` als tekst/alinea's en
lijsten. `helpOpen: Set<string>` bezit alleen vluchtige open-/sluitstatus per tab.
De bestaande `bindRange -> change/flush -> human_annotation_v1.save` blijft eigenaar
van bronselecties; preview inspecteert en `materialise_knowledge_candidates` blijft
de enige kandidaatmaker. Alleen presentatietekst verandert, geen signatures,
typecontract, schrijvers, opslag, review, publicatie, status of CAS-regels.

## Keuze en afweging

Twee alternatieven beoordeeld door dezelfde agent, geen onafhankelijke reviews:

| Vorm | Aansluiting | Extra belasting | Eigenaarschap |
| --- | --- | --- | --- |
| A: bestaande introductie en HELP-teksten | Bestaande renderfunctie en toegankelijkheidsattributen | Eén korte aanwijzing, details op verzoek | Alleen bestaande vluchtige UI-state |
| B: apart beslisformulier vóór selectie | Nieuwe interactie en validatie nodig | Verplichte extra keuzes | Nieuwe antwoorden en synchronisatie met selectie |

Keuze A volgt het ontwerp en voorkomt een tweede annotatieworkflow. We accepteren
dat de hulp geen inhoudelijke grens afdwingt in ruil voor behoud van menselijke
keuze en de bestaande werkwijze. Geen nieuwe abstracties, dode-codeverwijdering
of scaffolding nodig. Eerst copy aanpassen, daarna bestaande browserproef
uitbreiden en relevante regressiecontroles uitvoeren. Bij tegenstrijdige regels
eerst de copy herzien; geen nieuwe beslislogica toevoegen.

## Bewijsgrens

De browserproef kan tonen dat hulp leesbaar en bedienbaar is en opgeslagen werk
ongemoeid laat. Alleen een vergelijkende proef met 5–8 medewerkers en vooraf
beoordeelde broncasussen kan de semantische kwaliteitswinst beoordelen. De zes
synthetische contrasten uit het ontwerp zijn uitleg, geen nieuwe objecttaxonomie.
Onzekere broninhoud blijft onder de bestaande documentcontrole vallen.

## Technische verificatie en overdracht

Geteste implementatie: `ab7fd8047aee8fd69175070f7cbcedcdcd24a151`.
De daaropvolgende documentatiecommit verandert geen productcode of tests.
`main` is daarna tot `95e79197f3ba05b5073ad3ed2356f4202318155b` geïntegreerd:
de gemergde KO-definitie uit #1090 past bij deze UI-uitleg. De drie nieuwe
protocolcontroles en zes architectuurcontroles zijn aanvullend geslaagd
([JUnit](../../evidence/1091/main-integration.xml)).

- Gerichte regressie: 46 passed, inclusief de echte browserroute.
- Laatste browserrun: 1 passed; desktop en mobiel bekeken.
- Repositorypreflight, release-controlpreflight op alle gewijzigde paden,
  Python-compilatie, architectuurgrenzen en JavaScript-syntax: PASS.
- [Bewijs en schermbeelden](../../evidence/1091/README.md).
- Volledige suite: **loopt nog**, met de bestaande vierdelige CI-verdeling via
  `scripts/measure_test_suite.py`; resultaten onder
  `/workspace/metis-test-tools/shards/`. Niet als PASS of voltooiing meetellen.
  De eerdere seriële run is vervangen door deze complete CI-verdeling nadat
  het ontbrekende `psql`-zoekpad is hersteld.
- Bekende omgevingsfout in de brede suite: de TLS-proef kan de lokale testserver
  niet starten met `SSL is not supported by this build`. Geïsoleerd
  gereproduceerd; een PostgreSQL-build met OpenSSL is gestart onder
  `/workspace/metis-test-tools/pg16-tls`. Nog geen geslaagde TLS-proef geclaimd.

Volgende stap: vier suite-uitkomsten beoordelen en combineren met
`scripts/ci_test_shards.py merge`, daarna inhoudelijke review en de vergelijkende
medewerkersproef. MET-106 blijft In Progress; geen merge of deployment uitgevoerd.
