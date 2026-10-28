# Known issues

## NGSI LD q filtering

Status: diagnosed and corrected in Phase 3.1.

The local MCP registration omitted the deployment context. Direct HTTP and MCP
both returned empty results for compact custom q terms without that context,
then returned the expected stored values when the request supplied it.

Configure the trusted deployment context with `NGSI_LD_CONTEXT_URL`, or allowlist
contexts with `NGSI_LD_CONTEXT_URLS` and select one using `context_url`. Restart
the MCP connection after changing its environment. Use compact attribute paths
in q; full IRIs in type or attrs do not replace the q request context.

Phase 3.1 adds eleven live filtering cases and six unit regressions. Query
transport logic is unchanged. See the [diagnosis](QUERY_FILTERING.md) and
[verification report](VERIFICATION.md) for evidence and reproduction commands.
Other brokers and every possible q expression remain outside this validation.
