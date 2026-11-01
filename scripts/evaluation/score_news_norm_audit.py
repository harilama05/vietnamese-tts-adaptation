#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import difflib
import hashlib
import json
import os
import re
import unicodedata
from pathlib import Path

from jiwer import cer, wer


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def metric_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text).lower()
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def diff_summary(reference: str, hypothesis: str) -> str:
    a = metric_text(reference).split()
    b = metric_text(hypothesis).split()
    sm = difflib.SequenceMatcher(a=a, b=b)
    parts: list[str] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        left = " ".join(a[i1:i2]) or "∅"
        right = " ".join(b[j1:j2]) or "∅"
        parts.append(f"{tag}:{left}→{right}")
        if len(parts) >= 8:
            parts.append("...")
            break
    return " | ".join(parts)


def repeated_ngram(text: str, n: int = 4) -> int:
    words = metric_text(text).split()
    if len(words) < n:
        return 0
    counts: dict[tuple[str, ...], int] = {}
    for i in range(len(words) - n + 1):
        gram = tuple(words[i:i+n])
        counts[gram] = counts.get(gram, 0) + 1
    return max(counts.values(), default=0)


def read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def read_checkpoint(path: Path) -> dict[str, dict[str, object]]:
    out: dict[str, dict[str, object]] = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
            out[str(row["case_id"])] = row
        except (json.JSONDecodeError, KeyError):
            pass
    return out


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise RuntimeError("No rows")
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--model", default="large-v3")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--compute-type", default="float16")
    args = ap.parse_args()

    root = args.root.expanduser().resolve()
    cases = read_jsonl(root / "prepared_cases.jsonl")

    from faster_whisper import WhisperModel
    model = WhisperModel(args.model, device=args.device, compute_type=args.compute_type)
    checkpoint_path = root / "whisper_case_metrics.jsonl"
    completed = read_checkpoint(checkpoint_path)
    transcript_dir = root / "transcripts"
    transcript_dir.mkdir(parents=True, exist_ok=True)

    scoring_mode = "chunk-wise; condition_on_previous_text=False; beam_size=5; temperature=0.0; vad_filter=False"
    total = len(cases)

    for case in cases:
        case_id = str(case["case_id"])
        wav = root / "full_model" / "chunks" / f"{case_id}.wav"
        if not wav.is_file():
            raise FileNotFoundError(wav)
        wav_hash = sha256_file(wav)
        old = completed.get(case_id)
        if old and old.get("wav_sha256") == wav_hash and old.get("whisper_model") == args.model and old.get("scoring_mode") == scoring_mode:
            print(f"SKIP {case_id}", flush=True)
            continue

        segments, info = model.transcribe(
            str(wav), language="vi", beam_size=5, temperature=0.0,
            vad_filter=False, condition_on_previous_text=False,
        )
        hypothesis = " ".join(seg.text.strip() for seg in segments).strip()
        reference = str(case["normalized_text"])
        ref_metric = metric_text(reference)
        hyp_metric = metric_text(hypothesis)
        case_wer = float(wer(ref_metric, hyp_metric)) if ref_metric else 1.0
        case_cer = float(cer(ref_metric, hyp_metric)) if ref_metric else 1.0

        residual = str(case.get("residual_patterns", ""))
        norm_status = str(case.get("norm_auto_status", ""))
        norm_unsettled = bool(residual) or norm_status == "NORM_REVIEW"
        if norm_unsettled:
            model_auto_status = "NOT_JUDGED_NORM_UNSETTLED"
        elif case_wer <= 0.05 and case_cer <= 0.03:
            model_auto_status = "MODEL_AUTO_OK"
        elif case_wer > 0.15 or case_cer > 0.08:
            model_auto_status = "MODEL_OR_ASR_REVIEW_HIGH"
        else:
            model_auto_status = "MODEL_OR_ASR_REVIEW"

        row: dict[str, object] = {
            "case_id": case_id,
            "document_id": case.get("document_id", ""),
            "source_label": case.get("source_label", ""),
            "chunk_index": case.get("chunk_index", ""),
            "category": case.get("category", ""),
            "reference_normalized_text": reference,
            "whisper_text": hypothesis,
            "wer": round(case_wer, 6),
            "cer": round(case_cer, 6),
            "hypothesis_length_ratio": round(len(hyp_metric) / max(1, len(ref_metric)), 6),
            "max_repeated_4gram_count": repeated_ngram(hypothesis, 4),
            "diff_summary": diff_summary(reference, hypothesis),
            "norm_auto_status": norm_status,
            "residual_patterns": residual,
            "model_auto_status": model_auto_status,
            "wav_path": str(wav.relative_to(root)),
            "wav_sha256": wav_hash,
            "transcript_path": f"transcripts/{case_id}.txt",
            "whisper_model": args.model,
            "whisper_language": getattr(info, "language", "vi"),
            "scoring_mode": scoring_mode,
        }
        with checkpoint_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush(); os.fsync(f.fileno())
        (transcript_dir / f"{case_id}.txt").write_text(hypothesis + "\n", encoding="utf-8")
        completed[case_id] = row
        print(f"[{len(completed)}/{total}] {case_id} WER={case_wer:.3f} CER={case_cer:.3f} {model_auto_status}", flush=True)

    ordered = [completed[str(case["case_id"])] for case in cases]
    write_csv(root / "whisper_case_metrics.csv", ordered)
    summary = {
        "chunk_count": len(ordered),
        "document_count": len({str(r.get('document_id', '')) for r in ordered}),
        "mean_wer": round(sum(float(r["wer"]) for r in ordered) / len(ordered), 6),
        "mean_cer": round(sum(float(r["cer"]) for r in ordered) / len(ordered), 6),
        "model_auto_ok": sum(r["model_auto_status"] == "MODEL_AUTO_OK" for r in ordered),
        "model_or_asr_review": sum(str(r["model_auto_status"]).startswith("MODEL_OR_ASR_REVIEW") for r in ordered),
        "not_judged_norm_unsettled": sum(r["model_auto_status"] == "NOT_JUDGED_NORM_UNSETTLED" for r in ordered),
        "whisper_model": args.model,
        "scoring_mode": scoring_mode,
    }
    (root / "whisper_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_csv(root / "whisper_summary.csv", [summary])
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
