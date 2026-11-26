# Stap 2 · Bronbewijs voor sterktelabels

Change class: A. Rewrite risk: none. Part of MET-145. Refs #1159 and #1164.

Een aanbeveling uit annotatie kan een optionele selectie **Sterktelabel** krijgen. Het selectiemenu legt de exacte plaats vast via de bestaande annotatieopslag. Zonder keuze zoekt de bouw binnen de bestaande bronregels. Een naburig label geldt alleen als het direct aansluit bij de kern of in het eerstvolgende losse bronblok staat. Cellen die Docling als tabelcellen vastlegt, vallen buiten deze regel. Voor afzonderlijke kaders geldt de bestaande bronindeling en is end-to-end-verificatie nog nodig.

De eventuele bewijsrecord bevat het letterlijke label, bronfragmenten en exacte posities van het label en de richtingverwijzing binnen de uitspraak. De canonieke objecthash omvat de bewijsrecord. De oorspronkelijke uitspraak en bronmapping blijven eigendom van de deterministische materialiser. Een ongeldig aangewezen label is een annotatiebevinding. Als automatisch bewijs ontbreekt of tegenstrijdig is, blijft de aanbeveling zonder dat bewijs beschikbaar voor review.

De materiaal- en Admission-controle reconstrueren het label vanuit de bron, ook als een semantisch voorstel ontbreekt. De reviewopdracht hercontroleert de bewijsbinding met de bron van precies de beoordeelde versie. Een handmatig aangewezen label dat ook expliciet richting noemt kan een voorstel opleveren. De reviewer bevestigt richting en sterkte via het bestaande keuzepad. De annotatie en de bewijsrecord leveren op zichzelf geen review- of publicatiebevoegdheid op.

Bij een correctie bindt de bouw het label aan de nieuwe selectie. Eerdere objectversies en historische releases behouden hun eigen bewijs. Oude annotaties en objectversies blijven leesbaar zonder nieuwe velden. De bestaande generatiecontrole, opslagtransactie, canonieke hash en reviewbinding beschermen tegen stale, dubbele en partiële verwerking.

## Bewijs

- `tests/test_annotation_strength_label_pdf.py::test_pdf_strength_label_survives_annotation_build_admission_and_review` bestrijkt beide blokindelingen. Per indeling wordt het handmatige en het automatische pad via native PostgreSQL, herstart, materiaalcontrole, Admission en Review getest.
- `tests/test_annotation_strength_label_pdf.py::test_pdf_strength_label_does_not_bind_when_missing_distant_or_conflicting` bestrijkt afwezig, naburig en strijdig bewijs. De eerste proef wijzigt ook de bewijsrecord om de versiehash en de afwijzing bij Admission te controleren.
- `tests/browser_annotation_strength_label_check.cjs` volgt selecteren, opslaan, heropenen en verwijderen in Chromium op desktop en telefoonbreedte.
- De PDF-proeven genereren de twee blokindelingen met de bewaarde tekst uit pagina 18 van de Smetten-conceptrichtlijn.
- Op 25 november 2026 is de volledig geüploade concept-PDF van 46 pagina’s via de vergelijkings-extractor verwerkt. De kern en het sterktelabel staan in hetzelfde bronblok op pagina 18. Voor deze ene geselecteerde aanbeveling bereikten het handmatige en het automatische pad beide Admission en expliciete bevestiging in Review met bevestigd documentoverzicht en documentcontrole actief. De bron-PDF blijft buiten de repository.
- De herhaalproef `test_original_smetten_pdf_strength_label_reaches_review` leest het lokale originele bestand uit `METIS_SMETTEN_PDF`. Standaard kiest zij Docling. Voor de vergelijking is `METIS_PDF_EXTRACTOR=legacy-comparison` expliciet ingesteld. De vastgezette Docling-pakketten zijn geïnstalleerd, maar de publieke download van de twee vereiste modelrevisies kreeg HTTP 403. Daardoor blijft de acceptatie met de productie-extractor open.
