# Dataopslag en versiegebonden bewijscontrole

Status: PStack-ontwerp voor #1023 / P-MET-7, 8 november 2026. Geen productiegegevens of broncitaten. Geen productie- of Azure-proef uitgevoerd.

## Belofte en harde grens

Een bevoegde tweede persoon opent één exacte KO-versie en kan de letterlijke geselecteerde tekst, bronversie, rol van elke passage, gevormde inhoud, reviewbesluiten en historische publicatiestatus controleren. De bestaande Azure PostgreSQL- en Blob-opslag blijven de enige toegestane duurzame plaatsen voor productgegevens. De huidige ingest-reviewconfiguratie blijft gelden. Dit is een projectgrens, geen hier bewezen juridische uitspraak.

De gebruikersroute is: kies exact object-ID plus objectversie, eventueel release-ID; toon een tijdelijke geautoriseerde bewijsweergave; controleer gepinde hashes en verwijzingen; rapporteer ontbrekende of afwijkende schakels. Een live browserweergave is geen nieuwe duurzame opslag of bewijsautoriteit. Er komt geen nieuwe tekstexport buiten de toegestane Azure-grens.

Voorgestelde domeinoperaties, nog geen bestaande functies:

- inspect_object_version(actor, object_id, object_version) -> EvidenceView | EvidenceFailure
- inspect_release_object(actor, release_id, object_id, object_version) -> EvidenceView | EvidenceFailure
- verify_evidence_in_place(exact_ref) -> IntegrityFindings

EvidenceView onderscheidt source_quote, formed_text, annotation_proposal, confirmed_review en historical_release van current_serving. De browser levert geen eigen canonieke tekst of afgeleide status terug. De lezer mag geen annotatie, kandidaat, review, publicatie of herstelbesluit schrijven.

## Ground: bestaande eigenaren

| Feit | Autoriteit | Consequentie |
| --- | --- | --- |
| Bronbytes | Bestaande immutable Azure Blob-bronstore met hash/locator in PostgreSQL | Verifieer de gepinde snapshot; geen quote-search in de nieuwste bron. |
| Geaccepteerde extractie en bronblokken | workflow.prepared_extraction_versions en bronviews in PostgreSQL | Lees extractiehash, blok-ID, halfopen codepointbereik en quotegetuige. |
| Researcherkeuzes | workflow.annotation_sets, annotation_versions en annotation_heads | Oude versies zijn append-only; de actuele head bewijst niet wat eerder gebouwd is. |
| KO-versie | Enige materialiser, workflow.document_objects en na publicatie canonical_object_versions | Exacte annotation-revisie → objectversie/hash-binding uit HA-2b is vereist. |
| Beoordeling | workflow.review_events en publish_authorizations | Voorstel en bevestiging zijn verschillende feiten; ingestpolicy bepaalt geldigheid. |
| Publicatie en serving | Canonieke release-items en publication_registry | Historische release en huidige serving afzonderlijk tonen. |

Waargenomen op main: migratie 034 en human_annotation_v1 slaan keuzes rijgericht op; overview reconstrueert tekst uit de gepinde extractie en verifieert de quotehash. release_for_snapshot zoekt de laatste release en active_release_items alleen actieve items; geen van beide is zelfstandig de gevraagde historische exacte-objectlezer. PR #1021 is op main gemerged. Controleer de integratie van recovery-PR #1022 op main afzonderlijk.

De runtime-compositie vereist PostgreSQL en in Azure een Blob-bronautoriteit, maar configureert ook lokale bron- en runtimepaden. De backup-CLI neemt een archiefpad aan en de ketenbackup gebruikt tijdelijke ZIP-bestanden. Dit is een onderzoekspunt, geen bewijs dat een specifieke productierun een kopie heeft gemaakt. Bestemming, retentie en actuele praktijk zijn onbekend.

## Sketch: datavorm vóór logica

SourceRef = snapshot-ID, bronhash, Bloblocator, extractiehash, normalisatieversie. SelectionRef = annotation-ID, revisie, block-ID, start/einde, quotehash. ObjectRef = object-ID, objectversie, contenthash. DecisionRef = exact object, reviewer, ingestpolicy en besluit. ReleaseRef = release-ID, exact lidmaatschap, historische status en actuele registrystatus. Dit zijn logische typen, geen voorstel voor aparte tabellen.

Dominante read: één exacte KO-versie, enkele bronbereiken en geldige reviewerbindings. Schrijvers blijven de bestaande annotatie-, materialisatie-, review- en publicatieoperaties; de bewijslezer leest alleen. PostgreSQL levert een consistente momentopname; externe Blobcontrole vergelijkt de gepinde hash. Een browserpagina houdt geen langdurige transactielock.

De server verwerpt onbekende objectversie, ontbrekende input-outputbinding, afwijkende contenthash, ontbrekende extractie/Blob, ongeldige offset of quote, ontbrekende essentiële context en oordeel op een andere objecthash. Geen automatische herextractie, herankering, reviewerbesluit of latest-fallback. Voor historische bronnen zonder nieuwe annotatiegeschiedenis wordt dat ontbreken expliciet getoond.

## Twee structurele alternatieven en keuze

| Criterium | A: op verzoek lezen uit bestaande autoriteiten | B: vast bewijsdossier in bestaande Blob met PG-index |
| --- | --- | --- |
| Fysieke herhaling | Geen nieuwe bewijsinhoud | Nieuwe immutable kopie per versie |
| Gezag | Bestaande eigenaren blijven leidend | Afwijking tussen dossier en bronrecords vraagt voorrangsregel |
| Historische lezing | Versiegebonden lezer moet oude records begrijpen | Dossier kan software-onafhankelijker zijn |
| Commit/herstel | Geen nieuwe schrijfgrens | Nieuwe PG/Blob-commit-, cleanup- en recoverygrens |
| Toegangspad | Gericht lezen per object | Eenvoudig dossier lezen, extra opslag en rechten |

Deze alternatieven zijn in één PStack-ontwerppass opgesteld, niet onafhankelijk door verschillende modellen beoordeeld. Kies A. Heropen B alleen als een historische herstelproef aantoont dat A de oude betekenis niet duurzaam kan reconstrueren. JSONB of herhaalde metadata zijn geen zelfstandige fout; toets doel, eigenaar, versie en herstelregel per representatie.

## Implementatie en verwijdering

1. #1026 / MET-62: inventariseer werkelijke opslagconfiguratie en kopieën. De eerste read-only operatorcontrole telt alleen lokale entries en rapporteert haar blinde vlekken. Controleer backupbestemming, temp-extractie, logging, browser, exports en retentie aanvullend.
2. #1025 / MET-63: leg autoriteit, versies, rechten, foutcodes, compatibiliteit en Class A/high-risk-grens vast. Geen nieuwe algemene evidence-engine.
3. #1015 / HA-2b levert eerst een immutable annotation-revisie → objectversie/hash-koppeling. #1024 / MET-64 bouwt daarop één read-only serverprojectie en geautoriseerde gebruikersweergave. Frontendwerk volgt de verplichte projectinstructies zodra dat begint.
4. #1028 / MET-65: vervang of blokkeer concrete strijdige contentkopieën pas nadat hun operationele functie, retentie, rollback en recovery bewezen zijn. Oude historische bewijslezers blijven read-only. Geen blind wissen.
5. #1027 / MET-66: Smetten-proef in de toegestane Azure-grens, plus synthetische negatieve gevallen voor tabellen/OCR, dubbele quote, verschoven offset, corrupte Blob en v1/v2. Een tweede persoon controleert de betekenis zonder SQL-ID's te hoeven interpreteren. Smetten bewijst niet alle documentklassen.

## Bewijs en open punten

De eerste operatorcontrole heeft twee synthetische checks direct doorlopen; compileall en de architectuurgrenschecker slaagden. Pytest was in de oorspronkelijke werkruimte niet geïnstalleerd en is geen geclaimd CI-bewijs. Geen native PostgreSQL-, Azure-, browser-, release- of productieproef voor dit project is uitgevoerd.

Open: feitelijke Azure-resource-identiteiten/retentie; lokale en tijdelijke inhoudskopieën; archiefbestemming; bronrechten voor bewijsweergave; HA-2b-binding; herstel zonder kopie buiten de grens. Een lege lokale scan blijft INCOMPLETE en is nooit een conformiteitsverklaring.
