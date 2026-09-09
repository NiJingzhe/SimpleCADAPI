import cadquery as cq

result = (
cq.Workplane("YZ")
.circle(12.5)
.extrude(16.2, taper=24.257)
.faces(">X").workplane()
.circle(5.2)
.extrude(9.0, taper=-10.697)
.faces(">X").workplane()
.circle(6.9)
.extrude(10.8)
.cut(
cq.Workplane("YZ")
.transformed(offset=cq.Vector(7.245, 0.0, 25.8), rotate=cq.Vector(0, 0, 0))
.cylinder(19.8, 1.2)
)
.cut(
cq.Workplane("YZ")
.transformed(offset=cq.Vector(6.694, 2.773, 25.8), rotate=cq.Vector(0, 0, 0))
.cylinder(19.8, 1.2)
)
.cut(
cq.Workplane("YZ")
.transformed(offset=cq.Vector(5.123, 5.123, 25.8), rotate=cq.Vector(0, 0, 0))
.cylinder(19.8, 1.2)
)
.cut(
cq.Workplane("YZ")
.transformed(offset=cq.Vector(2.773, 6.694, 25.8), rotate=cq.Vector(0, 0, 0))
.cylinder(19.8, 1.2)
)
.cut(
cq.Workplane("YZ")
.transformed(offset=cq.Vector(0.0, 7.245, 25.8), rotate=cq.Vector(0, 0, 0))
.cylinder(19.8, 1.2)
)
.cut(
cq.Workplane("YZ")
.transformed(offset=cq.Vector(-2.773, 6.694, 25.8), rotate=cq.Vector(0, 0, 0))
.cylinder(19.8, 1.2)
)
.cut(
cq.Workplane("YZ")
.transformed(offset=cq.Vector(-5.123, 5.123, 25.8), rotate=cq.Vector(0, 0, 0))
.cylinder(19.8, 1.2)
)
.cut(
cq.Workplane("YZ")
.transformed(offset=cq.Vector(-6.694, 2.773, 25.8), rotate=cq.Vector(0, 0, 0))
.cylinder(19.8, 1.2)
)
.cut(
cq.Workplane("YZ")
.transformed(offset=cq.Vector(-7.245, 0.0, 25.8), rotate=cq.Vector(0, 0, 0))
.cylinder(19.8, 1.2)
)
.cut(
cq.Workplane("YZ")
.transformed(offset=cq.Vector(-6.694, -2.773, 25.8), rotate=cq.Vector(0, 0, 0))
.cylinder(19.8, 1.2)
)
.cut(
cq.Workplane("YZ")
.transformed(offset=cq.Vector(-5.123, -5.123, 25.8), rotate=cq.Vector(0, 0, 0))
.cylinder(19.8, 1.2)
)
.cut(
cq.Workplane("YZ")
.transformed(offset=cq.Vector(-2.773, -6.694, 25.8), rotate=cq.Vector(0, 0, 0))
.cylinder(19.8, 1.2)
)
.cut(
cq.Workplane("YZ")
.transformed(offset=cq.Vector(-0.0, -7.245, 25.8), rotate=cq.Vector(0, 0, 0))
.cylinder(19.8, 1.2)
)
.cut(
cq.Workplane("YZ")
.transformed(offset=cq.Vector(2.773, -6.694, 25.8), rotate=cq.Vector(0, 0, 0))
.cylinder(19.8, 1.2)
)
.cut(
cq.Workplane("YZ")
.transformed(offset=cq.Vector(5.123, -5.123, 25.8), rotate=cq.Vector(0, 0, 0))
.cylinder(19.8, 1.2)
)
.cut(
cq.Workplane("YZ")
.transformed(offset=cq.Vector(6.694, -2.773, 25.8), rotate=cq.Vector(0, 0, 0))
.cylinder(19.8, 1.2)
)
.faces("<X").workplane()
.hole(10.0)
)

# Export
show_object(result)
