#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  PYTHON_BIN="python"
fi

if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  echo "Error: python interpreter not found." >&2
  exit 1
fi

PYTHON_BIN="$(command -v "${PYTHON_BIN}")"
export PYTHON_BIN

if [[ $# -lt 1 ]]; then
  echo "Usage: scripts/jupyter_with_skill.sh <lab|notebook> [-- <extra args>]" >&2
  exit 1
fi

JUPYTER_APP="$1"
shift

case "${JUPYTER_APP}" in
  lab|notebook) ;;
  *)
    echo "Error: first argument must be 'lab' or 'notebook'." >&2
    exit 1
    ;;
esac

if [[ "${1:-}" == "--" ]]; then
  shift
fi

exec "${SCRIPT_DIR}/with_skill.sh" --ensure-jupyter -- "${PYTHON_BIN}" -m jupyter "${JUPYTER_APP}" "$@"
