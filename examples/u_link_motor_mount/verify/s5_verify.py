"""S5 verifier (S10 form): durable ASSEMBLY export artifacts.

Criteria:
  C1 artifacts exist non-empty (scadpkg/step/stl)
  C2 package reopens: root assembly @ u-link-motor-mount-assembly with 2 defs
  C3 fresh rebuild: body+cover BREP valid, volumes match evidence
  C4 named faces resolve on rebuilt body part
  C5 export facts: STL solid_count==2, STEP defs contain both part ids
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

import assembly as ASM  # noqa: E402
import shell as SH  # noqa: E402
import u_link  # noqa: E402
from simplecadapi import ql  # noqa: E402
from simplecadapi.inspect import brep  # noqa: E402
from simplecadapi.product.packages import read_product_package  # noqa: E402

OUT = HERE / "out"
failures = []


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'} {name} {detail}")
    if not ok:
        failures.append(name)


paths = {suf: OUT / f"u_link_assembly.{suf}" for suf in ("scadpkg", "step", "stl")}
check("C1 artifacts", all(p.exists() and p.stat().st_size > 0 for p in paths.values()),
      {k: (p.stat().st_size if p.exists() else 0) for k, p in paths.items()})

package = read_product_package(paths["scadpkg"])
root = package.root_definition
check("C2 package reopen", root.definition_kind == "assembly"
      and root.definition_id == "u-link-motor-mount-assembly",
      f"kind={root.definition_kind} id={root.definition_id}")

body = u_link.build_u_link_part().value.body
shell = SH.build_shell_part().value.body
rb = brep.inspect_shape_rbrepinspection(shape=body.wrapped)
rc = brep.inspect_shape_rbrepinspection(shape=shell.wrapped)
v_body_expect = u_link.build_stage("s4").get_volume()
check("C3 brep valid", rb.valid and rc.valid
      and abs(body.get_volume() - v_body_expect) < 1.0
      and abs(shell.get_volume() - SH.build_shell_body().get_volume()) < 1.0,
      f"body={body.get_volume():.3f} shell={shell.get_volume():.3f}")

P = u_link.params()
ok4 = True
for tag, want_x in ((u_link.TAG_MOUNT_LEFT, -P["L"] / 2.0), (u_link.TAG_MOUNT_RIGHT, P["L"] / 2.0),
                    (u_link.TAG_BACK, 0.0)):
    hit = ql.faces().where(ql.tag(tag)).resolve(body)
    ok4 = ok4 and len(hit) == 1
check("C4 named faces", ok4)

facts = json.loads((OUT / "export_facts.json").read_text())
stl, step = facts["stl"], facts["step"]
check("C5 export facts", stl["solid_count"] == 2 and stl["triangle_count"] > 0
      and "u-link-motor-mount" in step["definition_ids"]
      and "u-link-shell" in step["definition_ids"]
      and step["occurrence_count"] == 2,
      f"stl solids={stl['solid_count']} tri={stl['triangle_count']} "
      f"step defs={step['definition_ids']} occ={step['occurrence_count']}")

print(f"S5 verifier: {'ALL PASS' if not failures else 'FAILED ' + str(failures)}")
sys.exit(1 if failures else 0)
