import cadquery as cq

result = (
    cq.Workplane("YZ")
    .box(110.69, 154.26, 13.98)
    .faces(">X").workplane()
    .rarray(20.37, 75.31, 4, 2)
    .rect(11.65, 38.68)
    .cutBlind(-6.99)
)

show_object(result)
