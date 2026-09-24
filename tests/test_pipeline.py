import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from chinesecap.pipeline import load_whisper_model
from chinesecap import models


class PipelineDeviceTests(unittest.TestCase):
    def fake_module(self, constructor):
        return types.SimpleNamespace(WhisperModel=constructor)

    def test_cpu_is_explicit(self):
        calls = []
        def constructor(path, **kwargs):
            calls.append(kwargs)
            return object()
        with patch.dict(sys.modules, {'faster_whisper': self.fake_module(constructor)}):
            _, device = load_whisper_model(Path('model'), 'cpu', 6, lambda _: None)
        self.assertEqual(device, 'cpu')
        self.assertEqual(calls[0]['device'], 'cpu')
        self.assertEqual(calls[0]['compute_type'], 'int8')

    def test_auto_falls_back_when_cuda_load_fails(self):
        calls = []
        def constructor(path, **kwargs):
            calls.append(kwargs)
            if kwargs['device'] == 'cuda':
                raise RuntimeError('missing CUDA runtime')
            return object()
        with patch('chinesecap.pipeline.cuda_available', return_value=True), \
             patch.dict(sys.modules, {'faster_whisper': self.fake_module(constructor)}):
            _, device = load_whisper_model(Path('model'), 'auto', 4, lambda _: None)
        self.assertEqual(device, 'cpu')
        self.assertEqual([call['device'] for call in calls], ['cuda', 'cpu'])

    def test_manual_cuda_reports_failure(self):
        def constructor(path, **kwargs):
            raise RuntimeError('missing CUDA runtime')
        with patch.dict(sys.modules, {'faster_whisper': self.fake_module(constructor)}):
            with self.assertRaisesRegex(RuntimeError, 'CUDA 12'):
                load_whisper_model(Path('model'), 'cuda', 4, lambda _: None)

    def test_macos_runtime_selection(self):
        with patch.object(models.sys, 'platform', 'darwin'), \
             patch.object(models.platform, 'machine', return_value='arm64'):
            info = models.runtime_info()
        self.assertEqual(info['deno'], 'deno')
        self.assertEqual(info['llama'], 'llama-server')
        self.assertIn('macos-arm64', info['llama_url'])


if __name__ == '__main__':
    unittest.main()
