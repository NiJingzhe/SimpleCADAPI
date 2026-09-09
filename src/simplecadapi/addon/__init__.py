"""Addon ecosystem for SimpleCADAPI.

The ``sca`` console script installs third-party addon packages (skill +
tooling repositories) that extend SimpleCADAPI with non-modeling
capabilities — simulation, analysis, downstream tooling. Addons never
import :mod:`simplecadapi`; their only contact surface is the
``.scadpkg`` file format and process-level tooling.
"""

from __future__ import annotations

__all__ = ["AddonError"]


class AddonError(Exception):
    """Addon manager failure with a user-actionable, named-cause message."""
