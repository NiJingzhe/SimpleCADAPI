"""Targeted warning filters for noisy third-party imports.

These filters intentionally suppress only known upstream warnings that are not
actionable for SimpleCADAPI users and would otherwise pollute LLM-facing error
output.
"""

from __future__ import annotations

import warnings


_SWIG_MODULE_WARNING = (
    r"builtin type (SwigPyPacked|SwigPyObject|swigvarlink) has no __module__ attribute"
)


def suppress_vendor_deprecation_warnings() -> None:
    """Suppress precise third-party deprecation warnings we cannot fix locally."""

    warnings.filterwarnings(
        "ignore",
        message=_SWIG_MODULE_WARNING,
        category=DeprecationWarning,
    )
