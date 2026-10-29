# Smart Farming evaluation research

Reviewed on 2026-10-29. This is an offline study and reference pack, not a new
live MCP evaluation. The MCP implementation, broker data, Docker resources and
canonical Git checkout were not modified. CSV dataset ingestion remains deferred.

## Main finding

The linked tutorial is useful as a question catalogue, but its answers cannot be
used as the expected answers for our existing fixture. It describes a richer,
different environment and includes later writes that change its baseline.

The current checkout already contains the reproducible `tests/farm/` harness.
Reimplementing that loader is unnecessary. The next useful addition is an
independent reference answer set and a repeatable natural-language evaluation.

## Sources inspected

* [Published transcript](https://fiware.github.io/tutorials.MCP-Server/farm_transcript.html).
  The published URL could not be retrieved through the browsing tool. Its HTML
  was successfully read through the GitHub connector from
  [the gh-pages source](https://github.com/FIWARE/tutorials.MCP-Server/blob/gh-pages/farm_transcript.html).
  Inspected Git blob: `38e904eaa8d497b91d2980ffc9433f60b985bcc2`.
* [Tutorial architecture and tool interface](https://github.com/FIWARE/tutorials.MCP-Server/blob/master/README.md).
* [Original tutorial loader](https://github.com/FIWARE/tutorials.MCP-Server/blob/master/import-data).
  Read only; no upstream script was executed.
* [Orion deployment](https://github.com/FIWARE/tutorials.MCP-Server/blob/master/docker-compose/orion-ld.yml)
  and [Mintaka deployment](https://github.com/FIWARE/tutorials.MCP-Server/blob/master/docker-compose/mintaka.yml).
* Tutorial `data/cow.csv`, `pig.csv`, `cow-history.csv` and
  `cow-history-young.csv`, plus the farm-status prompt.
* Current canonical checkout: `348dbf89f8db516f5fc782342733a7f78a5165f9`,
  branch `refactor`, clean at initial inspection. Reviewed the four existing
  Smart Farming audit/verification/native-client reports, `tests/farm/README.md`,
  `VALIDATION.md`, fixture files and relevant harness verification code.

The tutorial master branch can change. The specific transcript blob and CSV
blob hashes in `tutorial-source-record.json` identify inspected material. A future
adoption should pin a full upstream commit and verify all input file hashes.

## Dataset differences that affect correctness

| Aspect | Existing reference fixture | Linked tutorial |
| --- | --- | --- |
| Animals | 47: 43 cattle and four pigs | CSV identities contain 43 cattle and 30 pigs |
| Entity types | Animal, AgriParcel, Building, Person | Additional farm, soil, crop, weather and device data; later Pen and AnimalDisease writes |
| Beany | 838 KGM, locatedAt AgriParcel:003, North Pasture | Transcript initially reports different weight and location |
| North Pasture | Present as AgriParcel:003 | Transcript says it does not exist |
| Missing targets | Four distinct targets, nine edges | Additional tutorial source entities may resolve these differently |
| Weight history | Not supplied by our seven-tool interface | Separate CSV observations and a temporal query tool |
| Schema reference | Observed attributes; no formal model validation claim | Curated ontology resources and schema-related tools |
| Data stability | Fixed original batches and seed-captured fixture | Transcript changes breed, positions, weights, health and creates entities |

These differences are not evidence of an MCP defect. Evaluate each deployment
against its own versioned data, context, tenant and capabilities. Avoid loading
the tutorial on top of the current reference broker: overlapping identifiers
would change existing expected answers.

## What the temporal example actually uses

The tutorial's Orion Compose file enables TRoE and points it at a Timescale
database. Its MCP configuration routes temporal requests separately and selects
the `openiot` temporal tenant. The loader imports current farmer records into
`farmer`, measurements into `openiot`, and creates context source registrations.
The published example therefore depends on more than the static farm dataset.
Do not assume one tenant's current data and another tenant's history join
automatically in our minimal deployment.

The inspected source has:

| File | Observation rows | Distinct entity IDs |
| --- | ---: | ---: |
| cow.csv | 43 | 43 |
| pig.csv | 30 | 30 |
| cow-history.csv | 907 | 40 |
| cow-history-young.csv | 32 | 2 |

History rows are observations, not new entities. The importer supplies month or
week offset interpretation through headers. Absolute dates must be frozen before
using this as a reproducible temporal benchmark. The transcript discusses three
calves; the inspected young-history CSV supplies two IDs, so verify each animal's
actual observations rather than assuming all three have the same history.

For the deployed Orion-LD 1.12.0, the version-specific
[TRoE documentation](https://github.com/FIWARE/context.Orion-LD/blob/1.12.0/doc/manuals-ld/troe.md)
describes Postgres/PostGIS/Timescale storage and Mintaka queries, and labels that
functionality experimental. Current develop documentation describes additional
native temporal endpoints; that is not proof that the deployed 1.12.0 image
implements them. No broker change or temporal service deployment was tested here.
Our existing seven tools do not expose a temporal query interface.

## Evaluation design

1. Retain the existing pinned fixture and its JSON-LD context. Verify it before
   each scored run. No concurrent writers or simulators should change answers.
2. Derive expected answers offline from the source operations in original order:
   the first four batches update, and the last batch replaces. Generated and
   static IDs overlap; counting operation rows would be incorrect.
3. Keep reference entities and answers on the evaluator side. Give the evaluated
   client only `questions-only.json`, connection settings and native MCP tools.
   An evaluated client must not have file access to this directory or prior
   answers. Use a fresh working directory and conversation for independent cases.
4. Require actual native MCP traces. A notebook can calculate expected answers
   and compare output; Python API calls do not count as an LLM choosing tools.
5. Score exact ID sets, values, units, relationship target retrieval and complete
   pagination. Do not score wording similarity. Broker sorting order is not fixed.
6. Separate invalid questions, empty successful results, missing entities and
   unsupported capabilities. Expected 404s or an honest inability to answer can
   be correct outcomes.
7. Record framework errors, broker status, retries, corrected arguments,
   unnecessary calls and unsupported assertions. A corrected answer can pass
   correctness while still recording a first-attempt argument error.
8. Repeat a fixed question set across clients with the same starting data and
   context. Historical Claude/Codex runs demonstrate functionality but used
   different workloads, so their tool-call totals are not an efficiency ranking.

At initial research time all 16 cases were NOT_RUN. Subsequent dated native
Claude and Codex evaluations are recorded separately under experiments/; see
[the reviewed comparison](../../experiments/smart-farming/2026-10-29-COMPARISON.md).

## Prepared offline reference pack

* `questions-only.json`: 16 English questions, with IDs and no answers.
* `reference-answers.json`: exact expected results, suggested tools, example
  arguments for filters and limits, and constraints against unsupported claims.
* `reference-entities.json`: all 61 final source entities, retaining original
  metadata and any omitted relationship type declarations.
* `reference-relationships.json`: all 102 edges with fixture target availability.
* `reference-attributes.csv`: long-form inspection table. Compound values,
  coordinates, vocabularies and relationship objects remain JSON cells rather
  than losing structure in a flat export. A blank declared type remains blank.
* `build_reference.py`: standard-library-only generator, no HTTP or broker writes.

| Cases | Coverage | Expected result |
| --- | --- | --- |
| F01-F02 | Discovery and observed attribute types | Four types, 61 entities; observations are not a complete formal schema |
| F03 | heartRate greater than 56 | Sun, cow005, 70 with stored unit 5K |
| F04 | weight greater than 500 | cow001 838 KGM and cow021 699 KGM |
| F05-F06 | Species equality | Four pigs and 43 dairy cattle |
| F07 | Parcel temperature greater than 10 | Parcels 001, 002 and 003, each 10.4 CEL |
| F08 | Empty valid filter | No heartRate greater than 1000 in the fixture |
| F09-F10 | Ownership, location and parent traversal | Retrieve exact targets; Bumble has no stored locatedAt |
| F11-F12 | Dangling references | Person:001 remains absent; four distinct missing targets over nine edges |
| F13 | Parcel existence and missing area/boundary | North Pasture exists; area and fence crossing cannot be established |
| F14 | Missing breed and ambiguous clinical note | No observed breed; preserve Twilight's healthy label and vet note without diagnosis |
| F15 | Complete pagination | 47 unique Animal IDs; 20, 20 and seven when page size is 20 |
| F16 | Unsupported temporal request | Explain lack of temporal tool; do not invent a history from observedAt |

The bank is a starting point. User-authored variants can be added with expected
answers calculated before evaluation and hidden from the client.

## Cautions about the demonstration transcript

The transcript is a conversational demonstration, not an independently checked
answer key. It contains interpretive statements about animal health, breed,
stocking and likely field dimensions. Such statements require additional evidence
or domain references and must not become factual expected outputs merely because
they appear in a demonstration. A parent relationship and a vet note do not
establish a current diagnosis; absent recorded facilities do not prove absent
physical facilities. GPS fixes without parcel boundaries do not establish fence
crossing or actual parcel area.

The transcript contains subsequent writes and deletions. Our first evaluation
should remain read only. Write evaluation, if requested later, needs explicit
approval, dedicated entities and independently checked read-after-write results.
No Smart Data Models integration, new tools or query rewriting is needed for
these current-state questions.

## Checks executed in this investigation

```sh
# Canonical repository, read only inspection:
git status --short --branch
git log -1 --format='%H %s'
tests/farm/test_farm.sh --prepare-only

# Offline reference generator in permitted scratch space:
.venv/bin/python evaluation/farm-reference/build_reference.py
```

Fixture preparation PASS: exact pinned provenance, 61 entities and expected type
counts, no network. Reference generation checks: five batch sizes, all counts,
102 relationships, nine missing edges and 16 generated questions. The historical
farm validation report records 57 farm tests, 114 total non-integration tests
and prior live verification; those were not rerun or relabelled as new results.

To verify the existing farm broker manually from an authorized terminal:

```sh
cd tests/farm
./test_farm.sh --broker-url http://127.0.0.1:1126 --verify-only --mcp
```

This command does not load data. Its SDK client verifies the MCP server but does
not substitute for the separate native LLM evaluation.

## Operational limits and next step

This managed session can read the canonical checkout but cannot write there.
The initial research pack was prepared in permitted scratch space and later
copied into evaluation/farm-reference in the canonical checkout. No live network/broker verification or new
LLM run was performed, and the canonical working tree was left unchanged.

Next, review the questions and optionally create a notebook in the canonical
checkout from an authorized session. It should expose data tables and reference
calculations to the evaluator, while keeping the answers out of the evaluated
client's context. Temporal experiments and general CSV ingestion remain separate
future work.
