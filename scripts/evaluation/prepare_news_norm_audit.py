#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import dataclasses
import hashlib
import importlib
import json
import re
import sys
import unicodedata
from pathlib import Path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def tree_sha256(root: Path) -> str:
    h = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        rel = path.relative_to(root).as_posix().encode()
        h.update(rel + b"\0")
        with path.open("rb") as f:
            for block in iter(lambda: f.read(1024 * 1024), b""):
                h.update(block)
    return h.hexdigest()


def metric_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text).lower()
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def residual_patterns(text: str) -> list[str]:
    checks = [
        ("digit", r"\d"),
        ("percent_symbol", r"[%‰]"),
        ("currency_symbol", r"[$€£₫]"),
        ("numeric_range", r"\d\s*[–—-]\s*\d"),
        ("numeric_slash", r"\d\s*/\s*\d"),
        ("clock_colon", r"\d\s*:\s*\d"),
        ("currency_code", r"\b(?:USD|VND|VNĐ|EUR|GBP|JPY|CNY|KRW)\b"),
        ("news_acronym", r"\b(?:AI|APEC|ASEAN|BRICS|D\.C\.|GDP|CPI|PMI|FDI|FED|ECB|WHO|NATO|OPEC|GRDP|UBND|JETP)\b"),
        ("unit_slash", r"\b[A-Za-zÀ-ỹ]+\s*/\s*[A-Za-zÀ-ỹ]+\b"),
        ("url_or_email", r"(?:https?://|www\.|\b[\w.+-]+@[\w.-]+\.|\b[\w-]+\.(?:com|vn|org|net|io)\b)"),
        ("latin_acronym", r"\b[A-ZĐ]{2,}(?:[-+][A-Z0-9]+)*\b"),
    ]
    return [name for name, pattern in checks if re.search(pattern, text)]


def read_documents(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for line_no, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_no}: invalid JSON: {exc}") from exc
        doc_id = str(row.get("document_id") or row.get("case_id") or "").strip()
        raw_text = str(row.get("raw_text", "")).strip()
        if not doc_id or not raw_text:
            raise ValueError(f"{path}:{line_no}: document_id/case_id and raw_text required")
        if doc_id in seen:
            raise ValueError(f"Duplicate document_id: {doc_id}")
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", doc_id):
            raise ValueError(f"Unsafe document_id {doc_id!r}")
        seen.add(doc_id)
        rows.append({
            "document_id": doc_id,
            "source_label": str(row.get("source_label", doc_id)).strip() or doc_id,
            "category": str(row.get("category", "news")).strip() or "news",
            "raw_text": re.sub(r"\s+", " ", raw_text).strip(),
            "expected_text": str(row.get("expected_text", "")).strip(),
            "note": str(row.get("note", "")).strip(),
        })
    if not rows:
        raise RuntimeError(f"No documents found: {path}")
    return rows


def split_sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    # News prose: split primarily after sentence-final punctuation.
    parts = re.split(r"(?<=[.!?])\s+(?=[\"'“”‘’(]*[A-ZÀ-Ỹ0-9])", text)
    return [p.strip() for p in parts if p.strip()]


def split_long_once(text: str, target: int) -> tuple[str, str]:
    if len(text) <= target:
        return text, ""
    lo = max(1, int(target * 0.55))
    hi = min(len(text) - 1, target)
    candidates: list[int] = []
    for pat in (r";\s+", r",\s+", r":\s+", r"\s+[–—-]\s+", r"\s+"):
        for m in re.finditer(pat, text[: hi + 1]):
            if m.end() >= lo:
                candidates.append(m.end())
        if candidates:
            break
    cut = max(candidates) if candidates else hi
    left = text[:cut].strip()
    right = text[cut:].strip()
    if not left or not right:
        cut = max(1, min(len(text) - 1, target))
        left, right = text[:cut].strip(), text[cut:].strip()
    return left, right


def raw_chunks(text: str, target_chars: int) -> list[str]:
    sentences = split_sentences(text)
    atoms: list[str] = []
    for sent in sentences:
        pending = sent
        while len(pending) > target_chars:
            left, right = split_long_once(pending, target_chars)
            atoms.append(left)
            pending = right
        if pending:
            atoms.append(pending)

    out: list[str] = []
    current = ""
    for atom in atoms:
        candidate = atom if not current else current + " " + atom
        if len(candidate) <= target_chars:
            current = candidate
        else:
            if current:
                out.append(current)
            current = atom
    if current:
        out.append(current)
    return out


def normalize_and_fit(raw: str, normalizer, max_chars: int) -> list[tuple[str, object, str]]:
    """Return final (raw_chunk, normalization_result, normalized_text) rows <= max_chars."""
    result = normalizer.normalize_with_trace(raw)
    normalized = re.sub(r"\s+", " ", unicodedata.normalize("NFC", result.text)).strip()
    if not normalized:
        raise RuntimeError("Normalizer returned empty text")
    if len(normalized) <= max_chars:
        return [(raw, result, normalized)]

    # Expansion made it too long. Split raw conservatively and retry recursively.
    target = max(80, min(len(raw) - 1, int(len(raw) * max_chars / max(len(normalized), 1) * 0.88)))
    left, right = split_long_once(raw, target)
    if not right or left == raw:
        raise RuntimeError(
            f"Could not split expanded chunk: raw={len(raw)} normalized={len(normalized)} max={max_chars}"
        )
    return normalize_and_fit(left, normalizer, max_chars) + normalize_and_fit(right, normalizer, max_chars)


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", type=Path, required=True, help="Document JSONL generated from danhgia_tts.txt")
    ap.add_argument("--output-root", type=Path, required=True)
    ap.add_argument("--omninorm-root", type=Path, required=True)
    ap.add_argument("--max-chars", type=int, default=430, help="Maximum normalized chars per TTS chunk")
    ap.add_argument("--raw-target-chars", type=int, default=330, help="Initial raw chunk target before normalization")
    args = ap.parse_args()

    cases_path = args.cases.expanduser().resolve()
    output = args.output_root.expanduser().resolve()
    norm_root = args.omninorm_root.expanduser().resolve()
    norm_pkg = norm_root / "norm"
    if not norm_pkg.is_dir():
        raise FileNotFoundError(norm_pkg)

    sys.path.insert(0, str(norm_root))
    importlib.invalidate_caches()
    norm = importlib.import_module("norm")
    normalizer = norm.Normalizer()
    version = getattr(norm, "__version__", "unknown")

    output.mkdir(parents=True, exist_ok=True)
    documents = read_documents(cases_path)
    prepared: list[dict[str, object]] = []
    traces: list[dict[str, object]] = []
    chunks: list[dict[str, object]] = []
    document_manifest: list[dict[str, object]] = []

    suspicious_preserved_kinds = {
        "numeric_structure", "structured_quantity", "long_expression", "long_token",
        "compound", "protected", "scientific", "extended_version", "unit_group",
    }

    for doc in documents:
        initial = raw_chunks(doc["raw_text"], args.raw_target_chars)
        finals: list[tuple[str, object, str]] = []
        for raw in initial:
            finals.extend(normalize_and_fit(raw, normalizer, args.max_chars))

        document_manifest.append({
            "document_id": doc["document_id"],
            "source_label": doc["source_label"],
            "category": doc["category"],
            "raw_text": doc["raw_text"],
            "raw_chars": len(doc["raw_text"]),
            "chunk_count": len(finals),
            "note": doc["note"],
        })

        for chunk_index, (raw_chunk, result, normalized) in enumerate(finals, 1):
            chunk_id = f"{doc['document_id']}_chunk_{chunk_index:02d}"
            span_dicts = [dataclasses.asdict(span) for span in result.spans]
            reasons = sorted({str(s.get("reason")) for s in span_dicts if s.get("reason")})
            preserved = [
                s for s in span_dicts
                if s.get("status") == "preserved" and s.get("kind") in suspicious_preserved_kinds
            ]
            residual = residual_patterns(normalized)

            warnings: list[str] = []
            if preserved:
                warnings.append("preserved_structured_span")
            if reasons:
                warnings.append("trace_reason")
            if residual:
                warnings.append("residual_pattern")
            norm_auto_status = "NORM_REVIEW" if warnings else "AUTO_CLEAN_UNVERIFIED"

            row: dict[str, object] = {
                "case_id": chunk_id,
                "document_id": doc["document_id"],
                "source_label": doc["source_label"],
                "chunk_index": chunk_index,
                "chunk_count_in_document": len(finals),
                "category": doc["category"],
                "raw_text": raw_chunk,
                "normalized_text": normalized,
                "expected_text": "",
                "expected_match": "",
                "norm_auto_status": norm_auto_status,
                "norm_warning": ";".join(warnings),
                "trace_reasons": ";".join(reasons),
                "residual_patterns": ";".join(residual),
                "trace_span_count": len(span_dicts),
                "preserved_suspicious_count": len(preserved),
                "note": doc["note"],
            }
            prepared.append(row)
            traces.append({
                "case_id": chunk_id,
                "document_id": doc["document_id"],
                "source_label": doc["source_label"],
                "chunk_index": chunk_index,
                "raw_text": raw_chunk,
                "normalized_text": normalized,
                "spans": span_dicts,
            })
            chunks.append({
                "text_id": doc["document_id"],
                "chunk_index": chunk_index,
                "chunk_id": chunk_id,
                "raw_chunk": raw_chunk,
                "tts_text": normalized,
                "tts_chars": len(normalized),
            })

    content_blob = json.dumps(chunks, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    content_sha256 = hashlib.sha256(content_blob).hexdigest()

    with (output / "prepared_cases.jsonl").open("w", encoding="utf-8") as f:
        for row in prepared:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    with (output / "norm_trace.jsonl").open("w", encoding="utf-8") as f:
        for row in traces:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    with (output / "documents.jsonl").open("w", encoding="utf-8") as f:
        for row in document_manifest:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    fields = [
        "case_id", "document_id", "source_label", "chunk_index", "chunk_count_in_document",
        "category", "raw_text", "normalized_text", "expected_text", "expected_match",
        "norm_auto_status", "norm_warning", "trace_reasons", "residual_patterns",
        "trace_span_count", "preserved_suspicious_count", "note",
    ]
    write_csv(output / "prepared_cases.csv", prepared, fields)
    write_csv(
        output / "documents.csv",
        document_manifest,
        ["document_id", "source_label", "category", "raw_text", "raw_chars", "chunk_count", "note"],
    )

    chunk_payload = {
        "normalizer": "Vietnamese TTS Normalizer",
        "normalizer_version": version,
        "normalizer_module": str(Path(norm.__file__).resolve()),
        "normalizer_tree_sha256": tree_sha256(norm_pkg),
        "source_cases": str(cases_path),
        "source_cases_sha256": sha256_file(cases_path),
        "max_chars": args.max_chars,
        "raw_target_chars": args.raw_target_chars,
        "text_count": len(documents),
        "chunk_count": len(chunks),
        "content_sha256": content_sha256,
        "chunks": chunks,
    }
    (output / "shared_chunks.json").write_text(
        json.dumps(chunk_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    config = {
        "normalizer_version": version,
        "normalizer_module": str(Path(norm.__file__).resolve()),
        "normalizer_tree_sha256": tree_sha256(norm_pkg),
        "cases_path": str(cases_path),
        "cases_sha256": sha256_file(cases_path),
        "document_count": len(documents),
        "chunk_count": len(chunks),
        "max_chars": args.max_chars,
        "raw_target_chars": args.raw_target_chars,
        "content_sha256": content_sha256,
    }
    (output / "prepare_config.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    flagged = sum(row["norm_auto_status"] == "NORM_REVIEW" for row in prepared)
    print(f"Prepared {len(documents)} documents -> {len(prepared)} TTS chunks")
    print(f"Normalizer version: {version}")
    print(f"Norm auto-review candidates: {flagged}/{len(prepared)} chunks")
    print(f"Saved: {output / 'documents.csv'}")
    print(f"Saved: {output / 'prepared_cases.csv'}")
    print(f"Saved: {output / 'norm_trace.jsonl'}")
    print(f"Saved: {output / 'shared_chunks.json'}")


if __name__ == "__main__":
    main()
