# Slice 2: command, worker and checkpoint evidence

Issue #616. Extends slice 1 (#615). The trace is an observation of the existing
workflow envelope, not a status writer, retry decision or publication gate.

## Collect without opening the worklist

Use **Verwerkingsspoor downloaden** on a source-selection card, or the authenticated
GET `/source-selection/processing-trace?document=SNAPSHOT_ID`. This reads one
stored envelope. It does not list documents, reconstruct sources, inspect objects,
claim work, expire an attempt or call the model. Existing researcher/named-reviewer
authorization is enforced; responses use `Cache-Control: no-store`.

The JSON contains the command hash, exact attempt/retry identities, original
server-generated HTTP request ID (where recorded), source hash, hashes of version,
expected revision/configuration, reservation and worker runtime identities,
claim time, checkpoint phase/time, bounded current artifact references and stored
terminal state. Claim tokens, cookies, headers, source/model text, filenames,
user-supplied command/version/revision prose and exception messages are excluded.

Use an existing private cookie file when collecting outside the UI:

```sh
curl --fail --silent --show-error --cookie "$METIS_COOKIE_FILE" \
  --get --data-urlencode "document=$METIS_SNAPSHOT" \
  "$METIS_BASE/source-selection/processing-trace" --output /private/processing.json
python scripts/export_section_incident.py --processing /private/processing.json \
  --output /private/processing-incident
```

Keep session files outside Git and exported incident directories. This command
only reads evidence; it never starts or retries work. If the whole app is down,
use the independent section probe/platform evidence from slice 1, then read the
persisted processing trace after a runtime becomes available.

## Correlate observations

`RequestDiagnostics` now observes POST `/source-selection/start`. The generated
`X-Metis-Request-Id` is committed inside the existing reserved attempt's diagnostic
metadata. Repeating the same command preserves that original identity. A fresh
HTTP request ID is not a fresh processing attempt.

The dispatcher claims the existing attempt. Claim metadata records which process
observed execution. Checkpoints and terminal observations use the existing
`metis_diagnostic` App Service console stream, joined by `request_id`, `attempt_id`,
`command_sha256` and `source_hash`. `processing-trace.kql` selects that evidence.
Background observation rows are not sent through a new Application Insights
provider/exporter. Existing App Service logging must actually be collected.

```sh
python scripts/export_section_incident.py --processing /private/processing.json \
  --application /private/events.jsonl --attempt-id "$METIS_ATTEMPT" \
  --output /private/correlated-processing-incident
```

Alternatively select `--request-id` using the original server request ID. If the
projection has multiple attempts and no unique explicit selector, the exporter
reports ambiguity instead of choosing the latest attempt. Incorrect selectors,
missing historical request correlation, missing terminal results, elapsed
deadlines, omitted evidence and changed/current artifact references are explicit.
`--browser` and `--platform` remain supported; section navigation and processing
are independently observed. A browser GET is not assumed to be the origin POST.

## Interpret checkpoints correctly

- `stored_state` is the observed persisted attempt state. Succeeded does not
  establish complete source formation, review completion or publication readiness.
- Diagnostic checkpoints record investigation evidence. They do not by themselves
  constitute a validated model replay or authorize resume.
- `extraction_checkpoint_hash` identifies the extraction record associated with
  that attempt. The current retained record may legitimately differ after later
  authorized re-extraction; a mismatch is not silently treated as corruption.
- Semantic identity/validation and formation progress are recorded values from
  the current replay. The trace does not revalidate those artifacts. Source,
  configuration, revision, ownership and authorization checks remain in the
  existing execution/activation owners.
- A killed worker can leave a stored running/claimed attempt. The export does
  not change it. Use existing expiry/reconciliation and authorized retry paths.
- Runtime log observations are explicitly not SQL commit proof. Lost logs do not
  undo work; a returned inner operation may still belong to an outer transaction.
  Fresh reads of the durable authority establish retained evidence.

A worker detaches both HTTP diagnostic and performance counters before running.
Its work remains linked by durable identity while HTTP timing ends at the HTTP
response. This avoids late background phases reopening a finished request trace.

## Bounds and compatibility

The projection retains the latest 64 attempts and 128 checkpoints per attempt;
omission counts are included. Console checkpoint observations stop after the
first 64 recorded diagnostic checkpoints of an attempt. An offline incident
retains at most 256 matching operational rows. Existing input files are limited
to 8 MiB and output directories are never overwritten. There is no new ledger,
queue, table, automatic retry or global exactly-once promise.

Historical attempts without request/runtime correlation remain readable and
explicitly incomplete. Existing processing ZIP export v13 adds
`processing_trace.csv` containing this same bounded JSON projection. Raw evidence
in other existing ZIP datasets retains its existing access restrictions; the
bounded trace is not a claim that the entire old ZIP is free of source text.

## PR 3: verwerkings- en herstelmarges

Dezelfde JSON bevat nu `processing_margins`: gemeten wachttijd vóór claim,
uitvoertijd sinds claim, resterende opgeslagen pogingstijd, checkpointleeftijd
en de tussentijd bij expliciete retry-verwijzingen. De documentdiagnose in Inzicht
toont deze gegevens met dezelfde bestaande verwerkingsbevoegdheden. Een verlopen
deadline verandert de opgeslagen toestand niet; herstelrechten blijven bij de
kernel. Ontbrekende tijden blijven onbekend en een oud checkpoint bewijst geen
stilstand.

Een experimentele vergelijking gebruikt minimaal drie eerdere technisch geslaagde
pogingen met dezelfde bron, configuratie, uitvoerversie en pogingsoort. Alleen
uitkomsten van vóór de betreffende claim tellen mee. Als bij claim minder tijd
overbleef dan hun mediane uitvoertijd, toont Inzicht de meetbasis en onderzoeksadvies.
Dit is geen voorspelde storingstijd of garantie op voldoende interventietijd.

De grens blijft 64 pogingen en 128 checkpoints; afgekapt of tegenstrijdig bewijs
blijft zichtbaar. Pogingaantallen zijn geen retrybudget. Zie
[het ontwerp en de bewijsgrenzen](../change-contracts/processing-recovery-margins.md).

## Deadline-schaduwprognose (PR 4)

Een expliciet gekozen document op `/source-selection?document=…` toont een
experimentele vergelijking van de bestaande grove tijdschatting met de opgeslagen
verwerkingsdeadline. Alleen voor die gebruiker zichtbare documenten leveren
historie. Een chronologische toets gebruikt per eerdere aanvraag uitsluitend
uitkomsten die toen al bekend waren; de weergave noemt ook gemiste en onterechte
grenssignalen binnen de toetsbare, technisch geslaagde pogingen.

Ontbrekende configuratie/timing, mislukte of destijds nog onvoltooide vergelijkbare
pogingen, onvoldoende toetsbare historie of een analyselimiet geven HOLD. Er zijn
geen automatische ingrepen en geen bewezen voorspellende nauwkeurigheid of
gegarandeerde handelingsruimte. Deze schaduwberekening wijzigt de bestaande
verwerkingsspoor-export niet. Zie het
[meet- en acceptatiecontract](../change-contracts/processing-deadline-forecast.md).
