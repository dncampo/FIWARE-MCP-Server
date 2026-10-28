# Known issues

## NGSI LD q filtering

Status: reported, unresolved, intentionally preserved in the refactor baseline.

After the Phase 2 integration suite passed, the maintainer reported that a
subsequent Claude Code session exposed a potential defect in NGSI LD q filtering.
Claude Code had successfully connected to the MCP server.

The exact failing tool arguments, expected entities, returned entities, context
and broker response were not supplied with the preservation request. The cause
has not been established. This baseline does not attribute the defect to Orion,
query encoding, context resolution or LLM reasoning without a reproduction.

The existing tests cover specific numeric and textual filters. Their passing
results do not prove correctness for every q expression or client configuration.
Treat filtering results as requiring verification for affected use cases.

No query handling code, tool definitions or test assertions were changed during
baseline preservation. Phase 3.1 investigation and bug fixing are deferred.

For the next phase, capture the natural language request, exact MCP arguments,
JSON LD context, broker version, expected IDs and actual structured response.
Compare the same expression through MCP and the broker API before selecting a
fix. This is an investigation plan, not a diagnosis or completed test.
