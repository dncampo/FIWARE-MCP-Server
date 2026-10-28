"""Real NGSI-LD API checks without using the MCP server or production wrapper."""
import os
from urllib.parse import quote
import uuid

import pytest

from examples.demo import CONTEXT, entities, verify_entity

pytestmark = [pytest.mark.integration, pytest.mark.skipif(os.getenv('FIWARE_INTEGRATION') != '1', reason='Set FIWARE_INTEGRATION=1 with Compose broker running')]


def entity_path(entity_id):
    return 'ngsi-ld/v1/entities/' + quote(entity_id, safe='')


@pytest.fixture
def seeded(raw_broker):
    # Repeatable direct loading isolates these API checks from the MCP layer.
    for entity in entities():
        headers = dict(raw_broker.headers)
        headers.pop('link', None)
        response = raw_broker.post('ngsi-ld/v1/entities', json=entity,
                                   headers={**headers, 'Content-Type': 'application/ld+json'})
        assert response.status_code in (201, 409), response.text
        stored = raw_broker.get(entity_path(entity['id']))
        assert stored.status_code == 200, stored.text
        verify_entity(stored.json(), entity)
    return raw_broker


def test_direct_connectivity(raw_broker):
    response = raw_broker.get('version')
    assert response.status_code == 200, response.text
    version = response.json()
    assert isinstance(version, dict) and version
    assert any(str(value).startswith('1.12.0') for value in version.values()), version
    response = raw_broker.get('ngsi-ld/v1/types', params={'details': 'true', 'limit': 10})
    assert response.status_code == 200, response.text
    data = response.json()
    assert isinstance(data, list) or (isinstance(data, dict) and data.get('type') == 'EntityTypeList' and isinstance(data.get('typeList'), list)), data


def test_direct_dataset_and_relationships(seeded):
    for kind in ('Building', 'Room', 'Sensor'):
        response = seeded.get('ngsi-ld/v1/entities', params={'type': kind, 'limit': 100, 'count': 'true'})
        assert response.status_code == 200, response.text
        actual = {entity['id']: entity for entity in response.json()}
        expected = [entity for entity in entities() if entity['type'] == kind]
        assert set(actual) == {entity['id'] for entity in expected}
        assert int(response.headers['NGSILD-Results-Count']) == 3
        for entity in expected:
            verify_entity(actual[entity['id']], entity)


def test_direct_discovery(seeded):
    response = seeded.get('ngsi-ld/v1/types', params={'details': 'true', 'limit': 100})
    assert response.status_code == 200, response.text
    types = response.json()
    assert isinstance(types, list) and len(types) == 3, types
    names = {item['typeName'] for item in types}
    assert names == {'Building', 'Room', 'Sensor'}, types
    response = seeded.get('ngsi-ld/v1/types/Sensor')
    assert response.status_code == 200, response.text
    metadata = response.json()
    assert metadata['typeName'] == 'Sensor'
    attributes = {item['attributeName']: item for item in metadata['attributeDetails']}
    assert 'Property' in attributes['temperature']['attributeTypes']
    assert 'Relationship' in attributes['locatedIn']['attributeTypes']


def test_direct_filters_and_projection(seeded):
    for query, expected in [('temperature>21', {'urn:ngsi-ld:Sensor:2', 'urn:ngsi-ld:Sensor:3'}),
                            ('temperature>100', set())]:
        response = seeded.get('ngsi-ld/v1/entities', params={'type': 'Sensor', 'q': query, 'attrs': 'temperature'})
        assert response.status_code == 200, response.text
        assert {entity['id'] for entity in response.json()} == expected
        for entity in response.json():
            assert entity['temperature']['value'] > 21
            assert 'name' not in entity and 'locatedIn' not in entity
    response = seeded.get('ngsi-ld/v1/entities', params={'type': 'Room', 'q': 'name=="Room 1"'})
    assert response.status_code == 200, response.text
    assert [entity['id'] for entity in response.json()] == ['urn:ngsi-ld:Room:1']


def test_direct_pagination(seeded):
    ids = []
    for offset in range(3):
        response = seeded.get('ngsi-ld/v1/entities', params={'type': 'Room', 'limit': 1, 'offset': offset, 'count': 'true'})
        assert response.status_code == 200, response.text
        assert int(response.headers['NGSILD-Results-Count']) == 3
        assert len(response.json()) == 1
        ids.append(response.json()[0]['id'])
    assert set(ids) == {f'urn:ngsi-ld:Room:{i}' for i in range(1, 4)}
    response = seeded.get('ngsi-ld/v1/entities', params={'type': 'Room', 'limit': 1, 'offset': 3})
    assert response.status_code == 200 and response.json() == []


def test_direct_write_read_and_errors(seeded):
    entity = dict(entities()[-1], id=f'urn:ngsi-ld:Sensor:direct-{uuid.uuid4()}')
    path = entity_path(entity['id'])
    headers = dict(seeded.headers)
    headers.pop('link', None)
    headers['Content-Type'] = 'application/ld+json'
    response = seeded.post('ngsi-ld/v1/entities', json=entity, headers=headers)
    assert response.status_code == 201, response.text
    try:
        stored = seeded.get(path)
        assert stored.status_code == 200, stored.text
        verify_entity(stored.json(), entity)
        duplicate = seeded.post('ngsi-ld/v1/entities', json=entity, headers=headers)
        assert duplicate.status_code == 409, duplicate.text
        response = seeded.patch(path + '/attrs', json={'temperature': {'type': 'Property', 'value': 29}, '@context': CONTEXT}, headers=headers)
        assert response.status_code == 204, response.text
        stored = seeded.get(path)
        assert stored.status_code == 200, stored.text
        verify_entity(stored.json(), dict(entity, temperature={'type': 'Property', 'value': 29}))
    finally:
        response = seeded.delete(path)
        assert response.status_code == 204, response.text
    missing = seeded.get(entity_path('urn:ngsi-ld:Sensor:missing'))
    assert missing.status_code == 404 and missing.json().get('type'), missing.text
    invalid = seeded.get('ngsi-ld/v1/entities', params={'type': 'Sensor', 'q': 'temperature>'})
    assert invalid.status_code == 400 and invalid.json().get('type'), invalid.text
