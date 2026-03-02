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

missing=0
required=(
  "SKILL.md"
  "scripts/with_skill.sh"
  "scripts/jupyter_with_skill.sh"
  "scripts/repl_bootstrap.py"
  "scripts/add_new_case.sh"
  "scripts/rebuild_exports.sh"
  "scripts/refresh_docs.sh"
  "scripts/repack_skill.sh"
  "scripts/validate_skill.sh"
  "references/PROJECT_OVERVIEW.md"
  "references/API_INDEX.md"
  "references/CORE_INDEX.md"
  "references/EVOLVE_WORKFLOW.md"
  "assets/project_snapshot/src/simplecadapi/operations.py"
  "assets/project_snapshot/src/simplecadapi/evolve.py"
  "assets/project_snapshot/docs/api/README.md"
)

for relative in "${required[@]}"; do
  if [[ ! -e "${SKILL_ROOT}/${relative}" ]]; then
    echo "Missing required path: ${relative}" >&2
    missing=1
  fi
done

if [[ "${missing}" -ne 0 ]]; then
  exit 1
fi

if command -v skills-ref >/dev/null 2>&1; then
  skills-ref validate "${SKILL_ROOT}"
else
  echo "skills-ref not found, skipped external spec validation."
fi

echo "Skill validation succeeded: ${SKILL_ROOT}"
