# Historische annotaties in het documentoverzicht

GitHub #1106 · Linear MET-112 · Eerste implementatiestap

Bij de overgang op 15 november werd voor één document opnieuw inleveren voorzien. De melding in build 1.1.589 is lokaal gereproduceerd met het formaat van vóór migratie 042. Het betrokken productierecord is niet onderzocht.

## Besluit en ontwerp

GO projectlead, 20 november 2026: leg het verbeter­voorstel vast in GitHub en Linear en start de implementatie. Het werkpakket omvat ook expliciete afhandeling van inhoudelijke oude besluiten en herstel van historische back-ups. Deze eerste stap maakt het overzicht bruikbaar en laat een medewerker een gecontroleerde neutrale selectie opslaan.

Een migratie van de bestaande JSON zou de hashes van revisies, opdrachten en verzegelde bouwinvoer raken. Daarom leest het overzicht de oorspronkelijke revisie en controleert de bron op een tijdelijke kopie. Bij een neutrale annotatie gaat de gecontroleerde selectie via de bestaande schrijfopdracht naar een opvolgende revisie. Er is geen bulkbewerking of automatische opslag bij openen. Bij een inhoudelijke oude keuze toont het overzicht de vastgelegde informatie. De schrijfroute controleert de oorspronkelijke kop onder het bestaande transactieslot. Een nieuw seal vereist dat alle huidige annotatiekoppen het actuele contract volgen.

## Change contract

Change class: A
Promise: Een onderzoeker kan historische annotaties terugvinden en een neutrale annotatie onder dezelfde identiteit voortzetten.
Proof: Geauthenticeerd HTTP, native PostgreSQL vóór en na migratie 042, herstart, echte opbouw na neutrale correctie en expliciete afwijzing van overschrijven van een essentieel verband. Vaste voorbeelden zijn gegenereerd met de validatie en opslagrepresentatie van de ouder van f33ea688.
Touches lifecycle invariants: yes
Rewrite risk: high
Rewrite target: de interpretatie van opgeslagen historische invoer tijdens levende documentcontrole.
Why local patching is insufficient: de kaart, de schrijfopdracht en de controle vóór afsluiten moeten hetzelfde onderscheid maken. Een marker-only v2-concept faalt zelfs na het weghalen van lege velden.
Current authority/writer/reader map: annotation_versions en annotation_heads bevatten de invoer. save bewaakt revisie en generatie. inspect_for_overview projecteert de actuele koppen. finalize controleert het overzicht en de vastgelegde basis. De materialisatie en herstelcontrole roepen de strikte inspect_document aan.
Supported runtime topologies: PostgreSQL-workflowopslag met migratie 042. Lokale proeven gebruiken native PostgreSQL en de productiecompositie met synthetische bronnen.
Persisted-state impact: de gewone opslagopdracht kan een nieuwe huidige revisie toevoegen voor een neutrale kop. De oude payload en hash blijven in de geschiedenis.
Compatibility/migration plan: eerst lezen en gecontroleerd hervatten, daarna betekenisvolle oude koppelingen expliciet afhandelen en oude archieven onder het oorspronkelijke contract herstellen. Deze stap voegt geen SQL-migratie toe.
Rollback/recovery plan: terugzetten van de applicatie laat nieuwe revisies leesbaar via het huidige formaat. De oude versie kan opnieuw vastlopen op historische koppen. Herstel van een archief met zulke revisies valt onder de volgende stap en moet vóór productie-uitrol met een lege database worden bewezen.
Cutover trigger: afzonderlijke review, bewijs van de vervolgstappen en apart uitrolbesluit.
Cleanup/decommission criteria: de leesondersteuning blijft nodig zolang een ondersteunde historie of een ondersteund archief deze vorm kan bevatten.
Failure blast radius: de weergave en voortzetting van oude annotaties. Een weergave mag geen bouw of publicatie vrijgeven.
Adversarial proof matrix: gewijzigde hash, verschoven citaatgetuige, onbekend veld, v2-downgrade, echte oude beslissing, direct POST naar opslaan en directe finalize. Een gewone nieuwe revisie blijft bouwbaar.
Lifecycle entity: annotatiekop en verzegelde invoer voor een WorkingRevision.
Lifecycle transition: historische kop lezen, gecontroleerde neutrale selectie als opvolger opslaan, daarna via bestaande afsluiting naar opbouw.
Initial durable state: een opgeslagen pre-042-kop en optioneel huidige annotaties in hetzelfde document.
Trigger: documentoverzicht openen, de selectie controleren en opslaan, of expliciet afsluiten.
Authorization: bestaande onderzoeker of aangewezen deelnemer via de huidige routes.
Validation: opgeslagen hash, brongetuigen, oorspronkelijke revisie, documentgeneratie en actueel objectfront.
Mutable entities: de bestaande opslagopdracht maakt een nieuwe annotatieversie en verplaatst de kop.
Immutable entities: bestaande revisies, bron, eerder verzegelde bouwinvoer en gepubliceerde versies.
Workflow state before: document met een historische annotatiekop.
Workflow state after: na bekijken dezelfde generatie; na geslaagde correctie een nieuwe revisie en generatie.
Release state before: bestaande publicatiestatus.
Release state after: een leesactie en annotatiecorrectie geven geen release uit.
Serving state before: de laatst geactiveerde publicatie.
Serving state after: publicatieregister blijft eigenaar van de uitlevering.
Expected API result: overzicht 200, actuele neutrale correctie via het bestaande opslagcontract, overschrijven van een historische beslissing 409.
Expected UI result: eerdere annotaties herkenbaar per kaart, neutrale selectie kan na controle worden opgeslagen, een oude inhoudelijke beslissing is alleen leesbaar.
Failure result: een ongeldige getuige of payload blijft een fout; een geweigerde correctie maakt geen revisie of seal.
Restart result: dezelfde historische revisie blijft zichtbaar en een geaccepteerde opvolger doorloopt de normale bouwroute.
Recovery result: het pad voor archiefherstel gebruikt de bestaande strikte controles. Ondersteuning voor archieven van vóór 042 is afzonderlijk te bewijzen.
Legacy-data result: oude velden in gekoppelde en open bereiken, lege v2-concepten, teruggenomen annotaties, essentiële verbanden en terugnameredenen worden in het overzicht herkend.
Required black-box scenario: oud concept vastleggen, 042 toepassen, herstarten, gemengd document openen, downgrade weigeren en geldige opvolger onder dezelfde annotatie-ID opslaan.
Explicit non-goals: productie-uitrol, directe databaseconversie, automatisch laten vervallen van een historische keuze en herinterpretatie van bestaande publicaties.
