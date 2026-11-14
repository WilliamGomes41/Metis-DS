"""Read-only Metis explanation: one content source, URL navigation, no writes."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlencode
import unicodedata

from src.settings.metis_explained_content import (
    MODELS, REFERENCE_REVISION, SECTIONS, Model, Term,
)


PAGES = (
    ("start", "Zo werkt Metis"),
    ("begrippen", "Begrippen"),
    ("modellen", "Modellen en verantwoording"),
    ("kennisbasis", "De kennisbasis"),
)


@dataclass(frozen=True)
class SearchHit:
    kind: str
    title: str
    description: str
    url: str


def page_url(section: str = "start", *, model_id: str = "", anchor: str = "") -> str:
    params = {"section": section}
    if model_id:
        params["model"] = model_id
    return "/over-console?" + urlencode(params) + ("#" + anchor if anchor else "")


def _normalized(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text.casefold())
                   if not unicodedata.combining(c))


def search(query: str) -> tuple[SearchHit, ...]:
    """Small, immutable collection: all words must match, aliases included."""
    words = _normalized(query).split()
    if not words:
        return ()
    hits = []
    for category in SECTIONS:
        for term in category.terms:
            text = _normalized(" ".join((term.name, term.definition, term.example,
                                         term.boundary, *term.aliases)))
            if all(word in text for word in words):
                hits.append(SearchHit("Begrip", term.name, term.definition,
                                      page_url("begrippen", anchor="begrip-" + term.id)))
    for model in MODELS:
        text = _normalized(" ".join((model.title, model.summary, model.purpose,
                                     model.working, model.rationale, model.evidence,
                                     *model.limits, *model.aliases)))
        if all(word in text for word in words):
            hits.append(SearchHit("Model", model.title, model.summary,
                                  page_url("modellen", model_id=model.id)))
    return tuple(sorted(hits, key=lambda hit: (
        _normalized(query) not in _normalized(hit.title), hit.kind, hit.title.casefold())))


def _term(term: Term, escape: Callable[[object], str]) -> str:
    boundary = (f'<p class="explained-boundary"><strong>Bewijsgrens.</strong> '
                f'{escape(term.boundary)}</p>' if term.boundary else "")
    return f'''<article class="dictionary-term" id="begrip-{escape(term.id)}">
      <h4><a class="explained-anchor" href="{escape(page_url('begrippen', anchor='begrip-' + term.id))}">{escape(term.name)}</a></h4>
      <p>{escape(term.definition)}</p>
      <p class="dictionary-example"><strong>Voorbeeld</strong><span>{escape(term.example)}</span></p>
      {boundary}
    </article>'''


def _overview(escape: Callable[[object], str]) -> str:
    steps = (
        ("Bron aanleveren", "De precieze bronversie wordt vastgelegd en verandert daarna niet meer. Je kiest of er één of twee beoordelaars nodig zijn."),
        ("Kennisobjecten aanwijzen", "Per kennisobject selecteer je in de annotatiekaart de uitspraak en voeg je met + toe wat erbij hoort en de onderbouwing. Metis stelt voor wat het kan afleiden."),
        ("Bron afronden en bouwen", "De documentcontrole bewaakt dat alle brontekst een plek heeft. Daarna bouwt Metis de kennisobjecten, letterlijk uit wat je hebt aangewezen."),
        ("Inhoudelijk beoordelen", "Een beoordelaar controleert elk kennisobject, past het zo nodig aan in dezelfde kaart en bouwt opnieuw, of wijst het af."),
        ("Publiceren", "Een bevoegde publisher geeft de goedgekeurde kennisobjecten vrij."),
        ("Gebruiken", "Een toegelaten toepassing krijgt alleen gepubliceerde kennisobjecten, met hun vindplaats in de bron."),
    )
    chain = "".join(f'<li><strong>{escape(title)}</strong><p>{escape(body)}</p></li>'
                    for title, body in steps)
    knowledge_object = page_url("begrippen", anchor="begrip-kennisstuk-kennisobject")
    return f'''<h2 id="kennisobject">Het kennisobject: de bouwsteen van Metis</h2>
      <p class="explained-intro">Een kennisobject is één uitspraak uit een bron, letterlijk overgenomen, met de tekst die nodig is om haar juist te begrijpen, de onderbouwing als de bron die geeft, het soort uitspraak, de precieze vindplaats en een eigen versie.</p>
      <p>Neem een opsomming over smetten: ‘Bij diabetes mellitus zou de huid vatbaarder kunnen zijn voor irritatie en infecties.’ Los gelezen is niet duidelijk waarover die zin gaat. Daarom hoort de inleidende zin ‘De volgende mechanismen spelen mogelijk een rol bij het risico op smetten:’ bij hetzelfde kennisobject.</p>
      <section class="explained-reading-section" id="waarom-kennisobjecten">
        <h3>Waarom alles om het kennisobject draait</h3>
        <dl class="explained-principles">
          <div><dt>Eén uitspraak, één oordeel</dt><dd>Een beoordelaar keurt geen hele richtlijn goed, maar elke uitspraak afzonderlijk. Zo valt een fout op één plek op en blijft de rest bruikbaar.</dd></div>
          <div><dt>De context reist mee</dt><dd>Doelgroep, voorwaarden en uitzonderingen zitten in het kennisobject zelf. Een toepassing kan de uitspraak dus niet los van haar voorwaarden gebruiken.</dd></div>
          <div><dt>Altijd terug te vinden</dt><dd>Elk kennisobject wijst naar de exacte bronversie en passage. Wie een antwoord krijgt, kan nagaan waar het op berust. Dat bewijst niet dat de bron zelf actueel of sterk onderbouwd is.</dd></div>
          <div><dt>Een oordeel geldt voor één versie</dt><dd>Wordt een kennisobject aangepast, dan ontstaat een nieuwe versie die opnieuw beoordeeld moet worden. Een oude goedkeuring geldt nooit stilzwijgend voor nieuwe tekst.</dd></div>
          <div><dt>Een mens beslist</dt><dd>Een voorstel van Metis, een geslaagde technische controle en een inhoudelijke goedkeuring zijn verschillende dingen. Alleen een mens keurt goed en publiceert.</dd></div>
          <div><dt>Alleen gepubliceerde kennis wordt gebruikt</dt><dd>Toepassingen krijgen alleen gepubliceerde kennisobjecten. Is er geen passend kennisobject, dan volgt geen onderbouwd antwoord in plaats van een gok.</dd></div>
        </dl>
        <p><a href="{escape(knowledge_object)}">Lees de begrippen rond het kennisobject</a></p>
      </section>
      <h2 id="zo-werkt-metis">Van bron naar bruikbare kennis</h2>
      <ol class="explained-chain" aria-label="De kennisketen">{chain}</ol>
      <section class="explained-reading-section">
        <h2>Verder lezen</h2>
        <ul class="explained-reading-links">
          <li><a href="{escape(page_url('begrippen'))}">Zoek een begrip op</a><p>Betekenis, voorbeelden en belangrijke bewijsgrenzen.</p></li>
          <li><a href="{escape(page_url('modellen'))}">Bekijk de modellen en hun verantwoording</a><p>Hoe Metis kennis ordent, welke keuzes zijn gemaakt en waar de grenzen liggen.</p></li>
          <li><a href="{escape(page_url('kennisbasis'))}">Lees over de reikwijdte van de kennisbasis</a><p>Bronkwaliteit, actualiteit en dekking zijn afzonderlijke vragen.</p></li>
        </ul>
      </section>'''


def _glossary(escape: Callable[[object], str]) -> str:
    index = "".join(f'<li><a href="#categorie-{escape(category.id)}">{escape(category.title)}</a></li>'
                    for category in SECTIONS)
    sections = "".join(f'''<section class="explained-category" id="categorie-{escape(category.id)}">
        <h3>{escape(category.title)}</h3><p class="explained-muted">{escape(category.introduction)}</p>
        {''.join(_term(term, escape) for term in category.terms)}
      </section>''' for category in SECTIONS)
    return f'''<h2>Begrippen</h2><p>Zoek bovenaan op een term of kies een onderwerp. Nederlandse termen en technische aliassen worden samen doorzocht.</p>
      <nav class="explained-topic-index" aria-label="Onderwerpen in de begrippenlijst"><ul>{index}</ul></nav>
      {sections}'''


def _models(escape: Callable[[object], str]) -> str:
    rows = "".join(f'''<li><a href="{escape(page_url('modellen', model_id=model.id))}">{escape(model.title)}</a>
        <p>{escape(model.summary)}</p></li>''' for model in MODELS)
    return f'''<h2>Modellen en verantwoording</h2>
      <p>Een model kan een inhoudelijk stelsel van afspraken zijn, zoals het kennisobjectmodel, of een AI-systeem dat voorstellen ondersteunt. Beide vragen om een eigen verantwoording.</p>
      <p class="explained-boundary">De dossiers beschrijven de aanpak en verwijzen naar systeemdocumentatie. Hun aanwezigheid bewijst niet dat een bepaalde versie in productie actief of klinisch gevalideerd is.</p>
      <ul class="explained-model-list">{rows}</ul>'''


def _model(model: Model, escape: Callable[[object], str]) -> tuple[str, str]:
    fields = (("doel", "Doel", model.purpose), ("werking", "Hoe het werkt", model.working),
              ("keuze", "Waarom deze aanpak", model.rationale),
              ("bewijs", "Onderbouwing en bewijsgrens", model.evidence),
              ("grenzen", "Beperkingen", ""),
              ("verantwoordelijkheid", "Wie is verantwoordelijk?", model.responsibility))
    sections = []
    for key, title, text in fields:
        body = ("<ul>" + "".join(f'<li>{escape(limit)}</li>' for limit in model.limits) + "</ul>"
                if key == "grenzen" else f'<p>{escape(text)}</p>')
        if key == "verantwoordelijkheid":
            body += '<p class="explained-muted">De aangewezen personen en hun mandaat moeten door de verantwoordelijke organisatie worden vastgelegd; namen zijn in dit dossier nog niet bevestigd.</p>'
        sections.append(f'<section id="model-{key}" class="explained-reading-section"><h3>{escape(title)}</h3>{body}</section>')
    reference_base = f"https://github.com/WilliamGomes41/Metis-DS/blob/{REFERENCE_REVISION}/"
    references = "".join(f'<li><a href="{escape(reference_base + reference.path)}">{escape(reference.title)}</a></li>'
                         for reference in model.references)
    terms = {term.id: term for category in SECTIONS for term in category.terms}
    related = "".join(f'<li><a href="{escape(page_url("begrippen", anchor="begrip-" + key))}">{escape(terms[key].name)}</a></li>'
                      for key in model.term_ids)
    toc = "".join(f'<li><a href="#model-{key}">{escape(title)}</a></li>' for key, title, _ in fields)
    aside = f'''<aside class="explained-toc"><nav aria-label="Op deze modelpagina"><strong>Op deze pagina</strong><ul>{toc}<li><a href="#model-bronnen">Bronnen en verwante begrippen</a></li></ul></nav></aside>'''
    content = f'''<a class="explained-back" href="{escape(page_url('modellen'))}">Alle modellen</a>
      <h2>{escape(model.title)}</h2><p class="explained-intro">{escape(model.summary)}</p>
      <dl class="explained-status"><div><dt>Deze beschrijving</dt><dd>Versie 1 · ter inhoudelijke beoordeling</dd></div><div><dt>Operationeel gebruik</dt><dd>Niet vastgesteld op deze pagina</dd></div></dl>
      {''.join(sections)}
      <section class="explained-reading-section" id="model-bronnen"><h3>Bronnen en verwante begrippen</h3>
        <p>De verwijzingen horen bij de vastgelegde systeemversie waarop deze beschrijving is gebaseerd. Zij zijn geen actuele productiecontrole.</p>
        <ul class="explained-reference-list">{references}</ul>
        <h4>Verwante begrippen</h4><ul class="explained-related">{related}</ul>
      </section>'''
    return content, aside


def _collection() -> str:
    return '''<h2>De kennisbasis</h2>
      <p class="explained-intro">De bruikbaarheid van de kennisbasis hangt af van wat zij dekt, hoe actueel de bronnen zijn en voor welke situaties de kennis bedoeld is.</p>
      <section class="explained-reading-section"><h3>Omvang is iets anders dan dekking</h3>
        <p>Meer kennisobjecten betekent niet vanzelf dat meer praktijkvragen verantwoord kunnen worden beantwoord. Bekijk per vraag welke onderwerpen, doelgroepen en zorgsettings worden gedekt.</p>
      </section>
      <section class="explained-reading-section"><h3>Bronnen behouden hun eigen status</h3>
        <p>Een richtlijn, handreiking en artikel hebben ieder hun eigen doel en onderbouwing. De plaats in Metis maakt die bronnen niet onderling gelijkwaardig. Gebruiksrechten bepalen mede welke verwerking en levering zijn toegestaan.</p>
      </section>
      <section class="explained-reading-section"><h3>Actualiteit vraagt onderhoud</h3>
        <p>Een nieuwe bronversie kan gevolgen hebben voor bestaande kennis. Beoordeling, vervanging en intrekking moeten herkenbaar blijven. Een oude beoordeling is geen bewijs dat een nieuwe bronversie al is verwerkt.</p>
      </section>
      <section class="explained-reading-section"><h3>Wat is hier vastgesteld?</h3>
        <p>Deze uitleg toont geen live collectieaantallen, lijst van opgenomen richtlijnen of actueel dekkingsrapport. Zulke gegevens moeten uit een actueel, bevoegd collectieoverzicht komen. Hun afwezigheid hier zegt niet dat de collectie leeg is.</p>
        <p class="explained-boundary"><strong>Bij onvoldoende onderbouwing.</strong> Een vraag kan buiten de beschikbare of toegestane kennis vallen. Dan mag een ontbrekend antwoord niet worden ingevuld alsof er wel passende onderbouwing bestaat.</p>
      </section>'''


def render(escape: Callable[[object], str], *, section: str = "start",
           query: str = "", model_id: str = "") -> str:
    """Only known content IDs can select pages. Query is always rendered escaped."""
    if section not in dict(PAGES):
        raise ValueError("Onbekend onderdeel")
    if model_id and (section != "modellen" or model_id not in {m.id for m in MODELS}):
        raise ValueError("Onbekend model")
    query = query.strip()
    toc = ""
    if query:
        hits = search(query)
        count = len(hits)
        rows = "".join(f'''<li><span class="explained-result-kind">{escape(hit.kind)}</span>
          <h3><a href="{escape(hit.url)}">{escape(hit.title)}</a></h3><p>{escape(hit.description)}</p></li>''' for hit in hits)
        content = f'<h2>Zoekresultaten voor “{escape(query)}”</h2><p>{count} ' + ('resultaat' if count == 1 else 'resultaten') + ' in begrippen en modellen.</p>'
        if hits:
            content += f'<ul class="explained-search-results">{rows}</ul>'
        else:
            content += '<p>Geen uitleg gevonden. Probeer een kortere zoekterm of een verwant begrip.</p>'
        content += f'<p><a href="{escape(page_url("begrippen"))}">Bekijk alle begrippen</a> of <a href="{escape(page_url("modellen"))}">bekijk alle modellen</a>.</p>'
    elif section == "start":
        content = _overview(escape)
    elif section == "begrippen":
        content = _glossary(escape)
    elif section == "modellen" and model_id:
        content, toc = _model(next(m for m in MODELS if m.id == model_id), escape)
    elif section == "modellen":
        content = _models(escape)
    else:
        content = _collection()
    navigation = "".join(f'<li><a href="{escape(page_url(key))}"' +
                         (' aria-current="page"' if key == section and not query else '') +
                         f'>{escape(title)}</a></li>' for key, title in PAGES)
    return f'''<section class="room explained-room">
      <header class="explained-header"><h1>Metis uitgelegd</h1>
        <p>Hoe kennis wordt gevormd, beoordeeld en verantwoord.</p>
        <form class="explained-search" method="get" action="/over-console" role="search" aria-label="Zoek in de uitleg">
          <label for="metis-explained-query">Zoek een begrip, model of onderwerp</label>
          <div><input type="search" id="metis-explained-query" name="q" value="{escape(query)}" maxlength="200" placeholder="Bijvoorbeeld brontrouw of beslisboom"><button class="btn-primary" type="submit">Zoeken</button></div>
        </form>
      </header>
      <a class="explained-skip" href="#uitleg-inhoud">Naar de inhoud</a>
      <div class="explained-layout{' explained-with-toc' if toc else ''}">
        <nav class="explained-nav" aria-label="Over Metis"><ul>{navigation}</ul></nav>
        {toc}<main class="explained-content" id="uitleg-inhoud" tabindex="-1">{content}</main>
      </div>
    </section>'''
