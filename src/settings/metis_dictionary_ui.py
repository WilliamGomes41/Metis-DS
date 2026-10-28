"""Read-only explanation page for the Metis operations console."""
from __future__ import annotations

from collections.abc import Callable

Section = tuple[str, str, tuple[tuple[str, str, str], ...]]

SECTIONS: tuple[Section, ...] = (
    ("Werken met een bron", "De begrippen die je nodig hebt wanneer je een richtlijn, handreiking of andere kennisbron in Metis verwerkt.", (
        ("Bron", "Het oorspronkelijke document of de oorspronkelijke webpagina die je in Metis gebruikt. Metis verandert de bron zelf niet.", "Een vastgestelde V&VN-richtlijn over wondzorg is een bron."),
        ("Versie van de bron", "De precieze uitgave van een bron die Metis heeft vastgelegd. Zo blijven oude en nieuwe versies van elkaar te onderscheiden.", "Versie 1.2 en 2.0 van dezelfde richtlijn blijven afzonderlijk herkenbaar."),
        ("Passage uit de bron", "Het specifieke stuk tekst, de tabel of de aanbeveling waarop een kennisvoorstel of kennisstuk is gebaseerd.", "Bij een aanbeveling over wondreiniging is dit precies de alinea waarin die aanbeveling staat."),
        ("Vindplaats in de bron", "De precieze plek waar de passage terug te vinden is, bijvoorbeeld pagina, hoofdstuk, paragraaf of webadres.", "Richtlijn Wondzorg, versie 2.0, hoofdstuk 4, aanbeveling 3."),
    )),
    ("Van bron naar kennis", "Metis maakt van relevante broninhoud afzonderlijke kennisstukken die je inhoudelijk kunt controleren.", (
        ("Kennisvoorstel", "Een voorgesteld kennisstuk dat nog beoordeeld moet worden. Het is nog geen goedgekeurde of gepubliceerde kennis.", "Metis herkent een aanbeveling in een richtlijn en maakt daarvan een voorstel voor beoordeling."),
        ("Kennisstuk (kennisobject)", "Een zelfstandig begrijpelijk stukje kennis uit een bron, bijvoorbeeld een aanbeveling, voorwaarde, uitzondering of definitie. In Metis heet dit technisch een kennisobject.", "‘Overweeg X bij Y, tenzij Z’ kan één kennisstuk zijn als de voorwaarde en uitzondering nodig zijn om de betekenis te behouden."),
        ("Context", "De informatie die nodig is om een kennisstuk correct te begrijpen en toe te passen, zoals doelgroep, situatie, setting of aanleiding.", "Een aanbeveling geldt alleen voor volwassenen in de acute zorg; die context hoort bij het kennisstuk."),
        ("Voorwaarde", "Iets dat eerst moet gelden voordat een aanbeveling of andere kennis van toepassing is.", "‘Bij onvoldoende effect na drie dagen’ is een voorwaarde voor de vervolgstap."),
        ("Uitzondering", "Een situatie waarin een algemene aanbeveling niet of anders geldt.", "Een aanbeveling geldt voor de meeste patiënten, behalve bij een specifiek veiligheidsrisico."),
        ("Herkomst", "De vastgelegde relatie tussen een kennisstuk en de bron waaruit het komt. Je kunt nagaan uit welke versie en passage de kennis is afgeleid.", "Bij een kennisstuk kun je terugzien uit welke richtlijnversie en passage het afkomstig is."),
        ("Brontrouw", "De eis dat een kennisstuk de betekenis van de bron correct behoudt. Formuleringen mogen duidelijker worden, maar mogen de inhoud niet sterker, zwakker of anders maken.", "Als de bron ‘overweeg’ zegt, mag het kennisstuk daar niet ‘doe altijd’ van maken."),
    )),
    ("Kennis beoordelen", "Hier controleer je of een kennisvoorstel inhoudelijk klopt voordat het verder kan.", (
        ("Inhoudelijke beoordeling (review)", "De controle of een kennisvoorstel de bron correct weergeeft. Je beoordeelt onder meer betekenis, context, voorwaarden, uitzonderingen en de koppeling met de bron.", "Je ziet dat een uitzondering uit de oorspronkelijke aanbeveling ontbreekt en stuurt het voorstel terug voor correctie."),
        ("Beoordelaar (reviewer)", "De bevoegde professional die een kennisvoorstel inhoudelijk beoordeelt. De beoordelaar beslist of het voorstel de bron voldoende correct en compleet weergeeft.", "Een verpleegkundig inhoudsdeskundige beoordeelt of een aanbeveling en de relevante context goed zijn overgenomen."),
        ("Menselijke controle", "Een mens blijft verantwoordelijk voor inhoudelijke beoordeling en publicatie. Automatisering kan voorstellen doen, maar neemt die beslissing niet over.", "Software selecteert een mogelijke passage; een beoordelaar bepaalt of daarvan bruikbare kennis kan worden gemaakt."),
        ("Tweede beoordeling (four-eyes)", "Een extra beoordeling door een tweede bevoegde persoon wanneer de kennis of de handeling voldoende risicovol is om extra controle te vereisen.", "Een instructie met mogelijke gevolgen voor patiëntveiligheid krijgt naast de eerste beoordeling een tweede controle."),
        ("Kennis met verhoogd risico (high-risk)", "Kennis waarbij een fout grotere gevolgen kan hebben, bijvoorbeeld voor patiëntveiligheid of verplicht professioneel handelen. Daarvoor gelden zwaardere controles.", "Een instructie rond medicatieveiligheid kan als kennis met verhoogd risico worden behandeld."),
    )),
    ("Kennis publiceren", "Goedkeuren en publiceren zijn twee verschillende stappen. Pas na publicatie mag kennis door toepassingen worden gebruikt.", (
        ("Publiceren", "Het expliciet vrijgeven van beoordeelde kennis voor gebruik. Een afgeronde inhoudelijke beoordeling publiceert een kennisstuk niet automatisch.", "Een goedgekeurd kennisstuk blijft intern totdat een bevoegde publisher het in een publicatie opneemt."),
        ("Publicatiecontrole (publicatiegate)", "De verplichte controle vóór publicatie. Metis controleert onder meer of bron, beoordeling, bevoegdheid en vereiste extra controles aanwezig zijn.", "Een kennisstuk zonder geldige koppeling met de bron kan niet worden gepubliceerd."),
        ("Momentopname (snapshot)", "Een vastgelegde toestand van de kennis op één moment. Hierdoor kan later worden gereconstrueerd wat precies is beoordeeld of gepubliceerd.", "Je kunt terugvinden welke kennisversie beschikbaar was toen een bepaalde release werd gepubliceerd."),
        ("Release", "Een herkenbare, vastgelegde publicatie van één of meer kennisstukken.", "Release 2026.10 bevat de gepubliceerde kennis uit een vernieuwde richtlijn."),
        ("Vervangen of intrekken", "Kennis die niet meer gebruikt mag worden kan worden ingetrokken. Als nieuwe kennis de oude opvolgt, blijft zichtbaar welke versie de eerdere vervangt.", "Na herziening van een richtlijn wordt de oude aanbeveling ingetrokken en opgevolgd door de nieuwe."),
        ("Officiële kennisversie (canonieke kennis)", "De versie van een kennisstuk die binnen Metis als geldende, vastgestelde kennis wordt beheerd. Dit voorkomt concurrerende kopieën.", "Een toepassing gebruikt de gepubliceerde Metis-versie van de aanbeveling, niet een losse kopie uit een spreadsheet."),
    )),
    ("Kennis gebruiken", "Wat er gebeurt nadat kennis is gepubliceerd en beschikbaar komt voor een toepassing.", (
        ("Gepubliceerde kennis", "Kennis die de vereiste beoordeling en publicatiecontrole heeft doorlopen en expliciet is vrijgegeven voor gebruik.", "Een toepassing kan een gepubliceerde aanbeveling gebruiken, maar geen voorstel dat nog in review staat."),
        ("Kennis ophalen (retrieval)", "Het gericht zoeken naar relevante, gepubliceerde kennis voor een vraag of situatie.", "Bij een vraag over wondzorg wordt gezocht binnen de gepubliceerde kennisstukken die daarbij passen."),
        ("Onderbouwd (supported)", "Een antwoord of resultaat is onderbouwd wanneer er relevante gepubliceerde kennis met een herleidbare bron voor beschikbaar is.", "Bij het resultaat is terug te vinden op welke richtlijnversie en passage het steunt."),
        ("Geen onderbouwd antwoord (abstain)", "Als Metis onvoldoende passende, gepubliceerde kennis heeft, wordt niet gedaan alsof er wel een betrouwbaar antwoord is.", "Bij een vraag buiten de beschikbare richtlijnen meldt de toepassing dat er geen onderbouwd antwoord beschikbaar is."),
        ("Toegangsrecht (entitlement)", "De vastgelegde toestemming die bepaalt welke toepassing of gebruiker welke gepubliceerde kennis mag gebruiken.", "Een interne testtoepassing kan een proefrelease zien die nog niet voor een publiek product beschikbaar is."),
    )),
    ("Automatisering in Metis", "Wat software of AI mag ondersteunen en waar menselijke verantwoordelijkheid begint.", (
        ("Automatisch voorstel", "Een voorstel dat software of AI helpt samenstellen uit een bron. Het blijft een voorstel totdat een bevoegde beoordelaar het inhoudelijk heeft gecontroleerd.", "Metis kan relevante passages selecteren en daar een kennisvoorstel van maken voor de review."),
        ("Semantische interpretatie", "Het herkennen van betekenis en samenhang in tekst, niet alleen van dezelfde woorden. Metis kan dit gebruiken om relevante passages te vinden of te groeperen.", "‘Niet toepassen’ en ‘afzien van behandeling’ kunnen inhoudelijk verwant zijn, ook al gebruiken ze andere woorden."),
        ("Model", "Een AI-systeem dat taalpatronen kan herkennen en gestructureerde voorstellen kan maken. Een model heeft geen inhoudelijke bevoegdheid en kent de geldigheid van een bron niet automatisch.", "Een model kan helpen een passage te selecteren, maar mag niet zelf besluiten dat de inhoud juist of publiceerbaar is."),
        ("Vaste controle (deterministische controle)", "Een controle met een vaste, herhaalbare uitkomst, bijvoorbeeld of een bronkoppeling, beoordeling of publicatiestatus aanwezig is.", "De publicatiecontrole kijkt steeds op dezelfde manier of de vereiste goedkeuringen aanwezig zijn."),
    )),
    ("Onderzoek naar Metis", "Deze begrippen zijn vooral relevant wanneer je onderzoekt hoe Metis zelf presteert of kan worden verbeterd. Voor het gewone verwerken van richtlijnen heb je ze meestal niet nodig.", (
        ("Audit", "Het onderzoeken of Metis werkt zoals bedoeld: inhoudelijk, technisch en procesmatig. Een audit levert bewijs en verbeterpunten op en verandert de productie niet automatisch.", "Een audit controleert of ingetrokken kennis daadwerkelijk niet meer beschikbaar is."),
        ("Experiment", "Een afgebakende proef om een aanname of nieuwe werkwijze te toetsen.", "Je vergelijkt twee manieren van passagevorming om te onderzoeken welke minder correcties door reviewers nodig heeft."),
        ("Baseline", "De gemeten uitgangssituatie waarmee een experiment wordt vergeleken.", "De huidige reviewtijd en het huidige aantal correcties vormen samen de baseline."),
        ("Kandidaatroute", "Een mogelijke nieuwe werkwijze die nog wordt onderzocht en nog niet automatisch onderdeel is van het gewone proces.", "Een nieuwe methode voor passagevorming draait naast de bestaande methode in een experiment."),
        ("READY FOR IMPLEMENTATION", "De onderzoeksuitkomst dat een verbetering voldoende is onderzocht en voorbereid om als ontwikkelopdracht te worden opgepakt. Dit betekent niet dat de wijziging al live staat.", "Een experiment levert voldoende bewijs op om de verbetering gecontroleerd te laten implementeren."),
    )),
    ("Technische begrippen", "Deze termen kun je tegenkomen in Metis, maar je hoeft ze niet te begrijpen om een richtlijn inhoudelijk te beoordelen.", (
        ("Operations console", "De interne werkomgeving waarin bevoegde medewerkers bronnen beheren, kennis beoordelen en publicaties voorbereiden.", "Je opent hier een kennisvoorstel naast de bijbehorende bronpassage."),
        ("Product API", "De technische ingang waarmee een toegelaten toepassing gepubliceerde Metis-kennis kan opvragen. Ongepubliceerd reviewwerk is daar niet beschikbaar.", "Een toepassing vraagt via de Product API alleen kennis op die Metis voor gebruik heeft vrijgegeven."),
        ("SHA-256", "Een digitale vingerafdruk waarmee Metis kan controleren of een opgeslagen bronbestand nog exact hetzelfde is.", "Als één teken in een bestand verandert, verandert ook de digitale vingerafdruk."),
        ("Ongewijzigd opgeslagen bron (immutable bron)", "Een bronbestand dat na vastlegging niet stilzwijgend wordt overschreven. Een gewijzigde bron wordt als een nieuwe versie behandeld.", "Een geactualiseerde pdf krijgt een nieuwe bronversie; de eerder beoordeelde versie blijft intact."),
        ("Bij twijfel blokkeren (fail-closed)", "Als Metis een vereiste controle niet kan bevestigen, wordt de handeling geblokkeerd in plaats van aangenomen dat het waarschijnlijk goed is.", "Als niet kan worden vastgesteld dat een kennisstuk is gepubliceerd, wordt het niet aan een toepassing geleverd."),
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
        <p class="eyebrow">Over Metis</p>
        <h1>Metis uitgelegd</h1>
        <p class="lead">Wat er met een richtlijn gebeurt in Metis, welke keuzes jij als inhoudelijk beoordelaar maakt en wanneer kennis gebruikt mag worden.</p>
        <section class="dictionary-chain" aria-label="Zo werkt Metis">
          <h2>Zo werkt Metis</h2>
          <ol>
            <li>Bron aanleveren</li>
            <li>Kennisvoorstellen maken</li>
            <li>Inhoudelijk beoordelen</li>
            <li>Publiceren</li>
            <li>Gebruiken</li>
          </ol>
          <p>Je levert een richtlijn, handreiking of andere kennisbron aan. Metis maakt van relevante passages afzonderlijke kennisvoorstellen. Een bevoegde beoordelaar controleert of de inhoud, context, voorwaarden en uitzonderingen correct zijn overgenomen. Alleen kennis die de vereiste controles heeft doorlopen en expliciet is gepubliceerd, kan daarna door een toepassing worden gebruikt. Bij ieder kennisstuk blijft zichtbaar uit welke bron en passage het afkomstig is.</p>
        </section>
        <div class="dictionary-sections">{"".join(sections)}</div>
      </section>
    '''
