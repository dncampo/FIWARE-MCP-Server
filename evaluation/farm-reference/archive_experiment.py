"""Create a dated, portable experiment record from saved native-client evidence.

Raw client events stay local. Export only questions, answers, MCP call data and
provenance, excluding client account/session metadata and reasoning blocks.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys

from run_codex_questions import snapshot
from run_questions import python_executable, write_json

HERE = Path(__file__).resolve().parent


def clean(value, root):
    if isinstance(value, dict):
        return {k: clean(v, root) for k, v in value.items()
                if k.lower().replace('-', '_') not in
                {'authorization', 'proxy_authorization', 'cookie', 'set_cookie',
                 'access_token', 'refresh_token', 'api_key', 'client_secret'}}
    if isinstance(value, list):
        return [clean(v, root) for v in value]
    if isinstance(value, str):
        return value.replace(str(root), '$REPO').replace(str(Path.home()), '$HOME')
    return value


def content_json(content):
    if isinstance(content, list):
        content = ''.join(b.get('text', '') for b in content if b.get('type') == 'text')
    return json.loads(content) if isinstance(content, str) else content


def collect_calls(events, record):
    if any(e.get('type') == 'item.completed' for e in events):
        calls = []
        for event in events:
            item = event.get('item', {})
            if event.get('type') != 'item.completed' or item.get('type') != 'mcp_tool_call':
                continue
            result = item.get('result')
            if isinstance(result, dict):
                result = result.get('structured_content', result.get('structuredContent')) or content_json(result.get('content'))
            calls.append({'id': item.get('id'), 'server': item.get('server'),
                          'tool': item.get('tool'), 'arguments': item.get('arguments'),
                          'framework_status': item.get('status'), 'framework_error': item.get('error'),
                          'result': result})
        return calls
    if any(e.get('type') == 'tool_use' for e in events):
        calls = []
        for call in record['tool_calls']:
            calls.append({
                'id': call['id'],
                'server': call.get('server', 'fiware_farm'),
                'tool': call['tool'],
                'arguments': call['arguments'],
                'framework_status': call.get('status', 'completed'),
                'framework_error': call.get('error', False),
                'result': call.get('result')
            })
        return calls
    responses = {}
    for event in events:
        if event.get('type') == 'user':
            for block in event.get('message', {}).get('content', []):
                if block.get('type') == 'tool_result':
                    responses[block['tool_use_id']] = block
    calls = []
    for call in record['tool_calls']:
        response = responses.get(call['id'], {})
        calls.append({'id': call['id'], 'server': 'fiware_farm',
                      'tool': call['tool'].split('__')[-1], 'arguments': call['arguments'],
                      'framework_status': 'completed' if response else 'missing_result',
                      'framework_error': response.get('is_error', False),
                      'result': content_json(response.get('content'))})
    return calls


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--repo-root', type=Path, default=HERE.parent.parent)
    parser.add_argument('--python', dest='python_path', type=Path)
    parser.add_argument('--review', type=Path, help='review JSON with matching per-trace hashes')
    parser.add_argument('--output', type=Path, help='new experiment directory, never overwritten')
    args = parser.parse_args(argv)
    root = args.repo_root.resolve()
    run = args.run.resolve()
    records = json.loads((run / 'results.json').read_text())
    selected = json.loads((run / 'questions.json').read_text())
    metadata = json.loads((run / 'run.json').read_text())
    is_codex = metadata.get('native_client') == 'Codex CLI'
    is_hermes = metadata.get('native_client') == 'Hermes Agent'
    client = 'hermes' if is_hermes else ('codex' if is_codex else 'claude')
    recorded = re.search(r'(\d{8}T\d{12}Z)', run.name)
    if not recorded:
        parser.error('Run folder must contain its UTC timestamp for a dated archive')
    date = datetime.strptime(recorded.group(1), '%Y%m%dT%H%M%S%fZ').date().isoformat()
    output = args.output or root / 'experiments/smart-farming' / (date + '-' + client + '-' + recorded.group(1))
    review_by_id = {}
    if args.review:
        review = json.loads(args.review.read_text())
        if Path(review['run']).name != run.name:
            parser.error('Review belongs to a different run')
        review_by_id = {r['id']: r for r in review['reviews']}
        if set(review_by_id) != {r['id'] for r in records}:
            parser.error('Review and execution question IDs differ')
        for identifier, reviewed in review_by_id.items():
            actual_hash = hashlib.sha256((run / (identifier + '.events.jsonl')).read_bytes()).hexdigest()
            if reviewed['events_sha256'] != actual_hash:
                parser.error('Trace changed since review: ' + identifier)
    if is_codex or is_hermes:
        provenance = {k: metadata[k] for k in ('captured_at_utc', 'platform', 'dependencies', 'mcp', 'dataset', 'questions_sha256')}
        provenance['capture_note'] = f'Captured before this native {metadata.get("native_client")} run.'
    else:
        provenance = snapshot(root, python_executable(args.python_path or root / '.venv/bin/python'),
                              root / 'evaluation/farm-reference/questions-only.json')
        provenance['capture_note'] = ('Source hashes and dependencies captured at archive time. '
                                      'They were not independently recorded during the historical Claude run.')
    answers, calls, prompts, model_names, client_versions, broker_versions = [], [], [], set(), set(), set()
    for record in records:
        identifier = record['id']
        event_file = run / (identifier + '.events.jsonl')
        events = [json.loads(line) for line in event_file.read_text().splitlines() if line.strip()]
        for event in events:
            if event.get('type') == 'system' and event.get('subtype') == 'init':
                model_names.add(event.get('model'))
                client_versions.add(event.get('claude_code_version'))
        traced = collect_calls(events, record)
        if len(traced) != record['native_read_calls']:
            parser.error('Saved trace and summary call counts differ: ' + identifier)
        for call in traced:
            if call['server'] != 'fiware_farm':
                parser.error('Unexpected MCP provider')
            calls.append({'question_id': identifier, **call})
            if call['tool'] == 'get_broker_info' and isinstance(call.get('result'), dict):
                version = call['result'].get('data', {}).get('version_probe', {}).get('data')
                if isinstance(version, dict) and version.get('orionld version'):
                    broker_versions.add('Orion-LD ' + version['orionld version'])
        prompt_file = run / (identifier + '.prompt.txt')
        prompts.append({'id': identifier, 'text': prompt_file.read_text(),
                        'sha256': hashlib.sha256(prompt_file.read_bytes()).hexdigest()})
        answers.append({'id': identifier, 'question': record['question'], 'answer': record['answer'],
                        'execution_status': record['execution_status'],
                        'correctness': review_by_id.get(identifier, {}).get('classification', 'UNREVIEWED'),
                        'review_note': review_by_id.get(identifier, {}).get('observation'),
                        'native_calls': len(traced), 'duration_seconds': record['duration_seconds'],
                        'exit_status': record['exit_status'], 'timed_out': record['timed_out'],
                        'source_trace_sha256': hashlib.sha256(event_file.read_bytes()).hexdigest()})
    subset = {q['id']: q['question'] for q in selected}
    if any(subset.get(r['id']) != r['question'] for r in records):
        parser.error('Question text differs between selected bank and saved execution')
    manifest = {'experiment': 'smart-farming-native-mcp', 'experiment_date_utc': date,
                'run_id': run.name, 'client_family': client,
                'client_version': sorted(v for v in client_versions if v) or metadata['client'],
                'model_requested': metadata.get('model_requested'),
                'model_observed_in_events': sorted(m for m in model_names if m) or None,
                'model_note': 'Codex resolved model revision is not separately identified by these events.' if is_codex else None,
                'broker_url': metadata['broker'], 'context_url': metadata['context'],
                'broker_version_observed': sorted(broker_versions) or None,
                'transport': 'STDIO', 'writes_enabled': False,
                'evaluation_status': 'REVIEWED' if review_by_id else 'UNREVIEWED',
                'selected_questions': len(selected), 'attempted_questions': len(records),
                'native_mcp_calls': len(calls),
                'classifications': dict(__import__('collections').Counter(a['correctness'] for a in answers)),
                'questions_sha256': hashlib.sha256((run / 'questions.json').read_bytes()).hexdigest(),
                'provenance': provenance,
                'evidence_note': 'Curated native MCP calls, returned data and answers. Raw client events and stderr remain local.'}
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / 'manifest.json', clean(manifest, root))
    write_json(output / 'questions.json', selected)
    write_json(output / 'prompts.json', prompts)
    write_json(output / 'answers.json', clean(answers, root))
    write_json(output / 'mcp-calls.json', clean(calls, root))
    if review_by_id:
        write_json(output / 'review.json', {'reviews': list(review_by_id.values())})
    print(f'Experiment archive: {output}')
    print(f'{len(records)} attempted questions, {len(calls)} native MCP calls; ' + manifest['evaluation_status'])
    print('Review curated artifacts before publishing. No commit or push was performed.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
