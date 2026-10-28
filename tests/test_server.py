import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

import httpx
import pytest
from mcp import Client, StdioServerParameters

from broker import Broker, Config
from server import build_server


def invoke(name, args=None, *, status=200, data=None, headers=None, writes=False, config=None):
    requests = []
    def handle(request):
        requests.append(request)
        return httpx.Response(status, json=data, headers=headers)
    async def run():
        async with Client(build_server(config or Config(writes=writes), transport=httpx.MockTransport(handle))) as client:
            response = await client.call_tool(name, args or {})
            assert not response.is_error, response
            return response.structured_content
    return asyncio.run(run()), requests


def test_discovery_schema():
    async def run():
        async with Client(build_server()) as client:
            tools = (await client.list_tools()).tools
            assert {t.name for t in tools} == {'get_broker_info', 'get_types', 'get_attributes', 'get_entity', 'query_entities', 'create_entity', 'update_entity'}
            for tool in tools:
                assert len(tool.description) > 120
                assert tool.input_schema['type'] == 'object'
                assert tool.output_schema
    asyncio.run(run())


def test_query_encoding_and_page():
    q = 'name=="Room 1 & 2";temperature>20'
    result, requests = invoke('query_entities', {'type': 'https://example.org/Room', 'q': q, 'limit': 1, 'attrs': ['name', 'temperature']}, data=[{'id': 'urn:room:1'}], headers={'NGSILD-Results-Count': '2'})
    assert result['ok'] and result['pagination']['has_more'] is True
    assert result['pagination']['next_offset'] == 1
    assert requests[0].url.params['q'] == q
    assert requests[0].url.params['attrs'] == 'name,temperature'


@pytest.mark.parametrize('data,total,more', [([], '0', False), ([{}], None, None), ([{}], '1', False)])
def test_pagination(data, total, more):
    result, _ = invoke('get_types', {'limit': 1}, data=data, headers={'NGSILD-Results-Count': total} if total else {})
    assert result['ok']
    assert result['pagination']['has_more'] is more


@pytest.mark.parametrize('status', [400, 401, 404, 409, 500])
def test_broker_errors(status):
    result, _ = invoke('get_entity', {'entity_id': 'urn:entity:missing'}, status=status, data={'detail': 'diagnostic'})
    assert result['ok'] is False and result['status'] == status
    assert result['data']['detail'] == 'diagnostic'


def test_encoded_id_cannot_redirect():
    result, requests = invoke('get_entity', {'entity_id': 'https://evil.example/a?x=1#frag'}, data={})
    assert result['ok']
    assert requests[0].url.host == 'localhost'
    assert '%3F' in requests[0].url.raw_path.decode()


@pytest.mark.parametrize('args', [{'limit': 0}, {'offset': -1}, {'limit': 101}, {'georel': 'near'}, {'q': ''}, {'id': ['relative']}, {'attrs': []}])
def test_invalid_queries_never_sent(args):
    result, requests = invoke('query_entities', args)
    assert not result['ok'] and not requests


def test_geo_query():
    result, requests = invoke('query_entities', {'type': 'Room', 'georel': 'near;maxDistance==100', 'geometry': 'Point', 'coordinates': [1, 2]}, data=[])
    assert result['ok'] and requests[0].url.params['coordinates'] == '[1,2]'


ENTITY = {'id': 'urn:ngsi-ld:Room:1', 'type': 'Room', 'name': {'type': 'Property', 'value': 'Room 1'}, '@context': {'Room': 'https://example.org/Room', 'name': 'https://example.org/name'}}


@pytest.mark.parametrize('tool,args', [('create_entity', {'entity': ENTITY}), ('update_entity', {'entity_id': ENTITY['id'], 'attributes': {'name': ENTITY['name']}})])
def test_read_only(tool, args):
    result, requests = invoke(tool, args)
    assert result['error']['kind'] == 'read_only' and not requests


def test_create_duplicate_never_updates():
    result, requests = invoke('create_entity', {'entity': ENTITY}, status=409, data={'detail': 'exists'}, writes=True)
    assert not result['ok'] and len(requests) == 1 and requests[0].method == 'POST'


def test_create_inline_context():
    result, requests = invoke('create_entity', {'entity': ENTITY}, status=201, writes=True)
    assert result['ok'] and requests[0].headers['content-type'] == 'application/ld+json'
    assert json.loads(requests[0].content) == ENTITY


def test_context_allowlist():
    result, requests = invoke('get_entity', {'entity_id': ENTITY['id'], 'context_url': 'http://evil/context'})
    assert not result['ok'] and not requests
    config = Config(default_context='http://context/context.jsonld')
    result, requests = invoke('get_entity', {'entity_id': ENTITY['id']}, config=config, data={})
    assert result['ok'] and '<http://context/context.jsonld>' in requests[0].headers['link']


@pytest.mark.parametrize('context', ['http://evil', {'@import': 'http://evil'}, {'term': {'@id': 'urn:x', '@context': 'http://evil'}}])
def test_nested_remote_context_rejected(context):
    result, requests = invoke('create_entity', {'entity': dict(ENTITY, **{'@context': context})}, writes=True)
    assert not result['ok'] and not requests


def test_update_partial_failure_and_context():
    result, requests = invoke('update_entity', {'entity_id': ENTITY['id'], 'attributes': {'name': ENTITY['name'], '@context': ENTITY['@context']}}, status=207, data={'notUpdated': [{'attributeName': 'name'}]}, writes=True)
    assert not result['ok'] and result['error']['kind'] == 'partial_update'
    assert requests[0].method == 'PATCH' and requests[0].url.path.endswith('/attrs')
    assert '@context' in json.loads(requests[0].content)


@pytest.mark.parametrize('entity', [{'type': 'Room'}, dict(ENTITY, name={'type': 'Property'}), dict(ENTITY, rel={'type': 'Relationship', 'object': 'relative'})])
def test_invalid_entities(entity):
    result, requests = invoke('create_entity', {'entity': entity}, writes=True)
    assert not result['ok'] and not requests


def test_http_edge_cases():
    for response, kind in [(httpx.Response(302, headers={'Location': 'http://evil/'}), 'broker_error'), (httpx.Response(200, text='not json'), 'invalid_response'), (httpx.Response(200, text='x' * 100), 'response_too_large')]:
        result = Broker(Config(max_bytes=50), httpx.MockTransport(lambda r: response)).request('GET', '/version')
        assert not result.ok and result.error['kind'] == kind
    def timeout(r):
        raise httpx.ReadTimeout('timeout')
    assert Broker(Config(), httpx.MockTransport(timeout)).request('GET', '/version').error['kind'] == 'timeout'


def test_attributes_observed_sample():
    result, requests = invoke('get_attributes', {'entity_type': 'Room', 'sample_limit': 2}, data=[])
    assert result['ok'] and result['data']['complete_schema'] is False
    assert len(requests) == 2 and requests[1].url.params['limit'] == '2'


@pytest.mark.parametrize('mode', ['auto', 'legacy'])
def test_stdio_real_client(mode):
    async def run():
        params = StdioServerParameters(command=sys.executable, args=[str(Path('server.py').resolve())], env={**os.environ, 'NGSI_LD_BROKER_URL': 'http://127.0.0.1:1', 'NGSI_LD_TIMEOUT': '0.1'})
        async with Client(params, mode=mode) as client:
            assert client.protocol_version == ('2026-07-28' if mode == 'auto' else '2025-11-25')
            assert len((await client.list_tools()).tools) == 7
            response = await client.call_tool('get_types')
            assert response.structured_content['error']['kind'] == 'connection'
    asyncio.run(run())


def test_streamable_http_real_client():
    import socket
    with socket.socket() as sock:
        try:
            sock.bind(('127.0.0.1', 0))
        except PermissionError:
            pytest.skip('Runtime sandbox forbids binding local sockets')
        port = sock.getsockname()[1]
    process = subprocess.Popen([sys.executable, 'server.py', '--http', '--port', str(port)], env={**os.environ, 'NGSI_LD_BROKER_URL': 'http://127.0.0.1:1'}, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    async def run():
        for _ in range(50):
            if process.poll() is not None:
                raise AssertionError('HTTP server exited before becoming ready')
            try:
                with httpx.Client(trust_env=False, timeout=1) as http:
                    http.get(f'http://127.0.0.1:{port}/mcp')
                break
            except httpx.ConnectError:
                await asyncio.sleep(0.1)
        else:
            raise AssertionError('HTTP server did not become ready')
        async with Client(f'http://127.0.0.1:{port}/mcp') as client:
            assert len((await client.list_tools()).tools) == 7
            result = await client.call_tool('get_entity', {'entity_id': 'relative'})
            assert result.structured_content['error']['kind'] == 'validation'
    try:
        asyncio.run(run())
    finally:
        process.terminate()
        process.communicate(timeout=10)


def test_streamable_http_asgi_client():
    import httpx2
    from mcp.client.streamable_http import streamable_http_client
    async def run():
        server = build_server(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=[])))
        app = server.streamable_http_app(json_response=True)
        async with app.router.lifespan_context(app):
            async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app)) as http:
                async with Client(streamable_http_client('http://127.0.0.1:5001/mcp', http_client=http)) as client:
                    assert client.protocol_version == '2026-07-28'
                    assert len((await client.list_tools()).tools) == 7
                    response = await client.call_tool('get_types')
                    assert response.structured_content['ok']
                    assert response.structured_content['data'] == []
    asyncio.run(run())


def test_context_in_attribute_value_cannot_fetch_remote():
    entity = dict(ENTITY, name={'type': 'Property', 'value': {'@context': 'http://evil/private', 'x': 1}})
    result, requests = invoke('create_entity', {'entity': entity}, writes=True)
    assert not result['ok'] and not requests


@pytest.mark.parametrize('kwargs', [{'url': 'ftp://broker'}, {'url': 'http://user:password@broker'}, {'headers': {'Host': 'evil'}}, {'timeout': 0}])
def test_invalid_configuration(kwargs):
    with pytest.raises(ValueError):
        Config(**kwargs)


def test_inline_context_omits_link_and_update_success():
    config = Config(writes=True, default_context='http://context/context.jsonld')
    result, requests = invoke('create_entity', {'entity': ENTITY}, status=201, config=config)
    assert result['ok'] and 'link' not in requests[0].headers
    result, requests = invoke('update_entity', {'entity_id': ENTITY['id'], 'attributes': {'name': ENTITY['name']}}, status=204, writes=True)
    assert result['ok'] and result['status'] == 204


def test_broker_info_does_not_require_vendor_endpoint():
    def handle(request):
        return httpx.Response(404, json={'detail': 'no vendor endpoint'}) if request.url.path == '/version' else httpx.Response(200, json=[])
    async def run():
        async with Client(build_server(transport=httpx.MockTransport(handle))) as client:
            result = (await client.call_tool('get_broker_info')).structured_content
            assert result['ok'] and result['data']['version_probe']['status'] == 404
    asyncio.run(run())


@pytest.mark.parametrize('types', [[], ['Room']])
def test_entity_type_list_response(types):
    result, _ = invoke('get_types', data={'id': 'urn:types:1', 'type': 'EntityTypeList', 'typeList': types})
    assert result['ok'] and result['data'] == types
    assert result['pagination']['returned'] == len(types)
