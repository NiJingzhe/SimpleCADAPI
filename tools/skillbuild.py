#!/usr/bin/env python3
"""Checkout entry point for the shared skill compiler."""
from simplecadapi.skill.compiler import (
    Condition,
    SkillBuildError,
    SkillProject,
    SourceFile,
    build_target,
    collect_source_files,
    compile_text,
    find_project_root,
    load_project,
    main,
    verify_output,
)

if __name__ == "__main__":
    raise SystemExit(main())
