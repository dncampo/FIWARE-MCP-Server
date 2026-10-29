"""Offline reference material; does not contact or modify a Context Broker."""
import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
REVISION = '05c6fdd118b731a5c362b0892c9efb00968dc7a4'

def save(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')

def value(entity, attribute):
    return entity.get(attribute, {}).get('value')

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', type=Path, default=ROOT)
    args = parser.parse_args(argv)
    root = args.repo_root.resolve()
    fixture = root / 'tests/farm/fixtures/payloads.json'
    batches = json.loads(fixture.read_text())
    assert [len(batch) for batch in batches] == [40, 20, 5, 3, 8]
    entities = {}
    for position, batch in enumerate(batches):
        for operation in batch:
            identifier = operation['id']
            if position == 4:
                entities[identifier] = operation.copy()
            else:
                entities.setdefault(identifier, {}).update(operation)
    counts = dict(Counter(entity['type'] for entity in entities.values()))
    assert counts == {'Animal': 47, 'AgriParcel': 6, 'Building': 4, 'Person': 4}
    edges = []
    for entity in entities.values():
        for attribute, payload in entity.items():
            for item in payload if isinstance(payload, list) else [payload]:
                if isinstance(item, dict) and 'object' in item:
                    targets = item['object'] if isinstance(item['object'], list) else [item['object']]
                    for target in targets:
                        edges.append({'source': entity['id'], 'attribute': attribute,
                                      'target': target, 'target_in_fixture': target in entities})
    assert len(edges) == 102
    assert sum(not edge['target_in_fixture'] for edge in edges) == 9
    animals = sorted(e['id'] for e in entities.values() if e['type'] == 'Animal')
    cases = []

    def case(identifier, question, expected, tools, category='current_state', arguments=None):
        cases.append({'id': identifier, 'question': question, 'category': category,
                      'expected': expected, 'suggested_tools': tools,
                      'example_arguments': arguments or {},
                      'execution_status': 'NOT_RUN'})

    case('F01', 'Explore the farm and report the available entity types and the count of each type.',
         {'counts': counts, 'total': len(entities)}, ['get_types', 'query_entities'])
    observed = {}
    for entity in entities.values():
        if entity['type'] == 'Animal':
            for attribute, payload in entity.items():
                if isinstance(payload, dict):
                    kind = payload.get('type') or ('Relationship' if 'object' in payload else None)
                    observed.setdefault(attribute, set()).add(kind)
    case('F02', 'Which attributes are observed on Animals, and which represent relationships or geographic locations?',
         {'observed_attributes': {k: sorted(v) for k, v in sorted(observed.items())},
          'formal_schema_established': False,
          'note': 'Six source relationship attributes omit type; prior Orion ingestion normalizes them.'},
         ['get_attributes', 'query_entities'])
    specifications = [
        ('F03', 'Which Animals have a heart rate greater than 56?', 'Animal', 'heartRate>56', 'heartRate', lambda x: x > 56),
        ('F04', 'Which Animals have a weight greater than 500, and what units are recorded?', 'Animal', 'weight>500', 'weight', lambda x: x > 500),
        ('F05', 'List all pigs on the farm.', 'Animal', 'species=="pig"', 'species', lambda x: x == 'pig'),
        ('F06', 'How many dairy cattle are there?', 'Animal', 'species=="dairy cattle"', 'species', lambda x: x == 'dairy cattle'),
        ('F07', 'Which parcels have a temperature greater than 10, and what values are recorded?', 'AgriParcel', 'temperature>10', 'temperature', lambda x: x > 10),
        ('F08', 'Are there any Animals with a heart rate greater than 1000?', 'Animal', 'heartRate>1000', 'heartRate', lambda x: x > 1000),
    ]
    for identifier, question, kind, query, attribute, predicate in specifications:
        matches = sorted((e for e in entities.values() if e['type'] == kind
                          and value(e, attribute) is not None and predicate(value(e, attribute))),
                         key=lambda e: e['id'])
        expected = {'count': len(matches), 'matches': [
            {'id': e['id'], 'name': value(e, 'name'), 'value': value(e, attribute),
             'unitCode': e[attribute].get('unitCode')} for e in matches]}
        case(identifier, question, expected, ['query_entities'], arguments={
            'type': kind, 'q': query, 'attrs': ['name', attribute], 'limit': 20, 'offset': 0})
    beany = entities['urn:ngsi-ld:Animal:cow001']
    selected = [edge for edge in edges if edge['source'] == beany['id']]
    case('F09', 'Where is Beany located, and who is the recorded owner? Retrieve the related entities.',
         {'animal': beany['id'], 'relationships': selected,
          'targets': [entities[edge['target']] for edge in selected]}, ['query_entities', 'get_entity'])
    calves = ['urn:ngsi-ld:Animal:cow10' + str(i) for i in (1, 2, 3)]
    case('F10', 'Identify the parents and recorded locations of Bumble, Blossom and Buttercup.',
         {'calves': {i: {k: entities[i].get(k) for k in ('name', 'calvedBy', 'siredBy', 'locatedAt')}
                     for i in calves},
          'missing_location': ['urn:ngsi-ld:Animal:cow101']}, ['query_entities', 'get_entity'])
    case('F11', 'Can you retrieve the recorded owner of Twilight?',
         {'source': 'urn:ngsi-ld:Animal:cow006', 'attribute': 'ownedBy',
          'target': 'urn:ngsi-ld:Person:001', 'expected_http_status': 404,
          'must_not_substitute': 'urn:ngsi-ld:Person:person001'}, ['query_entities', 'get_entity'])
    case('F12', 'Which relationship references cannot be resolved in this dataset?',
         {'missing_edges': [edge for edge in edges if not edge['target_in_fixture']],
          'distinct_targets': sorted({edge['target'] for edge in edges if not edge['target_in_fixture']})},
         ['query_entities', 'get_entity'])
    case('F13', 'Does North Pasture exist? What is its area, and can you verify its boundaries?',
         {'entity': entities['urn:ngsi-ld:AgriParcel:003'], 'area_recorded': False,
          'parcel_boundary_recorded': False, 'cannot_establish': ['parcel area', 'fence crossing']},
         ['query_entities', 'get_entity'], category='missing_information')
    case('F14', 'What breed are the cattle, and can you confirm why Twilight needs to see the vet?',
         {'breed_observed': False, 'twilight': entities['urn:ngsi-ld:Animal:cow006'],
          'diagnosis_confirmed': False,
          'must_not_claim': ['all cattle are Jersey', 'Twilight is definitely not sick', 'calved today relative to current date']},
         ['get_attributes', 'query_entities', 'get_entity'], category='missing_information')
    case('F15', 'Retrieve all Animals in pages of twenty, without duplicates.',
         {'count': 47, 'ids': animals, 'page_lengths': [20, 20, 7],
          'order_requirement': 'Compare sets, not an assumed broker sorting order.'},
         ['query_entities'], arguments={'type': 'Animal', 'attrs': ['name'], 'limit': 20, 'offset': 0})
    case('F16', 'How has the weight of the Animals changed over the last twelve months?',
         {'capability_status': 'UNSUPPORTED_BY_CURRENT_MCP',
          'reason': 'The seven tools expose current state, not a temporal history endpoint.',
          'observedAt_is_not_a_time_series': True,
          'must_not_invent': ['historical values', 'growth rates', 'trends']},
         [], category='unsupported_capability')

    head = subprocess.run(['git', '-C', str(root), 'rev-parse', 'HEAD'],
                          capture_output=True, text=True, timeout=10)
    provenance = {'source_repository': 'https://github.com/dncampo/fgs2025-talking-with-smart-solution',
                  'source_revision': REVISION,
                  'checkout_head': head.stdout.strip() if head.returncode == 0 else None,
                  'payload_sha256': hashlib.sha256(fixture.read_bytes()).hexdigest(),
                  'method': 'Offline replay of original update/update/update/update/replace batches; no broker or LLM calls.',
                  'restriction': 'Keep reference answers outside evaluated client context; these are expected results, not live test passes.'}
    save('reference-answers.json', {'provenance': provenance, 'questions': cases})
    save('questions-only.json', [{'id': c['id'], 'question': c['question']} for c in cases])
    save('reference-entities.json', list(entities.values()))
    save('reference-relationships.json', edges)
    with (OUT / 'reference-attributes.csv').open('w', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['entity_id', 'entity_type', 'attribute', 'declared_ngsi_type',
                         'value_json', 'object_json', 'vocab_json', 'unitCode', 'observedAt'])
        for entity in sorted(entities.values(), key=lambda e: e['id']):
            for attribute, payload in sorted(entity.items()):
                if not isinstance(payload, dict):
                    continue
                writer.writerow([entity['id'], entity['type'], attribute, payload.get('type', ''),
                                 *[json.dumps(payload[k], ensure_ascii=False) if k in payload else ''
                                   for k in ('value', 'object', 'vocab')],
                                 payload.get('unitCode', ''), payload.get('observedAt', '')])
    print(json.dumps({'status': 'OFFLINE_REFERENCE_READY', 'questions': len(cases),
                      'entities': counts, 'relationships': len(edges), 'missing_edges': 9,
                      'output': str(OUT)}))

if __name__ == '__main__':
    main()
