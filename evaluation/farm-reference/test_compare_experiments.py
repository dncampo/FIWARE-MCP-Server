"""Offline comparison safeguards, without native client or broker execution."""
import unittest

import compare_experiments as comparison


def archive():
    return {'manifest': {'native_mcp_calls': 1, 'run_id': 'example', 'client_family': 'example',
                         'evaluation_status': 'REVIEWED',
                         'provenance': {'dataset': {'source_revision': 'source', 'payload_sha256': 'payload',
                                                    'context_sha256': 'context'},
                                        'mcp': {'source_sha256': {'server.py': 'source'}}}},
            'questions': [{'id': 'F01', 'question': 'Explore.'}],
            'prompts': [{'id': 'F01', 'text': 'Explore.', 'sha256': 'example'}],
            'answers': {'F01': {'correctness': 'PASS', 'native_calls': 1, 'duration_seconds': 1}}, 'calls': [{}]}


class ComparisonTests(unittest.TestCase):
    def test_matching_archives_keep_reviewed_verdicts(self):
        left, right = archive(), archive()
        right['answers']['F01']['correctness'] = 'PARTIAL'
        result = comparison.compare(left, right)
        self.assertEqual(result['compatibility'], 'MATCH')
        self.assertEqual(result['candidate']['classifications'], {'PARTIAL': 1})

    def test_unreviewed_archive_is_never_promoted_to_pass(self):
        left, right = archive(), archive()
        right['manifest']['evaluation_status'] = 'UNREVIEWED'
        self.assertEqual(comparison.compare(left, right)['questions'][0]['candidate'], 'UNREVIEWED')

    def test_different_dataset_is_refused(self):
        right = archive()
        right['manifest']['provenance']['dataset']['payload_sha256'] = 'different'
        with self.assertRaisesRegex(ValueError, 'dataset.payload_sha256'):
            comparison.compare(archive(), right)

    def test_different_prompt_is_refused(self):
        right = archive()
        right['prompts'][0]['text'] = 'An easier question.'
        with self.assertRaisesRegex(ValueError, 'prompts'):
            comparison.compare(archive(), right)

    def test_changed_server_is_not_called_a_controlled_comparison(self):
        right = archive()
        right['manifest']['provenance']['mcp']['source_sha256']['server.py'] = 'changed'
        with self.assertRaisesRegex(ValueError, 'mcp.source_sha256'):
            comparison.compare(archive(), right)

    def test_missing_answer_is_not_run(self):
        right = archive()
        right['answers'] = {}
        self.assertEqual(comparison.compare(archive(), right)['questions'][0]['candidate'], 'NOT_RUN')


if __name__ == '__main__':
    unittest.main()
