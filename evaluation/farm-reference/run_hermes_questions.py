"""Evaluate the existing question bank through native Hermes CLI with read-only MCP."""
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


def summarize_hermes_events(trace_path):
    events = [json.loads(line) for line in trace_path.read_text().splitlines() if line.strip()]
    calls = []
    other_tools = []
    errors = []
    text_chunks = []
    final_answer = ""
    model_name = "gemini-3.6-flash"
    
    pending_tool_calls = {} # tool_use_id / name -> call object

    for event in events:
        etype = event.get('type')
        if etype == 'system' and event.get('subtype') == 'init':
            model_name = event.get('model', model_name)
        elif etype == 'tool_use':
            name = event.get('name', '')
            raw_input = event.get('input', {})
            tool_short = name.split('__')[-1]
            if tool_short in READS:
                call_obj = {
                    'id': f"call_{len(calls)+1}",
                    'server': 'fiware_farm',
                    'tool': tool_short,
                    'arguments': raw_input,
                    'status': 'pending',
                    'error': None,
                    'result': None
                }
                pending_tool_calls[name] = call_obj
                calls.append(call_obj)
            elif name in ('tool_call', 'tool_describe') or tool_short in ('list_resources', 'read_resource', 'list_prompts', 'get_prompt'):
                pass  # Internal framework / MCP metadata helpers
            else:
                other_tools.append(event)
        elif etype == 'tool_result':
            name = event.get('name', '')
            output_raw = event.get('output', '')
            if name in pending_tool_calls:
                call_obj = pending_tool_calls[name]
                call_obj['status'] = 'completed' if not event.get('is_error') else 'error'
                call_obj['error'] = event.get('is_error', False)
                try:
                    # output is JSON string with {"result": "{\"ok\": true, ...}"}
                    outer = json.loads(output_raw) if isinstance(output_raw, str) else output_raw
                    if isinstance(outer, dict) and 'result' in outer:
                        call_obj['result'] = json.loads(outer['result']) if isinstance(outer['result'], str) else outer['result']
                    else:
                        call_obj['result'] = outer
                except Exception:
                    call_obj['result'] = output_raw
        elif etype == 'text':
            text_chunks.append(event.get('text', ''))
        elif etype == 'result':
            final_answer = event.get('text', '')
            if event.get('error'):
                errors.append(event['error'])

    if not final_answer and text_chunks:
        final_answer = "".join(text_chunks)

    turn_completed = any(e.get('type') == 'result' and e.get('exit_code') == 0 for e in events)

    return {
        'model': model_name,
        'calls': calls,
        'other_tools': other_tools,
        'errors': errors,
        'answer': final_answer,
        'turn_completed': turn_completed
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', type=Path, default=HERE.parent.parent)
    parser.add_argument('--questions', type=Path, default=HERE / 'questions-only.json')
    parser.add_argument('--question', action='append', help='question ID, repeatable; default all 16')
    parser.add_argument('--broker-url', required=True)
    parser.add_argument('--context-url', required=True)
    parser.add_argument('--model', default='gemini-3.6-flash', help='explicit model, recorded in manifest')
    parser.add_argument('--profile', default='fiware-eval', help='Hermes profile name')
    parser.add_argument('--python', dest='python_path', type=Path)
    parser.add_argument('--hermes', default='hermes', help='native Hermes executable')
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
    executable = shutil.which(args.hermes)
    if not executable or not interpreter.is_file() or not (root / 'server.py').is_file():
        parser.error('Require Hermes CLI, server.py and the project Python environment')
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
    output = (args.output or HERE / 'runs' / ('hermes-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))).resolve()
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    (output / 'questions.json').write_text(json.dumps(questions, indent=2))
    manifest = {**provenance, 'client': version.stdout.strip(), 'native_client': 'Hermes Agent',
                'model_requested': args.model, 'model_resolved': args.model,
                'profile': args.profile,
                'broker': args.broker_url, 'context': args.context_url, 'writes_enabled': False,
                'transport': 'STDIO', 'question_ids': [q['id'] for q in questions],
                'configuration': f'profile {args.profile}', 'evaluation_status': 'UNREVIEWED'}
    (output / 'run.json').write_text(json.dumps(manifest, indent=2))

    print(f'Output: {output}', flush=True)
    print(f'Each question starts native Hermes session in profile {args.profile}, with read-only FIWARE MCP.', flush=True)
    print(f'Model: {args.model}; same question wording and prompt as Claude/Codex; no reference answers.', flush=True)
    results = []
    
    for number, question in enumerate(questions, 1):
        identifier = question['id']
        res_file = output / (identifier + '.result.json')
        if res_file.exists():
            try:
                prev_rec = json.loads(res_file.read_text())
                if prev_rec.get('execution_status') == 'COMPLETED_UNREVIEWED':
                    print(f'[{number}/{len(questions)}] {identifier}: (reusing completed run)', flush=True)
                    results.append(prev_rec)
                    continue
            except Exception:
                pass
        identifier = question['id']
        prompt = prompt_for(question)
        trace = output / (identifier + '.events.jsonl')
        errors = output / (identifier + '.stderr.txt')
        prompt_file = output / (identifier + '.prompt.txt')
        prompt_file.write_text(prompt)
        print(f'[{number}/{len(questions)}] {identifier}: {question["question"]}', flush=True)
        timed_out = False
        started = time.monotonic()
        
        # Build Hermes command
        cmd = [
            executable,
            '-p', args.profile,
            'chat',
            '--query-file', str(prompt_file),
            '--format', 'stream-json',
            '--ignore-rules',
            '--accept-hooks'
        ]
        
        with tempfile.TemporaryDirectory(prefix='farm-hermes-question-') as workspace:
            with trace.open('w') as stdout, errors.open('w') as stderr:
                trace.chmod(0o600)
                errors.chmod(0o600)
                process = subprocess.Popen(cmd, stdout=stdout, stderr=stderr,
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
            parsed = summarize_hermes_events(trace)
            parse_error = None
        except (ValueError, TypeError, AttributeError) as exc:
            parsed = {'calls': [], 'other_tools': [], 'errors': [], 'answer': '', 'turn_completed': False, 'model': args.model}
            parse_error = str(exc)
            
        calls = parsed['calls']
        allowed = all(c['server'] == 'fiware_farm' and c['tool'] in READS for c in calls)
        completed = (process.returncode == 0 and not timed_out and parsed['turn_completed'] and
                     bool(calls) and allowed and not parsed['other_tools'] and not parsed['errors'] and
                     all(c['status'] == 'completed' and not c['error'] for c in calls) and not parse_error)
        diagnostics = errors.read_text()
        blocked = not calls and ('Operation not permitted' in diagnostics or 'credentials or agent init failed' in diagnostics)
        execution = 'COMPLETED_UNREVIEWED' if completed else ('BLOCKED' if blocked else 'INCOMPLETE')
        record = {'id': identifier, 'question': question['question'], 'answer': parsed['answer'],
                  'execution_status': execution, 'correctness': 'UNREVIEWED',
                  'exit_status': process.returncode, 'timed_out': timed_out,
                  'duration_seconds': round(time.monotonic() - started, 2),
                  'native_read_calls': len(calls), 'tool_calls': calls,
                  'other_tools': parsed['other_tools'], 'errors': parsed['errors'],
                  'parse_error': parse_error, 'prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest()}
        (output / (identifier + '.answer.txt')).write_text(parsed['answer'])
        (output / (identifier + '.result.json')).write_text(json.dumps(record, indent=2))
        results.append(record)
        print(f'  {execution}: {len(calls)} native MCP calls', flush=True)
        if not completed:
            print(diagnostics[-3000:], flush=True)
            print('Stopping. Evidence retained; no fallback client, policy changes or data access.', flush=True)
            break
            
    (output / 'results.json').write_text(json.dumps(results, indent=2))
    print('Results saved. Correctness is UNREVIEWED until compared with reference answers and tool data.', flush=True)
    return 0 if len(results) == len(questions) and all(r['execution_status'] == 'COMPLETED_UNREVIEWED' for r in results) else 1


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
