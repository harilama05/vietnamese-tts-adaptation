#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from scipy.signal import resample_poly


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_mono(path: Path) -> tuple[np.ndarray, int]:
    audio, sr = sf.read(path, dtype="float32", always_2d=False)
    if audio.ndim == 2:
        audio = audio.mean(axis=1)
    audio = np.asarray(audio, dtype=np.float32).reshape(-1)
    if not len(audio) or sr <= 0:
        raise RuntimeError(f"Invalid WAV: {path}")
    return np.clip(audio, -1.0, 1.0), int(sr)


def signal_metrics(audio: np.ndarray, sr: int) -> dict[str, float]:
    eps = 1e-12
    peak = float(np.max(np.abs(audio)))
    rms = float(np.sqrt(np.mean(np.square(audio, dtype=np.float64)) + eps))
    frame = max(1, round(0.02 * sr))
    usable = audio[: len(audio) // frame * frame]
    if len(usable):
        framed = usable.reshape(-1, frame)
        frame_rms = np.sqrt(np.mean(np.square(framed, dtype=np.float64), axis=1) + eps)
        silence = float(np.mean(frame_rms < 10 ** (-45.0 / 20.0)))
    else:
        silence = 0.0
    return {
        "duration_seconds": len(audio) / float(sr),
        "sample_rate": sr,
        "peak_dbfs": 20.0 * math.log10(max(peak, eps)),
        "rms_dbfs": 20.0 * math.log10(max(rms, eps)),
        "clipping_pct": 100.0 * float(np.mean(np.abs(audio) >= 0.999)),
        "silence_frame_pct": 100.0 * silence,
        "dc_offset": float(np.mean(audio, dtype=np.float64)),
    }


def pad_min(audio: np.ndarray, sr: int, seconds: float = 4.0) -> tuple[np.ndarray, float]:
    need = round(seconds * sr)
    if len(audio) >= need:
        return audio, 0.0
    padded = np.pad(audio, (0, need - len(audio)))
    return padded.astype(np.float32), (need - len(audio)) / float(sr)


def read_cases(path: Path) -> list[dict[str, object]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def read_checkpoint(path: Path) -> dict[str, dict[str, object]]:
    out = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
                out[str(row["case_id"])] = row
            except (json.JSONDecodeError, KeyError):
                pass
    return out


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    fields: list[str] = []
    for row in rows:
        for k in row:
            if k not in fields:
                fields.append(k)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


class SpeakerScorer:
    def __init__(self, model_name: str, device: str) -> None:
        from transformers import Wav2Vec2FeatureExtractor, WavLMForXVector
        self.device = torch.device(device)
        self.extractor = Wav2Vec2FeatureExtractor.from_pretrained(model_name)
        self.model = WavLMForXVector.from_pretrained(model_name).to(self.device).eval()

    def embedding(self, audio: np.ndarray, sr: int) -> torch.Tensor:
        if sr != 16000:
            div = math.gcd(sr, 16000)
            audio = resample_poly(audio, 16000 // div, sr // div).astype(np.float32)
        inputs = self.extractor(audio, sampling_rate=16000, return_tensors="pt")
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        with torch.inference_mode():
            emb = self.model(**inputs).embeddings
        return torch.nn.functional.normalize(emb, dim=-1)[0].cpu()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--reference-audio", type=Path, required=True)
    ap.add_argument("--speaker-model", default="microsoft/wavlm-base-plus-sv")
    ap.add_argument("--device", default="cuda:0")
    ap.add_argument("--cpu-threads", type=int, default=8)
    args = ap.parse_args()

    root = args.root.expanduser().resolve()
    ref_path = args.reference_audio.expanduser().resolve()
    cases = read_cases(root / "prepared_cases.jsonl")
    reference, reference_sr = load_mono(ref_path)
    reference_hash = sha256_file(ref_path)

    from torchmetrics.functional.audio.dnsmos import deep_noise_suppression_mean_opinion_score
    from torchmetrics.functional.audio.nisqa import non_intrusive_speech_quality_assessment

    speaker = SpeakerScorer(args.speaker_model, args.device)
    reference_emb = speaker.embedding(reference, reference_sr)

    checkpoint_path = root / "objective_case_metrics.jsonl"
    completed = read_checkpoint(checkpoint_path)
    total = len(cases)

    for case in cases:
        case_id = str(case["case_id"])
        wav = root / "full_model" / "chunks" / f"{case_id}.wav"
        if not wav.is_file():
            raise FileNotFoundError(wav)
        wav_hash = sha256_file(wav)
        old = completed.get(case_id)
        if (
            old
            and old.get("wav_sha256") == wav_hash
            and old.get("reference_sha256") == reference_hash
            and old.get("speaker_model") == args.speaker_model
        ):
            print(f"SKIP {case_id}", flush=True)
            continue

        audio, sr = load_mono(wav)
        sig = signal_metrics(audio, sr)
        quality_audio, padded_sec = pad_min(audio, sr, 4.0)
        waveform = torch.from_numpy(quality_audio.copy())
        with torch.inference_mode():
            nisqa = non_intrusive_speech_quality_assessment(waveform, sr).detach().cpu().numpy().reshape(5)
            dnsmos = deep_noise_suppression_mean_opinion_score(
                waveform, sr, personalized=False, device="cpu",
                num_threads=args.cpu_threads, cache_session=True,
            ).detach().cpu().numpy().reshape(4)
        emb = speaker.embedding(audio, sr)
        spk = float(torch.nn.functional.cosine_similarity(
            emb.unsqueeze(0), reference_emb.unsqueeze(0)
        ).item())

        row: dict[str, object] = {
            "case_id": case_id,
            "category": case.get("category", ""),
            "nisqa_mos": round(float(nisqa[0]), 6),
            "nisqa_noisiness": round(float(nisqa[1]), 6),
            "nisqa_discontinuity": round(float(nisqa[2]), 6),
            "nisqa_coloration": round(float(nisqa[3]), 6),
            "nisqa_loudness": round(float(nisqa[4]), 6),
            "dnsmos_p808": round(float(dnsmos[0]), 6),
            "dnsmos_sig": round(float(dnsmos[1]), 6),
            "dnsmos_bak": round(float(dnsmos[2]), 6),
            "dnsmos_ovrl": round(float(dnsmos[3]), 6),
            "speaker_similarity": round(spk, 6),
            "quality_padding_seconds": round(padded_sec, 6),
            **{k: round(float(v), 6) if isinstance(v, float) else v for k, v in sig.items()},
            "wav_path": str(wav.relative_to(root)),
            "wav_sha256": wav_hash,
            "reference_sha256": reference_hash,
            "speaker_model": args.speaker_model,
        }
        with checkpoint_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())
        completed[case_id] = row
        print(
            f"[{len(completed)}/{total}] {case_id} NISQA={row['nisqa_mos']:.3f} "
            f"DNSMOS={row['dnsmos_ovrl']:.3f} SPK={row['speaker_similarity']:.3f}",
            flush=True,
        )

    ordered = [completed[str(c["case_id"])] for c in cases]
    write_csv(root / "objective_case_metrics.csv", ordered)
    mean_fields = [
        "nisqa_mos", "dnsmos_ovrl", "speaker_similarity", "clipping_pct",
        "silence_frame_pct", "rms_dbfs", "peak_dbfs",
    ]
    summary: dict[str, object] = {"case_count": len(ordered), "reference_sha256": reference_hash}
    for field in mean_fields:
        summary[f"mean_{field}"] = round(float(np.mean([float(r[field]) for r in ordered])), 6)
    (root / "objective_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    write_csv(root / "objective_summary.csv", [summary])
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
