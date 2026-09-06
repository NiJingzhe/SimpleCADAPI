"""Run the integrated BLDC actuator export scripts concurrently."""

from __future__ import annotations

import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

SCRIPTS = (
    "examples/integrated_bldc_joint_actuator/export_mjcf.py",
    "examples/integrated_bldc_joint_actuator/export_step.py",
    "examples/integrated_bldc_joint_actuator/export_fcstd.py",
)


def run(script: str) -> tuple[str, int, float, str, str]:
    start = time.perf_counter()
    proc = subprocess.run(
        [sys.executable, script],
        capture_output=True,
        text=True,
    )
    elapsed = time.perf_counter() - start
    return script, proc.returncode, elapsed, proc.stdout, proc.stderr


def main() -> None:
    """Export MJCF, STEP, and FCStd from the captured package in parallel."""

    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=len(SCRIPTS)) as pool:
        futures = [pool.submit(run, script) for script in SCRIPTS]
        results = [future.result() for future in futures]
    for script, code, elapsed, stdout, stderr in sorted(results):
        status = "OK" if code == 0 else f"FAIL({code})"
        print(f"[export] {script.rsplit('/', 1)[-1]}: {status} {elapsed:.1f}s")
        if stdout.strip():
            print(_indent(stdout.strip()))
        if code != 0 and stderr.strip():
            print(_indent(stderr.strip()[-2000:]))
    failed = [r for r in results if r[1] != 0]
    print(f"[export] total {time.perf_counter() - start:.1f}s failed={len(failed)}")
    if failed:
        raise SystemExit(1)


def _indent(text: str) -> str:
    return "\n".join(f"  {line}" for line in text.splitlines())


if __name__ == "__main__":
    main()
