# Codex native MCP evaluation

Date: 2026-10-28. Final status: PASS through the actual native Codex CLI in the user's normal macOS terminal. All five functional tests passed. The run made 14 native MCP calls and completed in 96.33 seconds. No independent Python MCP test is counted as a Codex result. The earlier managed-session startup failure is retained below as separate evidence.

## Verified native execution

The executed client was codex exec, launched by evaluate_codex.py with the per invocation configuration described below. The requested model was gpt-6.1-sol; the event stream does not separately identify a resolved model revision. The process exited with code zero, without reaching its timeout. Exit status was not used as the sole pass criterion.

The saved JSONL contains 14 completed mcp_tool_call items, all with server=fiware_farm and framework error=null. There are also three agent messages and a completed model turn. No shell, file inspection, web, other MCP or alternative client calls appear in the trace. All dataset queries were performed inside a fresh session in an empty temporary directory with the independent natural language prompt. The launcher read connection settings, not dataset files or previous answers. The only expected count provided was the user's 47 Animals, which the model independently verified.

| Connectivity stage | Result | Actual evidence |
| --- | --- | --- |
| MCP server startup | PASS | The configured STDIO server served real native tool requests |
| MCP protocol connectivity | PASS | Native mcp_tool_call events contain structured tool results |
| Broker connectivity | PASS | get_broker_info returned ok=true, HTTP 200, successful type and version probes, Orion-LD 1.12.0 |
| Successful native execution | PASS | Fourteen completed calls; five distinct read tools invoked |

The final answer identified all seven tool definitions and relevant input formats. Actual call counts were get_broker_info 1, get_types 1, get_attributes 4, get_entity 3 and query_entities 5. create_entity and update_entity were not invoked. Broker information confirmed writes_enabled=false.

## Functional test results

| Test | Result | Grounded findings |
| --- | --- | --- |
| 1: discovery | PASS | Found Animal 47, Person 4, AgriParcel 6 and Building 4. Inspected one entity per type and observed attribute metadata. Explicitly said schema validation and a registry were not established. |
| 2: attribute filtering | PASS | Independently chose q=weight>800 after observing a weight of 838. Returned only urn:ngsi-ld:Animal:cow001, value 838 and stored unitCode KGM, with a complete result page. |
| 3: Animal relationships | PASS | Reused the cow001 discovery sample. Followed ownedBy to Person:person002 and locatedAt to AgriParcel:003, retrieving both actual target entities. No relationship or target was invented. |
| 4: missing target | PASS | Used AgriParcel:001's actual cropType relationship to AgriCrop:BuckWheat. Reported the exact target and structured HTTP 404 ResourceNotFound response without repair or substitution. |
| 5: pagination | PASS | Recovered from an unsuitable projection, then used name projection with limit 20 and offsets 0, 20 and 40. Retrieved 20, 20 and 7 Animals, matched total 47, stopped on terminal pagination and listed all 47 complete URNs. |

The reviewer checked every returned entity field against captured broker data after model execution, verified type counts and relationship source IDs, and compared both the pages and the final answer's complete ID array with the full stored Animal ID set. There were no duplicate or omitted IDs. The final answer did not fabricate types, attribute names, values, units or relationships. It did not turn the Person entity named Napoleon the Pig into an Animal.

## Exact native calls

The table is ordered by native event ID, not response completion time; some independent reads completed in parallel. C means the explicit context_url http://context/user-context.jsonld. N means representation=normalized. No other arguments were supplied beyond those listed.

| Event | Tool | Arguments | Result |
| --- | --- | --- | --- |
| item_1 | get_broker_info | {} | ok=true, 200, writes false |
| item_2 | get_types | limit=100, offset=0 | Four types, complete |
| item_3 | get_attributes | entity_type=Person, sample_limit=1, C | Metadata and one sample |
| item_4 | get_attributes | entity_type=Animal, sample_limit=1, C | Metadata and cow001 sample |
| item_5 | get_attributes | entity_type=AgriParcel, sample_limit=1, C | Metadata and parcel 001 sample |
| item_6 | get_attributes | entity_type=Building, sample_limit=1, C | Metadata and barn002 sample |
| item_7 | get_entity | entity_id=urn:ngsi-ld:Person:person002, C, N | 200, Napoleon the Pig, type Person |
| item_8 | get_entity | entity_id=urn:ngsi-ld:AgriParcel:003, C, N | 200, North Pasture |
| item_9 | get_entity | entity_id=urn:ngsi-ld:AgriCrop:BuckWheat, C, N | ok=false, 404, original target absent |
| item_10 | query_entities | type=Animal, q=weight>800, attrs=["weight"], limit=20, offset=0, C, N | cow001 with weight 838 KGM |
| item_12 | query_entities | type=Animal, attrs=["id"], limit=20, offset=0, C, N | 200, empty array, total 0 |
| item_13 | query_entities | type=Animal, attrs=["name"], limit=20, offset=0, C, N | 20 IDs, total 47, next_offset=20 |
| item_14 | query_entities | type=Animal, attrs=["name"], limit=20, offset=20, C, N | 20 IDs, total 47, next_offset=40 |
| item_15 | query_entities | type=Animal, attrs=["name"], limit=20, offset=40, C, N | Seven IDs, total 47, has_more=false, next_offset=null |

The exact call and response records remain in the ignored local-evidence/codex-evaluation.jsonl. The concise reviewed record is codex-evaluation.calls.json. codex-evaluation.execution.json now records PASS, native_mcp_calls=14 and PASS for Tests 1 through 5. The stderr file contains only Reading prompt from stdin, with no startup or protocol error. The full final answer remains in the native event stream.

## Errors, recovery and limitations

The model initially assumed attrs=["id"] could provide minimal entity projection. The broker returned HTTP 200 and zero matches. Codex compared that result with the observed 47 Animal metadata and sample, did not claim the collection was empty, and changed the projection to the observed name Property. The next three calls returned the correct complete collection. This was one avoidable model argument choice followed by successful recovery, not an invalid numeric q expression or a remaining filtering failure.

The missing AgriCrop response was an expected unsuccessful entity lookup, not an MCP transport error. It was accurately reported as ok=false with status 404. No retries, repaired query strings, synthetic entities or substituted target IDs were used. The initial readiness connection retry seen in the earlier dataset loader is not part of this native model run.

Future tool documentation could clarify that attrs selects observed attributes and that identifier/type fields are already returned. That is a recommendation only: no tool description or server code was changed in this phase. The existing MCP correctly preserved the broker's empty result and the missing target diagnostic.

This is one successful run on one populated dataset, not a statistical reliability benchmark. Read only policy was reported and no write calls occurred; actual create/update behavior was not evaluated here. STDIO was tested, not HTTP. Snapshot isolation during pagination, geo queries and behavior on other brokers remain outside this run. The original managed session still has the startup restriction described below; passing in the normal terminal does not attach FIWARE tools to this already running conversation.

## Native client comparison

Both clients demonstrated the requested functional capabilities through their own native MCP integration. Claude used 19 calls; Codex used 14. Claude performed three filter tasks and seven relationship target lookups, while Codex performed one filter task and three target lookups, so those totals do not establish a model efficiency ranking.

Claude's earlier evaluation recorded four PASS cases and one PARTIAL discovery explanation for an unsupported general claim about schema registries. Codex's explanation explicitly distinguished observed metadata from unestablished schema capabilities, and all five cases PASS. Codex made an initial projection mistake and recovered; Claude did not make that projection attempt. Claude reported a missing Person:001 target, while Codex reported a missing AgriCrop:BuckWheat target. Both were grounded in stored relationships.

The prompts and workloads were comparable rather than identical, and only one session per model was reviewed. No conclusion about general model superiority is warranted. The 273 automated assertions remain separate server evidence, not native model calls.

## Connection and environment

The local Codex CLI is 0.165.0. Its configured model is gpt-6.1-sol. The existing environment is macOS 26.6 on arm64, Python 3.14.6 and MCP SDK 2.3.0. The unchanged MCP implementation is in /Users/dncampo/code/FIWARE-MCP-Server, branch refactor, inspected HEAD 1ecb4dc. That checkout's working tree is clean.

The active Codex session's available tool inventory contains no FIWARE tools. Read only inspection of ~/.codex/config.toml found two MCP entries: node_repl, enabled, and computer-use, disabled. It contains no FIWARE entry. Credentials and unrelated environment values were not printed.

A fresh native CLI invocation was prepared with per invocation configuration, without editing the global file. It reuses only the existing local Smart Farming connection configuration from evaluation/smart_farming/local-evidence/claude.mcp.local.json. Reading that configuration does not supply dataset answers. Its settings are:

| Setting | Value |
| --- | --- |
| MCP name | fiware_farm |
| Transport | STDIO |
| Command | Existing .venv/bin/python in MCP_CB_refactor |
| Server script | /Users/dncampo/code/FIWARE-MCP-Server/server.py |
| Broker | http://127.0.0.1:1126 |
| Default and allowed context | http://context/user-context.jsonld |
| Write policy | NGSI_LD_ENABLE_WRITES=false |
| Required startup | true, timeout 15 seconds |
| Tool timeout | 20 seconds |
| Read permissions | Five existing read tools approved for this invocation |

The command uses --ignore-user-config so unrelated user MCP entries are not loaded; authentication still uses the normal Codex account. It also uses --no-daemon, --ephemeral, --sandbox read-only, features.shell_tool=false and web_search=disabled. It runs in an empty temporary directory. No unrestricted sandbox option, network policy relaxation, global registration or security bypass is proposed.

These configuration choices follow the [official OpenAI MCP documentation](https://learn.chatgpt.com/docs/extend/mcp?surface=cli) and [configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference). The installed CLI help confirmed the execution flags. Registration options alone are not evidence of successful initialization or invocation.

## Original managed-session attempt

Executed from the managed workspace:

```sh
.venv/bin/python evaluation/smart_farming/evaluate_codex.py --connectivity-only --timeout 30 --label codex-sandbox-connectivity
```

This launcher invokes codex exec, not the Python MCP Client. The connectivity prompt requests discovery of the native FIWARE definitions and exactly one get_broker_info call, then stops before dataset queries. Its actual output was:

```text
WARNING: proceeding, even though we could not create PATH aliases: Operation not permitted (os error 1)
Reading prompt from stdin...
Error: failed to initialize in-process app-server client: Operation not permitted (os error 1)
```

The CLI exited with code 1 after approximately one second. Its JSON event file is empty. Actual native MCP tool invocations: zero. No tool names or arguments can be reported as executed. The intended get_broker_info arguments were {}, but that call was not made.

The exact failing stage is Codex's in-process app-server client initialization. The CLI does not name the denied resource or syscall, so the evidence does not justify identifying it as Docker access, broker networking or an MCP protocol mismatch. It is an execution permission failure before any native tool invocation was recorded. No further initialization retries or fallback HTTP requests were attempted.

Evidence retained in the ignored evaluation/smart_farming/local-evidence directory:

1. codex-sandbox-connectivity.stderr.txt: exact startup diagnostic.
2. codex-sandbox-connectivity.jsonl: zero bytes, no native events.
3. codex-sandbox-connectivity.execution.json: exit status, requested model, elapsed time and BLOCKED classification, with native_mcp_calls=0.

## Original blocked attempt results

| Check | Classification | Evidence |
| --- | --- | --- |
| Active session has FIWARE tools | BLOCKED | No FIWARE tools in available inventory |
| Fresh native client startup | BLOCKED | In-process app-server initialization denied |
| MCP server startup and protocol connectivity | BLOCKED | Not established by this attempt |
| Broker connectivity through native Codex | BLOCKED | No tool invocation recorded |
| Test 1: discovery | BLOCKED | Not executed |
| Test 2: numeric or categorical filtering | BLOCKED | Not executed |
| Test 3: Animal relationship traversal | BLOCKED | Not executed |
| Test 4: missing target handling | BLOCKED | Not executed |
| Test 5: complete Animal pagination | BLOCKED | Not executed |

No query syntax, reasoning accuracy or recovery behavior could be scored from that unstarted attempt. The regular terminal run described above supplied the missing native execution evidence. No server implementation, tool definition or broker entity was changed.

## Reproduction command used in the normal macOS terminal

The launcher and a separate natural language prompt have been prepared. Run:

```sh
/Users/dncampo/code/MCP_CB_refactor/.venv/bin/python \
  /Users/dncampo/code/MCP_CB_refactor/evaluation/smart_farming/evaluate_codex.py
```

This starts a new native Codex session with the same per invocation connection settings. It first requires successful native connectivity, then asks the model to perform Tests 1 through 5 using only MCP responses. It does not pass previous answers, fixtures or entity values. The sole expected dataset count supplied is 47 Animals, explicitly requested by the user; the model is required to verify it through pagination. The model chooses its own filter and relationship paths from observed data.

The CLI uses its normal account authentication. No model provider credentials, global configuration changes or sandbox bypass are needed in this command. It retains the read only sandbox and disables shell and web tools. If the regular environment also denies startup or broker access, retain the actual error and stop; do not weaken policy to force a pass.

Progress prints every 15 seconds, with a five minute limit. Results are saved to codex-evaluation.jsonl, codex-evaluation.stderr.txt and codex-evaluation.execution.json in the same local evidence directory. Existing files are not overwritten. Successful process exit is UNREVIEWED until actual mcp_tool_call events, results and final answers are examined. A new session alone does not establish success.

The execution has now been reviewed: native tool arguments, responses, complete IDs, values and errors support the final classifications above. No Phase B query was answered from source code or previous reports. Oracle comparison with previously captured broker data occurred separately after model execution. A future repeat should preserve these files and choose a new --label, then be reviewed in the same way.

## Historical comparison before the terminal run

Claude Code previously completed a real native session with 19 MCP calls, correctly filtering, following relationships, reporting a missing target and paginating 47 Animals. Its evaluation recorded four PASS cases and one PARTIAL discovery explanation because of an unsupported general statement. Those findings belong to Claude's execution and do not count as Codex evidence.

At that stage Codex had zero native calls and no reasoning comparison was justified. The normal terminal run has since supplied and passed the native evaluation. The prior 273 automated assertions still establish server behavior only and were not substituted for those 14 native calls.

## Files and Git state

This report, evaluation/smart_farming/evaluate_codex.py and evaluation/smart_farming/codex-evaluation.txt were added under the writable original workspace /Users/dncampo/code/MCP_CB_refactor, which is not a Git checkout. Local evidence remains ignored. The separate permanent checkout /Users/dncampo/code/FIWARE-MCP-Server remains clean on refactor. No commits, branches, pushes or merges were created.

After the evaluation result has been reviewed, the following commands can preserve only the reviewed report in the existing refactor branch. Do not execute them before review. If the terminal evaluation succeeds later, update this report first so it records that evidence accurately.

```sh
git -C /Users/dncampo/code/FIWARE-MCP-Server status --short
git -C /Users/dncampo/code/FIWARE-MCP-Server switch refactor
cp /Users/dncampo/code/MCP_CB_refactor/docs/CODEX_SMART_FARMING_EVALUATION.md /Users/dncampo/code/FIWARE-MCP-Server/docs/CODEX_SMART_FARMING_EVALUATION.md
git -C /Users/dncampo/code/FIWARE-MCP-Server diff --no-index -- /dev/null docs/CODEX_SMART_FARMING_EVALUATION.md
git -C /Users/dncampo/code/FIWARE-MCP-Server add -- docs/CODEX_SMART_FARMING_EVALUATION.md
git -C /Users/dncampo/code/FIWARE-MCP-Server diff --cached -- docs/CODEX_SMART_FARMING_EVALUATION.md
git -C /Users/dncampo/code/FIWARE-MCP-Server commit --only -m "docs: record native Codex Smart Farming evaluation" -- docs/CODEX_SMART_FARMING_EVALUATION.md
git -C /Users/dncampo/code/FIWARE-MCP-Server status --short
```

The no-index diff exits with status 1 when it displays differences; that is normal. These are documentation-only commit instructions, not instructions to publish local traces, credentials or machine-specific configuration. They do not push, merge, rewrite history or modify main or master. Publishing the launcher and prompt, if desired, is a separate reviewed change.
