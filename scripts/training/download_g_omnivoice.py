#!/usr/bin/env python3
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-id", default="g-group-ai-lab/g-omnivoice")
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--revision", default="main", help="Hub revision; resolved to a commit and recorded locally")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    out = Path(args.output_dir).expanduser().resolve()
    if (
        not args.force
        and (out / "config.json").is_file()
        and (out / "audio_tokenizer" / "config.json").is_file()
        and (
            (out / "model.safetensors").is_file()
            or (out / "model.safetensors.index.json").is_file()
            or (out / "pytorch_model.bin").is_file()
        )
    ):
        print(f"MODEL ALREADY PRESENT: {out}")
        return

    from huggingface_hub import HfApi, snapshot_download

    token = os.environ.get("HF_TOKEN") or None
    out.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {args.repo_id} -> {out}")
    try:
        revision = HfApi().model_info(args.repo_id, revision=args.revision, token=token).sha
        snapshot_download(
            repo_id=args.repo_id,
            revision=revision,
            local_dir=str(out),
            token=token,
        )
    except Exception as exc:
        raise SystemExit(
            f"Download failed: {exc}\n"
            "If Hugging Face asks for authentication/access, run `hf auth login` "
            "or export HF_TOKEN, then retry."
        )

    required = [out / "config.json", out / "audio_tokenizer" / "config.json"]
    missing = [str(x) for x in required if not x.is_file()]
    if missing:
        raise SystemExit(f"Downloaded snapshot is incomplete; missing: {missing}")
    (out / "download_provenance.json").write_text(json.dumps({
        "repo_id": args.repo_id, "revision": revision,
    }, indent=2) + "\n", encoding="utf-8")
    print("DOWNLOAD OK")
    print(out)

if __name__ == "__main__":
    main()
