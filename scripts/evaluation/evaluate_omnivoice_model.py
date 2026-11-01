#!/usr/bin/env python3
"""Generate one OmniVoice benchmark variant with resumable chunk output."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import random
import statistics
import time
from pathlib import Path

import numpy as np
import soundfile as sf
import torch


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def seed_all(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def read_checkpoint(path: Path) -> dict[str, dict[str, object]]:
    rows: dict[str, dict[str, object]] = {}
    if not path.is_file():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
            rows[str(row["chunk_id"])] = row
        except (json.JSONDecodeError, KeyError):
            continue
    return rows


def valid_wav(path: Path) -> bool:
    try:
        info = sf.info(path)
        return info.frames > 0 and info.samplerate > 0
    except Exception:
        return False


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    fields = list(rows[0])
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def stitch_texts(output_dir: Path, rows: list[dict[str, object]], sample_rate: int) -> None:
    stitched_dir = output_dir / "stitched"
    stitched_dir.mkdir(parents=True, exist_ok=True)
    text_ids = sorted({str(row["text_id"]) for row in rows})
    silence = np.zeros(round(0.25 * sample_rate), dtype=np.float32)
    for text_id in text_ids:
        parts: list[np.ndarray] = []
        subset = sorted(
            (row for row in rows if str(row["text_id"]) == text_id),
            key=lambda row: int(row["chunk_index"]),
        )
        for index, row in enumerate(subset):
            audio, sr = sf.read(str(output_dir / str(row["wav_path"])), dtype="float32")
            if sr != sample_rate:
                raise RuntimeError(f"Unexpected sample rate {sr}")
            if audio.ndim > 1:
                audio = audio.mean(axis=1)
            if index:
                parts.append(silence)
            parts.append(audio)
        sf.write(stitched_dir / f"{text_id}.wav", np.concatenate(parts), sample_rate, subtype="PCM_16")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("--model", default="k2-fsa/OmniVoice")
    parser.add_argument("--adapter", type=Path)
    parser.add_argument("--chunks", type=Path, required=True)
    parser.add_argument("--reference-audio", type=Path, required=True)
    parser.add_argument("--reference-text", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-chunks", type=int, default=0)
    args = parser.parse_args()

    from omnivoice import OmniVoice

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable")
    args.reference_audio = args.reference_audio.expanduser().resolve()
    if not valid_wav(args.reference_audio):
        raise RuntimeError(f"Invalid reference WAV: {args.reference_audio}")
    if args.adapter:
        args.adapter = args.adapter.expanduser().resolve()
        for required in ("adapter_config.json", "adapter_model.safetensors"):
            if not (args.adapter / required).is_file():
                raise FileNotFoundError(args.adapter / required)

    payload = json.loads(args.chunks.read_text(encoding="utf-8"))
    all_chunks = list(payload["chunks"])
    chunks = all_chunks[: args.max_chunks] if args.max_chunks > 0 else all_chunks
    output_dir = args.output_dir.expanduser().resolve()
    wav_dir = output_dir / "chunks"
    wav_dir.mkdir(parents=True, exist_ok=True)
    checkpoint = output_dir / "results.jsonl"
    completed = read_checkpoint(checkpoint)

    config = {
        "name": args.name,
        "base_model": args.model,
        "adapter": str(args.adapter) if args.adapter else None,
        "chunks_sha256": payload["content_sha256"],
        "reference_audio": str(args.reference_audio),
        "reference_sha256": file_sha256(args.reference_audio),
        "reference_text": args.reference_text,
        "seed": args.seed,
        "generation": {
            "language": "vi",
            "num_step": 32,
            "guidance_scale": 2.0,
            "speed": 1.0,
            "t_shift": 0.1,
            "denoise": True,
            "postprocess_output": True,
            "layer_penalty_factor": 5.0,
            "position_temperature": 5.0,
            "class_temperature": 0.0,
            "normalize_text": False,
        },
    }
    config_path = output_dir / "run_config.json"
    if config_path.is_file():
        old = json.loads(config_path.read_text(encoding="utf-8"))
        if old != config:
            raise RuntimeError(f"Existing output has different config: {config_path}")
    else:
        config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    started = time.perf_counter()
    model = OmniVoice.from_pretrained(args.model, device_map=args.device, dtype=torch.float16)
    if args.adapter:
        from omnivoice.utils.lora import load_lora_adapter

        model = load_lora_adapter(model, str(args.adapter), merge=True)
    torch.cuda.synchronize()
    load_seconds = time.perf_counter() - started

    started = time.perf_counter()
    prompt = model.create_voice_clone_prompt(
        ref_audio=str(args.reference_audio), ref_text=args.reference_text
    )
    torch.cuda.synchronize()
    prompt_seconds = time.perf_counter() - started

    # One identical warm-up per model; excluded from benchmark timing.
    seed_all(args.seed)
    with torch.inference_mode():
        model.generate(
            text="Xin chào, đây là bước làm nóng mô hình.",
            language="vi",
            voice_clone_prompt=prompt,
            num_step=32,
            guidance_scale=2.0,
            speed=1.0,
            t_shift=0.1,
            denoise=True,
            postprocess_output=True,
            layer_penalty_factor=5.0,
            position_temperature=5.0,
            class_temperature=0.0,
            normalize_text=False,
        )
    torch.cuda.synchronize()

    for global_index, item in enumerate(chunks):
        chunk_id = str(item["chunk_id"])
        wav_rel = f"chunks/{chunk_id}.wav"
        wav_path = output_dir / wav_rel
        if chunk_id in completed and valid_wav(wav_path):
            print(f"SKIP {args.name} {chunk_id}", flush=True)
            continue
        seed_all(args.seed + global_index)
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()
        torch.cuda.synchronize()
        started = time.perf_counter()
        with torch.inference_mode():
            audio = model.generate(
                text=str(item["tts_text"]),
                language="vi",
                voice_clone_prompt=prompt,
                num_step=32,
                guidance_scale=2.0,
                speed=1.0,
                t_shift=0.1,
                denoise=True,
                postprocess_output=True,
                layer_penalty_factor=5.0,
                position_temperature=5.0,
                class_temperature=0.0,
                normalize_text=False,
            )[0]
        torch.cuda.synchronize()
        generation_seconds = time.perf_counter() - started
        waveform = np.asarray(audio, dtype=np.float32).reshape(-1)
        sf.write(wav_path, waveform, model.sampling_rate, subtype="PCM_16")
        audio_seconds = len(waveform) / float(model.sampling_rate)
        row: dict[str, object] = {
            "model_name": args.name,
            "text_id": item["text_id"],
            "chunk_index": item["chunk_index"],
            "chunk_id": chunk_id,
            "tts_chars": item["tts_chars"],
            "seed": args.seed + global_index,
            "generation_seconds": round(generation_seconds, 6),
            "audio_seconds": round(audio_seconds, 6),
            "rtf": round(generation_seconds / audio_seconds, 6),
            "peak_vram_mib": round(torch.cuda.max_memory_allocated() / 1024**2, 2),
            "wav_path": wav_rel,
        }
        with checkpoint.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        completed[chunk_id] = row
        print(
            f"[{len(completed)}/{len(chunks)}] {args.name} {chunk_id} "
            f"gen={generation_seconds:.2f}s audio={audio_seconds:.2f}s "
            f"RTF={generation_seconds / audio_seconds:.3f}",
            flush=True,
        )

    ordered = [completed[str(item["chunk_id"])] for item in chunks if str(item["chunk_id"]) in completed]
    if len(ordered) != len(chunks):
        raise RuntimeError(f"Incomplete: {len(ordered)}/{len(chunks)} chunks")
    write_csv(output_dir / "chunk_metrics.csv", ordered)
    stitch_texts(output_dir, ordered, int(model.sampling_rate))
    total_generation = sum(float(row["generation_seconds"]) for row in ordered)
    total_audio = sum(float(row["audio_seconds"]) for row in ordered)
    rtfs = [float(row["rtf"]) for row in ordered]
    summary = {
        "model_name": args.name,
        "base_model": args.model,
        "adapter": str(args.adapter) if args.adapter else None,
        "text_count": len({str(row["text_id"]) for row in ordered}),
        "chunk_count": len(ordered),
        "load_seconds_last_invocation": round(load_seconds, 3),
        "reference_prompt_seconds_last_invocation": round(prompt_seconds, 3),
        "generation_seconds": round(total_generation, 3),
        "audio_seconds": round(total_audio, 3),
        "weighted_rtf": round(total_generation / total_audio, 6),
        "median_chunk_rtf": round(statistics.median(rtfs), 6),
        "peak_vram_mib": max(float(row["peak_vram_mib"]) for row in ordered),
        "chunks_sha256": payload["content_sha256"],
        "reference_sha256": config["reference_sha256"],
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
