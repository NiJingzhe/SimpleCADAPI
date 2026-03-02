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

if [[ ! -d "${SNAPSHOT_ROOT}/src" ]]; then
  echo "Error: missing skill source path: ${SNAPSHOT_ROOT}/src" >&2
  exit 1
fi

export SIMPLECAD_SKILL_ROOT="${SKILL_ROOT}"
export SIMPLECAD_SKILL_SRC="${SNAPSHOT_ROOT}/src"

if [[ -n "${PYTHONPATH:-}" ]]; then
  export PYTHONPATH="${SIMPLECAD_SKILL_SRC}:${PYTHONPATH}"
else
  export PYTHONPATH="${SIMPLECAD_SKILL_SRC}"
fi

if [[ "${1:-}" == "--print-env" ]]; then
  printf 'export SIMPLECAD_SKILL_ROOT="%s"\n' "${SIMPLECAD_SKILL_ROOT}"
  printf 'export SIMPLECAD_SKILL_SRC="%s"\n' "${SIMPLECAD_SKILL_SRC}"
  printf 'export PYTHONPATH="%s"\n' "${PYTHONPATH}"
  exit 0
fi

if [[ "${1:-}" == "--check" ]]; then
  "${PYTHON_BIN}" - <<'PY'
import importlib

deps = ("numpy", "cadquery")
missing = []
for dep in deps:
    try:
        importlib.import_module(dep)
    except Exception as exc:
        missing.append((dep, str(exc)))

if missing:
    print("Missing runtime dependencies:")
    for name, reason in missing:
        print(f"- {name}: {reason}")
    raise SystemExit(1)

import simplecadapi  # noqa: F401
print("Dependency check passed. simplecadapi import is available.")
PY
  exit 0
fi

if [[ "${1:-}" == "--" ]]; then
  shift
fi

if [[ $# -eq 0 ]]; then
  echo "Skill import path is ready in this shell process."
  echo "Run with wrapper: scripts/with_skill.sh -- python3 your_script.py"
  echo 'Or export vars into current shell: eval "$(scripts/with_skill.sh --print-env)"'
  echo "Check dependencies: scripts/with_skill.sh --check"
  exit 0
fi

exec "$@"
