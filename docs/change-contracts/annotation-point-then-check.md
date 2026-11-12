# Aanwijzen, daarna alleen open punten

Change class: B
Promise: Na één bronselectie ziet de annotator alleen nog de punten die Metis niet zelf brongetrouw kon invullen, als gerichte vraag; daarna rondt de annotator met één handeling af.
Proof: Native browser/PostgreSQL-proef: selectie → voorstel → nul bevindingen → direct naar afronden zonder veldformulier; en selectie → dubbelzinnig voorstel → precies één zichtbare vraag bij het betreffende onderdeel.
Touches lifecycle invariants: no
Rewrite risk: none

Opdracht William, 12 november 2026: maak het change contract. Dit is nog geen
implementatie-GO. GitHub-issue en Linear-werkpakket moeten nog worden toegewezen;
hernoem dit bestand dan naar het issuenummer.

Vervolg op [#1055](1055-meaning-proposals.md) en
[#1051](1051-guided-annotation-workspace.md). Dit contract dekt stap 1 en 2 uit
het onderzoek van 12 november. Stap 3 (omliggende bron in de modelcall) en stap 4
(automatisch gereed, bouw per passage) vallen erbuiten en krijgen een eigen contract.

## Wat de mens doet

| Wie | Expliciete handeling | Vervalt als normale route |
| --- | --- | --- |
| Annotator | 1. Volledige uitspraak aanwijzen. 2. Een gestelde vraag beantwoorden, alleen als die er is. 3. Afronden. | Type kiezen, betekenisvelden nalopen, zinsdelen opnieuw aanwijzen |
| Reviewer | Ongewijzigd: drie vragen op de bestaande kaart | — |

De handmatige veldbediening blijft bestaan achter één secundaire actie ‘Zelf
corrigeren’, voor correcties en provideruitval. Zij is geen tweede route met
eigen opslag: dezelfde editor, dezelfde payload, dezelfde save.

## Grens: de reviewpagina verandert niet

Deze slice wijzigt niets in `src/review/` en niets aan
`_source_bound_fields_html`. Onderzocht op `main` `5b3b6cb`: de kaart toont al
de letterlijke kern, type, richting en sterkte, de samenvattingstabel
(doelgroep, voorwaarde, uitzondering, onderbouwing) met een statusregel per
waarde, en in het uitklapdeel alle velden met ‘Onzeker’ of ‘Niet expliciet
vermeld’. Zolang de annotator zelf afrondt, is de annotator verantwoordelijk
voor elk onderdeel; een aparte herkomst ‘door model voorgesteld’ voegt voor de
reviewer dan niets toe en wordt niet opgeslagen of getoond.

Regel voor de vervolgstappen: de reviewkaart krijgt geen nieuwe secties, vragen
of knoppen. Mocht stap 4 herkomst nodig maken, dan uitsluitend als tekst in de
bestaande statusregel van de samenvattingstabel, naast het al bestaande
‘Voorstel, nog niet bevestigd’. Dat besluit hoort bij het contract van stap 4.

## Program-design gate

- **Bestaand mechanisme en autoriteit:** selectie → `annotations.save` (CAS,
  receipts) → `POST /annotations/suggest` (readonly, één providercall) →
  client zet voorstel in de draft → save → `GET /annotations/check`
  (`inspect_annotation`) → expliciete `ready`-save. De kernel is de enige
  schrijver; `materialise_knowledge_candidates` de enige kandidaatmaker.
- **Gedragswijziging:** (1) na een voorstel leest de client de bestaande
  controle; bij nul bevindingen opent taak 3 met de afrondactie, zonder
  veldformulier. (2) Het voorstelantwoord benoemt per onderdeel waarom het niet
  gebonden is, zodat de client één gerichte vraag toont in plaats van een stil
  ‘onzeker’.
- **Geraakte functies:** `human_annotation_suggestion_v1.bind_quote`,
  `bind_proposal`, `suggest` (extra antwoordsleutel `open_points`);
  `human_annotation_editor.js` (`proposeMeaning`, `showTask`, `renderFields`,
  `runCheck`); `human_annotation_ui_v1` (copy en de secundaire actie).
- **Mag muteren:** de draft-annotatie via de bestaande save. **Blijft gelijk:**
  payloadvorm en `selection_version`, schema, `_validate`, `inspect_annotation`,
  `inspect_document`, seal/build, materialisatie, toelating, review en publicatie.
- **Ongewijzigd gedrag:** niets wordt automatisch gereed gemeld; onderbouwing
  ‘niet van toepassing’, essentialiteit en ontbreekredenen worden nooit
  automatisch gekozen; stale voorstel wordt geweigerd; geen automatische retry.
- **Kleinste bewijs:** de twee browserproeven uit `Proof`.

## Open punten in het voorstelantwoord

`open_points` is een lijst `{field, reason}` in het antwoord van de readonly
query. Zij wordt niet opgeslagen en is geen nieuwe autoriteit of status.

| Reden | Wanneer | Vraag aan de annotator |
| --- | --- | --- |
| `quote_ambiguous` | Quote komt meer dan eens voor in de kern | Welke van deze plaatsen bedoelt de bron? (de plaatsen worden getoond) |
| `quote_not_in_selection` | Quote staat niet letterlijk in de kern | Wijs dit onderdeel aan of kies een ontbreekreden |
| `type_unclear` | `object_type` is `null` | Welk type uitspraak is dit? |
| `model_uncertain` | Model gaf zelf `uncertain` | Wijs dit onderdeel aan of kies een ontbreekreden |

De gebonden waarde blijft in al deze gevallen `uncertain`, zoals nu. Alleen de
reden wordt zichtbaar. Bevindingen uit `GET /annotations/check` blijven de
enige bron voor wat nog open staat vóór afronden; `open_points` verklaart
alleen waarom het voorstel iets openliet.

## Stateful overlay

Domain entity/aggregate: annotatie binnen de bestaande annotatieset.
Invariant(s): immutable bron, exacte bronspans, draft tot menselijke afronding, één kandidaatmaker, bestaande toelating/review/publicatie.
Durable state before: draft met kernselectie.
Durable state after: dezelfde draft met voorgestelde velden via de bestaande save; daarna `ready` uitsluitend na de menselijke afrondhandeling. Geen nieuw veld, geen nieuwe tabel.
Transaction boundary: ongewijzigd; voorstel- en controlequery schrijven niets, elke save is de bestaande atomische kerneltransactie.
Failure/recovery result: bij providerfout, timeout of ongeldig voorstel blijven kern en bestaande velden bewaard en opent ‘Zelf corrigeren’; herladen leest alleen bevestigd werk.
Duplicate execution / idempotency result: queries zijn readonly; save houdt de bestaande command receipts.
Concurrency result: ongewijzigd; basis- en revisiecontrole vóór en na de providercall, CAS bij save, controle alleen geldig voor de gecontroleerde revision.
Audit/evidence requirement: bestaande immutable annotatieversies en receipts; `open_points` is vluchtig en geen bewijs.

## Risico en bewijs

| Risico | Bewijs |
| --- | --- |
| Verborgen velden verbergen een open punt | Afronden blijft alleen mogelijk na een actuele controle met nul bevindingen; proef met een voorstel dat één verplicht veld mist toont dat veld en blokkeert afronden |
| Annotator rondt af zonder te zien wat is ingevuld | Taak 3 toont de bestaande leesbare samenvatting (kern, type, onderdelen met bronplaats) vóór de afrondknop |
| Dubbelzinnige quote bindt aan de verkeerde plaats | `bind_quote` blijft weigeren bij meer dan één treffer; unittest per reden in `open_points` |
| Handmatige route raakt onbereikbaar | Browserproef: providerfout → ‘Zelf corrigeren’ → handmatig aanwijzen → afronden |
| Reviewkaart wijzigt ongemerkt | Bestaande goldens en reviewproeven blijven ongewijzigd groen; diff bevat geen bestand onder `src/review/` |

Frontend valt onder Impeccable en de Emil-skills volgens `AGENTS.md`. Technisch
bewijs meet geen lagere werklast en geen inhoudelijke juistheid van live
modeluitvoer; dat vraagt de praktijktoets met een bevroren referentie.

## Buiten deze slice

- Omliggende bron naar het model; context of onderbouwing buiten de kern zoeken.
- Automatisch gereed melden, bouw per passage, een derde toestand voor onderbouwing.
- Rollen en veldbindingen samenvoegen; `pending_range` of `required_links` wijzigen.
- Elke wijziging aan de reviewkaart, de bon of het documentoverzicht.
