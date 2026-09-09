import cadquery as cq

result = (
    cq.Workplane("XZ")
    .circle(32.4)
    .extrude(5.0)
    .faces(">Y").workplane()
    .hole(37.0)
    .edges(">Y")
    .chamfer(0.4)
)

show_object(result)
