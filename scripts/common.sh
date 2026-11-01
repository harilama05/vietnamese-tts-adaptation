#!/usr/bin/env bash
# Load machine-specific settings once and export them to background jobs.
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PROJECT_ROOT
if [[ -f "$PROJECT_ROOT/configs/local.env" ]]; then
  set -a
  source "$PROJECT_ROOT/configs/local.env"
  set +a
fi
export BASE_DIR="${BASE_DIR:-$PROJECT_ROOT}"
export OMNIVOICE_REPO="${OMNIVOICE_REPO:-$PROJECT_ROOT/external/OmniVoice}"
