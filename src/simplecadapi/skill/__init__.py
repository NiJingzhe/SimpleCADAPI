"""Skill compilation and installation for SimpleCADAPI.

The wheel ships the uncompiled skill source tree (``docs/skill`` plus
``skillproj.toml``) as package resources; this module compiles it into
per-harness builds at install time via the ``sca skill`` command group.
``tools/skillbuild.py`` is a thin wrapper around the same compiler for
maintainer-side builds from a checkout.
"""

from __future__ import annotations

from .compiler import (
    Condition,
    SkillBuildError,
    SkillProject,
    SourceFile,
    build_target,
    collect_source_files,
    compile_text,
    find_project_root,
    load_project,
)

__all__ = [
    "Condition",
    "SkillBuildError",
    "SkillProject",
    "SourceFile",
    "build_target",
    "collect_source_files",
    "compile_text",
    "find_project_root",
    "load_project",
]
