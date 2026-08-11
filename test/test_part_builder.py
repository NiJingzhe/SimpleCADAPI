from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import importlib.util
import threading
import time
from pathlib import Path
import pytest

import simplecadapi as scad
from simplecadapi.artifacts.canonical import ArtifactValidationError


def _load_function(path: Path, source: str, name: str):
    path.write_text(source, encoding="utf-8")
    spec = importlib.util.spec_from_file_location(f"part_fixture_{path.stem}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, getattr(module, name)


def _policy(root: Path, mode: str = "read_write") -> scad.CachePolicy:
    return scad.CachePolicy(mode=mode, root=root)


def test_part_reuses_runtime_in_process_and_restores_across_wrappers(
    tmp_path: Path,
) -> None:
    calls = 0
    policy = _policy(tmp_path / "cache")

    @scad.part(id="cached_box", cache=policy)
    def build_box(width: float = 2.0) -> scad.Part:
        nonlocal calls
        calls += 1
        body = scad.make_box_rsolid(width=width, height=3.0, depth=4.0)
        body = scad.apply_tag(shape=body, tag="role.body")
        part = scad.make_part_rpart(part_id="cached_box", body=body)
        connector = scad.make_placement_connector_rconnector(
            connector_id="mount",
            placement=scad.make_placement_rplacement(origin=(1.0, 0.0, 0.0)),
        )
        return scad.add_connector_rpart(part=part, connector=connector)

    cold = build_box()
    memory_warm = build_box()
    restored_builder = scad.part(id="cached_box", cache=policy)(build_box.__wrapped__)
    disk_warm = restored_builder()

    assert calls == 1
    assert not cold.cache_report.hit
    assert memory_warm.cache_report.hit
    assert memory_warm.cache_report.part_lookups == 0
    assert memory_warm.cache_report.bytes_read == 0
    assert memory_warm.session is cold.session
    assert memory_warm.value is cold.value
    assert disk_warm.cache_report.hit
    assert disk_warm.cache_report.part_lookups == 1
    assert disk_warm.cache_report.bytes_read > 0
    assert disk_warm.session is not cold.session
    assert disk_warm.value is not cold.value
    assert disk_warm.value.body is not cold.value.body
    assert disk_warm.value.body.get_volume() == pytest.approx(24.0)
    assert disk_warm.definition.canonical_bytes == cold.definition.canonical_bytes
    assert disk_warm.model_json == cold.model_json
    assert disk_warm.session.graph.to_dict() == cold.session.graph.to_dict()
    assert disk_warm.value.connector_ids() == ("mount",)
    assert disk_warm.definition.interface_hashes == cold.definition.interface_hashes
    assert scad.list_tags(shape=disk_warm.value.body) == scad.list_tags(
        shape=cold.value.body
    )


def test_part_operations_create_only_a_whole_part_cache_record(
    tmp_path: Path,
) -> None:
    policy = _policy(tmp_path / "cache")

    @scad.part(id="layered_cache", cache=policy)
    def build() -> scad.Solid:
        body = scad.make_box_rsolid(width=4.0, height=4.0, depth=2.0)
        tool = scad.make_cylinder_rsolid(
            radius=1.0,
            height=4.0,
            bottom_face_center=(2.0, 2.0, -1.0),
        )
        return scad.cut_rsolid(body, tool)

    result = build()
    store = scad.ContentAddressedStore(policy)

    assert not result.cache_report.hit
    assert store.stats().records == 1
    assert (store.records_dir / "part").exists()


def test_part_accepts_solid_and_wraps_definition_id(tmp_path: Path) -> None:
    @scad.part(id="solid_result", cache=_policy(tmp_path / "cache"))
    def build() -> scad.Solid:
        return scad.make_box_rsolid(width=1.0, height=2.0, depth=3.0)

    result = build()

    assert result.value.part_id == "solid_result"
    assert result.value.body.get_volume() == pytest.approx(6.0)
    assert result.result_node_ids == result.session.result_node_ids


def test_part_deduplicates_concurrent_same_parameter_calls(tmp_path: Path) -> None:
    calls = 0
    guard = threading.Lock()

    @scad.part(id="concurrent_part", cache=_policy(tmp_path / "cache"))
    def build(width: float) -> scad.Solid:
        nonlocal calls
        with guard:
            calls += 1
        time.sleep(0.05)
        return scad.make_box_rsolid(width=width, height=2.0, depth=3.0)

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda _: build(4.0), range(8)))

    assert calls == 1
    assert sum(not result.cache_report.hit for result in results) == 1
    assert all(result.value is results[0].value for result in results)
    assert all(
        result.value.body.get_volume() == pytest.approx(24.0) for result in results
    )


def test_part_rejects_wrong_result_and_mismatched_part_id(tmp_path: Path) -> None:
    @scad.part(id="expected", cache=_policy(tmp_path / "cache-a"))
    def wrong_type():
        scad.make_box_rsolid(width=1.0, height=1.0, depth=1.0)
        return ()

    @scad.part(id="expected", cache=_policy(tmp_path / "cache-b"))
    def wrong_id():
        body = scad.make_box_rsolid(width=1.0, height=1.0, depth=1.0)
        return scad.make_part_rpart(part_id="actual", body=body)

    with pytest.raises(ArtifactValidationError, match="solid_cardinality_invalid"):
        wrong_type()
    with pytest.raises(ArtifactValidationError, match="definition_id_mismatch"):
        wrong_id()


def test_part_rejects_multiple_explicit_results(tmp_path: Path) -> None:
    @scad.part(id="multiple", cache=_policy(tmp_path / "cache"))
    def build():
        first = scad.make_box_rsolid(width=1.0, height=1.0, depth=1.0)
        second = scad.make_box_rsolid(width=2.0, height=2.0, depth=2.0)
        scad.capture_result(value=(first, second))
        return second

    with pytest.raises(ArtifactValidationError, match="exactly one result node"):
        build()


def test_part_rejects_nested_session_and_async(tmp_path: Path) -> None:
    @scad.part(id="nested", cache=_policy(tmp_path / "cache"))
    def build():
        return scad.make_box_rsolid(width=1.0, height=1.0, depth=1.0)

    with scad.GraphSession(graph_id="outer"):
        with pytest.raises(RuntimeError, match="cannot be nested"):
            build()

    async def async_build():
        return None

    with pytest.raises(TypeError, match="does not support async"):
        scad.part(async_build)


def test_part_key_changes_with_arguments_and_file_bytes_not_mtime(
    tmp_path: Path,
) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname='fixture'\nversion='1.0.0'\n", encoding="utf-8"
    )
    source = tmp_path / "input.txt"
    source.write_text("alpha", encoding="utf-8")
    module, function = _load_function(
        tmp_path / "builder.py",
        "import simplecadapi as scad\n"
        "calls = 0\n"
        "def build(width, depth):\n"
        "    global calls\n"
        "    calls += 1\n"
        "    return scad.make_box_rsolid(width=width, height=1.0, depth=depth)\n",
        "build",
    )
    build = scad.part(
        id="dependent",
        inputs=(scad.file_input("input.txt"),),
        cache=_policy(tmp_path / "cache"),
        project_root=tmp_path,
    )(function)

    first = build(2.0, 3.0)
    same = build(2.0, 3.0)
    changed_argument = build(4.0, 3.0)
    previous_mtime = source.stat().st_mtime_ns
    source.write_text("bravo", encoding="utf-8")
    source.touch()
    assert source.stat().st_mtime_ns >= previous_mtime
    changed_file = build(4.0, 3.0)

    assert module.calls == 3
    assert same.cache_report.hit
    assert (
        len(
            {
                first.cache_report.build_key,
                changed_argument.cache_report.build_key,
                changed_file.cache_report.build_key,
            }
        )
        == 3
    )


def test_part_argument_normalizer_rejects_unknown_cycles_and_nonfinite(
    tmp_path: Path,
) -> None:
    class Unknown:
        pass

    @scad.part(id="arguments", cache=_policy(tmp_path / "cache"))
    def build(value):
        return scad.make_box_rsolid(width=1.0, height=1.0, depth=1.0)

    cycle: list[object] = []
    cycle.append(cycle)
    with pytest.raises(ArtifactValidationError, match="unsupported canonical value"):
        build(Unknown())
    with pytest.raises(ArtifactValidationError, match="cycle_invalid"):
        build(cycle)
    with pytest.raises(ArtifactValidationError, match="number must be finite"):
        build(float("nan"))


def test_part_cache_modes_off_read_only_and_refresh(tmp_path: Path) -> None:
    calls = 0
    cache_root = tmp_path / "cache"

    def body() -> scad.Solid:
        nonlocal calls
        calls += 1
        return scad.make_box_rsolid(width=1.0, height=1.0, depth=1.0)

    cached = scad.part(id="modes", cache=_policy(cache_root))(body)
    assert not cached().cache_report.hit
    assert cached().cache_report.hit
    after_cached = calls

    off = scad.part(id="modes", cache=_policy(cache_root, "off"))(body)
    assert not off().cache_report.hit
    assert not off().cache_report.hit
    after_off = calls

    read_only = scad.part(id="modes", cache=_policy(cache_root, "read_only"))(body)
    assert read_only().cache_report.hit
    after_read_only = calls

    refresh = scad.part(id="modes", cache=_policy(cache_root, "refresh"))(body)

    refreshed = refresh()
    assert not refreshed.cache_report.hit
    assert refreshed.cache_report.miss_reason == "refresh"
    assert (after_cached, after_off, after_read_only, calls) == (1, 3, 3, 4)


def test_part_corrupt_payload_rebuilds_and_quarantines(tmp_path: Path) -> None:
    calls = 0
    policy = _policy(tmp_path / "cache")

    @scad.part(id="corrupt", cache=policy)
    def build() -> scad.Solid:
        nonlocal calls
        calls += 1
        return scad.make_box_rsolid(width=1.0, height=1.0, depth=1.0)

    first = build()
    store = scad.ContentAddressedStore(policy)
    entry = store.get("part", first.cache_report.build_key)
    assert entry is not None
    store.object_path(entry.record.object_hash).write_bytes(b"not-a-cache-payload")

    rebuilt = scad.part(id="corrupt", cache=policy)(build.__wrapped__)()

    assert calls == 2
    assert not rebuilt.cache_report.hit
    assert rebuilt.cache_report.corrupt_entries == 0
    assert rebuilt.cache_report.miss_reason == "record_missing"
    assert store.stats().quarantined >= 1


def test_part_default_export_is_product_package(tmp_path: Path) -> None:
    output = tmp_path / "out"

    @scad.part(
        id="exported",
        cache=_policy(tmp_path / "cache"),
        export_dir=output,
    )
    def build() -> scad.Solid:
        return scad.make_box_rsolid(width=1.0, height=2.0, depth=3.0)

    result = build()

    assert set(result.artifact_paths) == {"product"}
    assert result.artifact_paths["product"].name == "exported.scadpkg"
    assert (
        scad.load_product_package(result.artifact_paths["product"]).definition_id
        == "exported"
    )


def test_part_definition_archive_round_trip_and_reexport(tmp_path: Path) -> None:
    @scad.part(id="definition_io", cache=_policy(tmp_path / "cache"))
    def build() -> scad.Solid:
        return scad.make_box_rsolid(width=2.0, height=3.0, depth=4.0)

    result = build()
    first = result.export_definition(path=tmp_path / "first.part-definition.zip")
    loaded = scad.load_part_definition(first)
    second = scad.export_part_definition(
        loaded,
        tmp_path / "second.part-definition.zip",
    )

    assert loaded.canonical_bytes == result.definition.canonical_bytes
    assert first.read_bytes() == second.read_bytes()


def test_part_definition_archive_rejects_mutated_and_extra_blobs(
    tmp_path: Path,
) -> None:
    from simplecadapi.scene.archive import canonical_zip_bytes, preflight_zip_bytes

    @scad.part(id="definition_corrupt", cache=_policy(tmp_path / "cache"))
    def build() -> scad.Solid:
        return scad.make_box_rsolid(width=1.0, height=1.0, depth=1.0)

    encoded = scad.encode_part_definition(build().definition)
    archive = preflight_zip_bytes(encoded, manifest_name="part-definition.json")
    members = dict(archive.members)
    body_name = next(name for name in members if name.endswith(".brep"))
    members[body_name] += b"x"
    mutated = canonical_zip_bytes(members, manifest_name="part-definition.json")
    with pytest.raises(
        ArtifactValidationError, match="blob_size_mismatch|blob_hash_mismatch"
    ):
        scad.load_part_definition(mutated)

    members = dict(archive.members)
    members["blobs/unexpected.bin"] = b"unexpected"
    extra = canonical_zip_bytes(members, manifest_name="part-definition.json")
    with pytest.raises(ArtifactValidationError, match="member set differs"):
        scad.load_part_definition(extra)
