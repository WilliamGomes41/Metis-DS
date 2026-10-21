# Metis

Metis helpt V&VN om richtlijnen en andere brondocumenten om te zetten in kennis die mensen kunnen beoordelen, publiceren en terugvinden. Bij ieder kennisobject blijft zichtbaar uit welke bronpassage het komt en welke context erbij hoort.

## Van bron naar gepubliceerde kennis

1. **Inleveren** — het brondocument wordt opgeslagen. Verwerking start afzonderlijk.
2. **Bronselectie** — Metis verwerkt de bron en stelt passages en kennisobjecten voor.
3. **Review** — bevoegde beoordelaars controleren de inhoud, bronverwijzingen en context. Onopgeloste broninhoud blijft zichtbaar als werk.
4. **Publicatie** — gecontroleerde kennis wordt na de vereiste beoordelingen en controles beschikbaar gemaakt.
5. **Ontsluiting** — andere toepassingen kunnen gepubliceerde kennis via de Product API opvragen.

Automatische verwerking kan voorstellen doen, maar geeft geen toestemming om te publiceren. Als vereist bewijs of beoordeling ontbreekt, blijft publicatie geblokkeerd. Nieuwe versies behouden de geschiedenis van eerder gepubliceerd werk.

## Gebruiken en koppelen

Onderzoekers, reviewers en publishers werken in de Metis-webomgeving, ieder met eigen bevoegdheden. Via **Documenten** kunnen zij hun documenten en voortgang terugvinden.

- [Microsoft-aanmelding](docs/ENTRA_SIGN_IN.md) — inrichting en toegang.
- [ChatGPT-koppeling](docs/METIS_CHATGPT_MCP.md) — documenten onderzoeken via MCP, alleen lezen en binnen de eigen documentrechten. Externe configuratie is vereist.
- [Product API](docs/product-api/CONSUMER_GUIDE_V1.md) — gepubliceerde kennis beschikbaar maken aan andere toepassingen.

## Verder lezen en bijdragen

- [Protocol](PROTOCOL.md) — productafspraken en blijvende eisen.
- [Roadmap](ROADMAP.md) — veranderopgaven en acceptatievoorwaarden.
- [GitHub Issues](https://github.com/WilliamGomes41/Metis-DS/issues) — actuele werkzaamheden en voortgang.
- [Codeaudit](docs/audit/README.md) — voortgang van de auditbevindingen A01–A27.
- [Repositoryafspraken](docs/REPOSITORY_CONVENTIONS.md) en [werkinstructies voor agents](AGENTS.md) — voor ontwikkelaars.

De code op `main` laat zien wat is gemerged. Of een wijziging ook in de liveomgeving draait en daar is geaccepteerd, moet afzonderlijk worden vastgesteld. Historische rapporten staan in [docs/history](docs/history/).
