from __future__ import annotations

import csv
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import wave

ROOT = Path(__file__).resolve().parents[1]


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts/training' / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tokens = load_script('tokenize_parts')


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='gov-')
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)

    def run_script(self, script, *args, success=True):
        result = subprocess.run([sys.executable, str(ROOT / script), *map(str, args)], cwd=ROOT,
                                env={**os.environ, 'PYTHONIOENCODING': 'utf-8'},
                                capture_output=True, text=True, encoding='utf-8')
        if success:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0)
        return result

    def make_csv(self, missing=False):
        audio = self.work / 'audio.wav'
        with wave.open(str(audio), 'wb') as stream:
            stream.setnchannels(1)
            stream.setsampwidth(2)
            stream.setframerate(24000)
            stream.writeframes(b'\0\0' * 240)
        path = self.work / 'input.csv'
        with path.open('w', newline='', encoding='utf-8-sig') as stream:
            writer = csv.DictWriter(stream, fieldnames=['dataset', 'segment_id', 'audio_path', 'text', 'wer'])
            writer.writeheader()
            for index in range(3):
                writer.writerow({'dataset': 'htv/news', 'segment_id': 'duplicate/id',
                                 'audio_path': 'missing.wav' if missing else audio.name,
                                 'text': 'Ngày 14/9, giá 12,5%.', 'wer': '0.99'})
        return path

    def test_manifest_preserves_all_rows_and_text(self):
        source = self.make_csv()
        output = self.work / 'manifest'
        self.run_script('scripts/training/prepare_manifest.py', '--csv', source, '--output-dir', output,
                        '--part-rows', 2, '--smoke-rows', 1)
        rows = [json.loads(line) for line in (output / 'train.jsonl').read_text(encoding='utf-8').splitlines()]
        self.assertEqual(len(rows), 3)
        self.assertEqual(len({row['id'] for row in rows}), 3)
        self.assertTrue(all('/' not in row['id'] for row in rows))
        self.assertTrue(all(row['text'] == 'Ngày 14/9, giá 12,5%.' and row['wer'] == 0.99 for row in rows))
        self.assertFalse((output / 'dev.jsonl').exists())
        self.assertEqual(len(list((output / 'parts/train').glob('*.jsonl'))), 2)

    def test_failed_prepare_never_publishes_partial_manifest(self):
        output = self.work / 'manifest'
        self.run_script('scripts/training/prepare_manifest.py', '--csv', self.make_csv(missing=True),
                        '--output-dir', output, success=False)
        self.assertFalse(output.exists())
        self.assertEqual(len(list(self.work.glob('manifest.tmp.*/manifest_report.json'))), 1)

    def test_prepare_refuses_existing_output(self):
        output = self.work / 'manifest'
        output.mkdir()
        (output / 'keep.txt').write_text('keep')
        self.run_script('scripts/training/prepare_manifest.py', '--csv', self.make_csv(),
                        '--output-dir', output, success=False)
        self.assertEqual((output / 'keep.txt').read_text(), 'keep')

    def test_invalid_partition_size_is_rejected(self):
        self.run_script('scripts/training/prepare_manifest.py', '--csv', self.make_csv(),
                        '--output-dir', self.work / 'manifest', '--part-rows', 0, success=False)

    def test_config_targets_17500_and_full_finetune(self):
        train, data = self.work / 'config/train.json', self.work / 'config/data.json'
        args = ['--model', self.work / 'model', '--train-list', self.work / 'data.lst',
                '--train-config-out', train, '--data-config-out', data]
        self.run_script('scripts/training/make_train_config.py', *args)
        cfg = json.loads(train.read_text())
        self.assertEqual(cfg['steps'], 17500)
        self.assertIs(cfg['use_lora'], False)
        self.assertEqual(cfg['learning_rate'], 1e-5)
        self.assertEqual(set(json.loads(data.read_text())), {'train'})
        self.run_script('scripts/training/make_train_config.py', *args, '--smoke')
        self.assertEqual(json.loads(train.read_text())['steps'], 10)

    def make_token_part(self, output, records=2):
        output.mkdir(parents=True, exist_ok=True)
        tar = output / 'shard.tar'
        tar.write_bytes(b'fake-token-shard-for-metadata-validation')
        metadata = output / 'shard.jsonl'
        metadata.write_text('{}\n' * records, encoding='utf-8')
        (output / 'data.lst').write_text(f'{tar} {metadata} {records} 2.0\n', encoding='utf-8')
        return tar

    def test_token_verification_catches_dropped_rows_and_missing_shards(self):
        manifest = self.work / 'part.jsonl'
        manifest.write_text('{}\n{}\n', encoding='utf-8')
        output = self.work / 'tokens'
        tar = self.make_token_part(output)
        tokens.verify_part(manifest, output)
        tar.unlink()
        with self.assertRaisesRegex(RuntimeError, 'Missing or empty'):
            tokens.verify_part(manifest, output)
        self.make_token_part(output, records=1)
        with self.assertRaisesRegex(RuntimeError, 'expected 2'):
            tokens.verify_part(manifest, output)

    def test_token_cache_rebuilds_on_changes_and_checks_shards(self):
        parts, output, tokenizer = self.work / 'parts', self.work / 'tokens', self.work / 'codec'
        parts.mkdir()
        tokenizer.mkdir()
        manifest = parts / 'part-00000.jsonl'
        manifest.write_text('{}\n{}\n', encoding='utf-8')
        (tokenizer / 'config.json').write_text('{}')
        arguments = ['tokenize_parts.py', '--parts-dir', str(parts), '--output-dir', str(output),
                     '--tokenizer-path', str(tokenizer)]

        def extract(command, **kwargs):
            part = Path(command[command.index('--tar_output_pattern') + 1]).parent.parent
            self.make_token_part(part)

        with patch.object(sys, 'argv', arguments), patch.object(tokens.subprocess, 'run', side_effect=extract) as run:
            tokens.main()
            tokens.main()
            self.assertEqual(run.call_count, 1)
            (tokenizer / 'config.json').write_text('{"changed": true}')
            tokens.main()
            self.assertEqual(run.call_count, 2)
            (output / 'part-00000/shard.tar').unlink()
            tokens.main()
            self.assertEqual(run.call_count, 3)
            manifest.write_text('{"changed": true}\n{}\n', encoding='utf-8')
            tokens.main()
            self.assertEqual(run.call_count, 4)
            self.assertTrue((output / 'data.lst').is_file())
        with patch.object(sys, 'argv', arguments), patch.object(tokens.subprocess, 'run', side_effect=RuntimeError('interrupted')):
            (tokenizer / 'config.json').write_text('{"changed": 2}')
            with self.assertRaisesRegex(RuntimeError, 'interrupted'):
                tokens.main()
            self.assertFalse((output / 'data.lst').exists())

    def test_17_documents_reproduce_the_archived_101_chunks(self):
        output = self.work / 'benchmark'
        self.run_script('scripts/prepare_benchmark.py', '--output-dir', output)
        actual = json.loads((output / 'shared_chunks.json').read_text(encoding='utf-8'))
        expected = json.loads((ROOT / 'benchmarks/expected_shared_chunks.json').read_text(encoding='utf-8'))
        self.assertEqual(actual['text_count'], 17)
        self.assertEqual(actual['chunk_count'], 101)
        self.assertEqual(actual['chunks'], expected['chunks'])
        self.assertEqual(actual['content_sha256'], expected['content_sha256'])
        self.assertTrue(all(len(row['tts_text']) <= 430 for row in actual['chunks']))

    def test_archived_results_match_the_selected_checkpoint(self):
        root = ROOT / 'reports/checkpoint-17500'
        run = json.loads((root / 'run_config.json').read_text(encoding='utf-8'))
        self.assertTrue(run['base_model'].endswith('/checkpoint-17500'))
        self.assertIsNone(run['adapter'])
        self.assertEqual(json.loads((root / 'whisper_summary.json').read_text())['chunk_count'], 101)


if __name__ == '__main__':
    unittest.main()
