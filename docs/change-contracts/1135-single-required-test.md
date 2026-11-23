# Eén verplichte CI-teststatus voor Metis

Change class: C
Promise: G1 vereist één teststatus die alleen slaagt na volledig productiegericht testbewijs, het bestaande browserbewijs en de gerichte Python 3.12-proeven.
Proof: Gedragstests voor de eindcheck en de omschakeling, versiecontroles over de releasepaden, de echte Docling-imageproef op de exacte PR-head en native readback na aanpassing van G1.
Touches lifecycle invariants: no
Rewrite risk: none

Werkpakket [GitHub #1135](https://github.com/WilliamGomes41/Metis-DS/issues/1135) · [Linear MET-133](https://linear.app/metis-phoenix/issue/MET-133). De projectlead gaf op 22 november 2026 in de sessie de opdracht **Richt in** voor de afgesproken consolidatie. De PR volgt het bestaande Forge-controlerapport en het afzonderlijke mergebesluit. [Uitvoeringscontract](../agents/execution-contract.md)

## Eén uitslag

De vier suiteshards, preflight en het bestaande browserbewijs draaien op Python 3.13. Het releasecommando in `scripts/build_azure_release_image.sh` selecteert `Dockerfile.docling --target runtime`. Die stage en de daarvan afgeleide acceptance-stage gebruiken Python 3.13, net als het losse Docling-acceptatieimage, de Docling-testhost en het Product API-image. De ZIP-route accepteert `PYTHON|3.13`. Daarom gebruikt de job `package` Python 3.13, selecteert de ZIP-bouwer `cp313`- en compatibele `abi3`-wheels en draait de importproef op Python 3.13.

De characterization-job draait op Python 3.12 en controleert daar de workercompatibiliteit, het Docling-contract en de Product API-contractguard. De echte Docling-proef MOET op Python 3.13 de vastgelegde CPU-wheels, het lockbestand, `pip check`, de modelvoorbereiding, Chromium en de verpakte PDF-keten uitvoeren. Als die proef faalt, MOET de geaggregeerde `test` ook de volledige vier suiteshards, het browserbewijs en de PostgreSQL-proeven op Python 3.12 vereisen. [CI-workflow](../../.github/workflows/ci.yml) · [Docling-acceptatie](../../.github/workflows/docling-acceptance.yml)

**OPENVRAAG** De actuele Azure-hosting is niet geverifieerd. De repository beschrijft een afzonderlijke eerste containerovergang met eigen rollback- en capaciteitsbewijs. [Azure-releaseprocedure](../AZURE_RELEASE_RUNBOOK.md)

De enkelvoudige job `test` accepteert uitsluitend vier geslaagde afhankelijkheden. Daarna controleert hij het volledige suiteshardbewijs en de bestaande PostgreSQL-bewijsexport. Het browserbewijs omvat de bestaande Review- en Vorming-proeven. Nieuwe gedragsproeven uit het UX-ontwerp horen bij de wijzigingen die dat productgedrag realiseren. De twee tijdelijke contextnamen geven precies de uitslag van `test` door. Daarmee blijven de huidige vereiste contextnamen beschikbaar tijdens de overstap.

## Overgang van G1

1. Laat de PR en de exacte head controleren. Verifieer dat `test` en beide tijdelijke statusnamen verschijnen en groen worden. Gebruik een gecontroleerde falende of overgeslagen proef om de afwijzende route vast te stellen.
2. Merge via de bestaande projectafspraak. Controleer vervolgens op de actuele `main`-commit dat `test` met succes is afgegeven door GitHub Actions. Lees daarna een verse snapshot van G1 met `gh api repos/WilliamGomes41/Metis-DS/rulesets/21686159`.
3. Genereer op die snapshot het vervangingsvoorstel met `python scripts/check_github_merge_policy.py --ruleset <snapshot.json> --plan --retire-legacy-test-checks`. De expliciete vlag retireert alleen de twee benoemde contexten met de verwachte integratiebinding. De beheerder houdt de snapshot beschikbaar voor herstel en past de vervanging in één wijziging toe. G1 vereist dan `test` en `handoff-contract` naast eventueel onafhankelijk toegevoegde checks.
4. Lees G1 na toepassing opnieuw terug en draai de validator zonder `--plan`. Verifieer ook in GitHub dat een proef-PR zonder geslaagde `test` niet kan mergen. Schrap daarna de tijdelijke statusnamen met een kleine vervolgwijziging. Tot dan kan de beheerder de oorspronkelijke contexten terugzetten.

G1 blijft de mergeautoriteit. De bestaande regel voor actuele branches, opgeloste reviewthreads, checkbron en afwezigheid van bypass blijft gelden. De projectlead behoudt het beheer van de gate en beoordeelt wijzigingen in de test- en workflowdefinities. De planner schrijft alleen een voorstel. [Live G1](https://github.com/WilliamGomes41/Metis-DS/rules/21686159) · [G1-validator](../../scripts/check_github_merge_policy.py) · [Bestaand governancebesluit](1087-native-merge-policy.md)
