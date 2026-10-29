"""Compare archived native-client experiments without grading prose automatically."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def load(directory):
    manifest = json.loads((directory / 'manifest.json').read_text())
    questions = json.loads((directory / 'questions.json').read_text())
    prompts = json.loads((directory / 'prompts.json').read_text())
    answers = json.loads((directory / 'answers.json').read_text())
    calls = json.loads((directory / 'mcp-calls.json').read_text())
    for prompt in prompts:
        if hashlib.sha256(prompt['text'].encode()).hexdigest() != prompt['sha256']:
            raise ValueError('Prompt hash mismatch: ' + prompt['id'])
    if manifest['native_mcp_calls'] != len(calls):
        raise ValueError('Manifest/native call count mismatch')
    if len({q['id'] for q in questions}) != len(questions):
        raise ValueError('Duplicate question IDs')
    if len({a['id'] for a in answers}) != len(answers):
        raise ValueError('Duplicate answer IDs')
    if any(a['id'] not in {q['id'] for q in questions} for a in answers):
        raise ValueError('Answer outside selected questions')
    return {'manifest': manifest, 'questions': questions, 'prompts': prompts,
            'answers': {a['id']: a for a in answers}, 'calls': calls}


def compare(baseline, candidate):
    a, b = baseline['manifest'], candidate['manifest']
    mismatches = []
    if baseline['questions'] != candidate['questions']:
        mismatches.append('questions')
    if baseline['prompts'] != candidate['prompts']:
        mismatches.append('prompts')
    for key in ('source_revision', 'payload_sha256', 'context_sha256'):
        if a['provenance']['dataset'][key] != b['provenance']['dataset'][key]:
            mismatches.append('dataset.' + key)
    if a['provenance']['mcp']['source_sha256'] != b['provenance']['mcp']['source_sha256']:
        mismatches.append('mcp.source_sha256')
    if mismatches:
        raise ValueError('Controlled comparison refused; differing ' + ', '.join(mismatches))
    rows = []
    for question in baseline['questions']:
        identifier = question['id']
        left = baseline['answers'].get(identifier, {})
        right = candidate['answers'].get(identifier, {})
        # An unreviewed archive never becomes PASS merely by having an answer.
        def classification(archive, answer):
            if not answer:
                return 'NOT_RUN'
            return answer.get('correctness', 'UNREVIEWED') if archive['manifest']['evaluation_status'] == 'REVIEWED' else 'UNREVIEWED'
        rows.append({'id': identifier, 'baseline': classification(baseline, left),
                     'candidate': classification(candidate, right),
                     'baseline_calls': left.get('native_calls', 0),
                     'candidate_calls': right.get('native_calls', 0)})
    return {'compatibility': 'MATCH', 'question_count': len(rows),
            'grading': 'Existing reviewed classifications only; no automatic semantic correctness judgment.',
            'baseline': {'run_id': a['run_id'], 'client': a['client_family'],
                         'classifications': dict(Counter(r['baseline'] for r in rows)),
                         'native_mcp_calls': a['native_mcp_calls'],
                         'question_duration_seconds': round(sum(x['duration_seconds'] for x in baseline['answers'].values()), 2)},
            'candidate': {'run_id': b['run_id'], 'client': b['client_family'],
                          'classifications': dict(Counter(r['candidate'] for r in rows)),
                          'native_mcp_calls': b['native_mcp_calls'],
                          'question_duration_seconds': round(sum(x['duration_seconds'] for x in candidate['answers'].values()), 2)},
            'questions': rows,
            'limitation': 'Single runs, client/model defaults and provenance capture timing can differ; inspect manifests.'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline', type=Path)
    parser.add_argument('candidate', type=Path)
    parser.add_argument('--output', type=Path, help='optional new JSON file; existing files refused')
    args = parser.parse_args(argv)
    try:
        result = compare(load(args.baseline), load(args.candidate))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(2, str(exc) + '\n')
    content = json.dumps(result, indent=2) + '\n'
    if args.output:
        with args.output.open('x') as stream:
            stream.write(content)
    else:
        print(content, end='')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
