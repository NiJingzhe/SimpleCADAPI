"""End-to-end tests for the ``sca addon`` CLI: init/add/update/remove/list
flows, the home resolution chain, and every hard-failure mode."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from simplecadapi.addon import AddonError
from simplecadapi.addon.cli import run
from simplecadapi.addon.home import resolve_paths
from simplecadapi.addon.install import sca_version
from simplecadapi.addon.platforms import PLATFORMS, detect_platform
from simplecadapi.addon.registry import REGISTRY_FILENAME


@pytest.fixture(autouse=True)
def fake_user_home(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.delenv("SCA_ADDON_HOME", raising=False)
    monkeypatch.delenv("SCA_SKILLS_DIR", raising=False)
    return tmp_path


def _compat_span() -> str:
    major = int(sca_version().split(".")[0])
    return f">=2.0,<{major + 10}"


def _make_addon_repo(
    parent: Path,
    *,
    name: str = "demo-addon",
    version: str = "0.1.0",
    compat: str | None = None,
    kind: str = "none",
    platforms: list[str] | None = None,
    check_cmd: str | None = None,
    overrides: dict[str, str] | None = None,
    skill_name: str | None = None,
) -> Path:
    repo = parent / name
    skill_dir = repo / "skill"
    skill_dir.mkdir(parents=True, exist_ok=True)
    effective_name = skill_name or name
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: sca-{effective_name}\ndescription: demo {version}\n---\n# demo\n",
        encoding="utf-8",
    )
    lines = [
        "[addon]",
        f'name = "{name}"',
        f'version = "{version}"',
        'license = "MIT"',
        'skill_path = "skill"',
        "",
        "[compat]",
        f'sca = "{compat or _compat_span()}"',
        "",
        "[runtime]",
        f'kind = "{kind}"',
    ]
    if platforms is not None:
        rendered = ", ".join(f'"{item}"' for item in platforms)
        lines.append(f"platforms = [{rendered}]")
    if check_cmd is not None:
        escaped = check_cmd.replace('"', '\\"')
        lines.append(f'check_cmd = "{escaped}"')
    if overrides:
        lines.append("[runtime.check_overrides]")
        for key, value in overrides.items():
            escaped = value.replace('"', '\\"')
            lines.append(f'"{key}" = "{escaped}"')
    (repo / "sca-addon.toml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return repo


def _init(tmp_path) -> dict:
    report, code = run(["addon", "init"])
    assert code == 0
    return report


def _registry(home: Path) -> dict:
    return json.loads((home / REGISTRY_FILENAME).read_text(encoding="utf-8"))


# ------------------------------------------------------------------- init


def test_commands_require_init_first():
    with pytest.raises(AddonError) as err:
        run(["addon", "list"])
    assert "sca addon init" in str(err.value)


def test_init_creates_home_config_and_registry(tmp_path):
    report = _init(tmp_path)
    home = Path(report["home"])
    assert home == tmp_path / ".sca" / "addons"
    assert (home / REGISTRY_FILENAME).is_file()
    assert (tmp_path / ".sca" / "config.toml").is_file()
    assert (tmp_path / ".agents" / "skills").is_dir()


def test_init_is_idempotent_and_preserves_registry(tmp_path):
    _init(tmp_path)
    source = _make_addon_repo(tmp_path)
    report, code = run(["addon", "add", str(source)])
    assert code == 0
    second = _init(tmp_path)
    assert second["registry"] == "preserved"
    assert "demo-addon" in _registry(Path(second["home"]))["addons"]


def test_resolution_chain_flag_beats_env_beats_config(tmp_path, monkeypatch):
    _init(tmp_path)
    default_home = tmp_path / ".sca" / "addons"

    env_home = tmp_path / "env-addons"
    env_home.mkdir()
    monkeypatch.setenv("SCA_ADDON_HOME", str(env_home))
    resolved = resolve_paths()
    assert resolved.home == env_home
    assert resolved.home_source == "env SCA_ADDON_HOME"

    flag_home = tmp_path / "flag-addons"
    flag_home.mkdir()
    resolved = resolve_paths(home=flag_home)
    assert resolved.home == flag_home
    assert resolved.home_source == "flag"

    monkeypatch.delenv("SCA_ADDON_HOME")
    resolved = resolve_paths()
    assert resolved.home == default_home
    assert resolved.home_source == "config"


# -------------------------------------------------------------------- add


def test_add_local_addon_full_flow(tmp_path):
    _init(tmp_path)
    source = _make_addon_repo(tmp_path)
    report, code = run(["addon", "add", str(source)])
    assert code == 0
    assert report["name"] == "demo-addon"
    assert report["version"] == "0.1.0"
    assert report["runtime_check"] is None

    home = tmp_path / ".sca" / "addons"
    assert (home / "demo-addon" / "sca-addon.toml").is_file()
    skill = tmp_path / ".agents" / "skills" / "sca-demo-addon" / "SKILL.md"
    assert skill.is_file()

    record = _registry(home)["addons"]["demo-addon"]
    assert record["source"]["kind"] == "local"
    assert record["skill_install"]["dir_name"] == "sca-demo-addon"
    assert record["sca_version_at_install"] == sca_version()


def test_add_with_runtime_probe_warns_but_installs(tmp_path):
    _init(tmp_path)
    source = _make_addon_repo(
        tmp_path,
        kind="binary",
        platforms=[detect_platform()],
        check_cmd=f'"{sys.executable}" -c "raise SystemExit(3)"',
    )
    report, code = run(["addon", "add", str(source)])
    assert code == 0
    assert report["runtime_check"]["passed"] is False
    assert report["runtime_check"]["exit_code"] == 3

    passing = _make_addon_repo(
        tmp_path / "ok",
        name="ok-addon",
        kind="binary",
        platforms=[detect_platform()],
        check_cmd=f'"{sys.executable}" -c "print(1)"',
        overrides={detect_platform(): f'"{sys.executable}" -c "print(2)"'},
    )
    report, code = run(["addon", "add", str(passing)])
    assert code == 0
    assert report["runtime_check"]["passed"] is True


def test_add_twice_is_rejected(tmp_path):
    _init(tmp_path)
    source = _make_addon_repo(tmp_path)
    run(["addon", "add", str(source)])
    with pytest.raises(AddonError) as err:
        run(["addon", "add", str(source)])
    assert "already installed" in str(err.value)
    assert "update" in str(err.value)


def test_add_refuses_foreign_skill_directory(tmp_path):
    _init(tmp_path)
    source = _make_addon_repo(tmp_path)
    foreign = tmp_path / ".agents" / "skills" / "sca-demo-addon"
    foreign.mkdir(parents=True)
    with pytest.raises(AddonError) as err:
        run(["addon", "add", str(source)])
    assert "refusing to overwrite" in str(err.value)


def test_add_compat_mismatch_is_a_hard_block(tmp_path):
    _init(tmp_path)
    source = _make_addon_repo(tmp_path, compat=">=99,<100")
    with pytest.raises(AddonError) as err:
        run(["addon", "add", str(source)])
    message = str(err.value)
    assert ">=99,<100" in message
    assert sca_version() in message


def test_add_unsupported_platform_is_a_hard_block(tmp_path):
    _init(tmp_path)
    host = detect_platform()
    other = next(item for item in PLATFORMS if item != host)
    source = _make_addon_repo(tmp_path, kind="binary", platforms=[other], check_cmd="x -v")
    with pytest.raises(AddonError) as err:
        run(["addon", "add", str(source)])
    message = str(err.value)
    assert host in message
    assert other in message


# ----------------------------------------------------------------- update


def _bump_version(repo: Path, old: str, new: str) -> None:
    descriptor = repo / "sca-addon.toml"
    descriptor.write_text(
        descriptor.read_text(encoding="utf-8").replace(f'version = "{old}"', f'version = "{new}"'),
        encoding="utf-8",
    )
    skill = repo / "skill" / "SKILL.md"
    skill.write_text(
        skill.read_text(encoding="utf-8").replace(f"demo {old}", f"demo {new}"),
        encoding="utf-8",
    )


def test_update_local_source_pulls_new_version(tmp_path):
    _init(tmp_path)
    source = _make_addon_repo(tmp_path, version="0.1.0")
    run(["addon", "add", str(source)])

    skill_file = tmp_path / ".agents" / "skills" / "sca-demo-addon" / "SKILL.md"
    assert "demo 0.1.0" in skill_file.read_text(encoding="utf-8")

    _bump_version(source, old="0.1.0", new="0.2.0")
    report, code = run(["addon", "update", "demo-addon"])
    assert code == 0
    assert report["version"] == "0.2.0"
    assert report["previous_version"] == "0.1.0"
    assert "demo 0.2.0" in skill_file.read_text(encoding="utf-8")


def test_update_downgrade_reports_warning(tmp_path):
    _init(tmp_path)
    source = _make_addon_repo(tmp_path, version="0.5.0")
    run(["addon", "add", str(source)])
    _bump_version(source, old="0.5.0", new="0.4.0")
    report, code = run(["addon", "update", "demo-addon"])
    assert code == 0
    assert any("downgrade" in warning for warning in report["warnings"])


def test_update_rename_upstream_is_rejected(tmp_path):
    _init(tmp_path)
    source = _make_addon_repo(tmp_path, name="alpha-addon")
    run(["addon", "add", str(source)])
    renamed = _make_addon_repo(tmp_path / "elsewhere", name="beta-addon")
    (source / "sca-addon.toml").write_text(
        (renamed / "sca-addon.toml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    with pytest.raises(AddonError) as err:
        run(["addon", "update", "alpha-addon"])
    assert "renamed" in str(err.value)


def test_update_unknown_name_lists_installed(tmp_path):
    _init(tmp_path)
    with pytest.raises(AddonError) as err:
        run(["addon", "update", "ghost"])
    assert "not installed" in str(err.value)


# ------------------------------------------------------------------ remove


def test_remove_deletes_both_locations(tmp_path):
    _init(tmp_path)
    source = _make_addon_repo(tmp_path)
    run(["addon", "add", str(source)])
    report, code = run(["addon", "remove", "demo-addon"])
    assert code == 0
    home = tmp_path / ".sca" / "addons"
    assert not (home / "demo-addon").exists()
    assert not (tmp_path / ".agents" / "skills" / "sca-demo-addon").exists()
    assert _registry(home)["addons"] == {}
    assert len(report["removed"]) == 2

    with pytest.raises(AddonError) as err:
        run(["addon", "remove", "demo-addon"])
    assert "not installed" in str(err.value)


def test_remove_reports_missing_directories(tmp_path):
    _init(tmp_path)
    source = _make_addon_repo(tmp_path)
    run(["addon", "add", str(source)])
    import shutil

    shutil.rmtree(tmp_path / ".agents" / "skills" / "sca-demo-addon")
    report, code = run(["addon", "remove", "demo-addon"])
    assert code == 0
    assert any("missing" in warning for warning in report["warnings"])


# -------------------------------------------------------------------- list


def test_list_empty_and_populated_with_drift(tmp_path):
    _init(tmp_path)
    report, code = run(["addon", "list"])
    assert code == 0
    assert report["addons"] == []

    source = _make_addon_repo(tmp_path)
    run(["addon", "add", str(source)])
    report, code = run(["addon", "list"])
    assert code == 0
    entry = report["addons"][0]
    assert entry["name"] == "demo-addon"
    assert entry["drift"] == []

    import shutil

    shutil.rmtree(tmp_path / ".sca" / "addons" / "demo-addon")
    report, _ = run(["addon", "list"])
    assert report["addons"][0]["drift"]


def test_corrupt_registry_is_a_named_failure(tmp_path):
    _init(tmp_path)
    registry_file = tmp_path / ".sca" / "addons" / REGISTRY_FILENAME
    tampered = json.loads(registry_file.read_text(encoding="utf-8"))
    tampered["schema_version"] = "0.0"
    registry_file.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(AddonError) as err:
        run(["addon", "list"])
    assert "schema_version" in str(err.value)
