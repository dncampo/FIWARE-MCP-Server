# Query filtering diagnosis

Status: missing request context confirmed by direct HTTP and MCP evidence.
The source workspace's local client configuration was corrected. Its recorded
complete live suite passed: 77 tests, no failures and no skips, in 10.68 seconds.
This report records that Phase 3.1 investigation. The implementation and tests
are now integrated on refactor; see [verification](VERIFICATION.md) for the
fresh checkout run. Historical diagnostic logs remain in the preserved source
workspace and are excluded from Git.

## Root cause and evidence

The Claude Code server registration in .mcp.json had an empty env object. No
deployment context was selected. Stored custom attributes use the
https://example.org/ vocabulary, but the contextless query responses contain
only Orion's core context. The compact term temperature in a predicate therefore
does not identify the stored custom temperature attribute.

The inspected phase31-diagnostic.jsonl contains sixteen completed records: eight
direct HTTP requests and eight matching MCP calls. Every request received HTTP
200. The stderr file records the actual MCP HTTP URLs and no failed call. The
values below are observed results, not expected fixture answers:

| Request | Context supplied | Direct HTTP | MCP |
| --- | --- | --- | --- |
| Full Sensor type, no predicate | No | Three sensors: 20, 22, 24 | Same |
| Full Sensor type, temperature>19 | No | Empty | Empty |
| Sensor, temperature>19 | Yes | Sensor 1, 2, 3: 20, 22, 24 | Same |
| Full Sensor type, temperature==20 | Yes | Sensor 1: 20 | Same |
| Room, floor==1 | Yes | Room 1: floor 1 | Same |
| Full Sensor type, full temperature IRI in attrs | No | Three projected values: 20, 22, 24 | Same |
| Bare full temperature IRI as q path | No | Empty | Empty |
| Bare full temperature IRI as q path | Yes | Empty | Empty |

The full Sensor type in this table is https://example.org/Sensor. The working
context is http://context:3000/context.jsonld, served on the existing private
Compose network. It is used only in deployment configuration and test fixtures.

Without a supplied application context, returned entities show the stored
Properties under their full IRIs and include only
https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context-v1.8.jsonld as context. With
the Link header, returned entities include the deployment context and compact
names temperature and floor. Their values and relationships remain intact.

This establishes a deployment context mismatch, not missing numeric values or
an MCP transport filtering failure. Direct HTTP reproduces the same behavior as
MCP, and the supplied context restores valid compact predicates. The Phase 2
fixtures explicitly selected a context on every direct request and MCP server
subprocess, which explains why those tests passed while the client with empty
environment did not.

## Expanded IRIs are not a substitute for a q context

There are two separate issues in the reported attempts. Missing context prevents
custom compact terms from identifying their stored attributes. Replacing a q
attribute path with a bare full IRI is not a valid repair.

[ETSI clause 4.9](https://cim.etsi.org/NGSI-LD/official/clause-4.html) specifies
compact attribute paths in q, resolved by the supplied context. Full IRIs are
usable in type and attrs; this does not make them standard q attribute paths.
The diagnostic confirms that this Orion version returns an empty HTTP 200 result
for the attempted bare IRI predicate even with the correct context. This is
observed broker behavior for that attempted syntax, not a portable syntax rule.
The server neither rewrites that predicate nor claims it is valid.

[Orion LD 1.12.0 context documentation](https://github.com/FIWARE/context.Orion-LD/blob/1.12.0/doc/manuals-ld/developer-documentation.md)
identifies the Link header as the way to supply a context for GET requests. A
context supplied during entity creation does not become the application context
of every subsequent query request.

## Smallest fix applied

The local Claude Code registration now explicitly configures:

```json
{
  "NGSI_LD_BROKER_URL": "http://localhost:1026",
  "NGSI_LD_CONTEXT_URL": "http://context:3000/context.jsonld",
  "NGSI_LD_ENABLE_WRITES": "false"
}
```

Restart the Claude Code MCP connection so the new child process reads these
variables. No global client settings were modified. This is local deployment
configuration and should not be published as a portable client configuration.

For another deployment, select its own trusted context URL. Production code does
not contain a default sample application context. The existing configurable
NGSI_LD_CONTEXT_URL mechanism sends the selected context as a Link header. For
several deployment contexts, configure NGSI_LD_CONTEXT_URLS and supply the trusted
choices to the LLM in deployment instructions; its context_url tool argument can
select an allowed URL for each request. Arbitrary context URLs remain rejected.
The LLM can then use the matching compact terms in q without guessing a context.

No request rewriting, schema registry, new tool or application specific production
logic was added. broker.py is byte identical to the baseline. AST comparison of
server.py with docstrings removed confirms that executable logic and tool
signatures are unchanged; only the query description was clarified.

The help text and README explain that attrs is a JSON array, q predicates target
Property values directly, compact names require the appropriate request context,
and empty ok=true results indicate no match under the supplied inputs rather than
proving absence of matching data under every context.

## Regression coverage

The new read only integration module compares direct HTTP and actual STDIO MCP
results using exact stored IDs and values. Before filtering, it verifies that the
three stored Sensor values are 20, 22 and 24 and Room floors are 1, 2 and 3.

| Predicate | Expected IDs and values |
| --- | --- |
| temperature>19 | Sensor 1: 20, Sensor 2: 22, Sensor 3: 24 |
| temperature>21 | Sensor 2: 22, Sensor 3: 24 |
| temperature==20 | Sensor 1: 20 |
| temperature>25 | Empty successful result |
| floor==1 | Room 1: floor 1 |

These five cases run with compact type/attrs and with expanded type/attrs IRIs,
for ten pytest cases. Every MCP case tests both a configured default context and
an allowlisted per call context_url. Projection must omit unrelated name and
relationship attributes. q remains a standard compact predicate in both variants.

An eleventh live case holds type and predicate identical while changing only the
context. It reproduces the empty contextless result, then requires all three
Sensor IDs and values after supplying the Link header directly or context_url
through MCP. It never writes or reloads data.

Unit regressions inspect the generated Link header and exact q/attrs parameters,
check encoding only once, cover a different deployment context URL, preserve
contextless requests without silent rewriting, and inspect the tool description.
No test assertion was weakened to make a failed filter pass.

Restricted execution in the source workspace after the fix: 56 passed, one TCP
test skipped, twenty integration tests deselected. That session denied localhost
and Docker socket access. The user therefore executed the diagnostic and complete
suite in a normal terminal; their complete saved outputs were inspected.

The final phase31-test-results.txt lists all 77 tests as PASSED, including all
eleven new filtering cases and the original nine integration cases. Its footer
records 77 passed in 10.68s, with no failures or skips. There are twenty integration
tests and 57 other checks. The earlier 60 test baseline is historical evidence,
not a substitute for this fresh run.

| Fresh verification | Result |
| --- | --- |
| Direct HTTP and MCP diagnostic pairs | Eight matching pairs inspected |
| Controlled missing context failure and recovery | PASS |
| temperature>19, temperature>21, temperature==20, temperature>25 | PASS |
| floor==1 and attribute projection | PASS |
| Compact terms with a configured default context | PASS |
| Compact q terms with expanded type and attrs IRIs | PASS |
| Allowed per call context_url | PASS |
| Existing STDIO, HTTP and write integration cases | PASS |
| Complete suite | 77 PASS, 0 FAIL, 0 SKIP |

The first attempted source-workspace terminal command did not start pytest
because a relative Python path was mistyped. Its shell error was not counted as
a test run. The successful rerun used an absolute Python path; the equivalent
command from this checkout is:

```sh
FIWARE_INTEGRATION=1 .venv/bin/python -m pytest -v --tb=short > phase31-test-results.txt 2>&1
```

The full suite includes the existing tests that create, update and remove their
own unique temporary entities. Fixed fixture contents are checked and retained.
The eleven new filtering cases and the diagnostic perform no broker writes.

Run the new read only cases against the existing broker:

```sh
FIWARE_INTEGRATION=1 .venv/bin/python -m pytest tests/test_query_filtering.py -v --tb=short
```

Run the full suite, including the existing controlled write integration tests:

```sh
FIWARE_INTEGRATION=1 .venv/bin/python -m pytest -v --tb=short > phase31-test-results.txt 2>&1
```

## Files changed and remaining limits

1. .mcp.json: local deployment context configuration; writes remain disabled.
2. server.py: query tool description only.
3. README.md: q syntax, attrs type, context selection and client restart guidance.
4. tests/test_query_filtering.py: eleven direct HTTP/MCP regression cases.
5. tests/test_server.py: context, encoding and description regressions.
6. docs/QUERY_FILTERING.md: evidence, diagnosis, fix and validation status.
7. docs/VERIFICATION.md: link to the fresh filtering results.

The original investigation created no commits, branches or pushes. Integration
preserves that source directory and keeps machine specific client configuration
outside Git, with local executable and script paths updated for this checkout.
The read only diagnostic did not change stored broker data. Interactive Claude
Code behavior after its MCP restart is not yet recorded. Other broker vendors
and every possible q expression are outside this validation.
