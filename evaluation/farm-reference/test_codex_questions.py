"""Offline launcher and archive tests. No broker or model calls."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import tomllib
import unittest
from unittest import mock

import archive_experiment as archive
import run_codex_questions as runner


class CodexQuestionTests(unittest.TestCase):
    def test_prompt_has_question_only_and_matches_claude_contract(self):
        prompt = runner.prompt_for({'id': 'F03', 'question': 'Which Animals have a heart rate greater than 56?'})
        self.assertTrue(prompt.startswith('Answer the following question in English using only native FIWARE MCP read tools.'))
        self.assertTrue(prompt.endswith('F03: Which Animals have a heart rate greater than 56?\n'))
        self.assertNotIn('cow005', prompt)
        self.assertNotIn('reference-answers', prompt)

    def test_scoped_configuration_is_valid_toml_and_read_only(self):
        arguments = runner.arguments_for('codex', 'gpt-6.1-sol', Path('/repo/.venv/bin/python'),
                                         Path('/repo'), 'http://127.0.0.1:1126', 'http://context/user-context.jsonld')
        settings = {}
        for position, token in enumerate(arguments):
            if token == '-c':
                item = arguments[position + 1]
                tomllib.loads(item)
                key, value = item.split('=', 1)
                settings[key] = json.loads(value)
        self.assertIn('--ignore-user-config', arguments)
        self.assertEqual(arguments[arguments.index('--sandbox') + 1], 'read-only')
        self.assertEqual(settings['mcp_servers.fiware_farm.command'], '/repo/.venv/bin/python')
        self.assertEqual(settings['mcp_servers.fiware_farm.env.NGSI_LD_ENABLE_WRITES'], 'false')
        self.assertEqual(settings['mcp_servers.fiware_farm.enabled_tools'], list(runner.READS))
        self.assertTrue(settings['mcp_servers.fiware_farm.required'])
        self.assertFalse(settings['features.shell_tool'])
        self.assertFalse(any('bypass' in a for a in arguments))

    def test_native_trace_keeps_call_and_last_answer(self):
        events = [
            {'type': 'item.completed', 'item': {'id': 'one', 'type': 'mcp_tool_call',
             'server': 'fiware_farm', 'tool': 'get_entity', 'arguments': {'entity_id': 'urn:missing'},
             'status': 'completed', 'error': None, 'result': {'structured_content': {'ok': False, 'status': 404}}}},
            {'type': 'item.completed', 'item': {'type': 'agent_message', 'text': 'Target absent.'}},
            {'type': 'turn.completed'},
        ]
        with tempfile.TemporaryDirectory() as directory:
            trace = Path(directory) / 'events.jsonl'
            trace.write_text('\n'.join(json.dumps(e) for e in events))
            summary = runner.summarize(trace)
            self.assertTrue(summary['turn_completed'])
            self.assertEqual(summary['answer'], 'Target absent.')
            self.assertEqual(summary['calls'][0]['tool'], 'get_entity')
            self.assertEqual(summary['other_tools'], [])
            self.assertEqual(summary['errors'], [])

    def test_file_or_shell_access_and_failed_turn_are_retained(self):
        events = [
            {'type': 'item.completed', 'item': {'type': 'command_execution', 'command': 'cat fixture'}},
            {'type': 'turn.failed', 'error': {'message': 'denied'}},
        ]
        with tempfile.TemporaryDirectory() as directory:
            trace = Path(directory) / 'events.jsonl'
            trace.write_text('\n'.join(json.dumps(e) for e in events))
            summary = runner.summarize(trace)
            self.assertFalse(summary['turn_completed'])
            self.assertEqual(len(summary['other_tools']), 1)
            self.assertEqual(len(summary['errors']), 1)

    def test_cli_permission_failure_stops_and_saves_blocker(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'server.py').touch()
            (root / 'python').touch()
            questions = root / 'questions.json'
            questions.write_text('[{"id":"F01","question":"Explore the farm."},{"id":"F02","question":"List attributes."}]')
            fake = root / 'codex'
            fake.write_text('#!/bin/sh\nif [ "$1" = "--version" ]; then echo simulated-cli; exit 0; fi\necho "Operation not permitted" >&2\nexit 1\n')
            fake.chmod(0o700)
            output = root / 'run'
            with mock.patch.object(runner, 'snapshot', return_value={}), \
                 contextlib.redirect_stdout(io.StringIO()):
                status = runner.main(['--repo-root', str(root), '--python', str(root / 'python'),
                                      '--codex', str(fake), '--questions', str(questions),
                                      '--broker-url', 'http://127.0.0.1:1126',
                                      '--context-url', 'http://context/user-context.jsonld',
                                      '--output', str(output)])
            self.assertEqual(status, 1)
            records = json.loads((output / 'results.json').read_text())
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]['execution_status'], 'BLOCKED')
            self.assertEqual(records[0]['native_read_calls'], 0)
            self.assertFalse((output / 'F02.events.jsonl').exists())

    def test_archive_removes_credentials_and_local_paths(self):
        root = Path('/example/repository')
        value = {'Authorization': 'secret', 'data': {'refresh_token': 'secret2',
                 'message': '/example/repository/server.py', 'count': 47}}
        cleaned = archive.clean(value, root)
        self.assertNotIn('Authorization', cleaned)
        self.assertNotIn('refresh_token', cleaned['data'])
        self.assertEqual(cleaned['data']['message'], '$REPO/server.py')
        self.assertEqual(cleaned['data']['count'], 47)

    def test_archive_preserves_codex_structured_broker_error(self):
        events = [{'type': 'item.completed', 'item': {'id': 'one', 'type': 'mcp_tool_call',
                   'server': 'fiware_farm', 'tool': 'get_entity', 'arguments': {'entity_id': 'urn:missing'},
                   'status': 'completed', 'error': None,
                   'result': {'structured_content': {'ok': False, 'status': 404}}}}]
        calls = archive.collect_calls(events, {})
        self.assertEqual(calls[0]['result'], {'ok': False, 'status': 404})

    def test_archive_preserves_claude_broker_reply(self):
        events = [{'type': 'user', 'message': {'content': [
            {'type': 'tool_result', 'tool_use_id': 'one', 'content': '{"ok":true,"status":200,"data":[]}'}]}}]
        record = {'tool_calls': [{'id': 'one', 'tool': 'mcp__fiware_farm__query_entities',
                                  'arguments': {'type': 'Animal'}}]}
        calls = archive.collect_calls(events, record)
        self.assertEqual(calls[0]['tool'], 'query_entities')
        self.assertEqual(calls[0]['result']['status'], 200)


if __name__ == '__main__':
    unittest.main()
