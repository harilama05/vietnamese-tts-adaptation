#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import html
import json
from pathlib import Path


def read_jsonl_map(path: Path, key: str) -> dict[str, dict[str, object]]:
    out: dict[str, dict[str, object]] = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            out[str(row[key])] = row
    return out


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str] | None = None) -> None:
    if not rows:
        return
    if fields is None:
        fields = []
        for row in rows:
            for k in row:
                if k not in fields:
                    fields.append(k)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader(); w.writerows(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    args = ap.parse_args()
    root = args.root.expanduser().resolve()

    prepared = read_jsonl_map(root / "prepared_cases.jsonl", "case_id")
    whisper = read_jsonl_map(root / "whisper_case_metrics.jsonl", "case_id")
    objective = read_jsonl_map(root / "objective_case_metrics.jsonl", "case_id")
    generation = read_jsonl_map(root / "full_model" / "results.jsonl", "chunk_id")
    if not prepared:
        raise RuntimeError("Missing prepared_cases.jsonl")
    if not whisper:
        raise RuntimeError("Missing whisper_case_metrics.jsonl; run whisper-score first")

    rows: list[dict[str, object]] = []
    review_rows: list[dict[str, object]] = []
    for case_id, p in prepared.items():
        w = whisper.get(case_id, {})
        o = objective.get(case_id, {})
        g = generation.get(case_id, {})
        norm_status = str(p.get("norm_auto_status", ""))
        model_status = str(w.get("model_auto_status", ""))
        norm_problem = norm_status == "NORM_REVIEW"
        model_problem = model_status.startswith("MODEL_OR_ASR_REVIEW")
        not_judged = model_status == "NOT_JUDGED_NORM_UNSETTLED"
        if norm_problem and model_problem:
            issue = "BOTH_REVIEW"
        elif norm_problem or not_judged:
            issue = "NORM_REVIEW"
        elif model_problem:
            issue = "MODEL_OR_ASR_REVIEW"
        else:
            issue = "AUTO_OK_UNVERIFIED"

        row: dict[str, object] = {
            "case_id": case_id,
            "document_id": p.get("document_id", ""),
            "source_label": p.get("source_label", ""),
            "chunk_index": p.get("chunk_index", ""),
            "chunk_count_in_document": p.get("chunk_count_in_document", ""),
            "category": p.get("category", ""),
            "issue_type": issue,
            "raw_text": p.get("raw_text", ""),
            "normalized_text": p.get("normalized_text", ""),
            "norm_auto_status": norm_status,
            "norm_warning": p.get("norm_warning", ""),
            "trace_reasons": p.get("trace_reasons", ""),
            "residual_patterns": p.get("residual_patterns", ""),
            "whisper_text": w.get("whisper_text", ""),
            "wer": w.get("wer", ""),
            "cer": w.get("cer", ""),
            "model_auto_status": model_status,
            "diff_summary": w.get("diff_summary", ""),
            "audio_path": w.get("wav_path", f"full_model/chunks/{case_id}.wav"),
            "transcript_path": w.get("transcript_path", ""),
            "generation_seconds": g.get("generation_seconds", ""),
            "audio_seconds": g.get("audio_seconds", ""),
            "rtf": g.get("rtf", ""),
            "peak_vram_mib": g.get("peak_vram_mib", ""),
            "nisqa_mos": o.get("nisqa_mos", ""),
            "dnsmos_ovrl": o.get("dnsmos_ovrl", ""),
            "speaker_similarity": o.get("speaker_similarity", ""),
            "clipping_pct": o.get("clipping_pct", ""),
            "silence_frame_pct": o.get("silence_frame_pct", ""),
            "manual_norm_status": "",
            "manual_model_status": "",
            "manual_asr_status": "",
            "manual_note": "",
        }
        rows.append(row)
        if issue != "AUTO_OK_UNVERIFIED":
            review_rows.append(row.copy())

    write_csv(root / "audit_results.csv", rows)
    if review_rows:
        write_csv(root / "review_cases.csv", review_rows)
    else:
        with (root / "review_cases.csv").open("w", encoding="utf-8-sig", newline="") as f:
            csv.DictWriter(f, fieldnames=list(rows[0])).writeheader()
    write_csv(root / "manual_review_template.csv", rows)

    doc_summary: dict[str, dict[str, object]] = {}
    for row in rows:
        doc_id = str(row["document_id"])
        d = doc_summary.setdefault(doc_id, {
            "document_id": doc_id,
            "source_label": row["source_label"],
            "chunk_count": 0,
            "review_chunk_count": 0,
            "norm_review_count": 0,
            "model_or_asr_review_count": 0,
            "mean_wer": 0.0,
            "mean_cer": 0.0,
            "stitched_audio_path": f"full_model/stitched/{doc_id}.wav",
        })
        d["chunk_count"] = int(d["chunk_count"]) + 1
        if row["issue_type"] != "AUTO_OK_UNVERIFIED":
            d["review_chunk_count"] = int(d["review_chunk_count"]) + 1
        if row["issue_type"] in {"NORM_REVIEW", "BOTH_REVIEW"}:
            d["norm_review_count"] = int(d["norm_review_count"]) + 1
        if row["issue_type"] in {"MODEL_OR_ASR_REVIEW", "BOTH_REVIEW"}:
            d["model_or_asr_review_count"] = int(d["model_or_asr_review_count"]) + 1
        try: d["mean_wer"] = float(d["mean_wer"]) + float(row["wer"])
        except (TypeError, ValueError): pass
        try: d["mean_cer"] = float(d["mean_cer"]) + float(row["cer"])
        except (TypeError, ValueError): pass
    document_rows = []
    for d in doc_summary.values():
        n = max(1, int(d["chunk_count"]))
        d["mean_wer"] = round(float(d["mean_wer"]) / n, 6)
        d["mean_cer"] = round(float(d["mean_cer"]) / n, 6)
        document_rows.append(d)
    document_rows.sort(key=lambda x: str(x["document_id"]))
    write_csv(root / "document_summary.csv", document_rows)

    counts: dict[str, int] = {}
    for row in rows:
        counts[str(row["issue_type"])] = counts.get(str(row["issue_type"]), 0) + 1
    summary = {
        "document_count": len(document_rows),
        "chunk_count": len(rows),
        "review_chunk_count": len(review_rows),
        "issue_counts": counts,
        "note": "Automatic model flags are screening signals. Listen to flagged audio to separate MODEL_ERROR from ASR_ERROR.",
    }
    (root / "audit_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    cards = []
    for row in review_rows:
        audio = html.escape(str(row["audio_path"]), quote=True)
        cards.append(f"""
<article class="card">
  <h2>{html.escape(str(row['source_label']))} · chunk {html.escape(str(row['chunk_index']))} · {html.escape(str(row['issue_type']))}</h2>
  <div><code>{html.escape(str(row['case_id']))}</code></div>
  <audio controls preload="none" src="{audio}"></audio>
  <p><b>RAW:</b> {html.escape(str(row['raw_text']))}</p>
  <p><b>NORM:</b> {html.escape(str(row['normalized_text']))}</p>
  <p><b>WHISPER:</b> {html.escape(str(row['whisper_text']))}</p>
  <p><b>Norm:</b> {html.escape(str(row['norm_auto_status']))}<br>
     <b>Trace reasons:</b> {html.escape(str(row['trace_reasons']))}<br>
     <b>Residual:</b> {html.escape(str(row['residual_patterns']))}</p>
  <p><b>WER/CER:</b> {html.escape(str(row['wer']))} / {html.escape(str(row['cer']))}<br>
     <b>Diff:</b> {html.escape(str(row['diff_summary']))}</p>
  <p><b>Quality:</b> NISQA={html.escape(str(row['nisqa_mos']))}, DNSMOS={html.escape(str(row['dnsmos_ovrl']))}, SPK={html.escape(str(row['speaker_similarity']))}</p>
</article>""")

    report = f"""<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><title>danhgia_tts norm audit</title>
<style>body{{font-family:system-ui,sans-serif;max-width:1200px;margin:24px auto;padding:0 16px;background:#f7f7f7;color:#111}}.card{{background:white;border:1px solid #ddd;border-radius:12px;padding:16px;margin:14px 0}}h2{{font-size:18px}}p{{line-height:1.45}}audio{{width:100%;max-width:650px}}code{{background:#eee;padding:2px 5px;border-radius:4px}}</style></head><body>
<h1>Normalizer + Combined HTV/Podcast audit — danhgia_tts.txt</h1>
<p>Documents: {len(document_rows)} · Chunks: {len(rows)} · Need review: {len(review_rows)}</p>
<p>NORM sai → sửa normalizer. NORM đúng nhưng audio đọc sai → MODEL_ERROR. Audio đúng nhưng Whisper sai → ASR_ERROR.</p>
{''.join(cards) if cards else '<p>No auto-flagged chunks.</p>'}
</body></html>"""
    (root / "review.html").write_text(report, encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Saved: {root / 'audit_results.csv'}")
    print(f"Saved: {root / 'review_cases.csv'}")
    print(f"Saved: {root / 'manual_review_template.csv'}")
    print(f"Saved: {root / 'document_summary.csv'}")
    print(f"Saved: {root / 'review.html'}")


if __name__ == "__main__":
    main()
