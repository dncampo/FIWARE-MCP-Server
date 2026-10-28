# Phase 3.4 validation record

Date: 2026-10-28. Work was performed in the canonical FIWARE-MCP-Server checkout,
on `refactor`, starting with a clean working tree. No commits, pushes, merges,
generic MCP changes, Docker changes or broker deletions were performed.

## Automated tests

```sh
.venv/bin/python -m pytest tests/farm/test_harness.py -q --tb=short
# 57 passed

.venv/bin/python -m pytest -m 'not integration' -q --tb=short
# 114 passed, 20 deselected
```

The sandbox initially denied loopback socket binding. Both final commands passed
after approved execution outside that sandbox. There were no skipped tests in the
final full run. The 20 deselected cases are the existing generic real-broker
integration tests, which are not farming tests. The local farm emulator is not a
broker implementation or evidence of remote-broker compatibility.

| Requested scenario | Evidence and result |
| --- | --- |
| Default broker | Defaults tested in argument tests. Live read-only request reached localhost:1026 and correctly failed: zero Animals, expected 47. No load attempted there. |
| Custom broker URL | Complete load/repeat/verify flow through local emulator's `/proxy` path; live verification on 127.0.0.1:1126 PASS. |
| Custom host and port | Complete local emulator load PASS; live `--host 127.0.0.1 --port 1126 -y` repeat PASS. |
| Invalid/unavailable broker | Invalid URL/port tests and refused local connection test PASS. |
| Missing/inaccessible context | Missing document, wrong context, and reachable host alias with unreachable broker Link URL tests PASS; zero writes. |
| Rejected interactive confirmation | No, newline and EOF tests PASS; zero network requests. |
| Noninteractive `-y` | Local load PASS; colliding data still requires a separate confirmation. |
| Repeated execution | Local repeat makes GET requests only; live repeat says all 61 match and no writes needed. |
| Verification only | Local and live tests PASS on reference data; malformed/incomplete fixture tests fail as expected with GET requests only. |
| Incorrect/incomplete dataset | Missing ID, wrong value, extra same-type ID, wrong query results, inconsistent counts, duplicate pagination and fabricated target tests PASS. |
| Port and URL validation | Precedence, conflicting forms, malformed ports, non-HTTP URLs, URL credentials/query/fragment, IPv6 and reverse-proxy prefix cases PASS. |
| Execution from tests/farm | Shell subprocess tests execute from that exact directory, including help and offline preparation. |

Additional local checks cover HTTP 207 with per-entity errors, HTTP 204 with no
actual writes, different-type collision refusal, same-type collision
acceptance/refusal, exact source static batch extraction, source Git blob hashes,
fixture hashes and VocabProperty normalization. A real SDK MCP STDIO client runs
against the local HTTP emulator with broker writes disabled.

## Actual populated broker

The already populated evaluation broker is Orion-LD 1.12.0 at
`http://127.0.0.1:1126`, configured separately in the earlier evaluation. These
new harness commands both returned exit 0:

```sh
tests/farm/test_farm.sh --broker-url http://127.0.0.1:1126 --verify-only --mcp
tests/farm/test_farm.sh --host 127.0.0.1 --port 1126 -y
```

Both used the default pinned public upstream context. Host document comparison,
the broker context-dependent preflight and expanded-IRI semantic checks passed.
The first command discovered all seven existing tools through the actual MCP SDK
STDIO client and tested discovery, five filters, complete pagination and explicit
relationship traversal. The second inspected all fixture IDs and reported
`Already loaded: all 61 fixture entities match; no writes needed.`

| Type | Expected | Verified live |
| --- | ---: | ---: |
| Animal | 47 | 47 |
| AgriParcel | 6 | 6 |
| Building | 4 | 4 |
| Person | 4 | 4 |
| Total | 61 | 61 |

Live verification checked exact IDs and all source fields. Animal pagination
uses pages of 20, 20 and seven. Numeric/equality results were one Animal for
`heartRate>56`, two for `weight>500`, four for `species=="pig"`, 43 for
`species=="dairy cattle"`, and three AgriParcels for `temperature>10`.
All 102 relationship edges were checked: 93 resolved and nine original dangling
edges returned 404. Four distinct missing targets remained absent.

The default `tests/farm/test_farm.sh --verify-only` reached the existing port-1026
broker, accepted its context-dependent query and exited 1 with the complete
missing Animal ID list. This is an expected failure against an environment that
does not contain the farming fixture, not a successful default-environment load.

## Scope of the evidence

The exact frozen payloads derive from upstream revision
`05c6fdd118b731a5c362b0892c9efb00968dc7a4`, with the same payload SHA-256 as the
earlier verified real ingestion. This phase did not erase the existing dataset
to repeat a fresh live ingestion: fresh loading of the new harness is exercised
by the local HTTP tests; prior actual broker acceptance is recorded in
[SMART_FARMING_VERIFICATION.md](../../docs/SMART_FARMING_VERIFICATION.md).

Remote hosts, HTTPS broker endpoints, other NGSI-LD implementations, Linux
runtime and Docker networking examples remain untested live. Public HTTPS context
retrieval worked. Broker resolution can use its cache; the checks do not claim a
fresh container-origin network fetch. There is no global broker lock against
concurrent writers. Device/IoT provisioning, federation and natural-language agent
evaluations were not rerun. No paid LLM services were used.
