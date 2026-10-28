# Repository audit and implementation decision

Audited all seven upstream files at commit
`80ffba4da93bbc99c4af66f47ff9a46cb24514bc` before implementation:
server.py, requirements.txt, README.md, claude_desktop_configuration.json,
.template.env, .gitignore and LICENSE. No tests, package metadata or additional
modules were present. Source was fetched through the GitHub connector because the
local workspace was empty and shell DNS/network access prevented cloning.

## Original behavior

| Tool | Behavior and issues |
| --- | --- |
| CB_version | GET caller-specified HTTP address/port `/version`. Assumes vendor endpoint. |
| get_all_entities | GET entities with local=true, count=true, default limit 1000, arbitrary extra headers. Discards count header. |
| get_entity_types | GET types, limit 1000, no offset or explicit completeness. |
| execute_query | Accepts a query path, strips GET and localhost prefix, deletes all spaces, hardcodes broker and remote user context. README example uses an invalid NGSI-LD path. |
| publish_to_CB | POST creation; automatically PATCHes on 409, stripping id/type/context. Returns completed even when writes fail. Logs full entity data. |

Requests were synchronous, with no timeout; redirects followed by default. Most
results were double-encoded JSON strings. Errors lost status/body information.
There was no single-entity tool, structured query interface, attribute discovery,
write policy, local structure validation or test coverage. Arbitrary caller broker
addresses/ports and headers exposed SSRF and credential-routing risks. Missing
URL quoting affected IDs and type IRIs. Broad exception catching in publishing
masked broker failures. SDK initialization parsed CLI arguments and changed global
signal/logging configuration at import time. Startup errors were swallowed with a
sleep, potentially yielding a successful exit code.

Requirements were requests>=2.31.0, fastmcp>=0.3.0, uv>=0.4.18 and unbounded
mcp[cli]. There was no lock or installed-version evidence, so the actual original
runtime/protocol version could not be established. Python 3.7 in README was
inconsistent with modern MCP dependencies. The standalone Claude configuration
used uvx with a script path and nonstandard host/port fields; README separately
described STDIO correctly but listed a nonexistent query_CB tool. The environment
template requested an unused OpenAI API key. Public unauthenticated tunneling was
recommended without an inbound access-control design.

## Selected implementation

Official Python SDK mcp==2.3.0, MCP revision 2026-07-28; project Python >=3.11.
Official documentation and release notes were checked on 2026-10-28:

- https://modelcontextprotocol.io/specification/2026-07-28
- https://github.com/modelcontextprotocol/python-sdk/releases/tag/v2.3.0
- https://py.sdk.modelcontextprotocol.io/
- https://py.sdk.modelcontextprotocol.io/run/
- https://gofastmcp.com/updates
- https://cim.etsi.org/NGSI-LD/official/clause-6.html
- https://github.com/FIWARE/context.Orion-LD/releases

Independent FastMCP 4.1.4 is also current. Both provide decorator-based tools and
modern transports. The official SDK keeps the same basic decorator style, removes
the duplicate independent FastMCP dependency and offers the needed typed outputs,
client and transports directly. Most required changes concern broker semantics,
not MCP registration, so retaining independent FastMCP offers little reduction in
code churn here. No protocol implementation is hand-written. Runtime tests verify
modern negotiation rather than relying only on dependency claims.

Production code has two modules: server.py owns the seven tool signatures and
CLI; broker.py owns configuration, HTTP/result handling and minimal validation.
Synchronous HTTP tools run in the SDK's thread offload. A bounded per-request HTTP
client avoids introducing connection-lifecycle abstractions. No framework beyond
the selected SDK and HTTP library is added. Direct dependencies are bounded;
transitive dependencies follow SDK constraints and are not fully locked.

Preserved: CB-assistant server name, direct Python startup, STDIO default,
--http/--host/--port (port 5001), stderr logging, version lookup, entity/type
reading, queries, creation and attribute updates, Apache license and gitignore.

Changed: tool names and schemas, dictionary results with status/errors/pagination,
fixed trusted configuration, explicit contexts, separate create/update operations,
read-only default, bounded responses and pagination. Removed: arbitrary URL/header
tool arguments, query rewriting, forced local-only federation option, implicit
upsert, hardcoded user context, unused uv/requests/OpenAI settings, import-time
CLI/signal side effects and public-tunnel instructions. Existing clients must
migrate tool calls; no legacy aliases duplicate the interface.

Optional delete and relationship tools were omitted to keep scope focused.
