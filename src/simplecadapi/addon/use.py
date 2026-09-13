"""``sca addon use``: run a command inside an installed addon's environment.

The addon's ``[runtime].command_prefix`` (a shell prelude, with
``{addon_dir}`` resolving to the installed addon directory) is joined in
front of the requested command and handed to the shell, so ``sca addon
use conn-tools python train.py`` executes with exactly the environment
the addon declares — its own venv, tool paths, or variables — without
the caller having to provision anything. The installed addon directory
is also exported as ``SCA_ADDON_DIR``.

Calling without a command reports the effective prefix and addon
directory instead of executing anything.
"""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence

from . import AddonError
from .descriptor import load_descriptor
from .home import ResolvedPaths, require_initialized
from .install import effective_command
from .registry import get_record, load_registry


def use_addon(
    resolved: ResolvedPaths,
    name: str,
    cmd: Sequence[str],
    *,
    capture_output: bool = False,
) -> dict[str, Any]:
    """Dispatch ``cmd`` through the addon's command prefix.

    With ``capture_output`` the command's stdout/stderr come back in the
    report (for tests and tooling); otherwise they stream straight to the
    caller's terminal and only the exit code is reported.
    """
    require_initialized(resolved)
    registry = load_registry(resolved.home)
    record = get_record(registry, name)
    if record is None:
        installed = sorted(registry.get("addons", {}))
        listing = ", ".join(installed) if installed else "(none installed)"
        raise AddonError(f"addon {name!r} is not installed; installed: {listing}")
    addon_dir = resolved.home / str(record.get("addon_relpath", name))
    if not addon_dir.is_dir():
        raise AddonError(
            f"addon directory {addon_dir} is missing from the addon home — "
            f"reinstall with `sca addon update {name}` or `sca addon add`"
        )
    # The installed descriptor is the source of truth for the prefix: a
    # user may provision or edit it after install without re-adding.
    descriptor = load_descriptor(addon_dir)
    prefix = descriptor.command_prefix

    if not cmd:
        return {
            "action": "use",
            "name": name,
            "addon_dir": str(addon_dir),
            "command_prefix": prefix,
        }

    # Shell-quote each argv element so the joined line re-parses to exactly
    # the requested argv, even for arguments with spaces or shell metachars.
    effective = effective_command(
        prefix, addon_dir, " ".join(shlex.quote(part) for part in cmd)
    )
    env = dict(os.environ)
    env["SCA_ADDON_DIR"] = str(addon_dir)
    argv = ["cmd", "/c", effective] if sys.platform == "win32" else ["sh", "-c", effective]
    try:
        completed = subprocess.run(
            argv, env=env, capture_output=capture_output,
            text=capture_output,
        )
    except FileNotFoundError as exc:
        raise AddonError(f"cannot launch the shell for {effective!r}: {exc}") from exc
    report: dict[str, Any] = {
        "action": "use",
        "name": name,
        "addon_dir": str(addon_dir),
        "command": effective,
        "exit_code": completed.returncode,
    }
    if capture_output:
        report["output"] = completed.stdout
        if completed.stderr:
            report["stderr"] = completed.stderr
    return report
