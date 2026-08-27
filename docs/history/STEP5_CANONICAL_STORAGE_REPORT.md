# V&VN Data Services - Stap 5: Canonieke storage/publication layer

Datum: 2026-08-19
Protocol: v2.0
Status implementatie: technisch gereed
Status echte Fractuurpreventie-release: BLOCKED (verwacht)

## Doel

Deze stap implementeert de SQL-kenniskern en release-gebaseerde publicatie. Klinisch `approved` en extern `published` zijn technisch gescheiden. Publiceren muteert de canonieke knowledge object JSON niet.

## Geimplementeerd

- PostgreSQL-referentieschema (`db/schema_v2.sql`)
- Lokale SQLite-reference runtime voor reproduceerbare tests
- Importgate: uitsluitend volledig goedgekeurde, bron-gehashte objects
- Herberekening van content hashes bij import en publicatie
- Controle van first-review snapshot tegen de actuele objectinhoud
- Vier-ogencontrole voor high-risk objects, inclusief content-hash snapshot
- Immutable `(object_id, object_version)`
- Expliciete publication releases met release owner
- Atomische release-publicatie
- Publication registry als externe visibility pointer
- Supersession van objectversies zonder historische versies te verwijderen
- Emergency unpublish op objectniveau
- Withdrawal op releaseniveau
- Append-only audit events
- Exportview die uitsluitend actief gepubliceerde objecten blootstelt

## Architectuurregel

`canonical_object_versions` is de inhoudelijke waarheid. `publication_registry` bepaalt alleen wat extern zichtbaar is.

Een object kan dus klinisch `approved` blijven terwijl het emergency-unpublished is. De historische approved inhoud wordt daarbij niet overschreven of verwijderd.

## Echte dataset

De huidige Fractuurpreventie-set is getest tegen de importgate:

- input: 21 objects
- geimporteerd in canonieke approved store: 0
- geblokkeerd: 21

Dit is de verwachte uitkomst omdat:

1. de expertvalidatie nog niet gereed is;
2. de canonieke PDF nog geen lokaal geverifieerde SHA-256 heeft;
3. high-risk objects nog geen afgeronde tweede review hebben.

De actieve canonieke store bevat daarom terecht 0 objectversies en er zijn 0 gepubliceerde objects.

## Regressietests

23 tests slagen.

Onder andere getest:

- echte unreviewed dataset wordt geweigerd;
- approved + verified object wordt toegelaten;
- high-risk object zonder tweede review wordt geweigerd;
- tampering/content-hash mismatch wordt geweigerd;
- dezelfde objectversie kan niet met andere inhoud worden overschreven;
- publiceren muteert canonical JSON niet;
- supersession verplaatst de publicatiepointer en bewaart historie;
- emergency unpublish verwijdert externe zichtbaarheid, niet canonieke waarheid;
- release withdrawal verwijdert zichtbaarheid van de betreffende actieve release;
- releasecreatie is atomisch bij fouten;
- release owner is verplicht.

## Gate voor echte activering

De volgende echte release mag pas worden gemaakt als:

- bronbinary SHA-256 = verified;
- first clinical/technical reviews = afgerond;
- high-risk objects second review = approved;
- prepublication gate = PASS;
- approved objects succesvol in canonical store zijn geimporteerd.

Embeddings, vectorindex en RAG blijven buiten deze stap en zijn nog uitgeschakeld.
