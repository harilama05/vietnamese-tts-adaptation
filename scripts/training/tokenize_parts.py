#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--parts-dir", required=True)
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--tokenizer-path", required=True)
    ap.add_argument("--gpu-ids", default="0")
    ap.add_argument("--nj-per-gpu", type=int, default=3)
    ap.add_argument("--loader-workers", type=int, default=4)
    args = ap.parse_args()
    if args.nj_per_gpu <= 0 or args.loader_workers < 0:
        ap.error("nj-per-gpu must be positive; loader-workers must be nonnegative")

    parts_dir = Path(args.parts_dir).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    if any(c.isspace() for c in str(output_dir)):
        ap.error("Token output paths cannot contain whitespace (upstream data.lst format)")
    tokenizer = Path(args.tokenizer_path).expanduser().resolve()
    if not (tokenizer / "config.json").is_file():
        ap.error(f"Missing tokenizer config: {tokenizer}")
    digest = hashlib.sha256()
    for file in sorted(tokenizer.rglob("*")):
        if file.is_file() and not any(x in file.relative_to(tokenizer).parts for x in (".cache", ".git")):
            digest.update(file.relative_to(tokenizer).as_posix().encode())
            digest.update(sha256_file(file).encode())
    tokenizer_hash = digest.hexdigest()
    output_dir.mkdir(parents=True, exist_ok=True)

    manifests = sorted(parts_dir.glob("part-*.jsonl"))
    if not manifests:
        raise SystemExit(f"No manifest parts under {parts_dir}")
    master = output_dir / "data.lst"
    master.unlink(missing_ok=True)

    master_lines: list[str] = []

    for i, manifest in enumerate(manifests, 1):
        tag = manifest.stem
        part_out = output_dir / tag
        done = part_out / ".done"
        hash_file = part_out / ".manifest.sha256"
        data_lst = part_out / "data.lst"
        current_hash = hashlib.sha256((sha256_file(manifest) + tokenizer_hash).encode()).hexdigest()

        cache_ok = (
            done.is_file()
            and hash_file.is_file()
            and data_lst.is_file()
            and data_lst.stat().st_size > 0
            and hash_file.read_text(encoding="utf-8").strip() == current_hash
        )
        if cache_ok:
            try:
                verify_part(manifest, part_out)
            except (OSError, ValueError, RuntimeError):
                cache_ok = False

        if cache_ok:
            print(f"[{i}/{len(manifests)}] SKIP {tag}: manifest hash unchanged", flush=True)
        else:
            if part_out.exists():
                if part_out.is_symlink() or not part_out.resolve().is_relative_to(output_dir):
                    raise RuntimeError(f"Unsafe derived token path: {part_out}")
                shutil.rmtree(part_out)
            (part_out / "audios").mkdir(parents=True)
            (part_out / "txts").mkdir(parents=True)

            cmd = [
                sys.executable,
                "-m",
                "omnivoice.scripts.extract_audio_tokens",
                "--input_jsonl",
                str(manifest),
                "--tar_output_pattern",
                str(part_out / "audios" / "shard-%06d.tar"),
                "--jsonl_output_pattern",
                str(part_out / "txts" / "shard-%06d.jsonl"),
                "--tokenizer_path",
                args.tokenizer_path,
                "--nj_per_gpu",
                str(args.nj_per_gpu),
                "--loader_workers",
                str(args.loader_workers),
                "--shuffle",
                "True",
            ]
            env = os.environ.copy()
            env["CUDA_VISIBLE_DEVICES"] = args.gpu_ids

            print(f"[{i}/{len(manifests)}] TOKENIZE {tag}", flush=True)
            subprocess.run(cmd, env=env, check=True)

            if not data_lst.is_file() or data_lst.stat().st_size == 0:
                raise RuntimeError(f"Tokenizer completed but data.lst is missing/empty: {data_lst}")
            verify_part(manifest, part_out)

            hash_file.write_text(current_hash + "\n", encoding="utf-8")
            done.write_text("ok\n", encoding="utf-8")

        master_lines.extend(
            x.strip()
            for x in data_lst.read_text(encoding="utf-8").splitlines()
            if x.strip()
        )

    temporary = master.with_suffix(".lst.tmp")
    temporary.write_text("\n".join(master_lines) + "\n", encoding="utf-8")
    temporary.replace(master)
    print(f"TOKENIZE OK: {master}")
    print(f"Manifest shard records: {len(master_lines)}")


def count_records(path: Path) -> int:
    with path.open(encoding="utf-8") as stream:
        return sum(bool(line.strip()) for line in stream)


def verify_part(manifest: Path, output: Path) -> None:
    """Enforce the all-rows policy even if upstream silently skips an audio read."""
    errors = output / "errors.jsonl"
    if errors.is_file() and count_records(errors):
        raise RuntimeError(f"Tokenization errors in {errors}")
    total = 0
    for line in (output / "data.lst").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        fields = line.split()
        if len(fields) != 4:
            raise RuntimeError(f"Invalid data.lst row in {output}; whitespace in paths is unsupported")
        tar_path, metadata_path, count, duration = fields
        tar, metadata = Path(tar_path), Path(metadata_path)
        if not tar.is_file() or tar.stat().st_size == 0 or not metadata.is_file():
            raise RuntimeError(f"Missing or empty shard in {output}")
        if int(count) <= 0 or float(duration) < 0 or count_records(metadata) != int(count):
            raise RuntimeError(f"Shard row-count mismatch in {output}")
        total += int(count)
    expected = count_records(manifest)
    if expected == 0 or total != expected:
        raise RuntimeError(f"Tokenized {total} rows, expected {expected}: {manifest}")


if __name__ == "__main__":
    main()
