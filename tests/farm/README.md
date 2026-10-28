# Reproducible Smart Farming integration test

## Quick start

Use an **existing NGSI-LD broker**, with permission to load these predictable IDs.
Python 3.11+ and a POSIX shell are required on macOS or Linux. The direct loader
and verifier use only Python's standard library. They do not require Docker, Git
network access, an LLM, Claude Code, Codex, credentials for an LLM, or paid services.

```sh
cd tests/farm
./test_farm.sh
```

The default broker is `http://localhost:1026`. The script displays the destination
and asks `Continue? [y/N]:` before any network requests. Empty input, EOF and any
answer except `y` cancel with exit code 3. To accept this initial prompt:

```sh
./test_farm.sh -y
./test_farm.sh --help
./test_farm.sh --prepare-only             # offline checks only
./test_farm.sh --verify-only              # no writes or loading prompt
./test_farm.sh --broker-url http://localhost:9090 -y
./test_farm.sh --host 192.168.1.50 --port 1026 -y
```

The wrapper uses `FARM_PYTHON` if set, otherwise the repository's `.venv/bin/python`
when present, otherwise `python3`. All paths are resolved from the wrapper's
location; execution from the repository root also works.

Orion-LD 1.12.0 needs the original deployment's **`-mongocOnly`** setting for this
dataset's VocabProperties. The root demo Compose broker does not enable that
setting. The harness does not change or restart it: select a suitable existing
broker, or provision a separate environment yourself. Other broker implementations
may reject the original six untyped relationship attributes; rejection is a test
failure, with the source payload retained unchanged.

## Connection configuration

| Setting | CLI | Environment | Default |
| --- | --- | --- | --- |
| Broker base URL | `--broker-url` | `NGSI_LD_BROKER_URL` | HTTP with host and port below |
| Broker host | `--host` | `NGSI_LD_HOST` | `localhost` |
| Broker port | `--port` | `NGSI_LD_PORT` | `1026` |
| Broker context URL | `--context-url` | `NGSI_LD_CONTEXT_URL` | Pinned upstream `user-context.jsonld` on raw.githubusercontent.com |
| Host context alias | `--context-host-url` | none | Same URL as broker context |
| HTTP timeout | `--timeout` | none | 10 seconds per request |
| Request headers | none | `NGSI_LD_HEADERS` | `{}` |
| Python interpreter | none | `FARM_PYTHON` | Repository venv, then python3 |

CLI settings override environment settings. At each level the URL form and
host/port form are alternatives:

* CLI `--broker-url` combined with CLI `--host` or `--port` is rejected.
* CLI `--broker-url` overrides all broker environment settings.
* Either CLI `--host` or `--port` selects the HTTP host/port form, ignores an
  environment broker URL, and fills its other component from environment/defaults.
* Without either CLI form, an environment URL combined with environment host or
  port is rejected. Unset one form instead of relying on a silent choice.
* Host/port form uses HTTP. Use a full URL for HTTPS or reverse-proxy prefixes.

For example:

```sh
./test_farm.sh --broker-url https://broker.example.org/farm -y
./test_farm.sh --host 192.168.1.50 --port 9090 -y
NGSI_LD_BROKER_URL=http://localhost:9090 ./test_farm.sh --verify-only
```

Do not append `/ngsi-ld/v1` to the base URL. The base path is retained for every
loader, query, discovery and MCP request. HTTP and HTTPS are accepted; ports must
be 1..65535. IPv6 hosts require brackets, e.g. `--host '[::1]'`. Credentials,
queries and fragments in URLs are rejected. Redirects and HTTP proxy environment
variables are disabled; configure the final destination directly. TLS validation
remains enabled. Optional `NGSI_LD_HEADERS` is the same JSON object used by the
MCP server, for example an Authorization or NGSILD-Tenant header. Reserved framing,
Link and representation headers are rejected. Headers are never sent to the
context host. The harness and MCP child use the same resolved URL, headers,
context and timeout; no internal fallback substitutes localhost.

## Context hosting and network topology

The default context URL is:

```text
https://raw.githubusercontent.com/dncampo/fgs2025-talking-with-smart-solution/05c6fdd118b731a5c362b0892c9efb00968dc7a4/src/data-models/user-context.jsonld
```

Both the developer's host and broker must be able to access it. A fresh load
requires outbound broker HTTPS access, or a locally hosted override. Dataset
preparation itself is offline. The original `user-context.jsonld` is self-contained:
namespace IRIs identify terms and do not import their websites. The bundled
`ngsi-context.jsonld` instead imports `http://context/user-context.jsonld` and the
ETSI core v1.8 context; it is not selected by this harness. The bundled
`alternate-context.jsonld` changes some type namespaces and is unsuitable as a
replacement. Brokers may separately retrieve/cache their own ETSI core context.

Optionally serve the original bundled files, in a separate terminal:

```sh
cd tests/farm
python3 serve_context.py --bind 0.0.0.0 --port 3004
```

This serves `.jsonld` with `application/ld+json`, and starts no containers. If the
broker runs directly on your host:

```sh
./test_farm.sh --broker-url http://localhost:1026 \
  --context-url http://localhost:3004/user-context.jsonld -y
```

For Docker Desktop on macOS, a typical host-served context configuration is:

```sh
./test_farm.sh --broker-url http://localhost:1026 \
  --context-url http://host.docker.internal:3004/user-context.jsonld \
  --context-host-url http://localhost:3004/user-context.jsonld -y
```

`host.docker.internal` is a Docker Desktop example, not a universal default.
On Linux, arrange a host-gateway mapping when creating your own broker container,
or use a host/LAN address routable from both environments. For a remote broker,
host the context at an address reachable from that remote network.

These three concepts differ:

* **Host-accessible URL**: Python on the developer machine fetches this document
  and checks its JSON against the pinned context. `--context-host-url` can supply
  a host alias for this check.
* **Container-network URL**: DNS such as a Compose service name works only on
  networks to which that container is attached. Container localhost refers to
  that container. Host localhost and container localhost are different machines
  from the broker's perspective.
* **Link header URL**: `--context-url` is sent unchanged in every NGSI-LD Link
  header and in the MCP child configuration. This is the URL the **broker** must
  resolve. A host alias never replaces it internally.

Preflight makes a context-dependent query through the broker using this exact
Link URL; a resolution error stops before ingestion. Verification then checks
full compacted content and queries the same entity using expanded type and
attribute IRIs, so a successful empty HTTP 200 is insufficient. This tests broker
resolution and semantics through its API; it does not inspect container DNS or
prove a fresh network fetch when the broker already cached the context. If
troubleshooting networking, check the context URL from the broker's execution
environment using its available network tools and inspect its context fetch logs.
The harness never enters or reconfigures containers.

## Fixture provenance and expected data

Source: [fgs2025-talking-with-smart-solution at the pinned revision](https://github.com/dncampo/fgs2025-talking-with-smart-solution/tree/05c6fdd118b731a5c362b0892c9efb00968dc7a4).
The exact revision is **`05c6fdd118b731a5c362b0892c9efb00968dc7a4`**.
The bundled fixture reuses the payloads verified in
[SMART_FARMING_VERIFICATION.md](../../docs/SMART_FARMING_VERIFICATION.md).

| Entity type | Expected count |
| --- | ---: |
| Animal | 47 |
| AgriParcel | 6 |
| Building | 4 |
| Person | 4 |
| Total | 61 |

Animals are 40 generated cows, three static calves and four pigs. Ten static cows
overlay generated IDs; they are not ten additional Animals. The original
`COW_COUNT=40` generator was captured twice with seed 1729, reporting Bash 5.2.15
on x86_64; both outputs have SHA-256
`60a9787ed8f84d586fcfcc668d49b3ef7905057ddfd3ecf4e5da146fe1959560`.
Its output is frozen here rather than rerunning shell RANDOM on different Bash
versions. The complete five-batch payload SHA-256 is
`801836e2928521c2d2f0de99956c72e449f7620fed5515d796cecd78e39350a1`.

`fixtures/manifest.json` preserves source Git blob hashes, generation metadata,
anomalies and SHA-256 hashes for all bundled input files. The original import
scripts under `source/` are included for inspection and provenance and **are never
executed**. Their literal static payloads match fixture batches two through five.
The upstream MIT license is retained in `source/LICENSE`. The recorded image
inspection describes the prior host image; an image tag or seed alone is not a
portable deterministic generator contract. These checked-in fixture bytes define
the regression dataset.

Import preserves the original five batches in order: 40 generated operations,
then static batches of 20, five, three and eight. The first four use
`upsert?options=update`; the final one uses replacement. There are 76 operations
over 61 unique IDs. Properties, VocabProperties, GeoProperties, structured values,
original unit codes, historical timestamps and relationships are unchanged.
Only singleton VocabProperty arrays versus scalar output are treated as equivalent
broker normalization. Ordinary arrays and coordinates retain their structure.

There are **102 relationship edges**, **93 resolved** and **nine unresolved** in
the reference profile. Four distinct absent targets remain deliberately absent:

* `urn:ngsi-ld:Person:001` (three edges; imported Person IDs include `person`).
* `urn:ngsi-ld:AgriCrop:BuckWheat` (one edge).
* `urn:ngsi-ld:AgriCrop:Corn` (one edge).
* `urn:ngsi-ld:AgriCrop:Grass` (four edges).

The verifier prints every unresolved source/attribute/target triple. It fails if
an expected target disappears or a reference absent target appears; it never
fabricates target entities. Six source relationship attributes lack `type` in
their input. Orion's verified implementation normalizes them to Relationships;
the harness sends the original payload and checks normalized output. Unmapped
terms and inconsistent source comments remain unchanged. Device provisioning,
IoT Agents, simulators, context source registration and federation are excluded,
matching the evaluated baseline. No Device or AgriCrop entities are claimed.

## Existing data and repeated execution

The script never calls upstream `services`, starts/stops containers, modifies
databases, removes volumes or deletes NGSI-LD entities. There is no cleanup flag.
`-y` accepts only the initial data-loading prompt.

Before any writes, it reads all 61 expected IDs. Matching entities are skipped,
including on repeated execution; a matching repeat makes GET requests only.
Missing IDs are loaded using the original operations filtered to those IDs. A
collision with a different entity type stops all writes. Same-type content
collisions list each ID and its first mismatch, explain update/replacement
behavior, and require a separate `Overwrite ...? [y/N]:` confirmation, including
when `-y` was supplied. EOF/default No refuses all writes. After a partial load,
use `--verify-only` to inspect the failure; replaying mismatched IDs likewise
requires that confirmation. No ownership is inferred merely from an ID prefix.

Other entity types can coexist. Exact counts are checked over the entire four
reference types, so additional Animal, AgriParcel, Building or Person entities
cause a verification failure with extra IDs listed. They are never deleted.
Use a suitable dedicated broker/tenant for an exact baseline. Do not run
concurrent writers: standard NGSI-LD has no atomic lock spanning preflight and
upsert; collision inspection cannot eliminate races with other writers.

Ingestion accepts only complete 201/204 responses with no error payload. A 207,
unexpected success body, failure status, malformed JSON, timeout or connection
failure stops loading. Earlier operations may have applied; no automatic rollback
can safely distinguish them from pre-existing data. Verification checks actual
ID sets, all source content, counts, pagination, discovery, numeric comparisons,
string equality/category filters and relationship target content. It does not
infer success solely from a status code.

Exit codes: **0** PASS, **1** validation/dataset/HTTP failure, **2** CLI or
prerequisite error, **3** declined confirmation, **4** network/TLS/timeout error,
**130** interrupt from the command line. `--prepare-only` validates fixture hashes,
batch sizes and expected counts without network or writes. `--verify-only` uses
only broker GET operations and fails on missing/incorrect data.

For manual cleanup, first retain a backup of your broker data. Inspect the exact
IDs from the fixture without connecting to the broker:

```sh
python3 -c 'import farm; print("\n".join(sorted(farm.prepare()[1])))'
```

Only delete individually reviewed fixture IDs that you own using your normal
broker administration tools, accounting for relationship dependencies. Restoring
prior values of overwritten IDs requires your own backup. Stop the optional
context server with Ctrl-C. No global Docker prune, database clearing or volume
removal is needed.

## MCP and optional natural-language evaluation

The unchanged seven-tool server is tested using an actual SDK STDIO client when
`--mcp` is supplied. Install the repository's existing requirements first:

```sh
# From repository root:
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cd tests/farm
./test_farm.sh --broker-url http://localhost:9090 -y --mcp
./test_farm.sh --broker-url http://localhost:9090 --verify-only --mcp
```

The child server is forced read-only and receives the resolved configuration.
Checks include seven-tool discovery, broker info, attribute samples, five filters,
complete pagination and explicit relationship traversal including missing-target
404s. No write tools or paid services are invoked. This harness uses STDIO; the
existing generic tests cover other server behavior separately.

Natural-language evaluations remain optional. Configure your own Claude Code or
Codex MCP client with this repository's `server.py`, your Python environment,
`NGSI_LD_BROKER_URL`, `NGSI_LD_CONTEXT_URL`, an allowlist containing that URL in
`NGSI_LD_CONTEXT_URLS`, and `NGSI_LD_ENABLE_WRITES=false`. Ask it to discover types,
filter animal heart rates, identify pigs, follow stored ownership/location/parent
relationships, report missing targets, and paginate all 47 Animal IDs. These
steps do not form part of automated PASS. The historical reports are
[Claude](../../docs/CLAUDE_SMART_FARMING_EVALUATION.md) and
[Codex](../../docs/CODEX_SMART_FARMING_EVALUATION.md); their old machine-specific
launcher paths are historical evidence, not prerequisites for this harness.

## Validation and limits

Run local regression tests, with no real broker or LLM:

```sh
# From repository root:
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest tests/farm/test_harness.py -q --tb=short
.venv/bin/python -m pytest -m 'not integration' -q --tb=short
```

The local HTTP emulator binds an ephemeral loopback port. Tests cover URL/env
precedence, host/port execution, proxy paths, rejected/EOF confirmation, `-y`,
load/repeat/verify-only, partial ingestion, ineffective writes, context failures
(including a host-accessible alias with a broker-inaccessible Link URL), wrong
counts/content/queries, duplicate or truncated pagination, fabricated targets,
collision acceptance/refusal and execution from this directory. A real MCP SDK
client also runs against the emulator. Emulator results are not evidence of
compatibility with another broker implementation.

The final local runs passed **57 farm tests** and **114 total non-integration
tests**, with 20 existing integration tests deselected. See
[VALIDATION.md](VALIDATION.md) for the exact commands and scenario results.

During development on 2026-10-28, the new harness passed read-only verification
against the previously populated **Orion-LD 1.12.0 on `127.0.0.1:1126`**, including
the actual MCP STDIO client, all 61 entities and all 102 relationship edges, using
the pinned public context. Fresh loading is covered by local HTTP tests and the
earlier verified exact-source load; the new harness does not reset the live
broker. Remote broker hosts, remote HTTPS broker endpoints, Linux runtime,
other implementations and Docker DNS examples have not been live tested here.

If a managed execution sandbox blocks local sockets or broker access, run the
commands above in a normal terminal. For the already populated evaluation broker:

```sh
cd tests/farm
./test_farm.sh --broker-url http://127.0.0.1:1126 --verify-only --mcp
```

For a fresh compatible broker, select its actual URL and run `-y` (plus your
context override if public HTTPS is unavailable). Do not point the harness at a
production broker expecting cleanup or isolation to be automatic.
