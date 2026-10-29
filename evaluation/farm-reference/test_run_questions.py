"""Offline tests for native-client launcher safeguards; no LLM calls."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import run_questions as runner


class LauncherTests(unittest.TestCase):
    def test_virtual_environment_symlink_is_not_dereferenced(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / 'base-python'
            target.touch()
            interpreter = root / '.venv/bin/python'
            interpreter.parent.mkdir(parents=True)
            interpreter.symlink_to(target)
            selected = runner.python_executable(interpreter)
            self.assertEqual(selected.name, 'python')
            self.assertEqual(selected.parent.name, 'bin')
            self.assertEqual(selected.parent.parent.name, '.venv')
            self.assertNotEqual(selected, target.resolve())

    def test_actual_virtual_environment_prefix_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            environment = Path(directory) / 'venv'
            subprocess.run([sys.executable, '-m', 'venv', '--without-pip', str(environment)],
                           check=True, capture_output=True, timeout=30)
            interpreter = runner.python_executable(environment / 'bin/python')
            result = subprocess.run([str(interpreter), '-c', 'import sys; print(sys.prefix)'],
                                    check=True, capture_output=True, text=True, timeout=10)
            self.assertEqual(Path(result.stdout.strip()).resolve(), environment.resolve())

    def test_missing_dependencies_stop_before_claude_or_output_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'server.py').touch()
            interpreter = root / 'python'
            interpreter.touch()
            output = root / 'run'
            failed = subprocess.CompletedProcess([], 1, stdout='', stderr="ModuleNotFoundError: No module named 'mcp'")
            with mock.patch.object(runner.shutil, 'which', return_value='/fake/claude'), \
                 mock.patch.object(runner.subprocess, 'run', return_value=failed) as check, \
                 mock.patch.object(runner.subprocess, 'Popen') as launch, \
                 mock.patch('sys.stderr'):
                with self.assertRaises(SystemExit) as failure:
                    runner.main(['--repo-root', str(root), '--python', str(interpreter),
                                 '--broker-url', 'http://127.0.0.1:1126',
                                 '--context-url', 'http://context/user-context.jsonld',
                                 '--output', str(output)])
                self.assertEqual(failure.exception.code, 2)
                self.assertEqual(check.call_args.args[0][0], str(interpreter))
                launch.assert_not_called()
                self.assertFalse(output.exists())

    def test_trace_extraction_keeps_native_arguments_and_answer(self):
        events = [
            {'type': 'assistant', 'message': {'content': [
                {'type': 'tool_use', 'id': 'one', 'name': 'mcp__fiware_farm__query_entities',
                 'input': {'type': 'Animal', 'q': 'heartRate>56'}}]}},
            {'type': 'result', 'result': 'Captured answer', 'is_error': False},
        ]
        with tempfile.TemporaryDirectory() as directory:
            trace = Path(directory) / 'events.jsonl'
            trace.write_text('\n'.join(json.dumps(e) for e in events))
            final, calls = runner.summarize(trace)
            self.assertEqual(final['result'], 'Captured answer')
            self.assertEqual(calls[0]['arguments']['q'], 'heartRate>56')


if __name__ == '__main__':
    unittest.main()
