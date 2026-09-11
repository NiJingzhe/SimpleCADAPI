"""The ``sca`` console script: SimpleCADAPI addon manager.

Commands (human-readable output; machine-checkable reports come back
from :func:`run` for tests and tooling):

* ``sca addon init``            — create the addon home and write config
* ``sca addon add <source>``    — install an addon (GitHub or local path)
* ``sca addon update [name]``   — re-fetch one addon or all of them
* ``sca addon remove <name>``   — delete exactly what was installed
* ``sca addon list``            — registry contents with on-disk drift
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

from . import AddonError
from .home import ResolvedPaths, init_home, resolve_paths
from .install import install_addon, list_addons, parse_source, remove_addon, update_addon


def _add_location_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--home", type=Path, help="addon home override (beats env and config)")
    parser.add_argument(
        "--skills-dir",
        type=Path,
        help="skills install directory override (beats env and config)",
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sca",
        description="SimpleCADAPI addon manager: install third-party analysis, "
        "simulation, and downstream tooling packaged with agent skills.",
    )
    groups = parser.add_subparsers(dest="group", required=True)

    addon = groups.add_parser("addon", help="manage SimpleCADAPI addons")
    commands = addon.add_subparsers(dest="command", required=True)

    init = commands.add_parser(
        "init", help="create the addon home, registry, and config (idempotent)"
    )
    _add_location_flags(init)

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
    return parser


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


def run(argv: Sequence[str] | None = None) -> tuple[dict[str, Any], int]:
    args = _parser().parse_args(argv)
    resolved = resolve_paths(home=args.home, skills_dir=args.skills_dir)
    if args.command == "init":
        return init_home(resolved), 0
    if args.command == "add":
        source = parse_source(args.source)
        return install_addon(resolved, source, method=args.method), 0
    if args.command == "update":
        return (_update_all(resolved) if args.name is None else update_addon(resolved, args.name)), 0
    if args.command == "remove":
        return remove_addon(resolved, args.name), 0
    if args.command == "list":
        return list_addons(resolved), 0
    raise AssertionError(f"unsupported command: {args.command}")


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
