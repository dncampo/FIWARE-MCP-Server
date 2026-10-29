# Smart Farming question evaluation review

Reviewed on 2026-10-29. Run: `20261029T120603975738Z`.

## Result

Twelve answers PASS and four are PARTIAL. All 16 questions ran through native
Claude Code MCP integration. The partial classifications concern model reporting
and interpretation; no MCP request construction or broker filtering defect was
observed in this run. This does not establish that every MCP feature or deployment
is defect-free.

Client: Claude Code 2.1.308. The native events identify model
`claude-opus-5-5` consistently across all 16 sessions. The server was connected
through STDIO to the existing Smart Farming broker at `http://127.0.0.1:1126`.
Each session exposed only the five existing read tools. No native write calls
occurred. Summed per-question execution time was 405.05 seconds.

There were 88 completed native MCP calls with corresponding results: 79 HTTP 200
responses and nine expected HTTP 404 responses for original missing targets.
There were no framework tool errors or denied permissions. Execution success was
reviewed separately from correctness.

| Tool | Calls |
| --- | ---: |
| get_broker_info | 8 |
| get_types | 13 |
| get_attributes | 7 |
| get_entity | 19 |
| query_entities | 41 |
| Total | 88 |

## Per-question results

| Case | Calls | Classification | Evidence |
| --- | ---: | --- | --- |
| F01 | 7 | PASS | Four types and 61 exact entities. Incorrect guessed projection returned zero; model removed it and recovered. |
| F02 | 7 | PASS | Correct 17 observed Animal attributes, four Relationship names and one GeoProperty. No complete formal schema claimed. |
| F03 | 3 | PASS | heartRate>56 returned cow005 only: 70 with unit 5K. |
| F04 | 4 | PASS | weight>500 returned cow001 at 838 KGM and cow021 at 699 KGM. |
| F05 | 4 | PASS | Four exact pig IDs and actual stored fields; missing weights/locations acknowledged. |
| F06 | 3 | PASS | 43 dairy cattle; full listing and filtered count agree. |
| F07 | 3 | PASS | Parcel IDs 001, 002 and 003 at 10.4 CEL; absent temperatures not treated as low values. |
| F08 | 6 | PASS | Empty heartRate>1000 result interpreted correctly, with a positive control and seven absent measurements acknowledged. |
| F09 | 6 | PARTIAL | Actual location and owner retrieved correctly; extra inference treats an ID prefix as a sex/type constraint. |
| F10 | 4 | PASS | Correct three calves, all parents and recorded locations; six real targets retrieved; Bumble has no stored location. |
| F11 | 5 | PASS | Twilight's exact Person:001 target returned 404; similar person001 was not substituted. |
| F12 | 15 | PARTIAL | Correct targets and source groups listed and four target lookups returned 404; headline and arithmetic report incorrect counts. |
| F13 | 8 | PASS | North Pasture exists; area and boundaries absent; animal points not substituted for a parcel polygon. |
| F14 | 5 | PASS | Breed unknown and vet reason unconfirmed; possible post-calving explanation explicitly labeled a guess. |
| F15 | 4 | PARTIAL | Exact 47 IDs through 20/20/7 pages; additional sex totals are wrong. |
| F16 | 4 | PARTIAL | Correctly refuses to invent a trend and identifies missing temporal tools; opening claims no history exists beyond evidence available through these tools. |

The criterion includes incorrect factual additions, even when the narrow requested
retrieval is correct. No case is classified FAIL or BLOCKED. Partial answers must
not be silently converted to PASS because the underlying tool calls succeeded.

## Specific model issues

### F09: identifier interpretation

The requested answer is correct: Beany is locatedAt AgriParcel:003 (North
Pasture), and ownedBy Person:person002 (Napoleon the Pig). Both entities were
actually retrieved. Further links to Animal Farm and missing AgriCrop:Grass were
also followed correctly.

The extra statement that `cow001` conflicts with Male/maleAdult or a bull legalId
is unsupported. An entity identifier does not impose an additional sex
constraint. The stored type Animal and the male attributes are consistent.

### F12: missing-reference counts

The broker evidence and reference fixture establish:

* Person:001: three edges from cow006, cow102 and cow103.
* AgriCrop:BuckWheat: one edge from parcel 001.
* AgriCrop:Corn: one edge from parcel 002.
* AgriCrop:Grass: four edges from parcels 003 through 006.

Correct totals: **nine relationship edges and four distinct target IDs**.
The answer lists those source groups but incorrectly says seven edges and two
IDs. Grouping all AgriCrop identifiers under a wildcard does not make them one
distinct ID. All four missing IDs were queried and each returned 404.

### F15: unnecessary incorrect rollup

All 47 Animal IDs were recovered exactly once, with offsets 0, 20 and 40 and
page lengths 20, 20 and seven. The complete ID set matches the frozen reference.

The additional sex summary says six Male and 41 Female. The actual values are
**five Male and 42 Female**. Its own male-ID list contains the correct five IDs:
cow001, cow021, cow101, pig001 and pig003. This is a model arithmetic/reporting
error, not a pagination or response-content defect.

### F16: scope of the temporal conclusion

The model correctly identifies that no available tool exposes temporal history.
It reports no invented dates, growth rates or trends. Its current-weight
statistics check out: 43 recorded weights total 17,264 KGM, mean approximately
401.5 KGM; four pigs have no weight.

The statement that no history exists is stronger than the tools establish.
Correct wording would be: historical weights cannot be retrieved or verified
through the currently exposed MCP tools. A separate temporal backend could exist
without appearing among current entity types. No temporal endpoint was queried
in this evaluation. Lack of observedAt on current weight is not proof that an
external history store is empty.

## Query and evidence checks

The offline reviewer loaded native event records and paired all 88 tool calls
with their responses. All 41 query result totals, entity memberships and returned
page lengths were checked against the reference entities using the actual
arguments, including expanded type IRIs, exact IDs, regex patterns, numeric and
string q predicates, OR expressions, relationship equality and attribute
projection. Returned entity fields and reported unit/timestamp metadata were
compared to the original snapshot.

The F15 page union was independently compared with all 47 expected Animal IDs,
without assuming a broker sorting order. Missing get_entity targets were checked
against the frozen entity set and their 404 results preserved. Every startup event
showed fiware_farm connected, and all session tools belonged to that read provider.

The F01 projection mistake used `https://smartdatamodels.org/name`, which is not
the stored name IRI. Its valid HTTP 200 empty result was preserved by the MCP.
The model noticed the contradiction, removed the guessed projection and got all
47 Animals. There was no silent query rewriting or conversion of a failed filter
into a success by the server.

Numeric and categorical filters, traversal, missing target handling, empty
results and pagination worked. Compact names resolved through the configured
deployment context; some calls used explicit context_url and others relied on
the configured default. These observations support the existing context fix.

## Artifacts and reproduction

Original evidence remains unchanged under:

```text
evaluation/farm-reference/runs/20261029T120603975738Z/
```

Each question has its exact prompt, raw native events, stderr, final text and
execution summary. Those files remain execution evidence and are still marked
UNREVIEWED by the launcher; this separate review records the correctness verdicts.

`20261029T120603975738Z.review.json` includes all 16 classifications, observations,
per-trace SHA-256 hashes, exact tool arguments, result statuses and aggregate call
counts. Offline evidence assertions were executed against this specific saved run.
Per-question prose classifications are explicit human review decisions, not an
automatic semantic judge or a benchmark for arbitrary new sessions.

No new model calls, broker requests, server changes, fixture changes, commits or
pushes were performed during review. The canonical checkout remains read only
from this managed session, so review artifacts were prepared in permitted scratch
space for the user to copy into the existing run directory.

## Recommended next steps

1. Preserve this run and review, including the partial answers. Do not edit the
   original model answers to make them pass.
2. Keep deterministic count and ID-set checks on the evaluator side. Require the
   model to provide the supporting IDs before interpreting arithmetic summaries.
3. Clarify in future evaluation instructions that identifiers are opaque and
   capability absence must not be stated as data absence. Any changed prompt
   defines a new run and must be recorded.
4. If desired, repeat the same frozen questions through native Codex using the
   same starting dataset. This run evaluates Claude only; the older Codex run had
   a different prompt and cannot substitute for the same 16-question comparison.
5. Treat historical queries as separate work requiring an explicitly tested
   temporal backend and interface. This run does not demonstrate temporal access.

This is one run per question against one static dataset. It is not a statistical
reliability estimate, a write test, or proof of compatibility with other brokers.
