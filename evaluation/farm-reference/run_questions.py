"""Run English questions through native Claude Code and retain review evidence.

This launcher never reads reference answers. It uses only the question file and
an explicitly configured, read-only local FIWARE MCP server.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
READS = ('get_broker_info', 'get_types', 'get_attributes', 'get_entity', 'query_entities')


def python_executable(path):
    # Preserve venv/bin/python: resolving its symlink selects the base interpreter
    # and loses the virtual environment's installed dependencies.
    return Path(os.path.abspath(path.expanduser()))


def write_json(path, value):
    with path.open('x', encoding='utf-8') as stream:
        path.chmod(0o600)
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write('\n')


def summarize(trace):
    events = []
    for line in trace.read_text(encoding='utf-8').splitlines():
        if line.strip():
            events.append(json.loads(line))
    calls = []
    for event in events:
        if event.get('type') == 'assistant':
            for block in event.get('message', {}).get('content', []):
                if block.get('type') == 'tool_use':
                    calls.append({'id': block.get('id'), 'tool': block.get('name'),
                                  'arguments': block.get('input')})
    final = next((e for e in reversed(events) if e.get('type') == 'result'), {})
    return final, calls


def stop(process):
    os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', type=Path, default=HERE.parent.parent)
    parser.add_argument('--questions', type=Path, default=HERE / 'questions-only.json')
    parser.add_argument('--question', action='append', help='question ID, repeatable; default: all')
    parser.add_argument('--broker-url', required=True, help='explicit NGSI-LD broker base URL')
    parser.add_argument('--context-url', required=True, help='JSON-LD context URL reachable by broker')
    parser.add_argument('--python', dest='python_path', type=Path, help='Python with project dependencies')
    parser.add_argument('--claude', default='claude', help='native Claude Code executable')
    parser.add_argument('--model', help='optional Claude model name; otherwise client default')
    parser.add_argument('--timeout', type=int, default=300, help='seconds per question, default 300')
    parser.add_argument('--output', type=Path, help='new output directory; existing paths are refused')
    args = parser.parse_args(argv)
    if args.timeout < 1:
        parser.error('--timeout must be positive')
    for label, address in [('broker', args.broker_url), ('context', args.context_url)]:
        parsed = urlsplit(address)
        if (parsed.scheme not in ('http', 'https') or not parsed.hostname or
                parsed.username or parsed.password or parsed.fragment or parsed.query):
            parser.error(f'{label} URL must be HTTP(S), without credentials, query or fragment')
    root = args.repo_root.resolve()
    interpreter = python_executable(args.python_path or root / '.venv/bin/python')
    executable = shutil.which(args.claude)
    if not executable or not interpreter.is_file() or not (root / 'server.py').is_file():
        parser.error('Require Claude Code, server.py and project Python; use --repo-root/--python if needed')
    try:
        check = subprocess.run([str(interpreter), '-c', 'import mcp, httpx'],
                               capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired) as exc:
        parser.error(f'Cannot check project Python {interpreter}: {exc}')
    if check.returncode:
        parser.error(f'Project Python {interpreter} cannot import MCP dependencies:\n{check.stderr.strip()}')
    questions = json.loads(args.questions.read_text(encoding='utf-8'))
    if (not isinstance(questions, list) or not questions or
            any(not isinstance(q, dict) or set(q) != {'id', 'question'} or
                not isinstance(q['id'], str) or not q['id'].isalnum() or
                not isinstance(q['question'], str) or not q['question'].strip() for q in questions) or
            len({q['id'] for q in questions}) != len(questions)):
        parser.error('Question file must contain unique alphanumeric IDs and question text only')
    if args.question:
        unknown = set(args.question) - {q['id'] for q in questions}
        if unknown:
            parser.error(f'Unknown question IDs: {sorted(unknown)}')
        questions = [q for q in questions if q['id'] in args.question]
    output = (args.output or HERE / 'runs' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')).resolve()
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    write_json(output / 'questions.json', questions)
    version = subprocess.run([executable, '--version'], capture_output=True, text=True, timeout=10)
    write_json(output / 'run.json', {'client': version.stdout.strip(), 'model_requested': args.model,
               'broker': args.broker_url, 'context': args.context_url, 'writes_enabled': False,
               'python': str(interpreter),
               'transport': 'STDIO', 'question_ids': [q['id'] for q in questions],
               'evaluation_status': 'UNREVIEWED'})
    results = []
    print(f'Output: {output}', flush=True)
    print('Each question uses a fresh native Claude session and your normal account.', flush=True)
    with tempfile.TemporaryDirectory(prefix='farm-native-questions-') as temporary:
        workspace = Path(temporary)
        config = workspace / 'mcp.json'
        write_json(config, {'mcpServers': {'fiware_farm': {
            'command': str(interpreter), 'args': [str(root / 'server.py')],
            'env': {'NGSI_LD_BROKER_URL': args.broker_url,
                    'NGSI_LD_CONTEXT_URL': args.context_url,
                    'NGSI_LD_CONTEXT_URLS': json.dumps([args.context_url]),
                    'NGSI_LD_ENABLE_WRITES': 'false', 'NGSI_LD_HEADERS': '{}'}}}})
        arguments = [executable, '-p', '--verbose', '--output-format', 'stream-json',
                     '--strict-mcp-config', '--mcp-config', str(config), '--tools', '',
                     '--allowedTools', ','.join('mcp__fiware_farm__' + n for n in READS),
                     '--disallowedTools', 'mcp__fiware_farm__create_entity,mcp__fiware_farm__update_entity',
                     '--disable-slash-commands', '--no-session-persistence', '--setting-sources', '']
        if args.model:
            arguments += ['--model', args.model]
        for number, question in enumerate(questions, 1):
            identifier = question['id']
            prompt = ('Answer the following question in English using only native FIWARE MCP read tools. '
                      'Do not read files, use shell or web tools, modify broker data, or invent missing facts. '
                      'Discover the necessary types and attributes from the broker. Follow actual relationship '
                      'targets and paginate where needed. Include exact entity IDs, observed values and units, '
                      'query arguments, and relevant errors or limitations. Distinguish facts from assumptions.\n\n'
                      + identifier + ': ' + question['question'] + '\n')
            trace = output / (identifier + '.events.jsonl')
            errors = output / (identifier + '.stderr.txt')
            (output / (identifier + '.prompt.txt')).write_text(prompt, encoding='utf-8')
            print(f'[{number}/{len(questions)}] {identifier}: {question["question"]}', flush=True)
            timed_out = False
            started = time.monotonic()
            with tempfile.TemporaryFile(mode='w+', encoding='utf-8') as stdin:
                stdin.write(prompt)
                stdin.seek(0)
                with trace.open('x') as stdout, errors.open('x') as stderr:
                    trace.chmod(0o600)
                    errors.chmod(0o600)
                    process = subprocess.Popen(arguments, stdin=stdin, stdout=stdout, stderr=stderr,
                                               cwd=workspace, start_new_session=True,
                                               env={**os.environ, 'ENABLE_TOOL_SEARCH': 'false'})
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
                final, calls = summarize(trace)
                parse_error = None
            except (ValueError, TypeError, AttributeError) as exc:
                final, calls, parse_error = {}, [], str(exc)
            native = [c for c in calls if c['tool'] in {'mcp__fiware_farm__' + n for n in READS}]
            completed = (process.returncode == 0 and not timed_out and bool(final) and
                         not final.get('is_error') and not final.get('permission_denials') and
                         bool(native) and len(native) == len(calls) and not parse_error)
            answer = final.get('result', '')
            (output / (identifier + '.answer.txt')).write_text(answer, encoding='utf-8')
            record = {'id': identifier, 'question': question['question'], 'answer': answer,
                      'execution_status': 'COMPLETED_UNREVIEWED' if completed else 'INCOMPLETE',
                      'correctness': 'UNREVIEWED', 'exit_status': process.returncode,
                      'timed_out': timed_out, 'duration_seconds': round(time.monotonic()-started, 2),
                      'native_read_calls': len(native), 'tool_calls': calls,
                      'permission_denials': final.get('permission_denials', []), 'parse_error': parse_error}
            write_json(output / (identifier + '.result.json'), record)
            results.append(record)
            print(f'  {record["execution_status"]}: {len(native)} native read calls', flush=True)
            if not completed:
                print(f'  Stopping. Inspect {errors} and {trace} before retrying.', flush=True)
                break
    write_json(output / 'results.json', results)
    print('Results saved. Correctness requires comparison with reference-answers.json.', flush=True)
    return 0 if len(results) == len(questions) and all(r['execution_status'] == 'COMPLETED_UNREVIEWED' for r in results) else 1


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
