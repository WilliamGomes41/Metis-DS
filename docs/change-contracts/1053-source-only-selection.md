# #1053 — selecteren in de bron, zonder tweede tekstvak

Change class: B
Promise: Het dubbele hulpvak verdwijnt; bronselectie en koppelen blijven werken met muis, touch en toetsenbord.
Proof: Native browser/PostgreSQL-proef voor verwijderen, directe Unicode/grapheme-selectie, omgekeerde selectie over highlights, readonly bron en hervatten; bestaande annotatie/opbouw/reviewproeven.
Touches lifecycle invariants: no
Rewrite risk: none

Part of MET-72. GO William, 11 november 2026: verwijder ‘Hulp bij tekstselectie’.

Bestaande owner: source_document_html → focusbare bronblokken → rememberSelection
→ captureSelection → bestaande pending_range/save-controller → annotations.save.
Verwijderd: details, textarea, kopie van actieve brontekst en textarea-selectevents.
Toetsenbord beweegt de browserselectie rechtstreeks in hetzelfde bronblok, over
gewone tekst en bestaande mark-elementen; Intl.Segmenter behoudt graphemegrenzen.
De bestaande keyup-handler vertaalt deze DOM-selectie naar codepoint-offsets.
Muis en touch houden dezelfde bestaande handlers. Geen editable bron, verborgen
kopie, nieuwe status, opslagroute, serializer of framework.

Stateful overlay: bestaande annotatie/annotatieset vóór en na dezelfde draft/
pending_range/ranges. Exacte bronankers en readonly bron blijven invariant;
annotation.save blijft de enige transactie met dezelfde autorisatie, CAS en
commandreceipts. Fout/retry/hervatten, dubbele uitvoering en concurrency houden
het bestaande resultaat. Audit: bestaande immutable versies/receipts, geen nieuwe.

Risico: verkeerde offsets bij emoji/combining marks of mark-elementen; browser-
proef controleert quote, block_id en exacte opgeslagen start/end na herladen.
Herhaalde gelijke tekst op twee plaatsen behoudt verschillende bronidentiteiten.
Touch-eventproef is emulatie van de applicatiecallback, geen bewijs voor native
selectiehandles op fysiek iOS/Android. Bronselectie met muis, bestaande volledige
bronblokactie, werk opslaan, vereiste relaties en review/publicatie blijven behouden.

De nieuwe browserproef faalde vóór de implementatie op de echte pagina:
‘The duplicate selection field must be removed’, actual 2, expected 0.
Skill: Impeccable/distill en emil-design-eng; geen animatie of extra visueel
hulppaneel. Contextengine niet beschikbaar; bestaande projectcontext toegepast.

## CI-herstel (11 november 2026)

Browser- en echte-PDF-jobs falen vóór de tests op APT-DNS. De geïsoleerde
APT-aanvraag reproduceert dit zonder proxy; met de bestaande proxy wordt de
Ubuntu-index opgehaald. Sudo en Playwrights geneste sudo verliezen de geërfde
proxyinstellingen. Een gedeelde CI-wrapper normaliseert de geërfde variabelen
naar APTs lowercase namen en voert de installatie eenmaal via sudo met een
expliciete preserve-lijst uit. Geen proxywaarden in argumenten/logs, nieuwe
netwerkregels, alternatieve mirrors of versoepelde TLS-/pakketcontroles.
De wrapper bewaart foutcodes; echte browser/PDF-tests en hun bestaande
verplichte bewijscontroles blijven behouden. Een subprocessproef simuleert
sudo env_reset en toont rood zonder behoud, groen met behoud. Workflowwiring
is afzonderlijk getest. Succes van de nieuwe CI-jobs blijft vereist.
