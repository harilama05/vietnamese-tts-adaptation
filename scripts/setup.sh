#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"
REVISION="08be0b4ccbac3e13e374e86fbfead4b4cac343e2"
VENV_DIR="${VENV_DIR:-$PROJECT_ROOT/.venv}"
PYTHON_BIN="${PYTHON_BIN:-python3.12}"
if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi
if [[ ! -d "$OMNIVOICE_REPO" ]]; then
  mkdir -p "$(dirname "$OMNIVOICE_REPO")"
  git clone --no-checkout https://github.com/k2-fsa/OmniVoice.git "$OMNIVOICE_REPO"
  git -C "$OMNIVOICE_REPO" checkout --detach "$REVISION"
elif [[ "$(git -C "$OMNIVOICE_REPO" rev-parse HEAD)" != "$REVISION" ]]; then
  echo "Existing OmniVoice checkout differs from $REVISION; choose a fresh OMNIVOICE_REPO." >&2
  exit 1
fi
"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install \
  -r "$PROJECT_ROOT/requirements.txt" \
  -e "$OMNIVOICE_REPO" -e "$PROJECT_ROOT/norm"
mkdir -p "$BASE_DIR/outputs"
"$VENV_DIR/bin/python" -m pip freeze > "$BASE_DIR/outputs/environment.freeze.txt"
git -C "$OMNIVOICE_REPO" rev-parse HEAD > "$BASE_DIR/outputs/omnivoice_revision.txt"
echo "Setup complete. Configure your CSV/reference files before running training or evaluation."
