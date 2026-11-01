#!/usr/bin/env python3
"""Prepare the 17-text benchmark on CPU without loading an audio model."""
from __future__ import annotations
import argparse
import subprocess
import sys
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--input-text', type=Path, default=root / 'benchmarks/danhgia_tts.txt')
    args = parser.parse_args()
    output = args.output_dir.expanduser().resolve()
    if output.exists() and any(output.iterdir()):
        parser.error('Use an empty output directory to preserve existing evaluation inputs')
    output.mkdir(parents=True, exist_ok=True)
    documents = output / 'input_documents.jsonl'
    subprocess.run([sys.executable, str(root / 'scripts/evaluation/build_news_cases.py'),
                    '--input-text', str(args.input_text), '--output', str(documents)], check=True)
    subprocess.run([sys.executable, str(root / 'scripts/evaluation/prepare_news_norm_audit.py'),
                    '--cases', str(documents), '--output-root', str(output), '--omninorm-root', str(root),
                    '--max-chars', '430', '--raw-target-chars', '330'], check=True)


if __name__ == '__main__':
    main()
