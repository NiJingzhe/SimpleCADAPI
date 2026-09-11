"""Addon ecosystem for SimpleCADAPI.

The ``sca`` console script installs third-party addon packages (skill +
tooling repositories) that extend SimpleCADAPI with non-modeling
capabilities — simulation, analysis, downstream tooling. Two
integration modes are supported:

* the recommended language-agnostic boundary — addons consume
  ``.scadpkg`` files and process-level tooling, never touching the SDK
  in-process;
* in-process SDK use inside the addon's own environment — legitimate
  when an addon needs the builtin exporters or the official package
  readers; the descriptor's ``[compat] sca`` range governs which SDK
  releases that dependency may be.

In both modes addons keep their own environment: mixing plugin
dependencies into the environment that models the geometry is the
thing the separation exists to prevent.
"""

from __future__ import annotations

__all__ = ["AddonError"]


class AddonError(Exception):
    """Addon manager failure with a user-actionable, named-cause message."""
