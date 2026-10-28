# Smart Farming dataset audit and deployment review

Audit date: 2026-10-28. Phase A is complete. The strategy below was reviewed and approved by the user. The subsequent execution attempt and exact continuation command are in [SMART_FARMING_VERIFICATION.md](SMART_FARMING_VERIFICATION.md). No Docker resources, upstream import scripts, services scripts or broker writes were executed during the audit itself. The MCP implementation and existing local MCP configuration were not changed.

Source: [Smart Farming repository at 05c6fdd](https://github.com/dncampo/fgs2025-talking-with-smart-solution/tree/05c6fdd118b731a5c362b0892c9efb00968dc7a4). Shell cloning failed because this session could not resolve github.com. The GitHub connector supplied a separate source export in `/private/tmp/fgs2025-smart-farming-audit`. All 15 files used by the offline audit match the pinned repository Git blob hashes. The export is not a Git checkout. No upstream files were edited.

Reviewed files include both import scripts, services, provisioning, linking, all three contexts, all four Compose files, MIME configuration and READMEs. The presentation PDF was not needed to establish loader behavior. No `.env` is tracked, so the original runtime image versions and configured counts cannot be recovered from this commit.

The permanent MCP checkout at `/Users/dncampo/code/FIWARE-MCP-Server` is on `refactor`, commit `1ecb4dc`, with a clean working tree at inspection. Evaluation artifacts are in the currently writable workspace, `/Users/dncampo/code/MCP_CB_refactor`. They have not been transferred to that checkout.

## Dataset inventory

Counts describe intended unique IDs if every operation is accepted. They are not live broker counts. The parser reads literal JSON without executing upstream scripts. Its generated record is [inventory.json](../evaluation/smart_farming/inventory.json), including every static ID, attribute kind, relationship target, context definition and provisioning profile.

| Entity type | Static unique IDs | Default generation, COW_COUNT=4 | Proposed generation, COW_COUNT=40 |
| --- | ---: | ---: | ---: |
| Animal | 17 | 17 | 47 |
| AgriParcel | 6 | 6 | 6 |
| Building | 4 | 4 | 4 |
| Person | 4 | 4 | 4 |
| Total | 31 | 31 | 61 |

The static Animal IDs comprise cows 001 through 010, calves 101 through 103 and pigs 001 through 004. Dynamic generation precedes static import and generates only cows 001 through a configured maximum of 100. Pig generation is commented out. For 40 generated cows, the intended Animal population is 43 cattle and four pigs. For a positive generation count n from 1 through 100, the intended total is `max(10,n)+21`. Zero would expose the original generator's unconditional trailing comma removal on an empty array; the proposed profile uses 40.

The source README advertises 40 cows, 40 pigs, three fields, four buildings and five people. The scripts do not implement those counts. PIG_COUNT does not activate the commented generation block.

Static import has four batches, with 20, 5, 3 and 8 operations, respectively. There are 36 operations affecting 31 IDs. Cows 001 and 006 and parcels 001 through 003 occur twice. The first three batches use upsert with `options=update`; the last uses default replacement. Order matters. Flattening these operations into an unordered create list would change the intended result.

### Attributes in direct imports

| Type | Properties | VocabProperties | Relationships | GeoProperties |
| --- | --- | --- | --- | --- |
| Animal | species, name, fedWith, legalId, comment, weight; generated cows also heartRate, birthdate | sex, phenologicalCondition, reproductiveCondition, healthCondition | locatedAt, ownedBy, calvedBy, siredBy | location on generated cows |
| AgriParcel | name; temperature on 001 through 003 | cropStatus | cropType | none |
| Building | name, address | category | owner | location |
| Person | name, givenName, gender, jobTitle, weight | none | owns | none |

Not every attribute occurs on every entity. Six intended relationship attributes lack their required type, detailed below. Address and jobTitle contain structured object values; address also has a nested verified Property. Parent relationships occur on calves. Static Person weights are numeric 270, 230 and 250; calf weights are 50, 30 and 20. Dynamic weights and heart rates are generated. Parcel temperatures are all 10.4 CEL. These are observed structures, not validated Smart Data Model schemas.

### Devices and runtime generation

Direct imports create no Device, TemperatureSensor, FillingLevelSensor, Water, Tractor, SoilSensor or AgriCrop entities.

`provision-devices` defines seven IoT service groups: TemperatureSensor, SoilSensor, FillingLevelSensor, two Device groups, Water and Tractor. It provisions four TemperatureSensor, four FillingLevelSensor, four Water and four Tractor records. SoilSensor has a service group but no device instances. `link-devices` provisions 100 cow collars and 100 pig collars, all type Device, independently of generation counts. Total provisioning records: 216. Provisioning records are not proof that 216 NGSI-LD entities exist or have received observations.

The IoT attribute definitions are:

| Type | Measurements or status | Commands | Other structures |
| --- | --- | --- | --- |
| TemperatureSensor | temperature Integer, CEL | none | description, category, controlledProperty, supportedProtocol |
| SoilSensor | humidity Integer, P1 | none | description, category, controlledProperty, supportedProtocol |
| FillingLevelSensor | filling Number, C62 | add, remove | description, category, controlledProperty, supportedProtocol |
| Device | heartRate Integer, 5K; status Integer; statusDescription; location geo:point | none | description, category, controlledProperty, supportedProtocol; pig group also function |
| Water | none declared | on, off | description, category, supportedProtocol |
| Tractor | status Integer; statusDescription; location geo:point | start, stop | description, category, controlledProperty, supportedProtocol |

Device profiles add location and controlledAsset relationships to buildings or animals. Collar provisioning requests a reverse providedBy link for heartRate and location. That is an IoT Agent instruction, not a relationship already present in direct imports. Exact provisioning attributes and targets are retained in inventory.json. IoT Agent formats must not be posted directly as normalized NGSI-LD entities.

The dynamic import creates a randomized initial snapshot, not a running simulation. It uses shell RANDOM for location, owner, parcel, birthdate, heart rate and weight. The fifth cow has heartRate 70; other generated rates are 50 through 56. Generated males occur at zero based indices divisible by 20. Static overlays replace selected generated attributes. Historical observedAt values remain in 2024.

## Contexts and relationship semantics

The primary context is `http://context/user-context.jsonld`, with 153 definitions. It maps Animal and AgriParcel to the Agrifood namespace, Building to the Building namespace, Device to the Device namespace and Person to schema.org. The source MIME configuration serves `.jsonld` as `application/ld+json`.

Relevant mappings include heartRate to `https://purl.bioontology.org/ontology/MESH/D006339`, location and weight to SAREF IRIs, and cropType to `agrifood:hasAgriCrop`. Query requests must use the same context as imports. A missing context can make compact terms refer to different attributes and produce empty results.

`calvedBy`, `siredBy` and `owns` have no explicit mapping in the supplied user context. Several VocabProperty values also lack explicit definitions, including maleAdult, femaleAdult, active, inHeat, inCalf, inTreatment, healthy, grazingBaby, lactatingBaby, noStatus, seeded, growing and maturing. Their expansion depends on the effective default vocabulary. Capture the broker's expanded attributes and values during verification; do not silently supply new vocabulary definitions.

`ngsi-context.jsonld` combines the user context with the ETSI core v1.8 context. It introduces an external ETSI context dependency if used directly. The original imports select the user context through Link. The isolated baseline will do the same, without changing context definitions.

`alternate-context.jsonld` has 135 definitions. It is not merely a translated alias file: Animal and Person terms use different namespaces from the primary context. It must not substitute for the primary context during baseline import or querying.

Explicit intended relationship paths include Animal to AgriParcel or Building through locatedAt, Animal to Person through ownedBy, calf to parent Animal through calvedBy and siredBy, AgriParcel to AgriCrop through cropType, Building to Person through owner and Person to Building through owns. Devices introduce controlledAsset only through IoT provisioning. Do not infer inverse relationships where none are stored.

## Data quality and operational defects

1. In static batch two, locatedAt and ownedBy each omit `type: Relationship` on cow102, cow103 and cow006. The audit initially flagged these six attributes under an assumed normalized input requirement. Live Orion 1.12 testing in mongocOnly mode accepted them and returned normalized Relationships without a source repair. Exact original values remain in inventory.json. Acceptance by other broker implementations remains untested.
2. Those three ownedBy targets use `urn:ngsi-ld:Person:001`. The imported ID is `urn:ngsi-ld:Person:person001`. The target is missing. Adding a Relationship type alone would not repair this dangling target.
3. Six parcel cropType edges target three absent entities: `urn:ngsi-ld:AgriCrop:BuckWheat`, `urn:ngsi-ld:AgriCrop:Corn` and `urn:ngsi-ld:AgriCrop:Grass`.
4. Dynamic field selection can produce AgriParcel:007 at the upper endpoint of RANDOM, but only parcels 001 through 006 are imported. The birthdate formatting can produce month 010 when the generated month reaches 10. Record these possibilities and inspect the selected deterministic output.
5. The later cow006 update changes healthCondition to healthy while an earlier comment says it needs a vet. The later cow001 comment has an older observedAt than its earlier comment. Preserve and report source order and inconsistent evidence.
6. Pig002 is Female but has an M-sow legalId prefix. Preserve that source discrepancy. For numeric values, report the actual returned unitCode: the recorded Person:person002 response specifies KGM. The earlier audit's statement that Person weights had no documented unit was incorrect. Do not infer units that are absent from a response.
7. At the proposed 40 cow profile, 60 cow collar targets and 96 pig collar targets are absent. These are 156 potential missing targets if all collar provisioning is included. The minimal baseline excludes provisioning and therefore does not claim Device coverage.
8. The csource registration has an unterminated quoted media type in its Link header and targets `http://devices`. Its inclusive Animal federation behavior depends on the forwarder. Do not register a missing forwarder in the isolated snapshot.
9. Import curl commands discard response bodies and do not fail on HTTP errors. Upsert can report partial success through 207; treating that as a successful load would conceal missing entities. Orion documents per entity batch failures and update versus replacement semantics in its [developer manual](https://github.com/FIWARE/context.Orion-LD/blob/develop/doc/manuals-ld/developer-documentation.md#post-ngsi-ldv1entityoperationsupsert).
10. The shell scripts declare Bash but services launches them through `/bin/ash`. Dynamic generation uses Bash constructs and negative substring offsets. This host has Bash 3.2.57, so it is unsuitable as the reproducible generator runtime without further qualification. No original script was executed.

## Dependency and Orion compatibility analysis

Do not execute upstream services start or stop. The stoppingContainers function enumerates all host containers with `docker ps -aq`, removes them with `docker rm -f`, then removes every dangling Docker volume. Broker selection calls this function before Compose startup. This cleanup is not limited to the tutorial project.

The original Compose stack also uses fixed container names, the shared fiware_default network, public database ports, unpinned tutorial images, Neo4j host directories and configuration from an absent `.env`. Reuse would risk conflicts with the current broker.

MongoDB configuration mounts `/data` rather than the default `/data/db`, runs `--nojournal`, and uses a mongosh healthcheck. The shell is not compatible with the previously verified Mongo 4.4 image; `--nojournal` also prevents blindly selecting newer Mongo releases. Use the known Phase 2 pair Orion-LD 1.12.0 and MongoDB 4.4.29 instead, with a mongo healthcheck and correct volume path. On Apple Silicon use linux/amd64 for both, consistent with the verified deployment.

Orion 1.12 supports VocabProperty; Orion's [release notes](https://github.com/FIWARE/context.Orion-LD/releases) document support and related fixes predating 1.12. Actual testing established that the default legacy batch upsert path rejects this type. The isolated Compose now preserves the original stack's -mongocOnly flag, selecting the newer implementation. The initial audit incorrectly omitted this required setting. Forwarding and entityMaps remain omitted because this local snapshot does not use those features. Untyped attributes, custom location expansion, VocabProperty filtering and compound Property values still require live verification.

IoT Agent, simulators and forwarder are required for the original device and federated behavior, not the direct imports. Neo4j and the tutorial application are unnecessary for a broker snapshot. Scorpio and Stellio stacks add their own dependencies and are outside this test. IoT calls use openiot service or tenant settings, whereas direct imports do not send a tenant. The initial MCP must query the default tenant; adding openiot would hide the directly imported data.

## Isolated strategy proposed for review

The reviewed configuration is [compose.review.yaml](../evaluation/smart_farming/compose.review.yaml). It has now been executed successfully in the user's terminal. Final evidence is in SMART_FARMING_VERIFICATION.md.

| Resource | Proposed setting |
| --- | --- |
| Compose project | fiware-farm-audit |
| Broker | fiware/orion-ld:1.12.0, linux/amd64 |
| Database | mongo:4.4.29, linux/amd64, no published port |
| Database volume | project scoped farm-data, mounted at /data/db |
| Context server | python:3.12.8-slim, internal service context on port 80 |
| Context content | original src/data-models mounted read only, explicit JSON-LD media type |
| Broker listener | 127.0.0.1:1126, subject to a port availability check |
| Dataset profile | COW_COUNT=40, original four static batches, intended 61 entities |
| Initial MCP policy | read only, primary context, default tenant |

No shared networks, fixed container names, existing Mongo volumes or existing Compose projects are referenced. The original broker on port 1026 stays untouched. The source checkout stays unchanged. Image digests and actual running versions will be recorded during live verification; tags alone do not provide immutable image identity.

The approved loader is now implemented in evaluation/smart_farming/run.py. Its live execution is blocked by this session's Docker socket permissions, as recorded in SMART_FARMING_VERIFICATION.md. Its behavior follows this reviewed contract:

1. Pin the source commit and verify payload hashes. Extract the four static JSON arguments, including the final --data-raw argument. Reject duplicate JSON keys or unexpected source layout.
2. Capture the original dynamic generator's output under a pinned Bash runtime with a fixed RANDOM seed, without network access. A capture wrapper must intercept curl and accept only the expected entity upsert and registration calls. Discard the registration as an explicitly excluded dependency, not as a hidden data repair. No upstream services script is involved.
3. Generate twice and compare output hashes. Freeze generated payloads and the effective seed, runtime, image identity and source commit in a manifest. Validate the resulting JSON and report date and relationship anomalies before any insertion. Bash seeding alone across different Bash versions is insufficient reproducibility.
4. Default to exact source replay and stop on any broker rejection, recording full operation and per entity errors. Do not silently skip malformed entities or count a 207 response as success. If exact replay fails, request a separate explicit decision about a derived copy adding only the six missing Relationship types. Keep the wrong Person ID and all other anomalies visible unless separately authorized. No original files are edited.
5. Require an empty dedicated broker before first load. Import dynamic entities then the four static batches in source order, preserving update and replacement modes. Verify every expected ID and intended final attribute values after writes, not just aggregate counts.
6. On a repeated run, verify the saved manifest against stored IDs and content without writing when it matches. Stop on any mismatch or unexpected entity. Do not regenerate random values and silently upsert them. Store manifests outside the source checkout.

This first profile evaluates directly imported entities. It cannot validate Device relationships because those require the excluded IoT Agent flow. No Device entities will be invented as replacements. If Device coverage is required immediately, review that as a separate provisioning profile with pinned dependencies and explicit tenant checks.

## Reproduction commands and review boundary

The following source clone and offline audit commands are safe to run before deployment approval from a regular terminal. Use a fresh destination if the source directory already exists.

```sh
git clone https://github.com/dncampo/fgs2025-talking-with-smart-solution.git /Users/dncampo/code/fgs2025-smart-farming-source
git -C /Users/dncampo/code/fgs2025-smart-farming-source checkout --detach 05c6fdd118b731a5c362b0892c9efb00968dc7a4
export FARM_SOURCE_DIR=/Users/dncampo/code/fgs2025-smart-farming-source
export FARM_EVAL_DIR=/Users/dncampo/code/MCP_CB_refactor/evaluation/smart_farming
python3 "$FARM_EVAL_DIR/audit.py" "$FARM_SOURCE_DIR" > /tmp/smart-farming-inventory.json
```

The following deployment commands are for after strategy review only. They were not executed. A successful Compose start is not broker readiness.

```sh
lsof -nP -iTCP:1126 -sTCP:LISTEN
docker compose -p fiware-farm-audit -f "$FARM_EVAL_DIR/compose.review.yaml" config
docker compose -p fiware-farm-audit -f "$FARM_EVAL_DIR/compose.review.yaml" up -d
docker compose -p fiware-farm-audit -f "$FARM_EVAL_DIR/compose.review.yaml" ps
docker compose -p fiware-farm-audit -f "$FARM_EVAL_DIR/compose.review.yaml" exec -T context python -c 'import urllib.request; r=urllib.request.urlopen("http://context/user-context.jsonld", timeout=5); print(r.status, r.headers.get("Content-Type")); print(r.read().decode())'
curl --fail-with-body --max-time 10 http://127.0.0.1:1126/version
curl --fail-with-body --max-time 10 'http://127.0.0.1:1126/ngsi-ld/v1/entities?idPattern=.*&limit=1'
```

If lsof reports a listener, stop before up; the runner also checks port availability and refuses a conflict. A nonzero lsof exit with no output normally means there is no listener. Wait for the broker to answer both probes; inspect only this project's logs if it fails. The complete load command and automated live assertions are now supplied by run.py; see SMART_FARMING_VERIFICATION.md for the exact command to execute from the regular terminal.

Cleanup after evaluation, when requested, is scoped to this project. The following stops its services and retains its data volume; no volume removal or host prune is proposed:

```sh
docker compose -p fiware-farm-audit -f "$FARM_EVAL_DIR/compose.review.yaml" down
```

## Claude Code connection after loading

The separate [claude.mcp.example.json](../evaluation/smart_farming/claude.mcp.example.json) uses the existing seven tool STDIO server and disables writes. It does not overwrite or merge the existing .mcp.json. The broker resolves the internal context URL; the host MCP process only sends it in Link. There is no new public MCP listener. A working local file using this workspace's verified Python interpreter is now prepared; use the exact Claude command in SMART_FARMING_VERIFICATION.md. The generic template below assumes a virtual environment exists inside FIWARE_MCP_ROOT.

For predictable executable paths, materialize a separate local file rather than depending on client interpolation. Run after the dataset is loaded and verified:

```sh
export FIWARE_MCP_ROOT=/Users/dncampo/code/FIWARE-MCP-Server
python3 - <<'PY'
import json, os
from pathlib import Path
template = Path(os.environ['FARM_EVAL_DIR']) / 'claude.mcp.example.json'
text = template.read_text().replace('${FIWARE_MCP_ROOT}', os.environ['FIWARE_MCP_ROOT'])
destination = Path('/tmp/fiware-smart-farming.mcp.json')
destination.write_text(json.dumps(json.loads(text), indent=2) + '\n')
destination.chmod(0o600)
print(destination)
PY
claude --strict-mcp-config --mcp-config /tmp/fiware-smart-farming.mcp.json
```

Check `/mcp`, discover all seven tool descriptions and schemas, then invoke get_broker_info. `--strict-mcp-config` limits this invocation to the supplied MCP configuration; the existing configuration remains available in normal sessions. These flags follow the [Claude Code MCP documentation](https://code.claude.com/docs/en/mcp). The native Claude Code connection and five natural language cases are now evaluated in CLAUDE_SMART_FARMING_EVALUATION.md.

## Verification plan and results

| Check | Status | Evidence or remaining work |
| --- | --- | --- |
| Pinned source inspection and file identity | PASS | 15 audit input files match upstream Git blob hashes |
| Static JSON parsing, unique IDs and counts | PASS | Four batches, 36 operations, 31 IDs; duplicate JSON keys rejected |
| Attribute and relationship inventory | PASS | Source inspection; six missing type fields and absent targets recorded |
| MCP environment settings | PASS | Parsed with the existing Config class; writes false, broker 1126, primary context |
| Draft YAML and isolation assertions | PASS | PyYAML parse; only three services, Mongo unpublished, broker bound to loopback |
| Deterministic dynamic output | PASS | Two equal generated payloads, seed 1729, Bash 5.2.15 |
| Compose syntax and image execution | PASS | Dedicated project executed; Orion 1.12 requires mongocOnly for source VocabProperty |
| Broker connectivity and context expansion | PASS | Version and entity readiness; original context served and used |
| Loaded counts and entity content | PASS | 61 IDs and source contents verified; singleton VocabProperty compaction allowed |
| Numeric and categorical filters | PASS | Direct and MCP results matched actual values and expected IDs |
| Relationship traversal and missing targets | PASS | 102 edges checked, 93 targets resolved, nine expected 404 responses |
| Pagination | PASS | Animal pages of 20, 20 and 7; no missing or duplicate IDs |
| Independent SDK MCP STDIO invocation | PASS | Seven tools discovered and invoked; write calls blocked by read only mode |
| Claude Code native MCP invocation | PASS | Seven tools available; 19 native read calls, including one expected missing target response |

After loading, compare paginated IDs and content with the frozen manifest. Require exactly four direct entity types, count each type independently, inspect representative attributes including all calves, verify relationship target existence, and compare direct HTTP with MCP responses using the same context. Record a 404 for every missing target instead of inventing a relationship. Exact source rejection is a dataset compatibility result, not an MCP defect.

For the proposed accepted 40 cow profile, categorical `species=="pig"` should yield the four pig IDs, and `species=="dairy cattle"` should yield 43 cattle. Numeric `heartRate>56` should yield only cow005 with value 70: the generator forces that value and static import does not replace it. Test weight thresholds against the frozen actual values. `temperature>10` on AgriParcel should return 001 through 003 with value 10.4. Compare projection with attrs supplied as a JSON array and use page sizes of 20 for Animal without assuming any order. Detect duplicate and missing IDs across pages on the quiescent broker.

Suggested natural language regression requests:

1. Explore the farm broker. List stored entity types and counts, distinguishing observed attributes from a formal schema.
2. Find cattle whose heart rate exceeds 56. Show each actual value, unit and query filter.
3. List all pigs and their legal identifiers. Report any disagreement between sex and the identifier text.
4. For each calf, follow the recorded mother and father IDs. Do not infer parents for other animals.
5. Follow each animal's locatedAt and ownedBy relationships. Report unresolved targets explicitly.
6. Show parcels with temperature above 10 and identify which parcels lack a temperature observation.
7. Follow building owner and Person owns relationships. Explain which directions are explicitly stored.
8. Retrieve every Animal using bounded pages and show that no ID was duplicated or omitted.
9. Look for animal Device relationships. Distinguish an absent Device dataset from a failed query.
10. Inspect cow006's healthCondition and comment. Describe the inconsistency without choosing which statement is true.

The combined available pytest suite now reports 72 passed, one skipped for sandbox socket binding and 20 existing integration cases deselected. The separate live Smart Farming evaluation reports 273 passing assertions. The prior 77 Building/Room/Sensor tests remain historical baseline evidence. Docker and local networking execution used the regular macOS terminal because this Codex session cannot access Docker. Native Claude Code evaluation is also complete, with four cases PASS and discovery PARTIAL for an unsupported general statement. Its evidence is separate from the independent SDK client result.

All evaluation files and fixes are listed in SMART_FARMING_VERIFICATION.md. No MCP implementation changes, commits, branches, pushes or merges were created.
