"""The single ``sca`` console script: the whole SimpleCADAPI command line.

Groups, each owned by its module and registered here at parser level so
``sca <group> --help`` works::

    sca init                      # machine setup: addon home + shell wiring
    sca addon add|update|remove|list|use
    sca cache status|verify|prune|clear
    sca export <package.scadpkg> [--format ...]

Shared contract: group handlers return ``(report, exit_code)`` and are
followed by the group's own printer (human-readable for init/addon, JSON
for cache/export); errors print one ``sca: ...`` line to stderr and exit 2.
The historical ``simplecad-cache``/``simplecad-export`` entry points are
gone — the same commands live here.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any, Sequence

from .addon import AddonError
from .addon.install import sca_version


def build_parser() -> argparse.ArgumentParser:
    from .addon import cli as addon_cli
    from .cache import cli as cache_cli
    from .exporter import cli as exporter_cli

    parser = argparse.ArgumentParser(
        prog="sca",
        description="SimpleCADAPI command line: setup, addons, package export, "
        "cache diagnostics.",
    )
    parser.add_argument(
        "--version", action="version", version=f"sca {sca_version()}"
    )
    subparsers = parser.add_subparsers(dest="group", required=True)
    addon_cli.configure(subparsers)
    cache_cli.configure(subparsers)
    exporter_cli.configure(subparsers)
    return parser


def run(argv: Sequence[str] | None = None) -> tuple[dict[str, Any], int, Any]:
    """Parse and dispatch; return ``(report, exit_code, printer)``."""
    args = build_parser().parse_args(argv)
    report, exit_code = args.handler(args)
    return report, exit_code, args.printer


def main(argv: Sequence[str] | None = None) -> int:
    try:
        report, exit_code, printer = run(argv)
    except (AddonError, OSError, ValueError) as exc:
        print(f"sca: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    printer(report)
    return exit_code


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
