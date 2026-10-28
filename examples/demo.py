"""Load the synthetic dataset through an independent MCP STDIO client."""
import asyncio
import json
import os
from pathlib import Path
import sys

from mcp import Client, StdioServerParameters

ROOT = Path(__file__).resolve().parents[1]
CONTEXT = json.loads((ROOT / 'examples/context.jsonld').read_text())['@context']
CONTEXT_URL = 'http://context:3000/context.jsonld'


def entities():
    result = []
    for kind in ('Building', 'Room', 'Sensor'):
        for i in range(1, 4):
            entity = {'id': f'urn:ngsi-ld:{kind}:{i}', 'type': kind,
                      'name': {'type': 'Property', 'value': f'{kind} {i}'}, '@context': CONTEXT}
            if kind == 'Building':
                entity['location'] = {'type': 'GeoProperty', 'value': {'type': 'Point', 'coordinates': [round(-3.7 + i / 1000, 3), 40.4]}}
            elif kind == 'Room':
                entity['floor'] = {'type': 'Property', 'value': i}
                entity['locatedIn'] = {'type': 'Relationship', 'object': f'urn:ngsi-ld:Building:{i}'}
            else:
                entity['temperature'] = {'type': 'Property', 'value': 18 + i * 2}
                entity['locatedIn'] = {'type': 'Relationship', 'object': f'urn:ngsi-ld:Room:{i}'}
            result.append(entity)
    return result


def stdio_params(*, writes=True):
    return StdioServerParameters(command=sys.executable, args=[str(ROOT / 'server.py')],
                                 env={**os.environ, 'NGSI_LD_ENABLE_WRITES': str(writes).lower(),
                                      'NGSI_LD_CONTEXT_URL': CONTEXT_URL})


def verify_entity(actual, expected):
    """Check fixture fields while allowing broker-added metadata and contexts."""
    def check(value, wanted, path):
        if isinstance(wanted, dict):
            if not isinstance(value, dict):
                raise RuntimeError(f'{path}: expected an object, got {value!r}')
            for key, item in wanted.items():
                if key != '@context':
                    if key not in value:
                        raise RuntimeError(f'{path}.{key}: missing from stored entity')
                    check(value[key], item, f'{path}.{key}')
        elif value != wanted:
            raise RuntimeError(f'{path}: expected {wanted!r}, got {value!r}')
    check(actual, expected, expected['id'])


async def populate(client):
    counts = {'inserted': 0, 'existing': 0, 'verified': 0}
    for entity in entities():
        response = await client.call_tool('create_entity', {'entity': entity})
        result = response.structured_content
        if response.is_error or not result or result['status'] not in (201, 409):
            raise RuntimeError(result)
        if result['status'] == 201 and not result['ok']:
            raise RuntimeError(result)
        counts['inserted' if result['status'] == 201 else 'existing'] += 1
        stored = await client.call_tool('get_entity', {'entity_id': entity['id']})
        if stored.is_error or not stored.structured_content or not stored.structured_content['ok']:
            raise RuntimeError(f"Could not verify {entity['id']}: {stored}")
        verify_entity(stored.structured_content['data'], entity)
        counts['verified'] += 1
        print(f"{entity['id']}: HTTP {result['status']}, stored content verified")
    print(json.dumps(counts))
    return counts


async def main():
    async with Client(stdio_params()) as client:
        info = (await client.call_tool('get_broker_info')).structured_content
        if not info['ok']:
            raise RuntimeError(info)
        await populate(client)


if __name__ == '__main__':
    asyncio.run(main())
