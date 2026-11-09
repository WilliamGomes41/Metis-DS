# HA-4 — gedeelde documentstructuur losmaken van AI-proza

Change class: C — niet-semantische verplaatsing van een pure helper.
Rewrite risk: none
Promise: De menselijke bouwer gebruikt een gedeelde documentstructuurhelper zonder die uit de oude AI-prozamodule te halen; uitvoer en kandidaatidentiteit blijven gelijk.
Proof: Drie vóór verplaatsing vastgelegde envelopehashes en één hash van de werkelijke menselijke materialisatie/transform/Admission-uitvoer; bestaande gerichte regressietests en repositorychecks.
Touches lifecycle invariants: no

Part of #1017 / MET-61. William vroeg op 9 november 2026 om de HA-4-acties
daadwerkelijk uit te voeren. Deze kleine voorbereidende codewijziging maakt
geen cutover, providerverwijdering, deployment of menselijke praktijkacceptatie.
De oude planninglabels vervangen die expliciete opdracht niet.

## Bestaande route en beperkte wijziging

Op main `c985eaf376f4c686851f198f526510ca32e98b9e` zijn er twee callers van
`pre_review_semantic_v1.document_spec`: `semantic_spec_from_fragments` in
dezelfde module en `human_annotation_materialisation_v1.build_objects`.
De helper bouwt alleen een structureel documentobject en enveloppe rond al
gematerialiseerde units. Hij schrijft niets en bepaalt geen kandidaattekst,
identiteit, bronbinding, reviewrecht of workflowstatus.

Verplaats de functie ongewijzigd naar `src/vorming/document_spec_v1.py`.
Beide callers importeren dezelfde functie. De oude module importeert haar
voorlopig als dezelfde naam, zodat de bestaande semantische route werkt;
er is één implementatie. Dat importpad verdwijnt met de latere verwijdering
van de prozamodule. De boomconstructie heeft een eigen bestaand speccontract
en wordt niet in deze verplaatsing betrokken.

Invoer/uitvoer, unitvolgorde, unitreferenties, Unicode, document-ID, versie en
topicvelden blijven gelijk. `materialise_knowledge_candidates` blijft de enige
kandidaatmaker; bestaande transform, Admission en opslag blijven eigenaren.
Geen durable state of autoriteit verhuist. Transacties, concurrency, retries,
herstel en schema krijgen hier geen nieuwe semantiek.

## Bewijs en grenzen

`tests/test_document_spec_v1.py` legt vóór wijziging drie canonieke JSON-hashes
vast: leeg document, menselijke selectie met context/Unicode en modelselectie
met meerdere units. Een vierde test doorloopt de echte pure menselijke
inspectie/materialisatie/transform/Admission-keten met bestaande fixtures.
Die test schakelt uitsluitend de oude `document_spec`-referentie uit en eist
dezelfde eindobjecthash. Dat bewijst deze ontkoppeling, niet dat alle andere
human-/bronhelpers al onafhankelijk van de oude module zijn.

Native PostgreSQL, volledige browserketen en de latere cutovervoorwaarden
blijven waar toepasselijk afzonderlijke bewijzen. Deze verplaatsing bevat
geen productie- of datamigratie; terugdraaien betreft alleen imports en code.
Het productcompositiediagram behoeft geen wijziging: de opslag-, schrijf-,
lees-, review- en servingroutes en de deploytopologie blijven gelijk.

## Uitgevoerd bewijs — 9 november 2026

- Nieuwe ontkoppelingstest vóór de verplaatsing: rood op de bedoelde oude
  helperaanroep; na verplaatsing groen met gelijke eindobjecthash.
- De functie-AST is identiek aan de oorspronkelijke functie op bovenstaande
  main. De drie envelopehashes en kandidaatobjectreferenties blijven gelijk.
- 75 gerichte tests geslaagd: nieuwe helper + menselijke materialisatie (6),
  bestaande pure broninspecties (5), bestaande semantische selectie/fail-closed
  proeven (3), boomvoorstellen (20), release-control (35), architectuurinvarianten (6).
- Repositorypreflight PASS (2312 bestanden), architectuurgrenzen PASS,
  compileall PASS, diffcheck PASS en release-control op alle vijf wijzigingspaden PASS.
- De volledige lokale suite is geprobeerd maar kon niet starten: PostgreSQL 16
  ontbreekt. Ook de gemengde previewmodule bevat native tests en weigerde daarom
  zonder database te starten; de vijf afzonderlijk geselecteerde pure inspecties
  hierboven zijn wel uitgevoerd. Geen PostgreSQL-skip als PASS geteld.
- De Python-testafhankelijkheden zijn in een lokale virtualenv geïnstalleerd.
  Systeminstallatie van PostgreSQL kon niet via sudo: sudo ontbreekt. De
  bestaande native/full-suite-CI blijft nodig vóór merge; er is geen
  productieomgeving aangepast.
