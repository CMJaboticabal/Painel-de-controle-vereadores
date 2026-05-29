#!/usr/bin/env bash
set -euo pipefail

export PYTHONUTF8=1

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

SESSION_ID="$(date +"%Y-%m-%d_%H-%M-%S")"
export PAINEL_SESSION_ID="$SESSION_ID"

echo
echo "========================================================"
echo "  SISTEMA DE CONTROLE DE TRIBUNA (macOS)"
echo "========================================================"
echo
echo "Iniciando aplicacao..."
echo "Session ID: $PAINEL_SESSION_ID"
echo

if [[ -x ".venv/bin/python" ]]; then
  exec .venv/bin/python main.py
else
  exec python3 main.py
fi
