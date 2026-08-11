"""Command-line diagnostics for the SimpleCAD content-addressed cache."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

from .policy import CacheMode, CachePolicy, resolve_cache_policy
from .store import ContentAddressedStore


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="simplecad-cache")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="project root used to resolve pyproject.toml and relative cache paths",
    )
    parser.add_argument("--cache-dir", type=Path, help="override the resolved cache root")
    subparsers = parser.add_subparsers(dest="command", required=True)

    status = subparsers.add_parser("status", help="report cache counts")
    status.add_argument("--namespace")

    verify = subparsers.add_parser("verify", help="verify records and objects")
    verify.add_argument("--namespace")
    verify.add_argument("--repair", action="store_true")

    prune = subparsers.add_parser("prune", help="report or quarantine orphan objects")
    prune.add_argument("--apply", action="store_true")

    clear = subparsers.add_parser("clear", help="clear one namespace or the complete cache")
    clear.add_argument("--namespace")
    clear.add_argument("--yes", action="store_true", help="confirm destructive removal")
    return parser


def _policy(args: argparse.Namespace, *, writable: bool) -> CachePolicy:
    explicit: dict[str, Any] = {}
    if args.cache_dir is not None:
        explicit["root"] = args.cache_dir
    explicit["mode"] = (
        CacheMode.READ_WRITE.value if writable else CacheMode.READ_ONLY.value
    )
    return resolve_cache_policy(explicit or None, project_root=args.project_root)


def run(argv: Sequence[str] | None = None) -> tuple[dict[str, Any], int]:
    args = _parser().parse_args(argv)
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


def main(argv: Sequence[str] | None = None) -> int:
    try:
        report, exit_code = run(argv)
    except (OSError, PermissionError, ValueError) as exc:
        print(json.dumps({"error": type(exc).__name__, "message": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(report, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
