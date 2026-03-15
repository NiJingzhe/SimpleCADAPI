"""
SimpleCAD API操作函数实现
基于README中的API设计，实现各种几何操作
"""

from typing import List, Tuple, Union, Optional, Sequence, cast, Dict
import math
import numpy as np
import cadquery as cq
from cadquery import Vector
from OCP.BRepBuilderAPI import BRepBuilderAPI_Sewing
from OCP.TopAbs import TopAbs_SHELL
from OCP.TopExp import TopExp_Explorer

from .core import (
    Vertex,
    Edge,
    Wire,
    Face,
    Solid,
    AnyShape,
    get_current_cs,
)
from .field import (
    ScalarField,
    bounds_rbbox,
    eval_rarray,
    make_box_rscalarfield,
    intersect_rscalarfield,
)

from cadquery.occ_impl.shapes import fuse, cut, intersect, revolve


# =============================================================================
# 基础图形创建函数
# =============================================================================


def make_point_rvertex(x: float, y: float, z: float) -> Vertex:
    """创建三维空间中的点并返回顶点对象

    Args:
        x (float): X坐标值，用于定义点在X轴方向的位置
        y (float): Y坐标值，用于定义点在Y轴方向的位置
        z (float): Z坐标值，用于定义点在Z轴方向的位置

    Returns:
        Vertex: 创建的顶点对象，包含指定坐标的点

    Raises:
        ValueError: 当坐标无效时抛出异常

    Usage:
        创建三维空间中的几何点，通常用作其他几何对象的构造参数，如作为线段的端点、
        圆弧的控制点等。支持当前坐标系变换。

    Example:
         # 创建原点
         origin = make_point_rvertex(0, 0, 0)

         # 创建指定坐标的点
         point = make_point_rvertex(1.5, 2.0, 3.0)

         # 在工作平面中创建点
         with SimpleWorkplane((1, 1, 1)):
        ...     local_point = make_point_rvertex(0, 0, 0)  # 实际位置为(1, 1, 1)
    """
    try:
        cs = get_current_cs()
        global_point = cs.transform_point(np.array([x, y, z]))
        cq_vertex = cq.Vertex.makeVertex(*global_point)
        return Vertex(cq_vertex)
    except Exception as e:
        raise ValueError(f"创建点失败: {e}. 请检查坐标值是否有效。")


def make_line_redge(
    start: Tuple[float, float, float], end: Tuple[float, float, float]
) -> Edge:
    """创建两点之间的直线段并返回边对象

    Args:
        start (Tuple[float, float, float]): 起始点坐标 (x, y, z)，定义线段的起点
        end (Tuple[float, float, float]): 结束点坐标 (x, y, z)，定义线段的终点

    Returns:
        Edge: 创建的边对象，表示连接两点的直线段

    Raises:
        ValueError: 当坐标无效或起始点与结束点重合时抛出异常

    Usage:
        创建两点之间的直线段，是构建复杂几何形状的基础元素。可用于构造线框、
        创建草图轮廓、定义路径等。支持当前坐标系变换。

    Example:
         # 创建水平线段
         line = make_line_redge((0, 0, 0), (5, 0, 0))

         # 创建三维空间中的线段
         line_3d = make_line_redge((1, 1, 1), (3, 2, 4))

         # 在工作平面中创建线段
         with SimpleWorkplane((0, 0, 1)):
        ...     elevated_line = make_line_redge((0, 0, 0), (2, 2, 0))
    """
    try:
        cs = get_current_cs()
        start_global = cs.transform_point(np.array(start))
        end_global = cs.transform_point(np.array(end))

        start_vec = Vector(*start_global)
        end_vec = Vector(*end_global)

        cq_edge = cq.Edge.makeLine(start_vec, end_vec)
        return Edge(cq_edge)
    except Exception as e:
        raise ValueError(f"创建线段失败: {e}. 请检查起始点和结束点坐标是否有效。")


def make_segment_redge(
    start: Tuple[float, float, float], end: Tuple[float, float, float]
) -> Edge:
    """创建线段并返回边对象（make_line_redge的别名函数）

    Args:
        start (Tuple[float, float, float]): 起始点坐标 (x, y, z)，定义线段的起点
        end (Tuple[float, float, float]): 结束点坐标 (x, y, z)，定义线段的终点

    Returns:
        Edge: 创建的边对象，表示连接两点的直线段

    Usage:
        与make_line_redge功能完全相同，提供更直观的函数名称。用于创建两点之间的
        直线段，是构建复杂几何形状的基础元素。

    Example:
         # 创建垂直线段
         vertical_line = make_segment_redge((0, 0, 0), (0, 0, 5))

         # 创建对角线段
         diagonal = make_segment_redge((0, 0, 0), (1, 1, 1))
    """
    return make_line_redge(start, end)


def make_segment_rwire(
    start: Tuple[float, float, float], end: Tuple[float, float, float]
) -> Wire:
    """创建线段并返回线对象

    Args:
        start (Tuple[float, float, float]): 起始点坐标 (x, y, z)，定义线段的起点
        end (Tuple[float, float, float]): 结束点坐标 (x, y, z)，定义线段的终点

    Returns:
        Wire: 创建的线对象，包含一个连接两点的直线段

    Raises:
        ValueError: 当坐标无效或创建线对象失败时抛出异常

    Usage:
        创建包含单个线段的线对象，用于构建更复杂的线框结构。与make_segment_redge
        不同，此函数返回的是线对象，可以与其他线对象连接形成复杂路径。

    Example:
         # 创建基本线段线
         wire = make_segment_rwire((0, 0, 0), (3, 0, 0))

         # 创建斜线段
         diagonal_wire = make_segment_rwire((0, 0, 0), (2, 2, 0))
    """
    try:
        edge = make_line_redge(start, end)
        cq_wire = cq.Wire.assembleEdges([edge.cq_edge])
        return Wire(cq_wire)
    except Exception as e:
        raise ValueError(f"创建线段线失败: {e}")


def make_circle_redge(
    center: Tuple[float, float, float],
    radius: float,
    normal: Tuple[float, float, float] = (0, 0, 1),
) -> Edge:
    """创建圆形并返回边对象

    Args:
        center (Tuple[float, float, float]): 圆心坐标 (x, y, z)，定义圆的中心位置
        radius (float): 圆的半径，必须为正数
        normal (Tuple[float, float, float], optional): 圆所在平面的法向量 (x, y, z)，
            默认为 (0, 0, 1) 表示XY平面

    Returns:
        Edge: 创建的边对象，表示一个完整的圆形

    Raises:
        ValueError: 当半径小于等于0或其他参数无效时抛出异常

    Usage:
        创建圆形边对象，用于构建圆形轮廓、圆弧路径等。圆的方向由法向量确定，
        支持在任意平面内创建圆形。支持当前坐标系变换。

    Example:
         # 创建XY平面上的圆
         circle = make_circle_redge((0, 0, 0), 2.0)

         # 创建垂直平面上的圆
         vertical_circle = make_circle_redge((0, 0, 0), 1.5, (1, 0, 0))

         # 创建指定位置的圆
         offset_circle = make_circle_redge((2, 3, 1), 1.0, (0, 0, 1))
    """
    try:
        if radius <= 0:
            raise ValueError("半径必须大于0")

        cs = get_current_cs()
        center_global = cs.transform_point(np.array(center))
        normal_global = cs.transform_point(np.array(normal)) - cs.origin

        center_vec = Vector(*center_global)
        normal_vec = Vector(*normal_global)

        cq_edge = cq.Edge.makeCircle(radius, center_vec, normal_vec)
        return Edge(cq_edge)
    except Exception as e:
        raise ValueError(f"创建圆失败: {e}. 请检查圆心坐标、半径和法向量是否有效。")


def make_circle_rwire(
    center: Tuple[float, float, float],
    radius: float,
    normal: Tuple[float, float, float] = (0, 0, 1),
) -> Wire:
    """创建圆形并返回线对象

    Args:
        center (Tuple[float, float, float]): 圆心坐标 (x, y, z)，定义圆的中心位置
        radius (float): 圆的半径，必须为正数
        normal (Tuple[float, float, float], optional): 圆所在平面的法向量 (x, y, z)，
            默认为 (0, 0, 1) 表示XY平面

    Returns:
        Wire: 创建的线对象，表示一个完整的圆形轮廓

    Raises:
        ValueError: 当半径小于等于0或其他参数无效时抛出异常

    Usage:
        创建圆形线对象，用于构建封闭的圆形轮廓。与make_circle_redge不同，
        此函数返回的是线对象，可以直接用于创建面或进行其他线操作。

    Example:
         # 创建标准圆形轮廓
         circle_wire = make_circle_rwire((0, 0, 0), 3.0)

         # 创建小圆轮廓
         small_circle = make_circle_rwire((1, 1, 0), 0.5)
    """
    try:
        edge = make_circle_redge(center, radius, normal)
        cq_wire = cq.Wire.assembleEdges([edge.cq_edge])
        return Wire(cq_wire)
    except Exception as e:
        raise ValueError(f"创建圆线失败: {e}")


def make_circle_rface(
    center: Tuple[float, float, float],
    radius: float,
    normal: Tuple[float, float, float] = (0, 0, 1),
) -> Face:
    """创建圆形并返回面对象

    Args:
        center (Tuple[float, float, float]): 圆心坐标 (x, y, z)，定义圆的中心位置
        radius (float): 圆的半径，必须为正数
        normal (Tuple[float, float, float], optional): 圆所在平面的法向量 (x, y, z)，
            默认为 (0, 0, 1) 表示XY平面

    Returns:
        Face: 创建的面对象，表示一个实心的圆形面

    Raises:
        ValueError: 当半径小于等于0或其他参数无效时抛出异常

    Usage:
        创建圆形面对象，用于构建实心圆形截面。可以用于拉伸、旋转等操作来创建
        圆柱体、圆锥体等三维几何体。面积等于πr²。

    Example:
         # 创建标准圆形面
         circle_face = make_circle_rface((0, 0, 0), 2.0)
         area = circle_face.get_area()  # 面积为π×2²≈12.57

         # 创建用于拉伸的圆形截面
         profile = make_circle_rface((0, 0, 0), 1.0)
         cylinder = extrude_rsolid(profile, (0, 0, 1), 5.0)
    """
    try:
        wire = make_circle_rwire(center, radius, normal)
        cq_face = cq.Face.makeFromWires(wire.cq_wire)
        return Face(cq_face)
    except Exception as e:
        raise ValueError(f"创建圆面失败: {e}")


def make_rectangle_rwire(
    width: float,
    height: float,
    center: Tuple[float, float, float] = (0, 0, 0),
    normal: Tuple[float, float, float] = (0, 0, 1),
) -> Wire:
    """创建矩形并返回线对象

    Args:
        width (float): 矩形的宽度，必须为正数
        height (float): 矩形的高度，必须为正数
        center (Tuple[float, float, float], optional): 矩形中心坐标 (x, y, z)，
            默认为 (0, 0, 0)
        normal (Tuple[float, float, float], optional): 矩形所在平面的法向量 (x, y, z)，
            默认为 (0, 0, 1) 表示XY平面

    Returns:
        Wire: 创建的线对象，表示一个封闭的矩形轮廓

    Raises:
        ValueError: 当宽度或高度小于等于0或其他参数无效时抛出异常

    Usage:
        创建矩形线对象，用于构建矩形轮廓。矩形以指定中心点为中心，在指定平面内
        创建。可以用于构建复杂的多边形轮廓或作为拉伸的基础轮廓。

    Example:
         # 创建标准矩形轮廓
         rect = make_rectangle_rwire(4.0, 3.0)

         # 创建偏移的矩形
         offset_rect = make_rectangle_rwire(2.0, 2.0, (1, 1, 0))

         # 创建垂直平面上的矩形
         vertical_rect = make_rectangle_rwire(3.0, 2.0, (0, 0, 0), (1, 0, 0))
    """
    try:
        if width <= 0 or height <= 0:
            raise ValueError("宽度和高度必须大于0")

        cs = get_current_cs()
        center_global = cs.transform_point(np.array(center))
        normal_global = cs.transform_point(np.array(normal)) - cs.origin

        # 标准化法向量
        normal_vec = normal_global / np.linalg.norm(normal_global)

        # 创建本地坐标系
        # 如果法向量接近Z轴，使用X轴作为参考
        if abs(normal_vec[2]) > 0.9:
            ref_vec = np.array([1.0, 0.0, 0.0])
        else:
            ref_vec = np.array([0.0, 0.0, 1.0])

        # 计算本地坐标系的X和Y轴
        local_x = np.cross(normal_vec, ref_vec)
        local_x = local_x / np.linalg.norm(local_x)
        local_y = np.cross(normal_vec, local_x)
        local_y = local_y / np.linalg.norm(local_y)

        # 创建矩形的四个顶点（在本地坐标系中）
        half_w, half_h = width / 2, height / 2
        local_points = [
            (-half_w, -half_h),
            (half_w, -half_h),
            (half_w, half_h),
            (-half_w, half_h),
        ]

        # 转换到全局坐标系
        global_points = []
        for local_point in local_points:
            # 在本地坐标系中的点
            point_3d = (
                center_global + local_point[0] * local_x + local_point[1] * local_y
            )
            global_points.append(Vector(*point_3d))

        # 创建边
        edges = []
        for i in range(len(global_points)):
            start = global_points[i]
            end = global_points[(i + 1) % len(global_points)]
            edges.append(cq.Edge.makeLine(start, end))

        cq_wire = cq.Wire.assembleEdges(edges)
        return Wire(cq_wire)
    except Exception as e:
        raise ValueError(f"创建矩形失败: {e}. 请检查宽度、高度和中心点坐标是否有效。")


def make_rectangle_rface(
    width: float,
    height: float,
    center: Tuple[float, float, float] = (0, 0, 0),
    normal: Tuple[float, float, float] = (0, 0, 1),
) -> Face:
    """创建矩形并返回面对象

    Args:
        width (float): 矩形的宽度，必须为正数
        height (float): 矩形的高度，必须为正数
        center (Tuple[float, float, float], optional): 矩形中心坐标 (x, y, z)，
            默认为 (0, 0, 0)
        normal (Tuple[float, float, float], optional): 矩形所在平面的法向量 (x, y, z)，
            默认为 (0, 0, 1) 表示XY平面

    Returns:
        Face: 创建的面对象，表示一个实心的矩形面

    Raises:
        ValueError: 当宽度或高度小于等于0或其他参数无效时抛出异常

    Usage:
        创建矩形面对象，用于构建实心矩形截面。可以用于拉伸、旋转等操作来创建
        立方体、棱柱等三维几何体。面积等于width×height。

    Example:
         # 创建标准矩形面
         rect_face = make_rectangle_rface(5.0, 3.0)
         area = rect_face.get_area()  # 面积为5×3=15

         # 创建用于拉伸的矩形截面
         profile = make_rectangle_rface(2.0, 2.0)
         box = extrude_rsolid(profile, (0, 0, 1), 3.0)
    """
    try:
        wire = make_rectangle_rwire(width, height, center, normal)
        cq_face = cq.Face.makeFromWires(wire.cq_wire)
        return Face(cq_face)
    except Exception as e:
        raise ValueError(f"创建矩形面失败: {e}")


def make_face_from_wire_rface(
    wire: Wire, normal: Tuple[float, float, float] = (0, 0, 1)
) -> Face:
    """从封闭的线对象创建面对象

    Args:
        wire (Wire): 输入的线对象，必须是封闭的线轮廓
        normal (Tuple[float, float, float], optional): 期望的面法向量 (x, y, z)，
            用于确定面的方向，默认为 (0, 0, 1)

    Returns:
        Face: 创建的面对象，由输入的线轮廓围成的面

    Raises:
        ValueError: 当输入的线对象无效、不封闭或创建面失败时抛出异常

    Usage:
        将封闭的线轮廓转换为面对象，用于从复杂的线框轮廓创建面。输入的线必须
        是封闭的，函数会检查面的法向量方向，如果与期望方向相反会发出警告。

    Example:
         # 从矩形线创建面
         rect_wire = make_rectangle_rwire(3.0, 2.0)
         rect_face = make_face_from_wire_rface(rect_wire)

         # 从圆形线创建面
         circle_wire = make_circle_rwire((0, 0, 0), 1.5)
         circle_face = make_face_from_wire_rface(circle_wire)

         # 从多边形线创建面
         points = [(0, 0, 0), (2, 0, 0), (2, 2, 0), (0, 2, 0)]
         poly_wire = make_polyline_rwire(points, closed=True)
         poly_face = make_face_from_wire_rface(poly_wire)
    """
    try:
        if not isinstance(wire, Wire):
            raise ValueError("输入必须是Wire类型")

        # 检查Wire是否封闭
        if not wire.is_closed():
            raise ValueError("Wire必须是封闭的才能创建面")

        # 获取当前坐标系并转换法向量
        cs = get_current_cs()
        global_normal = cs.transform_point(np.array(normal)) - cs.origin

        # 标准化法向量
        normal_vec = global_normal / np.linalg.norm(global_normal)

        # 创建面
        cq_face = cq.Face.makeFromWires(wire.cq_wire)

        # 检查面的法向量是否与期望方向一致
        # normalAt方法返回tuple (normal_vector, u_vector)
        face_normal_tuple = cq_face.normalAt(0.5, 0.5)
        face_normal = face_normal_tuple[0]  # 取第一个元素作为法向量
        face_normal_vec = np.array([face_normal.x, face_normal.y, face_normal.z])

        # 计算法向量的点积，如果小于0则需要反向
        dot_product = np.dot(normal_vec, face_normal_vec)

        if dot_product < 0:
            # 反向面（通过反向Wire的方向）
            # CADQuery的Wire没有直接的reverse方法，我们需要重新构建
            # 简单的方法是使用makeFromWires的orientation参数
            # 或者我们接受当前面的方向，添加一个警告
            print(f"警告: 创建的面的法向量与期望方向相反 (点积: {dot_product:.3f})")

        face = Face(cq_face)

        # 复制标签和元数据
        face._tags = wire._tags.copy()
        face._metadata = wire._metadata.copy()

        return face
    except Exception as e:
        raise ValueError(f"创建面失败: {e}. 请检查输入的线是否有效且封闭。")


_TETRAHEDRA = (
    (0, 5, 1, 6),
    (0, 1, 2, 6),
    (0, 2, 3, 6),
    (0, 3, 7, 6),
    (0, 7, 4, 6),
    (0, 4, 5, 6),
)
_TETRA_EDGES = ((0, 1), (1, 2), (2, 0), (0, 3), (1, 3), (2, 3))
_TETRA_TRI_TABLE = (
    (),
    (0, 3, 2),
    (0, 1, 4),
    (1, 4, 2, 2, 4, 3),
    (1, 2, 5),
    (0, 3, 5, 0, 5, 1),
    (0, 2, 5, 0, 5, 4),
    (5, 4, 3),
    (3, 4, 5),
    (4, 5, 0, 5, 2, 0),
    (1, 5, 0, 5, 3, 0),
    (5, 2, 1),
    (3, 4, 2, 2, 4, 1),
    (4, 1, 0),
    (2, 3, 0),
    (),
)
_CUBE_OFFSETS = np.array(
    [
        [0, 0, 0],
        [1, 0, 0],
        [1, 1, 0],
        [0, 1, 0],
        [0, 0, 1],
        [1, 0, 1],
        [1, 1, 1],
        [0, 1, 1],
    ],
    dtype=float,
)


def _evaluate_field_values(
    field, xs: np.ndarray, ys: np.ndarray, zs: np.ndarray
) -> np.ndarray:
    if isinstance(field, ScalarField):
        return eval_rarray(field, xs, ys, zs)

    if callable(field):
        try:
            values = field(xs, ys, zs)
            values = np.asarray(values, dtype=float)
            if values.shape != xs.shape:
                raise ValueError("field 输出形状不匹配")
            return values
        except Exception:
            vectorized = np.vectorize(field)
            return vectorized(xs, ys, zs).astype(float)

    raise ValueError("field 必须是 ScalarField 或可调用对象")


def _marching_tetrahedra(
    xs: np.ndarray,
    ys: np.ndarray,
    zs: np.ndarray,
    values: np.ndarray,
    iso: float,
) -> List[List[Tuple[float, float, float]]]:
    triangles: List[List[Tuple[float, float, float]]] = []
    nx, ny, nz = values.shape
    for i in range(nx - 1):
        for j in range(ny - 1):
            for k in range(nz - 1):
                cube_vals = np.array(
                    [
                        values[i + int(o[0]), j + int(o[1]), k + int(o[2])]
                        for o in _CUBE_OFFSETS
                    ],
                    dtype=float,
                )
                cube_pos = np.array(
                    [
                        (xs[i + int(o[0])], ys[j + int(o[1])], zs[k + int(o[2])])
                        for o in _CUBE_OFFSETS
                    ],
                    dtype=float,
                )
                grad = np.array(
                    [
                        cube_vals[1] - cube_vals[0],
                        cube_vals[3] - cube_vals[0],
                        cube_vals[4] - cube_vals[0],
                    ],
                    dtype=float,
                )
                eps = 1e-9 * max(1.0, float(np.max(np.abs(cube_vals))))
                for tetra in _TETRAHEDRA:
                    idx = list(tetra)
                    tpos = cube_pos[idx]
                    tval = cube_vals[idx] - iso
                    tval = np.where(np.abs(tval) < eps, -eps, tval)
                    case_index = 0
                    for v_index, v_val in enumerate(tval):
                        if v_val < 0:
                            case_index |= 1 << v_index

                    table = _TETRA_TRI_TABLE[case_index]
                    if not table:
                        continue

                    edge_points: dict[int, np.ndarray] = {}
                    for edge_index in set(table):
                        a, b = _TETRA_EDGES[edge_index]
                        v0 = tval[a]
                        v1 = tval[b]
                        t = v0 / (v0 - v1)
                        edge_points[edge_index] = tpos[a] + t * (tpos[b] - tpos[a])

                    for tri_idx in range(0, len(table), 3):
                        p0 = edge_points[table[tri_idx]]
                        p1 = edge_points[table[tri_idx + 1]]
                        p2 = edge_points[table[tri_idx + 2]]
                        tri = [p0, p1, p2]
                        if np.linalg.norm(grad) > 1e-9:
                            normal = np.cross(p1 - p0, p2 - p0)
                            if float(np.dot(normal, grad)) < 0:
                                tri = [p0, p2, p1]
                        triangles.append([tuple(p.tolist()) for p in tri])
    return triangles


def make_field_surface_rsolid(
    field,
    bounds: Optional[
        Tuple[Tuple[float, float, float], Tuple[float, float, float]]
    ] = None,
    resolution: Tuple[int, int, int] = (24, 24, 24),
    iso: float = 0.0,
    cap_bounds: bool = True,
) -> Solid:
    """通过场函数等势面构建闭合曲面实体。

    Args:
        field: 标量场对象（ScalarField）或可调用函数。
        bounds: 采样边界 (min_xyz, max_xyz)，可为 None（自动推导）。
        resolution: 采样分辨率 (nx, ny, nz)。
        iso: 等势面值。
        cap_bounds: 是否对边界裁切处进行封闭封口。

    Returns:
        Solid: 等势面闭合实体。

    Raises:
        ValueError: 当采样失败或无法构建实体时抛出异常。

    Usage:
        使用场函数定义隐式曲面，并抽取等势面生成闭合实体。

    Example:
         field = Field.make_sphere_rscalarfield((0, 0, 0), 1.0)
         solid = make_field_surface_rsolid(field, ((-1.2, -1.2, -1.2), (1.2, 1.2, 1.2)))
    """
    try:
        if bounds is None:
            if isinstance(field, ScalarField):
                bounds = bounds_rbbox(field)
            else:
                raise ValueError("bounds 不能为空")

        (xmin, ymin, zmin), (xmax, ymax, zmax) = bounds
        if cap_bounds:
            center = ((xmin + xmax) / 2.0, (ymin + ymax) / 2.0, (zmin + zmax) / 2.0)
            size = (xmax - xmin, ymax - ymin, zmax - zmin)
            if isinstance(field, ScalarField):
                box_field = make_box_rscalarfield(center, size)
                field = intersect_rscalarfield(field, box_field)
            else:
                field_fn = field
                cx, cy, cz = center
                sx, sy, sz = size

                def box_eval(x, y, z):
                    dx = np.abs(x - cx) - sx / 2.0
                    dy = np.abs(y - cy) - sy / 2.0
                    dz = np.abs(z - cz) - sz / 2.0
                    return np.maximum.reduce([dx, dy, dz])

                def capped(x, y, z):
                    return np.maximum(field_fn(x, y, z), box_eval(x, y, z))

                field = capped
        nx, ny, nz = resolution
        if nx < 2 or ny < 2 or nz < 2:
            raise ValueError("resolution 每个维度必须 >= 2")

        xs = np.linspace(xmin, xmax, nx)
        ys = np.linspace(ymin, ymax, ny)
        zs = np.linspace(zmin, zmax, nz)
        grid_x, grid_y, grid_z = np.meshgrid(xs, ys, zs, indexing="ij")
        values = _evaluate_field_values(field, grid_x, grid_y, grid_z)
        triangles = _marching_tetrahedra(xs, ys, zs, values, iso)
        if not triangles:
            raise ValueError("未找到等势面，请调整 bounds 或 iso")

        faces = []
        edge_count: dict[
            Tuple[Tuple[float, float, float], Tuple[float, float, float]], int
        ] = {}
        for tri in triangles:
            if len({tri[0], tri[1], tri[2]}) < 3:
                continue
            try:
                wire = cq.Wire.makePolygon(tri, close=True)
                faces.append(cq.Face.makeFromWires(wire))
            except Exception:
                continue
            pts = [tuple(np.round(p, 8)) for p in tri]
            edges = [(pts[0], pts[1]), (pts[1], pts[2]), (pts[2], pts[0])]
            for a, b in edges:
                key = (a, b) if a <= b else (b, a)
                edge_count[key] = edge_count.get(key, 0) + 1
        sewing = BRepBuilderAPI_Sewing(1e-6)
        for face in faces:
            sewing.Add(face.wrapped)
        sewing.Perform()
        sewed = sewing.SewedShape()
        shells = []
        if sewed.ShapeType() == TopAbs_SHELL:
            shells.append(sewed)
        else:
            explorer = TopExp_Explorer(sewed, TopAbs_SHELL)
            while explorer.More():
                shells.append(explorer.Current())
                explorer.Next()

        if not shells:
            raise ValueError("未能从等势面构建闭合壳体")

        def _shell_metric(shell_obj):
            cq_shell = cq.Shell(shell_obj)
            bb = cq_shell.BoundingBox()
            volume = (bb.xmax - bb.xmin) * (bb.ymax - bb.ymin) * (bb.zmax - bb.zmin)
            face_count = len(cq_shell.Faces())
            return (face_count, volume)

        shell = max(shells, key=_shell_metric)

        solid = Solid(cq.Solid.makeSolid(cq.Shell(shell)))

        shell_closed_value = bool(cq.Shell(shell).Closed())

        mesh_closed = all(count == 2 for count in edge_count.values())
        report = {
            "bounds": {"min": (xmin, ymin, zmin), "max": (xmax, ymax, zmax)},
            "resolution": resolution,
            "iso": iso,
            "field_min": float(np.min(values)),
            "field_max": float(np.max(values)),
            "triangles": len(triangles),
            "shells": len(shells),
            "mesh_closed": mesh_closed,
            "shell_closed": shell_closed_value,
            "cap_bounds": bool(cap_bounds),
        }
        solid.set_metadata("field_report", report)
        return solid
    except Exception as e:
        raise ValueError(f"场函数等势面构建失败: {e}.")


def make_wire_from_edges_rwire(edges: List[Edge]) -> Wire:
    """从边对象列表创建线对象

    Args:
        edges (List[Edge]): 输入的边对象列表，边应该能够连接成连续的线

    Returns:
        Wire: 创建的线对象，由输入的边组成的连续线

    Raises:
        ValueError: 当边列表为空或边无法连接时抛出异常

    Usage:
        将多个边对象连接成一个连续的线对象。边的顺序很重要，相邻的边应该
        能够连接在一起。用于构建复杂的线框结构。

    Example:
         # 创建L形线
         edge1 = make_line_redge((0, 0, 0), (2, 0, 0))  # 水平线
         edge2 = make_line_redge((2, 0, 0), (2, 2, 0))  # 垂直线
         l_wire = make_wire_from_edges_rwire([edge1, edge2])

         # 创建包含直线和圆弧的复杂线
         line = make_line_redge((0, 0, 0), (2, 0, 0))
         arc = make_three_point_arc_redge((2, 0, 0), (3, 1, 0), (2, 2, 0))
         complex_wire = make_wire_from_edges_rwire([line, arc])
    """
    try:
        if not edges:
            raise ValueError("边列表不能为空")

        cq_wire = cq.Wire.assembleEdges([edge.cq_edge for edge in edges])
        return Wire(cq_wire)
    except Exception as e:
        raise ValueError(f"创建线失败: {e}. 请检查输入的边是否有效。")


def make_box_rsolid(
    width: float,
    height: float,
    depth: float,
    bottom_face_center: Tuple[float, float, float] = (0, 0, 0),
) -> Solid:
    """创建立方体并返回实体对象

    Args:
        width (float): 立方体的宽度（X方向尺寸），必须为正数
        height (float): 立方体的高度（Y方向尺寸），必须为正数
        depth (float): 立方体的深度（Z方向尺寸），必须为正数
        bottom_face_center (Tuple[float, float, float], optional): 立方体的底面中心坐标 (x, y, z)，
            默认为 (0, 0, 0)，注意这里的中心是立方体底面的中心点

    Returns:
        Solid: 创建的实体对象，表示一个立方体

    Raises:
        ValueError: 当宽度、高度或深度小于等于0时抛出异常

    Usage:
        创建矩形立方体实体，是最基础的三维几何体之一。自动为立方体的面添加
        标签（top、bottom、front、back、left、right），便于后续的面选择操作。
        体积等于width×height×depth。

    Example:
         # 创建标准单位立方体
         unit_cube = make_box_rsolid(1.0, 1.0, 1.0)
         volume = unit_cube.get_volume()  # 体积为1

         # 创建矩形立方体
         rect_box = make_box_rsolid(4.0, 2.0, 3.0)

         # 创建偏移的立方体
         offset_box = make_box_rsolid(2.0, 2.0, 2.0, (1, 1, 1))

         # 获取立方体的面进行后续操作
         faces = unit_cube.get_faces()
         top_faces = [f for f in faces if f.has_tag("top")]
    """
    try:
        if width <= 0 or height <= 0 or depth <= 0:
            raise ValueError("宽度、高度和深度必须大于0")

        cs = get_current_cs()
        center_global = cs.transform_point(np.array(bottom_face_center))
        pnt = center_global - np.array([width / 2, height / 2, 0])

        # 创建立方体
        cq_solid = cq.Solid.makeBox(width, height, depth, Vector(*pnt))
        solid = Solid(cq_solid)

        # 自动标记面
        solid.auto_tag_faces("box")
        solid.apply_tag("geom.primitive.box", propagate=False)
        solid.add_tag("box")
        solid.add_tag(f"bottom center: {bottom_face_center}")
        solid.add_tag(f"size: {width}x{height}x{depth}")
        solid.set_metadata(
            "geo",
            {
                "type": "box",
                "size": {"x": width, "y": height, "z": depth},
                "bottom_face_center": bottom_face_center,
            },
        )

        return solid
    except Exception as e:
        raise ValueError(f"创建立方体失败: {e}. 请检查尺寸和中心点坐标是否有效。")


def make_cylinder_rsolid(
    radius: float,
    height: float,
    bottom_face_center: Tuple[float, float, float] = (0, 0, 0),
    axis: Tuple[float, float, float] = (0, 0, 1),
) -> Solid:
    """创建圆柱体并返回实体对象

    Args:
        radius (float): 圆柱体的半径，必须为正数
        height (float): 圆柱体的高度，必须为正数
        bottom_face_center (Tuple[float, float, float], optional): 圆柱体底面中心坐标 (x, y, z)，
            默认为 (0, 0, 0)
        axis (Tuple[float, float, float], optional): 圆柱体的轴向向量 (x, y, z)，
            定义圆柱体的方向，默认为 (0, 0, 1) 表示沿Z轴方向

    Returns:
        Solid: 创建的实体对象，表示一个圆柱体

    Raises:
        ValueError: 当半径或高度小于等于0时抛出异常

    Usage:
        创建圆柱体实体，是基础的三维几何体之一。自动为圆柱体的面添加标签
        （top、bottom、cylindrical），便于后续的面选择操作。体积等于πr²h。

    Example:
         # 创建标准圆柱体
         cylinder = make_cylinder_rsolid(2.0, 5.0)
         volume = cylinder.get_volume()  # 体积为π×2²×5≈62.83

         # 创建水平圆柱体
         horizontal_cyl = make_cylinder_rsolid(radius=1.0, height=4.0, bottom_face_center=(0, 0, 0), axis=(1, 0, 0))

         # 创建偏移的圆柱体,底面中心在(2, 2, 0)
         offset_cyl = make_cylinder_rsolid(1.5, 3.0, (2, 2, 0))

         # 获取圆柱体的面进行后续操作
         faces = cylinder.get_faces()
         top_faces = [f for f in faces if f.has_tag("top")]
    """
    try:
        if radius <= 0 or height <= 0:
            raise ValueError("半径和高度必须大于0")

        cs = get_current_cs()
        center_global = cs.transform_point(np.array(bottom_face_center))
        axis_global = cs.transform_vector(np.array(axis))

        center_vec = Vector(*center_global)
        axis_vec = Vector(*axis_global)

        cq_solid = cq.Solid.makeCylinder(radius, height, center_vec, axis_vec)
        solid = Solid(cq_solid)

        # 自动标记面
        solid.auto_tag_faces("cylinder")
        solid.apply_tag("geom.primitive.cylinder", propagate=False)
        solid.add_tag("cylinder")
        solid.add_tag(f"bottom center: {bottom_face_center}")
        solid.add_tag(f"size: {radius}x{height}")
        solid.set_metadata(
            "geo",
            {
                "type": "cylinder",
                "radius": radius,
                "height": height,
                "bottom_face_center": bottom_face_center,
                "axis": axis,
            },
        )

        return solid
    except Exception as e:
        raise ValueError(
            f"创建圆柱体失败: {e}. 请检查半径、高度、中心点和轴向是否有效。"
        )


def make_cone_rsolid(
    bottom_radius: float,
    height: float,
    top_radius: float = 0.0,
    bottom_face_center: Tuple[float, float, float] = (0, 0, 0),
    axis: Tuple[float, float, float] = (0, 0, 1),
) -> Solid:
    """创建圆锥体并返回实体对象

    Args:
        bottom_radius (float): 圆锥体的底面半径，必须为正数
        height (float): 圆锥体的高度，必须为正数
        top_radius (float, optional): 圆锥体的顶面半径，默认为0.0（尖锥）
        bottom_face_center (Tuple[float, float, float], optional): 圆锥体底面中心坐标 (x, y, z)，
            默认为 (0, 0, 0)
        axis (Tuple[float, float, float], optional): 圆锥体的轴向向量 (x, y, z)，
            定义圆锥体的方向，默认为 (0, 0, 1) 表示沿Z轴方向

    Returns:
        Solid: 创建的实体对象，表示一个圆锥体

    Raises:
        ValueError: 当半径或高度小于等于0时抛出异常

    Usage:
        创建圆锥体实体，是基础的三维几何体之一。自动为圆锥体的面添加标签
        （top、bottom、conical），便于后续的面选择操作。

    Example:
         # 创建标准圆锥体（尖锥）
         cone = make_cone_rsolid(2.0, 5.0)
         volume = cone.get_volume()  # 体积为(1/3)π×2²×5≈20.94

         # 创建截锥体
         truncated_cone = make_cone_rsolid(3.0, 4.0, 1.0)
    """
    try:
        if bottom_radius <= 0 or height <= 0:
            raise ValueError("底面半径和高度必须大于0")

        cs = get_current_cs()
        center_global = cs.transform_point(np.array(bottom_face_center))
        axis_global = cs.transform_vector(np.array(axis))

        center_vec = Vector(*center_global)
        axis_vec = Vector(*axis_global)

        # 使用正确的makeCone参数：bottom_radius, top_radius, height, center, direction
        cq_solid = cq.Solid.makeCone(
            bottom_radius, top_radius, height, center_vec, axis_vec
        )
        solid = Solid(cq_solid)

        # 自动标记面
        solid.apply_tag("geom.primitive.cone", propagate=False)
        solid.add_tag("cone")
        solid.add_tag(f"bottom center: {bottom_face_center}")
        solid.add_tag(
            f"size: bottom_radius: {bottom_radius}, top_radius: {top_radius}, height: {height}"
        )
        solid.set_metadata(
            "geo",
            {
                "type": "cone",
                "bottom_radius": bottom_radius,
                "top_radius": top_radius,
                "height": height,
                "bottom_face_center": bottom_face_center,
                "axis": axis,
            },
        )

        return solid
    except Exception as e:
        raise ValueError(
            f"创建圆锥体失败: {e}. 请检查半径、高度、中心点和轴向是否有效。"
        )


def make_sphere_rsolid(
    radius: float, center: Tuple[float, float, float] = (0, 0, 0)
) -> Solid:
    """创建球体并返回实体对象

    Args:
        radius (float): 球体的半径，必须为正数
        center (Tuple[float, float, float], optional): 球体的中心坐标 (x, y, z)，
            默认为 (0, 0, 0)

    Returns:
        Solid: 创建的实体对象，表示一个球体

    Raises:
        ValueError: 当半径小于等于0时抛出异常

    Usage:
        创建球体实体，是基础的三维几何体之一。自动为球体的面添加标签（surface），
        便于后续的面选择操作。体积等于(4/3)πr³。

    Example:
         # 创建标准单位球体
         unit_sphere = make_sphere_rsolid(1.0)
         volume = unit_sphere.get_volume()  # 体积为(4/3)π≈4.19

         # 创建大球体
         large_sphere = make_sphere_rsolid(3.0)

         # 创建偏移的球体
         offset_sphere = make_sphere_rsolid(2.0, (1, 1, 1))

         # 获取球体的面进行后续操作
         faces = unit_sphere.get_faces()
         surface_faces = [f for f in faces if f.has_tag("surface")]
    """
    try:
        if radius <= 0:
            raise ValueError("半径必须大于0")

        cs = get_current_cs()
        center_global = cs.transform_point(np.array(center))

        # 使用Workplane.sphere方法创建球体，然后移动到正确位置
        if center_global[0] != 0 or center_global[1] != 0 or center_global[2] != 0:
            cq_solid = (
                cq.Workplane("XY")
                .center(center_global[0], center_global[1])
                .workplane(offset=center_global[2])
                .sphere(radius)
                .val()
            )
        else:
            cq_solid = cq.Workplane("XY").sphere(radius).val()

        solid = Solid(cq_solid)

        # 自动标记面
        solid.auto_tag_faces("sphere")
        solid.apply_tag("geom.primitive.sphere", propagate=False)
        solid.add_tag("sphere")
        solid.add_tag(f"center: {center}")
        solid.add_tag(f"radius: {radius}")
        solid.set_metadata(
            "geo",
            {
                "type": "sphere",
                "radius": radius,
                "center": center,
            },
        )

        return solid
    except Exception as e:
        raise ValueError(f"创建球体失败: {e}. 请检查半径和中心点坐标是否有效。")


def make_three_point_arc_redge(
    start: Tuple[float, float, float],
    middle: Tuple[float, float, float],
    end: Tuple[float, float, float],
) -> Edge:
    """通过三点创建圆弧并返回边对象

    Args:
        start (Tuple[float, float, float]): 圆弧的起始点坐标 (x, y, z)
        middle (Tuple[float, float, float]): 圆弧上的中间点坐标 (x, y, z)，
            用于确定圆弧的曲率和方向
        end (Tuple[float, float, float]): 圆弧的结束点坐标 (x, y, z)

    Returns:
        Edge: 创建的边对象，表示通过三点的圆弧

    Raises:
        ValueError: 当三个点共线或坐标无效时抛出异常

    Usage:
        通过三个点创建圆弧边，三个点不能共线。圆弧从起始点经过中间点到结束点。
        中间点的位置决定了圆弧的弯曲程度和方向。

    Example:
         # 创建90度圆弧
         arc = make_three_point_arc_redge((0, 0, 0), (1, 1, 0), (2, 0, 0))

         # 创建大圆弧
         large_arc = make_three_point_arc_redge((0, 0, 0), (0, 3, 0), (0, 6, 0))

         # 创建3D圆弧
         arc_3d = make_three_point_arc_redge((0, 0, 0), (1, 1, 1), (2, 0, 2))
    """
    try:
        cs = get_current_cs()
        start_global = cs.transform_point(np.array(start))
        middle_global = cs.transform_point(np.array(middle))
        end_global = cs.transform_point(np.array(end))

        start_vec = Vector(*start_global)
        middle_vec = Vector(*middle_global)
        end_vec = Vector(*end_global)

        cq_edge = cq.Edge.makeThreePointArc(start_vec, middle_vec, end_vec)
        return Edge(cq_edge)
    except Exception as e:
        raise ValueError(f"创建三点圆弧失败: {e}. 请检查三个点的坐标是否有效且不共线。")


def make_three_point_arc_rwire(
    start: Tuple[float, float, float],
    middle: Tuple[float, float, float],
    end: Tuple[float, float, float],
) -> Wire:
    """通过三点创建圆弧并返回线对象

    Args:
        start (Tuple[float, float, float]): 圆弧的起始点坐标 (x, y, z)
        middle (Tuple[float, float, float]): 圆弧上的中间点坐标 (x, y, z)，
            用于确定圆弧的曲率和方向
        end (Tuple[float, float, float]): 圆弧的结束点坐标 (x, y, z)

    Returns:
        Wire: 创建的线对象，包含一个通过三点的圆弧

    Raises:
        ValueError: 当三个点共线或坐标无效时抛出异常

    Usage:
        通过三个点创建圆弧线对象，与make_three_point_arc_redge功能相同，
        但返回的是线对象，可以与其他线对象连接或用于构建复杂轮廓。

    Example:
         # 创建圆弧线
         arc_wire = make_three_point_arc_rwire((0, 0, 0), (1, 1, 0), (0, 2, 0))

         # 与直线连接创建复杂轮廓
         line = make_segment_rwire((0, 2, 0), (3, 2, 0))
         # 然后可以连接arc_wire和line
    """
    try:
        edge = make_three_point_arc_redge(start, middle, end)
        cq_wire = cq.Wire.assembleEdges([edge.cq_edge])
        return Wire(cq_wire)
    except Exception as e:
        raise ValueError(f"创建三点圆弧线失败: {e}")


def make_angle_arc_redge(
    center: Tuple[float, float, float],
    radius: float,
    start_angle: float,
    end_angle: float,
    normal: Tuple[float, float, float] = (0, 0, 1),
) -> Edge:
    """通过角度创建圆弧并返回边对象

    Args:
        center (Tuple[float, float, float]): 圆弧的中心点坐标 (x, y, z)
        radius (float): 圆弧的半径，必须为正数
        start_angle (float): 起始角度，单位为度数（0-360）
        end_angle (float): 结束角度，单位为度数（0-360）
        normal (Tuple[float, float, float], optional): 圆弧所在平面的法向量 (x, y, z)，
            默认为 (0, 0, 1) 表示XY平面

    Returns:
        Edge: 创建的边对象，表示指定角度范围的圆弧

    Raises:
        ValueError: 当半径小于等于0或其他参数无效时抛出异常

    Usage:
        通过指定中心点、半径和角度范围创建圆弧边。角度采用度数制，
        0度对应X轴正方向，逆时针为正角度。可以创建任意角度范围的圆弧。

    Example:
         # 创建90度圆弧（从0度到90度）
         arc_90 = make_angle_arc_redge((0, 0, 0), 2.0, 0, 90)

         # 创建180度半圆弧
         semicircle = make_angle_arc_redge((0, 0, 0), 1.5, 0, 180)

         # 创建270度圆弧
         arc_270 = make_angle_arc_redge((0, 0, 0), 1.0, 45, 315)

         # 创建垂直平面上的圆弧
         vertical_arc = make_angle_arc_redge((0, 0, 0), 1.0, 0, 90, (1, 0, 0))
    """
    try:
        if radius <= 0:
            raise ValueError("半径必须大于0")
        if start_angle == end_angle:
            raise ValueError("起始角度和结束角度不能相同")

        cs = get_current_cs()
        center_global = cs.transform_point(np.array(center))
        normal_global = cs.transform_point(np.array(normal)) - cs.origin

        # 标准化法向量
        normal_vec = normal_global / np.linalg.norm(normal_global)

        # 创建本地坐标系
        # 如果法向量接近Z轴，使用X轴作为参考
        if abs(normal_vec[2]) > 0.9:
            ref_vec = np.array([1.0, 0.0, 0.0])
        else:
            ref_vec = np.array([0.0, 0.0, 1.0])

        # 计算本地坐标系的X和Y轴
        local_x = np.cross(normal_vec, ref_vec)
        local_x = local_x / np.linalg.norm(local_x)
        local_y = np.cross(normal_vec, local_x)
        local_y = local_y / np.linalg.norm(local_y)

        # 在本地坐标系中计算起始、结束和中间点
        start_local = np.array(
            [radius * np.cos(start_angle), radius * np.sin(start_angle), 0]
        )
        end_local = np.array(
            [radius * np.cos(end_angle), radius * np.sin(end_angle), 0]
        )
        mid_angle = (start_angle + end_angle) / 2
        mid_local = np.array(
            [radius * np.cos(mid_angle), radius * np.sin(mid_angle), 0]
        )

        # 转换到全局坐标系
        start_global = (
            center_global + start_local[0] * local_x + start_local[1] * local_y
        )
        end_global = center_global + end_local[0] * local_x + end_local[1] * local_y
        mid_global = center_global + mid_local[0] * local_x + mid_local[1] * local_y

        start_vec = Vector(*start_global)
        end_vec = Vector(*end_global)
        mid_vec = Vector(*mid_global)

        # 使用三点圆弧方法
        cq_edge = cq.Edge.makeThreePointArc(start_vec, mid_vec, end_vec)
        return Edge(cq_edge)
    except Exception as e:
        raise ValueError(f"创建角度圆弧失败: {e}. 请检查参数是否有效。")


def make_angle_arc_rwire(
    center: Tuple[float, float, float],
    radius: float,
    start_angle: float,
    end_angle: float,
    normal: Tuple[float, float, float] = (0, 0, 1),
) -> Wire:
    """通过角度创建圆弧并返回线对象

    Args:
        center: 圆心坐标
        radius: 半径
        start_angle: 起始角度（弧度）
        end_angle: 结束角度（弧度）
        normal: 法向量

    Returns:
        Wire: 线对象，表示通过角度创建的圆弧线

    Raises:
        ValueError: 当半径小于等于0或其他参数无效时

    Usage:
        通过指定中心点、半径和角度范围创建圆弧线。
        角度采用度数制，0度对应X轴正方向，逆时针为正角度。
        可以创建任意角度范围的圆弧线。

    Example:
         # 创建90度圆弧线（从0度到90度）
         arc_90_wire = make_angle_arc_rwire((0, 0, 0), 2.0, 0, 90)

         # 创建180度半圆弧线
         semicircle_wire = make_angle_arc_rwire((0, 0, 0), 1.5, 0, 180)
         # 创建270度圆弧线
         arc_270_wire = make_angle_arc_rwire((0, 0, 0), 1.0, 45, 315)

         # 创建垂直平面（YZ，法相指向X轴正方向）上的圆弧线
         vertical_arc_wire = make_angle_arc_rwire((0, 0, 0), 1.0, 0, 90, (1, 0, 0))
    """

    try:
        edge = make_angle_arc_redge(center, radius, start_angle, end_angle, normal)
        cq_wire = cq.Wire.assembleEdges([edge.cq_edge])
        return Wire(cq_wire)
    except Exception as e:
        raise ValueError(f"创建角度圆弧线失败: {e}")


def make_spline_redge(
    points: List[Tuple[float, float, float]],
    tangents: Optional[List[Tuple[float, float, float]]] = None,
) -> Edge:
    """创建样条曲线并返回边对象

    Args:
        points (List[Tuple[float, float, float]]): 控制点坐标列表 [(x, y, z), ...]，
            至少需要2个点，点的顺序决定样条曲线的走向
        tangents (Optional[List[Tuple[float, float, float]]], optional):
            可选的切线向量列表 [(x, y, z), ...]，如果提供则数量必须与控制点一致

    Returns:
        Edge: 创建的边对象，表示通过控制点的平滑样条曲线

    Raises:
        ValueError: 当控制点少于2个或切线向量数量不匹配时抛出异常

    Usage:
        创建平滑的样条曲线边，用于构建复杂的曲线路径。样条曲线会平滑地通过
        所有控制点，可选择性地指定每个点的切线方向来控制曲线的形状。

    Example:
         # 创建简单的样条曲线
         points = [(0, 0, 0), (1, 2, 0), (3, 1, 0), (4, 3, 0)]
         spline = make_spline_redge(points)

         # 创建带切线控制的样条曲线
         points = [(0, 0, 0), (2, 0, 0), (4, 0, 0)]
         tangents = [(1, 0, 0), (0, 1, 0), (1, 0, 0)]
         controlled_spline = make_spline_redge(points, tangents)

         # 创建3D样条曲线
         points_3d = [(0, 0, 0), (1, 1, 1), (2, 0, 2), (3, 1, 1)]
         spline_3d = make_spline_redge(points_3d)
    """
    try:
        if len(points) < 2:
            raise ValueError("至少需要2个控制点")

        cs = get_current_cs()

        # 转换控制点到全局坐标系
        global_points = []
        for point in points:
            global_point = cs.transform_point(np.array(point))
            global_points.append(Vector(*global_point))

        # 转换切线向量（如果提供）
        global_tangents = None
        if tangents:
            if len(tangents) != len(points):
                raise ValueError("切线向量数量必须与控制点数量一致")
            global_tangents = []
            for tangent in tangents:
                global_tangent = cs.transform_point(np.array(tangent)) - cs.origin
                global_tangents.append(Vector(*global_tangent))

        if global_tangents:
            # CADQuery的makeSpline不支持tangents参数，使用makeSplineApprox
            cq_edge = cq.Edge.makeSplineApprox(global_points)
        else:
            cq_edge = cq.Edge.makeSpline(global_points)

        return Edge(cq_edge)
    except Exception as e:
        raise ValueError(f"创建样条曲线失败: {e}. 请检查控制点和切线向量是否有效。")


def make_spline_rwire(
    points: List[Tuple[float, float, float]],
    tangents: Optional[List[Tuple[float, float, float]]] = None,
    closed: bool = False,
) -> Wire:
    """创建样条曲线并返回线对象

    Args:
        points (List[Tuple[float, float, float]]): 控制点坐标列表 [(x, y, z), ...]，
            至少需要2个点，点的顺序决定样条曲线的走向
        tangents (Optional[List[Tuple[float, float, float]]], optional):
            可选的切线向量列表 [(x, y, z), ...]，如果提供则数量必须与控制点一致
        closed (bool, optional): 是否创建闭合的样条曲线，默认为False

    Returns:
        Wire: 创建的线对象，包含一个样条曲线

    Raises:
        ValueError: 当控制点少于2个或切线向量数量不匹配时抛出异常

    Usage:
        创建样条曲线线对象，与make_spline_redge功能相同但返回线对象。
        可以设置为闭合样条曲线，适用于构建复杂的封闭轮廓。

    Example:
         # 创建开放样条曲线线
         points = [(0, 0, 0), (2, 3, 0), (4, 1, 0), (6, 2, 0)]
         spline_wire = make_spline_rwire(points)

         # 创建闭合样条曲线
         points = [(0, 0, 0), (2, 2, 0), (4, 0, 0), (2, -2, 0)]
         closed_spline = make_spline_rwire(points, closed=True)
    """
    try:
        edge = make_spline_redge(points, tangents)
        cq_wire = cq.Wire.assembleEdges([edge.cq_edge])
        if closed:
            cq_wire = cq_wire.close()  # 确保线是闭合的
        rv = Wire(cq_wire)
        return rv
    except Exception as e:
        raise ValueError(f"创建样条曲线线失败: {e}")


def make_polyline_rwire(
    points: List[Tuple[float, float, float]], closed: bool = False
) -> Wire:
    """创建多段线并返回线对象

    Args:
        points (List[Tuple[float, float, float]]): 顶点坐标列表 [(x, y, z), ...]，
            至少需要2个点，相邻点之间用直线连接
        closed (bool, optional): 是否创建闭合的多段线，默认为False。
            如果为True，会自动连接最后一个点和第一个点

    Returns:
        Wire: 创建的线对象，由多个直线段组成的多段线

    Raises:
        ValueError: 当顶点少于2个时抛出异常

    Usage:
        创建由多个直线段连接的多段线，用于构建折线、多边形轮廓等。
        相邻点之间用直线连接，可以创建开放或闭合的多段线。

    Example:
         # 创建L形多段线
         points = [(0, 0, 0), (3, 0, 0), (3, 2, 0)]
         l_shape = make_polyline_rwire(points)

         # 创建三角形轮廓
         triangle_points = [(0, 0, 0), (2, 0, 0), (1, 2, 0)]
         triangle = make_polyline_rwire(triangle_points, closed=True)

         # 创建复杂的多边形
         polygon_points = [(0, 0, 0), (2, 0, 0), (3, 1, 0), (2, 2, 0), (0, 2, 0)]
         polygon = make_polyline_rwire(polygon_points, closed=True)
    """
    try:
        if len(points) < 2:
            raise ValueError("至少需要2个点")

        cs = get_current_cs()

        # 转换所有点到全局坐标系
        global_points = []
        for point in points:
            global_point = cs.transform_point(np.array(point))
            global_points.append(Vector(*global_point))

        # 创建边列表
        edges = []
        num_points = len(global_points)

        # 创建连接相邻点的边
        for i in range(num_points - 1):
            start_vec = global_points[i]
            end_vec = global_points[i + 1]
            edge = cq.Edge.makeLine(start_vec, end_vec)
            edges.append(edge)

        # 如果闭合，添加最后一条边
        if closed and num_points > 2:
            start_vec = global_points[-1]
            end_vec = global_points[0]
            edge = cq.Edge.makeLine(start_vec, end_vec)
            edges.append(edge)

        cq_wire = cq.Wire.assembleEdges(edges)
        return Wire(cq_wire.close() if closed else cq_wire)
    except Exception as e:
        raise ValueError(f"创建多段线失败: {e}. 请检查点坐标是否有效。")


def make_helix_redge(
    pitch: float,
    height: float,
    radius: float,
    center: Tuple[float, float, float] = (0, 0, 0),
    dir: Tuple[float, float, float] = (0, 0, 1),
) -> Edge:
    """创建螺旋线并返回边对象

    Args:
        pitch (float): 螺距，每转一圈在轴向上的距离，必须为正数
        height (float): 螺旋线的总高度，必须为正数
        radius (float): 螺旋线的半径，必须为正数
        center (Tuple[float, float, float], optional): 螺旋线的中心点坐标 (x, y, z)，
            默认为 (0, 0, 0)
        dir (Tuple[float, float, float], optional): 螺旋轴的方向向量 (x, y, z)，
            默认为 (0, 0, 1) 表示沿Z轴方向

    Returns:
        Edge: 创建的边对象，表示一个螺旋线

    Raises:
        ValueError: 当螺距、高度或半径小于等于0时抛出异常

    Usage:
        创建螺旋线边对象，用于构建螺旋形状的路径或进行螺旋扫掠。
        螺旋线绕指定轴旋转，同时沿轴向移动，形成螺旋形状。

    Example:
         # 创建标准螺旋线
         helix = make_helix_redge(2.0, 10.0, 1.0)  # 螺距2，高度10，半径1

         # 创建紧密螺旋线
         tight_helix = make_helix_redge(0.5, 5.0, 0.5)

         # 创建水平螺旋线
         horizontal_helix = make_helix_redge(1.0, 8.0, 2.0, (0, 0, 0), (1, 0, 0))
    """
    try:
        if pitch <= 0:
            raise ValueError("螺距必须大于0")
        if height <= 0:
            raise ValueError("高度必须大于0")
        if radius <= 0:
            raise ValueError("半径必须大于0")

        cs = get_current_cs()
        global_center = cs.transform_point(np.array(center))
        global_dir = cs.transform_point(np.array(dir)) - cs.origin

        center_vec = Vector(*global_center)
        dir_vec = Vector(*global_dir)

        # 使用CADQuery的Wire.makeHelix方法创建螺旋线，然后提取边
        cq_wire = cq.Wire.makeHelix(pitch, height, radius, center_vec, dir_vec)
        # 螺旋线通常是连续的，所以我们取第一个边
        edges = cq_wire.Edges()
        if edges:
            return Edge(edges[0])
        else:
            raise ValueError("无法从螺旋线中提取边")
    except Exception as e:
        raise ValueError(f"创建螺旋线边失败: {e}. 请检查参数是否有效。")


def make_helix_rwire(
    pitch: float,
    height: float,
    radius: float,
    center: Tuple[float, float, float] = (0, 0, 0),
    dir: Tuple[float, float, float] = (0, 0, 1),
) -> Wire:
    """创建螺旋线并返回线对象

    Args:
        pitch (float): 螺距，每转一圈在轴向上的距离，必须为正数
        height (float): 螺旋线的总高度，必须为正数
        radius (float): 螺旋线的半径，必须为正数
        center (Tuple[float, float, float], optional): 螺旋线的中心点坐标 (x, y, z)，
            默认为 (0, 0, 0)
        dir (Tuple[float, float, float], optional): 螺旋轴的方向向量 (x, y, z)，
            默认为 (0, 0, 1) 表示沿Z轴方向

    Returns:
        Wire: 创建的线对象，包含一个螺旋线

    Raises:
        ValueError: 当螺距、高度或半径小于等于0时抛出异常

    Usage:
        创建螺旋线线对象，与make_helix_redge功能相同但返回线对象。
        可以用于后续的扫掠操作或作为复杂路径的一部分。

    Example:
         # 创建螺旋线线对象
         helix_wire = make_helix_rwire(1.5, 6.0, 1.0)

         # 用于扫掠操作的螺旋路径
         profile = make_circle_rface((0, 0, 0), 0.1)
         helix_path = make_helix_rwire(2.0, 10.0, 2.0)
         # 然后可以用 sweep_rsolid(profile, helix_path) 创建螺旋扫掠
    """
    try:
        cs = get_current_cs()
        global_center = cs.transform_point(np.array(center))
        global_dir = cs.transform_point(np.array(dir)) - cs.origin

        center_vec = Vector(*global_center)
        dir_vec = Vector(*global_dir)

        # 使用CADQuery的Wire.makeHelix方法
        cq_wire = cq.Wire.makeHelix(pitch, height, radius, center_vec, dir_vec)
        return Wire(cq_wire)
    except Exception as e:
        raise ValueError(f"创建螺旋线失败: {e}. 请检查参数是否有效。")


# =============================================================================
# 变换操作函数
# =============================================================================


def translate_shape(shape: AnyShape, vector: Tuple[float, float, float]) -> AnyShape:
    """平移几何体到新位置

    Args:
        shape (AnyShape): 要平移的几何体，可以是点、边、线、面、实体等任意几何对象
        vector (Tuple[float, float, float]): 平移向量 (dx, dy, dz)，
            定义在X、Y、Z方向上的平移距离

    Returns:
        AnyShape: 平移后的几何体，类型与输入相同

    Raises:
        ValueError: 当几何体或平移向量无效时抛出异常

    Usage:
        将几何体从当前位置平移到新位置，不改变几何体的形状和大小。
        平移操作支持当前坐标系变换，适用于所有类型的几何对象。

    Example:
         # 平移立方体
         box = make_box_rsolid(2, 2, 2)
         moved_box = translate_shape(box, (5, 0, 0))  # 沿X轴移动5个单位

         # 平移圆形面
         circle = make_circle_rface((0, 0, 0), 1.0)
         moved_circle = translate_shape(circle, (1, 1, 2))

         # 平移线段
         line = make_line_redge((0, 0, 0), (1, 0, 0))
         moved_line = translate_shape(line, (0, 3, 0))
    """
    try:
        cs = get_current_cs()
        global_vector = cs.transform_point(np.array(vector)) - cs.origin

        translation_vec = Vector(*global_vector)

        if isinstance(shape, Vertex):
            new_cq_shape = shape.cq_vertex.translate(translation_vec)
            new_shape = Vertex(new_cq_shape)
        elif isinstance(shape, Edge):
            new_cq_shape = shape.cq_edge.translate(translation_vec)
            new_shape = Edge(new_cq_shape)
        elif isinstance(shape, Wire):
            new_cq_shape = shape.cq_wire.translate(translation_vec)
            new_shape = Wire(new_cq_shape)
        elif isinstance(shape, Face):
            new_cq_shape = shape.cq_face.translate(translation_vec)
            new_shape = Face(new_cq_shape)
        elif isinstance(shape, Solid):
            new_cq_shape = shape.cq_solid.translate(translation_vec)
            new_shape = Solid(new_cq_shape)

        # 复制标签和元数据
        new_shape._tags = shape._tags.copy()
        new_shape._metadata = shape._metadata.copy()

        return new_shape
    except Exception as e:
        raise ValueError(f"平移几何体失败: {e}. 请检查几何体和平移向量是否有效。")


def rotate_shape(
    shape: AnyShape,
    angle: float,
    axis: Tuple[float, float, float] = (0, 0, 1),
    origin: Tuple[float, float, float] = (0, 0, 0),
) -> AnyShape:
    """旋转几何体到新方向

    Args:
        shape (AnyShape): 要旋转的几何体，可以是点、边、线、面、实体等任意几何对象
        angle (float): 旋转角度，单位为度数（0-360），正值表示逆时针旋转
        axis (Tuple[float, float, float], optional): 旋转轴向量 (x, y, z)，
            默认为 (0, 0, 1) 表示绕Z轴旋转
        origin (Tuple[float, float, float], optional): 旋转中心点坐标 (x, y, z)，
            默认为 (0, 0, 0)

    Returns:
        AnyShape: 旋转后的几何体，类型与输入相同

    Raises:
        ValueError: 当几何体或旋转参数无效时抛出异常

    Usage:
        围绕指定轴和中心点旋转几何体，不改变几何体的形状和大小。
        旋转操作支持当前坐标系变换，适用于所有类型的几何对象。
        角度使用度数制，正值表示右手定则的逆时针旋转。

    Example:
         # 绕Z轴旋转立方体45度
         box = make_box_rsolid(2, 2, 2)
         rotated_box = rotate_shape(box, 45)

         # 绕X轴旋转圆形面90度
         circle = make_circle_rface((0, 0, 0), 1.0)
         rotated_circle = rotate_shape(circle, 90, (1, 0, 0))

         # 围绕指定点旋转
         line = make_line_redge((0, 0, 0), (2, 0, 0))
         rotated_line = rotate_shape(line, 90, (0, 0, 1), (1, 0, 0))
    """
    if angle == 0:
        return shape
    else:
        try:
            cs = get_current_cs()
            global_axis = cs.transform_point(np.array(axis)) - cs.origin
            global_origin = cs.transform_point(np.array(origin))

            origin_vec = Vector(*global_origin)
            axis_vec = Vector(*global_axis).normalized() + origin_vec

            if isinstance(shape, Vertex):
                new_cq_shape = shape.cq_vertex.rotate(origin_vec, axis_vec, angle)
                new_shape = Vertex(new_cq_shape)
            elif isinstance(shape, Edge):
                new_cq_shape = shape.cq_edge.rotate(origin_vec, axis_vec, angle)
                new_shape = Edge(new_cq_shape)
            elif isinstance(shape, Wire):
                new_cq_shape = shape.cq_wire.rotate(origin_vec, axis_vec, angle)
                new_shape = Wire(new_cq_shape)
            elif isinstance(shape, Face):
                new_cq_shape = shape.cq_face.rotate(origin_vec, axis_vec, angle)
                new_shape = Face(new_cq_shape)
            elif isinstance(shape, Solid):
                new_cq_shape = shape.cq_solid.rotate(origin_vec, axis_vec, angle)
                new_shape = Solid(new_cq_shape)
            else:
                raise ValueError(f"不支持的几何体类型: {type(shape)}")  # type: ignore[unreachable]

            # 复制标签和元数据
            new_shape._tags = shape._tags.copy()
            new_shape._metadata = shape._metadata.copy()

            return new_shape
        except Exception as e:
            raise ValueError(
                f"旋转几何体失败: {e}. 请检查几何体、角度、轴向和中心点是否有效。"
            )


# =============================================================================
# 3D操作函数
# =============================================================================


def extrude_rsolid(
    profile: Union[Wire, Face], direction: Tuple[float, float, float], distance: float
) -> Solid:
    """拉伸轮廓创建实体

    Args:
        profile (Union[Wire, Face]): 要拉伸的轮廓，可以是封闭的线或面
        direction (Tuple[float, float, float]): 拉伸方向向量 (x, y, z)，
            定义拉伸的方向，会被标准化处理
        distance (float): 拉伸距离，必须为正数

    Returns:
        Solid: 拉伸后的实体对象

    Raises:
        ValueError: 当轮廓不是封闭的线、距离小于等于0或其他参数无效时抛出异常

    Usage:
        沿指定方向拉伸二维轮廓创建三维实体。如果输入是线，必须是封闭的线；
        如果输入是面，直接进行拉伸。这是创建柱状、管状等规则几何体的基础操作。

    Example:
         # 拉伸圆形面创建圆柱体
         circle = make_circle_rface((0, 0, 0), 1.0)
         cylinder = extrude_rsolid(circle, (0, 0, 1), 5.0)

         # 拉伸矩形面创建立方体
         rect = make_rectangle_rface(2.0, 2.0)
         box = extrude_rsolid(rect, (0, 0, 1), 3.0)

         # 拉伸复杂轮廓
         points = [(0, 0, 0), (2, 0, 0), (2, 1, 0), (0, 1, 0)]
         profile_wire = make_polyline_rwire(points, closed=True)
         extruded_shape = extrude_rsolid(profile_wire, (0, 0, 1), 4.0)
    """
    try:
        if distance <= 0:
            raise ValueError("拉伸距离必须大于0")

        cs = get_current_cs()
        global_direction = cs.transform_point(np.array(direction)) - cs.origin

        direction_vec = Vector(*global_direction).normalized() * distance

        if isinstance(profile, Wire):
            # 如果是线，先转换为面
            if profile.is_closed():
                face = Face(cq.Face.makeFromWires(profile.cq_wire))
            else:
                raise ValueError(
                    "如果传入线框作为拉伸对象，那么线框必须是闭合的, 而你的线框没有闭合，请检查构成线框的点是否正确"
                )
        elif isinstance(profile, Face):
            face = profile
        else:
            raise ValueError("只能拉伸线或面")  # type: ignore[unreachable]

        # 使用CADQuery的Solid.extrudeLinear方法
        cq_solid = cq.Solid.extrudeLinear(face.cq_face, direction_vec)
        solid = Solid(cq_solid)

        side_face_count = 0
        profile_face_normal = None
        for face_after_extrusion in solid.get_faces():
            if face_after_extrusion.cq_face.Center() == face.cq_face.Center():
                face_after_extrusion._tags = profile._tags.copy()
                face_after_extrusion.add_tag("extrusion start face")
                face_after_extrusion._metadata = profile._metadata.copy()
                profile_face_normal = face_after_extrusion.cq_face.normalAt(
                    face.cq_face.Center().x, face.cq_face.Center().y
                )[0]

        if profile_face_normal is None:
            raise ValueError("没有找到和Profile一致的面对象")

        for face_after_extrusion in solid.get_faces():
            # 开始根据法向量判断顶面底面和侧面
            face_center = face_after_extrusion.cq_face.Center()
            # 如果法向量和dir正交，认为是侧面
            face_normal, _ = face_after_extrusion.cq_face.normalAt(
                face_center.x, face_center.y
            )
            if face_normal.dot(direction_vec) == 0:
                face_after_extrusion._tags = profile._tags.copy()
                face_after_extrusion.add_tag("extrusion side face")
                side_face_count += 1
                face_after_extrusion.add_tag(f"{side_face_count}")

            # 法向量夹角180度，是顶面
            if face_normal.getAngle(profile_face_normal) == math.pi:
                face_after_extrusion._tags = profile._tags.copy()
                face_after_extrusion.add_tag("extrusion end face")

        # 复制标签和元数据
        solid._tags = profile._tags.copy()
        solid.add_tag("extrusion solid")
        solid._metadata = profile._metadata.copy()

        return solid
    except Exception as e:
        raise ValueError(f"拉伸失败: {e}. 请检查轮廓、方向和距离是否有效。")


def revolve_rsolid(
    profile: Union[Wire, Face],
    axis: Tuple[float, float, float] = (0, 0, 1),
    angle: float = 360,
    origin: Tuple[float, float, float] = (0, 0, 0),
) -> Solid:
    """围绕轴旋转轮廓创建实体

    Args:
        profile (Union[Wire, Face]): 要旋转的轮廓，可以是封闭的线或面
        axis (Tuple[float, float, float], optional): 旋转轴向量 (x, y, z)，
            定义旋转轴的方向，默认为 (0, 0, 1)
        angle (float, optional): 旋转角度，单位为度数（0-360），
            默认为360度（完整旋转），正值表示逆时针旋转
        origin (Tuple[float, float, float], optional): 旋转轴通过的点坐标 (x, y, z)，
            默认为 (0, 0, 0), 由此我们知道，origin和axis可以求出转轴两点，一点是origin本身，另一点是origin+axis向量的终点

    Returns:
        Solid: 旋转后的实体对象

    Raises:
        ValueError: 当轮廓不是封闭的线、角度小于等于0或其他参数无效时抛出异常

    Usage:
        围绕指定轴旋转二维轮廓创建三维实体。常用于创建轴对称的几何体，
        如圆柱体、圆锥体、球体等。如果输入是线，必须是封闭的线。

    Example:
         # 旋转矩形创建圆柱体
         rect = make_rectangle_rface(1.0, 3.0, (2, 0, 0))  # 远离旋转轴
         cylinder = revolve_rsolid(rect, (0, 0, 1), 360)

         # 创建圆锥体
         triangle_points = [(1, 0, 0), (2, 0, 0), (1.5, 2, 0)]
         triangle = make_polyline_rwire(triangle_points, closed=True)
         cone = revolve_rsolid(triangle, (0, 0, 1), 360)

         # 创建部分旋转体（90度扇形）
         rect = make_rectangle_rface(0.5, 2.0, (1.5, 0, 0))
         partial_solid = revolve_rsolid(rect, (0, 0, 1), 90)
    """
    try:
        if angle <= 0:
            raise ValueError("旋转角度必须大于0")

        cs = get_current_cs()
        global_axis = cs.transform_point(np.array(axis)) - cs.origin
        global_origin = cs.transform_point(np.array(origin))

        # 获取轮廓对应的面
        if isinstance(profile, Wire):
            # 如果是线，先转换为面
            if profile.is_closed():
                face = Face(cq.Face.makeFromWires(profile.cq_wire))
            else:
                raise ValueError("旋转的线必须是闭合的")
        elif isinstance(profile, Face):
            face = profile
        else:
            raise ValueError("只能旋转线或面")

        print(f"revolve_rsolid: profile type: {type(profile)}, face type: {type(face)}")
        print(
            f"with parameters: axis={global_axis}, angle={angle}, origin={global_origin}"
        )

        rv = revolve(
            face.cq_face,
            p=Vector((global_origin[0], global_origin[1], global_origin[2])),
            d=Vector(
                (
                    global_axis[0],
                    global_axis[1],
                    global_axis[2],
                )
            ).normalized(),
            a=angle,
        )

        print(f"Revolve result type: {type(rv)}")

        if hasattr(rv, "Solids") and rv.Solids():
            cq_solid = rv.Solids()[0]
        else:
            cq_solid = rv

        solid = Solid(cq_solid)

        # 复制标签和元数据
        solid._tags = profile._tags.copy()
        solid._metadata = profile._metadata.copy()

        return solid
    except Exception as e:
        raise ValueError(f"旋转失败: {e}. 请检查轮廓、轴向、角度和中心点是否有效。")


# =============================================================================
# 标签和选择函数
# =============================================================================


def set_tag(shape: AnyShape, tag: str) -> AnyShape:
    """为几何体设置标签

    Args:
        shape: 几何体
        tag: 标签名称

    Returns:
        设置标签后的几何体
    """
    try:
        shape.add_tag(tag)
        return shape
    except Exception as e:
        raise ValueError(f"设置标签失败: {e}. 请检查几何体和标签名称是否有效。")


def select_faces_by_tag(solid: Solid, tag: str) -> List[Face]:
    """根据标签选择面

    Args:
        solid: 实体
        tag: 标签名称

    Returns:
        匹配标签的面列表
    """
    try:
        faces = solid.get_faces()
        return [face for face in faces if face.has_tag(tag)]
    except Exception as e:
        raise ValueError(f"选择面失败: {e}. 请检查实体和标签名称是否有效。")


def select_edges_by_tag(shape: Union[Face, Solid], tag: str) -> List[Edge]:
    """根据标签选择边

    Args:
        shape: 面或实体
        tag: 标签名称

    Returns:
        匹配标签的边列表
    """
    try:
        if isinstance(shape, Face):
            edges = [Edge(edge) for edge in shape.cq_face.Edges()]
        elif isinstance(shape, Solid):
            edges = shape.get_edges()
        else:
            raise ValueError("只能从面或实体中选择边")

        return [edge for edge in edges if edge.has_tag(tag)]
    except Exception as e:
        raise ValueError(f"选择边失败: {e}. 请检查几何体和标签名称是否有效。")


# =============================================================================
# 布尔运算函数
# =============================================================================


def union_rsolidlist(*solids: Union[Solid, Sequence[Solid]]) -> List[Solid]:
    """实体列表并集运算

    Args:
        *solids: 需要尝试并集的实体对象，可以传入：
            - 单个序列：union_rsolidlist([solid1, solid2, ...])
            - 多个参数：union_rsolidlist(solid1, solid2, ...)
            - 混合输入：union_rsolidlist(solid1, [solid2, solid3], ...)，会自动展开所有序列

    Returns:
        List[Solid]: 并集运算后的实体列表。可以合并为整体的实体会被融合，
            无法融合的实体会原样保留。

    Raises:
        ValueError: 当输入列表无效或内部包含非Solid对象时抛出异常

    Usage:
        将一组实体尝试进行并集运算。任何可以通过并集连接成整体的实体
        都会被融合成一个新的实体；无法连接的实体保持独立。该过程会一直
        进行，直到没有新的实体可以被成功融合为止。

    Example:
         # 创建三个实体，其中前两个接触可以融合，第三个独立
         box1 = make_box_rsolid(2, 2, 2, (0, 0, 0))
         box2 = make_box_rsolid(2, 2, 2, (1, 0, 0))
         sphere = make_sphere_rsolid(1.0, (10, 0, 0))

         # 多种调用方式都支持且等价
         union_results1 = union_rsolidlist([box1, box2, sphere])
         union_results2 = union_rsolidlist(box1, box2, sphere)
         union_results3 = union_rsolidlist(box1, [box2, sphere])
         # union_results长度为2：一个融合后的立方体组合和一个独立的球体
    """

    def _attempt_fuse(base: Solid, candidate: Solid) -> Optional[Solid]:
        s1 = base.cq_solid
        s2 = candidate.cq_solid

        if s1.isNull() or s2.isNull():
            raise ValueError("输入实体无效，无法进行并集运算。")

        fused_shape = fuse(s1, s2)
        if hasattr(fused_shape, "Solids") and fused_shape.Solids():
            cq_result = fused_shape.Solids()[0]
        else:
            cq_result = fused_shape

        fused_solid = Solid(cq_result)
        if math.isclose(
            fused_solid.get_volume(),
            base.get_volume(),
            rel_tol=1e-9,
            abs_tol=1e-12,
        ):
            return None

        fused_solid._tags = base._tags.union(candidate._tags)
        fused_solid._metadata = {**base._metadata, **candidate._metadata}

        return fused_solid

    try:
        # 递归展开所有参数：将Solid直接添加，将序列展开
        def _flatten_solids(args):
            result = []
            for arg in args:
                if isinstance(arg, Solid):
                    result.append(arg)
                elif isinstance(arg, Sequence) and not isinstance(arg, (str, bytes)):
                    result.extend(_flatten_solids(arg))
                else:
                    result.append(arg)  # 保留非Solid对象，后续会进行类型检查
            return result

        remaining = _flatten_solids(solids)

        if not remaining:
            return []

        for solid in remaining:
            if not isinstance(solid, Solid):
                raise ValueError("union_rsolidlist函数只接受Solid类型的对象")

        result: List[Solid] = []

        while remaining:
            base = remaining.pop(0)
            merged = True

            while merged:
                merged = False
                idx = 0
                while idx < len(remaining):
                    candidate = remaining[idx]
                    fused = _attempt_fuse(base, candidate)
                    if fused is None:
                        idx += 1
                        continue

                    base = fused
                    remaining.pop(idx)
                    merged = True

                # 如果在本轮中没有融合发生，则跳出内循环

            result.append(base)

        return result
    except Exception as e:
        raise ValueError(f"并集运算失败: {e}. 请检查实体列表是否有效。")


def cut_rsolidlist(*solids: Union[Solid, Sequence[Solid]]) -> List[Solid]:
    """实体差集运算（布尔减法）

    Args:
        *solids: 需要进行差集运算的实体对象，可以传入：
            - 单个序列：cut_rsolidlist([solid1, solid2, ...])
            - 多个参数：cut_rsolidlist(solid1, solid2, ...)
            - 混合输入：cut_rsolidlist(solid1, [solid2, solid3], ...)，会自动展开所有序列

            第一个实体作为基础实体，后续实体依次从基础实体中减去。

    Returns:
        List[Solid]: 差集运算结果的实体列表。从第一个实体中依次减去其他所有实体。
            返回包含结果的列表：[result_solid]

    Raises:
        ValueError: 当输入实体无效或运算失败时抛出异常

    Usage:
        从第一个实体中依次减去其他实体的重叠部分，常用于创建孔洞、凹槽等。
        结果实体的体积 = solid1体积 - (solid1∩solid2) - (结果∩solid3) - ...

    Example:
         # 在立方体中创建圆形孔（两种方式等价）
         box = make_box_rsolid(4, 4, 4)
         hole = make_cylinder_rsolid(1.0, 4.0)
         result1 = cut_rsolidlist(box, hole)
         result2 = cut_rsolidlist([box, hole])

         # 创建多个孔的结构
         base = make_box_rsolid(6, 3, 2)
         hole1 = make_cylinder_rsolid(0.5, 2, (1, 0, 0))
         hole2 = make_cylinder_rsolid(0.5, 2, (5, 0, 0))
         slotted_base = cut_rsolidlist(base, hole1, hole2)

         # 从球体中减去立方体
         sphere = make_sphere_rsolid(2.0)
         cube = make_box_rsolid(2, 2, 2)
         carved_sphere = cut_rsolidlist(sphere, cube)
    """
    try:
        # 递归展开所有参数：将Solid直接添加，将序列展开
        def _flatten_solids(args):
            result = []
            for arg in args:
                if isinstance(arg, Solid):
                    result.append(arg)
                elif isinstance(arg, Sequence) and not isinstance(arg, (str, bytes)):
                    result.extend(_flatten_solids(arg))
                else:
                    result.append(arg)  # 保留非Solid对象，后续会进行类型检查
            return result

        remaining = _flatten_solids(solids)

        if not remaining:
            return []

        if len(remaining) == 1:
            return [remaining[0]]

        for solid in remaining:
            if not isinstance(solid, Solid):
                raise ValueError("cut_rsolidlist函数只接受Solid类型的对象")

        # 从第一个实体开始，依次减去其他实体
        result_solid = remaining[0]

        for i in range(1, len(remaining)):
            candidate = remaining[i]

            s1 = result_solid.cq_solid
            s2 = candidate.cq_solid

            if s1.isNull() or s2.isNull():
                raise ValueError("输入实体无效，无法进行差集运算。")

            # 检查是否有交集
            intersection = intersect(s1, s2)
            if hasattr(intersection, "Solids") and intersection.Solids():
                intersection_solid = intersection.Solids()[0]
            else:
                intersection_solid = intersection

            intersection_obj = Solid(intersection_solid)

            if intersection_obj.get_volume() < 1e-12:
                # 没有有效的交集，跳过此次切割
                continue

            # 执行差集操作
            rv = cut(s1, s2)

            if hasattr(rv, "Solids") and rv.Solids():
                cq_result = rv.Solids()[0]
            else:
                cq_result = rv

            result_solid = Solid(cq_result)

        # 保留第一个实体的标签和元数据
        result_solid._tags = remaining[0]._tags.copy()
        result_solid._metadata = remaining[0]._metadata.copy()
        result_solid.add_tag("cut_result")

        return [result_solid]
    except Exception as e:
        raise ValueError(f"差集运算失败: {e}. 请检查实体列表是否有效。")


def intersect_rsolidlist(*solids: Union[Solid, Sequence[Solid]]) -> List[Solid]:
    """实体交集运算（布尔交集）

    Args:
        *solids: 需要进行交集运算的实体对象，可以传入：
            - 单个序列：intersect_rsolidlist([solid1, solid2, ...])
            - 多个参数：intersect_rsolidlist(solid1, solid2, ...)
            - 混合输入：intersect_rsolidlist(solid1, [solid2, solid3], ...)，会自动展开所有序列

    Returns:
        List[Solid]: 交集运算结果的实体列表。所有输入实体的共同交集部分。
            如果没有有效的交集，返回空列表。

    Raises:
        ValueError: 当输入实体无效或运算失败时抛出异常

    Usage:
        计算多个实体的交集，返回只包含所有实体重叠部分的新实体列表。
        如果多个实体不相交，可能返回空列表。交集体积小于等于任一输入实体。

    Example:
         # 计算多个实体的交集（两个方式等价）
         box1 = make_box_rsolid(3, 3, 3, (0, 0, 0))
         box2 = make_box_rsolid(3, 3, 3, (1, 1, 0))
         sphere = make_sphere_rsolid(2.5)
         intersection1 = intersect_rsolidlist([box1, box2, sphere])
         intersection2 = intersect_rsolidlist(box1, box2, sphere)
         # 两种调用方式等价

         # 球体和立方体的交集
         sphere = make_sphere_rsolid(2.0)
         cube = make_box_rsolid(3, 3, 3)
         rounded_cube = intersect_rsolidlist(sphere, cube)

         # 三个实体的交集
         cylinder = make_cylinder_rsolid(1.5, 4.0)
         slab = make_box_rsolid(4, 4, 2, (0, 0, 1))
         intersection = intersect_rsolidlist(cylinder, slab, sphere)
    """
    try:
        # 递归展开所有参数：将Solid直接添加，将序列展开
        def _flatten_solids(args):
            result = []
            for arg in args:
                if isinstance(arg, Solid):
                    result.append(arg)
                elif isinstance(arg, Sequence) and not isinstance(arg, (str, bytes)):
                    result.extend(_flatten_solids(arg))
                else:
                    result.append(arg)  # 保留非Solid对象，后续会进行类型检查
            return result

        remaining = _flatten_solids(solids)

        if not remaining:
            return []

        for solid in remaining:
            if not isinstance(solid, Solid):
                raise ValueError("intersect_rsolidlist函数只接受Solid类型的对象")

        if len(remaining) == 1:
            # 只有一个实体，直接返回
            return [remaining[0]]

        # 从第一个实体开始，依次与后续实体进行交集运算
        result_solid = remaining[0]

        for i in range(1, len(remaining)):
            candidate = remaining[i]

            s1 = result_solid.cq_solid
            s2 = candidate.cq_solid

            if s1.isNull() or s2.isNull():
                raise ValueError("输入实体无效，无法进行交集运算。")

            rv = intersect(s1, s2)

            if hasattr(rv, "Solids") and rv.Solids():
                cq_result = rv.Solids()[0]
            else:
                cq_result = rv

            result_solid = Solid(cq_result)

            # 检查交集是否为空
            if result_solid.get_volume() < 1e-12:
                # 交集体积太小，视为无交集
                return []

        # 合并所有输入实体的标签和元数据
        all_tags: set = set()
        all_metadata: dict = {}
        for solid in remaining:
            all_tags = (
                all_tags.intersection(solid._tags) if all_tags else solid._tags.copy()
            )
            all_metadata.update(solid._metadata)

        result_solid._tags = all_tags
        result_solid._metadata = all_metadata
        result_solid.add_tag("intersect_result")

        return [result_solid]
    except Exception as e:
        raise ValueError(f"交集运算失败: {e}. 请检查实体列表是否有效。")


# =============================================================================
# 导出函数
# =============================================================================


_EXPORTABLE_TYPES = (Solid, Face, Wire, Edge, Vertex)


def _normalize_shape_input(
    shapes: Union[AnyShape, Sequence[AnyShape]],
) -> List[AnyShape]:
    """将导出输入标准化为平坦的几何体列表"""

    if isinstance(shapes, _EXPORTABLE_TYPES):
        return [shapes]

    if isinstance(shapes, Sequence) and not isinstance(shapes, (str, bytes)):
        normalized: List[AnyShape] = []
        for item in shapes:
            normalized.extend(_normalize_shape_input(cast(AnyShape, item)))
        return normalized

    raise ValueError(
        "export 函数只支持 Solid、Face、Wire、Edge、Vertex 或其序列类型的输入"
    )


def export_step(shapes: Union[AnyShape, Sequence[AnyShape]], filename: str) -> None:
    """导出为STEP格式

    Args:
        shapes: 要导出的几何体或几何体列表
        filename: 输出文件名

    Raises:
        ValueError: 当导出失败时
    """
    try:
        shape_list = _normalize_shape_input(shapes)

        # 创建CADQuery的Workplane并添加所有几何体
        wp = cq.Workplane()
        for shape in shape_list:
            if isinstance(shape, Solid):
                wp = wp.add(shape.cq_solid)
            elif isinstance(shape, Face):
                wp = wp.add(shape.cq_face)
            elif isinstance(shape, Wire):
                wp = wp.add(shape.cq_wire)
            elif isinstance(shape, Edge):
                wp = wp.add(shape.cq_edge)
            elif isinstance(shape, Vertex):
                wp = wp.add(shape.cq_vertex)
            else:
                raise ValueError(
                    "export_step函数只支持Solid、Face、Wire、Edge和Vertex类型的几何体"
                )

        # 导出到STEP文件
        cq.exporters.export(wp, filename)
    except Exception as e:
        raise ValueError(f"导出STEP文件失败: {e}. 请检查几何体和文件名是否有效。")


def export_stl(shapes: Union[AnyShape, Sequence[AnyShape]], filename: str) -> None:
    """导出为STL格式

    Args:
        shapes: 要导出的几何体或几何体列表
        filename: 输出文件名

    Raises:
        ValueError: 当导出失败时
    """
    try:
        shape_list = _normalize_shape_input(shapes)

        # 创建CADQuery的Workplane并添加所有几何体
        wp = cq.Workplane()
        for shape in shape_list:
            if isinstance(shape, Solid):
                wp = wp.add(shape.cq_solid)
            elif isinstance(shape, Face):
                wp = wp.add(shape.cq_face)
            else:
                raise ValueError("export_stl函数只支持Solid和Face类型的几何体")

        # 导出到STL文件
        cq.exporters.export(wp, filename)
    except Exception as e:
        raise ValueError(f"导出STL文件失败: {e}. 请检查几何体和文件名是否有效。")


def render_screenshot_rpath(
    shapes: Union[Solid, Sequence[Solid]],
    output_path: str,
    highlight_tags: Optional[Sequence[str]] = None,
    tag_labels: Optional[Dict[str, str]] = None,
    image_size: Tuple[int, int] = (1400, 900),
    view: Union[Tuple[float, float], str] = "auto",
    show_axes: bool = True,
    show_legend: bool = True,
    zoom: float = 4.0,
) -> str:
    """渲染几何体截图并保存到文件。

    Args:
        shapes: 要渲染的实体或实体列表。
        output_path: 输出图片路径（PNG）。
        highlight_tags: 需要高亮的标签列表（对Solid或Face生效）。
        tag_labels: 标签显示名映射。
        image_size: 输出图片尺寸 (width, height)。
        view: 视角 (elev, azim) 或预设名称（auto/iso/top/bottom/front/back/left/right）。
        show_axes: 是否显示XYZ正方向。
        show_legend: 是否在左上角显示标签图例。
        zoom: 视图边距缩放倍率（>1 减少边距使模型更大，仍保持不裁剪）。

    Returns:
        str: 输出文件路径。

    Raises:
        ValueError: 当输入几何体无效或渲染失败时抛出异常。

    Usage:
        生成截图并高亮指定标签。

    Example:
         box = make_box_rsolid(4, 3, 2)
         render_screenshot_rpath(box, "preview.png", highlight_tags=["top"])
    """
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.colors import to_rgb
        from mpl_toolkits.mplot3d import proj3d
        from mpl_toolkits.mplot3d.art3d import Line3DCollection, Poly3DCollection

        shape_list = _normalize_shape_input(shapes)
        solids = [shape for shape in shape_list if isinstance(shape, Solid)]
        if not solids:
            raise ValueError("render_screenshot_rpath 仅支持 Solid 类型")

        background = "#111111"
        base_color = (0.6, 0.62, 0.64)
        highlight_colors: Dict[str, Tuple[float, float, float]] = {}
        fit_mode = "model"
        axis_scale = 1.6
        axis_fit_weight = 0.0
        wireframe_only = False
        mesh_tolerance = 0.35
        mesh_angular_tolerance = 0.22

        highlight_list = [tag for tag in (highlight_tags or [])]
        labels = tag_labels or {}
        label_points: Dict[str, Tuple[float, float, float]] = {}

        all_polys: List[List[Tuple[float, float, float]]] = []
        all_colors: List[Tuple[float, float, float, float]] = []
        triangles: List[np.ndarray] = []
        tri_normals: List[np.ndarray] = []
        bbox_min = np.array([np.inf, np.inf, np.inf])
        bbox_max = np.array([-np.inf, -np.inf, -np.inf])

        base_rgb = np.array(to_rgb(base_color))
        palette = [
            "#f39c12",
            "#9b59b6",
            "#f1c40f",
            "#1abc9c",
            "#e67e22",
            "#e84393",
            "#16a085",
            "#d35400",
        ]
        highlight_colors = highlight_colors or {}
        highlight_color_map: Dict[str, np.ndarray] = {}
        for idx, tag in enumerate(highlight_list):
            if tag in highlight_colors:
                highlight_color_map[tag] = np.array(to_rgb(highlight_colors[tag]))
            else:
                highlight_color_map[tag] = np.array(to_rgb(palette[idx % len(palette)]))

        light_dirs = [
            np.array([0.7, -0.1, 0.7]),
            np.array([-0.6, 0.25, 0.32]),
            np.array([0.15, -0.9, 0.2]),
            np.array([0.0, 0.0, 1.0]),
            np.array([-0.15, -0.1, -0.98]),
        ]
        light_dirs = [vec / np.linalg.norm(vec) for vec in light_dirs]
        light_weights = [1.35, 0.4, 0.3, 0.18, 0.08]

        def _shade(normals: np.ndarray, color: np.ndarray) -> np.ndarray:
            ambient = 0.12
            intensity = np.full((normals.shape[0],), ambient, dtype=float)
            for w, light in zip(light_weights, light_dirs):
                intensity += w * np.maximum(0.0, normals @ light)
            intensity = np.clip(intensity, 0.0, 1.0)
            intensity = np.power(intensity, 1.35)
            shaded = color[None, :] * intensity[:, None]
            shaded = np.clip(shaded, 0.0, 1.0)
            alpha = np.ones((shaded.shape[0], 1))
            return np.hstack([shaded, alpha])

        for solid in solids:
            bb = solid.cq_solid.BoundingBox()
            bbox_min = np.minimum(bbox_min, np.array([bb.xmin, bb.ymin, bb.zmin]))
            bbox_max = np.maximum(bbox_max, np.array([bb.xmax, bb.ymax, bb.zmax]))

        model_min = bbox_min.copy()
        model_max = bbox_max.copy()

        axis_solids: List[Solid] = []
        axis_colors: Dict[str, np.ndarray] = {}
        axis_len_x = 0.0
        axis_len_y = 0.0
        axis_len_z = 0.0
        if show_axes:
            span = float(np.max(model_max - model_min))
            if span <= 0:
                span = 1.0
            axis_margin = span * 0.08
            axis_len_x_base = max(span * 0.3, max(0.0, bbox_max[0]) + axis_margin)
            axis_len_y_base = max(span * 0.3, max(0.0, bbox_max[1]) + axis_margin)
            axis_len_z_base = max(span * 0.3, max(0.0, bbox_max[2]) + axis_margin)
            axis_len_x = max(0.0, axis_len_x_base + axis_margin * (axis_scale - 1.0))
            axis_len_y = max(0.0, axis_len_y_base + axis_margin * (axis_scale - 1.0))
            axis_len_z = max(0.0, axis_len_z_base + axis_margin * (axis_scale - 1.0))
            axis_radius = max(
                span * 0.004, min(axis_len_x, axis_len_y, axis_len_z) * 0.02
            )
            head_len_factor = 0.2
            head_radius = axis_radius * 2.0

            def _axis_solid(axis: Tuple[float, float, float], length: float) -> Solid:
                shaft_len = length * (1.0 - head_len_factor)
                head_len = length * head_len_factor
                shaft = make_cylinder_rsolid(
                    axis_radius,
                    shaft_len,
                    bottom_face_center=(0.0, 0.0, 0.0),
                    axis=axis,
                )
                cone = make_cone_rsolid(
                    head_radius,
                    head_len,
                    0.0,
                    bottom_face_center=tuple(np.array(axis) * shaft_len),
                    axis=axis,
                )
                merged = union_rsolidlist(shaft, cone)[0]
                return merged

            axis_x = _axis_solid((1.0, 0.0, 0.0), axis_len_x)
            axis_y = _axis_solid((0.0, 1.0, 0.0), axis_len_y)
            axis_z = _axis_solid((0.0, 0.0, 1.0), axis_len_z)

            axis_x.apply_tag("axis.x")
            axis_y.apply_tag("axis.y")
            axis_z.apply_tag("axis.z")
            axis_solids = [axis_x, axis_y, axis_z]
            axis_colors = {
                "axis.x": np.array([1.0, 0.35, 0.35]),
                "axis.y": np.array([0.35, 1.0, 0.55]),
                "axis.z": np.array([0.45, 0.65, 1.0]),
            }

        render_solids = solids + axis_solids

        for solid in render_solids:
            bb = solid.cq_solid.BoundingBox()
            if solid not in solids and fit_mode == "axes":
                bbox_min = np.minimum(bbox_min, np.array([bb.xmin, bb.ymin, bb.zmin]))
                bbox_max = np.maximum(bbox_max, np.array([bb.xmax, bb.ymax, bb.zmax]))

            highlight_tag = next(
                (tag for tag in highlight_list if solid.has_tag(tag)), None
            )
            axis_tag = next((tag for tag in axis_colors if solid.has_tag(tag)), None)
            if highlight_tag and highlight_tag not in label_points:
                label_points[highlight_tag] = (
                    0.5 * (bb.xmin + bb.xmax),
                    0.5 * (bb.ymin + bb.ymax),
                    0.5 * (bb.zmin + bb.zmax),
                )

            for face in solid.get_faces():
                face_tag = next(
                    (tag for tag in highlight_list if face.has_tag(tag)), None
                )
                face_highlight_tag = face_tag or highlight_tag
                if face_highlight_tag and face_tag and face_tag not in label_points:
                    center = face.get_center()
                    label_points[face_tag] = (center.x, center.y, center.z)

                verts, tri_indices = face.cq_face.tessellate(
                    mesh_tolerance, mesh_angular_tolerance
                )
                if not tri_indices:
                    continue

                vertices = np.array([[v.x, v.y, v.z] for v in verts], dtype=float)
                tris = np.array(tri_indices, dtype=int)
                tri_pts = vertices[tris]
                normals = np.cross(
                    tri_pts[:, 1] - tri_pts[:, 0], tri_pts[:, 2] - tri_pts[:, 0]
                )
                norms = np.linalg.norm(normals, axis=1)
                normals = np.divide(
                    normals,
                    norms[:, None],
                    out=np.zeros_like(normals),
                    where=norms[:, None] != 0,
                )

                if axis_tag:
                    color = axis_colors[axis_tag]
                elif face_highlight_tag:
                    color = highlight_color_map.get(face_highlight_tag, base_rgb)
                else:
                    color = base_rgb
                colors = _shade(normals, color)
                all_polys.extend(tri_pts.tolist())
                all_colors.extend(colors.tolist())
                triangles.extend(list(tri_pts))
                tri_normals.extend(list(normals))

        if not all_polys:
            raise ValueError("未生成任何可渲染三角面")

        fig = plt.figure(figsize=(image_size[0] / 100, image_size[1] / 100), dpi=100)
        fig.patch.set_facecolor(background)
        ax = fig.add_subplot(111, projection="3d")
        ax.set_facecolor(background)
        ax.set_axis_off()
        fig.subplots_adjust(left=0.0, right=1.0, bottom=0.0, top=1.0)
        ax.set_position((0.0, 0.0, 1.0, 1.0))

        if wireframe_only:
            face_colors = np.array(all_colors, dtype=float)
            face_colors[:, 3] = 0.0
            collection = Poly3DCollection(
                all_polys, facecolors=face_colors, linewidths=0.0
            )
        else:
            collection = Poly3DCollection(
                all_polys, facecolors=all_colors, linewidths=0.0
            )
        collection.set_edgecolor((0, 0, 0, 0))
        collection.set_zsort("average")
        ax.add_collection3d(collection)

        bbox_min = model_min
        bbox_max = model_max
        axis_origin = np.array([0.0, 0.0, 0.0])
        if show_axes:
            axis_points = np.array(
                [
                    axis_origin,
                    axis_origin + np.array([axis_len_x, 0.0, 0.0]),
                    axis_origin + np.array([0.0, axis_len_y, 0.0]),
                    axis_origin + np.array([0.0, 0.0, axis_len_z]),
                ]
            )
        else:
            axis_points = np.array([axis_origin])

        extent_min = model_min.copy()
        extent_max = model_max.copy()
        if fit_mode == "axes":
            extent_min = np.minimum(extent_min, axis_points.min(axis=0))
            extent_max = np.maximum(extent_max, axis_points.max(axis=0))
        elif fit_mode == "model":
            weight = float(axis_fit_weight)
            if weight > 0 and show_axes:
                weight = max(0.0, min(1.0, weight))
                axis_min = axis_points.min(axis=0)
                axis_max = axis_points.max(axis=0)
                extent_min = np.where(
                    axis_min < extent_min,
                    extent_min + (axis_min - extent_min) * weight,
                    extent_min,
                )
                extent_max = np.where(
                    axis_max > extent_max,
                    extent_max + (axis_max - extent_max) * weight,
                    extent_max,
                )
        else:
            raise ValueError("fit_mode 仅支持 'model' 或 'axes'")

        span = float(np.max(extent_max - extent_min))
        if span <= 0:
            span = 1.0
        if zoom <= 0:
            raise ValueError("zoom 必须大于 0")
        size = extent_max - extent_min
        pad_ratio = 0.08
        pad_min = span * 0.01
        pad_vec = np.maximum(size * (pad_ratio / zoom), pad_min)
        min_extent = extent_min - pad_vec
        max_extent = extent_max + pad_vec
        ax.set_xlim(min_extent[0], max_extent[0])
        ax.set_ylim(min_extent[1], max_extent[1])
        ax.set_zlim(min_extent[2], max_extent[2])
        try:
            ax.set_box_aspect(max_extent - min_extent)
        except Exception:
            pass

        def _resolve_view(view_spec):
            if isinstance(view_spec, str):
                token = view_spec.strip().lower()
                spans = bbox_max - bbox_min
                if token == "auto":
                    azim = 35.0 if spans[0] >= spans[1] else 125.0
                    elev = 22.0 if spans[2] <= max(spans[0], spans[1]) else 35.0
                    return elev, azim
                if token in {"iso", "isometric"}:
                    return 25.0, 35.0
                if token == "top":
                    return 90.0, 0.0
                if token == "bottom":
                    return -90.0, 0.0
                if token == "front":
                    return 0.0, -90.0
                if token == "back":
                    return 0.0, 90.0
                if token == "left":
                    return 0.0, 180.0
                if token == "right":
                    return 0.0, 0.0
                if token == "front_right":
                    return 20.0, -45.0
                if token == "front_left":
                    return 20.0, 135.0
                if token == "rear_right":
                    return 20.0, 45.0
                if token == "rear_left":
                    return 20.0, -135.0
                raise ValueError(f"不支持的 view 预设: {view_spec}")

            if isinstance(view_spec, (list, tuple)) and len(view_spec) == 2:
                return float(view_spec[0]), float(view_spec[1])

            raise ValueError("view 必须为 (elev, azim) 或预设名称")

        elev, azim = _resolve_view(view)
        ax.view_init(elev=elev, azim=azim)

        if triangles:
            elev_rad = math.radians(elev)
            azim_rad = math.radians(azim)
            view_dir = np.array(
                [
                    math.cos(elev_rad) * math.cos(azim_rad),
                    math.cos(elev_rad) * math.sin(azim_rad),
                    math.sin(elev_rad),
                ],
                dtype=float,
            )
            edge_quant = max(mesh_tolerance * 0.001, 1e-6)

            def _quantize_point(point: np.ndarray) -> Tuple[float, float, float]:
                snapped = np.round(point / edge_quant) * edge_quant
                return (float(snapped[0]), float(snapped[1]), float(snapped[2]))

            edge_to_tris: Dict[
                Tuple[Tuple[float, float, float], Tuple[float, float, float]],
                List[int],
            ] = {}
            edge_to_seg: Dict[
                Tuple[Tuple[float, float, float], Tuple[float, float, float]],
                Tuple[np.ndarray, np.ndarray],
            ] = {}

            for tri_idx, tri in enumerate(triangles):
                for i0, i1 in ((0, 1), (1, 2), (2, 0)):
                    p0 = tri[i0]
                    p1 = tri[i1]
                    q0 = _quantize_point(p0)
                    q1 = _quantize_point(p1)
                    key = (q0, q1) if q0 <= q1 else (q1, q0)
                    edge_to_tris.setdefault(key, []).append(tri_idx)
                    edge_to_seg.setdefault(key, (p0, p1))

            hard_segments: List[np.ndarray] = []
            silhouette_segments: List[np.ndarray] = []
            angle_threshold = max(math.radians(40.0), mesh_angular_tolerance * 3.0)

            for key, tri_indices in edge_to_tris.items():
                seg = edge_to_seg[key]
                if len(tri_indices) == 1:
                    silhouette_segments.append(np.array(seg, dtype=float))
                    continue

                normals = [tri_normals[i] for i in tri_indices]
                facing = [float(np.dot(n, view_dir)) for n in normals]
                if min(facing) <= 0.0 <= max(facing):
                    silhouette_segments.append(np.array(seg, dtype=float))

                max_angle = 0.0
                for i in range(len(normals)):
                    for j in range(i + 1, len(normals)):
                        dot = float(np.clip(np.dot(normals[i], normals[j]), -1.0, 1.0))
                        angle = math.acos(dot)
                        if angle > max_angle:
                            max_angle = angle
                if max_angle >= angle_threshold:
                    hard_segments.append(np.array(seg, dtype=float))

            if hard_segments:
                hard_collection = Line3DCollection(
                    hard_segments,
                    colors=[(0.62, 0.64, 0.68, 0.75)],
                    linewidths=0.6,
                )
                ax.add_collection3d(hard_collection)
            if silhouette_segments:
                sil_collection = Line3DCollection(
                    silhouette_segments,
                    colors=[(0.88, 0.89, 0.92, 0.9)],
                    linewidths=1.1,
                )
                ax.add_collection3d(sil_collection)

        def _project_to_fig(point: Tuple[float, float, float]) -> Tuple[float, float]:
            x2, y2, _ = proj3d.proj_transform(
                point[0], point[1], point[2], ax.get_proj()
            )
            display = ax.transData.transform((x2, y2))
            return tuple(fig.transFigure.inverted().transform(display))

        def _clamp(value: float, low: float, high: float) -> float:
            return max(low, min(high, value))

        if show_axes:
            axis_label_offset = 0.008
            axis_label_specs = (
                ("X", axis_origin + np.array([axis_len_x, 0.0, 0.0]), "axis.x"),
                ("Y", axis_origin + np.array([0.0, axis_len_y, 0.0]), "axis.y"),
                ("Z", axis_origin + np.array([0.0, 0.0, axis_len_z]), "axis.z"),
            )
            for label, point, tag in axis_label_specs:
                color = axis_colors.get(tag, np.array([1.0, 1.0, 1.0]))
                xfig, yfig = _project_to_fig(
                    (float(point[0]), float(point[1]), float(point[2]))
                )
                xfig = _clamp(xfig + axis_label_offset, 0.02, 0.98)
                yfig = _clamp(yfig + axis_label_offset, 0.02, 0.98)
                fig.text(
                    xfig,
                    yfig,
                    label,
                    color=color,
                    fontsize=16,
                    ha="left",
                    va="center",
                )

        if show_legend and (highlight_list or show_axes):
            y = 0.98
            if highlight_list:
                for tag in highlight_list:
                    label = labels.get(tag, tag)
                    color = highlight_color_map.get(tag, base_rgb)
                    fig.text(
                        0.02,
                        y,
                        f"■ {label}",
                        color=color,
                        fontsize=10,
                        ha="left",
                        va="top",
                    )
                    y -= 0.035

            if show_axes:
                for label, color in (
                    ("+X", axis_colors.get("axis.x", np.array([1.0, 0.35, 0.35]))),
                    ("+Y", axis_colors.get("axis.y", np.array([0.35, 1.0, 0.55]))),
                    ("+Z", axis_colors.get("axis.z", np.array([0.45, 0.65, 1.0]))),
                ):
                    fig.text(
                        0.02,
                        y,
                        f"■ {label}",
                        color=color,
                        fontsize=10,
                        ha="left",
                        va="top",
                    )
                    y -= 0.035

        label_offset = 0.012
        for idx, (tag, point) in enumerate(label_points.items()):
            label = labels.get(tag, tag)
            xfig, yfig = _project_to_fig(point)
            xfig = _clamp(xfig + label_offset, 0.02, 0.98)
            yfig = _clamp(yfig + label_offset, 0.02, 0.98)
            yfig = _clamp(yfig - idx * 0.02, 0.02, 0.98)
            fig.text(
                xfig,
                yfig,
                label,
                color="#ffd27a",
                fontsize=10,
                ha="left",
                va="center",
                bbox=dict(
                    boxstyle="round,pad=0.2", fc="#111111", ec="#ffaa33", alpha=0.9
                ),
            )

        plt.savefig(output_path, facecolor=background)
        plt.close(fig)
        return output_path
    except Exception as e:
        raise ValueError(f"渲染截图失败: {e}.")


# =============================================================================
# 高级特征操作函数
# =============================================================================


def fillet_rsolid(solid: Solid, edges: List[Edge], radius: float) -> Solid:
    """对实体的边进行圆角操作

    Args:
        solid (Solid): 要进行圆角操作的实体对象
        edges (List[Edge]): 要进行圆角的边列表，通常从实体获取
        radius (float): 圆角半径，必须为正数，不能大于相邻面的最小尺寸

    Returns:
        Solid: 圆角后的实体对象

    Raises:
        ValueError: 当圆角半径小于等于0或圆角操作失败时抛出异常

    Usage:
        对实体的指定边进行圆角处理，创建平滑的过渡面。常用于消除尖锐边缘，
        改善外观和减少应力集中。圆角半径不能太大，否则可能导致几何冲突。

    Example:
         # 对立方体的所有边进行圆角
         box = make_box_rsolid(4, 4, 4)
         all_edges = box.get_edges()
         rounded_box = fillet_rsolid(box, all_edges[:4], 0.5)  # 只对前4条边圆角

         # 对圆柱体的边进行圆角
         cylinder = make_cylinder_rsolid(2.0, 5.0)
         edges = cylinder.get_edges()
         # 选择顶部和底部的圆边
         circular_edges = [e for e in edges if e.has_tag("circular")]
         rounded_cylinder = fillet_rsolid(cylinder, circular_edges, 0.3)

         # 对复杂几何体的特定边圆角
         complex_solid = union_rsolidlist([box, cylinder])[0]
         selected_edges = complex_solid.get_edges()[:6]
         smoothed_solid = fillet_rsolid(complex_solid, selected_edges, 0.2)
    """
    try:
        if radius <= 0:
            raise ValueError("圆角半径必须大于0")

        # 转换为CADQuery边对象
        cq_edges = [edge.cq_edge for edge in edges]

        # 执行圆角操作
        cq_result = solid.cq_solid.fillet(radius, cq_edges)
        result = Solid(cq_result)

        # 复制标签和元数据
        result._tags = solid._tags.copy()
        result._metadata = solid._metadata.copy()

        return result
    except Exception as e:
        raise ValueError(f"圆角操作失败: {e}. 请检查实体、边和半径是否有效。")


def chamfer_rsolid(solid: Solid, edges: List[Edge], distance: float) -> Solid:
    """对实体的边进行倒角操作

    Args:
        solid (Solid): 要进行倒角操作的实体对象
        edges (List[Edge]): 要进行倒角的边列表，通常从实体获取
        distance (float): 倒角距离，必须为正数，定义从边缘向内的倒角深度

    Returns:
        Solid: 倒角后的实体对象

    Raises:
        ValueError: 当倒角距离小于等于0或倒角操作失败时抛出异常

    Usage:
        对实体的指定边进行倒角处理，创建斜面过渡。与圆角不同，倒角创建的是
        平面过渡而不是圆弧过渡。常用于机械零件的边缘处理，便于装配和安全。

    Example:
         # 对立方体的边进行倒角
         box = make_box_rsolid(4, 4, 4)
         edges = box.get_edges()
         chamfered_box = chamfer_rsolid(box, edges[:4], 0.3)

         # 对圆柱体的边倒角
         cylinder = make_cylinder_rsolid(2.0, 5.0)
         cylinder_edges = cylinder.get_edges()
         chamfered_cylinder = chamfer_rsolid(cylinder, cylinder_edges[:2], 0.2)

         # 选择性倒角
         complex_solid = make_box_rsolid(6, 3, 2)
         top_edges = [e for e in complex_solid.get_edges() if e.has_tag("top")]
         chamfered_top = chamfer_rsolid(complex_solid, top_edges, 0.1)
    """
    try:
        if distance <= 0:
            raise ValueError("倒角距离必须大于0")

        # 转换为CADQuery边对象
        cq_edges = [edge.cq_edge for edge in edges]

        # 执行倒角操作
        cq_result = solid.cq_solid.chamfer(distance, None, cq_edges)
        result = Solid(cq_result)

        # 复制标签和元数据
        result._tags = solid._tags.copy()
        result._metadata = solid._metadata.copy()

        return result
    except Exception as e:
        raise ValueError(f"倒角操作失败: {e}. 请检查实体、边和距离是否有效。")


def shell_rsolid(solid: Solid, faces_to_remove: List[Face], thickness: float) -> Solid:
    """对实体进行抽壳操作，创建空心结构

    Args:
        solid (Solid): 要抽壳的实体对象
        faces_to_remove (List[Face]): 要移除的面列表，这些面将被开口，
            如果为空列表则不移除任何面（闭合抽壳）
        thickness (float): 壁厚，必须为正数，定义抽壳后的壁厚度

    Returns:
        Solid: 抽壳后的实体对象，内部为空心结构

    Raises:
        ValueError: 当壁厚小于等于0或抽壳操作失败时抛出异常

    Usage:
        将实体转换为空心结构，常用于创建容器、外壳等。通过移除指定面
        创建开口，壁厚决定了外壳的厚度。如果不移除任何面则创建闭合空心体。

    Example:
         # 创建空心立方体容器
         box = make_box_rsolid(4, 4, 4)
         top_faces = [f for f in box.get_faces() if f.has_tag("top")]
         container = shell_rsolid(box, top_faces, 0.2)

         # 创建空心球体
         sphere = make_sphere_rsolid(3.0)
         # 不移除任何面，创建闭合空心球
         hollow_sphere = shell_rsolid(sphere, [], 0.3)

         # 创建有开口的圆柱体容器
         cylinder = make_cylinder_rsolid(2.0, 5.0)
         top_faces = [f for f in cylinder.get_faces() if f.has_tag("top")]
         cup = shell_rsolid(cylinder, top_faces, 0.1)
    """
    try:
        if thickness <= 0:
            raise ValueError("壁厚必须大于0")

        # 转换为CADQuery面对象
        cq_faces = (
            [face.cq_face for face in faces_to_remove] if faces_to_remove else None
        )

        # 执行抽壳操作
        cq_result = solid.cq_solid.shell(cq_faces, thickness)
        result = Solid(cq_result)

        # 复制标签和元数据
        result._tags = solid._tags.copy()
        result._metadata = solid._metadata.copy()

        return result
    except Exception as e:
        raise ValueError(f"抽壳操作失败: {e}. 请检查实体、面和壁厚是否有效。")


def loft_rsolid(profiles: List[Wire], ruled: bool = False) -> Solid:
    """通过多个轮廓放样创建实体

    Args:
        profiles (List[Wire]): 轮廓线列表，至少需要2个轮廓，
            轮廓按顺序连接，第一个为起始轮廓，最后一个为结束轮廓
        ruled (bool, optional): 是否为直纹面，默认为False。
            True表示轮廓间用直线连接，False表示用平滑曲面连接

    Returns:
        Solid: 放样后的实体对象

    Raises:
        ValueError: 当轮廓少于2个或放样操作失败时抛出异常

    Usage:
        通过多个二维轮廓创建三维实体，轮廓间通过放样面连接。
        常用于创建复杂的过渡形状，如飞机机翼、船体等变截面结构。

    Example:
         # 创建方形到圆形的过渡体
         square = make_rectangle_rwire(2, 2, (0, 0, 0))
         circle = make_circle_rwire((0, 0, 3), 1.0)
         transition = loft_rsolid([square, circle])

         # 创建多层过渡的复杂形状
         bottom = make_rectangle_rwire(4, 4, (0, 0, 0))
         middle = make_circle_rwire((0, 0, 2), 2.0)
         top = make_rectangle_rwire(1, 1, (0, 0, 4))
         complex_shape = loft_rsolid([bottom, middle, top])

         # 创建直纹面放样
         profile1 = make_circle_rwire((0, 0, 0), 2.0)
         profile2 = make_circle_rwire((0, 0, 5), 1.0)
         ruled_loft = loft_rsolid([profile1, profile2], ruled=True)
    """
    try:
        if len(profiles) < 2:
            raise ValueError("放样至少需要2个轮廓")

        # 转换为CADQuery线对象
        cq_wires = [profile.cq_wire for profile in profiles]

        # 执行放样操作
        cq_result = cq.Solid.makeLoft(cq_wires, ruled)
        result = Solid(cq_result)

        # 合并所有轮廓的标签和元数据
        all_tags = set()
        all_metadata = {}
        for profile in profiles:
            all_tags.update(profile._tags)
            all_metadata.update(profile._metadata)

        result._tags = all_tags
        result._metadata = all_metadata

        return result
    except Exception as e:
        raise ValueError(f"放样操作失败: {e}. 请检查轮廓是否有效。")


def sweep_rsolid(profile: Face, path: Wire, is_frenet: bool = False) -> Solid:
    """沿路径扫掠轮廓创建实体

    Args:
        profile (Face): 要扫掠的轮廓面，定义扫掠的横截面形状
        path (Wire): 扫掠路径线，定义轮廓沿其移动的路径
        is_frenet (bool, optional): 是否使用Frenet框架，默认为False。
            True时轮廓沿路径的法向量旋转，False时保持轮廓方向

    Returns:
        Union[Solid, Shell]: 扫掠后的实体或壳体，取决于make_solid参数

    Raises:
        ValueError: 当轮廓、路径无效或扫掠操作失败时抛出异常

    Usage:
        沿指定路径扫掠二维轮廓创建三维实体或壳体。常用于创建管道、导线、
        复杂曲面等。Frenet框架控制轮廓在路径上的旋转行为。

    Example:
         # 沿直线扫掠圆形创建圆管
         circle = make_circle_rface((0, 0, 0), 0.5)
         line_path = make_segment_rwire((0, 0, 0), (10, 0, 0))
         tube = sweep_rsolid(circle, line_path)

         # 沿螺旋路径扫掠创建螺旋管
         square = make_rectangle_rface(0.2, 0.2)
         helix_path = make_helix_rwire(1.0, 5.0, 2.0)
         spiral_tube = sweep_rsolid(square, helix_path, is_frenet=True)

         # 沿曲线扫掠创建复杂形状
         profile = make_rectangle_rface(1.0, 0.5)
         curve_points = [(0, 0, 0), (2, 2, 1), (4, 0, 2), (6, -1, 3)]
         curve_path = make_spline_rwire(curve_points)
         swept_shape = sweep_rsolid(profile, curve_path)
    """
    make_solid = True  # 默认创建实体
    try:
        # 执行扫掠操作
        cq_result = cq.Solid.sweep(
            profile.cq_face, path.cq_wire, makeSolid=make_solid, isFrenet=is_frenet
        )

        result = Solid(cq_result)

        # 合并轮廓和路径的标签和元数据
        result._tags = profile._tags.union(path._tags)
        result._metadata = {**profile._metadata, **path._metadata}

        return result
    except Exception as e:
        raise ValueError(f"扫掠操作失败: {e}. 请检查轮廓和路径是否有效。")


def linear_pattern_rsolidlist(
    shape: AnyShape, direction: Tuple[float, float, float], count: int, spacing: float
) -> List[Solid]:
    """创建线性阵列

    Args:
        shape (AnyShape): 要阵列的几何体，可以是任意类型的几何对象
        direction (Tuple[float, float, float]): 阵列方向向量 (x, y, z)，
            定义阵列的方向，会被标准化处理
        count (int): 阵列数量，必须为正整数，包括原始对象
        spacing (float): 阵列间距，必须为正数，定义相邻对象间的距离

    Returns:
        List[Solid]: 阵列后的几何体列表，包含原始对象和所有复制的对象

    Raises:
        ValueError: 当阵列数量小于等于0或间距小于等于0时抛出异常

    Usage:
        沿指定方向创建几何体的线性阵列，生成指定数量的等间距排列对象。
        常用于创建重复结构，如齿轮齿、栅栏、螺栓阵列等。

    Example:
         # 创建立方体的线性阵列
         box = make_box_rsolid(1, 1, 1)
         boxes = linear_pattern_rsolidlist(box, (2, 0, 0), 5, 2.0)
         # 创建5个立方体，沿X轴方向间距2.0

         # 创建圆柱体的对角线阵列
         cylinder = make_cylinder_rsolid(0.5, 2.0)
         cylinders = linear_pattern_rsolidlist(cylinder, (1, 1, 0), 4, 1.5)

         # 创建复杂几何体的阵列
         complex_shape = union_rsolidlist([box, cylinder])[0]
         array = linear_pattern_rsolidlist(complex_shape, (0, 3, 0), 3, 3.0)
    """
    try:
        if count <= 0:
            raise ValueError("阵列数量必须大于0")
        if spacing <= 0:
            raise ValueError("阵列间距必须大于0")

        cs = get_current_cs()
        global_direction = cs.transform_point(np.array(direction)) - cs.origin
        direction_vec = Vector(*global_direction).normalized()

        shapes = []
        for i in range(count):
            offset = direction_vec * (spacing * i)
            translated_shape = translate_shape(shape, (offset.x, offset.y, offset.z))
            shapes.append(translated_shape)

        rv = []
        for i, s in enumerate(shapes):
            s.add_tag(f"linear_pattern_{i + 1}")
            rv.append(s)

        return rv

    except Exception as e:
        raise ValueError(f"线性阵列失败: {e}. 请检查参数是否有效。")


def radial_pattern_rsolidlist(
    shape: AnyShape,
    center: Tuple[float, float, float],
    axis: Tuple[float, float, float],
    count: int,
    total_rotation_angle: float,
) -> List[Solid]:
    """创建径向阵列（圆形阵列）

    Args:
        shape (AnyShape): 要阵列的几何体，可以是任意类型的几何对象
        center (Tuple[float, float, float]): 旋转中心点坐标 (x, y, z)
        axis (Tuple[float, float, float]): 旋转轴向量 (x, y, z)，定义旋转轴方向
        count (int): 阵列数量，必须为正整数，包括原始对象
        total_rotation_angle (float): 总旋转角度，单位为度数（0-360），
            定义整个阵列的角度范围

    Returns:
        List[Solid]: 径向阵列后的几何体列表，包含原始对象和所有旋转的对象

    Raises:
        ValueError: 当阵列数量小于等于0或角度无效时抛出异常

    Usage:
        围绕指定轴创建几何体的径向阵列，生成等角度间隔的旋转排列。
        常用于创建齿轮、花瓣、螺栓圆形分布等对称结构。

    Example:
         # 创建立方体的径向阵列（6个，360度）
         box = make_box_rsolid(1, 0.5, 0.5, (2, 0, 0))  # 距离中心2单位
         radial_boxes = radial_pattern_rsolidlist(box, (0, 0, 0), (0, 0, 1), 6, 360)

         # 创建半圆阵列
         cylinder = make_cylinder_rsolid(0.3, 1.0, (1.5, 0, 0))
         half_circle = radial_pattern_rsolidlist(cylinder, (0, 0, 0), (0, 0, 1), 4, 180)

         # 围绕Y轴的径向阵列
         element = make_sphere_rsolid(0.5, (3, 0, 0))
         vertical_array = radial_pattern_rsolidlist(element, (0, 0, 0), (0, 1, 0), 8, 360)
    """
    try:
        if count <= 0:
            raise ValueError("阵列数量必须大于0")
        if total_rotation_angle <= 0:
            raise ValueError("角度必须大于0")

        shapes = []
        angle_step = total_rotation_angle / count  # 修正角度计算，均匀分布

        for i in range(count):
            rotation_angle = angle_step * i
            rotated_shape = rotate_shape(shape, rotation_angle, axis, center)
            shapes.append(rotated_shape)

        rv = []
        for i, s in enumerate(shapes):
            s.add_tag(f"radial_pattern_{i + 1}")
            rv.append(s)

        return rv
    except Exception as e:
        raise ValueError(f"径向阵列失败: {e}. 请检查参数是否有效。")


def mirror_shape(
    shape: AnyShape,
    plane_origin: Tuple[float, float, float],
    plane_normal: Tuple[float, float, float],
) -> AnyShape:
    """镜像几何体

    Args:
        shape (AnyShape): 要镜像的几何体，可以是任意类型的几何对象
        plane_origin (Tuple[float, float, float]): 镜像平面上的一个点坐标 (x, y, z)，
            定义镜像平面的位置
        plane_normal (Tuple[float, float, float]): 镜像平面的法向量 (x, y, z)，
            定义镜像平面的方向，会被标准化处理

    Returns:
        AnyShape: 镜像后的几何体，类型与输入相同

    Raises:
        ValueError: 当几何体或镜像平面参数无效时抛出异常

    Usage:
        将几何体沿指定平面进行镜像复制，创建对称的几何结构。
        镜像平面由一个点和法向量定义，几何体在平面另一侧生成对称副本。

    Example:
         # 沿YZ平面镜像立方体
         box = make_box_rsolid(2, 2, 2, (1, 0, 0))
         mirrored_box = mirror_shape(box, (0, 0, 0), (1, 0, 0))

         # 沿XY平面镜像圆柱体
         cylinder = make_cylinder_rsolid(1.0, 3.0, (0, 0, 1))
         mirrored_cyl = mirror_shape(cylinder, (0, 0, 0), (0, 0, 1))

         # 沿任意平面镜像
         sphere = make_sphere_rsolid(1.5, (2, 2, 0))
         mirrored_sphere = mirror_shape(sphere, (1, 1, 0), (1, 1, 0))
    """
    try:
        cs = get_current_cs()
        global_origin = cs.transform_point(np.array(plane_origin))
        global_normal = cs.transform_vector(np.array(plane_normal))

        # 确保法向量不是零向量
        if np.linalg.norm(global_normal) < 1e-10:
            raise ValueError("镜像平面法向量不能是零向量")

        cq_origin = Vector(global_origin[0], global_origin[1], global_origin[2])
        cq_normal = Vector(global_normal[0], global_normal[1], global_normal[2])

        if isinstance(shape, Solid):
            # 对于Solid，创建一个包含该Solid的Workplane
            wp = cq.Workplane().add(shape.cq_solid)

            # 执行镜像
            mirrored_wp = wp.mirror(cq_normal, basePointVector=cq_origin.toTuple())

            # 获取镜像后的Solid
            mirrored_solid = mirrored_wp.val()
            new_shape = Solid(mirrored_solid)

        else:
            # 对于其他类型的几何体，暂时不支持
            raise ValueError(f"暂不支持镜像 {type(shape).__name__} 类型的几何体")

        # 复制标签和元数据
        new_shape._tags = shape._tags.copy()
        new_shape._metadata = shape._metadata.copy()
        new_shape.add_tag("mirrored")

        return new_shape
    except Exception as e:
        raise ValueError(f"镜像操作失败: {e}. 请检查几何体和镜像平面是否有效。")


def helical_sweep_rsolid(
    profile: Wire,
    pitch: float,
    height: float,
    radius: float,
    center: Tuple[float, float, float] = (0, 0, 0),
    dir: Tuple[float, float, float] = (0, 0, 1),
) -> Solid:
    """沿螺旋路径扫掠轮廓创建实体

    Args:
        profile (Wire): 要扫掠的轮廓线，必须是封闭的线轮廓
        pitch (float): 螺距，每转一圈在轴向上的距离，必须为正数
        height (float): 螺旋的总高度，必须为正数
        radius (float): 螺旋的半径，必须为正数
        center (Tuple[float, float, float], optional): 螺旋中心点坐标 (x, y, z)，
            默认为 (0, 0, 0)
        dir (Tuple[float, float, float], optional): 螺旋轴方向向量 (x, y, z)，
            默认为 (0, 0, 1) 表示沿Z轴方向

    Returns:
        Solid: 螺旋扫掠后的实体对象

    Raises:
        ValueError: 当轮廓不封闭、螺距/高度/半径无效或扫掠失败时抛出异常

    Usage:
        沿螺旋路径扫掠二维轮廓创建三维实体，常用于创建螺纹、弹簧、
        螺旋管道等具有螺旋特征的几何体。轮廓必须是封闭的。

        函数会自动矫正profile的朝向和位置：
        - 确保profile的法向量朝向X轴正方向或负方向
        - 将profile移动到距离旋转中心指定半径的位置

    Example:
         # 创建螺旋弹簧
         circle_profile = make_circle_rwire((0, 0, 0), 0.2)
         spring = helical_sweep_rsolid(circle_profile, 1.0, 10.0, 2.0)

         # 创建方形截面的螺旋管
         square_profile = make_rectangle_rwire(0.5, 0.5)
         square_helix = helical_sweep_rsolid(square_profile, 2.0, 8.0, 1.5)

         # 创建紧密螺旋结构
         small_circle = make_circle_rwire((0, 0, 0), 0.1)
         tight_helix = helical_sweep_rsolid(small_circle, 0.5, 5.0, 1.0)
    """
    try:
        if pitch <= 0:
            raise ValueError("螺距必须大于0")
        if height <= 0:
            raise ValueError("高度必须大于0")
        if radius <= 0:
            raise ValueError("半径必须大于0")

        cs = get_current_cs()
        global_center = cs.transform_point(np.array(center))
        global_dir = cs.transform_point(np.array(dir)) - cs.origin

        center_vec = Vector(*global_center)
        dir_vec = Vector(*global_dir).normalized()

        # 复制profile以避免修改原始轮廓
        corrected_profile = Wire(profile.cq_wire.copy())

        # 将Wire转换为Face用于扫掠
        try:
            profile_face = cq.Face.makeFromWires(corrected_profile.cq_wire)
        except Exception as _:
            raise ValueError("螺旋扫掠轮廓必须是闭合的")

        # 1. 矫正profile的法向量：确保法向量朝向X轴正方向
        # 获取profile的法向量（在面的中心点）
        try:
            # 获取face的法向量，normalAt返回(Vector, Vector)，取第一个
            profile_normal = profile_face.normalAt(0.5, 0.5)[0]
        except Exception as _:
            try:
                profile_normal = profile_face.normalAt(0, 0)[0]
            except Exception as _:
                # 最后的fallback，假设法向量为Z轴方向
                profile_normal = Vector(0, 0, 1)

        # 定义目标法向量：Y轴正方向
        target_normal = Vector(0, 1, 0)

        # 检查当前法向量与目标法向量的夹角
        dot_product = profile_normal.dot(target_normal)

        # 如果法向量不朝向X轴正方向，需要旋转
        if abs(dot_product) < 0.99:  # 容差，允许约8度的偏差
            # 计算旋转轴（叉积）
            rotation_axis = profile_normal.cross(target_normal)

            # 如果法向量与X轴相反（dot_product < 0），需要180度旋转
            if dot_product < -0.99:
                # 使用Y轴或Z轴作为旋转轴
                rotation_axis = Vector(0, 1, 0)
                rotation_angle = math.pi
            elif rotation_axis.Length > 1e-6:
                # 计算旋转角度
                rotation_angle = math.acos(max(-1, min(1, abs(dot_product))))
                rotation_axis = rotation_axis.normalized()
            else:
                # 如果叉积为零向量，说明已经平行，不需要旋转
                rotation_angle = 0
                rotation_axis = Vector(0, 0, 1)

            # 如果需要旋转
            if rotation_angle > 1e-6:
                # 获取profile的中心点作为旋转中心
                profile_center = profile_face.Center()
                rotation_center = Vector(
                    profile_center.x, profile_center.y, profile_center.z
                )

                # 应用旋转
                profile_face = profile_face.rotate(
                    rotation_center, rotation_axis, math.degrees(rotation_angle)
                )

        # 2. 矫正profile的位置：将profile移动到指定半径的位置
        # 获取旋转后的profile中心点
        profile_center = profile_face.Center()

        # 计算当前profile中心到旋转中心的距离
        current_center = Vector(profile_center.x, profile_center.y, profile_center.z)
        spiral_center = center_vec

        # 计算在垂直于旋转轴的平面上的投影
        to_profile = current_center - spiral_center
        projection_on_axis = to_profile.dot(dir_vec) * dir_vec
        radial_vector = to_profile - projection_on_axis

        # 如果radial_vector太小，默认使用X轴方向
        if radial_vector.Length < 1e-6:
            radial_vector = Vector(1, 0, 0)

        # 归一化径向向量并缩放到目标半径
        radial_direction = radial_vector.normalized()
        target_position = spiral_center + radial_direction * radius + projection_on_axis

        # 计算平移向量
        translation = target_position - current_center

        # 应用平移
        profile_face = profile_face.translate(translation)

        # 创建螺旋路径
        helix = cq.Wire.makeHelix(pitch, height, radius, center_vec, dir_vec)

        # 沿螺旋路径扫掠
        cq_result = cq.Solid.sweep(profile_face, helix, makeSolid=True, isFrenet=True)
        result = Solid(cq_result)

        # 复制轮廓的标签和元数据
        result._tags = profile._tags.copy()
        result._metadata = profile._metadata.copy()
        result.add_tag("helical_sweep")

        return result
    except Exception as e:
        raise ValueError(f"螺旋扫掠失败: {e}. 请检查参数是否有效。")
