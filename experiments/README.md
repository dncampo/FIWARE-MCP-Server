# Experiments

Reproducible native-client evaluations of the existing FIWARE MCP interface.
Each dated record preserves its own questions, data version, MCP implementation
snapshot, client/model information, native calls, answers and review status.

## Smart Farming

| Date (UTC) | Native client | Question set | Outcome |
| --- | --- | --- | --- |
| 2026-10-29 | Claude Code 2.1.308, claude-opus-5-5 | 16 reference questions | 12 PASS, four PARTIAL; 88 native MCP calls |
| 2026-10-29 | Codex CLI 0.165.0, requested gpt-6.1-sol | Same 16 questions and instruction text | 16 PASS; 128 native MCP calls |

The Claude record is in
[`smart-farming/2026-10-29-claude-20261029T120603975738Z/`](smart-farming/2026-10-29-claude-20261029T120603975738Z/).
Its manifest identifies the exact original run, source hashes and limitations.
The reviewed Codex record is in
[`smart-farming/2026-10-29-codex-20261029T151154441881Z/`](smart-farming/2026-10-29-codex-20261029T151154441881Z/).
See the [same-question comparison](smart-farming/2026-10-29-COMPARISON.md).
Both runs used byte-identical prompts and matching fixture/context hashes. The
managed-session startup failure remains separate from this successful normal
terminal execution. The older five-task native Codex run is not substituted.

Dataset source revision: `05c6fdd118b731a5c362b0892c9efb00968dc7a4` from
[fgs2025-talking-with-smart-solution](https://github.com/dncampo/fgs2025-talking-with-smart-solution/tree/05c6fdd118b731a5c362b0892c9efb00968dc7a4).
The fixed fixture contains 47 Animal, six AgriParcel, four Building and four
Person entities. Nine relationship edges point to four absent target IDs; those
anomalies are preserved. Fixture and context SHA-256 hashes accompany each run.

MCP baseline: official Python SDK 2.3.0, supported protocol 2026-07-28, unchanged
seven-tool interface; only the five read tools are available to evaluated models.
The run manifest records exact source commit/hashes instead of treating this
paragraph as a permanent version claim. The evaluated broker was Orion-LD 1.12.0.
These are current-state evaluations, not demonstrations of temporal queries.

## Reproduction

1. Install the repository requirements and use a populated, verified farming
   broker. See [the fixture harness](../tests/farm/README.md).
2. Execute the question runner from an authorized terminal. See
   [native Codex instructions](../evaluation/farm-reference/CODEX.md) and
   [Claude instructions](../evaluation/farm-reference/RUNNING.md).
3. Retain raw native events locally under the ignored `runs/` directory.
4. Review exact ID sets, numeric values, query filters, relationship retrieval,
   pagination and unsupported claims against the independent reference answers.
5. Export a dated directory with `archive_experiment.py`, then inspect the diff
   before committing. Correctness is not inferred from successful process exit.

Every archive includes `manifest.json`, `questions.json`, `prompts.json`,
`answers.json` and `mcp-calls.json`. Reviewed archives also include `review.json`.
Exact prompts, tool data and reviewed partial results support reproducibility;
the model never receives the reference answers during execution.

Raw client account information, reasoning blocks, credentials and local absolute
paths must not be published. No automatic Git commit, push, broker modification
or resource cleanup is performed. Compare only experiments with matching
question/prompt hashes and dataset versions, and account for model and client
differences. A single run per question does not establish statistical reliability.

## Compare two archived experiments

From the repository root:

```sh
python3 evaluation/farm-reference/compare_experiments.py \
  experiments/smart-farming/2026-10-29-claude-20261029T120603975738Z \
  experiments/smart-farming/2026-10-29-codex-20261029T151154441881Z
```

The comparison refuses different questions/prompts, fixture/context versions or
MCP source hashes. It reports existing reviewed classifications, call counts and
question durations. It does not grade prose or promote an unreviewed archive to
PASS. Use --output with a new path to save the comparison as JSON. A new developer
can execute a run, export it, review its results, then compare it with a baseline.

See [additional provider plans](EXTENDING.md) for Gemini and local-model testing.
Those integrations are proposed and have not been executed.
