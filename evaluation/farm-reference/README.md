# Smart Farming reference questions

This directory contains an independent question bank, expected answers and native
Claude Code/Codex launchers. The model receives questions and MCP tools only.
Expected answers are kept on the evaluator side.

* [Claude execution](RUNNING.md)
* [Codex execution and experiment export](CODEX.md)
* [Dated experiment records](../../experiments/README.md)
* [Fixture loader and broker verification](../../tests/farm/README.md)

The fixed source revision is `05c6fdd118b731a5c362b0892c9efb00968dc7a4`.
It produces 61 entities: 47 Animal, six AgriParcel, four Building and four Person.
Nine relationships point to four original absent targets. The same fixtures
support both clients. No generic MCP server changes are needed for evaluation.

`questions-only.json` is the English model-facing bank. `reference-answers.json`
contains expected results and limitations. `reference-entities.json`,
`reference-relationships.json` and `reference-attributes.csv` support offline
inspection. Rebuild them from this directory using the original fixture:

```sh
../../.venv/bin/python build_reference.py
```

The generator does not contact or change a broker. Its update/replace order
matches the original five source batches. Comparison should use exact IDs and
values rather than prose similarity. A missing measurement is not a low value,
a missing target is not an alternative similarly named entity, and an absent
temporal tool is not proof that no historical backend exists.

Client output remains under the ignored `runs/` directory. Export reviewed
curated records to `experiments/` before publishing. Never give the evaluated
client file access to reference answers, fixtures or previous answers. Prompt
hashes and native MCP evidence distinguish this from executing predefined API
queries in Python. A zero process exit code is not a correctness PASS.

Run the 18 local launcher/archive/comparison tests from the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover \
  -s evaluation/farm-reference -p 'test_*.py' -v
```

No model call or broker connection is required by these local tests. The full
native experiments use each CLI's normal authenticated account. No account
credentials or global MCP configuration are committed.

Use compare_experiments.py to compare two dated archives. See the experiments
index for exact commands. This checks experiment compatibility and compares
existing reviewed results; it does not automatically judge model prose.
