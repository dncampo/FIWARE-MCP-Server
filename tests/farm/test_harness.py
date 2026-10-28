"""Local HTTP contract tests. This server is an emulator, not a real NGSI-LD broker."""

import copy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
from urllib.parse import parse_qs, unquote, urlsplit
from urllib.request import urlopen

import pytest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('farm_harness', HERE / 'farm.py')
farm = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = farm
spec.loader.exec_module(farm)


@pytest.fixture
def emulator():
    context = farm.read_json(HERE / 'contexts/user-context.jsonld')
    state = {'entities': {}, 'requests': [], 'reject_batch': False, 'wrong_query': False,
             'bad_pagination': False, 'context_available': True, 'ignore_writes': False,
             'duplicate_pages': False, 'allow_origin': False}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def respond(self, code, data=None, headers=None):
            payload = json.dumps(data).encode() if data is not None else b''
            self.send_response(code)
            self.send_header('Content-Type', 'application/ld+json')
            self.send_header('Content-Length', str(len(payload)))
            for key, value in (headers or {}).items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(payload)

        def handle_request(self):
            parsed = urlsplit(self.path)
            path = unquote(parsed.path)
            query = {k: v[0] for k, v in parse_qs(parsed.query).items()}
            state['requests'].append((self.command, path, query, dict(self.headers)))
            if path == '/user-context.jsonld':
                return self.respond(200, context) if state['context_available'] else self.respond(404, {})
            if path == '/wrong-context.jsonld':
                return self.respond(200, {'@context': {}})
            if state['allow_origin'] and path.startswith('/ngsi-ld/v1/'):
                path = '/proxy' + path
            if not path.startswith('/proxy/ngsi-ld/v1/'):
                return self.respond(404, {})
            # Fetch the URL from the Link header independently, as a broker would.
            # Host validation alone must not mask a URL inaccessible to this server.
            link = self.headers.get('Link', '')
            try:
                target = re.match(r'<([^>]+)>', link)[1]
                with urlopen(target, timeout=1) as response:
                    if json.load(response) != context:
                        raise ValueError('context mismatch')
            except Exception:
                return self.respond(400, {'detail': 'Broker could not resolve Link context'})
            endpoint = path.removeprefix('/proxy/ngsi-ld/v1/')
            if endpoint == 'entityOperations/upsert':
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                if state['reject_batch']:
                    return self.respond(207, {'success': [], 'errors': [{'detail': 'rejected'}]})
                if not state['ignore_writes']:
                    for entity in body:
                        entity = copy.deepcopy(entity)
                        for value in entity.values():
                            if isinstance(value, dict) and 'object' in value:
                                value.setdefault('type', 'Relationship')
                        if query.get('options') == 'update':
                            state['entities'].setdefault(entity['id'], {}).update(entity)
                        else:
                            state['entities'][entity['id']] = entity
                return self.respond(204)
            if endpoint.startswith('entities/'):
                entity = state['entities'].get(endpoint.removeprefix('entities/'))
                return self.respond(200, entity) if entity else self.respond(404, {'detail': 'not found'})
            if endpoint == 'types/Animal':
                return self.respond(200, {'typeName': 'Animal', 'attributeDetails': [
                    {'attributeName': name, 'attributeTypes': [kind]} for name, kind in
                    [('heartRate', 'Property'), ('sex', 'VocabProperty'),
                     ('locatedAt', 'Relationship'), ('location', 'GeoProperty')]]})
            if endpoint == 'types':
                return self.respond(200, [{'typeName': kind} for kind in farm.COUNTS])
            if endpoint != 'entities':
                return self.respond(404, {})
            values = list(state['entities'].values())
            kind = query.get('type')
            for compact in farm.COUNTS:
                if kind == farm.expand(compact, context['@context']):
                    kind = compact
            if kind:
                values = [e for e in values if e['type'] == kind]
            if 'id' in query:
                values = [e for e in values if e['id'] == query['id']]
            expression = query.get('q')
            if expression:
                match = re.fullmatch(r'(\w+)(>|==)(.+)', expression)
                if not match:
                    return self.respond(400, {})
                name, op, literal = match.groups()
                wanted = json.loads(literal)
                if not state['wrong_query']:
                    values = [e for e in values if name in e and
                              (e[name]['value'] > wanted if op == '>' else e[name]['value'] == wanted)]
            total = len(values)
            offset = int(query.get('offset', 0))
            if state['duplicate_pages']:
                offset = 0
            limit = int(query.get('limit', 20))
            values = values[offset:offset + limit]
            if 'attrs' in query:
                attr = query['attrs']
                if attr == farm.expand('heartRate', context['@context']):
                    attr = 'heartRate'
                values = [{k: v for k, v in e.items() if k in ('id', 'type', attr)} for e in values]
            if state['bad_pagination']:
                total += 1
            return self.respond(200, values, {'NGSILD-Results-Count': str(total)})

        do_GET = handle_request
        do_POST = handle_request

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    root = f'http://127.0.0.1:{server.server_port}'
    settings = farm.Settings(root + '/proxy', root + '/user-context.jsonld', None, 2, {})
    state['settings'] = settings
    try:
        yield state
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def run_cli(state, *args, stdin=''):
    settings = state['settings']
    env = {k: v for k, v in os.environ.items() if not k.startswith('NGSI_LD_')}
    env['FARM_PYTHON'] = sys.executable
    return subprocess.run([str(HERE / 'test_farm.sh'), '--broker-url', settings.broker,
                           '--context-url', settings.context, *args], input=stdin, text=True,
                          cwd=HERE, env=env, capture_output=True, timeout=30)


def stored_fixture():
    entities = copy.deepcopy(farm.prepare()[1])
    for entity in entities.values():
        for value in entity.values():
            if isinstance(value, dict) and 'object' in value:
                value.setdefault('type', 'Relationship')
    return entities


def test_fixture_matches_original_sources():
    import hashlib
    batches, expected = farm.prepare()
    source = (HERE / 'source/import-data-static').read_text()
    static = [json.loads(m[1]) for m in re.finditer(r"(?:-d|--data-raw)\s+'([\s\S]*?)'", source)]
    assert batches[1:] == static
    manifest = farm.read_json(HERE / 'fixtures/manifest.json')
    for name in ('import-data-static', 'import-data-dynamic'):
        data = (HERE / 'source' / name).read_bytes()
        assert hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest() == manifest['source_blobs']['src/' + name]
    assert len(expected) == 61 and len(batches[0]) == 40
    assert hashlib.sha256((HERE / 'fixtures/payloads.json').read_bytes()).hexdigest() == manifest['payload_sha256']


@pytest.mark.parametrize('argv,env,wanted', [
    ([], {}, 'http://localhost:1026'),
    (['--broker-url', 'https://farm.example/proxy/'], {}, 'https://farm.example/proxy'),
    (['--host', '192.168.1.50', '--port', '9090'], {}, 'http://192.168.1.50:9090'),
    (['--port', '9090'], {'NGSI_LD_HOST': 'farm.example', 'NGSI_LD_BROKER_URL': 'https://ignored'}, 'http://farm.example:9090'),
    (['--broker-url', 'https://chosen'], {'NGSI_LD_HOST': 'ignored'}, 'https://chosen'),
    ([], {'NGSI_LD_BROKER_URL': 'https://env.example/path'}, 'https://env.example/path'),
    ([], {'NGSI_LD_HOST': 'env.example', 'NGSI_LD_PORT': '9091'}, 'http://env.example:9091'),
    (['--host', '[::1]', '--port', '9090'], {}, 'http://[::1]:9090'),
])
def test_configuration(argv, env, wanted):
    assert farm.arguments(argv, env)[1].broker == wanted


@pytest.mark.parametrize('argv,env', [
    (['--broker-url', 'http://farm', '--host', 'farm'], {}),
    (['--broker-url', 'http://farm', '--port', '80'], {}),
    ([], {'NGSI_LD_BROKER_URL': 'http://farm', 'NGSI_LD_PORT': '80'}),
    *[(['--port', x], {}) for x in ('0', '65536', '-1', 'abc', '1.2', '')],
    *[(['--broker-url', x], {}) for x in ('ftp://farm', 'http://farm:abc', 'http://farm:0',
           'http://farm:', 'http://user:secret@farm', 'http://farm?x=1', 'http://farm#x',
           'farm:1026', 'http://farm/\n', 'http://[::1')],
    (['--host', 'https://farm'], {}), (['--host', 'farm/path'], {}),
    (['--context-url', 'file:///tmp/context'], {}),
    (['--timeout', 'nan'], {}), (['--timeout', '-1'], {}),
    ([], {'NGSI_LD_HEADERS': '{"Link":"bad"}'}),
])
def test_bad_configuration(argv, env):
    with pytest.raises(SystemExit) as exc:
        farm.arguments(argv, env)
    assert exc.value.code == 2


def test_prepare_and_help_from_test_directory():
    for arg in ('--help', '--prepare-only'):
        result = subprocess.run([str(HERE / 'test_farm.sh'), arg], cwd=HERE, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('answer', ['', '\n', 'n\n'])
def test_confirmation_defaults_no_before_any_network(emulator, answer):
    result = run_cli(emulator, stdin=answer)
    assert result.returncode == 3 and 'Continue? [y/N]:' in result.stdout
    assert not emulator['requests']


def test_load_repeat_and_read_only(emulator):
    # This exercises actual shell -> Python -> HTTP requests, with a proxy prefix.
    emulator['entities']['urn:ngsi-ld:Sensor:unrelated'] = {'id': 'urn:ngsi-ld:Sensor:unrelated', 'type': 'Sensor'}
    first = run_cli(emulator, '-y')
    assert first.returncode == 0, first.stdout + first.stderr
    writes = [r for r in emulator['requests'] if r[0] == 'POST']
    assert len(writes) == 5 and [r[2] for r in writes] == [{'options': 'update'}] * 4 + [{}]
    before = copy.deepcopy(emulator['entities'])
    emulator['requests'].clear()
    second = run_cli(emulator, '-y')
    assert second.returncode == 0 and 'no writes needed' in second.stdout, second.stderr
    assert all(r[0] == 'GET' for r in emulator['requests'])
    emulator['requests'].clear()
    third = run_cli(emulator, '--verify-only')
    assert third.returncode == 0 and 'Continue?' not in third.stdout, third.stderr
    assert all(r[0] == 'GET' for r in emulator['requests'])
    assert before == emulator['entities']
    assert 'Sensor:unrelated' in ''.join(emulator['entities'])


def test_host_and_port_cli(emulator):
    emulator['allow_origin'] = True
    root = urlsplit(emulator['settings'].broker)
    result = subprocess.run([str(HERE / 'test_farm.sh'), '--host', root.hostname, '--port', str(root.port),
                             '--context-url', emulator['settings'].context, '-y'],
                            cwd=HERE, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert any(r[1] == '/ngsi-ld/v1/entities' for r in emulator['requests'])
    assert len([r for r in emulator['requests'] if r[0] == 'POST']) == 5


def test_real_mcp_client_against_http_emulator(emulator):
    emulator['entities'] = stored_fixture()
    result = run_cli(emulator, '--verify-only', '--mcp')
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'MCP STDIO:' in result.stdout
    assert all(r[0] == 'GET' for r in emulator['requests'])


@pytest.mark.parametrize('switch', ['reject_batch', 'ignore_writes'])
def test_no_false_success_from_batch_status(emulator, switch):
    emulator[switch] = True
    result = run_cli(emulator, '-y')
    assert result.returncode == 1
    assert 'PASS:' not in result.stdout
    if switch == 'reject_batch':
        assert '207' in result.stderr
        assert len([r for r in emulator['requests'] if r[0] == 'POST']) == 1


@pytest.mark.parametrize('bad_context', ['missing', 'wrong', 'broker_only'])
def test_bad_context_before_writes(emulator, bad_context):
    settings = emulator['settings']
    if bad_context == 'missing':
        emulator['context_available'] = False
        extra = []
    elif bad_context == 'wrong':
        settings.context = settings.context.replace('user-context', 'wrong-context')
        extra = []
    else:
        settings.context_host_url = settings.context
        settings.context = 'http://127.0.0.1:1/user-context.jsonld'
        extra = ['--context-host-url', settings.context_host_url]
    result = run_cli(emulator, '-y', *extra)
    assert result.returncode != 0 and not any(r[0] == 'POST' for r in emulator['requests'])


@pytest.mark.parametrize('defect', ['missing', 'incorrect', 'extra_same_type', 'wrong_query',
                                    'bad_pagination', 'duplicate_pages', 'fabricated_target'])
def test_verify_rejects_incorrect_dataset(emulator, defect):
    emulator['entities'] = stored_fixture()
    if defect == 'missing':
        del emulator['entities']['urn:ngsi-ld:Animal:cow040']
    elif defect == 'incorrect':
        emulator['entities']['urn:ngsi-ld:Animal:cow005']['heartRate']['value'] = 999
    elif defect == 'extra_same_type':
        emulator['entities']['urn:ngsi-ld:Animal:other'] = {'id': 'urn:ngsi-ld:Animal:other', 'type': 'Animal'}
    elif defect == 'fabricated_target':
        emulator['entities']['urn:ngsi-ld:AgriCrop:Grass'] = {'id': 'urn:ngsi-ld:AgriCrop:Grass', 'type': 'AgriCrop'}
    else:
        emulator[defect] = True
    result = run_cli(emulator, '--verify-only')
    assert result.returncode == 1, result.stdout
    assert not any(r[0] != 'GET' for r in emulator['requests'])


def test_collisions_need_separate_confirmation_even_with_yes(emulator):
    emulator['entities'] = stored_fixture()
    emulator['entities']['urn:ngsi-ld:Animal:cow005']['heartRate']['value'] = 999
    rejected = run_cli(emulator, '-y')
    assert rejected.returncode == 3 and 'colliding Smart Farming IDs?' in rejected.stdout
    assert not any(r[0] == 'POST' for r in emulator['requests'])
    accepted = run_cli(emulator, '-y', stdin='y\n')
    assert accepted.returncode == 0, accepted.stderr
    assert emulator['entities']['urn:ngsi-ld:Animal:cow005']['heartRate']['value'] == 70


def test_different_type_collision_never_overwritten(emulator):
    key = 'urn:ngsi-ld:Animal:cow005'
    emulator['entities'][key] = {'id': key, 'type': 'Sensor'}
    result = run_cli(emulator, '-y', stdin='y\n')
    assert result.returncode == 1 and 'unrelated type' in result.stderr
    assert not any(r[0] == 'POST' for r in emulator['requests'])


def test_unavailable_broker():
    settings = farm.Settings('http://127.0.0.1:1', farm.DEFAULT_CONTEXT, None, 0.1, {})
    with pytest.raises(farm.FarmError, match='connection failed') as exc:
        farm.collection(farm.HTTP(settings), type='Animal', limit=1)
    assert exc.value.code == 4


def test_vocab_normalization_only():
    farm.same_content({'type': 'VocabProperty', 'vocab': 'barn'}, {'type': 'VocabProperty', 'vocab': ['barn']})
    with pytest.raises(farm.FarmError):
        farm.same_content({'value': 'barn'}, {'value': ['barn']})
    with pytest.raises(farm.FarmError):
        farm.same_content({'value': True}, {'value': 1})
