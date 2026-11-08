# MET-62 / #1026: lokale opslaggrens inventariseren

Change class: C (read-only operatorhulpmiddel, geen productstate of lifecycle-writer). Rewrite risk: none.

Promise: een operator kan twee geconfigureerde lokale contentoppervlakken inspecteren op aanwezigheid van bestanden zonder inhoud te openen of bestandsnamen/paden in het rapport te tonen.

Ground: console_asgi.compose_console configureert bron-/runtimepaden. runtime_data_inventory_v1 leest voor historische inventaris persoonsgegevens en document-ID's en is daarom ongeschikt als privacyarm rapport voor deze taak. Backupbestemming en tempbestanden zijn per operatie en vallen buiten deze eerste scan.

Alternatieven: (A) statische codezoekactie toont mogelijke routes maar geen aanwezige bestanden; (B) read-only metadata-scan van twee geconfigureerde lokale oppervlakken zonder symlinks te volgen. Kies B, met expliciete onvolledigheid en een afzonderlijke code-/configuratieinventaris. Geen bestand openen, geen lokale snapshot, geen Azure-verbinding, geen output met paden of ID's.

Interface: inventory(environ) -> version/status/surfaces/unverified/production_compliance_proven. Een surface geeft categorie, aantal entries en scanstatus. FINDINGS bij aanwezige entries of scanfout; INCOMPLETE bij nul gevonden. Nooit PASS of production_compliance_proven=true.

Bewijs: twee synthetische checks met private testtekst en een symlink rechtstreeks uitgevoerd; compileall en check_architecture_boundaries.py geslaagd. Native pytest/CI en echte runtime-inventaris moeten nog worden uitgevoerd. Dit hulpmiddel bewijst niet dat productie uitsluitend PostgreSQL/Blob gebruikt.
