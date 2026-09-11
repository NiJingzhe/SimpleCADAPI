"""OS-portability primitives for byte-exact file IO and process probes.

Windows defaults differ from POSIX in four ways that must not surface as
corrupted cache bytes or masked failures:

- ``os.open`` without ``O_BINARY`` opens in text mode: ``read()`` strips
  every CR and ``write()`` expands every LF, so byte counts and hashes
  drift on any checkout made with ``core.autocrlf=true``.
- Opening a directory with ``os.open`` and ``fsync`` is POSIX-only;
  Windows raises ``PermissionError``.
- ``os.kill(pid, 0)`` maps to ``TerminateProcess`` on Windows and kills
  the very process a liveness probe is asking about.
- Legacy consoles (cp1252) raise ``UnicodeEncodeError`` on non-ASCII
  diagnostic output, which can replace the real failure inside an error
  handler.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable


def with_binary_flag(flags: int) -> int:
    """Return read/write flags forced into binary mode on Windows."""

    return flags | getattr(os, "O_BINARY", 0)


def fsync_directory(path: Path) -> None:
    """Durability-sync a directory entry; a no-op off POSIX.

    Windows offers no portable directory fsync, so rename durability
    there rests on the filesystem journal alone.
    """

    if os.name != "posix":
        return
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def windows_pid_is_alive(pid: int) -> bool:
    """Liveness probe that cannot terminate its target on Windows."""

    import ctypes

    windll_factory = getattr(ctypes, "WinDLL", None)
    if windll_factory is None:
        # Only reachable on Windows; unknown platform stays conservative.
        return True
    kernel32 = windll_factory("kernel32", use_last_error=True)
    process_query_limited_information = 0x1000
    still_active = 259
    handle = kernel32.OpenProcess(
        process_query_limited_information, False, pid
    )
    if not handle:
        # ERROR_INVALID_PARAMETER (87) means "no such process"; access
        # denied and anything else mean the process exists. A missing
        # probe stub stays conservative and reports the process alive.
        get_last_error = getattr(ctypes, "get_last_error", lambda: 0)
        return get_last_error() != 87
    try:
        exit_code = ctypes.c_ulong()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            return True
        return exit_code.value == still_active
    finally:
        kernel32.CloseHandle(handle)


def harden_console_streams(streams: Iterable[object]) -> None:
    """Escape instead of crash when a stream cannot encode a diagnostic.

    Only non-UTF streams with strict error handling are reconfigured, so
    UTF-8 consoles and host-configured streams keep their behavior; the
    real failure stays visible instead of being replaced by a
    ``UnicodeEncodeError`` from a diagnostic print.
    """

    for stream in streams:
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        encoding = (getattr(stream, "encoding", "") or "")
        normalized = encoding.replace("-", "").replace("_", "").lower()
        if "utf" in normalized:
            continue
        try:
            reconfigure(errors="backslashreplace")
        except (ValueError, OSError):
            continue


__all__ = [
    "fsync_directory",
    "harden_console_streams",
    "with_binary_flag",
    "windows_pid_is_alive",
]
