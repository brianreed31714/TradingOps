import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tradingops.entrypoints import resolve_entrypoint
from tradingops.host_inventory import inspect_project
from tradingops.windows_probe import (probe_project, process_status,
                                      collect_process_observations, launched_script, normalized_windows_path)


class ActiveTraderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        # Exercise Windows path semantics with real temporary files on Linux CI.
        if self.root.as_posix().startswith('/'):
            original_normalize = normalized_windows_path
            def windows_temp(value):
                if isinstance(value, str) and value.startswith(str(self.root)):
                    value = 'C:' + value
                return original_normalize(value)
            normalizer = patch('tradingops.windows_probe.normalized_windows_path', side_effect=windows_temp)
            normalizer.start()
            self.addCleanup(normalizer.stop)
        (self.root / 'infrastructure').mkdir()
        (self.root / 'deploy/state').mkdir(parents=True)
        self.old = 'momentum_trader_v1_9_zpta_shadow.py'
        self.new = 'momentum_trader_v1_10_runtime_audit.py'
        for name in (self.old, self.new):
            (self.root / name).touch()
        self.registry = {'project': 'StockTracker', 'mode': 'PAPER_ONLY',
                         'runtime_manifest': 'deploy/state/active_release.json',
                         'components': [{'id': 'trader', 'entrypoint': self.old}]}
        self.manifest = self.root / self.registry['runtime_manifest']
        self.write_registry()

    def write_registry(self):
        (self.root / 'infrastructure/registry.json').write_text(json.dumps(self.registry))

    def reports(self, rows=(), complete=True):
        def git(cmd, **kwargs):
            return subprocess.CompletedProcess(cmd, 0, 'a' * 40 if 'rev-parse' in cmd else '', '')
        return [inspect_project(self.root, 'StockTracker', list(rows),
                                enumeration_complete=complete, run=git),
                probe_project(self.root, list(rows), enumeration_complete=complete)]

    def row(self, script=None, **overrides):
        return dict({'pid': 21372, 'cmdline': [r'C:\Python312\python.exe',
                     str(self.root / (script or self.new))],
                     'exe': r'C:\Python312\python.exe', 'create_time': 1794625712.0}, **overrides)

    def test_manifest_v110_overrides_v19_and_stale_manifest_pid_is_not_identity(self):
        self.manifest.write_text(json.dumps({'files': {'trader': self.new},
                                             'pids': {'trader': 34140}}))
        for report in self.reports([self.row()]):
            self.assertEqual(report['processes']['trader'], 'EXACT_SCRIPT_AND_PROCESS_START_OBSERVED_ONLY')
            self.assertEqual(report['entrypoint_resolution']['trader'], 'LOCAL_MANIFEST_OBSERVED_ONLY')
            self.assertFalse(report['loaded_code_independently_verified'])
            self.assertFalse(report['deployment_authority'])

    def test_missing_and_invalid_manifest_have_explicit_uncertain_fallback(self):
        for content in (None, '{', '[]', '{}', '{"files": []}',
                        json.dumps({'files': {'trader': '../escape.py'}}),
                        json.dumps({'files': {'trader': 'missing.py'}})):
            with self.subTest(content=content):
                if content is not None:
                    self.manifest.write_text(content)
                path, source, authoritative = resolve_entrypoint(self.root, self.registry, 'trader')
                self.assertEqual(Path(path).name, self.old)
                self.assertFalse(authoritative)
                self.assertIn('REGISTRY_FALLBACK', source)
                for report in self.reports():
                    self.assertEqual(report['processes']['trader'],
                                     'ACTIVE_ENTRYPOINT_UNCERTAIN:PROCESS_NOT_OBSERVED')
                for report in self.reports([self.row(self.old)]):
                    self.assertTrue(report['processes']['trader'].startswith('ACTIVE_ENTRYPOINT_UNCERTAIN:'))

    def test_unsafe_or_missing_fallback_and_duplicate_component_fail_closed(self):
        for value in ('../trader.py', r'C:\trader.py', '/trader.py', 'missing.py', 'a\\b.py'):
            with self.subTest(value=value):
                self.registry['components'][0]['entrypoint'] = value
                with self.assertRaises(ValueError):
                    resolve_entrypoint(self.root, self.registry, 'trader')
        self.registry['components'] *= 2
        with self.assertRaises(ValueError):
            resolve_entrypoint(self.root, self.registry, 'trader')

    def test_manifest_does_not_change_crypto_registry_contract(self):
        self.registry['project'] = 'CryptoTracker'
        self.manifest.write_text(json.dumps({'files': {'trader': self.new}}))
        path, source, authoritative = resolve_entrypoint(self.root, self.registry, 'trader')
        self.assertEqual(Path(path).name, self.old)
        self.assertEqual(source, 'REGISTRY')
        self.assertTrue(authoritative)

    def test_both_observers_reject_ambiguity_and_partial_scan(self):
        self.manifest.write_text(json.dumps({'files': {'trader': self.new}}))
        for rows, complete, state in (([self.row(), self.row(pid=2)], True, 'AMBIGUOUS_MULTIPLE_PROCESSES'),
                                      ([self.row()], False, 'PROCESS_ENUMERATION_INCOMPLETE'),
                                      ([self.row(self.old)], True, 'SCRIPT_IDENTITY_MISMATCH'),
                                      ([{'cmdline': None}], True, 'PROCESS_IDENTITY_UNCERTAIN')):
            for report in self.reports(rows, complete):
                self.assertEqual(report['processes']['trader'], state)

    def test_pid_start_and_executable_identity(self):
        script = str(self.root / self.new)
        for changes, state in (({'pid': None}, 'PROCESS_PID_UNVERIFIED'),
                               ({'pid': True}, 'PROCESS_PID_UNVERIFIED'),
                               ({'create_time': float('nan')}, 'PROCESS_START_TIME_UNVERIFIED'),
                               ({'create_time': float('inf')}, 'PROCESS_START_TIME_UNVERIFIED'),
                               ({'create_time': True}, 'PROCESS_START_TIME_UNVERIFIED'),
                               ({'exe': None}, 'EXECUTABLE_PATH_UNVERIFIED'),
                               ({'exe': r'C:\other\python.exe'}, 'EXECUTABLE_IDENTITY_MISMATCH')):
            with self.subTest(changes=changes):
                self.assertEqual(process_status(script, [self.row(**changes)]), state)
        reused = self.row(self.old)
        self.assertEqual(process_status(script, [self.row(), reused]), 'PROCESS_PID_IDENTITY_CONFLICT')
        self.assertIsNone(launched_script(['python-malware.exe', script]))
        self.assertEqual(process_status(script, [self.row(cmdline=[r'C:\Python312\python.exe',
                         str(self.root / 'subdir/../' / self.new)])]),
                         'EXACT_SCRIPT_AND_PROCESS_START_OBSERVED_ONLY')


class CollectionTests(unittest.TestCase):
    def test_hidden_fields_races_denials_and_unavailable_psutil_are_incomplete(self):
        class Error(Exception): pass
        class Denied(Error): pass
        class Gone(Error): pass
        class Proc:
            pid = 10
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def oneshot(self): return self
            def cmdline(self): return None
            def exe(self): return ''
            def create_time(self): return 100.0
            def is_running(self): return True
        fake = SimpleNamespace(Error=Error, AccessDenied=Denied, NoSuchProcess=Gone,
                               ZombieProcess=Gone, process_iter=lambda: iter([Proc()]))
        with patch.dict(sys.modules, {'psutil': fake}):
            self.assertEqual(collect_process_observations()[1:], (False, 'PARTIAL'))
            for exc in (Denied, Gone):
                with patch.object(Proc, 'cmdline', side_effect=exc):
                    self.assertEqual(collect_process_observations(), ([], False, 'PARTIAL'))
            with patch.object(Proc, 'is_running', return_value=False):
                self.assertEqual(collect_process_observations(), ([], False, 'PARTIAL'))
        with patch.dict(sys.modules, {'psutil': None}):
            self.assertEqual(collect_process_observations(), ([], False, 'PSUTIL_UNAVAILABLE'))
