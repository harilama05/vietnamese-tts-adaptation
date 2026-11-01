#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
from collections import Counter
from pathlib import Path
from urllib.parse import quote

REQUIRED = {"dataset", "segment_id", "audio_path", "text"}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def candidate_paths(raw: str, csv_parent: Path, fallback_roots: list[Path]):
    """Resolve audio conservatively.

    Priority is ALWAYS the path literally stored in the CSV. Fallbacks are only
    attempted when that exact path is not a readable file. The CSV itself is
    never rewritten.
    """
    raw = raw.strip()
    p = Path(raw).expanduser()
    seen: set[str] = set()

    def emit(mode: str, q: Path):
        key = str(q)
        if key in seen:
            return None
        seen.add(key)
        return mode, q

    # 1) Literal CSV path first.
    item = emit("exact_csv_path", p)
    if item:
        yield item

    # 2) Normal interpretations for relative paths.
    if not p.is_absolute():
        for mode, q in [
            ("relative_csv_parent", csv_parent / p),
            ("relative_cwd", Path.cwd() / p),
            ("relative_home", Path.home() / p),
        ]:
            item = emit(mode, q)
            if item:
                yield item

    # 3) Mount aliases. Preserve everything from ai-data-02 onward.
    # This is intentionally a fallback only, so a valid CSV path is never
    # replaced or second-guessed.
    marker = "ai-data-02/"
    s = raw.lstrip("/")
    idx = s.find(marker)
    if idx >= 0:
        suffix = s[idx:]
        auto_roots = [
            Path.home(),
            Path("/data") / os.environ.get("USER", ""),
        ]
        for root in [*fallback_roots, *auto_roots]:
            if not str(root):
                continue
            item = emit(f"fallback_root:{root}", root / suffix)
            if item:
                yield item


def resolve_audio(raw: str, csv_parent: Path, fallback_roots: list[Path]):
    for mode, p in candidate_paths(raw, csv_parent, fallback_roots):
        if p.is_file():
            return p.resolve(), mode
    return None, None


def split_parts(src: Path, dst_dir: Path, rows_per_part: int) -> int:
    dst_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    fout = None
    part_idx = -1
    try:
        with src.open("r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                if count % rows_per_part == 0:
                    if fout:
                        fout.close()
                    part_idx += 1
                    fout = (dst_dir / f"part-{part_idx:05d}.jsonl").open(
                        "w", encoding="utf-8"
                    )
                fout.write(line)
                count += 1
    finally:
        if fout:
            fout.close()
    return part_idx + 1 if count else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--part-rows", type=int, default=50000)
    ap.add_argument("--smoke-rows", type=int, default=256)
    ap.add_argument("--fallback-root", action="append", default=[])
    args = ap.parse_args()
    if args.part_rows <= 0 or args.smoke_rows <= 0:
        ap.error("--part-rows and --smoke-rows must be positive")

    csv_path = Path(args.csv).expanduser().resolve()
    final_dir = Path(args.output_dir).expanduser().resolve()
    if final_dir.exists():
        raise FileExistsError(f"Manifest output already exists; reuse it or choose a new output-dir: {final_dir}")
    tmp_dir = final_dir.with_name(final_dir.name + f".tmp.{os.getpid()}")

    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    tmp_dir.mkdir(parents=True)

    fallback_roots = [Path(x).expanduser() for x in args.fallback_root if x]
    train_tmp = tmp_dir / "train.jsonl"
    smoke_tmp = tmp_dir / "smoke.jsonl"
    report_tmp = tmp_dir / "manifest_report.json"

    total = 0
    missing_audio = 0
    empty_text = 0
    resolution_modes = Counter()
    dataset_counts = Counter()
    examples = []
    smoke_lines: list[str] = []

    try:
        with csv_path.open("r", encoding="utf-8-sig", newline="") as fin, train_tmp.open(
            "w", encoding="utf-8"
        ) as fout:
            reader = csv.DictReader(fin)
            fields = set(reader.fieldnames or [])
            missing_cols = sorted(REQUIRED - fields)
            if missing_cols:
                raise RuntimeError(
                    f"CSV missing required columns {missing_cols}; found {reader.fieldnames}"
                )

            for rownum, row in enumerate(reader, start=2):
                total += 1
                dataset = (row.get("dataset") or "unknown").strip() or "unknown"
                segment_id = (row.get("segment_id") or "").strip()
                raw_audio = (row.get("audio_path") or "").strip()
                text = (row.get("text") or "").strip()

                if not text:
                    empty_text += 1
                    if len(examples) < 100:
                        examples.append({"row": rownum, "reason": "empty_text"})
                    continue

                resolved, mode = resolve_audio(raw_audio, csv_path.parent, fallback_roots)
                if resolved is None:
                    missing_audio += 1
                    if len(examples) < 100:
                        examples.append(
                            {
                                "row": rownum,
                                "dataset": dataset,
                                "segment_id": segment_id,
                                "audio_path": raw_audio,
                                "reason": "audio_not_found",
                            }
                        )
                    continue

                # Include source row in the key so no duplicate segment_id ever causes
                # a CSV row to be dropped.
                sample_id = f"{quote(dataset, safe='')}__{quote(segment_id, safe='')}__row{rownum}"
                record = {
                    "id": sample_id,
                    "audio_path": str(resolved),
                    "text": text,
                    "language_id": "vi",
                    "dataset": dataset,
                    "segment_id": segment_id,
                    "source_row": rownum,
                }

                # WER is metadata only. It is never used to filter training rows.
                wer = str(row.get("wer", "")).strip()
                if wer:
                    try:
                        record["wer"] = float(wer)
                    except ValueError:
                        record["wer"] = wer

                line = json.dumps(record, ensure_ascii=False) + "\n"
                fout.write(line)
                if len(smoke_lines) < args.smoke_rows:
                    smoke_lines.append(line)

                resolution_modes[mode] += 1
                dataset_counts[dataset] += 1

        written = sum(dataset_counts.values())
        report = {
            "csv": str(csv_path),
            "csv_sha256": sha256_file(csv_path),
            "policy": {
                "use_all_csv_rows_for_training": True,
                "dev_split": False,
                "filter_by_wer": False,
                "filter_by_dataset": False,
                "dataset_reweighting": False,
                "text_normalization_in_bundle": False,
                "path_resolution": (
                    "exact CSV audio_path first; mount aliases only if exact path is not a file"
                ),
            },
            "total_csv_rows": total,
            "written_train_rows": written,
            "empty_text_rows": empty_text,
            "missing_audio_rows": missing_audio,
            "dataset_counts": dict(sorted(dataset_counts.items())),
            "resolution_modes": dict(resolution_modes),
            "problem_examples": examples,
        }
        report_tmp.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

        # Atomic failure: do not publish a partial manifest directory.
        if empty_text or missing_audio:
            print(json.dumps(report, ensure_ascii=False, indent=2))
            raise RuntimeError(
                f"PREPARE FAILED: empty_text={empty_text}, missing_audio={missing_audio}. "
                f"Temporary report: {report_tmp}"
            )
        if total == 0:
            raise RuntimeError("CSV contains zero data rows")
        if written != total:
            raise RuntimeError(f"Internal row-count mismatch: total={total}, written={written}")

        smoke_tmp.write_text("".join(smoke_lines), encoding="utf-8")
        split_parts(train_tmp, tmp_dir / "parts" / "train", args.part_rows)
        split_parts(smoke_tmp, tmp_dir / "parts" / "smoke", max(args.smoke_rows, 1))

        os.replace(tmp_dir, final_dir)

        print(json.dumps(report, ensure_ascii=False, indent=2))
        print(f"PREPARE OK: all {total} CSV rows are in the training manifest")
        print(f"Manifest: {final_dir / 'train.jsonl'}")
    except Exception:
        # tmp_dir is intentionally kept on failure so its report can be inspected.
        raise


if __name__ == "__main__":
    main()
