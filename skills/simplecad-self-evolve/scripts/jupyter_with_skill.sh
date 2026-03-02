#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SNAPSHOT_ROOT="${SKILL_ROOT}/assets/project_snapshot"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  PYTHON_BIN="python"
fi

if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  echo "Error: python interpreter not found." >&2
  exit 1
fi

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

if ! "${PYTHON_BIN}" -m jupyter --version >/dev/null 2>&1; then
  echo "Error: jupyter is not available in current python environment." >&2
  echo "Install it with: ${PYTHON_BIN} -m pip install jupyterlab" >&2
  exit 1
fi

exec "${SCRIPT_DIR}/with_skill.sh" -- "${PYTHON_BIN}" -m jupyter "${JUPYTER_APP}" "$@"
