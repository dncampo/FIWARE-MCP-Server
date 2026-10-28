# Claude Code functional evaluation

Status: completed through the actual Claude Code MCP integration. Four cases PASS and one is PARTIAL because of an unsupported general statement in the explanation. Dataset discovery, both filters, relationship navigation and pagination were functionally correct. The separate automated broker integration also passed 273 assertions; it is distinct from this model evaluation.

Client: Claude Code 2.1.220. Model reported by the native client: claude-sonnet-5. Elapsed time reported by that client: 88.832 seconds. The process exited successfully with no permission denials. Its init event lists exactly seven tools, all belonging to fiware-smart-farming, and reports that MCP server connected. There were no built in tools, source file reads, direct HTTP tools or other MCP providers available in the session.

## Connectivity and evidence

Server startup and MCP protocol connectivity are demonstrated by the connected MCP status and seven available tool definitions. Broker connectivity and successful invocation are independently demonstrated by get_broker_info returning ok=true, HTTP 200, Orion-LD 1.12.0 and writes_enabled=false, followed by successful live discovery and query results.

Reviewed all 19 native MCP calls and their responses: 18 returned ok=true with HTTP 200; one get_entity returned the expected ok=false HTTP 404 for Person:001. That 404 was correctly interpreted and reported. No invalid query, unexpected broker error, model retry, permission rejection or write attempt occurred. No fabricated entity type, attribute, entity ID or relationship was found in the answers.

The review compared returned entity fields with the frozen stored.json evidence from the real broker, checked counts against discovery metadata, and verified every Animal ID across all three pages. The native trace is claude-evaluation.jsonl; a concise call record with arguments, status, pagination and returned IDs is claude-evaluation.calls.json in the same ignored local-evidence directory. The client's stderr file is empty.

## Results

| Case | Classification | Observed outcome |
| --- | --- | --- |
| A: solution discovery | PARTIAL | Correctly discovered Animal 47, Person 4, AgriParcel 6 and Building 4, with observed attributes and one sample per type. Correctly distinguished observations from a validated schema. Added an unsupported claim about universal absence of a schema registry; see qualification below. |
| B: numeric filter | PASS | Chose q=heartRate>56 with compact terms and the deployment context. Returned cow005, name Sun, value 70 and stored unitCode 5K. No .value suffix or full IRI was incorrectly inserted into the predicate. |
| C: categorical filter | PASS | Observed species values before constructing q=species=="pig". Returned the four actual pig IDs and names. The three discovery pages were reused for case E. |
| D: relationship navigation | PASS | Chose q=weight<100. Retrieved cow101, cow102 and cow103 with weights 50, 30 and 20 KGM. Followed seven unique target IDs, resolved six and reported Person:001 as absent. Did not substitute Person:person001 or invent location and owner fields on cow101. |
| E: pagination | PASS | Requested Animal with attrs=["species"], limit 20 and offsets 0, 20 and 40. Observed pages of 20, 20 and 7, total 47, and stopped on has_more=false with next_offset=null. The 47 distinct returned IDs exactly match all stored Animal IDs. |

The discovery classification is conservative about the answer's grounding, not a functional discovery failure. The statement that no formal schema registry exists in NGSI-LD/Orion-LD was not established by the tools. The supported statement is that these tools return observed metadata and do not establish whether any deployment schema validation or registry is available. The answer also placed complete_schema=false under type_metadata in prose, while the actual flag is data.complete_schema. Counts were genuinely present in each get_attributes response; the absence of counts from the get_types detail objects was not a data fabrication.

## Concise reproducible call trace

All names below omit the constant native prefix mcp__fiware-smart-farming__. C means the explicit context_url http://context/user-context.jsonld. Only query calls supplied that parameter explicitly; the other requests used the same configured default context. No query arguments were supplied to the model by the launcher.

| Call | Tool | Exact arguments | Result |
| --- | --- | --- | --- |
| 1 | get_broker_info | {} | 200, connected, writes false |
| 2 | get_types | limit=100, offset=0 | Four types, complete page |
| 3 | get_attributes | entity_type=Animal, sample_limit=1 | Metadata and cow001 sample |
| 4 | get_attributes | entity_type=Person, sample_limit=1 | Metadata and person001 sample |
| 5 | get_attributes | entity_type=AgriParcel, sample_limit=1 | Metadata and parcel 001 sample |
| 6 | get_attributes | entity_type=Building, sample_limit=1 | Metadata and barn002 sample |
| 7 | query_entities | type=Animal, q=heartRate>56, attrs=["name","heartRate","species"], limit=100, C | cow005 |
| 8 | query_entities | type=Animal, attrs=["species"], limit=20, offset=0, C | 20 IDs, next_offset=20 |
| 9 | query_entities | type=Animal, attrs=["species"], limit=20, offset=20, C | 20 IDs, next_offset=40 |
| 10 | query_entities | type=Animal, attrs=["species"], limit=20, offset=40, C | Seven IDs, complete |
| 11 | query_entities | type=Animal, q=species=="pig", attrs=["species","name"], limit=20, C | pig001 through pig004 |
| 12 | query_entities | type=Animal, q=weight<100, attrs=["name","weight","ownedBy","locatedAt","calvedBy","siredBy","species"], limit=20, C | cow101, cow102, cow103 |
| 13 | get_entity | entity_id=urn:ngsi-ld:Animal:cow001, attrs=["name","species"] | Beany, dairy cattle |
| 14 | get_entity | entity_id=urn:ngsi-ld:Animal:cow002, attrs=["name","species"] | Trotter, dairy cattle |
| 15 | get_entity | entity_id=urn:ngsi-ld:Animal:cow004, attrs=["name","species"] | River, dairy cattle |
| 16 | get_entity | entity_id=urn:ngsi-ld:Animal:cow006, attrs=["name","species"] | Twilight, dairy cattle |
| 17 | get_entity | entity_id=urn:ngsi-ld:AgriParcel:005 | Water Meadow |
| 18 | get_entity | entity_id=urn:ngsi-ld:Building:barn002 | Big Red Barn |
| 19 | get_entity | entity_id=urn:ngsi-ld:Person:001 | 404, unresolved original target |

Case A used calls 1 through 6. B used call 7. C used calls 8 through 11, while E reused calls 8 through 10. D used calls 12 through 19. Inputs, actual results and unsuccessful resolution are preserved in the native client events, not reconstructed from predefined Python queries.

## Reliability, efficiency and recommendations

No new MCP implementation defect was observed in this populated broker evaluation. The earlier empty broker discovery issue in Orion remains documented separately in SMART_FARMING_VERIFICATION.md. Only one model, dataset snapshot and successful session were evaluated; this is evidence of functional usability, not a statistical reliability estimate or validation of arbitrary deployments.

The model used JSON arrays for attrs, the correct JSON-LD context, standard NGSI-LD query strings and exact relationship URNs. It kept failed target resolution distinct from a successful empty query and used returned pagination rather than assuming a collection size. Its only unsuccessful call was the expected missing Person target; no unexpected failure required recovery, so recovery from network failures or invalid generated queries remains untested in this session.

Two get_entity calls were avoidable: cow001 and barn002 were already present in the initial attribute samples. Shared parent and ownership IDs were otherwise deduplicated, and the three species discovery pages also satisfied the required complete ID listing. Thus fetching all Animal IDs served an explicit task requirement and did not download their full attribute sets.

Prioritized improvements are evaluation or response guidance, without changing MCP tools:

1. Require precise capability language: observed metadata is not proof that a deployment lacks a schema registry. Refer to the actual response field path for complete_schema.
2. Reuse entities returned inside get_attributes samples when resolving later relationships, rather than fetching them again.
3. When asked for every complete ID, print each full URN or explicitly label range notation as a summary. The model's abbreviated ID ranges matched the actual 47 IDs, which remain fully listed in the trace.

No tool definition, server implementation, dataset or write configuration was changed for this review. No further execution is required to complete this evaluation record; a future rerun would measure consistency or improved response guidance, rather than establish missing core functionality.

The later native Codex evaluation is complete in CODEX_SMART_FARMING_EVALUATION.md: 14 MCP calls and five PASS cases, with one projection mistake corrected before the final answer. It used a different filter and fewer target lookups, so the call totals are not a controlled efficiency comparison. Both evaluations establish native client functionality on the existing populated broker.

## Reproduction procedure used

Run the native Claude Code client from the regular macOS terminal with:

```sh
/Users/dncampo/code/MCP_CB_refactor/.venv/bin/python /Users/dncampo/code/MCP_CB_refactor/evaluation/smart_farming/evaluate_claude.py
```

The evaluation launcher invokes the installed claude CLI, not a Python MCP client. It uses the separate local MCP configuration already prepared for port 1126, requires writes to be disabled, disables built in tools and skills, and preapproves only the five MCP read tools. It starts in an empty temporary directory and supplies natural language requests through stdin. It does not read the dataset or construct NGSI-LD query parameters for the model. The normal Claude Code account supplies authentication; no provider credentials are added or printed.

The installed CLI help was inspected to verify the flags. The invocation uses print mode, verbose stream JSON, strict MCP configuration, an explicit read tool allowlist and no session persistence. Tool search was disabled for this process so the seven MCP definitions were available directly. The native init event and recorded calls verify that this configuration worked in the executed session.

Progress prints every 15 seconds. There is a five minute limit; reaching it means incomplete evaluation, not a server failure. A repeat run refuses to overwrite existing Claude evidence. Other broker services and Docker resources are not restarted or changed.

| Case | Natural language objective | Current status |
| --- | --- | --- |
| A | Discover actual types and observed attributes; describe the solution without inventing a schema | PARTIAL |
| B | Construct a numeric query for animal heart rate above 56 and explain actual measurements | PASS |
| C | Construct a categorical query identifying pigs from stored species values | PASS |
| D | Find animals weighing less than 100 and follow explicit parent, location and ownership relationships, including missing targets | PASS |
| E | Retrieve all Animal IDs through pages of at most 20 with projection and accurate stopping and duplicate checks | PASS |

The exact natural language request is evaluation/smart_farming/claude-evaluation.txt. It does not supply expected counts or entity IDs. The launcher does not tell the model which query arguments to choose.

Native client events, answers, tool names, arguments and returned data are saved in the ignored local-evidence/claude-evaluation.jsonl. Diagnostic output is saved in local-evidence/claude-evaluation.stderr.txt. These local files have mode 0600. Successful process exit alone will not establish PASS: the recorded calls and grounded answers must be reviewed against final-direct.jsonl, final-mcp.jsonl and stored.json from the verified integration run.

The final review above records classifications, actual tool arguments, success or failure, query validity, unsupported claims, unnecessary calls and error handling. It separates broker and MCP behavior from model reporting errors. The source's absent Person:001 was reported correctly. Resolution of missing AgriCrop targets was verified in the separate automated evaluation, not in this native model session.

The MCP server implementation, tool definitions and existing Building/Room/Sensor configuration remain unchanged. Actual write operations are outside this read only evaluation. No commits or pushes are authorized by this workflow.
