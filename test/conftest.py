"""Shared test configuration."""

from __future__ import annotations

import os

# Failure-path evidence rendering stays off for the suite at large: it is
# slow (VTK worker per render) and exercises nothing those tests assert.
# Dedicated evidence tests opt back in via monkeypatch.delenv.
os.environ.setdefault("SCA_NO_DIAGNOSTIC_RENDER", "1")
