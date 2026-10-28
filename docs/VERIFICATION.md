# Verification

This branch includes the Phase 3.1 query context correction and regression tests.

## Selected versions

| Component | Version |
| --- | --- |
| MCP protocol target | 2026 07 28 |
| Official Python MCP SDK | 2.3.0 |
| Python project target | 3.11 or newer |
| Orion LD | 1.12.0 |
| MongoDB image | mongo:4.4.29 |
| Context server image | python:3.12.8-slim |

The protocol revision is written as `2026-07-28` in MCP messages.

## Recorded execution

The Phase 2 run on 28 October 2026 completed with 60 tests passed, no failures
and no skips. The full suite ran in the maintainer's terminal because the coding
session restricted Docker socket and local TCP access. Its complete output was
inspected during Phase 2. Raw terminal output and machine details are intentionally
excluded from this branch.

| Coverage | Result |
| --- | --- |
| Six direct NGSI LD API integration tests | PASS |
| Native Python MCP client over STDIO | PASS |
| Native Python MCP client over Streamable HTTP | PASS |
| Broker state checks after create and update | PASS |
| Read only policy and blocked write state checks | PASS |
| Nine synthetic fixtures and relationships | PASS |
| Other unit, schema and transport checks | PASS |

There are nine integration tests and 51 other checks in the recorded complete
suite. All seven tools were exercised against the real broker. The dataset has
three Buildings, three Rooms and three Sensors, including numeric and textual
Properties, GeoProperties and Relationships. Temporary entities created by the
write tests are removed by those tests; fixed fixtures remain.

During preservation, the local suite excluding integration tests reported
50 passed, one skipped and nine deselected. The skipped test requires local TCP
binding, which this session denies. This is a fresh local check, not a second
claim that the live suite ran here. Production modules, tests and fixture scripts
were copied without behavioral edits.

## Client evaluation and known limits

The maintainer reports successful Claude Code connectivity. Phase 3.1 traced the
reported filtering issue to a missing deployment context in the local MCP
registration. Direct HTTP and MCP reproduce the empty contextless response and
recover the expected values with the appropriate request context. See the
[query filtering diagnosis](QUERY_FILTERING.md). Passing the recorded test suite
does not establish correctness for every q expression.

A separate native Codex evaluation was blocked before MCP startup by a client
initialization permission error. No Codex natural language evaluation was marked
as passed. Local Codex configuration and generated evaluation output are omitted.

Other brokers, concurrency, remote authentication and immutable image digests
were not verified in Phase 2.

## Phase 3.1 coverage

The source implementation's recorded complete run on 28 October 2026 reported
77 passed in 10.68 seconds, with no failures or skips. The suite now contains
twenty integration cases and 57 other checks. Eleven new live cases compare
direct HTTP and MCP filtering, exact stored values, projection, configured and
per-call contexts, and missing-context recovery. Six unit regressions cover
context headers, encoding, contextless requests and the query tool description.

Fresh verification in this checkout on 28 October 2026 used a newly installed
Python 3.14.6 environment with requirements-dev.txt and the existing broker:

```sh
FIWARE_INTEGRATION=1 .venv/bin/python -m pytest -v --tb=short
```

Result: **77 passed in 11.52 seconds; no failures or skips**. The first restricted
attempt could not access localhost or bind TCP ports; the complete successful
run used approved access. Its output is retained locally in the ignored
phase31-test-results.txt file.

The production change clarifies the query tool description; executable query
logic and interfaces are unchanged. Machine specific client registrations remain
outside Git. See [known issues](KNOWN_ISSUES.md) for configuration guidance.

## Reproduce

Install requirements-dev.txt in a Python environment, then run:

```sh
docker compose up -d
.venv/bin/python examples/wait_for_broker.py
.venv/bin/python examples/demo.py
.venv/bin/python examples/demo.py
FIWARE_INTEGRATION=1 .venv/bin/python -m pytest tests/test_direct_ngsi.py -v
FIWARE_INTEGRATION=1 .venv/bin/python -m pytest -v
```

The first load into an empty broker should report nine inserted entities. A
repeat should report zero inserted, nine existing and nine verified. The suite
can also populate its own fixtures. Use the disposable Compose broker without
unrelated entities of the fixture types.

Local checks that do not require the real broker:

```sh
.venv/bin/python -m pytest -m 'not integration' -q
```

Inspect and stop this Compose project with:

```sh
docker compose ps
docker compose logs orion mongo context
docker compose down
```

Adding `-v` to the final command removes this project's demonstration data.
No production data or unrelated Docker resources are needed for the tests.
