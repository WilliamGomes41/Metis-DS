# #1091 — Domeinontwerp: selectiebegeleiding voor kennisobjecten

**Status:** ontwerp ter besluit; niet geïmplementeerd. **Bestaand project:** P-MET-6, Menselijke annotatie en bronverantwoording. **Werkpakket:** MET-106 onder MET-57 / GitHub #1013. **Normatieve samenhang:** KO-definitie #986/MET-49; annotatiewerkplek #1051/MET-71; huidige bron-eerst-kaart #1060/MET-75. **Datum:** 16 november 2026. De KO-definitieverduidelijking uit #1090 is gemergd (95e79197) en staat in `PROTOCOL.md` §4.2 (v4.3.1); dit ontwerp is daartegen opnieuw gecontroleerd: de begrenzing in §3 (afzonderlijk beoordeelbaar is niet zelfstandig een praktijkvraag beantwoorden) volgt §4.2.

**User promise:** Een medewerker die een bron leest krijgt op het **moment van de eerste inhoudelijke selectie** korte, begrijpelijke begeleiding om te onderscheiden of een tekstdeel een zelfstandige, afzonderlijk te beoordelen uitspraak vormt, of uitsluitend context, onderbouwing of bronstructuur is. De medewerker houdt het inhoudelijke besluit; het systeem maakt geen extra kennisobjecten.

## 1. Diagnose: de huidige begeleiding begint te laat

**Geobserveerd in actuele code op main:**
- `src/vorming/human_annotation_ui_v1.py` toont naast de bron de acties `Uitspraak`, `Hoort erbij` en `Onderbouwing`. Het documentoverzicht houdt niet-verantwoorde bronstukken zichtbaar met de keuze `Geen uitspraak` versus `Toch een uitspraak`.
- `src/vorming/human_annotation_editor.js`, `HELP.core`, zegt: “Selecteer één bewering of advies, letterlijk: meestal één zin, soms een zin met een opsomming.” Hetzelfde HELP-object geeft voorbeelden voor bijbehorende context en onderbouwing. `?` opent die uitleg bij de betreffende rij.
- `src/vorming/human_annotation_preview_v1.py` controleert **na** selectie onder andere onvolledige zinnen, bronbinding en open context. `no_independent_claim` is een signaal, geen garantie voor juiste kennisgrenzen.
- `src/vorming/knowledge_materialisation_v1.py` maakt vervolgens deterministisch de kandidaat op basis van exacte gekozen bronbereiken en beslist niet zelfstandig of de annotator de juiste kennisuitspraak heeft gevonden.
- `tests/browser_annotation_suggestions_check.cjs` controleert het openen van hulp, niet of medewerkers betekenisgrenzen inhoudelijk juist herkennen.

**Bewijsgrens:** Er zijn geen gemeten gebruikersfouten of vergelijkende praktijkresultaten beschikbaar in deze inspectie. Niet bewezen is dat extra guidance het gedrag verbetert. **Sterkste tegenargument:** extra hulp kan ervaren medewerkers vertragen, verkeerde één-zinregels versterken en een niet-bestaand probleem oplossen. Daarom eerst een kleine vergelijking zonder productcode.

## 2. Domeinclassificatie en state ownership

De voorgestelde **uitleg en voorbeeldprojectie zijn stateless**: ze lezen bestaande bron-/annotatiegegevens, maar creëren of wijzigen zelf geen domeinstaat. Open-/sluitstatus van een `?` is vluchtige UI-state, geen domeinstatus. De console blijft near-stateless.

**Enige persistente autoriteit:** bestaande Azure-kernel en workflow PostgreSQL/Blob. `human_annotation_v1.save` beheert bevoegde menselijke bronselecties en annotatieversies; `human_annotation_preview_v1` inspecteert ze; `knowledge_materialisation_v1.materialise_knowledge_candidates` blijft de enige kandidaatmaker; bestaande review- en publicatiedelen blijven hun eigen authority. Geen nieuwe tabellen, database, file store, auditledger, annotatiestatus, route of tweede opslagplaats.

**Change class bij latere UI-uitvoering:** Class B, `Rewrite risk: none`, zolang uitsluitend bestaande uitleg verandert. Deze documentatie is een ontwerp, geen implementatieopdracht. Als een voorstel `ready`, Admission, objecttype, bronidentiteit, bevestigde relaties, reviewbevoegdheid of publicatietransities wijzigt: **STOP** en eerst een afzonderlijk Class B-/Class A-ontwerp met passende verificatie.

## 3. Domeinbetekenis die de medewerker moet kunnen onderscheiden

| Begrip | Inhoudelijke keuze | Bestaande eigenaar |
|---|---|---|
| Bronpassage | Letterlijke tekst op een exacte bronpositie; is niet automatisch een KO | Brongegevens/extractie |
| Zelfstandige kennisuitspraak | Een afgebakende bewering, definitie, verklaring of aanbeveling die met haar noodzakelijke context als één betekenis afzonderlijk kan worden beoordeeld | Medewerker kiest; KO-contract begrenst |
| Hoort erbij | Voorwaarde, uitzondering, doelgroep, verwijzing, kop of inleiding die de geselecteerde claim begrenst en zonder eigen betekenisbesluit geen afzonderlijke KO is | Huidige contextbinding |
| Onderbouwing | Onderzoek, uitleg of argumentatie die de claim ondersteunt; niet automatisch nieuwe claim | Huidige onderbouwingsbinding |
| Bronverantwoording | Oordeel over broninhoud die geen eigen claim is, of nog onzeker is; nooit automatisch uitsluiten | Bestaande source accountability |
| Inhoudelijke goedkeuring | Beoordeling van exacte KO-versie na bouw; de annotator krijgt hiermee geen reviewerrol | Bestaande reviewkernel |

**Begrenzing:** “afzonderlijk te beoordelen” is **niet** hetzelfde als zelfstandig een volledige praktijkvraag kunnen beantwoorden. Een bewering kan over meerdere bronbereiken lopen; één zin kan meerdere claims bevatten. Voorwaarden en uitzonderingen die de betekenis begrenzen horen bij dezelfde claim. Een voorwaarde die zelf een nieuwe normatieve uitspraak doet, kan echter zelfstandig zijn. Geen vaste één-zin-, sleutelwoorden- of passagegrootte-regel.

## 4. Selectieheuristiek — begeleiding, geen gate

De medewerker kan in gewone taal vier vragen gebruiken, zonder ze als verplicht formulier te hoeven beantwoorden:

1. **Eigen uitspraak?** “Zegt de bron hier iets wat afzonderlijk kan worden begrepen en beoordeeld, zoals een aanbeveling, definitie, verklaring of observatie?” Administratieve opmaak en kopnummer zijn normaliter structuur.
2. **Één betekenis?** “Staan hier twee losse uitspraken, of één uitspraak met beperkingen?” Het aantal zinnen is geen beslisregel.
3. **Welke tekst hoort noodzakelijk bij deze uitspraak?** “Zou doelgroep, uitzondering, voorwaarde, inleidende zin of modaliteit de betekenis veranderen als ik ze weglaat?” Koppel dan brongetrouw in `Hoort erbij`.
4. **Onderbouwing of afzonderlijke claim?** “Is dit alleen bewijs waarom een andere uitspraak geldt, of bevat dit zelf een betekenisvolle onderzoeksbevinding?” Als onzeker: niet automatisch extra KO creëren, maar bestaande open/uncertain-broncontrole gebruiken.

**Niet uit de heuristiek afleiden:** wetenschappelijke waarheid, bronactualiteit, zelfstandige beantwoording, goedkeuring, nieuwe objecttypetaxonomie of publicatiebevoegdheid. Een feitelijke onderzoeksbevinding als kandidaat vraagt de bestaande objecttype-/bronstrategievoorwaarden; de nieuwe uitleg mag een niet-toegelaten type niet via UX legaliseren.

## 5. Concreet UI-ontwerp binnen huidige werkplek

**Voorkeur A: bestaande `?` uitbreiden met contrasterende voorbeelden en één korte vraag vóór selectie.**

**Boven de bron, één regel (voorstel):**
> “Wijs een eigen uitspraak aan: iets wat de bron stelt, definieert, verklaart of aanbeveelt. Tekst die alleen bij een andere uitspraak hoort, voeg je daar toe bij ‘Hoort erbij’ of ‘Onderbouwing’.”

**Bij `?` naast Uitspraak (voorstel):**
> “Een kennisobject bevat één afzonderlijk te beoordelen uitspraak met alle tekst die nodig is om haar goed te begrijpen. Eén zin kan twee uitspraken bevatten; één uitspraak kan meerdere regels beslaan. Gebruik niet automatisch de hele alinea.”

**Bij twijfel (voorstel):**
> “Niet duidelijk of dit een aparte uitspraak is? Houd het bronstuk zichtbaar voor controle. Het wordt niet automatisch uitgesloten.”

Deze tekst wordt alleen getoond bij de reeds bestaande taak. Geen nieuwe modal, wizard, verplichte beslischecklist, extra indicator of tweede `Hulp bij tekstselectie`-vak (dat is eerder expliciet geschrapt in #1053/MET-72). De bestaande `?` en `Uitspraak / Hoort erbij / Onderbouwing` blijven herkenbaar. Toon hulp desgewenst op dezelfde plaats bij het eerste bronbereik; geen duplicatie van interpretatielogica in JS en Python.

**Alternatief B — vóór elk KO een begeleid formulier:** voorlopig afwijzen. De extra belasting is niet onderbouwd. **Alternatief C — automatisch alle potentiële claims markeren als waarheid:** buiten scope; verandert menselijke selectieverantwoordelijkheid en semantische producent-/reviewgrenzen.

### Contrasterende synthetische oefencasus (geen klinische claims)

| Bronvorm | Te onderbouwen keuze | Niet automatisch |
|---|---|---|
| “Voer handeling A uit bij groep B. Niet bij conditie C.” | Eén aanbeveling met conditie C als context | Een tweede KO uit elke uitzondering |
| “Voer A uit. Controleer daarna B.” | Twee afzonderlijk beoordeelbare handelingen kunnen twee claims zijn | Eén KO per alinea |
| “Voor de volgende gevallen geldt:” + opsommingspunt | Voeg inleidende zin bij dezelfde claim als noodzakelijke context | Het losse opsommingspunt zonder referent als volledig KO |
| “De studie omvatte 238 deelnemers.” | Bepaal of dit uitsluitend methodologische context/bewijs is of binnen bronsoortstrategie een zelfstandige bevinding | Iedere feitelijke zin automatisch KO |
| “Figuur 3”, documentdatum, paginanummer | Bronstructuur/metadata, geen claim | KO alleen vanwege markeerbare tekst |
| “Bij groep C is de effectiviteit onzeker.” | Beoordeel eigen claim of begrenzende context op basis van bronfunctie en omliggende tekst | Onzekerheid automatisch uitsluiten of overschrijven |

Echte voorbeelden moeten afkomstig zijn uit toegelaten bronnen en vooraf door inhoudelijk bevoegde beoordelaars worden vastgesteld. Bij redelijk betwistbare grenzen mag de referentie **meerdere verdedigbare uitkomsten** hebben met motivering.

## 6. Hard invariants en falsificerende proeven

| Bestaande invariant | Autoriteit | Falsificerende proef bij latere implementatie |
|---|---|---|
| Hulp is niet een inhoudelijk besluit | UI vs `human_annotation_v1` | `?` openen/sluiten/vernieuwen schrijft geen annotatie of object |
| Alleen mens kiest de grens | `human_annotation_v1.save` | Helptekst triggert geen automatische `core`-, context- of bewijsbinding |
| Kandidaattekst blijft letterlijk brongebonden | Bronreconstructie + materialiser | Exacte geselecteerde spans geven identieke kandidaattekst/ID/mapping vóór en na wijziging |
| Onverantwoorde broninhoud blijft zichtbaar | `unaccounted_ranges` (`human_annotation_preview_v1`) + source-accountability closure | Na hulp openen/sluiten en opslaan blijven alle `unaccounted_ranges` open en zichtbaar in het documentoverzicht; geen bronstuk krijgt automatisch `excluded_with_reason`. De semantische signaalsectie `Niet vastgesteld door Metis` telt NOOIT als dit bewijs |
| Annoteren is geen goedkeuring | Reviewkernel/publicatie | Hulp openen verandert noch `ready`-gate noch review-/servingstatus |
| Bestaande runtime- en opslaggrenzen blijven | Azure kernel/PostgreSQL/Blob | Geen extra writer, SQL-migratie, externe API-call of data-export |

**Lifecycle:** geen nieuwe. Bestaande annotatie `draft/ready/uncertain/withdrawn`, versie- en reviewbesluiten blijven ongewijzigd.

**Transactiegrens:** geen nieuwe transacties; `?` en helpvoorbeelden zijn pure view. Bestaande `annotation_id/revision/generation/objects_revision`-CAS, durable save en bouwpoging blijven identiek. **Idempotentie:** herhaald help openen levert geen extra effect. **Concurrentie:** twee tabs kunnen onafhankelijk hulp tonen zonder elkaars opgeslagen selectie te beïnvloeden. **Herstel:** uitleg mogen sluiten/verliezen bij herladen; opgeslagen selecties/bronanker blijven intact. **Bewijs:** geen productiebrontekst of persoonsgegevens in GitHub; alleen fictieve casussen, referentierubric en geaggregeerde acceptatie-uitkomsten.

## 7. Implementatieplan als verticale slices — na expliciete GO

**Slice 0: eerst het gebruikersprobleem toetsen (zonder productcode).** Laat 5–8 bedoelde medewerkers 6–10 vooraf inhoudelijk beoordeelde moeilijke passages selecteren in de **huidige** interface. Meet afzonderlijk: verkeerde split/merge, gemiste zelfstandige claim, verkeerd als context/bewijs gekoppelde passage, gemiste uitzondering, benodigde tijd en rationale bij twijfel. Referentieopgave wordt vooraf vastgesteld, niet door het huidige Metis-resultaat. Geen representatieve foutprevalentie claimen op deze kleine steekproef.

**Beslispoort:** Als er geen terugkerende selectiefout of verwarring wordt gevonden: **ABSTAIN**, bouw geen extra helpfunctie. Als de fout terugkomt en de beoogde voorbeelden de oorzaak adresseren: product-owner GO voor slice 1.

**Slice 1: minimaal contrast in bestaande UI.** Alleen UI-help/copy aanpassen in huidige annotatieroute; geen andere endpoints, persistente velden, nieuwe componentarchitectuur, modelcalls of policy. Browserproeven voor keyboard, screenreader, desktop/mobiel, uitleg openen/sluiten, focusbehoud, statusweergave; bestaande save/build/reviewregressie intact.

**Slice 2: vergelijkende effectproef.** Gebruik vooraf vastgelegde referentiecasussen, afgewisselde volgorde en dezelfde meetcriteria. Vergelijk niet alleen snelheid maar vooral betekenisfouten en gemiste context. Bij slechtere kwaliteit: revert UI-copy, geen migratie. Documenteer ook de gevallen waarin extra guidance niet helpt.

**Acceptatie om implementatie gereed te noemen:** gemeten verbetering op vooraf gekozen kritieke fouten óf overtuigend bewijs dat dezelfde fouten worden vermeden zonder relevante extra belasting; geen regressies in bronbinding, annotatiestatus, review of toegankelijkheid. Een geslaagde browsertest alleen bewijst geen semantisch correcte menselijke selectie.

## 8. Open besluiten en non-goals

- Besluit nodig: welke 6–10 richtlijnproza-casussen vormen een eerlijke referentieset; wie stelt vooraf het onafhankelijke oordeel vast? Optie: inhoudelijk adviseur + bestaande reviewer, zonder verplicht standaard twee-annotatorenproces.
- Besluit nodig: slaat de eerste gebruikersproef daadwerkelijk een selectiefout aan, of is de bestaande uitleg voldoende? Pas daarna eventueel helpcopy aanpassen.
- Een onderzoeksbevinding als zelfstandig KO vergt zo nodig een apart taxonomie-/bronstrategiebesluit bij #986/MET-49. Geen stille uitbreiding via deze helptekst.
- Uitgesloten: extra KO-bouwer, automatische claimclassifier, annotatie- of reviewworkflow, nieuwe database, dashboard, scores, verplicht dual annotation, individuele publicatie-/intrekking (#991), aanpassing van `PROTOCOL.md`.

## 9. Ontwerpacceptatie en overdracht

- [x] Bestaande UI- en domeinowners onderzocht; huidige guidance en bewijsgrens afgebakend.
- [x] Domeinsemantiek, stateless eigenaarschap, invarianten, recovery, concurrency en auditgrenzen vastgelegd.
- [x] Minimale ontwerpcopy, contrasterende gevallen, alternatieven en voorwaardelijke slices beschreven.
- [ ] Praktijkproef en referentiecasussen uitgevoerd (**niet gebeurd**).
- [ ] Product-owner heeft UI-implementatie-GO gegeven (**niet gebeurd**).
- [ ] Productcode gewijzigd, geverifieerd en uitgerold (**niet gebeurd**).

GitHub #1091 is de canonieke ontwerpopdracht. Linear MET-106 volgt de status binnen bestaand project P-MET-6. GitHub PR wordt als draft ter review aangeleverd; geen merge, productieactie of uitvoering van de toekomstige slices.
