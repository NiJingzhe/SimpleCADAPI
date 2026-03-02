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
  echo "Usage: scripts/add_new_case.sh <python-script-path>" >&2
  exit 1
fi

INPUT_SCRIPT="$1"
shift

if [[ ! -f "${INPUT_SCRIPT}" ]]; then
  echo "Input script not found: ${INPUT_SCRIPT}" >&2
  exit 1
fi

"${SCRIPT_DIR}/validate_skill.sh"

"${PYTHON_BIN}" "${SNAPSHOT_ROOT}/src/simplecadapi/auto_tools/evolution.py"                   "${INPUT_SCRIPT}"                   --evolve_file "${SNAPSHOT_ROOT}/src/simplecadapi/evolve.py"

"${SCRIPT_DIR}/rebuild_exports.sh" --force
"${SCRIPT_DIR}/refresh_docs.sh"

if [[ "${NO_REPACK:-0}" != "1" ]]; then
  "${SCRIPT_DIR}/repack_skill.sh" "$@"
else
  echo "NO_REPACK=1 set, skipping skill repack step."
fi

echo "Add-new-case pipeline completed."
