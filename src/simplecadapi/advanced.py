from .operations import *
from .core import *


def make_round_spring(
    coil_radius: float = 1.0,
    string_radius: float = 0.1,
    pitch: float = 0.5,
    turns: int = 5,
) -> Body:

    """创建一个圆形弹簧模型
    """

    with LocalCoordinateSystem(
        origin=(0, 0, 0),
        x_axis=(0, 1, 0),
        y_axis=(0, 0, 1),
    ):

        circle = make_circle(string_radius)

    return helical_sweep(
        profile=circle,
        pitch=pitch,
        turns=turns,
        points_per_turn=20,  # 高精度
        smooth=True,
        coil_radius=coil_radius
    )


def make_square_spring(
    coil_radius: float = 1.0,
    string_radius: float = 0.1,
    pitch: float = 0.5,
    turns: int = 5,
) -> Body:
    """创建一个方形弹簧模型
    """

    with LocalCoordinateSystem(
        origin=(0, 0, 0),
        x_axis=(0, 1, 0),
        y_axis=(0, 0, 1),
    ):

        square = make_rectangle(string_radius * 2, string_radius * 2)

    return helical_sweep(
        profile=square,
        pitch=pitch,
        turns=turns,
        points_per_turn=20,  # 高精度
        smooth=True,
        coil_radius=coil_radius
    )
   
   
def make_bolt_body_with_triangle_thread(
    length: float = 10.0,
    diameter: float = 2.0,
    thread_pitch: float = 0.5,
    thread_start: float = 2,
    thread_end: float = 10,
    thread_depth: float = 0.1,
) -> Body:
    """创建一个带有三角形螺纹的螺栓模型
    """

    bolt_cylinder = make_cylinder(diameter / 2, length)

    bolt_cylinder = translate_body(
        bolt_cylinder,
        vector=(0, 0, length / 2)
    )

    with LocalCoordinateSystem(
        origin=(0, 0, 0),
        x_axis=(0, 1, 0),
        y_axis=(0, 0, 1),
    ):
        triangle_points = [
            make_point(0, -thread_depth/2, 0),     # 底部
            make_point(thread_pitch/2, 0, 0),      # 右顶点
            make_point(0, thread_depth/2, 0),      # 顶部
        ]
    
        triangle_lines = []
        for i in range(len(triangle_points)):
            p1 = triangle_points[i]
            p2 = triangle_points[(i + 1) % len(triangle_points)]
            triangle_lines.append(make_line([p1, p2], "segment"))
    
        thread_profile = make_sketch(triangle_lines)

    # 根据start和end位置计算螺纹参数
    thread_length = thread_end - thread_start
    thread_turns = thread_length / thread_pitch

    # 创建扫掠，并移动到正确的起始位置
    thread_sweep = helical_sweep(
        profile=thread_profile,
        pitch=thread_pitch,
        turns=thread_turns,
        points_per_turn=20,
        smooth=True,
        coil_radius=diameter / 2
    )
    
    # 将螺纹移动到正确的起始位置
    thread_sweep = translate_body(
        thread_sweep,
        vector=(0, 0, thread_start)
    )

    # 将螺纹扫掠与螺栓主体合并
    bolt_with_thread = union(bolt_cylinder, thread_sweep)

    return bolt_with_thread