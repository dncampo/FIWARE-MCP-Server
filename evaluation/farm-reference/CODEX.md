# Native Codex question evaluation

This runs the same 16 English questions and exact instruction prefix used for
the reviewed Claude run on 2026-10-29. Every question starts a new native CLI
session in an empty temporary directory. No expected answers, source fixtures or
previous model answers are sent to Codex. Connection settings and source hashes
are collected by the launcher outside the model session.

Requirements: Python 3.11+, this repository's installed dependencies, Codex CLI
and an authenticated normal Codex account. No new API key or paid service account
is required by the launcher. Model execution uses the existing account's usage
allowance. This workflow does not install or upgrade the CLI.

## Execute

From the repository root, first verify the existing farming fixture without
loading or modifying data:

```sh
tests/farm/test_farm.sh --broker-url http://127.0.0.1:1126 --verify-only --mcp
```

Then run the complete native evaluation:

```sh
cd evaluation/farm-reference
../../.venv/bin/python run_codex_questions.py \
  --broker-url http://127.0.0.1:1126 \
  --context-url http://context/user-context.jsonld \
  --model gpt-6.1-sol
```

The context URL above belongs to the existing isolated farm broker's Compose
network. It must be reachable by that broker; use the appropriate context URL
for another deployment. The server endpoint is never changed internally.

Use `--question F01` for a single-question smoke test; repeat it to select a
subset. Use `--timeout` to change the default 300-second limit per question.
Use `--output` to select a new output directory. Existing evidence is never
overwritten. Use `--python` if project dependencies are installed elsewhere.
The virtual environment interpreter path is preserved without resolving its
symlink to the base interpreter.

The launcher prints the output folder, each question and progress every 15
seconds. Results are saved under `runs/codex-<UTC timestamp>/`, using the same
answer/event/error/result filenames as the Claude launcher. Full execution can
take several minutes. A successful process exit is COMPLETED_UNREVIEWED, not a
correctness PASS. Correctness needs review of returned data and final answers.

## Isolation and evidence

The native invocation uses `--ignore-user-config`, `--ephemeral`, the read-only
sandbox and invocation-specific MCP settings. Shell and web tools are disabled.
Only the five FIWARE read tools are enabled and approved. The server is forced
read-only. The configured MCP provider is required: startup failure stops the
run. User configuration and broker entities are not modified.

Each run captures UTC date, client version, requested model, dataset source
revision, fixture/context hashes, question-bank hash, Python/SDK versions, SDK
supported protocol revision, MCP Git commit and actual server.py/broker.py hashes.
The supported SDK protocol is not represented as separately observed wire
negotiation. The requested Codex model is not represented as an independently
reported resolved model revision.

The launcher retains native event streams and stops on failed initialization,
timeouts, missing native calls, framework errors or unexpected non-MCP tool use.
Expected broker 404 results remain normal completed MCP exchanges and are
reviewed according to the question. Failures do not cause a fallback to Python
queries, direct HTTP, broader permissions or another model.

Official references: [Codex MCP configuration](https://learn.chatgpt.com/docs/extend/mcp)
and [non-interactive execution](https://learn.chatgpt.com/docs/non-interactive-mode).
The installed CLI 0.165.0 help confirmed the execution flags during preparation.

## Archive an experiment after execution

Keep raw runs local. Create the portable record under `experiments/`:

```sh
../../.venv/bin/python archive_experiment.py --run runs/codex-REPLACE_WITH_RUN_TIMESTAMP
```

The archive remains UNREVIEWED until a matching review is supplied with
`--review path/to/review.json`. Reviews must identify the same run and match all
per-trace SHA-256 hashes. Archive output is never overwritten; retain an unreviewed
archive or choose a different `--output` after review.

An archive includes the exact questions and prompts, model answers, native MCP
arguments and returned broker data, UTC date, versions and hashes. It excludes
account/session metadata and model reasoning blocks. Known credential header
keys and local home/repository paths are removed. Review curated artifacts before
publishing, especially if testing private data or remote deployments. Never
commit account files, .mcp.json or entire raw client event streams automatically.

The existing Claude experiment is reviewed as 12 PASS and four PARTIAL. Its
source/SDK hashes were captured when archived, not during the original execution;
the manifest explicitly records this provenance limitation. Codex source hashes
are collected before execution. Keep both successful and unsuccessful outcomes.

## Local launcher tests

From the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover \
  -s evaluation/farm-reference -p 'test_*questions.py' -v
```

Twelve local launcher/archive tests passed during preparation. All 16 generated
Codex prompts matched the actual Claude prompts byte for byte. The parser was
also checked against the earlier native Codex trace with 14 MCP calls; that older
run used different questions and is not a result for this new experiment.

The managed session's actual native startup probe failed before tool execution:

```text
Error: failed to initialize in-process app-server client: Operation not permitted (os error 1)
```

It made zero MCP calls and was classified BLOCKED. Run the command above from a
normal authorized terminal; do not weaken security settings to bypass the block.

## Reviewed 2026-10-29 execution

The normal terminal run `codex-20261029T151154441881Z` completed all 16 questions
with 128 native MCP calls and was reviewed as 16 PASS. It used requested model
`gpt-6.1-sol` and Codex CLI 0.165.0. All prompts matched the Claude run byte for
byte. Nine original missing-target lookups correctly returned HTTP 404; the other
119 broker results were HTTP 200. The earlier managed startup probe remains
BLOCKED and is not counted as a successful run. Source hashes and dataset hashes
matched the recorded pre-execution snapshot. See the dated record under
`experiments/smart-farming/2026-10-29-codex-20261029T151154441881Z/`.

F14 repeated the complete Animal query, and F15 repeated page zero before
correctly returning 47 unique IDs. These are recorded as unnecessary reads, not
incorrect final answers. No historical query, write operation, or general model
superiority claim is established by this evaluation.

The publication utilities now also include six offline archive-comparison tests.
The combined 18 launcher/archive/comparison tests passed with no model or broker
calls. Run all with the same unittest command using the pattern test_*.py.
