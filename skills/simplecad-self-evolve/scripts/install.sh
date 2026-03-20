#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
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

if ! "${PYTHON_BIN}" - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.prefix != sys.base_prefix else 1)
PY
then
  echo "Error: target interpreter is not inside a virtual environment." >&2
  echo "Hint: activate a venv first, or run with PYTHON_BIN=/path/to/venv/bin/python." >&2
  exit 1
fi

export SIMPLECAD_SKILL_ROOT="${SKILL_ROOT}"
export SIMPLECAD_RUNTIME_PACKAGE="simplecadapi"
export SIMPLECAD_CASES_ROOT="${SKILL_ROOT}/cases"
export SIMPLECAD_CASES_MODULE="simplecad_self_evolve_cases"

PACKAGE_SPEC="simplecadapi==2.0.5"
JUPYTER_DEPS=("jupyterlab>=4.5.5" "ipykernel>=6.29.5")
INSTALL_JUPYTER=0
INSTALL_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-jupyter)
      INSTALL_JUPYTER=1
      shift
      ;;
    --)
      shift
      INSTALL_ARGS+=("$@")
      break
      ;;
    *)
      INSTALL_ARGS+=("$1")
      shift
      ;;
  esac
done

if command -v uv >/dev/null 2>&1; then
  INSTALL_CMD=(uv pip install --python "${PYTHON_BIN}")
else
  INSTALL_CMD=("${PYTHON_BIN}" -m pip install)
fi

run_install() {
  local targets=("$@")
  if [[ ${#INSTALL_ARGS[@]} -gt 0 ]]; then
    "${INSTALL_CMD[@]}" "${INSTALL_ARGS[@]}" "${targets[@]}"
  else
    "${INSTALL_CMD[@]}" "${targets[@]}"
  fi
}

echo "Installing runtime package: ${PACKAGE_SPEC}"
run_install "${PACKAGE_SPEC}"

if [[ "${INSTALL_JUPYTER}" == "1" ]]; then
  echo "Installing Jupyter dependencies..."
  run_install "${JUPYTER_DEPS[@]}"
fi

"${PYTHON_BIN}" - <<'PY'
import simplecadapi as scad

print("simplecadapi import OK")
print(getattr(scad, "__description__", ""))
PY

echo "Runtime install completed for simplecadapi 2.0.5."
