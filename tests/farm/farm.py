"""Safe, frozen Smart Farming snapshot loader and NGSI-LD regression checks.

Only this test harness knows the farming model. No upstream script is executed.
"""

import argparse
import asyncio
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import sys
from urllib.parse import quote, urlsplit
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler
from urllib.error import HTTPError, URLError

HERE = Path(__file__).resolve().parent
REVISION = '05c6fdd118b731a5c362b0892c9efb00968dc7a4'
DEFAULT_HOST = 'localhost'
DEFAULT_PORT = 1026
DEFAULT_CONTEXT = (
    'https://raw.githubusercontent.com/dncampo/fgs2025-talking-with-smart-solution/'
    + REVISION + '/src/data-models/user-context.jsonld'
)
COUNTS = {'Animal': 47, 'AgriParcel': 6, 'Building': 4, 'Person': 4}
TOOLS = {'get_broker_info', 'get_types', 'get_attributes', 'get_entity',
         'query_entities', 'create_entity', 'update_entity'}
CASES = [('Animal', 'heartRate>56', 'heartRate', lambda v: v > 56),
         ('Animal', 'weight>500', 'weight', lambda v: v > 500),
         ('Animal', 'species=="pig"', 'species', lambda v: v == 'pig'),
         ('Animal', 'species=="dairy cattle"', 'species', lambda v: v == 'dairy cattle'),
         ('AgriParcel', 'temperature>10', 'temperature', lambda v: v > 10)]


class FarmError(Exception):
    def __init__(self, message, code=1):
        super().__init__(message)
        self.code = code


def require(condition, message):
    if not condition:
        raise FarmError(str(message))


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def port(value):
    if not str(value).isascii() or not str(value).isdigit() or not 1 <= int(value) <= 65535:
        raise ValueError('port must be an integer from 1 to 65535')
    return int(value)


def url(value, label):
    try:
        parsed = urlsplit(value)
        require(parsed.scheme in ('http', 'https') and parsed.hostname and
                not parsed.username and not parsed.password and not parsed.query and
                not parsed.fragment and not any(c.isspace() or c in '<>"\\' for c in value),
                f'{label} must be an HTTP(S) URL without credentials, query, fragment or whitespace')
        if parsed.netloc.endswith(':'):
            raise ValueError('empty port')
        if parsed.port is not None:
            port(parsed.port)
    except ValueError as exc:
        raise FarmError(f'Invalid {label}: {exc}', 2) from exc
    return value.rstrip('/')


@dataclass
class Settings:
    broker: str
    context: str
    context_host_url: str | None
    timeout: float
    headers: dict


def arguments(argv=None, environ=None):
    env = os.environ if environ is None else environ
    parser = argparse.ArgumentParser(description=__doc__, epilog=(
        'CLI overrides environment. CLI --broker-url cannot be combined with CLI --host/--port. '
        'CLI host/port ignores environment broker URL. At environment level URL and host/port '
        'are mutually exclusive. -y never approves collisions. See tests/farm/README.md.'))
    parser.add_argument('-y', '--yes', action='store_true', help='accept initial loading prompt only')
    parser.add_argument('--broker-url', help='HTTP(S) broker base URL, including optional proxy path')
    parser.add_argument('--host', help='broker hostname or bracketed IPv6 address (HTTP)')
    parser.add_argument('--port', help='broker TCP port, 1..65535')
    parser.add_argument('--context-url', help='original user context URL reachable by broker; sent in Link')
    parser.add_argument('--context-host-url', help='host-reachable alias of the same context for byte/content validation')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--verify-only', action='store_true', help='read-only verification; never loads entities')
    mode.add_argument('--prepare-only', action='store_true', help='offline fixture/hash/count validation; no network')
    parser.add_argument('--mcp', action='store_true', help='also verify through real read-only MCP STDIO client (project requirements needed)')
    parser.add_argument('--timeout', type=float, default=10, help='positive per-request timeout seconds (default: 10)')
    args = parser.parse_args(argv)
    try:
        if args.broker_url is not None and (args.host is not None or args.port is not None):
            raise ValueError('--broker-url cannot be combined with --host or --port')
        if args.broker_url is not None:
            broker = args.broker_url
        elif args.host is not None or args.port is not None:
            broker = None
        else:
            broker = env.get('NGSI_LD_BROKER_URL') or None
            if broker and (env.get('NGSI_LD_HOST') or env.get('NGSI_LD_PORT')):
                raise ValueError('NGSI_LD_BROKER_URL conflicts with NGSI_LD_HOST/NGSI_LD_PORT; unset one form')
        if broker is None:
            host = args.host if args.host is not None else env.get('NGSI_LD_HOST', DEFAULT_HOST)
            if not host or any(c in host for c in '/?#@'):
                raise ValueError('--host must contain only a hostname/IP, without scheme or path')
            number = port(args.port if args.port is not None else env.get('NGSI_LD_PORT', DEFAULT_PORT))
            broker = f'http://{host}:{number}'
        broker = url(broker, 'broker URL')
        context = url(args.context_url if args.context_url is not None else
                      env.get('NGSI_LD_CONTEXT_URL', DEFAULT_CONTEXT), 'context URL')
        host_context = url(args.context_host_url, 'context host URL') if args.context_host_url else None
        if not math.isfinite(args.timeout) or args.timeout <= 0:
            raise ValueError('--timeout must be finite and positive')
        headers = json.loads(env.get('NGSI_LD_HEADERS', '{}'))
        if not isinstance(headers, dict) or any(not isinstance(k, str) or not isinstance(v, str) or
                any(c in k + v for c in '\r\n') for k, v in headers.items()):
            raise ValueError('NGSI_LD_HEADERS must be a JSON object of string headers')
        if {k.lower() for k in headers} & {'host', 'link', 'content-type', 'accept', 'content-length',
                                                   'connection', 'transfer-encoding'}:
            raise ValueError('NGSI_LD_HEADERS contains a reserved header')
    except (FarmError, ValueError) as exc:
        parser.error(str(exc))
    return args, Settings(broker, context, host_context, args.timeout, headers)


def snapshot(batches):
    state = {}
    for index, batch in enumerate(batches):
        for entity in batch:
            if index == 4:  # Original last static batch replaces; previous batches update.
                state[entity['id']] = dict(entity)
            else:
                state.setdefault(entity['id'], {}).update(entity)
    return state


def prepare():
    manifest = read_json(HERE / 'fixtures/manifest.json')
    require(manifest['source_commit'] == REVISION, 'Unexpected fixture revision')
    for name, wanted in manifest['files_sha256'].items():
        require(hashlib.sha256((HERE / name).read_bytes()).hexdigest() == wanted,
                f'Bundled file checksum failed: {name}')
    batches = read_json(HERE / 'fixtures/payloads.json')
    require([len(b) for b in batches] == [40, 20, 5, 3, 8], 'Unexpected batch sizes')
    expected = snapshot(batches)
    require(dict(Counter(e['type'] for e in expected.values())) == COUNTS, 'Unexpected fixture counts')
    return batches, expected


def same_content(actual, expected, path='entity'):
    """Preserve source semantics; only vocab singleton compaction is equivalent."""
    if isinstance(expected, dict):
        require(isinstance(actual, dict), f'{path}: expected an object, got {actual!r}')
        for key, value in expected.items():
            if key == '@context':
                continue
            require(key in actual, f'{path}.{key}: missing')
            if key == 'vocab' and expected.get('type') == 'VocabProperty':
                observed = actual[key] if isinstance(actual[key], list) else [actual[key]]
                wanted = value if isinstance(value, list) else [value]
                same_content(observed, wanted, path + '.vocab')
            else:
                same_content(actual[key], value, path + '.' + key)
    else:
        require((type(actual) is type(expected) or
                 (type(actual) in (int, float) and type(expected) in (int, float))) and actual == expected,
                f'{path}: expected {expected!r}, got {actual!r}')


def same_entity(actual, expected):
    same_content(actual, expected, expected['id'])
    extras = set(actual) - set(expected) - {'@context', 'createdAt', 'modifiedAt'}
    require(not extras, f"{expected['id']}: unexpected attributes {sorted(extras)}")
    for name, value in expected.items():
        if isinstance(value, dict) and 'object' in value:
            require(actual[name].get('type') == 'Relationship', f'{name}: expected normalized Relationship')


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class HTTP:
    """Standard library transport; broker redirects/proxy environment never change target."""
    def __init__(self, settings):
        self.settings = settings
        self.opener = build_opener(ProxyHandler({}), NoRedirect())

    def request(self, method, target, *, params=None, body=None, context=True, external=False):
        from urllib.parse import urlencode
        destination = target if external else self.settings.broker + target
        if params:
            destination += '?' + urlencode(params)
        headers = {} if external else dict(self.settings.headers)
        headers['Accept'] = 'application/ld+json'
        if context and not external:
            headers['Link'] = (f'<{self.settings.context}>; rel="http://www.w3.org/ns/json-ld#context"; '
                               'type="application/ld+json"')
        if body is not None:
            headers['Content-Type'] = 'application/json'
        request = Request(destination, data=json.dumps(body).encode() if body is not None else None,
                          headers=headers, method=method)
        try:
            try:
                response = self.opener.open(request, timeout=self.settings.timeout)
            except HTTPError as exc:
                response = exc
            with response:
                raw = response.read(2_000_001)
                require(len(raw) <= 2_000_000, f'{method} {destination}: response exceeds 2 MB')
                try:
                    data = json.loads(raw) if raw else None
                except (ValueError, UnicodeDecodeError):
                    raise FarmError(f'{method} {destination}: HTTP {response.code}, invalid JSON response')
                return response.code, dict(response.headers.items()), data
        except (URLError, TimeoutError, OSError) as exc:
            raise FarmError(f'{method} {destination}: connection failed: {exc}. '
                            'Check broker/context URL, TLS, network and container DNS.', 4) from exc


def collection(http, **params):
    status, headers, data = http.request('GET', '/ngsi-ld/v1/entities', params=params)
    require(status == 200 and isinstance(data, list), f'NGSI-LD entity query failed: HTTP {status}: {data}')
    require(all(isinstance(e, dict) and isinstance(e.get('id'), str) and 'type' in e for e in data),
            f'Invalid NGSI-LD entity collection: {data}')
    return headers, data


def preflight(http):
    settings = http.settings
    status, _, document = http.request('GET', settings.context_host_url or settings.context, external=True)
    require(status == 200 and document == read_json(HERE / 'contexts/user-context.jsonld'),
            f'Context is missing, inaccessible or differs from pinned user-context.jsonld (HTTP {status}). '
            'Use --context-host-url for a host-reachable alias, while --context-url remains broker-reachable.')
    # This is executed BY THE BROKER with the actual Link URL, not an inference
    # from host connectivity. Full semantic checks follow after ingestion.
    collection(http, type='Animal', attrs='heartRate', q='heartRate>56', limit=1)
    print('Context bytes validated on host; broker accepted a context-dependent NGSI-LD query.', flush=True)


def get_entity(http, entity_id):
    status, _, data = http.request('GET', '/ngsi-ld/v1/entities/' + quote(entity_id, safe=''))
    require(status in (200, 404), f'{entity_id}: HTTP {status}: {data}')
    if status == 200:
        require(isinstance(data, dict) and data.get('id') == entity_id and 'type' in data,
                f'{entity_id}: invalid entity response: {data}')
    return status, data


def confirm(prompt):
    try:
        return input(prompt).strip().lower() == 'y'
    except EOFError:
        return False


def load(http, batches, expected):
    pending = set()
    collisions = []
    # Inspect EVERY ID before writing any batch. Unrelated entities aren't queried for loading.
    for entity_id, entity in expected.items():
        status, stored = get_entity(http, entity_id)
        if status == 404:
            pending.add(entity_id)
            continue
        require(stored['type'] == entity['type'],
                f'ID collision with unrelated type: {entity_id} ({stored["type"]}); refusing all writes')
        try:
            same_entity(stored, entity)
        except FarmError as exc:
            collisions.append((entity_id, str(exc)))
            pending.add(entity_id)
    if collisions:
        print('Existing fixture IDs differ. Replaying original batches will update these IDs:')
        for entity_id, reason in collisions:
            print(f'  {entity_id}: {reason}')
        print('Source attributes will be overwritten; IDs in the final static batch are replaced entirely.\n'
              'No other IDs will be written. -y does not accept this confirmation.')
        if not confirm('Overwrite these colliding Smart Farming IDs? [y/N]: '):
            raise FarmError('Collision overwrite declined; no writes made.', 3)
    if not pending:
        print('Already loaded: all 61 fixture entities match; no writes needed.', flush=True)
        return
    for index, batch in enumerate(batches):
        selected = [e for e in batch if e['id'] in pending]
        if not selected:
            continue
        print(f'Loading original batch {index + 1}/5 ({len(selected)} operations)', flush=True)
        status, _, data = http.request('POST', '/ngsi-ld/v1/entityOperations/upsert',
                                      params={} if index == 4 else {'options': 'update'}, body=selected)
        require(status in (201, 204) and data is None,
                f'Batch {index + 1}: HTTP {status}: {data}. Load stopped; some writes may have applied. '
                'No rollback or deletion was attempted. Inspect --verify-only before retrying.')


def paged(http, **filters):
    found = {}
    for offset in range(0, 10000, 20):
        headers, page = collection(http, **filters, limit=20, offset=offset, count='true')
        require(len(page) <= 20, 'Broker ignored pagination limit')
        for entity in page:
            require(entity['id'] not in found, f'Duplicate pagination ID: {entity["id"]}')
            found[entity['id']] = entity
        total = next((v for k, v in headers.items() if k.lower() == 'ngsild-results-count'), None)
        if total is not None:
            require(str(total).isdigit(), f'Invalid NGSI-LD count: {total}')
            require(len(found) <= int(total), 'Pagination exceeded reported count')
        if len(page) < 20:
            require(total is None or len(found) == int(total), 'Pagination ended before reported count')
            return found
    raise FarmError('Pagination safety bound reached')


def expected_case(expected, kind, attribute, predicate):
    return {key for key, e in expected.items() if e['type'] == kind and
            attribute in e and predicate(e[attribute]['value'])}


def expand(term, context):
    """Expand only pinned simple term mappings; this is test code, not a JSON-LD processor."""
    value = context[term]
    prefix, sep, suffix = value.partition(':')
    return context[prefix] + suffix if sep and prefix in context else value


def verify(http, expected):
    stored = {}
    actual_counts = {}
    # Count the entire four types. Other types are allowed and never written.
    # Additional same-type entities cause an explicit count/ID failure, never deletion.
    for kind, count in COUNTS.items():
        entities = paged(http, type=kind)
        wanted = {key for key, e in expected.items() if e['type'] == kind}
        require(set(entities) == wanted,
                f'{kind}: expected {count}, found {len(entities)}; missing={sorted(wanted-set(entities))}; '
                f'extra={sorted(set(entities)-wanted)}')
        for entity_id, entity in entities.items():
            same_entity(entity, expected[entity_id])
        stored.update(entities)
        actual_counts[kind] = len(entities)
        print(f'{kind}: {len(entities)}/{count}; IDs, content and pagination verified', flush=True)
    context = read_json(HERE / 'contexts/user-context.jsonld')['@context']
    # Expanded types/attributes must address the same data, proving the original
    # mappings actually took effect at the broker rather than accepting an empty 200.
    representative = 'urn:ngsi-ld:Animal:cow005'
    _, values = collection(http, type=expand('Animal', context), id=representative,
                           attrs=expand('heartRate', context), limit=1)
    require(len(values) == 1 and values[0]['id'] == representative and
            values[0].get('heartRate', {}).get('value') == 70,
            f'Broker context semantic resolution failed: {values}')
    status, _, types = http.request('GET', '/ngsi-ld/v1/types', params={'details': 'true', 'limit': 100})
    require(status == 200 and isinstance(types, list) and
            set(COUNTS) <= {t.get('typeName') for t in types if isinstance(t, dict)},
            f'Type discovery failed: HTTP {status}: {types}')
    status, _, metadata = http.request('GET', '/ngsi-ld/v1/types/Animal')
    require(status == 200 and isinstance(metadata, dict), f'Attribute discovery failed: {metadata}')
    attrs = {a['attributeName']: a for a in metadata.get('attributeDetails', [])}
    for name, kind in [('heartRate', 'Property'), ('sex', 'VocabProperty'),
                       ('locatedAt', 'Relationship'), ('location', 'GeoProperty')]:
        require(kind in attrs.get(name, {}).get('attributeTypes', []), f'Missing {name}/{kind} metadata')
    for kind, query, attribute, predicate in CASES:
        matches = paged(http, type=kind, q=query)
        require(set(matches) == expected_case(expected, kind, attribute, predicate), f'Incorrect results: {query}')
        for entity_id, entity in matches.items():
            same_entity(entity, expected[entity_id])
        print(f'Query {kind} {query}: {len(matches)} expected matches', flush=True)
    edges = []
    cache = {}
    for entity in expected.values():
        for name, value in entity.items():
            if isinstance(value, dict) and 'object' in value:
                target = value['object']
                if target not in cache:
                    cache[target] = get_entity(http, target)
                status, actual = cache[target]
                require(status == (200 if target in expected else 404),
                        f'Unexpected relationship target status: {target}: {status}; '
                        'reference missing targets must stay absent')
                if status == 200:
                    same_entity(actual, expected[target])
                edges.append((entity['id'], name, target, status))
    unresolved = [e for e in edges if e[3] == 404]
    require(len(edges) == 102 and len(unresolved) == 9, 'Unexpected relationship edge counts')
    print(f'Relationships: {len(edges) - len(unresolved)} resolved, {len(unresolved)} known dangling edges:')
    for source, name, target, _ in unresolved:
        print(f'  {source} --{name}--> {target} (404; preserved source defect)')
    return stored, actual_counts


async def verify_mcp(settings, expected):
    from mcp import Client, StdioServerParameters
    env = {**os.environ, 'NGSI_LD_BROKER_URL': settings.broker, 'NGSI_LD_ENABLE_WRITES': 'false',
           'NGSI_LD_CONTEXT_URL': settings.context, 'NGSI_LD_CONTEXT_URLS': json.dumps([settings.context]),
           'NGSI_LD_HEADERS': json.dumps(settings.headers), 'NGSI_LD_TIMEOUT': str(settings.timeout)}
    params = StdioServerParameters(command=sys.executable, args=[str(HERE.parents[1] / 'server.py')], env=env)
    async with Client(params) as client:
        require({t.name for t in (await client.list_tools()).tools} == TOOLS, 'MCP seven-tool interface changed')

        async def call(name, **args):
            response = await client.call_tool(name, args)
            result = response.structured_content
            require(not response.is_error and isinstance(result, dict) and result.get('ok'),
                    f'MCP {name}: {result}')
            return result

        info = await call('get_broker_info')
        require(info['data']['endpoint'] == settings.broker and not info['data']['writes_enabled'],
                'MCP endpoint or read-only policy mismatch')
        await call('get_types', limit=100)
        attributes = await call('get_attributes', entity_type='Animal', sample_limit=1)
        require(attributes['data']['observed_entities']['ok'] and
                attributes['data']['observed_entities']['data'], 'MCP attribute discovery returned no sample')
        for kind, query, attribute, predicate in CASES:
            result = await call('query_entities', type=kind, q=query, limit=100)
            require({e['id'] for e in result['data']} == expected_case(expected, kind, attribute, predicate),
                    f'MCP incorrect filter: {query}')
        for kind in COUNTS:
            ids = []
            for offset in range(0, 100, 20):
                result = await call('query_entities', type=kind, limit=20, offset=offset)
                ids.extend(e['id'] for e in result['data'])
                for entity in result['data']:
                    same_entity(entity, expected[entity['id']])
                pagination = result['pagination']
                require(pagination['returned'] == len(result['data']), 'MCP returned count mismatch')
                if len(result['data']) < 20:
                    require(pagination['has_more'] is False and pagination['next_offset'] is None,
                            'MCP terminal pagination incorrect')
                    break
                require(pagination['next_offset'] == offset + 20, 'MCP next offset incorrect')
            require(len(ids) == len(set(ids)) and set(ids) ==
                    {key for key, e in expected.items() if e['type'] == kind}, 'MCP pagination incorrect')
        targets = {v['object'] for e in expected.values() for v in e.values()
                   if isinstance(v, dict) and 'object' in v}
        for target in sorted(targets):
            response = await client.call_tool('get_entity', {'entity_id': target})
            result = response.structured_content
            require(not response.is_error and isinstance(result, dict), f'MCP relationship error: {target}')
            if target in expected:
                require(result.get('ok'), f'MCP failed target: {target}')
                same_entity(result['data'], expected[target])
            else:
                require(result.get('ok') is False and result.get('status') == 404,
                        f'MCP missing target fabricated or wrong error: {target}')
    print('MCP STDIO: seven tools, discovery, filters, pagination and relationship traversal PASS', flush=True)


def main(argv=None):
    args, settings = arguments(argv)
    try:
        require(sys.version_info >= (3, 11), 'Python 3.11+ is required')
        batches, expected = prepare()
        if args.prepare_only:
            print(f'Fixture PASS: revision {REVISION}; counts {COUNTS}; 61 entities; no network used.')
            return 0
        if args.mcp:
            try:
                import mcp  # noqa: F401
            except ImportError as exc:
                raise FarmError('Install project requirements before --mcp: python -m pip install -r requirements.txt', 2) from exc
        print(f'Smart Farming Integration Test\n\nContext Broker: {settings.broker}\n'
              'Source: fgs2025-talking-with-smart-solution\n', flush=True)
        if not args.verify_only:
            print('This operation will create or update Smart Farming\n'
                  'entities in the configured Context Broker.\n\n'
                  'Existing unrelated entities will not be deleted.\n', flush=True)
            if not args.yes and not confirm('Continue? [y/N]: '):
                raise FarmError('Cancelled; no broker requests or writes made.', 3)
        http = HTTP(settings)
        preflight(http)
        if not args.verify_only:
            load(http, batches, expected)
        _, counts = verify(http, expected)
        if args.mcp:
            try:
                asyncio.run(verify_mcp(settings, expected))
            except Exception as exc:
                raise FarmError(f'MCP STDIO verification failed: {exc}') from exc
        print(f'PASS: verified {sum(counts.values())} entities. Counts: {counts}', flush=True)
        return 0
    except (FarmError, OSError, ValueError, KeyError) as exc:
        print(f'FAIL: {exc}', file=sys.stderr, flush=True)
        return exc.code if isinstance(exc, FarmError) else 1


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print('\nInterrupted; earlier writes, if any, were not rolled back.', file=sys.stderr)
        raise SystemExit(130)
