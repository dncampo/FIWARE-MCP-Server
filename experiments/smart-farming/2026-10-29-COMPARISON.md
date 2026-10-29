# Same-question native MCP comparison

Date: 2026-10-29 UTC. Both clients used the same 16 English reference questions
and byte-identical instruction prompts in fresh sessions with read-only FIWARE
MCP access. No expected answers were supplied to either model.

| Item | Claude | Codex |
| --- | --- | --- |
| Run | 20261029T120603975738Z | codex-20261029T151154441881Z |
| Native CLI version | Claude Code 2.1.308 | Codex CLI 0.165.0 |
| Model | claude-opus-5-5, identified in events | gpt-6.1-sol requested; resolved revision not independently reported |
| PASS | 12 | 16 |
| PARTIAL | 4 | 0 |
| FAIL / BLOCKED questions | 0 / 0 | 0 / 0 |
| Native MCP calls | 88 | 128 |
| HTTP 200 broker results | 79 | 119 |
| Expected HTTP 404 broker results | 9 | 9 |
| Sum of question durations | 405.05 seconds | 549.33 seconds |
| Actual write calls | 0 | 0 |

The same dataset source revision, fixture/context hashes and MCP source hashes
are recorded in both manifests. The fixture has 61 entities including 47 Animals,
102 relationship edges and four distinct absent relationship targets. The MCP
used official Python SDK 2.3.0 and supported protocol 2026-07-28 over STDIO;
separate wire negotiation was not captured. Orion-LD 1.12.0 supplied broker data.

Claude source/SDK provenance was captured at archive time, rather than during
its historical run. Codex source/SDK provenance was captured before execution.
Both snapshots match, but this asymmetry remains a reproducibility limitation.

## Correctness observations

Both clients demonstrated discovery, numeric and categorical filtering,
relationship traversal, missing target handling, empty-result interpretation and
complete pagination through their actual native MCP integrations. Neither client
performed temporal queries: the current seven-tool interface does not expose
them. F16 evaluates honest handling of that capability limitation.

Claude's four PARTIAL answers contain incorrect extra claims:

* F09 treats the opaque cow001 identifier as conflicting with the stored male
  attributes despite correct location/owner traversal.
* F12 lists missing targets but reports seven edges/two IDs instead of nine/four.
* F15 retrieves all 47 IDs but adds six Male/41 Female instead of five/42.
* F16 correctly declines a trend calculation but overstates the evidence as no
  historical data existing, rather than no temporal tool being available.

Codex did not make those errors in this run. It correctly counted nine missing
edges to four target IDs, reported 47 unique paginated Animals without adding an
incorrect sex rollup, and bounded its historical conclusion to the available
tools. Its final answers and tables matched the recorded broker data.

## Efficiency and recovery

Claude guessed an incorrect expanded name IRI in F01, received a valid empty
result and recovered by removing that projection. Codex did not make that
projection error, but repeated a complete Animal query in F14 and page zero in
F15. It disclosed and deduplicated the repeated page. Both clients preserved
actual missing-target 404s rather than substituting similar IDs.

Codex made more calls, including more discovery and target-verification reads,
and its recorded duration was longer. These observations do not establish an
overall efficiency ranking: the question wording is identical, but clients made
different verification choices and use different models and runtime defaults.
No token, cost or inference-only latency benchmark was performed.

## Interpretation

This controlled pair supports that the existing MCP can serve both native
clients on this fixed farming dataset. The observed partial answers are model
reasoning/reporting issues; no request-construction or broker-filtering defect
was found in these traces. This is not proof of defect-free behavior across all
brokers, all tools or other datasets.

One run per question does not measure repeatability or statistical reliability.
Future changes should preserve prompt, fixture/context and source versions,
record client/model settings and retain unsuccessful outcomes. Repeated runs
would be required before making general model comparisons.
