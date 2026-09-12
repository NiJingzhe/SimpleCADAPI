"""The ``init`` and ``addon`` groups of the top-level ``sca`` console script
(see :mod:`simplecadapi.cli` for the dispatcher and the cache/export groups).

Groups (human-readable output; machine-checkable reports come back from
:func:`run` for tests and tooling):

* ``sca init``                  — create the addon home, write config, and
  wire the ``sca`` shim + PATH block so the command resolves in any new
  shell (``--no-shell`` skips the wiring)
* ``sca addon add <source>``    — install an addon (GitHub or local path)
* ``sca addon update [name]``   — re-fetch one addon or all of them
* ``sca addon remove <name>``   — delete exactly what was installed
* ``sca addon list``            — registry contents with on-disk drift
* ``sca addon use <name> <cmd>`` — run cmd inside the addon's declared
  environment (its ``[runtime].command_prefix`` is prepended; without a
  command, report the prefix and addon directory)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

from . import AddonError
from .home import ResolvedPaths, init_home, resolve_paths
from .install import install_addon, list_addons, parse_source, remove_addon, update_addon
from .shell import integrate_shell
from .use import use_addon


def _add_location_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--home", type=Path, help="addon home override (beats env and config)")
    parser.add_argument(
        "--skills-dir",
        type=Path,
        help="skills install directory override (beats env and config)",
    )


def _run_init(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    resolved = resolve_paths(home=args.home, skills_dir=args.skills_dir)
    report: dict[str, Any] = dict(init_home(resolved))
    report["shell"] = {"skipped": True} if args.no_shell else integrate_shell()
    return report, 0


def _run_addon(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    resolved = resolve_paths(home=args.home, skills_dir=args.skills_dir)
    if args.command == "add":
        source = parse_source(args.source)
        return install_addon(resolved, source, method=args.method), 0
    if args.command == "update":
        return (_update_all(resolved) if args.name is None else update_addon(resolved, args.name)), 0
    if args.command == "remove":
        return remove_addon(resolved, args.name), 0
    if args.command == "list":
        return list_addons(resolved), 0
    if args.command == "use":
        report = use_addon(resolved, args.name, args.cmd, capture_output=args.capture)
        return report, report.get("exit_code", 0)
    raise AssertionError(f"unsupported command: {args.command}")


def _update_all(resolved: ResolvedPaths) -> dict[str, Any]:
    from .registry import load_registry

    registry = load_registry(resolved.home) if resolved.home.is_dir() else {"addons": {}}
    names = sorted(registry.get("addons", {}))
    if not names:
        raise AddonError("no addons installed; nothing to update")
    return {
        "action": "update-all",
        "updated": [update_addon(resolved, name) for name in names],
    }


def configure(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``init`` and ``addon`` groups on a parent subparsers."""
    init = subparsers.add_parser(
        "init", help="create the addon home, registry, and config (idempotent)"
    )
    _add_location_flags(init)
    init.add_argument(
        "--no-shell", action="store_true",
        help="skip the shell integration (sca shim + PATH block)",
    )
    init.set_defaults(handler=_run_init, printer=_print)

    addon = subparsers.add_parser("addon", help="manage SimpleCADAPI addons")
    commands = addon.add_subparsers(dest="command", required=True)

    add = commands.add_parser(
        "add", help="install an addon from GitHub (owner/repo[@ref]) or a local path"
    )
    _add_location_flags(add)
    add.add_argument("source", help="owner/repo[@ref | @commit] or a local directory")
    add.add_argument(
        "--method",
        choices=("tarball", "clone"),
        default="tarball",
        help="fetch method for GitHub sources (tarball needs no git binary)",
    )

    update = commands.add_parser(
        "update", help="re-fetch one addon (or every installed addon) from its source"
    )
    _add_location_flags(update)
    update.add_argument("name", nargs="?", help="addon name (default: all installed addons)")

    remove = commands.add_parser("remove", help="remove an installed addon and its skill")
    _add_location_flags(remove)
    remove.add_argument("name", help="addon name")

    listing = commands.add_parser("list", help="list installed addons")
    _add_location_flags(listing)

    use = commands.add_parser(
        "use",
        help="run a command inside an installed addon's declared environment",
        description="Prepends the addon's [runtime].command_prefix (with "
        "{addon_dir} resolved) to the command and executes it via the shell; "
        "SCA_ADDON_DIR is exported. Without a command, report the prefix.",
    )
    _add_location_flags(use)
    use.add_argument("name", help="installed addon name")
    use.add_argument(
        "cmd", nargs=argparse.REMAINDER,
        help="command and arguments to run (everything after NAME)",
    )
    use.add_argument(
        "--capture", action="store_true",
        help="capture the command's output into the report instead of streaming it",
    )
    addon.set_defaults(handler=_run_addon, printer=_print)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sca",
        description="SimpleCADAPI command line: setup, addons, package export, "
        "cache diagnostics.",
    )
    subparsers = parser.add_subparsers(dest="group", required=True)
    configure(subparsers)
    return parser


def run(argv: Sequence[str] | None = None) -> tuple[dict[str, Any], int]:
    args = _parser().parse_args(argv)
    return args.handler(args)


def _print_check(check: Mapping[str, Any] | None) -> None:
    if check is None:
        print("  runtime check: n/a (no probe declared)")
        return
    if check.get("passed"):
        print(f"  runtime check: PASSED ({check.get('platform')})")
        return
    print(
        f"  runtime check: FAILED ({check.get('platform')}, exit "
        f"{check.get('exit_code')}) — the runtime is not usable yet; install it "
        "before relying on this addon"
    )
    print(f"    probe output: {check.get('output_tail', '')!r}")


def _print(report: Mapping[str, Any]) -> None:
    if "registry" in report and "home" in report:
        print(f"addon home ready: {report.get('home')}")
        print(f"  skills dir: {report.get('skills_dir')}")
        print(f"  config:     {report.get('config')}")
        print(f"  registry:   {report.get('registry')}")
        if report.get("created") == "yes":
            print("  hint: export SCA_ADDON_HOME / SCA_SKILLS_DIR to override these")
        shell = report.get("shell") or {}
        if shell.get("skipped"):
            print("  shell: integration skipped (--no-shell)")
        elif shell.get("shim"):
            print(f"  shell: shim {shell['shim']}")
            for rc_path, state in shell.get("shell_blocks", {}).items():
                print(f"    PATH block: {rc_path} ({state})")
            if "windows_path" in shell:
                print(f"    windows PATH: {shell['windows_path']}")
            for note in shell.get("notes", []):
                print(f"    note: {note}")
        return
    action = report.get("action")
    if action == "update-all":
        for item in report.get("updated", []):
            _print(item)
        return
    if action in {"add", "update"}:
        verb = "installed" if action == "add" else "updated"
        previous = f" (was {report['previous_version']})" if report.get("previous_version") else ""
        print(f"{verb} {report.get('name')} {report.get('version')}{previous}")
        print(f"  source: {report.get('source', '?')}")
        print(f"  addon:  {report.get('addon_dir', '?')}")
        print(f"  skill:  {report.get('skill_dir', '?')}")
        _print_check(report.get("runtime_check"))
        for warning in report.get("warnings", []):
            print(f"  WARNING: {warning}")
        return
    if action == "remove":
        for path in report.get("removed", []):
            print(f"removed {path}")
        for warning in report.get("warnings", []):
            print(f"WARNING: {warning}")
        return
    if "addons" in report:
        addons = report.get("addons") or []
        if not addons:
            print("no addons installed")
            return
        for entry in addons:
            check = entry.get("runtime_check")
            state = "-" if check is None else ("ok" if check.get("passed") else "FAILED")
            print(
                f"{entry.get('name')}  {entry.get('version', '?')}  "
                f"[{entry.get('source', '?')}]  runtime: {state}"
            )
            if entry.get("skill_dir"):
                print(f"  skill: {entry['skill_dir']}")
            for drift in entry.get("drift", []):
                print(f"  DRIFT: {drift}")
        return
    if report.get("action") == "use":
        if "exit_code" in report:
            return  # the command's own output already went to the terminal
        print(f"{report['name']}  addon dir: {report['addon_dir']}")
        print(f"  command prefix: {report['command_prefix'] or '(none)'}")
        print("  usage: sca addon use NAME COMMAND [ARGS...]")
        return
    print(str(report))


def main(argv: Sequence[str] | None = None) -> int:
    try:
        report, exit_code = run(argv)
    except AddonError as exc:
        print(f"sca: {exc}", file=sys.stderr)
        return 2
    except (OSError, ValueError) as exc:
        print(f"sca: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    _print(report)
    return exit_code


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
