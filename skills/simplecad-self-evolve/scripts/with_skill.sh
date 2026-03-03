#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
CASES_ROOT="${SKILL_ROOT}/cases"
CASES_MODULE="simplecad_self_evolve_cases"
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

export SIMPLECAD_SKILL_ROOT="${SKILL_ROOT}"
export SIMPLECAD_CASES_ROOT="${CASES_ROOT}"
export SIMPLECAD_CASES_MODULE="${CASES_MODULE}"

case ":${PYTHONPATH:-}:" in
  *":${CASES_ROOT}:"*) ;;
  *) export PYTHONPATH="${CASES_ROOT}${PYTHONPATH:+:${PYTHONPATH}}" ;;
esac

MODE="run"
ENSURE_JUPYTER=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --print-env)
      MODE="print-env"
      shift
      ;;
    --check)
      MODE="check"
      shift
      ;;
    --ensure-jupyter)
      ENSURE_JUPYTER=1
      shift
      ;;
    --)
      shift
      break
      ;;
    *)
      break
      ;;
  esac
done

ensure_runtime() {
  if ! "${PYTHON_BIN}" - <<'PY' >/dev/null 2>&1
import simplecadapi  # noqa: F401
PY
  then
    echo "Runtime package missing, running scripts/install.sh ..."
    "${SCRIPT_DIR}/install.sh"
  fi
}

ensure_jupyter() {
  if ! "${PYTHON_BIN}" - <<'PY' >/dev/null 2>&1
import jupyterlab  # noqa: F401
import ipykernel  # noqa: F401
PY
  then
    echo "Jupyter dependencies missing, running scripts/install.sh --with-jupyter ..."
    "${SCRIPT_DIR}/install.sh" --with-jupyter
  fi
}

if [[ "${MODE}" == "print-env" ]]; then
  printf 'export SIMPLECAD_SKILL_ROOT="%s"\n' "${SIMPLECAD_SKILL_ROOT}"
  printf 'export SIMPLECAD_CASES_ROOT="%s"\n' "${SIMPLECAD_CASES_ROOT}"
  printf 'export SIMPLECAD_CASES_MODULE="%s"\n' "${SIMPLECAD_CASES_MODULE}"
  printf 'export PYTHONPATH="%s"\n' "${PYTHONPATH}"
  exit 0
fi

ensure_runtime

if [[ "${ENSURE_JUPYTER}" == "1" ]]; then
  ensure_jupyter
fi

if [[ "${MODE}" == "check" ]]; then
  "${PYTHON_BIN}" - <<'PY'
import os
import simplecadapi as scad

print("Runtime check passed.")
print(getattr(scad, "__description__", ""))
print(f"Skill cases module: {os.environ.get('SIMPLECAD_CASES_MODULE', '')}")
PY
  exit 0
fi

if [[ $# -eq 0 ]]; then
  echo "Skill runtime is ready in current environment."
  echo "Run command via wrapper: scripts/with_skill.sh -- ${PYTHON_BIN} your_script.py"
  echo 'Add skill env vars: eval "$(scripts/with_skill.sh --print-env)"'
  echo "Or check runtime: scripts/with_skill.sh --check"
  exit 0
fi

exec "$@"
