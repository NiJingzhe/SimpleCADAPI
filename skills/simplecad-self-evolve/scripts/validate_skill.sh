#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

missing=0
required=(
  "SKILL.md"
  "scripts/install.sh"
  "scripts/with_skill.sh"
  "scripts/jupyter_with_skill.sh"
  "scripts/repl_bootstrap.py"
  "scripts/add_new_case.sh"
  "scripts/evolve_case.py"
  "scripts/validate_skill.sh"
  "references/PROJECT_OVERVIEW.md"
  "references/RUNTIME_INSTALL.md"
  "references/EVOLVE_WORKFLOW.md"
  "references/PROJECT_README.md"
  "references/LICENSE.txt"
  "references/docs/api/README.md"
  "references/docs/core/README.md"
  "cases/simplecad_self_evolve_cases/__init__.py"
  "cases/simplecad_self_evolve_cases/evolve.py"
)

for relative in "${required[@]}"; do
  if [[ ! -e "${SKILL_ROOT}/${relative}" ]]; then
    echo "Missing required path: ${relative}" >&2
    missing=1
  fi
done

if [[ -d "${SKILL_ROOT}/assets/project_snapshot/src" || -d "${SKILL_ROOT}/src" ]]; then
  echo "Unexpected bundled source code found in thin skill package." >&2
  missing=1
fi

if [[ "${missing}" -ne 0 ]]; then
  exit 1
fi

if command -v skills-ref >/dev/null 2>&1; then
  skills-ref validate "${SKILL_ROOT}"
else
  echo "skills-ref not found, skipped external spec validation."
fi

echo "Skill validation succeeded: ${SKILL_ROOT}"
