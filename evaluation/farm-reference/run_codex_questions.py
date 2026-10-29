"""Evaluate the existing question bank through native Codex CLI, with read-only MCP."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile
import time
from urllib.parse import urlsplit

from run_questions import READS, python_executable, stop, write_json

HERE = Path(__file__).resolve().parent
PROMPT_PREFIX = (
    'Answer the following question in English using only native FIWARE MCP read tools. '
    'Do not read files, use shell or web tools, modify broker data, or invent missing facts. '
    'Discover the necessary types and attributes from the broker. Follow actual relationship '
    'targets and paginate where needed. Include exact entity IDs, observed values and units, '
    'query arguments, and relevant errors or limitations. Distinguish facts from assumptions.\n\n'
)


def prompt_for(question):
    return PROMPT_PREFIX + question['id'] + ': ' + question['question'] + '\n'


def checksum(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot(root, interpreter, questions_path):
    """Record provenance only; none of this metadata is sent to the model."""
    command = ('import json,sys,mcp.types,httpx; from importlib.metadata import version; '
               'print(json.dumps({"python":sys.version.split()[0],"mcp_sdk":version("mcp"),'
               '"httpx":version("httpx"),"sdk_latest_protocol":mcp.types.LATEST_PROTOCOL_VERSION}))')
    dependencies = subprocess.run([str(interpreter), '-c', command], capture_output=True,
                                  text=True, timeout=15, check=True)
    head = subprocess.run(['git', '-C', str(root), 'rev-parse', 'HEAD'],
                          capture_output=True, text=True, timeout=10, check=True).stdout.strip()
    farm = root / 'tests/farm'
    manifest = json.loads((farm / 'fixtures/manifest.json').read_text())
    kinds = {e['id']: e['type'] for batch in json.loads((farm / 'fixtures/payloads.json').read_text()) for e in batch}
    return {'captured_at_utc': datetime.now(timezone.utc).isoformat(),
            'platform': {'os': platform.system(), 'release': platform.release(), 'architecture': platform.machine()},
            'dependencies': json.loads(dependencies.stdout),
            'mcp': {'repository': 'https://github.com/dncampo/FIWARE-MCP-Server', 'git_commit': head,
                    'source_sha256': {name: checksum(root / name) for name in ('server.py', 'broker.py')},
                    'transport': 'STDIO', 'protocol_note': 'SDK supported revision, not separately captured wire negotiation.'},
            'dataset': {'repository': 'https://github.com/dncampo/fgs2025-talking-with-smart-solution',
                        'source_revision': manifest['source_commit'],
                        'reference_entity_counts': dict(Counter(kinds.values())),
                        'payload_sha256': checksum(farm / 'fixtures/payloads.json'),
                        'context_sha256': checksum(farm / 'contexts/user-context.jsonld')},
            'questions_sha256': checksum(questions_path)}


def arguments_for(executable, model, interpreter, root, broker, context):
    arguments = [executable, '--no-daemon', 'exec', '--ignore-user-config', '--ephemeral',
                 '--skip-git-repo-check', '--sandbox', 'read-only', '--json', '--model', model]
    def override(key, value):
        arguments.extend(['-c', key + '=' + json.dumps(value)])
    override('features.shell_tool', False)
    override('web_search', 'disabled')
    override('mcp_servers.fiware_farm.command', str(interpreter))
    override('mcp_servers.fiware_farm.args', [str(root / 'server.py')])
    override('mcp_servers.fiware_farm.required', True)
    override('mcp_servers.fiware_farm.startup_timeout_sec', 15)
    override('mcp_servers.fiware_farm.tool_timeout_sec', 30)
    override('mcp_servers.fiware_farm.enabled_tools', list(READS))
    for key, value in {'NGSI_LD_BROKER_URL': broker, 'NGSI_LD_CONTEXT_URL': context,
                       'NGSI_LD_CONTEXT_URLS': json.dumps([context]),
                       'NGSI_LD_ENABLE_WRITES': 'false', 'NGSI_LD_HEADERS': '{}'}.items():
        override('mcp_servers.fiware_farm.env.' + key, value)
    for tool in READS:
        override('mcp_servers.fiware_farm.tools.' + tool + '.approval_mode', 'approve')
    return arguments


def summarize(trace):
    events = [json.loads(line) for line in trace.read_text().splitlines() if line.strip()]
    calls, other_tools, answers = [], [], []
    errors = []
    for event in events:
        if event.get('type') in ('error', 'turn.failed'):
            errors.append(event)
        if event.get('type') != 'item.completed':
            continue
        item = event.get('item', {})
        kind = item.get('type')
        if kind == 'mcp_tool_call':
            calls.append({'id': item.get('id'), 'server': item.get('server'),
                          'tool': item.get('tool'), 'arguments': item.get('arguments'),
                          'status': item.get('status'), 'error': item.get('error')})
        elif kind == 'agent_message':
            answers.append(item.get('text', ''))
        elif kind not in ('reasoning', 'plan_update'):
            other_tools.append(item)
    return {'calls': calls, 'other_tools': other_tools, 'errors': errors,
            'answer': answers[-1] if answers else '',
            'turn_completed': any(e.get('type') == 'turn.completed' for e in events)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', type=Path, default=HERE.parent.parent)
    parser.add_argument('--questions', type=Path, default=HERE / 'questions-only.json')
    parser.add_argument('--question', action='append', help='question ID, repeatable; default all 16')
    parser.add_argument('--broker-url', required=True)
    parser.add_argument('--context-url', required=True)
    parser.add_argument('--model', default='gpt-6.1-sol', help='explicit model, recorded in manifest')
    parser.add_argument('--python', dest='python_path', type=Path)
    parser.add_argument('--codex', default='codex', help='native Codex executable')
    parser.add_argument('--timeout', type=int, default=300, help='seconds per question')
    parser.add_argument('--output', type=Path, help='new directory; existing evidence is never overwritten')
    args = parser.parse_args(argv)
    if args.timeout < 1:
        parser.error('--timeout must be positive')
    for address in (args.broker_url, args.context_url):
        parsed = urlsplit(address)
        try:
            port = parsed.port
        except ValueError:
            parser.error('URL port must be valid')
        if (parsed.scheme not in ('http', 'https') or not parsed.hostname or
                parsed.username or parsed.password or parsed.fragment or parsed.query or
                any(c.isspace() for c in address) or port == 0):
            parser.error('Use full HTTP(S) URLs without credentials, query, fragment or whitespace')
    root = args.repo_root.resolve()
    interpreter = python_executable(args.python_path or root / '.venv/bin/python')
    executable = shutil.which(args.codex)
    if not executable or not interpreter.is_file() or not (root / 'server.py').is_file():
        parser.error('Require Codex CLI, server.py and the project Python environment')
    questions_path = args.questions.resolve()
    questions = json.loads(questions_path.read_text())
    if (not isinstance(questions, list) or not questions or
            any(not isinstance(q, dict) or set(q) != {'id', 'question'} or
                not isinstance(q['id'], str) or not q['id'].isalnum() or
                not isinstance(q['question'], str) or not q['question'].strip() for q in questions) or
            len({q['id'] for q in questions}) != len(questions)):
        parser.error('Question file must contain unique alphanumeric IDs and question text only')
    if args.question:
        if set(args.question) - {q['id'] for q in questions}:
            parser.error('Unknown question ID')
        questions = [q for q in questions if q['id'] in args.question]
    try:
        provenance = snapshot(root, interpreter, questions_path)
    except (OSError, subprocess.SubprocessError, ValueError, KeyError) as exc:
        parser.error('Cannot record dependencies/source provenance: ' + str(exc))
    version = subprocess.run([executable, '--version'], capture_output=True, text=True, timeout=10, check=True)
    output = (args.output or HERE / 'runs' / ('codex-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))).resolve()
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    write_json(output / 'questions.json', questions)
    manifest = {**provenance, 'client': version.stdout.strip(), 'native_client': 'Codex CLI',
                'model_requested': args.model, 'model_resolved': None,
                'broker': args.broker_url, 'context': args.context_url, 'writes_enabled': False,
                'transport': 'STDIO', 'question_ids': [q['id'] for q in questions],
                'configuration': 'invocation overrides only', 'evaluation_status': 'UNREVIEWED'}
    write_json(output / 'run.json', manifest)
    arguments = arguments_for(executable, args.model, interpreter, root, args.broker_url, args.context_url)
    print(f'Output: {output}', flush=True)
    print('Each question starts native Codex in an empty directory, with read-only FIWARE MCP.', flush=True)
    print(f'Model: {args.model}; same question wording and prompt as Claude; no reference answers.', flush=True)
    results = []
    for number, question in enumerate(questions, 1):
        identifier = question['id']
        prompt = prompt_for(question)
        trace = output / (identifier + '.events.jsonl')
        errors = output / (identifier + '.stderr.txt')
        (output / (identifier + '.prompt.txt')).write_text(prompt)
        print(f'[{number}/{len(questions)}] {identifier}: {question["question"]}', flush=True)
        timed_out = False
        started = time.monotonic()
        with tempfile.TemporaryDirectory(prefix='farm-codex-question-') as workspace:
            with tempfile.TemporaryFile(mode='w+') as stdin, trace.open('x') as stdout, errors.open('x') as stderr:
                trace.chmod(0o600)
                errors.chmod(0o600)
                stdin.write(prompt)
                stdin.seek(0)
                process = subprocess.Popen(arguments, stdin=stdin, stdout=stdout, stderr=stderr,
                                           cwd=workspace, start_new_session=True)
                progress = started
                try:
                    while process.poll() is None:
                        now = time.monotonic()
                        if now - started >= args.timeout:
                            timed_out = True
                            stop(process)
                            break
                        if now - progress >= 15:
                            print(f'  {identifier}: {int(now-started)} seconds, {trace.stat().st_size} trace bytes', flush=True)
                            progress = now
                        time.sleep(0.5)
                except KeyboardInterrupt:
                    stop(process)
                    raise
        try:
            parsed = summarize(trace)
            parse_error = None
        except (ValueError, TypeError, AttributeError) as exc:
            parsed = {'calls': [], 'other_tools': [], 'errors': [], 'answer': '', 'turn_completed': False}
            parse_error = str(exc)
        calls = parsed['calls']
        allowed = all(c['server'] == 'fiware_farm' and c['tool'] in READS for c in calls)
        completed = (process.returncode == 0 and not timed_out and parsed['turn_completed'] and
                     bool(calls) and allowed and not parsed['other_tools'] and not parsed['errors'] and
                     all(c['status'] == 'completed' and c['error'] is None for c in calls) and not parse_error)
        diagnostics = errors.read_text()
        blocked = not calls and 'Operation not permitted' in diagnostics
        execution = 'COMPLETED_UNREVIEWED' if completed else ('BLOCKED' if blocked else 'INCOMPLETE')
        record = {'id': identifier, 'question': question['question'], 'answer': parsed['answer'],
                  'execution_status': execution, 'correctness': 'UNREVIEWED',
                  'exit_status': process.returncode, 'timed_out': timed_out,
                  'duration_seconds': round(time.monotonic() - started, 2),
                  'native_read_calls': len(calls), 'tool_calls': calls,
                  'other_tools': parsed['other_tools'], 'errors': parsed['errors'],
                  'parse_error': parse_error, 'prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest()}
        (output / (identifier + '.answer.txt')).write_text(parsed['answer'])
        write_json(output / (identifier + '.result.json'), record)
        results.append(record)
        print(f'  {execution}: {len(calls)} native MCP calls', flush=True)
        if not completed:
            print(diagnostics[-3000:], flush=True)
            print('Stopping. Evidence retained; no fallback client, policy changes or data access.', flush=True)
            break
    write_json(output / 'results.json', results)
    print('Results saved. Correctness is UNREVIEWED until compared with reference answers and tool data.', flush=True)
    return 0 if len(results) == len(questions) and all(r['execution_status'] == 'COMPLETED_UNREVIEWED' for r in results) else 1


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
