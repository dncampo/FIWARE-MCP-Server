# Codex Smart Farming reference-question review

Date: 2026-10-29 UTC. Run: `codex-20261029T151154441881Z`.
Result: **16 PASS, zero PARTIAL, zero FAIL and zero BLOCKED questions**.

## Execution and provenance

The user ran the native Codex CLI 0.165.0 from a normal macOS terminal. The
requested model was `gpt-6.1-sol`; these events do not separately identify a
resolved model revision. Each question used a fresh native client session, an
empty temporary working directory and the same English prompt bytes as the
reviewed Claude run. Reference answers and fixture values were not passed to
the evaluated model.

The unchanged MCP server used official Python SDK 2.3.0, Python 3.14.6 and httpx
0.28.1. The SDK reports supported protocol revision 2026-07-28; separate wire
negotiation was not captured. The server source commit was
`348dbf89f8db516f5fc782342733a7f78a5165f9`, with pre-execution source hashes in
`manifest.json`. Broker results identify Orion-LD 1.12.0. All source hashes still
matched during review.

Dataset source revision: `05c6fdd118b731a5c362b0892c9efb00968dc7a4`.
Fixture SHA-256: `801836e2928521c2d2f0de99956c72e449f7620fed5515d796cecd78e39350a1`.
Context SHA-256: `0cbb9f6c6176a82e38aed1e23caa7799e3319b6c55225f213c65e611a9415ef4`.
Question-bank SHA-256: `1930c8820d6522625c0058838b4151f741cf5654fa60007c3114d9b2e1f0fd79`.

The fixture contains 47 Animal, six AgriParcel, four Building and four Person
entities. Runtime output was compared against that complete fixed reference.

## Native MCP evidence

There were **128 completed native MCP calls**: 119 HTTP 200 results and nine
expected HTTP 404 results for original missing relationship targets. Each call
had server=fiware_farm, status=completed and no framework error. No shell,
file-inspection, web, other provider or write calls appear among completed items.
Each model turn completed without a recorded turn/API error. No timeout occurred.

| Tool | Calls |
| --- | ---: |
| get_broker_info | 16 |
| get_types | 16 |
| get_attributes | 24 |
| query_entities | 26 |
| get_entity | 46 |
| Total | 128 |

The sum of per-question execution durations was 549.33 seconds. These durations
include native-client startup and tool execution, not only model inference.

## Per-question review

| Case | Calls | Result | Checked outcome |
| --- | ---: | --- | --- |
| F01 | 6 | PASS | Four types, 61 entities and exact returned ID sets. All fixture entities have name, so the selected projection preserves reference counts. |
| F02 | 16 | PASS | Correct 17 attributes: eight Properties, four VocabProperties, four Relationships and one GeoProperty. All 12 distinct direct Animal targets read, with one expected 404. |
| F03 | 4 | PASS | heartRate>56 returns cow005 only, 70 with unit 5K. |
| F04 | 4 | PASS | weight>500 returns cow001 838 KGM and cow021 699 KGM. |
| F05 | 5 | PASS | Four exact pig IDs, original sex/legalId values, absent measurements and unestablished physical farm membership reported accurately. |
| F06 | 4 | PASS | Exact 43 dairy cattle IDs from server-side species equality, without implying all are lactating. |
| F07 | 4 | PASS | Parcels 001, 002 and 003 at 10.4 CEL with original observation dates. |
| F08 | 4 | PASS | Valid empty heartRate>1000 result; no invented matches or failure claim. |
| F09 | 10 | PASS | Beany location and owner actually retrieved; owner-building link followed; missing crop returned 404; no identifier-based sex assumption. |
| F10 | 12 | PASS | Three calves, correct parent links and recorded locations; six real targets retrieved; Bumble location left unknown. |
| F11 | 5 | PASS | Exact missing Person:001 followed to 404; no replacement with person001. |
| F12 | 27 | PASS | All 102 edges checked; all 17 distinct targets read; nine missing edges to four IDs counted correctly. |
| F13 | 5 | PASS | North Pasture exists; no area, polygon or boundary invented; actual crop 404 reported. |
| F14 | 11 | PASS | No breed inferred from animal names; vet cause not established; calving relationship not treated as diagnosis. |
| F15 | 7 | PASS | All 47 unique IDs in 20/20/7 pages, with exact names, weights and heart rates. Repeated offset zero disclosed and excluded from final union. |
| F16 | 4 | PASS | Correctly limits inability to determine weight history to available tools; no invented trends or claim that no history store exists. |

## Detailed checks and limitations

All 26 query response totals, memberships and page lengths were checked against
the frozen entity reference using their actual query arguments. Returned fields,
units and observation timestamps were compared with the source. Attribute
samples were also checked where entity data was returned. Numeric predicates,
species and name equality, the three-name OR expression, expanded type IRIs,
compact attribute names and expanded attribute projection returned the expected
data.

F12 retrieved the 17 distinct targets of all 102 reference edges. Thirteen target
IDs exist, resolving 93 edges. Four absent target IDs account for nine edges:
Person:001 (three), AgriCrop:BuckWheat (one), AgriCrop:Corn (one) and AgriCrop:Grass
(four). All four actual missing IDs returned 404 and were not fabricated.

F15 read offset zero twice. Those two page bodies were identical; the model
explicitly retained one result per offset. The final 47-ID union was checked for
duplicates and completeness against the reference. All tabulated name, weight and
heart-rate values in the final answer match the returned data. No snapshot
isolation guarantee across pages is claimed.

F16 exposed no temporal tool. Its final answer correctly explains that historical
change cannot be determined from the available interface. All 43 reported current
weights were checked; four pig weights remain absent. A PASS means correct
handling of an unsupported request, **not successful temporal querying**.

## Unnecessary reads and comparison scope

F14 repeated the same complete Animal query, and F15 repeated page zero. These
are two avoidable reads without incorrect final results. F02 and F12 verified
many relationship targets, contributing to the larger call total. No rationale
for the duplicate queries is inferred beyond the observed trace.

Claude's same-question run used 88 calls and was reviewed as 12 PASS/four PARTIAL.
Codex avoided the four incorrect added claims/counts in those answers, but used
128 calls and more elapsed time. This is one run per question per client. It does
not establish general model superiority, efficiency or statistical reliability.
Client defaults and model settings differ. See the sibling comparison report.

The normal terminal execution supplies the actual native evidence. The earlier
managed-session attempt failed before any call and remains a separate BLOCKED
startup probe. No restriction was bypassed, and Python client results were not
substituted for native Codex results.

## Archived artifacts

`manifest.json` preserves date, versions and source/data hashes. `questions.json`
and `prompts.json` preserve exact model inputs. `answers.json` preserves final
answers and review classifications. `mcp-calls.json` contains all native tool
arguments and broker results. `review.json` contains classifications and SHA-256
hashes of the original per-question native event files.

Raw event streams, diagnostics, account metadata and reasoning blocks remain
local. The original model answers were not edited to improve results. No server
implementation change, broker write, new model execution, Git commit or push was
performed during this review. Curated artifacts were checked for personal local
paths and raw account/session metadata before preparing the archive.
