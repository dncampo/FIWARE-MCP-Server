# Running native Claude questions

Use a verified existing Smart Farming broker. The launcher does not load data.
Require Claude Code installed and authenticated, and the repository's Python
environment with project dependencies. From the repository root:

```sh
tests/farm/test_farm.sh --broker-url http://127.0.0.1:1126 --verify-only --mcp
cd evaluation/farm-reference
../../.venv/bin/python run_questions.py \
  --broker-url http://127.0.0.1:1126 \
  --context-url http://context/user-context.jsonld
```

This context service name belongs to the existing isolated farm Compose network.
Use the context URL reachable by your broker if your deployment differs. The
launcher passes it unchanged, and never substitutes another broker destination.

Add `--question F03` for one question or repeat the option for a subset. Use
`--model` for an explicit Claude model name, `--timeout` for the default
300-second per-question limit and `--output` for a new output directory. The
virtual environment interpreter path is preserved instead of resolving its
symlink to a base Python without the installed SDK. Dependency imports are checked
before launching Claude.

Each question starts a new native Claude session in an empty temporary directory.
Built-in tools and skills are disabled. Only the configured FIWARE MCP provider
is loaded, five read tools are approved, write tools are denied and the server is
forced read-only. The prompt contains no expected answers or source dataset.
The run uses your normal Claude account/usage allowance and can take several
minutes. It prints progress every 15 seconds.

Results go to `runs/<UTC timestamp>/`: exact selected questions and prompt text,
raw native event JSONL, stderr, final answer text, per-question execution summary
and combined `results.json`. Existing output is never overwritten. The run stops
on missing native calls, timeout or execution failure. Raw traces remain available
on interruption. COMPLETED_UNREVIEWED means the client executed, not that its
answer passed review.

Compare each answer and its native tool results with `reference-answers.json`:
exact result IDs, values/units, server-side q filters, retrieved relationship
targets and pagination. Preserve 404s for actual missing targets. Review added
claims and arithmetic even when the requested retrieval is correct. The launcher
does not act as an automatic semantic correctness judge.

For portable dated export, use `archive_experiment.py`; see [CODEX.md](CODEX.md).
The exporter supports both native clients. The older Claude launcher did not
capture source hashes during execution, so its archive records explicitly that
those hashes were captured later. Account metadata, reasoning blocks and local
paths are excluded from curated exports. Raw runs remain ignored and should not
be committed wholesale.
