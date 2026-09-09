import cadquery as cq

result = (
    cq.Workplane("XY")
    .polygon(6, 6.35)
    .extrude(2.4)
    .faces(">Z").workplane()
    .circle(1.5)
    .cutThruAll()
)

show_object(result)
