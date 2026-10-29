# FIWARE MCP Server

A small Python MCP server for discovering, reading, querying, creating and updating
NGSI-LD entities on one configured Context Broker. It contains no agent, model
registry or application-specific production logic.

The server uses the official Python MCP SDK **2.3.0**, pinned in requirements.txt,
and targets MCP **2026-07-28**. The same server supports legacy clients; STDIO
2025-11-25 negotiation is covered by tests. Python **3.11 or newer** is required
by this project. HTTP requests use httpx **>=0.28.1,<0.29**. Independent FastMCP
is no longer required. See [audit and selection rationale](docs/AUDIT.md).

## Install and run

```sh
git clone --branch refactor https://github.com/dncampo/FIWARE-MCP-Server.git
cd FIWARE-MCP-Server
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
export NGSI_LD_BROKER_URL=http://localhost:1026
.venv/bin/python server.py
```

STDIO waits for an MCP client on stdin. Logging goes to stderr. No LLM provider
or API key is required. On Windows use `.venv\Scripts\python.exe`.

For Streamable HTTP:

```sh
.venv/bin/python server.py --http --host 127.0.0.1 --port 5001
```

The endpoint is `http://127.0.0.1:5001/mcp`. HTTP defaults to loopback. The server
has no inbound authentication layer: keep it local or place an authenticated
reverse proxy in front of it. SDK Host/Origin protections remain enabled.

## Smart Farming integration test

Use an existing NGSI-LD broker compatible with the original farming dataset
(Orion-LD 1.12.0 requires `-mongocOnly`; the root demo stack does not enable it):

```sh
cd tests/farm
./test_farm.sh                         # default http://localhost:1026; asks first
./test_farm.sh --broker-url http://localhost:9090 -y
./test_farm.sh --broker-url http://localhost:9090 --verify-only --mcp
```

The pinned fixture reproduces **47 Animals and 61 entities total**. Matching
repeated runs make no writes; `-y` does not approve collision overwrites. No Docker
resources or unrelated entities are deleted. Direct checks use Python's standard
library; optional `--mcp` uses the installed project requirements. See the
[farm guide](tests/farm/README.md) for context hosting, network topology, environment
variables, provenance and regression tests.

## Native model experiments

The [experiments index](experiments/README.md) contains dated Claude Code and
Codex evaluations of the same 16 Smart Farming questions, including questions,
prompts, expected results, native MCP calls, answers, versions and dataset/source
hashes. See the [question runners](evaluation/farm-reference/README.md) to execute
your own run and compare reviewed results with the checked-in baselines. Model
client installation/authentication and a populated broker are prerequisites; the
MCP server itself requires no model provider. Raw account event streams remain
local. Gemini and local model integrations are planned separately.

## Configuration

Configuration is read once from process environment at startup. The server does
not load `.env` automatically; `.template.env` lists the available variables.

| Variable | Default | Meaning |
| --- | --- | --- |
| `NGSI_LD_BROKER_URL` | `http://localhost:1026` | HTTP(S) broker origin, optionally including a reverse-proxy prefix; omit `/ngsi-ld/v1`. No credentials, query or fragment. |
| `NGSI_LD_TIMEOUT` | `10` | Positive HTTP timeout in seconds per network operation. |
| `NGSI_LD_HEADERS` | `{}` | JSON object of string headers, e.g. `{"Authorization":"Bearer TOKEN","NGSILD-Tenant":"demo"}`. |
| `NGSI_LD_ENABLE_WRITES` | `false` | Only `true` enables create and update. |
| `NGSI_LD_CONTEXT_URL` | unset | Default remote JSON-LD context; sent as a Link header. |
| `NGSI_LD_CONTEXT_URLS` | `[]` | JSON array of additional permitted remote context URLs. |
| `NGSI_LD_MAX_RESPONSE_BYTES` | `2000000` | Maximum decoded broker response size. Narrow oversized queries. |

HTTP framing, Host, Accept, Content-Type and Link headers are reserved; configure
context through the context variables. Tool calls cannot change the broker URL,
credentials or headers. Redirects and environment proxies are disabled. Broker
TLS certificates are verified.

Read tools accept an optional `context_url` from the configured allowlist. Writes
accept inline `@context` definitions or a configured context URL. Inline contexts
may use absolute vocabulary IRIs without downloading them. Remote contexts,
including nested contexts and `@import`, must be explicitly allowed. The server
never downloads contexts itself; the broker may fetch them. Only configure trusted
context documents and use broker network restrictions to control their transitive
imports. No universal application context is assumed. With no context, use fully
qualified terms for type/attrs or the broker's core context behavior. In q,
use compact attribute paths with the context that defines them; a bare full IRI
is not a standard q attribute path.

Writes with inline `@context` use `application/ld+json`; others use
`application/json` and an optional context Link. Responses request
`application/ld+json` and preserve broker JSON-LD, identifiers and Relationships.

## MCP clients

Configure Claude Desktop to launch the installed environment Python executable
with the absolute path to server.py as its argument. Set broker configuration
under `env`, including the trusted deployment context in `NGSI_LD_CONTEXT_URL`;
add `NGSI_LD_ENABLE_WRITES=true` only when desired. Keep this machine specific
configuration outside Git. Claude Desktop is optional.

An independent Python client can discover and invoke tools:

```python
import asyncio
from mcp import Client, StdioServerParameters

async def main():
    params = StdioServerParameters(
        command="/absolute/path/FIWARE-MCP-Server/.venv/bin/python",
        args=["/absolute/path/FIWARE-MCP-Server/server.py"],
        env={"NGSI_LD_BROKER_URL": "http://localhost:1026"},
    )
    async with Client(params) as client:
        print((await client.list_tools()).tools)
        result = await client.call_tool("get_types", {"limit": 10})
        print(result.structured_content)

asyncio.run(main())
```

For HTTP replace `Client(params)` with `Client("http://127.0.0.1:5001/mcp")`.

## Tools and results

| Tool | Purpose and inputs |
| --- | --- |
| `get_broker_info` | Check standard type discovery connectivity and separately probe optional `/version`. Reports configured endpoint, write policy and actual probe results. |
| `get_types` | One page of currently available type identifiers and metadata with `details=true`; `limit`, `offset`, `context_url`. |
| `get_attributes` | `entity_type`, `sample_limit` (1..20), `context_url`. Returns type metadata and a small normalized entity sample, including observed attribute structures. This is not a complete schema. |
| `get_entity` | Absolute `entity_id`, optional `attrs` list, `context_url`, `representation` (`normalized` or `keyValues`). |
| `query_entities` | `type`, `attrs` list, `q`, `id` list, `idPattern`, `georel`, `geometry`, `coordinates` array, `limit`, `offset`, `context_url`, `representation`. |
| `create_entity` | Normalized `entity` object with absolute `id`, nonempty `type`, optional inline `@context`; optional `context_url`. Duplicate identifiers return HTTP 409. |
| `update_entity` | Absolute `entity_id`, normalized `attributes` object, optional `context_url`. PATCH existing attributes; never creates an entity or appends a missing attribute. Preserve inline context in attributes when needed. |

Every tool returns a structured JSON object with `ok`, `status` (null when no HTTP
response), `data`, `error`, selected `headers` and optional `pagination`. No JSON
string decoding is needed. Check **`ok`**, even when the MCP call itself succeeds:
expected broker/validation failures are structured tool results. MCP schema
validation errors use the SDK's tool-error channel. Diagnostics from failed broker
requests remain in `data`; `error.kind` classifies the failure. An empty successful
query is `ok=true, data=[]`. HTTP 207 updates have `ok=false`, preserving the
partial result; some attributes may already have changed. Timeouts do not prove
that a write failed; read before retrying. Requests are never automatically retried.

Collection limits default to 20 and accept 1..100. `pagination.total` is null if
no count was supplied. `has_more` is true, false or null (unknown). A full page
without a total is conservatively `incomplete=true`; follow `next_offset` until
complete. Broker pagination must be honored by the broker; pages are not a
snapshot under concurrent writes. Response Link headers are returned, never
followed automatically.

Query examples (MCP arguments):

```json
{"type":"Sensor","q":"temperature>21","attrs":["temperature"],"limit":10}
{"type":"Room","q":"name==\"Room 1\""}
{"type":"Sensor","q":"temperature>=20;temperature<25"}
{"id":["urn:ngsi-ld:Room:1","urn:ngsi-ld:Room:2"]}
{"type":"Room","limit":1,"offset":1}
{"type":"Building","georel":"near;maxDistance==1000","geometry":"Point","coordinates":[-3.7,40.4]}
```

`attrs` is a JSON array such as `["temperature"]`, not a comma separated MCP
argument. Fully qualified IRIs can be used in `type` and `attrs`. The attribute
paths inside `q` use compact context terms, such as `temperature`; do not replace
them with a bare attribute URL or append `.value`. Set `NGSI_LD_CONTEXT_URL` in
the MCP server environment, or pass an operator allowlisted `context_url` on the
tool call. The context used to create an entity does not automatically become
the context of every later query.

For the Compose demonstration, configure
`NGSI_LD_CONTEXT_URL=http://context:3000/context.jsonld` in the client environment
and restart its MCP connection. The broker resolves that private context URL.
For other applications, configure the appropriate trusted context instead.
If one deployment uses several contexts, configure their trusted URLs in
`NGSI_LD_CONTEXT_URLS`, provide those choices to the LLM in its deployment
instructions, and use `context_url` on the tool call to select one. The server
validates the choice and sends the Link header; it does not guess a vocabulary,
fetch a schema or rewrite the query.
An empty `ok=true` query is a valid result under the supplied type, context and
filter; check these before treating it as evidence that no matching data exists.

`q` uses NGSI-LD syntax directly; strings, spaces and punctuation are preserved
and encoded as query parameters. Geo filters require all three parameters and use
the default `location` GeoProperty. The broker validates full query, regex and
geometry semantics. Invalid queries are not repaired or replaced with empty results.

## Real broker demonstration

Requires Docker Engine and Docker Compose, including amd64 emulation on ARM hosts.
The Compose file pins Orion-LD 1.12.0 and MongoDB 4.4.29. A Python static server
serves the demonstration context on the private Compose network. MongoDB is not
published. Orion-LD binds to host loopback port 1026.

```sh
.venv/bin/python -m pip install -r requirements-dev.txt
docker compose up -d
.venv/bin/python examples/wait_for_broker.py
.venv/bin/python examples/demo.py
.venv/bin/python examples/demo.py
FIWARE_INTEGRATION=1 .venv/bin/python -m pytest tests/test_direct_ngsi.py -v
FIWARE_INTEGRATION=1 .venv/bin/python -m pytest -v
```

The loader connects through an actual STDIO MCP client and creates nine synthetic
entities: three Buildings with point locations, three Rooms with floors and
Relationships to Buildings, and three Sensors with temperatures and Relationships
to Rooms. All have textual names. The loader explicitly enables writes in its child
server, sends inline contexts and verifies every stored entity after either a 201
or a duplicate 409. A conflicting existing entity fails the load; it is never
silently overwritten. The second loader run should report inserted=0, existing=9
and verified=9.

The demo's default Link context URL is `http://context:3000/context.jsonld`. This
name is resolved **by the broker inside Compose**, not by the host. For other
brokers, configure a context URL they can reach and adapt the demonstration client.
The production server contains no example entity types.
The local Claude Code registration also needs the deployment context in its
server environment. An empty client `env` does not supply the demonstration
context. Restart the MCP connection after changing its environment.

Integration tests exercise the whole sequence over STDIO and real Streamable HTTP:
connectivity, population, types, attributes, entity retrieval, numeric/text/geo
queries, pagination, create, duplicate, update and read-back, invalid query and
missing entity. Direct API tests also check all nine stored fixtures and
attribute metadata without the MCP wrapper. The read-only test verifies that both
create and update are blocked and independently checks unchanged broker state.
Temporary entities are uniquely named and deleted after each write scenario; the
nine fixed fixtures remain. Use a disposable broker with no unrelated entities
of the demonstration types. To inspect or stop it:

```sh
docker compose logs orion mongo
docker compose down
```

`docker compose down -v` also deletes the demonstration dataset.

## Tests and verification limits

```sh
.venv/bin/python -m pytest tests/test_server.py -q
.venv/bin/python -m pytest -q
```

Unit tests use mocked broker HTTP responses through the SDK client. They cover
schemas, errors, bounded responses, URL encoding, contexts, writes, partial updates
and pagination. Transport tests launch real STDIO subprocesses (modern and legacy)
and exercise Streamable HTTP through ASGI. A separate socket-based HTTP test skips
only when the runtime prohibits local binding. Real-broker tests skip unless
`FIWARE_INTEGRATION=1`; once enabled they fail if the broker is unavailable.

Phase 2 verified **60 passed, no failures or skips** on macOS 26.6 / Apple
Silicon with Python 3.14.6 and Orion-LD 1.12.0. This includes **six direct NGSI-LD
integration tests**, **three real-broker MCP tests** (STDIO, Streamable HTTP and
read-only enforcement), and **51 other checks**. All nine sample entities and
create/update read-after-write behavior were verified. The complete live suite
was run by the user in a normal terminal because this Codex session's sandbox
blocks Docker socket and local TCP access; its saved results were inspected.
See the [verification report](docs/VERIFICATION.md) for versions, exact commands,
execution provenance and known limitations.

The later filtering investigation confirmed that requests without the deployment
context can return empty results even for matching stored values. Direct HTTP and
MCP agree when the correct context is supplied. See
[query filtering diagnosis](docs/QUERY_FILTERING.md) for the evidence, configuration
fix and regression commands. The fresh complete suite reports **77 passed**,
with no failures or skips, including all eleven new filtering regression cases.
This correction does not change query transport logic.

## Scope and known limitations

- Generic NGSI-LD endpoints are used; Scorpio, Stellio and Antares are not verified.
  Unsupported discovery endpoints return their actual errors. `/version` is optional.
- Write validation supports normalized Property, Relationship and GeoProperty
  instances, including instance lists and datasetId passthrough. Expanded JSON-LD,
  concise/simplified writes, LanguageProperty and other newer attribute kinds are
  outside this implementation. The broker validates detailed GeoJSON, subattributes
  and JSON-LD semantics. No schema registry validation is performed.
- Update uses standard PATCH existing-attribute semantics. No append, upsert, delete,
  batch operations, temporal API, subscriptions or relationship traversal tool.
  Relationships are preserved in normal entity results.
- Attribute discovery intentionally includes a bounded observed sample; missing
  sampled attributes do not imply absence from all entities.
- Configuration allows one trusted broker per process. Start separate instances
  for different brokers or tenants. Broker credentials stay in process environment.
- HTTP timeout is per network operation, not a total wall-clock deadline. Keep
  HTTP access restricted and use proxy request deadlines when deploying remotely.

Apache-2.0; the upstream LICENSE is preserved.
