"""Real broker acceptance tests; never substitute mocked HTTP responses."""
import asyncio
import os
import subprocess
import sys
import uuid

from mcp import Client
import pytest

from examples.demo import CONTEXT, entities, populate, stdio_params, verify_entity
from urllib.parse import quote

pytestmark = [pytest.mark.integration, pytest.mark.skipif(os.getenv('FIWARE_INTEGRATION') != '1', reason='Set FIWARE_INTEGRATION=1 with Compose broker running')]


async def exercise(client, raw_broker):
    async def call(name, **args):
        response = await client.call_tool(name, args)
        assert not response.is_error, response
        return response.structured_content
    async def success(name, **args):
        result = await call(name, **args)
        assert result['ok'], result
        return result
    tools = (await client.list_tools()).tools
    assert {tool.name for tool in tools} == {'get_broker_info', 'get_types', 'get_attributes', 'get_entity', 'query_entities', 'create_entity', 'update_entity'}
    for tool in tools:
        assert len(tool.description) > 120
        assert tool.input_schema['type'] == 'object' and tool.output_schema
    await success('get_broker_info')
    await populate(client)
    types = await success('get_types')
    assert len(types['data']) >= 3
    attributes = await success('get_attributes', entity_type='Sensor')
    assert attributes['data']['observed_entities']['ok']
    assert attributes['data']['observed_entities']['data']
    entity = await success('get_entity', entity_id='urn:ngsi-ld:Sensor:1')
    verify_entity(entity['data'], entities()[6])
    room = await success('get_entity', entity_id='urn:ngsi-ld:Room:1')
    verify_entity(room['data'], entities()[3])
    building = await success('get_entity', entity_id='urn:ngsi-ld:Building:1')
    verify_entity(building['data'], entities()[0])
    selected = await success('query_entities', type='Sensor', attrs=['temperature'])
    assert selected['data']
    assert all('temperature' in e and 'locatedIn' not in e and 'name' not in e for e in selected['data'])
    typed = await success('query_entities', type='Sensor')
    assert len(typed['data']) >= 3
    filtered = await success('query_entities', type='Sensor', q='temperature>21')
    assert filtered['data'] and all(e['temperature']['value'] > 21 for e in filtered['data'])
    text = await success('query_entities', type='Room', q='name=="Room 1"')
    assert [e['id'] for e in text['data']] == ['urn:ngsi-ld:Room:1']
    first = await success('query_entities', type='Room', limit=1)
    assert first['pagination']['incomplete']
    second = await success('query_entities', type='Room', limit=1, offset=first['pagination']['next_offset'])
    assert first['data'][0]['id'] != second['data'][0]['id']
    geo = await success('query_entities', type='Building', georel='near;maxDistance==10000', geometry='Point', coordinates=[-3.7, 40.4])
    assert geo['data']
    new = dict(entities()[-1], id=f'urn:ngsi-ld:Sensor:test-{uuid.uuid4()}')
    path = 'ngsi-ld/v1/entities/' + quote(new['id'], safe='')
    created = await success('create_entity', entity=new)
    assert created['status'] == 201
    try:
        stored = raw_broker.get(path)
        assert stored.status_code == 200, stored.text
        verify_entity(stored.json(), new)
        duplicate = await call('create_entity', entity=new)
        assert not duplicate['ok'] and duplicate['status'] == 409
        updated = await success('update_entity', entity_id=new['id'], attributes={'temperature': {'type': 'Property', 'value': 29}, '@context': CONTEXT})
        assert updated['status'] == 204
        reread = await success('get_entity', entity_id=new['id'])
        expected = dict(new, temperature={'type': 'Property', 'value': 29})
        verify_entity(reread['data'], expected)
        stored = raw_broker.get(path)
        assert stored.status_code == 200, stored.text
        verify_entity(stored.json(), expected)
    finally:
        deleted = raw_broker.delete(path)
        assert deleted.status_code == 204, deleted.text
    missing = await call('get_entity', entity_id='urn:ngsi-ld:Sensor:does-not-exist')
    assert not missing['ok'] and missing['status'] == 404
    invalid = await call('query_entities', type='Sensor', q='temperature>')
    assert not invalid['ok'] and invalid['status'] == 400


def test_real_broker_stdio(raw_broker):
    async def run():
        async with Client(stdio_params()) as client:
            await exercise(client, raw_broker)
    asyncio.run(run())


def test_real_broker_http(raw_broker):
    import socket
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    params = stdio_params()
    proc = subprocess.Popen([sys.executable, 'server.py', '--http', '--port', str(port)], env=params.env, stdout=subprocess.DEVNULL)
    async def run():
        import httpx
        for _ in range(100):
            try:
                with httpx.Client(trust_env=False) as http:
                    http.get(f'http://127.0.0.1:{port}/mcp')
                break
            except httpx.ConnectError:
                await asyncio.sleep(0.1)
        async with Client(f'http://127.0.0.1:{port}/mcp') as client:
            await exercise(client, raw_broker)
    try:
        asyncio.run(run())
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def test_real_broker_read_only(raw_broker):
    async def run():
        async with Client(stdio_params(writes=False)) as client:
            info = (await client.call_tool('get_broker_info')).structured_content
            assert info['ok'] and not info['data']['writes_enabled']
            await populate_read_only_fixture()
            original = raw_broker.get('ngsi-ld/v1/entities/urn%3Angsi-ld%3ASensor%3A1')
            assert original.status_code == 200, original.text
            new = dict(entities()[-1], id=f'urn:ngsi-ld:Sensor:blocked-{uuid.uuid4()}')
            for tool, arguments in [('create_entity', {'entity': new}),
                                    ('update_entity', {'entity_id': 'urn:ngsi-ld:Sensor:1',
                                                       'attributes': {'temperature': {'type': 'Property', 'value': -100}}})]:
                response = await client.call_tool(tool, arguments)
                assert not response.is_error
                result = response.structured_content
                assert not result['ok'] and result['status'] is None and result['error']['kind'] == 'read_only'
            absent = raw_broker.get('ngsi-ld/v1/entities/' + quote(new['id'], safe=''))
            assert absent.status_code == 404, absent.text
            stored = raw_broker.get('ngsi-ld/v1/entities/urn%3Angsi-ld%3ASensor%3A1')
            assert stored.status_code == 200 and stored.json() == original.json()
    async def populate_read_only_fixture():
        async with Client(stdio_params()) as writer:
            await populate(writer)
    asyncio.run(run())
