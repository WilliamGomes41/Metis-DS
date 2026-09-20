"""Read-only explanation page for the Metis operations console."""
from __future__ import annotations

from collections.abc import Callable

Section = tuple[str, str, tuple[tuple[str, str, str], ...]]

SECTIONS: tuple[Section, ...] = (
    ("Metis", "De basis: wat Metis is en welke rol het speelt.", (
        ("Metis", "Het systeem waarmee V&VN brondocumenten omzet in gecontroleerde digitale kennis. Metis bewaart de herkomst, laat mensen beoordelen en bepaalt wat gepubliceerd mag worden.", "Een richtlijn wordt verwerkt tot kleine kennisstukken die Athena later kan gebruiken."),
        ("Operations console", "De interne werkomgeving van Metis. Bevoegde medewerkers beheren hier bronnen, beoordelen kennis en zetten die klaar voor publicatie.", "Een reviewer ziet een voorstel naast de bronpassage en kiest: goedkeuren, aanpassen of afwijzen."),
        ("Kennislaag", "De gecontroleerde laag tussen een brondocument en een toepassing. Daardoor hoeft een toepassing niet zelf te bepalen welke kennis betrouwbaar is.", "Athena krijgt een actuele aanbeveling uit de kennislaag, niet een losse kopie uit een pdf."),
    )),
    ("Bron en kennis", "Hoe Metis onderscheid maakt tussen het oorspronkelijke document en bruikbare digitale kennis.", (
        ("Bron", "Het oorspronkelijke document of de oorspronkelijke pagina waarop kennis is gebaseerd. Metis verandert die bron niet.", "Een vastgestelde V&VN-richtlijn over wondzorg is een bron."),
        ("Bronversie", "De precieze uitgave van een bron die Metis heeft vastgelegd. Dit voorkomt dat oude en nieuwe richtlijnen door elkaar worden gebruikt.", "Versie 1.2 en 2.0 van een richtlijn blijven herkenbaar van elkaar gescheiden."),
        ("Bronpassage", "Het specifieke stuk tekst, de tabel of de aanbeveling waarop een kennisobject steunt.", "Bij een object over wondreiniging is dit precies de alinea met die aanbeveling."),
        ("Kennisobject", "Een zelfstandig begrijpelijk stukje kennis uit een bron: bijvoorbeeld een aanbeveling, voorwaarde, uitzondering of definitie. Het blijft gekoppeld aan de bronpassage.", "‘Overweeg X bij Y, tenzij Z’ is één kennisobject, inclusief de uitzondering."),
        ("Provenance", "De vastgelegde herkomst en bewerkingsgeschiedenis van kennis. In gewone taal: je kunt nagaan waar het vandaan kwam en wat ermee is gebeurd.", "Je kunt terugzien uit welke richtlijnversie een antwoord kwam en wie het object goedkeurde."),
        ("Locator", "De precieze verwijzing naar een plek in de bron, zoals een pagina, hoofdstuk, paragraaf of webadres.", "‘Richtlijn Wondzorg, versie 2.0, hoofdstuk 4, aanbeveling 3’ is een locator."),
        ("Brontrouw", "De eis dat kennis aantoonbaar klopt met de vastgelegde bron. Een samenvatting mag eenvoudiger zijn, maar de betekenis mag niet verschuiven.", "Een bron zegt ‘overweeg’; Metis mag dat niet veranderen in ‘doe altijd’."),
    )),
    ("Review", "Waarom Metis menselijke beoordeling gebruikt voordat kennis verder kan.", (
        ("Review", "De menselijke controle van een kennisvoorstel. De reviewer beoordeelt betekenis, context, type kennis en de koppeling met de bron.", "Een reviewer ziet dat een uitzondering ontbreekt en stuurt het voorstel terug voor correctie."),
        ("Reviewer", "De bevoegde professional die een voorstel inhoudelijk beoordeelt. Een reviewer toetst meer dan taal: ook of de kennis verantwoord gebruikt kan worden.", "Een verpleegkundig inhoudsdeskundige beoordeelt of een aanbeveling nog past bij de context van de richtlijn."),
        ("Menselijke controle", "Een mens blijft verantwoordelijk voor inhoudelijke beoordeling en publicatie. Automatisering kan voorstellen doen, maar neemt die beslissing niet over.", "Software vindt een mogelijke passage; een reviewer bepaalt of daarvan kennis mag worden gemaakt."),
        ("Four-eyes", "Een extra controle door een tweede bevoegde persoon bij belangrijke of risicovolle stappen.", "Kennis met gevolgen voor veilig handelen krijgt naast de eerste review een tweede beoordeling."),
        ("High-risk", "Kennis waarbij een fout grote gevolgen kan hebben, bijvoorbeeld voor patiëntveiligheid of een verplicht protocol. Daarvoor gelden zwaardere controles.", "Een instructie rond medicatieveiligheid kan high-risk zijn."),
    )),
    ("Publicatie", "Van gecontroleerd werk naar kennis die een toepassing werkelijk mag gebruiken.", (
        ("Publiceren", "Het expliciet vrijgeven van gecontroleerde kennis voor gebruik door toepassingen. Een afgeronde review is dus niet automatisch een publicatie.", "Een object kan goedgekeurd zijn, maar blijft intern totdat een publisher het in een release opneemt."),
        ("Publicatiegate", "De verplichte controle vóór publicatie. Als bron, review, bevoegdheid of andere vereiste ontbreekt, gaat de poort niet open.", "Een object zonder vastgelegde bronpassage komt niet door de publicatiegate."),
        ("Snapshot", "Een vastgelegde momentopname van kennis op één tijdstip. Daarmee is later te reconstrueren wat precies beschikbaar was.", "Metis kan terugvinden welke kennisversie beschikbaar was toen Athena een antwoord gaf."),
        ("Release", "Een herkenbare, vastgelegde publicatie van één of meer kennisobjecten.", "Release 2026.10 bevat de goedgekeurde kennis uit een vernieuwde richtlijn."),
        ("Ingetrokken en vervangen", "Ingetrokken kennis mag niet meer gebruikt worden. Vervangen maakt zichtbaar welke nieuwe versie de oude opvolgt; de geschiedenis blijft bewaard.", "Bij een ernstige fout wordt een object ingetrokken en verwijst de opvolger naar de nieuwe aanbeveling."),
    )),
    ("Veiligheid", "Waarborgen die voorkomen dat twijfelachtige kennis toch wordt gebruikt.", (
        ("Fail-closed", "Bij twijfel geeft Metis geen toestemming. Ontbreekt een verplichte controle, dan blijft kennis geblokkeerd.", "Als Metis niet kan bevestigen dat een object gepubliceerd is, krijgt een toepassing geen antwoord uit dat object."),
        ("SHA-256", "Een digitale vingerafdruk van een bestand. Verandert er één teken, dan verandert de vingerafdruk mee.", "Metis controleert zo of het opgeslagen bronbestand nog hetzelfde is als bij ontvangst."),
        ("Immutable bron", "Een bronbestand dat na vastlegging niet ongemerkt kan worden gewijzigd. Een nieuwe versie krijgt een nieuw bronrecord.", "Een geactualiseerde pdf wordt als nieuwe bronversie opgeslagen; de oude blijft intact."),
        ("Canonieke kennis", "De ene, officieel vastgestelde versie van een kennisobject die binnen Metis geldt. Dit voorkomt concurrerende kopieën.", "Athena gebruikt de canonieke aanbeveling uit Metis, niet een kopie uit een spreadsheet."),
    )),
    ("Gebruik van kennis", "Hoe een digitale toepassing betrouwbare Metis-kennis opvraagt en wat zij doet als die er niet is.", (
        ("Retrieval", "Het gericht ophalen van relevante, gepubliceerde kennis voor een vraag. Retrieval zoekt binnen wat Metis heeft vrijgegeven.", "Bij een vraag over wondzorg zoekt Athena naar gepubliceerde kennisobjecten die bij de situatie passen."),
        ("Product API", "De technische ingang waarmee een toegelaten toepassing gepubliceerde Metis-kennis kan opvragen. Ongepubliceerd reviewwerk is daar niet beschikbaar.", "Athena vraagt alleen kennis op die Metis voor gebruik heeft vrijgegeven."),
        ("Supported", "Een antwoord is ondersteund wanneer Metis er relevante, gepubliceerde kennis met een herleidbare bron voor kan leveren.", "Een antwoord noemt de richtlijnversie en aanbeveling waarop het steunt."),
        ("Abstain", "Het antwoord wanneer onvoldoende betrouwbare kennis beschikbaar is. Metis construeert dan geen antwoord dat misschien klopt.", "Bij een vraag buiten de beschikbare richtlijnen meldt Athena dat er geen onderbouwd antwoord beschikbaar is."),
        ("Entitlement", "De vastgelegde toestemming die bepaalt welke toepassing of gebruiker welke kennis mag gebruiken.", "Een interne testtoepassing kan een proefrelease zien, terwijl een publiek product alleen de reguliere release ziet."),
    )),
    ("AI in Metis", "Waar AI kan helpen en waar de grens ligt.", (
        ("Semantische interpretatie", "Het herkennen van betekenis en samenhang in tekst, niet alleen van losse woorden. Dit kan helpen om kandidaatpassages te vinden.", "AI kan signaleren dat ‘afzien van’ en ‘niet toepassen’ waarschijnlijk dezelfde handelingsrichting beschrijven."),
        ("Model", "Een AI-systeem dat patronen in taal kan herkennen en tekst kan genereren. Een model heeft geen professionele verantwoordelijkheid en kent de bron niet automatisch.", "Een model kan een samenvattingsvoorstel maken, maar mag niet zelf besluiten dat dit de richtlijn juist weergeeft."),
        ("Voorstel", "Een concept dat door een mens of AI is gemaakt en nog beoordeeld moet worden. Een voorstel is nadrukkelijk nog geen geldige kennis.", "Na analyse van een bronpassage maakt Metis een voorstel voor een kennisobject; de reviewer toetst het vóór publicatie."),
        ("Deterministische controle", "Een controle met een vaste, herhaalbare uitkomst, bijvoorbeeld of bron, reviewstatus en toestemming aanwezig zijn.", "De publicatiegate controleert steeds op dezelfde manier of de vereiste bronbinding en goedkeuring er zijn."),
    )),
    ("Audit en ontwikkeling", "Hoe Metis veilig leert en verbetert zonder experimenten als productie te behandelen.", (
        ("Audit", "Het onderzoeken of Metis werkt zoals bedoeld: inhoudelijk, technisch en procesmatig. Een audit levert bewijs en verbeterpunten op, geen automatische productieaanpassing.", "Een audit controleert of ingetrokken kennis niet meer via de Product API beschikbaar is."),
        ("Experiment", "Een afgebakende proef om een aanname of nieuwe werkwijze te toetsen.", "Metis test of een andere manier van bronpassages voorstellen de reviewtijd verkort zonder brontrouw te verlagen."),
        ("Baseline", "De huidige, gemeten uitgangssituatie waarmee een experiment wordt vergeleken.", "De gemiddelde reviewtijd vóór een nieuwe werkwijze is de baseline voor het experiment."),
        ("Kandidaatroute", "Een mogelijke nieuwe werkwijze die nog wordt onderzocht en niet automatisch onderdeel is van het gewone proces.", "Een nieuwe extractiemethode wordt naast de bestaande route getest."),
        ("READY FOR IMPLEMENTATION", "De uitkomst dat een oplossing voldoende is onderzocht en voorbereid om gecontroleerd in gebruik te nemen. Het is geen synoniem voor ‘al live’.", "Na een geslaagd experiment, documentatie en passende controles kan een kandidaatroute deze status krijgen."),
    )),
)


def render(escape: Callable[[object], str]) -> str:
    sections = []
    for number, (title, intro, terms) in enumerate(SECTIONS, start=1):
        entries = "".join(
            f'''<div class="dictionary-term">
                  <h3>{escape(name)}</h3>
                  <p>{escape(definition)}</p>
                  <p class="dictionary-example"><span>Voorbeeld</span>{escape(example)}</p>
                </div>'''
            for name, definition, example in terms
        )
        sections.append(
            f'''<section class="dictionary-section" aria-labelledby="dictionary-{number}">
                  <header><h2 id="dictionary-{number}">{escape(title)}</h2><p>{escape(intro)}</p></header>
                  <div class="dictionary-terms">{entries}</div>
                </section>'''
        )
    return f'''
      <section class="room dictionary-room">
        <p class="eyebrow">Over console</p>
        <h1>Metis uitgelegd</h1>
        <p class="lead">De begrippen achter Metis, in gewone taal. Van brondocument tot betrouwbare digitale kennis.</p>
        <section class="dictionary-chain" aria-label="De rol van Metis in de kennisketen">
          <ol><li>V&amp;VN-bron</li><li>Metis</li><li>Gecontroleerde kennis</li><li>Toepassing</li></ol>
          <p>Metis zorgt dat toepassingen V&amp;VN-kennis kunnen gebruiken zonder zelf te hoeven bepalen welke bron, versie en inhoud betrouwbaar en gepubliceerd is.</p>
        </section>
        <div class="dictionary-sections">{"".join(sections)}</div>
      </section>
    '''
