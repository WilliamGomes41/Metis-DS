# Ontwerp: de medewerker wijst aan, Metis leidt af, de reviewer bevestigt

Status: **ontwerpvoorstel ter besluit**. Niets hiervan is gebouwd. Onderzocht op
`main` `4c5b776` op 12 november 2026. Aanleiding: William vulde een echte
richtlijnpassage in en liep vast; zie “Aanleiding” onderaan.

Voorlopige classificatie: Class B, `Rewrite risk: high`. Het ontwerp vervangt de
betekenis van de opgeslagen annotatie en de toelatingsregels van een gedeelde
vormingskern; oud en nieuw moeten naast elkaar bestaan. De vijf
lifecycle-invarianten worden niet geraakt. Verandert tijdens uitwerking iets aan
wat review moet afsluiten vóór publicatie, dan wordt dit Class A.

## Doel

Een medewerker wijst brontekst aan. Metis maakt daarvan een kennisobject dat
inhoudelijk klopt, niets weglaat en naar de bron herleidbaar is. Een reviewer
beoordeelt het daarna. De medewerker doet zo min mogelijk.

## Het besluit in één alinea

De medewerker legt alleen vast wat een mens moet beslissen, in de taal van de
bron: **dit is de uitspraak**, **deze tekst hoort erbij om haar te begrijpen**
en **dit is de onderbouwing, of die staat er niet**. Type, zinsdelen, soort
context, richting en sterkte leidt Metis af. Die afleidingen zijn hulp voor de
reviewer en signalen bij twijfel; ze zijn geen velden die de medewerker invult
en ze houden afronden niet tegen.

## Waarom de huidige opzet structureel niet past

| Waarneming in de code | Gevolg |
| --- | --- |
| De annotatie bewaart 18 betekenisvelden, 12 contextrollen, essentialiteit, onderbouwingsfunctie en richting/sterkte (`human_annotation_v1._validate`) | De medewerker vult het controleformulier van het systeem in |
| Onderwerp, gezegde, handeling en “wat wordt toegelicht” worden niet uitgeleverd; retrieval en product-API serveren tekst, bevestigd type, gekoppelde context en bevestigde aanbevelingssemantiek | Velden die alleen de volledigheid van een zin controleren, blokkeren toch het afronden |
| Die velden accepteren alleen woorden uit de kernzin (`source_bound_fields_v3.CONTEXT_FIELDS`) | Een opsommingspunt dat op zijn inleidende zin leunt, is niet af te ronden |
| Het type moet uit een gesloten lijst van vijf komen en bepaalt welke velden verplicht zijn | Een feitelijke uitspraak krijgt een type dat niet past, met vragen die niet passen |
| Alleen een door een mens bevestigd type wordt uitgeleverd (`published_object_type`) | Het type is nu al een reviewbesluit; de medewerker hoeft het niet te kiezen |

## Wie doet wat

| | Medewerker | Metis | Reviewer |
| --- | --- | --- | --- |
| Uitspraak | Wijst aan | Controleert letterlijkheid; signaleert een afgebroken of verwijzende zin | Beoordeelt |
| Tekst die erbij hoort | Wijst aan, of bevestigt een voorstel met één klik | Stelt voor uit de omgeving (inleidende zin, kop, voorwaarde); benoemt de soort | Beoordeelt of het compleet is |
| Onderbouwing | Wijst aan, of kiest “staat niet in de bron” | Stelt een vindplaats voor als die er is | Beoordeelt |
| Type | — | Stelt voor | Bevestigt (bestaand) |
| Richting en sterkte van een aanbeveling | — | Stelt voor met bronbewijs | Bevestigt (bestaand) |
| Zinsdelen | — | Gebruikt ze intern als controle | Ziet alleen een signaal als er iets ontbreekt |

## Wat een annotatie vastlegt

```text
uitspraak:      een of meer exacte bronbereiken
hoort_erbij:    nul of meer exacte bronbereiken
onderbouwing:   exacte bronbereiken | "staat niet in de bron"
status:         concept | klaar | teruggenomen
```

Elk bereik blijft een exacte, onveranderlijke bronpositie met een citaatcontrole,
zoals nu. Afgeleide gegevens (voorgesteld type, soort context, signalen) worden
bij de opbouw berekend en staan niet in de invoer van de medewerker.

## Wat voor de medewerker vervalt

| Nu | Straks |
| --- | --- |
| Type kiezen | Voorstel van Metis; bevestiging bij review |
| 18 betekenisvelden met ontbreekredenen | Vervallen als invoer; interne controle |
| 12 contextrollen | Eén handeling: “hoort erbij”. Metis benoemt de soort |
| “Verandert de betekenis als dit ontbreekt?” | Vervalt: wat de medewerker koppelt, hoort erbij |
| Onderbouwt of verklaart | Vervalt als keuze |
| Richting en sterkte met bronbewijs | Voorstel van Metis; bevestiging bij review |
| Drie stappen, “Aanvullen”, “Beantwoorden” | Eén kaart met drie regels en één afrondknop |

## Wat tegenhoudt en wat alleen signaleert

**Houdt tegen** (blijft hard): een bereik dat niet letterlijk in de vastgelegde
bron staat, een lege uitspraak, dezelfde uitspraak twee keer, een gewijzigde
bron, en een onbeantwoorde onderbouwingskeuze.

**Signaleert** (naar medewerker en reviewer, zonder te blokkeren): de zin lijkt
afgebroken; de uitspraak verwijst naar iets buiten de selectie (“deze”,
“daarbij”, eindigt op een dubbele punt) en er is niets gekoppeld; het type is
onduidelijk; een voorgestelde koppeling is niet bevestigd.

Een signaal is een vraag aan de mens, geen oordeel. De medewerker kan erop
reageren door tekst te koppelen of het zo te laten; de reviewer ziet het.

## De reviewkaart

De kaart houdt haar opbouw en haar drie vragen. Zij toont al de uitspraak, het
type, richting en sterkte, en de gekoppelde context en onderbouwing. Nieuw is
alleen tekst op bestaande plekken: bij het type “voorstel van Metis”, en een
signaal bij de rij waar het over gaat. Geen nieuwe secties, vragen of knoppen.

## De passage van William in dit model

1. Selecteer “Bij diabetes mellitus zou de huid vatbaarder kunnen zijn…”.
2. Metis stelt voor: “Hoort de zin ‘De volgende onderliggende mechanismen spelen
   mogelijk een rol bij het risico op smetten:’ erbij?” Eén klik: ja.
3. Onderbouwing: “staat niet in de bron”.
4. Afronden.

De reviewer ziet de uitspraak, de inleidende zin als context, het voorgestelde
type en geen open vragen. Niemand hoeft te beantwoorden “welke uitspraak wordt
toegelicht”.

## Wat niet verandert

- `materialise_knowledge_candidates` blijft de enige kandidaatmaker; Metis
  stelt voor en schrijft nooit zelf kandidaattekst of identiteit.
- Exacte bronposities, onveranderlijke versies, versiecontrole bij opslaan.
- Alleen een door een mens bevestigd type en bevestigde aanbevelingssemantiek
  worden uitgeleverd. Review- en publicatieregels blijven zoals ze zijn.

## Bestaand werk

- **De kaart uit #1059** wordt vervangen. Zij verbetert het oude formulier en
  heeft in dit model geen functie meer.
- **Bestaande annotaties en kennisobjecten** blijven leesbaar en ongewijzigd; ze
  houden hun eigen contractversie en worden niet hervertaald.
- **Overgang** in stappen: eerst het nieuwe invoercontract en de nieuwe
  toelating naast de oude, dan nieuwe documenten via het nieuwe, dan het oude
  verwijderen. Geen omzetting van opgeslagen werk zonder apart besluit.

## Risico’s

| Risico | Tegenmaatregel |
| --- | --- |
| Zonder verplichte zinsdelen glipt een onvolledige uitspraak door | Dezelfde controles draaien als signaal; de reviewer ziet ze. Meten of reviewers ze oppakken |
| Het voorgestelde type is fout en de reviewer keurt gedachteloos goed | Typebevestiging blijft een expliciete reviewhandeling; fouten per type meten |
| Metis stelt verkeerde context voor en de medewerker klikt ja | Voorstel toont de letterlijke tekst en vindplaats; nooit automatisch gekoppeld |
| Meer werk verschuift naar de reviewer | Reviewtijd per object meten vóór en na |
| De toelating wordt te soepel voor aanbevelingen | Voor aanbevelingen blijven richting en sterkte een verplichte reviewbevestiging |

## Besluiten voor William

1. **Zinsdelen van blokkade naar signaal.** Advies: ja. Dit is de kern van het
   ontwerp; zonder dit besluit blijft het oude formulier bestaan.
2. **Eén handeling “hoort erbij” in plaats van twaalf rollen.** Advies: ja, met
   Metis die de soort benoemt en de reviewer die het ziet.
3. **Type als voorstel van Metis, bevestigd bij review.** Advies: ja. Los
   daarvan: komt er een type voor feitelijke uitspraken? Dat raakt wat wordt
   uitgeleverd en is een eigen besluit.
4. **Onderbouwing als twee keuzes** (aangewezen of “staat niet in de bron”).
   Advies: ja.
5. **Moet de hele bron verantwoord zijn vóór er iets wordt opgebouwd?** Dat is
   nu zo en staat “aanwijzen → review per passage” in de weg. Dit ontwerp laat
   het ongemoeid; het is een apart besluit.
6. **Eerst meten.** Advies: vóór de bouw het voorstel van Metis (type en
   context) vergelijken met bestaande, door mensen afgeronde annotaties. Dat
   vraagt betaalde modelcalls en iemand die verschillen beoordeelt.

## Wanneer is het geslaagd

Aantoonbaar minder handelingen en tijd per kennisobject, zonder meer
betekenisverlies, ongefundeerde toevoegingen of gemiste fouten dan de huidige
werkwijze. Dat vraagt een vooraf vastgelegde referentie en vooraf gekozen
grenzen; technische tests bewijzen dit niet.

## Aanleiding

Op 12 november 2026 is een passage over risicofactoren voor smetten ingevuld in
de werkplek van #1059 (lokaal, echte opslag, vastgelegd modelantwoord). Het
eerste opsommingspunt was af te ronden na acht handelingen, waarvan het koppelen
van de inleidende zin alleen via “Onderbouwing” te vinden was. Het tweede punt
was niet af te ronden: “Welke uitspraak wordt toegelicht?” accepteert alleen
woorden uit de zin zelf. Besluit William: geen losse reparaties; een structurele
oplossing of niets.
