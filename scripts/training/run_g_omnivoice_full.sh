#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-help}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

source "$SCRIPT_DIR/../common.sh"
CSV="${CSV:-$BASE_DIR/data/combined_train_shuffled.csv}"
VENV_DIR="${VENV_DIR:-$BASE_DIR/.venv}"
PYTHON="$VENV_DIR/bin/python"
ACCELERATE="$VENV_DIR/bin/accelerate"

GPU_IDS="${GPU_IDS:-0}"
NJ_PER_GPU="${NJ_PER_GPU:-3}"
STEPS="${STEPS:-17500}"

MODEL_REPO="${MODEL_REPO:-g-group-ai-lab/g-omnivoice}"
MODEL_DIR="${MODEL_DIR:-$BASE_DIR/models/g-omnivoice}"

WORK_ROOT="${WORK_ROOT:-$BASE_DIR/data/g_omnivoice}"
MANIFEST_DIR="$WORK_ROOT/manifests"
TOKEN_ROOT="$WORK_ROOT/tokens"
CONFIG_DIR="$WORK_ROOT/config"

RUN_ROOT="${RUN_ROOT:-$BASE_DIR/outputs/g_omnivoice_full}"
OUTPUT_DIR="$RUN_ROOT/run"
SMOKE_OUTPUT="$RUN_ROOT/smoke"
LOG_FILE="$RUN_ROOT/launcher.log"
PID_FILE="$RUN_ROOT/train.pid"

find_repo() {
  local c
  if [[ -n "${OMNIVOICE_REPO:-}" && -f "$OMNIVOICE_REPO/omnivoice/cli/train.py" ]]; then
    echo "$OMNIVOICE_REPO"
    return
  fi
  for c in "$BASE_DIR/_sources/OmniVoice" "$BASE_DIR/OmniVoice"; do
    if [[ -f "$c/omnivoice/cli/train.py" ]]; then
      echo "$c"
      return
    fi
  done
  echo "Cannot find OmniVoice source. Set OMNIVOICE_REPO=/path/to/OmniVoice" >&2
  exit 1
}

REPO_DIR="${OMNIVOICE_REPO:-$BASE_DIR/external/OmniVoice}"
export PYTHONPATH="$REPO_DIR:${PYTHONPATH:-}"
export HF_HOME="${HF_HOME:-$BASE_DIR/.cache/huggingface}"

basic_check() {
  [[ -x "$PYTHON" ]] || { echo "Missing Python: $PYTHON" >&2; exit 1; }
  [[ -x "$ACCELERATE" ]] || { echo "Missing accelerate: $ACCELERATE" >&2; exit 1; }
  [[ -s "$CSV" ]] || { echo "Missing CSV: $CSV" >&2; exit 1; }
  [[ -f "$REPO_DIR/omnivoice/cli/train.py" ]] || { echo "Bad OmniVoice repo: $REPO_DIR" >&2; exit 1; }
}

require_idle() {
  if [[ -f "$PID_FILE" ]]; then
    local active_pid
    active_pid="$(cat "$PID_FILE")"
    if [[ "$active_pid" =~ ^[0-9]+$ ]] && kill -0 "$active_pid" 2>/dev/null; then
      echo "Training already running: PID=$active_pid" >&2
      exit 1
    fi
  fi
}

gpu_check() {
  CUDA_VISIBLE_DEVICES="$GPU_IDS" "$PYTHON" - <<'PY'
import torch
print("torch:", torch.__version__)
print("CUDA build:", torch.version.cuda)
print("CUDA available:", torch.cuda.is_available())
print("visible GPU count:", torch.cuda.device_count())
if not torch.cuda.is_available():
    raise SystemExit("CUDA unavailable")
for i in range(torch.cuda.device_count()):
    p = torch.cuda.get_device_properties(i)
    print(f"GPU {i}: {p.name} | {p.total_memory/2**30:.1f} GiB")
print("BF16 supported:", torch.cuda.is_bf16_supported())
if not torch.cuda.is_bf16_supported():
    raise SystemExit("This BF16 recipe requires a GPU with BF16 support")
PY
  nvidia-smi -i "$GPU_IDS" || true
}

require_model() {
  [[ -f "$MODEL_DIR/config.json" ]] || {
    echo "G-OmniVoice is not present at $MODEL_DIR. Run download-model first." >&2
    exit 1
  }
  [[ -d "$MODEL_DIR/audio_tokenizer" ]] || {
    echo "Missing bundled audio_tokenizer under $MODEL_DIR" >&2
    exit 1
  }
}

latest_checkpoint() {
  [[ -d "$OUTPUT_DIR" ]] || return 0
  find "$OUTPUT_DIR" -maxdepth 1 -type d -name 'checkpoint-*' -printf '%f\n' 2>/dev/null \
    | awk -F- '/^checkpoint-[0-9]+$/ {print $2}' \
    | sort -n | tail -1 \
    | awk -v r="$OUTPUT_DIR" 'NF {print r "/checkpoint-" $1}'
}

make_config() {
  local mode="$1"
  local resume="${2:-}"
  mkdir -p "$CONFIG_DIR" "$RUN_ROOT"

  if [[ "$mode" == "smoke" ]]; then
    GEN_CFG="$CONFIG_DIR/train_smoke.json"
    GEN_DATA="$CONFIG_DIR/data_smoke.json"
    GEN_OUT="$SMOKE_OUTPUT"
    "$PYTHON" "$SCRIPT_DIR/make_train_config.py" \
      --model "$MODEL_DIR" \
      --train-list "$TOKEN_ROOT/smoke/data.lst" \
      --train-config-out "$GEN_CFG" \
      --data-config-out "$GEN_DATA" \
      --smoke
  else
    GEN_CFG="$CONFIG_DIR/train.json"
    GEN_DATA="$CONFIG_DIR/data.json"
    GEN_OUT="$OUTPUT_DIR"
    args=(
      --model "$MODEL_DIR"
      --train-list "$TOKEN_ROOT/train/data.lst"
      --train-config-out "$GEN_CFG"
      --data-config-out "$GEN_DATA"
      --steps "$STEPS"
    )
    [[ -n "$resume" ]] && args+=(--resume "$resume")
    "$PYTHON" "$SCRIPT_DIR/make_train_config.py" "${args[@]}"
  fi
}

launch_foreground() {
  CUDA_VISIBLE_DEVICES="$GPU_IDS" \
  OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
    "$ACCELERATE" launch --num_processes 1 \
      -m omnivoice.cli.train \
      --train_config "$GEN_CFG" \
      --data_config "$GEN_DATA" \
      --output_dir "$GEN_OUT"
}

launch_background() {
  mkdir -p "$RUN_ROOT"
  if [[ -f "$PID_FILE" ]]; then
    oldpid="$(cat "$PID_FILE" 2>/dev/null || true)"
    if [[ -n "$oldpid" ]] && kill -0 "$oldpid" 2>/dev/null; then
      echo "Training already running: PID=$oldpid" >&2
      exit 1
    fi
  fi

  nohup setsid env \
    CUDA_VISIBLE_DEVICES="$GPU_IDS" \
    PYTHONPATH="$PYTHONPATH" \
    HF_HOME="$HF_HOME" \
    OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
    "$ACCELERATE" launch --num_processes 1 \
      -m omnivoice.cli.train \
      --train_config "$GEN_CFG" \
      --data_config "$GEN_DATA" \
      --output_dir "$GEN_OUT" \
    >"$LOG_FILE" 2>&1 < /dev/null &

  echo $! > "$PID_FILE"
  echo "Started FULL fine-tune PID=$(cat "$PID_FILE")"
  echo "Log: $LOG_FILE"
}

case "$ACTION" in
  check)
    basic_check
    echo "Repo:      $REPO_DIR"
    echo "Venv:      $VENV_DIR"
    echo "CSV:       $CSV"
    echo "GPU IDs:   $GPU_IDS"
    echo "Model:     $MODEL_DIR"
    echo "Work root: $WORK_ROOT"
    echo "Output:    $OUTPUT_DIR"
    echo
    "$PYTHON" - "$CSV" <<'PY'
import csv,sys
p=sys.argv[1]
with open(p, encoding="utf-8-sig", newline="") as f:
    r=csv.DictReader(f)
    print("CSV columns:", r.fieldnames)
    row=next(r,None)
    print("First dataset:", None if row is None else row.get("dataset"))
    print("First audio_path:", None if row is None else row.get("audio_path"))
    print("First text chars:", 0 if row is None else len(row.get("text") or ""))
PY
    echo
    gpu_check
    ;;

  download-model)
    basic_check
    "$PYTHON" "$SCRIPT_DIR/download_g_omnivoice.py" \
      --repo-id "$MODEL_REPO" \
      --output-dir "$MODEL_DIR" --revision "${MODEL_REVISION:-main}"
    ;;

  prepare)
    basic_check
    args=(
      --csv "$CSV"
      --output-dir "$MANIFEST_DIR"
      --part-rows 50000
      --smoke-rows 256
    )
    [[ -n "${AUDIO_FALLBACK_ROOT:-}" ]] && args+=(--fallback-root "$AUDIO_FALLBACK_ROOT")
    "$PYTHON" "$SCRIPT_DIR/prepare_manifest.py" "${args[@]}"
    ;;

  smoke)
    basic_check
    require_model
    [[ -s "$MANIFEST_DIR/smoke.jsonl" ]] || { echo "Run prepare first." >&2; exit 1; }

    if [[ -d "$SMOKE_OUTPUT" ]]; then
      echo "Smoke output exists: $SMOKE_OUTPUT. Set RUN_ROOT to a fresh directory." >&2
      exit 1
    fi
    "$PYTHON" "$SCRIPT_DIR/tokenize_parts.py" \
      --parts-dir "$MANIFEST_DIR/parts/smoke" \
      --output-dir "$TOKEN_ROOT/smoke" \
      --tokenizer-path "$MODEL_DIR/audio_tokenizer" \
      --gpu-ids "$GPU_IDS" \
      --nj-per-gpu "$NJ_PER_GPU"

    make_config smoke
    echo "Running 10-step FULL fine-tune smoke test with recovered recipe..."
    launch_foreground
    ;;

  tokenize)
    basic_check
    require_model
    [[ -s "$MANIFEST_DIR/train.jsonl" ]] || { echo "Run prepare first." >&2; exit 1; }

    "$PYTHON" "$SCRIPT_DIR/tokenize_parts.py" \
      --parts-dir "$MANIFEST_DIR/parts/train" \
      --output-dir "$TOKEN_ROOT/train" \
      --tokenizer-path "$MODEL_DIR/audio_tokenizer" \
      --gpu-ids "$GPU_IDS" \
      --nj-per-gpu "$NJ_PER_GPU"
    ;;

  start)
    basic_check
    require_model
    require_idle
    [[ -s "$TOKEN_ROOT/train/data.lst" ]] || { echo "Run tokenize first." >&2; exit 1; }

    if [[ -n "$(latest_checkpoint)" ]]; then
      echo "Existing checkpoint found. Use resume or delete the run intentionally." >&2
      exit 1
    fi

    make_config train
    mkdir -p "$OUTPUT_DIR"
    cp -f "$GEN_CFG" "$RUN_ROOT/frozen_train_config.json"
    cp -f "$GEN_DATA" "$RUN_ROOT/frozen_data_config.json"
    launch_background
    ;;

  resume)
    basic_check
    require_model
    require_idle
    mkdir -p "$CONFIG_DIR"
    ckpt="$(latest_checkpoint)"
    [[ -n "$ckpt" ]] || { echo "No checkpoint found to resume." >&2; exit 1; }
    [[ -s "$RUN_ROOT/frozen_train_config.json" ]] || { echo "Missing frozen training config." >&2; exit 1; }
    [[ -s "$RUN_ROOT/frozen_data_config.json" ]] || { echo "Missing frozen data config." >&2; exit 1; }

    "$PYTHON" - "$RUN_ROOT/frozen_train_config.json" "$CONFIG_DIR/train_resume.json" "$ckpt" <<'PY'
import json,sys
src,dst,ckpt=sys.argv[1:]
x=json.load(open(src,encoding="utf-8"))
x["resume_from_checkpoint"]=ckpt
json.dump(x,open(dst,"w",encoding="utf-8"),ensure_ascii=False,indent=2)
PY
    cp -f "$RUN_ROOT/frozen_data_config.json" "$CONFIG_DIR/data_resume.json"
    GEN_CFG="$CONFIG_DIR/train_resume.json"
    GEN_DATA="$CONFIG_DIR/data_resume.json"
    GEN_OUT="$OUTPUT_DIR"
    launch_background
    ;;

  status)
    if [[ -f "$PID_FILE" ]]; then
      pid="$(cat "$PID_FILE")"
      if kill -0 "$pid" 2>/dev/null; then
        echo "RUNNING PID=$pid"
        ps -p "$pid" -o pid,ppid,etime,%cpu,%mem,stat,cmd || true
      else
        echo "NOT RUNNING (stale PID=$pid)"
      fi
    else
      echo "NOT RUNNING"
    fi
    echo
    echo "Checkpoints:"
    find "$OUTPUT_DIR" -maxdepth 1 -type d -name 'checkpoint-*' -printf '%f\n' 2>/dev/null | sort -V | tail -20 || true
    echo
    echo "Recent log:"
    tail -60 "$LOG_FILE" 2>/dev/null || true
    ;;

  stop)
    if [[ ! -f "$PID_FILE" ]]; then
      echo "No PID file"
      exit 0
    fi
    pid="$(cat "$PID_FILE")"
    if kill -0 "$pid" 2>/dev/null; then
      kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid"
      echo "Sent TERM to process group $pid"
    else
      echo "PID $pid is not running"
    fi
    ;;

  help|-h|--help|*)
    cat <<EOF
Usage: bash run_g_omnivoice_full.sh ACTION

Actions:
  check
  download-model
  prepare
  smoke
  tokenize
  start
  resume
  status
  stop

Training defaults (recovered v2 recipe, target checkpoint-17500):
  base checkpoint: g-group-ai-lab/g-omnivoice
  full FT:         use_lora=false
  steps:           17500
  learning rate:   1e-5
  batch_tokens:    8192
  grad accum:      1
  precision:       bf16
  attention:       flex_attention
  warmup ratio:    0.01
  seed:            42
  save:            every 500 steps

All CSV rows are included in the training manifest. No dev split/filter/reweight.
EOF
    ;;
esac
