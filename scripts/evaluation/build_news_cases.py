#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

HEADER_RE = re.compile(r"^\s*Văn\s+bản\s+(\d+)\s*:\s*$", re.IGNORECASE)


def parse_documents(path: Path) -> list[dict[str, str]]:
    text = path.read_text(encoding="utf-8-sig")
    docs: list[dict[str, str]] = []
    current_no: int | None = None
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_no, current_lines
        if current_no is None:
            return
        raw = " ".join(line.strip() for line in current_lines if line.strip())
        raw = re.sub(r"\s+", " ", raw).strip()
        if not raw:
            raise ValueError(f"Văn bản {current_no} is empty")
        docs.append({
            "case_id": f"text_{current_no:02d}",
            "document_id": f"text_{current_no:02d}",
            "source_label": f"Văn bản {current_no}",
            "category": "news",
            "raw_text": raw,
            "expected_text": "",
            "note": "",
        })
        current_no = None
        current_lines = []

    for line_no, line in enumerate(text.splitlines(), 1):
        m = HEADER_RE.match(line)
        if m:
            flush()
            current_no = int(m.group(1))
            current_lines = []
            continue
        if current_no is None:
            if line.strip():
                raise ValueError(
                    f"Unexpected text before first 'Văn bản N:' heading at line {line_no}: {line!r}"
                )
            continue
        current_lines.append(line)
    flush()

    if not docs:
        raise RuntimeError(f"No 'Văn bản N:' blocks found in {path}")

    ids = [d["case_id"] for d in docs]
    if len(ids) != len(set(ids)):
        raise RuntimeError("Duplicate document numbers found")
    return docs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-text", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    src = args.input_text.expanduser().resolve()
    out = args.output.expanduser().resolve()
    if not src.is_file():
        raise FileNotFoundError(src)
    if out.exists() and not args.overwrite:
        raise FileExistsError(f"Already exists: {out}. Use --overwrite if intended.")

    docs = parse_documents(src)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for row in docs:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"Parsed {len(docs)} documents from: {src}")
    print(f"Saved: {out}")
    for row in docs:
        print(f"  {row['case_id']}: {len(row['raw_text'])} chars")


if __name__ == "__main__":
    main()
