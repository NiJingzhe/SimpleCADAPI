import cadquery as cq

result = (
    cq.Workplane("YZ")
    .polyline([[17.5, -12.6], [31.5, -12.6], [62.4, -12.6], [62.4, -5.0], [70.0, -5.0], [70.0, 5.0], [62.4, 5.0], [62.4, 12.6], [31.5, 12.6], [17.5, 12.6]])
    .close()
    .revolve(360, (0, 0, 0), (0, 1, 0))
)

show_object(result)
