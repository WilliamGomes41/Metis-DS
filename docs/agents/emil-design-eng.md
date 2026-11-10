# Emil Design Engineering in Metis

De expliciet gevraagde skill staat ongewijzigd in
[`.agents/skills/emil-design-eng/SKILL.md`](../../.agents/skills/emil-design-eng/SKILL.md).
Installatie is uitgevoerd met de aangevraagde skills-CLI, voor Codex en alleen in
dit project. Er zijn geen applicatieafhankelijkheden of animatiebibliotheken toegevoegd.

Bron: [emilkowalski/skills](https://github.com/emilkowalski/skills), commit
`715c1807e08c497cfd1dc4feb450a2a3300ef2a9`, MIT. Het oorspronkelijke bestand en
de behouden licentie zijn vastgelegd met SHA-256 in
[`config/emil_design_eng.v1.json`](../../config/emil_design_eng.v1.json).
De door de installer gemaakte [`skills-lock.json`](../../skills-lock.json) blijft
behouden. Zijn `computedHash` is installer-metadata; de bytecontrole gebruikt het
afzonderlijke manifest en wijzigt die installerwaarde niet.

## Toepassing

Gebruik deze skill wanneer de gebruiker haar aanroept of wanneer precieze
interactie, componentfeedback, toegankelijkheid of motion-vraagstukken daartoe
aanleiding geven. Ze vult de verplichte [Impeccable-richtlijnen](impeccable.md) aan.
Bronidentiteit, annotatie-invarianten, autorisatie, review en publicatie blijven
onder de bestaande Metis-contracten vallen. Een skill verleent geen toestemming
voor extra publicatie, deployment, automatische merges of domeinwijzigingen.

Voor de annotatiewerkplek betekent dit: betekenisvolle standaardkeuzes, één
primaire actie per taak, onmiddellijke maar waarheidsgetrouwe feedback,
toetsenbordbediening zonder wachttijd, touch zonder hover-afhankelijkheid en
respect voor reduced motion. De bestaande Metis-vormgeving blijft leidend.
Herhaalde tekstselecties krijgen geen decoratieve animatie. Tijdelijke meldingen
mogen een blijvende opslagfout of een open inhoudelijke keuze niet verbergen.

De skill beveelt React/Motion-voorbeelden en visuele effecten aan waar passend.
Dat is geen reden om de huidige server-HTML/JavaScript-werkplek te vervangen of
nieuwe dependencies toe te voegen. Bij review gebruiken we de voorgeschreven
`Before | After | Why`-tabel. Voor dit ontwerp staat die vergelijking in het
[architectuurvoorstel](../architecture/annotation-workplace-guided.md).

## Bijwerken en controle

Een nieuwe upstreamversie wordt eerst inhoudelijk beoordeeld, daarna worden
bestand, broncommit, licentie en hashes samen bijgewerkt. De `@latest`-opdracht
zelf is geen reproduceerbare versiepin; de vastgelegde commit en hashes zijn dat.

```sh
python -m pytest -q tests/test_emil_design_eng_install.py
```

Deze controle is offline. Zij bewijst installatie-integriteit en documentlinks,
geen bruikbaarheid van een gerealiseerde interface. De skill is beschikbaar
voor agents die projectskills lezen; dit registreert geen extra plugin in een
lopende gehoste chatsessie.
