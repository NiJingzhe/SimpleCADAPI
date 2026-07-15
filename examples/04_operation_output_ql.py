"""Query kernel-proven feature outputs and projected source evidence.

Run from the repository root with:
    uv run --no-sync python examples/04_operation_output_ql.py
"""

from pathlib import Path

import simplecadapi as scad
from simplecadapi import ql as Q


OUT = Path("examples/out")
OUT.mkdir(parents=True, exist_ok=True)
MODEL_JSON_PATH = OUT / "operation_output_ql.model.json"


with scad.GraphSession() as session:
    profile = scad.make_rectangle_rface(width=12.0, height=8.0)

    # The returned semantic view must feed the feature for the source binding to
    # participate in replay and kernel-backed source projection.
    source_edge = (
        Q.edges()
        .where(Q.curve_type(kind="line"))
        .order_by(Q.center_axis(axis="x"), desc=True)
        .take(1)
        .exactly(1)
    )
    profile = scad.apply_tag_rselection(
        scope=profile,
        targets=source_edge,
        tag="role.profile_reference_edge",
    )
    tagged_edge = scad.select_edges_by_tag(
        shape=profile,
        tag="role.profile_reference_edge",
        scope="local",
    )[0]
    source_binding_id = scad.explain_tag(
        shape=tagged_edge,
        tag="role.profile_reference_edge",
        scope="local",
    )[0]["binding_id"]
    source_topo_id = tagged_edge.topo_id

    body = scad.extrude_rsolid(
        profile=profile,
        direction=(0.0, 0.0, 1.0),
        distance=6.0,
        result_tag="part.output_role_demo",
        start_face_tag="anchor.base",
        end_face_tag="role.mounting_surface",
        side_faces_tag="group.outer_walls",
    )

end_selector = (
    Q.faces()
    .where(Q.output_role(role_name="extrusion.end"))
    .exactly(1)
)
source_binding_selector = (
    Q.faces()
    .where(Q.source_binding(binding_id=source_binding_id))
    .exactly(1)
)
source_topology_selector = (
    Q.faces()
    .where(Q.source_topology(topo_id=source_topo_id))
    .exactly(1)
)

end_face = end_selector.resolve(body)[0]
projected_face = source_binding_selector.resolve(body)[0]
same_projected_face = source_topology_selector.resolve(body)[0]

model_json = scad.export_model_json(session=session)
MODEL_JSON_PATH.write_text(model_json, encoding="utf-8")
replayed_body = next(
    shape
    for shape in scad.replay_model_json(json_str=model_json)
    if isinstance(shape, scad.Solid)
)

print("end_role_count", len(end_selector.resolve(body)))
print("end_face_tags", scad.list_tags(shape=end_face, scope="local"))
print("projected_source_count", len(source_binding_selector.resolve(body)))
print("source_queries_agree", projected_face.topo_id == same_projected_face.topo_id)
print("replayed_end_role_count", len(end_selector.resolve(replayed_body)))
print(
    "replayed_projected_source_count",
    len(source_binding_selector.resolve(replayed_body)),
)
print("wrote", MODEL_JSON_PATH)
