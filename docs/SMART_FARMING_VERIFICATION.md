# Smart Farming execution record

Date: 2026-10-28. The user approved the isolated strategy and exact source replay. The existing MCP server, current broker and local MCP configuration were not modified. No commits or pushes were made.

## Verified final result

PASS. The final run saved summary.json with 273 passing assertions and no failed assertions. It reported `already loaded; content verified without writing`. The source dataset was loaded on the preceding run; the final run confirmed repeat loading without modifying stored entities. These are live evaluation assertions, not 273 pytest test cases.

The user executed Docker and local networking operations in a regular macOS terminal. Codex inspected the saved raw responses and assertion records. No MCP implementation, original source file, existing Building/Room/Sensor configuration or existing Docker project was changed. The permanent MCP checkout remains clean on refactor. No commits or pushes were created.

| Capability | Final result | Evidence |
| --- | --- | --- |
| Pinned original dataset and repeatable generation | PASS | Source commit 05c6fdd118b731a5c362b0892c9efb00968dc7a4; two equal generated payloads, seed 1729 |
| Isolated Orion, Mongo and context deployment | PASS | Dedicated fiware-farm-audit project, broker bound to 127.0.0.1:1126 |
| Original entity loading | PASS | All five batches accepted without data repairs; 61 expected IDs and contents verified |
| JSON-LD context | PASS | Original served JSON content and media type checked; deployment context used in direct and MCP requests |
| Direct discovery, content, filters and errors | PASS | Actual values and identifiers checked, including expected 400 and 404 responses |
| Independent MCP STDIO client | PASS | Seven tools discovered with descriptions and input/output schemas; 94 final tool calls |
| MCP numeric and categorical queries | PASS | Actual entities and values matched the frozen original payloads |
| Projection and pagination | PASS | heartRate projection; Animal pages of 20, 20 and 7 without missing or duplicate IDs |
| Explicit relationships and missing targets | PASS | 102 edges checked, 93 resolved and nine returned expected 404 responses |
| MCP read only policy | PASS | Both write tools blocked; full broker content unchanged afterwards |
| Repeat loading | PASS | Final raw HTTP trace contains GET requests only |
| HTTP transport for Smart Farming | NOT RUN | This evaluation used STDIO; earlier Building/Room/Sensor results are separate |
| Claude Code natural language evaluation | COMPLETED | Native client made 19 MCP calls; four cases PASS, discovery explanation PARTIAL; see CLAUDE_SMART_FARMING_EVALUATION.md |
| Codex native natural language evaluation | PASS | Native CLI made 14 MCP calls; all five cases PASS, including recovery from an unsuitable projection; see CODEX_SMART_FARMING_EVALUATION.md |

### Environment

The host is macOS 26.6 on arm64. Python is 3.14.6, MCP SDK is 2.3.0, Docker client and engine are 29.6.2, Docker Desktop is 4.85.0, and Compose is v5.3.1. Orion's actual version response is 1.12.0.

| Container image | Actual platform | Image ID |
| --- | --- | --- |
| fiware/orion-ld:1.12.0 | linux/amd64 | f562a93ed84c |
| mongo:4.4.29 | linux/amd64 | 52c42cbab240 |
| python:3.12.8-slim context server | linux/arm64/v8 | 2199a62885a1 |

The network disabled generator used the amd64 Python image and Bash 5.2.15, recorded separately in manifest.json. Image tags and recorded IDs describe this run; tags alone are not immutable image identities.

### Dataset and verified filters

Actual counts are 47 Animal, 6 AgriParcel, 4 Building and 4 Person. Animals comprise 43 cattle, including three calves, and four pigs. No Device or AgriCrop entities were fabricated. Original scripts, contexts, type definitions and data values were retained.

| NGSI-LD query | Actual result |
| --- | --- |
| Animal, heartRate>56 | cow005 only, heartRate 70 |
| Animal, species=="pig" | pig001 through pig004, four entities |
| Animal, species=="dairy cattle" | 43 cattle |
| Animal, weight>500 | cow001 with 838 KGM and cow021 with 699 KGM |
| AgriParcel, temperature>10 | Parcels 001 through 003, each 10.4 CEL |

All seven MCP tools were invoked. get_broker_info, get_types, get_attributes, get_entity and query_entities exercised live read operations. create_entity and update_entity were invoked solely to verify read only rejection; actual MCP writes were intentionally not enabled.

Four distinct missing relationship targets remain unchanged from the original data: urn:ngsi-ld:AgriCrop:BuckWheat, urn:ngsi-ld:AgriCrop:Corn, urn:ngsi-ld:AgriCrop:Grass and urn:ngsi-ld:Person:001. They account for nine unresolved edges. The actual person001 ID includes the person prefix. This is dataset quality evidence, not a reason to invent entities or rewrite identifiers.

### Verification artifacts and test counts

The local ignored evidence directory is evaluation/smart_farming/local-evidence. summary.json and checks.json are authoritative for the final result. final-direct.jsonl contains the 118 direct requests from the final run, all GET. final-mcp.jsonl contains its 94 MCP calls, including arguments and structured results. The original direct.jsonl and mcp.jsonl retain earlier unsuccessful attempts as well; they were not rewritten.

Stored content is in stored.json, the original expected snapshot is in expected.json, and relationship results are in relationships.json. Tool descriptions and schemas are in mcp-tools.json. Docker versions, image information, container status, served context and source provenance are retained separately.

The combined available pytest suite reported 72 passed, one skipped and 20 deselected using `.venv/bin/python -m pytest -q -m 'not integration' -rs`. This includes 16 new loader and verifier safeguard tests. The skipped test requires a local listening socket, forbidden by this Codex sandbox. The 20 existing Building/Room/Sensor integration cases were not rerun against the separate Smart Farming dataset. The live Smart Farming result is the independent 273 assertion run described above.

### Claude Code connection

A private local configuration has been materialized at evaluation/smart_farming/local-evidence/claude.mcp.local.json. It points to the unchanged server in /Users/dncampo/code/FIWARE-MCP-Server, uses the existing verified Python environment, supplies http://context/user-context.jsonld, selects the dedicated broker and sets NGSI_LD_ENABLE_WRITES=false. Its paths and write policy were checked. It is ignored by Git and does not replace the existing .mcp.json.

Run this from the regular terminal:

```sh
claude --strict-mcp-config --mcp-config /Users/dncampo/code/MCP_CB_refactor/evaluation/smart_farming/local-evidence/claude.mcp.local.json
```

Use `/mcp` to inspect the connection and tool count. Then request broker discovery before issuing application queries. Suggested requests are in SMART_FARMING_AUDIT.md. The pending natural language evaluation has now been executed using the real Claude Code client and reviewed in CLAUDE_SMART_FARMING_EVALUATION.md. The model generated valid numeric and categorical queries, followed relationships and paginated all Animal IDs. Its discovery explanation has a minor unsupported generalization; the data results were correct.

### Corrections and remaining limitations

The runner initially set Content-Type on bodyless GET requests. That was corrected and regression tested. The isolated Compose initially omitted the source deployment's -mongocOnly flag, causing legacy upsert to reject VocabProperty. Restoring the flag preserved the source data types. Type discovery on an empty broker in that mode hung; readiness now uses version and entity queries, while discovery remains fully asserted after population. An initial comparison also rejected documented singleton VocabProperty array normalization; it now accepts only that semantic equivalence and retains strict checks for ordinary values and coordinate arrays.

Empty broker type discovery remains an Orion 1.12 compatibility limitation. Native Claude Code reasoning has now been evaluated; Smart Farming HTTP transport remains untested in this phase. IoT provisioning, simulators and context source federation were deliberately excluded, so Device relationships from that separate flow are not claimed. Existing missing targets, inconsistent comments and undeclared context terms remain documented in the audit. No server fixes or additional MCP tools were introduced.

### Reproduction and cleanup

The exact successful continuation command is in the command section below. On a fresh machine, first clone the source repository separately and check out the pinned commit as described in SMART_FARMING_AUDIT.md, then pass that directory through --source. The runner starts only its dedicated Compose project. Preserve the generated manifest and output directory for repeat runs. A project or volume already present without that manifest is refused rather than adopted or overwritten.

To stop this evaluation later while retaining its database:

```sh
FARM_SOURCE_DIR=/private/tmp/fgs2025-smart-farming-audit docker compose -p fiware-farm-audit -f /Users/dncampo/code/MCP_CB_refactor/evaluation/smart_farming/compose.review.yaml down
```

This cleanup command has not been executed. No volume deletion or host prune is needed.

Evaluation files added are audit.py, capture.py, run.py, diagnose.py, evaluate_claude.py, test_runner.py, inventory.json, compose.review.yaml, compose.debug.yaml, claude.mcp.example.json, claude-evaluation.txt and .gitignore under evaluation/smart_farming, plus SMART_FARMING_AUDIT.md, CLAUDE_SMART_FARMING_EVALUATION.md and this report under docs. They are in the currently writable MCP_CB_refactor workspace, not yet transferred to the permanent Git checkout.

## Archived execution attempts

The revised readiness check allowed all five original batches to load successfully. Actual stored counts are 61 entities: 47 Animal, 6 AgriParcel, 4 Building and 4 Person. All source payloads were used without data repairs. In particular, Orion accepted the six attributes without an explicit Relationship type and returned them normalized; the earlier audit's concern did not require a source change in this mode.

The live run recorded 269 passed checks and four failed content comparisons. Each failure was a Building category VocabProperty: the input singleton vocab arrays were returned as scalars (farm, barn or water_tower). Orion documents singleton array reduction for normalized VocabProperty output in its [release notes](https://github.com/FIWARE/context.Orion-LD/releases). This is representation normalization, not loss of a category or an MCP filtering error.

Adjusted only the evaluation comparator to equate scalar and singleton list forms of VocabProperty.vocab. It still rejects lost values from a multi value vocab, changed ordinary Property arrays, and changed coordinate array structure. The original payload and stored response files are unchanged. A final repeat run is needed to obtain a full live PASS and exercise loading again without writes.

The fresh debug restart isolated the failure further: /version returned 200, /entities with idPattern=.* returned 200 and an empty array, and all three /types variants timed out. The issue affects type discovery before any dataset has been inserted, independently of the custom Link context.

The 1.12.0 [mongocEntityTypesGet implementation](https://github.com/FIWARE/context.Orion-LD/blob/1.12.0/src/lib/orionld/mongoc/mongocEntityTypesGet.cpp) returns NULL for an empty result. [dbEntityTypesGet](https://github.com/FIWARE/context.Orion-LD/blob/1.12.0/src/lib/orionld/db/dbEntityTypesGet.cpp) interprets NULL as a reason to use the legacy driver, even in mongocOnly mode. This source path is consistent with the observed empty broker hang. The runner now uses version plus a bounded entity query for initial readiness, and still performs the existing direct and MCP type discovery assertions after loading. The MCP implementation has not been changed to hide this limitation. Native MCP discovery on an empty broker in this mode remains a known broker compatibility limitation.

Added an empty broker readiness regression. Loader safeguards now have 11 passing tests. Live loading and discovery after population remain pending the next terminal run. The following paragraphs retain the earlier attempts.

After enabling -mongocOnly, /version initially answered but NGSI-LD readiness requests timed out. The original 60 attempt retry loop obscured the failure and could run for about 11 minutes when /types timed out on each attempt. It was reduced to three attempts with progress output and persisted HTTP exception records.

The subsequent bounded diagnostic timed out on all five probes, including /version. Mongo remained healthy. Its currentOp output showed no long running entity query or lock wait. Context service logs show successful original context retrieval, but the available broker warnings do not identify the hang. Request worker exhaustion after accumulated hanging calls is a hypothesis, not a confirmed root cause.

Prepared diagnose.py --restart-orion-debug and a separate compose.debug.yaml override. This command recreates only fiware-farm-audit's Orion service, retains the database and other services, then captures bounded HTTP probes and debug evidence under debug-prefixed filenames. It does not change the source dataset or MCP implementation. Execution of this new diagnostic remains pending the regular terminal.

On the next run, Orion-LD 1.12.0 connectivity and MCP STDIO communication succeeded. All seven tool descriptions and schemas were discovered. Read only create and update rejection, nonexistent entity errors and invalid query errors passed. The unchanged broker content check passed.

The first import returned HTTP 207 with success empty and 40 errors reporting Invalid type for attribute. stored.json confirms zero entities. The remaining static batches were not attempted. The recorded 80 failed checks are against the unpopulated expected dataset and do not establish MCP filtering or traversal defects; 11 checks passed.

The cause is an omitted broker startup setting in the evaluation Compose file. At tag 1.12.0, [orionldPostBatchUpsert.cpp](https://github.com/FIWARE/context.Orion-LD/blob/1.12.0/src/lib/orionld/serviceRoutines/orionldPostBatchUpsert.cpp#L102) selects the legacy implementation when experimental is false. [kjTreeToContextAttribute.cpp](https://github.com/FIWARE/context.Orion-LD/blob/1.12.0/src/lib/orionld/legacyDriver/kjTreeToContextAttribute.cpp#L263) accepts Property, Relationship, LanguageProperty and GeoProperty in that path, but rejects VocabProperty with the exact observed error. [orionld.cpp](https://github.com/FIWARE/context.Orion-LD/blob/1.12.0/src/app/orionld/orionld.cpp#L1133) enables experimental mode when -mongocOnly is set. The original demonstration already includes that flag.

Fixed only the isolated Compose command by restoring -mongocOnly. Dataset types and values are unchanged; no VocabProperty conversion, source repair or MCP implementation change was made. The same continuation command recreates the isolated Orion service with this setting and retains its Mongo volume. The existing broker on port 1026 is outside that Compose project. Live success after this configuration correction remains pending the next external run.

### Earlier readiness failure

The user's regular terminal successfully accessed Docker, generated the dataset twice, and started the isolated stack. The generated payload files match exactly. The generator used Bash 5.2.15 on x86_64 and produced 40 cows. The frozen intended final counts are 47 Animal, 6 AgriParcel, 4 Building and 4 Person. No generated birthdate anomalies were recorded.

The broker answered 59 saved NGSI-LD type probes with HTTP 200 and an empty typeList. All 59 saved /version responses were HTTP 400, explicitly rejecting Content-Type on a GET request. This was a test runner error, not a container readiness or MCP implementation failure. No entity load was reached.

Fixed run.py to omit a global Content-Type header and let httpx set application/json only when a JSON body is supplied. Added a regression test covering bodyless GET and JSON POST, preserving the Link context header on both. Loader safeguard tests now report 10 passed. The MCP implementation is unchanged.

Rerun the continuation command below. It reuses the saved manifest, generated payloads and existing isolated services. No volume reset or new source export is needed. Actual /version success, data insertion and MCP verification remain pending that rerun. The following original sandbox record is retained as historical evidence.

## Original sandbox result

Live execution is BLOCKED by Docker socket permissions in this Codex session. Docker client 29.6.2 on darwin/arm64 and Compose v5.3.1 are installed. The existing Python environment has MCP SDK 2.3.0. Docker reports:

```text
permission denied while trying to connect to the docker API at unix:///Users/dncampo/.docker/run/docker.sock
```

The runner stopped at its first Docker version check, before image generation, Compose startup or broker writes. No Docker resources were created by this test. No socket permissions were changed and no sandbox bypass was attempted. A localhost probe to port 1126 found no running broker there; that is not evidence of a broker defect.

| Check | Result |
| --- | --- |
| Original source audit | PASS, 15 matching Git blob hashes |
| Existing tests excluding integration marker | 56 PASS, 1 SKIP, 20 deselected |
| New loader safeguards | 9 PASS |
| Combined available suite on final discovery | 65 PASS, 1 SKIP, 20 deselected |
| Dynamic dataset generation | BLOCKED, Docker access required |
| Isolated broker startup and readiness | BLOCKED |
| Exact source load and inserted counts | BLOCKED |
| Direct API filters, content and relationships | BLOCKED |
| Independent SDK client through MCP STDIO | BLOCKED |
| Claude Code Smart Farming session | NOT RUN |

The existing skipped test is test_streamable_http_real_client: the runtime sandbox forbids binding local sockets. This is distinct from the 20 deselected existing broker integration tests. The prior 77 live tests remain historical baseline evidence; they were not reproduced here against Smart Farming.

## Prepared runner

`evaluation/smart_farming/run.py` provides one explicit workflow, using the existing project dependencies and Docker CLI. It does not invoke upstream services, import scripts with live curl, IoT provisioning or host cleanup.

It verifies the pinned source files, captures the original dynamic generator twice in a network disabled Bash container with seed 1729 and COW_COUNT=40, then compares generated payloads. Registration is captured but excluded because the minimal stack has no forwarder. It preserves the original four static batches, their order and their update or replacement options.

The intended population is 61 entities: 47 Animal, 6 AgriParcel, 4 Building and 4 Person. These counts have not been achieved or verified live. Six source attributes remain untyped. On a rejected or partially applied batch, the runner stops further writes and reports the response. It then performs read only inspection of whatever is actually stored; partial data cannot satisfy the expected content and count checks. No data repair is enabled.

A matching repeated load only verifies stored content. A mismatched nonempty broker is not overwritten. Existing resources with the selected project name, network or database volume are refused unless the local manifest from this workflow exists. A failed partial load is not reset or silently resumed; its evidence and data remain for diagnosis.

Automated verification covers direct entity content, ID retrieval, type and attribute discovery, numeric and string filters, projection, relationship targets and errors. It then starts the unchanged server as a subprocess and uses the official independent SDK client through STDIO to discover seven tools, inspect schemas, read entities, filter, project, paginate, resolve relationship targets and check errors. Both write tools are invoked only to assert read only rejection, followed by verification that broker content did not change. This is an automated protocol test, not a Claude Code reasoning evaluation.

## Command to continue from the regular macOS terminal

The audited source export already exists at the path below. It contains the original files required by the runner and is verified against the pinned Git blob hashes. If it has been removed, use the clone instructions in SMART_FARMING_AUDIT.md and change --source accordingly. Do not use the original services script.

```sh
/Users/dncampo/code/MCP_CB_refactor/.venv/bin/python \
  /Users/dncampo/code/MCP_CB_refactor/evaluation/smart_farming/run.py \
  --source /private/tmp/fgs2025-smart-farming-audit \
  --output /Users/dncampo/code/MCP_CB_refactor/evaluation/smart_farming/local-evidence \
  --mcp-root /Users/dncampo/code/FIWARE-MCP-Server
```

The existing local-evidence folder contains only the sandbox blocker record, so this command can use it. The command may pull the pinned images and creates only the reviewed fiware-farm-audit project. It never stops or removes other containers. It exits nonzero on a blocker or any failed assertion; inspect summary.json rather than assuming startup or HTTP 200 means success. Initial image downloads and emulation on Apple Silicon can take time.

After execution, retain the complete output folder and report the terminal result. In particular, inspect summary.json, manifest.json, direct.jsonl, stored.json, checks.json, relationships.json, mcp.jsonl and mcp-tools.json where created. JSONL records contain actual request arguments, statuses and returned data. No evidence is uploaded. The local evidence folder is ignored by its own .gitignore.

If a source batch is rejected, send the recorded diagnostic before changing data or rerunning with a new profile. Do not delete the dedicated volume to hide the rejection. If all checks pass, rerun the same command to exercise verification without writes. `--verify-only` skips loading and Compose startup, using the previously generated payloads and running broker for a further read only check.

Once the dataset is verified, use the separate Claude Code connection instructions in SMART_FARMING_AUDIT.md and its natural language requests. Keep the initial MCP write policy false. The existing Building/Room/Sensor configuration remains available.

## Commands executed in Codex

```sh
docker version
docker compose version
curl --noproxy '*' --connect-timeout 3 --max-time 3 -sS http://127.0.0.1:1126/version
.venv/bin/python -m pytest -q -m 'not integration'
.venv/bin/python -m pytest -q -m 'not integration' -rs
.venv/bin/python -m pytest -q evaluation/smart_farming/test_runner.py
.venv/bin/python evaluation/smart_farming/run.py --source /private/tmp/fgs2025-smart-farming-audit --output evaluation/smart_farming/local-evidence
```

Offline safeguards verify capture destination restrictions, refusal to overwrite captured output, source update and replacement behavior, rejection of 207/400/409/500 without subsequent writes, refusal to overwrite mismatched stored data, and repeat verification without writes. Mocked HTTP responses in these nine tests establish loader safeguards only; they do not establish Orion compatibility.

## Files added or adjusted for this execution attempt

Added evaluation/smart_farming/capture.py, run.py, test_runner.py, .gitignore and this report. Updated the Compose file comment to reflect approval and the audit report to point to this execution record. Evidence is local only. Production server.py and broker.py were not edited, and no existing fixture data was changed.
