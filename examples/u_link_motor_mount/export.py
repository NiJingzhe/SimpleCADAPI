"""S10 export: assembly package (body+shell) + STEP/STL + evidence renders.

Artifacts (out/):
  u_link_assembly.scadpkg    canonical durable product (assembly: body+cover)
  u_link_assembly.step/.stl  external formats
  render_front/iso.png       body with named mounting faces highlighted
  render_assembly.png        body+cover installed view
  export_facts.json          report facts consumed by verify/s5_verify.py
"""
import json
import sys
from dataclasses import asdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import simplecadapi as scad  # noqa: E402
from simplecadapi import ql  # noqa: E402

import assembly as ASM  # noqa: E402
import shell as SH  # noqa: E402
import u_link  # noqa: E402

OUT = HERE / "out"
OUT.mkdir(parents=True, exist_ok=True)

result = ASM.build_u_link_assembly()
asm = result.value
report = asm._get_runtime("constraint_report")
print(f"assembly: components={asm.component_ids()} residuals_ok="
      f"{all(r['within_tolerance'] for r in report['residuals'])}")

body = u_link.build_u_link_part().value.body
shell = SH.build_shell_part().value.body
tag_hits = {
    tag: len(ql.faces().where(ql.tag(tag)).resolve(body))
    for tag in (u_link.TAG_MOUNT_LEFT, u_link.TAG_MOUNT_RIGHT, u_link.TAG_BACK)
}
print(f"body: volume={body.get_volume():.3f} mount/back tag hits={tag_hits}")

package_path = OUT / "u_link_assembly.scadpkg"
capture = scad.capture(result, package_path)
print(f"captured: {package_path.name} bytes={package_path.stat().st_size}")

step_report = scad.exporter.step.export_product_package_to_step(
    data=package_path, output_path=OUT / "u_link_assembly.step")
stl_report = scad.exporter.stl.export_product_package_to_stl(
    data=package_path, output_path=OUT / "u_link_assembly.stl",
    linear_deflection=0.05, angular_deflection_degrees=10.0)
print(f"step defs={step_report.definition_ids} occ={step_report.occurrence_count}")
print(f"stl solids={stl_report.solid_count} tri={stl_report.triangle_count}")

# 安装面法向 = 部件 +Y；渲染相机方位角绕 +Z 度量 → 正对安装面须 azim=90
scad.render_screenshot_rpath(
    shapes=body, output_path=str(OUT / "render_front.png"),
    highlight_tags=[u_link.TAG_MOUNT_LEFT, u_link.TAG_MOUNT_RIGHT],
    view=(0.0, 90.0), show_axes=False, show_callouts=False, show_legend=False)
scad.render_screenshot_rpath(
    shapes=body, output_path=str(OUT / "render_iso.png"),
    highlight_tags=[u_link.TAG_MOUNT_LEFT, u_link.TAG_MOUNT_RIGHT, u_link.TAG_BACK],
    view=(35.0, 30.0), show_axes=False, show_callouts=False, show_legend=False)
scad.render_screenshot_rpath(
    shapes=[body, shell], output_path=str(OUT / "render_assembly.png"),
    view=(35.0, 30.0), show_axes=False, show_callouts=False, show_legend=False)
scad.render_screenshot_rpath(
    shapes=shell, output_path=str(OUT / "render_shell.png"),
    view=(35.0, 30.0), show_axes=False, show_callouts=False, show_legend=False)

(OUT / "export_facts.json").write_text(json.dumps({
    "stl": asdict(stl_report), "step": step_report.to_dict(),
    "mount_tag_hits": tag_hits,
    "assembly_components": list(asm.component_ids()),
}, indent=2, default=str))
print("export done")
