"""Addon platform taxonomy: a closed os-arch enum plus host detection."""

from __future__ import annotations

import platform as _platform

from . import AddonError

#: Closed enum of supported addon platforms. Additive evolution only:
#: new values may be appended by the spec, never removed or repurposed.
PLATFORMS: tuple[str, ...] = (
    "macos-arm64",
    "macos-x86_64",
    "linux-x86_64",
    "linux-aarch64",
    "windows-x86_64",
    "windows-arm64",
)

_OS_ALIASES = {"darwin": "macos", "macos": "macos", "linux": "linux", "windows": "windows"}
# Architecture spellings follow per-OS convention in the enum: macos and
# windows use "arm64", linux uses "aarch64"; all use "x86_64".
_ARCH_ALIASES: dict[str, dict[str, str]] = {
    "macos": {"arm64": "arm64", "aarch64": "arm64", "x86_64": "x86_64", "amd64": "x86_64"},
    "linux": {"aarch64": "aarch64", "arm64": "aarch64", "x86_64": "x86_64", "amd64": "x86_64"},
    "windows": {"arm64": "arm64", "aarch64": "arm64", "x86_64": "x86_64", "amd64": "x86_64"},
}


def detect_platform(
    *, system: str | None = None, machine: str | None = None
) -> str:
    """Return the addon platform id for this host.

    Unknown systems or architectures raise instead of guessing; the error
    names both raw values so the report is actionable.
    """
    raw_system = (system if system is not None else _platform.system()).strip().lower()
    raw_machine = (machine if machine is not None else _platform.machine()).strip().lower()
    os_name = _OS_ALIASES.get(raw_system)
    arch = _ARCH_ALIASES.get(os_name or "", {}).get(raw_machine) if os_name else None
    if os_name is None or arch is None:
        raise AddonError(
            "cannot classify this host as an addon platform: "
            f"system={raw_system!r} machine={raw_machine!r}; "
            f"known platforms are {', '.join(PLATFORMS)}"
        )
    candidate = f"{os_name}-{arch}"
    if candidate not in PLATFORMS:
        raise AddonError(
            f"host platform {candidate!r} is not in the addon platform enum; "
            f"known platforms are {', '.join(PLATFORMS)}"
        )
    return candidate
