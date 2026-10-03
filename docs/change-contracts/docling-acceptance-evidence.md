# Docling acceptance evidence — 2026-10-03

Status: **incomplete; do not merge or deploy**. This supersedes earlier notes
saying that all genuine conversion was blocked by missing network access.

## Reproducible runtime

Python 3.12, official `docling-slim==2.132.0`, `docling-core==2.99.0`,
`docling-parse==7.22.1`, `docling-ibm-models==4.0.3`, CPU PyTorch 2.14.1,
TableFormer and Heron prefetched by the official downloader. Complete resolved
pins are in `requirements-docling.lock`. The lean kernel remains isolated.

The previous 2.98.0 core pin was incompatible with docling-parse 7.22.1;
GitHub acceptance run 37154248285 failed during dependency resolution.
Actual conversion then revealed missing OpenCV in the selected SDK extras;
headless OpenCV is now explicitly pinned. `pip check` passed after installation.
Offline conversion used the real models, not mock extractor results.

## Actual source documents

These are available local originals, not proof they are the same three records
currently uploaded to production. No production data was changed.

| Source | Pages | Supervisor wall time | Worker peak RSS | Outcome after list-span correction |
| --- | ---: | ---: | ---: | --- |
| Smetten concept | 46 | 55.08 s | 1,885,484 KiB | Complete conversion and adapter validation |
| Continentie bij (kwetsbare) ouderen | 86 | 95.94 s | 2,884,036 KiB | Complete conversion and adapter validation |
| Beslisboom Mantelzorg | 5 | 11.49 s | not accepted | Blocked: source geometry outside page |

These measurements are on the development host, **not Azure capacity evidence**.
The worker reports `getrusage(RUSAGE_SELF).ru_maxrss`; supervisor `/proc` sampling
reported zero in this PID-isolated development environment and therefore does
not prove live memory-limit enforcement here. Neither document fits the existing
768 MiB conversion policy. Raising that policy without host capacity evidence
would be unsafe. The lean deployment ZIP does not install this interpreter or
its model files. No SKU change or new infrastructure was made.

The Mantelzorg failure is concrete: item `#/texts/112`, third provenance entry,
page 4, has a BOTTOMLEFT top of 1189.95 points while that page is only 904.5 points
high. It belongs to a merged cross-page text item. The adapter refuses it rather
than inventing/clamping a source location. PyMuPDF confirms the page dimensions.
The 2.133.0 wheel's reading-order implementation is unchanged from 2.132.0;
a blind minor-version bump is not evidence of a fix.

## Concrete same-source comparison

The following exact passage starts were independently located in the original
PDF. Both the old and new extracted text contain them (whitespace normalized for
comparison only). Both locators open a PDF crop containing the expected text.
This is a targeted source/highlight check, not a document-wide completeness claim.

| Source/page | Expected source text | Old route | Actual Docling route |
| --- | --- | --- | --- |
| Smetten / 6 | Het doel van deze richtlijn is het bieden van uniforme | present; crop verified | present; crop verified |
| Continentie / 2 | Houd tijdens het bespreken van mogelijke urine-incontinentie | present; crop verified | present; crop verified |
| Continentie / 4 | Adviseer de cliënt bij rectaal bloedverlies | present; crop verified | present; crop verified |
| Continentie / 67 | Leeg de urineopvangzak zodra deze voor twee derde vol zit. | present; crop verified | present; crop verified |

No general quality gain is claimed. In Continentie, DOEN/OVERWEEG are still separate
source fragments; semantic formation must relate them to the relevant passage.
This adapter must not turn a label into an approved recommendation by itself.

## Actual regression findings

- The one-page genuine PDF test passes: exact text, source SHA, actual versions,
  models, table pipeline, original crop, and reaped worker.
- The genuine upload -> source-bound semantic proposal -> admission -> human
  rejection -> restart test passes locally. The model proposal is controlled to
  avoid a paid API; extraction is genuine. Rejection persists on the object and
  grants no publication authorization (the earlier test incorrectly expected an
  approval binding for a rejected object).
- The two-column/two-page real test **fails** on page 2: Heron/Docling merges the
  first left and right lines into one item before the remaining left line. The
  failing reading-order assertion remains; it is not loosened to obtain green CI.
- Real Mantelzorg output exposed a translation bug: the SDK removes list markers
  from `text` while preserving full-original `charspan`. Translation now retains
  `orig` only when that exact declared-marker transformation can be proven. It
  records the text field per binding; unrelated invalid offsets remain blocked.
- Successful publication with native PostgreSQL has a separate genuine-PDF test.
  Its existence alone is not proof; the CI result must be read before acceptance.

## Outstanding acceptance / cutover

Correct real reading order and mixed-page geometry; full source completeness and
section/context checks; successful native PostgreSQL publication/restart proof;
real conversion failure/retry/concurrent commit proof; actual Azure artifact and
memory/time acceptance. OCR remains explicitly disabled; scanned-PDF support is
not claimed. Keep the existing staged default until these gates pass, then remove
the legacy new-upload route as defined in `docling-extraction.md`. Historical
source/review data remains untouched. Reupload and rollback instructions remain
in that contract.

## Selected-model retest (supersedes Heron failures above)

The official `layout_egret_large` preset resolves the two reproduced Heron
failures. The three local real-PDF tests now pass, including the unchanged
column-order assertion. No custom layout reconstruction was added. The model
repositories are pinned to exact commits in `MODEL_REVISIONS` and verified by
file hashes before conversion. Neither the model nor package selection is a
user-facing control.

| Source | Supervisor wall time | Worker peak RSS | Result |
| --- | ---: | ---: | --- |
| Mantelzorg, 5 pages | 11.12 s | 1,223,564 KiB | Complete conversion and validated geometry/spans |
| Smetten, 46 pages | 55.55 s | 1,812,036 KiB | Complete conversion and validated geometry/spans |
| Continentie, 86 pages | 73.51 s | 2,816,176 KiB | Complete conversion and validated geometry/spans |

`docling-comparison-evidence.json` identifies the exact files by SHA256 and records
five same-source passage checks, including original PDF crop verification for
both old and new routes. All five selected passages are present with valid crops
in both routes. This shows selected source fidelity, not general superiority.
The model treats part of the synthetic column fixture as a table; that structure
is preserved rather than rewritten by the adapter. Semantic interpretation and
human review remain necessary.

The full local staged suite reported 2604 passed / 171 skipped / 4 failures. The
same four failing tests were rerun on the verified main baseline and also failed:
parent-process death and three proxy/DNS-isolation security cases. No tests were
weakened. Repository preflight, release-control preflight, compilation and all
17 adapter/architecture tests passed. Native PostgreSQL is exercised in CI, not
claimed from locally skipped tests.

The user confirmed that the current Azure memory capacity is unknown. This is an
unresolved deployment acceptance input; no capacity increase is authorized by
that answer. The selected model still exceeds the 768 MiB conversion limit and
needs production-host capacity verification. Default activation, legacy cleanup
and a deployable production package remain blocked on this resource/topology
choice and the outstanding full acceptance gates.
