"""
SimpleCAD API操作函数实现
基于README中的API设计，实现各种几何操作
"""

from typing import List, Tuple, Union, Optional, Any
import numpy as np
import cadquery as cq
from cadquery import Vector, Plane

from .core import (
    Vertex, Edge, Wire, Face, Shell, Solid, Compound,
    AnyShape, CoordinateSystem, SimpleWorkplane, get_current_cs
)


# =============================================================================
# 基础图形创建函数
# =============================================================================

def make_point_rvertex(x: float, y: float, z: float) -> Vertex:
    """创建点并返回顶点
    
    Args:
        x: X坐标
        y: Y坐标
        z: Z坐标
        
    Returns:
        创建的顶点
        
    Raises:
        ValueError: 当坐标无效时
    """
    try:
        cs = get_current_cs()
        global_point = cs.transform_point(np.array([x, y, z]))
        cq_vertex = cq.Vertex.makeVertex(*global_point)
        return Vertex(cq_vertex)
    except Exception as e:
        raise ValueError(f"创建点失败: {e}. 请检查坐标值是否有效。")


def make_line_redge(start: Tuple[float, float, float], 
                    end: Tuple[float, float, float]) -> Edge:
    """创建线段并返回边
    
    Args:
        start: 起始点坐标
        end: 结束点坐标
        
    Returns:
        创建的边
        
    Raises:
        ValueError: 当坐标无效时
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


def make_segment_redge(start: Tuple[float, float, float], 
                       end: Tuple[float, float, float]) -> Edge:
    """创建线段并返回边（别名函数）
    
    Args:
        start: 起始点坐标
        end: 结束点坐标
        
    Returns:
        创建的边
    """
    return make_line_redge(start, end)


def make_segment_rwire(start: Tuple[float, float, float], 
                       end: Tuple[float, float, float]) -> Wire:
    """创建线段并返回线
    
    Args:
        start: 起始点坐标
        end: 结束点坐标
        
    Returns:
        创建的线
    """
    try:
        edge = make_line_redge(start, end)
        cq_wire = cq.Wire.assembleEdges([edge.cq_edge])
        return Wire(cq_wire)
    except Exception as e:
        raise ValueError(f"创建线段线失败: {e}")


def make_circle_redge(center: Tuple[float, float, float], 
                      radius: float,
                      normal: Tuple[float, float, float] = (0, 0, 1)) -> Edge:
    """创建圆并返回边
    
    Args:
        center: 圆心坐标
        radius: 半径
        normal: 法向量
        
    Returns:
        创建的圆边
        
    Raises:
        ValueError: 当参数无效时
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


def make_circle_rwire(center: Tuple[float, float, float], 
                      radius: float,
                      normal: Tuple[float, float, float] = (0, 0, 1)) -> Wire:
    """创建圆并返回线
    
    Args:
        center: 圆心坐标
        radius: 半径
        normal: 法向量
        
    Returns:
        创建的圆线
    """
    try:
        edge = make_circle_redge(center, radius, normal)
        cq_wire = cq.Wire.assembleEdges([edge.cq_edge])
        return Wire(cq_wire)
    except Exception as e:
        raise ValueError(f"创建圆线失败: {e}")


def make_circle_rface(center: Tuple[float, float, float], 
                      radius: float,
                      normal: Tuple[float, float, float] = (0, 0, 1)) -> Face:
    """创建圆并返回面
    
    Args:
        center: 圆心坐标
        radius: 半径
        normal: 法向量
        
    Returns:
        创建的圆面
    """
    try:
        wire = make_circle_rwire(center, radius, normal)
        cq_face = cq.Face.makeFromWires(wire.cq_wire)
        return Face(cq_face)
    except Exception as e:
        raise ValueError(f"创建圆面失败: {e}")


def make_rectangle_rwire(width: float, height: float, 
                         center: Tuple[float, float, float] = (0, 0, 0),
                         normal: Tuple[float, float, float] = (0, 0, 1)) -> Wire:
    """创建矩形并返回线
    
    Args:
        width: 宽度
        height: 高度
        center: 中心点坐标
        normal: 法向量
        
    Returns:
        创建的矩形线
        
    Raises:
        ValueError: 当参数无效时
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
            (-half_w, half_h)
        ]
        
        # 转换到全局坐标系
        global_points = []
        for local_point in local_points:
            # 在本地坐标系中的点
            point_3d = center_global + local_point[0] * local_x + local_point[1] * local_y
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


def make_rectangle_rface(width: float, height: float, 
                         center: Tuple[float, float, float] = (0, 0, 0),
                         normal: Tuple[float, float, float] = (0, 0, 1)) -> Face:
    """创建矩形并返回面
    
    Args:
        width: 宽度
        height: 高度
        center: 中心点坐标
        normal: 法向量
        
    Returns:
        创建的矩形面
    """
    try:
        wire = make_rectangle_rwire(width, height, center, normal)
        cq_face = cq.Face.makeFromWires(wire.cq_wire)
        return Face(cq_face)
    except Exception as e:
        raise ValueError(f"创建矩形面失败: {e}")


def make_box_rsolid(width: float, height: float, depth: float,
                    center: Tuple[float, float, float] = (0, 0, 0)) -> Solid:
    """创建立方体并返回实体
    
    Args:
        width: 宽度
        height: 高度
        depth: 深度
        center: 中心点坐标
        
    Returns:
        创建的立方体实体
        
    Raises:
        ValueError: 当参数无效时
    """
    try:
        if width <= 0 or height <= 0 or depth <= 0:
            raise ValueError("宽度、高度和深度必须大于0")
            
        cs = get_current_cs()
        center_global = cs.transform_point(np.array(center))
        
        # 创建立方体
        cq_solid = cq.Solid.makeBox(width, height, depth, Vector(*center_global))
        solid = Solid(cq_solid)
        
        # 自动标记面
        solid.auto_tag_faces("box")
        
        return solid
    except Exception as e:
        raise ValueError(f"创建立方体失败: {e}. 请检查尺寸和中心点坐标是否有效。")


def make_cylinder_rsolid(radius: float, height: float,
                         center: Tuple[float, float, float] = (0, 0, 0),
                         axis: Tuple[float, float, float] = (0, 0, 1)) -> Solid:
    """创建圆柱体并返回实体
    
    Args:
        radius: 半径
        height: 高度
        center: 中心点坐标
        axis: 轴向向量
        
    Returns:
        创建的圆柱体实体
        
    Raises:
        ValueError: 当参数无效时
    """
    try:
        if radius <= 0 or height <= 0:
            raise ValueError("半径和高度必须大于0")
            
        cs = get_current_cs()
        center_global = cs.transform_point(np.array(center))
        axis_global = cs.transform_point(np.array(axis)) - cs.origin
        
        center_vec = Vector(*center_global)
        axis_vec = Vector(*axis_global)
        
        cq_solid = cq.Solid.makeCylinder(radius, height, center_vec, axis_vec)
        solid = Solid(cq_solid)
        
        # 自动标记面
        solid.auto_tag_faces("cylinder")
        
        return solid
    except Exception as e:
        raise ValueError(f"创建圆柱体失败: {e}. 请检查半径、高度、中心点和轴向是否有效。")


def make_sphere_rsolid(radius: float,
                       center: Tuple[float, float, float] = (0, 0, 0)) -> Solid:
    """创建球体并返回实体
    
    Args:
        radius: 半径
        center: 中心点坐标
        
    Returns:
        创建的球体实体
        
    Raises:
        ValueError: 当参数无效时
    """
    try:
        if radius <= 0:
            raise ValueError("半径必须大于0")
            
        cs = get_current_cs()
        center_global = cs.transform_point(np.array(center))
        
        # 使用Workplane.sphere方法创建球体，然后移动到正确位置
        if center_global[0] != 0 or center_global[1] != 0 or center_global[2] != 0:
            cq_solid = cq.Workplane("XY").center(center_global[0], center_global[1]).workplane(offset=center_global[2]).sphere(radius).val()
        else:
            cq_solid = cq.Workplane("XY").sphere(radius).val()
        
        solid = Solid(cq_solid)
        
        # 自动标记面
        solid.auto_tag_faces("sphere")
        
        return solid
    except Exception as e:
        raise ValueError(f"创建球体失败: {e}. 请检查半径和中心点坐标是否有效。")


def make_three_point_arc_redge(start: Tuple[float, float, float],
                               middle: Tuple[float, float, float],
                               end: Tuple[float, float, float]) -> Edge:
    """通过三点创建圆弧并返回边
    
    Args:
        start: 起始点坐标
        middle: 中间点坐标
        end: 结束点坐标
        
    Returns:
        创建的圆弧边
        
    Raises:
        ValueError: 当参数无效时
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


def make_three_point_arc_rwire(start: Tuple[float, float, float],
                               middle: Tuple[float, float, float],
                               end: Tuple[float, float, float]) -> Wire:
    """通过三点创建圆弧并返回线
    
    Args:
        start: 起始点坐标
        middle: 中间点坐标
        end: 结束点坐标
        
    Returns:
        创建的圆弧线
    """
    try:
        edge = make_three_point_arc_redge(start, middle, end)
        cq_wire = cq.Wire.assembleEdges([edge.cq_edge])
        return Wire(cq_wire)
    except Exception as e:
        raise ValueError(f"创建三点圆弧线失败: {e}")


def make_angle_arc_redge(center: Tuple[float, float, float],
                         radius: float,
                         start_angle: float,
                         end_angle: float,
                         normal: Tuple[float, float, float] = (0, 0, 1)) -> Edge:
    """创建角度圆弧并返回边
    
    Args:
        center: 圆心坐标
        radius: 半径
        start_angle: 起始角度（弧度）
        end_angle: 结束角度（弧度）
        normal: 法向量
        
    Returns:
        创建的圆弧边
        
    Raises:
        ValueError: 当参数无效时
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
        start_local = np.array([radius * np.cos(start_angle), radius * np.sin(start_angle), 0])
        end_local = np.array([radius * np.cos(end_angle), radius * np.sin(end_angle), 0])
        mid_angle = (start_angle + end_angle) / 2
        mid_local = np.array([radius * np.cos(mid_angle), radius * np.sin(mid_angle), 0])
        
        # 转换到全局坐标系
        start_global = center_global + start_local[0] * local_x + start_local[1] * local_y
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


def make_angle_arc_rwire(center: Tuple[float, float, float],
                         radius: float,
                         start_angle: float,
                         end_angle: float,
                         normal: Tuple[float, float, float] = (0, 0, 1)) -> Wire:
    """创建角度圆弧并返回线
    
    Args:
        center: 圆心坐标
        radius: 半径
        start_angle: 起始角度（弧度）
        end_angle: 结束角度（弧度）
        normal: 法向量
        
    Returns:
        创建的圆弧线
    """
    try:
        edge = make_angle_arc_redge(center, radius, start_angle, end_angle, normal)
        cq_wire = cq.Wire.assembleEdges([edge.cq_edge])
        return Wire(cq_wire)
    except Exception as e:
        raise ValueError(f"创建角度圆弧线失败: {e}")


def make_spline_redge(points: List[Tuple[float, float, float]],
                      tangents: Optional[List[Tuple[float, float, float]]] = None) -> Edge:
    """创建样条曲线并返回边
    
    Args:
        points: 控制点坐标列表
        tangents: 可选的切线向量列表
        
    Returns:
        创建的样条曲线边
        
    Raises:
        ValueError: 当参数无效时
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


def make_spline_rwire(points: List[Tuple[float, float, float]],
                      tangents: Optional[List[Tuple[float, float, float]]] = None) -> Wire:
    """创建样条曲线并返回线
    
    Args:
        points: 控制点坐标列表
        tangents: 可选的切线向量列表
        
    Returns:
        创建的样条曲线线
    """
    try:
        edge = make_spline_redge(points, tangents)
        cq_wire = cq.Wire.assembleEdges([edge.cq_edge])
        return Wire(cq_wire)
    except Exception as e:
        raise ValueError(f"创建样条曲线线失败: {e}")


def make_polyline_redge(points: List[Tuple[float, float, float]],
                        closed: bool = False) -> Edge:
    """创建多段线并返回边（仅适用于两点间的单段）
    
    Args:
        points: 顶点坐标列表
        closed: 是否闭合
        
    Returns:
        创建的多段线边
        
    Raises:
        ValueError: 当参数无效时
    """
    try:
        if len(points) < 2:
            raise ValueError("至少需要2个点")
        if len(points) > 2:
            raise ValueError("Edge类型只支持两点间的线段，多点请使用make_polyline_rwire")
            
        cs = get_current_cs()
        start_global = cs.transform_point(np.array(points[0]))
        end_global = cs.transform_point(np.array(points[1]))
        
        start_vec = Vector(*start_global)
        end_vec = Vector(*end_global)
        
        cq_edge = cq.Edge.makeLine(start_vec, end_vec)
        return Edge(cq_edge)
    except Exception as e:
        raise ValueError(f"创建多段线边失败: {e}. 请检查点坐标是否有效。")


def make_polyline_rwire(points: List[Tuple[float, float, float]],
                        closed: bool = False) -> Wire:
    """创建多段线并返回线
    
    Args:
        points: 顶点坐标列表
        closed: 是否闭合
        
    Returns:
        创建的多段线
        
    Raises:
        ValueError: 当参数无效时
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
        return Wire(cq_wire)
    except Exception as e:
        raise ValueError(f"创建多段线失败: {e}. 请检查点坐标是否有效。")


def make_helix_redge(pitch: float,
                     height: float,
                     radius: float,
                     center: Tuple[float, float, float] = (0, 0, 0),
                     dir: Tuple[float, float, float] = (0, 0, 1)) -> Edge:
    """创建螺旋线并返回边
    
    Args:
        pitch: 螺距
        height: 总高度
        radius: 螺旋半径
        center: 螺旋中心
        dir: 螺旋轴方向
        
    Returns:
        创建的螺旋线边
        
    Raises:
        ValueError: 当参数无效时
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


def make_helix_rwire(pitch: float,
                     height: float,
                     radius: float,
                     center: Tuple[float, float, float] = (0, 0, 0),
                     dir: Tuple[float, float, float] = (0, 0, 1)) -> Wire:
    """创建螺旋线并返回线
    
    Args:
        pitch: 螺距
        height: 总高度
        radius: 螺旋半径
        center: 螺旋中心
        dir: 螺旋轴方向
        
    Returns:
        创建的螺旋线
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
    """平移几何体
    
    Args:
        shape: 要平移的几何体
        vector: 平移向量
        
    Returns:
        平移后的几何体
        
    Raises:
        ValueError: 当参数无效时
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
        elif isinstance(shape, Shell):
            new_cq_shape = shape.cq_shell.translate(translation_vec)
            new_shape = Shell(new_cq_shape)
        elif isinstance(shape, Solid):
            new_cq_shape = shape.cq_solid.translate(translation_vec)
            new_shape = Solid(new_cq_shape)
        elif isinstance(shape, Compound):
            new_cq_shape = shape.cq_compound.translate(translation_vec)
            new_shape = Compound(new_cq_shape)
        else:
            raise ValueError(f"不支持的几何体类型: {type(shape)}")
        
        # 复制标签和元数据
        new_shape._tags = shape._tags.copy()
        new_shape._metadata = shape._metadata.copy()
        
        return new_shape
    except Exception as e:
        raise ValueError(f"平移几何体失败: {e}. 请检查几何体和平移向量是否有效。")


def rotate_shape(shape: AnyShape, 
                 angle: float,
                 axis: Tuple[float, float, float] = (0, 0, 1),
                 origin: Tuple[float, float, float] = (0, 0, 0)) -> AnyShape:
    """旋转几何体
    
    Args:
        shape: 要旋转的几何体
        angle: 旋转角度（弧度）
        axis: 旋转轴向量
        origin: 旋转中心点
        
    Returns:
        旋转后的几何体
        
    Raises:
        ValueError: 当参数无效时
    """
    try:
        cs = get_current_cs()
        global_axis = cs.transform_point(np.array(axis)) - cs.origin
        global_origin = cs.transform_point(np.array(origin))
        
        axis_vec = Vector(*global_axis)
        origin_vec = Vector(*global_origin)
        
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
        elif isinstance(shape, Shell):
            new_cq_shape = shape.cq_shell.rotate(origin_vec, axis_vec, angle)
            new_shape = Shell(new_cq_shape)
        elif isinstance(shape, Solid):
            new_cq_shape = shape.cq_solid.rotate(origin_vec, axis_vec, angle)
            new_shape = Solid(new_cq_shape)
        elif isinstance(shape, Compound):
            new_cq_shape = shape.cq_compound.rotate(origin_vec, axis_vec, angle)
            new_shape = Compound(new_cq_shape)
        else:
            raise ValueError(f"不支持的几何体类型: {type(shape)}")
        
        # 复制标签和元数据
        new_shape._tags = shape._tags.copy()
        new_shape._metadata = shape._metadata.copy()
        
        return new_shape
    except Exception as e:
        raise ValueError(f"旋转几何体失败: {e}. 请检查几何体、角度、轴向和中心点是否有效。")


# =============================================================================
# 3D操作函数
# =============================================================================

def extrude_rsolid(profile: Union[Wire, Face], 
                   direction: Tuple[float, float, float],
                   distance: float) -> Solid:
    """拉伸轮廓创建实体
    
    Args:
        profile: 要拉伸的轮廓（线或面）
        direction: 拉伸方向
        distance: 拉伸距离
        
    Returns:
        拉伸后的实体
        
    Raises:
        ValueError: 当参数无效时
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
                raise ValueError("拉伸的线必须是闭合的")
        elif isinstance(profile, Face):
            face = profile
        else:
            raise ValueError("只能拉伸线或面")
        
        # 使用CADQuery的Solid.extrudeLinear方法
        cq_solid = cq.Solid.extrudeLinear(face.cq_face, direction_vec)
        solid = Solid(cq_solid)
        
        # 复制标签和元数据
        solid._tags = profile._tags.copy()
        solid._metadata = profile._metadata.copy()
        
        return solid
    except Exception as e:
        raise ValueError(f"拉伸失败: {e}. 请检查轮廓、方向和距离是否有效。")


def revolve_rsolid(profile: Union[Wire, Face],
                   axis: Tuple[float, float, float] = (0, 0, 1),
                   angle: float = 2 * np.pi,
                   origin: Tuple[float, float, float] = (0, 0, 0)) -> Solid:
    """旋转轮廓创建实体
    
    Args:
        profile: 要旋转的轮廓（线或面）
        axis: 旋转轴向量
        angle: 旋转角度（弧度）
        origin: 旋转中心点
        
    Returns:
        旋转后的实体
        
    Raises:
        ValueError: 当参数无效时
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
        
        # 使用CADQuery的Workplane方法进行旋转
        # 将角度转换为度数
        angle_degrees = angle * 180 / np.pi
        
        # 创建一个临时的Workplane，添加面，然后旋转
        wp = cq.Workplane("XY")
        wp.objects = [face.cq_face]
        
        # 执行旋转
        revolved_wp = wp.revolve(angleDegrees=angle_degrees)
        cq_solid = revolved_wp.val()
        
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

def union_rsolid(solid1: Solid, solid2: Solid) -> Solid:
    """实体并集运算
    
    Args:
        solid1: 第一个实体
        solid2: 第二个实体
        
    Returns:
        并集结果实体
        
    Raises:
        ValueError: 当运算失败时
    """
    try:
        cq_result = solid1.cq_solid.fuse(solid2.cq_solid)
        # 确保结果是Solid类型
        if hasattr(cq_result, 'Solids') and cq_result.Solids():
            cq_result = cq_result.Solids()[0]
        result = Solid(cq_result)
        
        # 合并标签和元数据
        result._tags = solid1._tags.union(solid2._tags)
        result._metadata = {**solid1._metadata, **solid2._metadata}
        
        return result
    except Exception as e:
        raise ValueError(f"并集运算失败: {e}. 请检查两个实体是否有效。")


def cut_rsolid(solid1: Solid, solid2: Solid) -> Solid:
    """实体差集运算
    
    Args:
        solid1: 被减实体
        solid2: 减去的实体
        
    Returns:
        差集结果实体
        
    Raises:
        ValueError: 当运算失败时
    """
    try:
        cq_result = solid1.cq_solid.cut(solid2.cq_solid)
        # 确保结果是Solid类型
        if hasattr(cq_result, 'Solids') and cq_result.Solids():
            cq_result = cq_result.Solids()[0]
        result = Solid(cq_result)
        
        # 保留第一个实体的标签和元数据
        result._tags = solid1._tags.copy()
        result._metadata = solid1._metadata.copy()
        
        return result
    except Exception as e:
        raise ValueError(f"差集运算失败: {e}. 请检查两个实体是否有效。")


def intersect_rsolid(solid1: Solid, solid2: Solid) -> Solid:
    """实体交集运算
    
    Args:
        solid1: 第一个实体
        solid2: 第二个实体
        
    Returns:
        交集结果实体
        
    Raises:
        ValueError: 当运算失败时
    """
    try:
        cq_result = solid1.cq_solid.intersect(solid2.cq_solid)
        # 确保结果是Solid类型
        if hasattr(cq_result, 'Solids') and cq_result.Solids():
            cq_result = cq_result.Solids()[0]
        result = Solid(cq_result)
        
        # 合并标签和元数据
        result._tags = solid1._tags.intersection(solid2._tags)
        result._metadata = {**solid1._metadata, **solid2._metadata}
        
        return result
    except Exception as e:
        raise ValueError(f"交集运算失败: {e}. 请检查两个实体是否有效。")


# =============================================================================
# 导出函数
# =============================================================================

def export_step(shapes: Union[AnyShape, List[AnyShape]], filename: str) -> None:
    """导出为STEP格式
    
    Args:
        shapes: 要导出的几何体或几何体列表
        filename: 输出文件名
        
    Raises:
        ValueError: 当导出失败时
    """
    try:
        if not isinstance(shapes, list):
            shapes = [shapes]
        
        # 创建CADQuery的Workplane并添加所有几何体
        wp = cq.Workplane()
        for shape in shapes:
            if isinstance(shape, Solid):
                wp = wp.add(shape.cq_solid)
            elif isinstance(shape, Face):
                wp = wp.add(shape.cq_face)
            elif isinstance(shape, Shell):
                wp = wp.add(shape.cq_shell)
            elif isinstance(shape, Wire):
                wp = wp.add(shape.cq_wire)
            elif isinstance(shape, Edge):
                wp = wp.add(shape.cq_edge)
            elif isinstance(shape, Vertex):
                wp = wp.add(shape.cq_vertex)
            elif isinstance(shape, Compound):
                # 处理复合体：将其中的所有几何体添加到工作平面
                solids = shape.get_solids()
                for solid in solids:
                    wp = wp.add(solid.cq_solid)
                # 注意：复合体可能还包含其他类型的几何体，但这里先只处理实体
        
        # 导出到STEP文件
        cq.exporters.export(wp, filename)
    except Exception as e:
        raise ValueError(f"导出STEP文件失败: {e}. 请检查几何体和文件名是否有效。")


def export_stl(shapes: Union[AnyShape, List[AnyShape]], filename: str) -> None:
    """导出为STL格式
    
    Args:
        shapes: 要导出的几何体或几何体列表
        filename: 输出文件名
        
    Raises:
        ValueError: 当导出失败时
    """
    try:
        if not isinstance(shapes, list):
            shapes = [shapes]
        
        # 创建CADQuery的Workplane并添加所有几何体
        wp = cq.Workplane()
        for shape in shapes:
            if isinstance(shape, Solid):
                wp = wp.add(shape.cq_solid)
            elif isinstance(shape, Face):
                wp = wp.add(shape.cq_face)
            elif isinstance(shape, Shell):
                wp = wp.add(shape.cq_shell)
            elif isinstance(shape, Compound):
                # 处理复合体：将其中的所有实体和面添加到工作平面
                solids = shape.get_solids()
                for solid in solids:
                    wp = wp.add(solid.cq_solid)
            # STL只支持实体和面
        
        # 导出到STL文件
        cq.exporters.export(wp, filename)
    except Exception as e:
        raise ValueError(f"导出STL文件失败: {e}. 请检查几何体和文件名是否有效。")


# =============================================================================
# 高级特征操作函数
# =============================================================================

def fillet_rsolid(solid: Solid, edges: List[Edge], radius: float) -> Solid:
    """对实体的边进行圆角操作
    
    Args:
        solid: 要进行圆角的实体
        edges: 要圆角的边列表
        radius: 圆角半径
        
    Returns:
        圆角后的实体
        
    Raises:
        ValueError: 当操作失败时
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
        solid: 要进行倒角的实体
        edges: 要倒角的边列表
        distance: 倒角距离
        
    Returns:
        倒角后的实体
        
    Raises:
        ValueError: 当操作失败时
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
    """对实体进行抽壳操作
    
    Args:
        solid: 要抽壳的实体
        faces_to_remove: 要移除的面列表
        thickness: 壁厚
        
    Returns:
        抽壳后的实体
        
    Raises:
        ValueError: 当操作失败时
    """
    try:
        if thickness <= 0:
            raise ValueError("壁厚必须大于0")
        
        # 转换为CADQuery面对象
        cq_faces = [face.cq_face for face in faces_to_remove] if faces_to_remove else None
        
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
        profiles: 轮廓线列表
        ruled: 是否为直纹面
        
    Returns:
        放样后的实体
        
    Raises:
        ValueError: 当操作失败时
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


def sweep_rsolid(profile: Face, path: Wire, 
                 make_solid: bool = True,
                 is_frenet: bool = False) -> Union[Solid, Shell]:
    """沿路径扫掠轮廓创建实体
    
    Args:
        profile: 要扫掠的轮廓
        path: 扫掠路径
        make_solid: 是否创建实体（否则创建壳）
        is_frenet: 是否使用Frenet框架
        
    Returns:
        扫掠后的实体或壳
        
    Raises:
        ValueError: 当操作失败时
    """
    try:
        # 执行扫掠操作
        cq_result = cq.Solid.sweep(profile.cq_face, path.cq_wire, 
                                   makeSolid=make_solid, isFrenet=is_frenet)
        
        if make_solid:
            result = Solid(cq_result)
        else:
            # 如果不是实体，则创建Shell
            result = Shell(cq_result)
        
        # 合并轮廓和路径的标签和元数据
        result._tags = profile._tags.union(path._tags)
        result._metadata = {**profile._metadata, **path._metadata}
        
        return result
    except Exception as e:
        raise ValueError(f"扫掠操作失败: {e}. 请检查轮廓和路径是否有效。")


def linear_pattern_rcompound(shape: AnyShape, 
                             direction: Tuple[float, float, float],
                             count: int,
                             spacing: float) -> Compound:
    """创建线性阵列
    
    Args:
        shape: 要阵列的几何体
        direction: 阵列方向
        count: 阵列数量
        spacing: 阵列间距
        
    Returns:
        阵列后的复合体
        
    Raises:
        ValueError: 当参数无效时
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
        
        # 创建复合体
        if isinstance(shape, Vertex):
            cq_shapes = [s.cq_vertex for s in shapes]
        elif isinstance(shape, Edge):
            cq_shapes = [s.cq_edge for s in shapes]
        elif isinstance(shape, Wire):
            cq_shapes = [s.cq_wire for s in shapes]
        elif isinstance(shape, Face):
            cq_shapes = [s.cq_face for s in shapes]
        elif isinstance(shape, Shell):
            cq_shapes = [s.cq_shell for s in shapes]
        elif isinstance(shape, Solid):
            cq_shapes = [s.cq_solid for s in shapes]
        else:
            raise ValueError(f"不支持的几何体类型: {type(shape)}")
        
        cq_compound = cq.Compound.makeCompound(cq_shapes)
        result = Compound(cq_compound)
        
        # 复制原始形状的标签和元数据
        result._tags = shape._tags.copy()
        result._metadata = shape._metadata.copy()
        result.add_tag("linear_pattern")
        
        return result
    except Exception as e:
        raise ValueError(f"线性阵列失败: {e}. 请检查参数是否有效。")


def radial_pattern_rcompound(shape: AnyShape,
                             center: Tuple[float, float, float],
                             axis: Tuple[float, float, float],
                             count: int,
                             angle: float) -> Compound:
    """创建径向阵列
    
    Args:
        shape: 要阵列的几何体
        center: 旋转中心
        axis: 旋转轴
        count: 阵列数量
        angle: 总角度（弧度）
        
    Returns:
        阵列后的复合体
        
    Raises:
        ValueError: 当参数无效时
    """
    try:
        if count <= 0:
            raise ValueError("阵列数量必须大于0")
        if angle <= 0:
            raise ValueError("角度必须大于0")
        
        shapes = []
        angle_step = angle / count  # 修正角度计算，均匀分布
        
        for i in range(count):
            rotation_angle = angle_step * i
            rotated_shape = rotate_shape(shape, rotation_angle, axis, center)
            shapes.append(rotated_shape)
        
        # 创建复合体
        if isinstance(shape, Vertex):
            cq_shapes = [s.cq_vertex for s in shapes]
        elif isinstance(shape, Edge):
            cq_shapes = [s.cq_edge for s in shapes]
        elif isinstance(shape, Wire):
            cq_shapes = [s.cq_wire for s in shapes]
        elif isinstance(shape, Face):
            cq_shapes = [s.cq_face for s in shapes]
        elif isinstance(shape, Shell):
            cq_shapes = [s.cq_shell for s in shapes]
        elif isinstance(shape, Solid):
            cq_shapes = [s.cq_solid for s in shapes]
        else:
            raise ValueError(f"不支持的几何体类型: {type(shape)}")
        
        cq_compound = cq.Compound.makeCompound(cq_shapes)
        result = Compound(cq_compound)
        
        # 复制原始形状的标签和元数据
        result._tags = shape._tags.copy()
        result._metadata = shape._metadata.copy()
        result.add_tag("radial_pattern")
        
        return result
    except Exception as e:
        raise ValueError(f"径向阵列失败: {e}. 请检查参数是否有效。")


def mirror_shape(shape: AnyShape, 
                 plane_origin: Tuple[float, float, float],
                 plane_normal: Tuple[float, float, float]) -> AnyShape:
    """镜像几何体
    
    Args:
        shape: 要镜像的几何体
        plane_origin: 镜像平面原点
        plane_normal: 镜像平面法向量
        
    Returns:
        镜像后的几何体
        
    Raises:
        ValueError: 当参数无效时
    """
    try:
        cs = get_current_cs()
        global_origin = cs.transform_point(np.array(plane_origin))
        global_normal = cs.transform_vector(np.array(plane_normal))
        
        # 确保法向量不是零向量
        if np.linalg.norm(global_normal) < 1e-10:
            raise ValueError("镜像平面法向量不能是零向量")
        
        # 坐标系转换：SimpleCAD (X前,Y右,Z上) -> CadQuery (X右,Y上,Z前)
        cq_origin = Vector(global_origin[1], global_origin[2], global_origin[0])
        cq_normal = Vector(global_normal[1], global_normal[2], global_normal[0])
        
        # 创建镜像平面
        mirror_plane = Plane(origin=cq_origin, normal=cq_normal)
        
        # 使用Workplane进行镜像操作
        if isinstance(shape, Solid):
            # 对于Solid，创建一个包含该Solid的Workplane
            wp = cq.Workplane().add(shape.cq_solid)
            
            # 根据法向量确定镜像平面
            abs_normal = np.abs(cq_normal.toTuple())
            max_idx = np.argmax(abs_normal)
            
            if max_idx == 0:  # X方向
                mirror_plane_str = "YZ"
            elif max_idx == 1:  # Y方向
                mirror_plane_str = "XZ"
            else:  # Z方向
                mirror_plane_str = "XY"
            
            # 执行镜像
            mirrored_wp = wp.mirror(mirror_plane_str, basePointVector=cq_origin.toTuple())
            
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


def helical_sweep_rsolid(profile: Wire,
                         pitch: float,
                         height: float,
                         radius: float,
                         center: Tuple[float, float, float] = (0, 0, 0),
                         dir: Tuple[float, float, float] = (0, 0, 1)) -> Solid:
    """沿螺旋路径扫掠轮廓创建实体
    
    Args:
        profile: 要扫掠的轮廓
        pitch: 螺距
        height: 总高度
        radius: 螺旋半径
        center: 螺旋中心
        dir: 螺旋轴方向
        
    Returns:
        螺旋扫掠后的实体
        
    Raises:
        ValueError: 当参数无效时
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
        
        # 创建螺旋路径
        helix = cq.Wire.makeHelix(pitch, height, radius, center_vec, dir_vec)
        
        # 将Wire转换为Face用于扫掠
        try:
            profile_face = cq.Face.makeFromWires(profile.cq_wire)
        except:
            raise ValueError("螺旋扫掠轮廓必须是闭合的")
        
        # 沿螺旋路径扫掠
        cq_result = cq.Solid.sweep(profile_face, helix, makeSolid=True)
        result = Solid(cq_result)
        
        # 复制轮廓的标签和元数据
        result._tags = profile._tags.copy()
        result._metadata = profile._metadata.copy()
        result.add_tag("helical_sweep")
        
        return result
    except Exception as e:
        raise ValueError(f"螺旋扫掠失败: {e}. 请检查参数是否有效。")
