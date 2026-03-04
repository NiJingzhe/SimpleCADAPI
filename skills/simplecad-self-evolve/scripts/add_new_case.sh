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
  echo "Usage: scripts/add_new_case.sh <path-to-python-file> [--function <name>] [--target <path>]" >&2
  exit 1
fi

exec "${SCRIPT_DIR}/with_skill.sh" -- "${PYTHON_BIN}" "${SCRIPT_DIR}/evolve_case.py" "$@"
