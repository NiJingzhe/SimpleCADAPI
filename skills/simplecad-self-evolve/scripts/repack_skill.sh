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

SKILLS_ROOT="$(cd "${SKILL_ROOT}/.." && pwd)"
SKILL_NAME="$(basename "${SKILL_ROOT}")"
TEMP_ROOT="$(mktemp -d)"
trap 'rm -rf "${TEMP_ROOT}"' EXIT

"${PYTHON_BIN}" "${SNAPSHOT_ROOT}/src/simplecadapi/auto_tools/skill_pack.py"                   --project-root "${SNAPSHOT_ROOT}"                   --output-root "${TEMP_ROOT}"                   --skill-name "${SKILL_NAME}"                   "$@"

GENERATED_SKILL="${TEMP_ROOT}/${SKILL_NAME}"

"${PYTHON_BIN}" - "${GENERATED_SKILL}" "${SKILL_ROOT}" <<'PY'
import shutil
import sys
from pathlib import Path

source = Path(sys.argv[1])
target = Path(sys.argv[2])

if not source.exists():
    raise SystemExit(f"Generated skill path does not exist: {source}")

for item in list(target.iterdir()):
    if item.is_dir():
        shutil.rmtree(item)
    else:
        item.unlink()

for item in source.iterdir():
    destination = target / item.name
    if item.is_dir():
        shutil.copytree(item, destination)
    else:
        shutil.copy2(item, destination)
PY

echo "Skill repacked: ${SKILL_ROOT}"
