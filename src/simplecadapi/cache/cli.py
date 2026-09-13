"""Command-line diagnostics for the SimpleCAD content-addressed cache.

This module owns the ``sca cache`` group (see :mod:`simplecadapi.cli`).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

from .policy import CacheMode, CachePolicy, resolve_cache_policy
from .store import ContentAddressedStore


def configure(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``cache`` group on a parent subparsers action."""
    parser = subparsers.add_parser(
        "cache", help="content-addressed cache diagnostics (status/verify/prune/clear)"
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="project root used to resolve pyproject.toml and relative cache paths",
    )
    parser.add_argument("--cache-dir", type=Path, help="override the resolved cache root")
    commands = parser.add_subparsers(dest="command", required=True)

    status = commands.add_parser("status", help="report cache counts")
    status.add_argument("--namespace")

    verify = commands.add_parser("verify", help="verify records and objects")
    verify.add_argument("--namespace")
    verify.add_argument("--repair", action="store_true")

    prune = commands.add_parser("prune", help="report or quarantine orphan objects")
    prune.add_argument("--apply", action="store_true")

    clear = commands.add_parser("clear", help="clear one namespace or the complete cache")
    clear.add_argument("--namespace")
    clear.add_argument("--yes", action="store_true", help="confirm destructive removal")

    parser.set_defaults(handler=_execute, printer=_print_report)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sca", description=__doc__)
    configure(parser.add_subparsers(dest="group", required=True))
    return parser


def _print_report(report: dict[str, Any]) -> None:
    print(json.dumps(report, sort_keys=True))


def _policy(args: argparse.Namespace, *, writable: bool) -> CachePolicy:
    explicit: dict[str, Any] = {}
    if args.cache_dir is not None:
        explicit["root"] = args.cache_dir
    explicit["mode"] = (
        CacheMode.READ_WRITE.value if writable else CacheMode.READ_ONLY.value
    )
    return resolve_cache_policy(explicit or None, project_root=args.project_root)


def _execute(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    if args.command == "clear" and not args.yes:
        raise ValueError("clear requires --yes confirmation")
    writable = bool(
        (args.command == "verify" and args.repair)
        or (args.command == "prune" and args.apply)
        or args.command == "clear"
    )
    store = ContentAddressedStore(_policy(args, writable=writable))

    if args.command == "status":
        return dict(store.diagnostics(args.namespace)), 0
    if args.command == "verify":
        report = dict(store.verify_cache(args.namespace, repair=args.repair))
        return report, 0 if report["ok"] else 1
    if args.command == "prune":
        report = dict(store.prune_orphans(dry_run=not args.apply))
        return report, 0
    if args.command == "clear":
        report = dict(store.clear_cache(args.namespace, confirm=args.yes))
        return report, 0
    raise AssertionError(f"unsupported command: {args.command}")


def run(argv: Sequence[str] | None = None) -> tuple[dict[str, Any], int]:
    args = _parser().parse_args(argv)
    return _execute(args)
