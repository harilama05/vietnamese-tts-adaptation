#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--train-list", required=True)
    ap.add_argument("--train-config-out", required=True)
    ap.add_argument("--data-config-out", required=True)
    ap.add_argument("--steps", type=int, default=17500)
    ap.add_argument("--resume", default="")
    ap.add_argument("--smoke", action="store_true")
    args = ap.parse_args()

    if args.steps <= 0:
        ap.error("--steps must be positive")

    steps = 10 if args.smoke else args.steps

    # Recovered v2 recipe, with the terminal step aligned to checkpoint-17500.
    # The original frozen config for that run was not present in the archive.
    cfg = {
        "llm_name_or_path": "Qwen/Qwen3-0.6B",
        "audio_vocab_size": 1025,
        "audio_mask_id": 1024,
        "num_audio_codebook": 8,
        "audio_codebook_weights": [8, 8, 6, 6, 4, 4, 2, 2],
        "drop_cond_ratio": 0.1,
        "prompt_ratio_range": [0.0, 0.3],
        "mask_ratio_range": [0.0, 1.0],
        "language_ratio": 0.8,
        "use_pinyin_ratio": 0.0,
        "instruct_ratio": 0.0,
        "only_instruct_ratio": 0.0,
        "resume_from_checkpoint": args.resume or None,
        "init_from_checkpoint": str(Path(args.model).expanduser().resolve()),
        "use_lora": False,
        "learning_rate": 1e-5,
        "weight_decay": 0.01,
        "max_grad_norm": 1.0,
        "steps": steps,
        "seed": 42,
        "warmup_type": "ratio",
        "warmup_ratio": 0.01,
        "warmup_steps": 0,
        "batch_tokens": 8192,
        "gradient_accumulation_steps": 1,
        "num_workers": 2,
        "mixed_precision": "bf16",
        "allow_tf32": True,
        "attn_implementation": "flex_attention",
        "logging_steps": 1 if args.smoke else 50,
        "eval_steps": 10 if args.smoke else 500,
        "save_steps": 10 if args.smoke else 500,
        "keep_last_n_checkpoints": 1 if args.smoke else -1,
    }

    # Full CSV goes into train. No dev split, no row removal.
    data_cfg = {
        "train": [
            {
                "language_id": "vi",
                "manifest_path": [str(Path(args.train_list).expanduser().resolve())],
                "repeat": 1,
            }
        ]
    }

    Path(args.train_config_out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.data_config_out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.train_config_out).write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    Path(args.data_config_out).write_text(
        json.dumps(data_cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print("WROTE", args.train_config_out)
    print("WROTE", args.data_config_out)


if __name__ == "__main__":
    main()
