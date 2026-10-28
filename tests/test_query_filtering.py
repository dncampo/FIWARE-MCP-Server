"""Read only query regressions against the stored demonstration fixtures."""
import asyncio
import json
import os
from pathlib import Path
import sys

from mcp import Client, StdioServerParameters
import pytest

from examples.demo import CONTEXT_URL

pytestmark = [pytest.mark.integration, pytest.mark.skipif(os.getenv('FIWARE_INTEGRATION') != '1', reason='Set FIWARE_INTEGRATION=1 with the existing Compose broker running')]
ROOT = Path(__file__).resolve().parents[1]
CASES = [
    ('Sensor', 'temperature', 'temperature>19', {1: 20, 2: 22, 3: 24}),
    ('Sensor', 'temperature', 'temperature>21', {2: 22, 3: 24}),
    ('Sensor', 'temperature', 'temperature==20', {1: 20}),
    ('Sensor', 'temperature', 'temperature>25', {}),
    ('Room', 'floor', 'floor==1', {1: 1}),
]


def stored_values(response, attribute):
    assert response.status_code == 200, response.text
    return {entity['id']: entity[attribute]['value'] for entity in response.json()}


@pytest.mark.parametrize('expanded', [False, True], ids=['compact_names', 'expanded_type_and_attrs'])
@pytest.mark.parametrize('kind,attribute,q,expected', CASES)
def test_direct_and_mcp_filter_values(raw_broker, kind, attribute, q, expected, expanded):
    entity_type = f'https://example.org/{kind}' if expanded else kind
    attrs = [f'https://example.org/{attribute}'] if expanded else [attribute]
    # Establish real stored values before relying on any filtered or empty result.
    existing = raw_broker.get('ngsi-ld/v1/entities', params={'type': kind, 'limit': 100})
    baseline = stored_values(existing, attribute)
    wanted_baseline = {f'urn:ngsi-ld:{kind}:{i}': (18 + i * 2 if kind == 'Sensor' else i) for i in range(1, 4)}
    assert baseline == wanted_baseline
    wanted = {f'urn:ngsi-ld:{kind}:{i}': value for i, value in expected.items()}
    direct = raw_broker.get('ngsi-ld/v1/entities', params={'type': entity_type, 'q': q, 'attrs': ','.join(attrs), 'count': 'true'})
    assert stored_values(direct, attribute) == wanted
    assert int(direct.headers['NGSILD-Results-Count']) == len(wanted)
    assert all('name' not in entity and 'locatedIn' not in entity for entity in direct.json())

    async def run():
        for context_mode in ('default', 'per_call'):
            env = {**os.environ, 'NGSI_LD_ENABLE_WRITES': 'false', 'NGSI_LD_CONTEXT_URLS': json.dumps([CONTEXT_URL])}
            env.pop('NGSI_LD_CONTEXT_URL', None)
            if context_mode == 'default':
                env['NGSI_LD_CONTEXT_URL'] = CONTEXT_URL
            arguments = {'type': entity_type, 'q': q, 'attrs': attrs}
            if context_mode == 'per_call':
                arguments['context_url'] = CONTEXT_URL
            params = StdioServerParameters(command=sys.executable, args=[str(ROOT / 'server.py')], env=env)
            async with Client(params) as client:
                result = await client.call_tool('query_entities', arguments)
                assert not result.is_error, result
                body = result.structured_content
                assert body['ok'] and body['status'] == 200, body
                assert {entity['id']: entity[attribute]['value'] for entity in body['data']} == wanted
                assert body['pagination']['returned'] == len(wanted)
                assert body['pagination']['total'] == len(wanted)
                assert all('name' not in entity and 'locatedIn' not in entity for entity in body['data'])
    asyncio.run(run())


def test_missing_context_reproduced_and_explicit_context_recovers():
    import httpx
    base = os.getenv('NGSI_LD_BROKER_URL', 'http://localhost:1026').rstrip('/')
    headers = json.loads(os.getenv('NGSI_LD_HEADERS', '{}'))
    # Same type and predicate on both requests: only the context header changes.
    headers.pop('Link', None)
    headers.pop('link', None)
    headers['Accept'] = 'application/ld+json'
    arguments = {'type': 'https://example.org/Sensor', 'q': 'temperature>19'}
    with httpx.Client(headers=headers, trust_env=False, timeout=10) as http:
        missing = http.get(base + '/ngsi-ld/v1/entities', params=arguments)
        assert missing.status_code == 200 and missing.json() == [], missing.text
        fixed = http.get(base + '/ngsi-ld/v1/entities', params=arguments, headers={
            'Link': f'<{CONTEXT_URL}>; rel="http://www.w3.org/ns/json-ld#context"; type="application/ld+json"'})
        assert fixed.status_code == 200, fixed.text
        expected = {f'urn:ngsi-ld:Sensor:{i}': 18 + i * 2 for i in range(1, 4)}
        assert stored_values(fixed, 'temperature') == expected

    async def run():
        env = {**os.environ, 'NGSI_LD_BROKER_URL': base, 'NGSI_LD_ENABLE_WRITES': 'false',
               'NGSI_LD_CONTEXT_URLS': json.dumps([CONTEXT_URL])}
        env.pop('NGSI_LD_CONTEXT_URL', None)
        params = StdioServerParameters(command=sys.executable, args=[str(ROOT / 'server.py')], env=env)
        async with Client(params) as client:
            missing = (await client.call_tool('query_entities', arguments)).structured_content
            assert missing['ok'] and missing['status'] == 200 and missing['data'] == [], missing
            fixed = (await client.call_tool('query_entities', {**arguments, 'context_url': CONTEXT_URL})).structured_content
            assert fixed['ok'] and fixed['status'] == 200, fixed
            assert {entity['id']: entity['temperature']['value'] for entity in fixed['data']} == expected
    asyncio.run(run())
