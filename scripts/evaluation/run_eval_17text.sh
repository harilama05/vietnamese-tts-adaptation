#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-help}"
AUDIT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$AUDIT_DIR/../common.sh"
VENV_DIR="${VENV_DIR:-$BASE_DIR/.venv}"
PYTHON="$VENV_DIR/bin/python"
GPU_ID="${GPU_ID:-0}"
CPU_SET="${CPU_SET:-0-7}"
CPU_CORES="${CPU_CORES:-8}"
FULL_MODEL="${FULL_MODEL:-$BASE_DIR/outputs/g_omnivoice_full/run/checkpoint-17500}"
OMNINORM_ROOT="${OMNINORM_ROOT:-$PROJECT_ROOT}"
PIPELINE_DIR="$AUDIT_DIR"
SOURCE_TEXTS_FILE="${EVAL_SOURCE_TEXTS_FILE:-$PROJECT_ROOT/benchmarks/danhgia_tts.txt}"
RESULT_ROOT="${EVAL_RESULT_ROOT:-$BASE_DIR/outputs/eval_checkpoint_17500}"
CASES_FILE="$RESULT_ROOT/input_documents.jsonl"
if [[ -n "${REF_AUDIO:-}" ]]; then
  SOURCE_REF_AUDIO="$REF_AUDIO"
elif [[ -s "$BASE_DIR/omnivoice_7text_benchmark_ref04/reference/ref04.wav" ]]; then
  SOURCE_REF_AUDIO="$BASE_DIR/omnivoice_7text_benchmark_ref04/reference/ref04.wav"
else
  SOURCE_REF_AUDIO="$BASE_DIR/data/reference/ref04.wav"
fi
if [[ -n "${REF_TEXT_FILE:-}" ]]; then
  SOURCE_REF_TEXT="$REF_TEXT_FILE"
elif [[ -s "$BASE_DIR/omnivoice_7text_benchmark_ref04/reference/ref04.txt" ]]; then
  SOURCE_REF_TEXT="$BASE_DIR/omnivoice_7text_benchmark_ref04/reference/ref04.txt"
else
  SOURCE_REF_TEXT="$BASE_DIR/data/reference/ref04.txt"
fi
REF_AUDIO_OUT="$RESULT_ROOT/reference/ref04.wav"
REF_TEXT_OUT="$RESULT_ROOT/reference/ref04.txt"
CHUNKS="$RESULT_ROOT/shared_chunks.json"
LOG_FILE="$RESULT_ROOT/generation.log"
PID_FILE="$RESULT_ROOT/generation.pid"
ZIP_PATH="${EVAL_ZIP_PATH:-$BASE_DIR/outputs/eval_checkpoint_17500_RESULTS.zip}"

find_repo() {
  if [[ -n "${OMNIVOICE_REPO:-}" && -f "$OMNIVOICE_REPO/omnivoice/models/omnivoice.py" ]]; then printf '%s\n' "$OMNIVOICE_REPO"; return; fi
  local candidate
  for candidate in "$BASE_DIR/_sources/OmniVoice" "$BASE_DIR/OmniVoice"; do
    if [[ -f "$candidate/omnivoice/models/omnivoice.py" ]]; then printf '%s\n' "$candidate"; return; fi
  done
  echo "Cannot find OmniVoice repo. Set OMNIVOICE_REPO=/path/to/OmniVoice" >&2; exit 1
}
REPO_DIR="${OMNIVOICE_REPO:-$BASE_DIR/external/OmniVoice}"
export PYTHONPATH="$REPO_DIR:$OMNINORM_ROOT:${PYTHONPATH:-}"

usage() {
cat <<EOF
Usage: $(basename "$0") ACTION
  check          Verify environment + exact danhgia_tts.txt input
  build-cases    Re-parse danhgia_tts.txt into 17 document JSONL rows
  prepare        Split documents -> TTS chunks, normalize + trace, snapshot inputs/code
  smoke          Generate first 3 chunks with G-OmniVoice full FT
  start          Generate every chunk in background (full FT model)
  status         Show generation progress
  stop           Stop generation
  whisper-score  Whisper each generated chunk independently, compute WER/CER screening
  quality-score  NISQA/DNSMOS/WavLM + signal metrics per chunk
  report         Merge audit CSVs + document summary + review.html
  score-all      whisper-score + quality-score + report
  pack           Zip complete result folder
EOF
}

check_all() {
  [[ -x "$PYTHON" ]] || { echo "Missing venv python: $PYTHON" >&2; exit 1; }
  [[ -s "$SOURCE_TEXTS_FILE" ]] || { echo "Missing source text file: $SOURCE_TEXTS_FILE" >&2; exit 1; }
  [[ -f "$AUDIT_DIR/prepare_news_norm_audit.py" ]] || { echo "Missing audit scripts: $AUDIT_DIR" >&2; exit 1; }
  [[ -f "$PIPELINE_DIR/evaluate_omnivoice_model.py" ]] || { echo "Missing evaluator: $PIPELINE_DIR/evaluate_omnivoice_model.py" >&2; exit 1; }
  [[ -f "$OMNINORM_ROOT/norm/__init__.py" ]] || { echo "Missing normalizer: $OMNINORM_ROOT/norm" >&2; exit 1; }
  [[ -f "$FULL_MODEL/config.json" ]] || { echo "Missing full model config: $FULL_MODEL/config.json" >&2; exit 1; }
  if ! compgen -G "$FULL_MODEL/model*.safetensors" >/dev/null && [[ ! -f "$FULL_MODEL/pytorch_model.bin" ]]; then
    echo "Missing full model weights under: $FULL_MODEL" >&2; exit 1
  fi
  [[ -s "$SOURCE_REF_AUDIO" ]] || { echo "Missing ref audio: $SOURCE_REF_AUDIO" >&2; exit 1; }
  [[ -s "$SOURCE_REF_TEXT" ]] || { echo "Missing ref text: $SOURCE_REF_TEXT" >&2; exit 1; }

  "$PYTHON" - "$OMNINORM_ROOT" "$FULL_MODEL" "$SOURCE_TEXTS_FILE" "$AUDIT_DIR/build_news_cases.py" <<'PY_CHECK'
import importlib, subprocess, sys, tempfile
from pathlib import Path
import torch
root=Path(sys.argv[1]).resolve(); sys.path.insert(0,str(root)); importlib.invalidate_caches(); import norm
print("Normalizer:", norm.__file__); print("Normalizer version:", getattr(norm,"__version__","unknown"))
print("Full fine-tuned model:", Path(sys.argv[2]).resolve())
print("Source texts:", Path(sys.argv[3]).resolve())
with tempfile.TemporaryDirectory() as d:
    out=Path(d)/"cases.jsonl"
    subprocess.run([sys.executable, sys.argv[4], "--input-text", sys.argv[3], "--output", str(out)], check=True, stdout=subprocess.DEVNULL)
    count=sum(1 for x in out.read_text(encoding="utf-8").splitlines() if x.strip())
    print("Parsed documents:", count)
print("Torch:", torch.__version__); print("CUDA build:", torch.version.cuda); print("CUDA available:", torch.cuda.is_available())
if not torch.cuda.is_available(): raise RuntimeError("CUDA unavailable")
print("CHECK OK")
PY_CHECK
}

prepare_reference() { mkdir -p "$RESULT_ROOT/reference"; cp -f "$SOURCE_REF_AUDIO" "$REF_AUDIO_OUT"; cp -f "$SOURCE_REF_TEXT" "$REF_TEXT_OUT"; }
reference_text() { "$PYTHON" - "$REF_TEXT_OUT" <<'PY_REF'
from pathlib import Path
import sys
print(" ".join(Path(sys.argv[1]).read_text(encoding="utf-8-sig").split()))
PY_REF
}
enable_nvidia_libraries() {
  local nvidia_libs
  nvidia_libs="$($PYTHON - <<'PY_LIB'
import site
from pathlib import Path
libs=[]
for root in site.getsitepackages():
    nvidia=Path(root)/"nvidia"
    if nvidia.is_dir(): libs.extend(str(path) for path in nvidia.glob("*/lib") if path.is_dir())
print(":".join(libs))
PY_LIB
)"
  export LD_LIBRARY_PATH="$nvidia_libs:${LD_LIBRARY_PATH:-}"
}

build_cases() {
  mkdir -p "$RESULT_ROOT"
  "$PYTHON" "$AUDIT_DIR/build_news_cases.py" --input-text "$SOURCE_TEXTS_FILE" --output "$CASES_FILE" --overwrite
}

snapshot_code() {
  mkdir -p "$RESULT_ROOT/code_snapshot"
  cp -f "$AUDIT_DIR"/*.py "$AUDIT_DIR"/*.sh "$RESULT_ROOT/code_snapshot/"
  cp -f "$AUDIT_DIR/../common.sh" "$RESULT_ROOT/code_snapshot/common.sh"
  cp -f "$PIPELINE_DIR/evaluate_omnivoice_model.py" "$RESULT_ROOT/code_snapshot/"
  rm -rf "$RESULT_ROOT/code_snapshot/norm"; cp -a "$OMNINORM_ROOT/norm" "$RESULT_ROOT/code_snapshot/norm"
  cp -f "$SOURCE_TEXTS_FILE" "$RESULT_ROOT/danhgia_tts.txt"
}

prepare() {
  check_all
  build_cases
  mkdir -p "$RESULT_ROOT"; prepare_reference
  "$PYTHON" "$AUDIT_DIR/prepare_news_norm_audit.py" --cases "$CASES_FILE" --output-root "$RESULT_ROOT" --omninorm-root "$OMNINORM_ROOT" --max-chars 430 --raw-target-chars 330
  snapshot_code
}

run_full_model() {
  local output_dir="$1" limit="$2" ref_text
  ref_text="$(reference_text)"
  local args=(--name g_omnivoice_full --model "$FULL_MODEL" --chunks "$CHUNKS" --reference-audio "$REF_AUDIO_OUT" --reference-text "$ref_text" --output-dir "$output_dir" --device cuda:0 --seed 42)
  [[ "$limit" -gt 0 ]] && args+=(--max-chunks "$limit")
  CUDA_VISIBLE_DEVICES="$GPU_ID" OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 taskset -c "$CPU_SET" "$PYTHON" -u "$PIPELINE_DIR/evaluate_omnivoice_model.py" "${args[@]}"
}

whisper_score() {
  [[ -f "$RESULT_ROOT/full_model/summary.json" ]] || { echo "Generation incomplete; run start first" >&2; exit 1; }
  enable_nvidia_libraries
  CUDA_VISIBLE_DEVICES="$GPU_ID" OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 taskset -c "$CPU_SET" "$PYTHON" -u "$AUDIT_DIR/score_news_norm_audit.py" --root "$RESULT_ROOT" --model large-v3 --device cuda --compute-type float16 2>&1 | tee "$RESULT_ROOT/whisper.log"
}
quality_score() {
  [[ -f "$RESULT_ROOT/full_model/summary.json" ]] || { echo "Generation incomplete; run start first" >&2; exit 1; }
  enable_nvidia_libraries
  CUDA_VISIBLE_DEVICES="$GPU_ID" OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 taskset -c "$CPU_SET" "$PYTHON" -u "$AUDIT_DIR/score_news_objective.py" --root "$RESULT_ROOT" --reference-audio "$REF_AUDIO_OUT" --speaker-model microsoft/wavlm-base-plus-sv --device cuda:0 --cpu-threads "$CPU_CORES" 2>&1 | tee "$RESULT_ROOT/objective.log"
}
make_report() { "$PYTHON" "$AUDIT_DIR/make_news_audit_report.py" --root "$RESULT_ROOT" 2>&1 | tee "$RESULT_ROOT/report.log"; }
total_chunks() { if [[ -f "$CHUNKS" ]]; then "$PYTHON" - "$CHUNKS" <<'PY_COUNT'
import json,sys
x=json.load(open(sys.argv[1],encoding="utf-8")); print(x["chunk_count"])
PY_COUNT
else echo 0; fi; }

case "$ACTION" in
  check) check_all ;;
  build-cases) check_all; build_cases ;;
  prepare) prepare ;;
  smoke) prepare; run_full_model "$RESULT_ROOT/smoke/full_model" 3 ;;
  start)
    prepare
    if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then echo "Already running PID $(cat "$PID_FILE")"; exit 1; fi
    nohup setsid bash "$0" _run >"$LOG_FILE" 2>&1 < /dev/null & echo $! > "$PID_FILE"
    echo "Started PID $(cat "$PID_FILE")"; echo "Log: $LOG_FILE" ;;
  _run) trap 'rm -f "$PID_FILE"' EXIT; run_full_model "$RESULT_ROOT/full_model" 0 ;;
  status)
    total="$(total_chunks)"; done_count=0
    [[ -f "$RESULT_ROOT/full_model/results.jsonl" ]] && done_count="$(wc -l < "$RESULT_ROOT/full_model/results.jsonl")"
    if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then echo "RUNNING PID $(cat "$PID_FILE")"; ps -p "$(cat "$PID_FILE")" -o pid,etime,%cpu,%mem,stat,cmd; else echo "NOT RUNNING"; fi
    echo "full_model: $done_count/$total chunks"; [[ -f "$LOG_FILE" ]] && tail -30 "$LOG_FILE" ;;
  stop)
    if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then kill -- -"$(cat "$PID_FILE")" 2>/dev/null || kill "$(cat "$PID_FILE")"; echo "Stopped PID $(cat "$PID_FILE")"; else echo "No running generation"; fi
    rm -f "$PID_FILE" ;;
  whisper-score) whisper_score ;;
  quality-score) quality_score ;;
  report) make_report ;;
  score-all) whisper_score; quality_score; make_report ;;
  pack)
    [[ -f "$RESULT_ROOT/audit_results.csv" ]] || { echo "Run score-all first" >&2; exit 1; }
    rm -f "$ZIP_PATH"; parent="$(dirname "$RESULT_ROOT")"; name="$(basename "$RESULT_ROOT")"; (cd "$parent" && zip -r "$ZIP_PATH" "$name"); echo "Created: $ZIP_PATH" ;;
  help|-h|--help) usage ;;
  *) usage; exit 2 ;;
esac
