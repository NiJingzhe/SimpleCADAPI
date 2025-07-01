"""
SimpleCAD API操作函数
使用更直接的CADQuery API调用
"""

from typing import List, Tuple, Optional, Literal
import math
import numpy as np
import cadquery as cq
import os
from .core import Point, Line, Sketch, Body, get_current_cs


# ===== 基础构造操作 =====

def make_point(x: float, y: float, z: float) -> Point:
    """在当前坐标系中创建点"""
    return Point((x, y, z), get_current_cs())


def make_line(points: List[Point], line_type: str = "segment") -> Line:
    """创建曲线（线段/圆弧/样条）"""
    return Line(points, line_type)

def make_segment(p1: Point, p2: Point) -> Line:
    """创建线段"""
    return Line([p1, p2], "segment")

def make_three_point_arc(p1: Point, p2: Point, p3: Point) -> Line:
    """创建圆弧"""
    return Line([p1, p2, p3], "arc")

def make_angle_arc(center: Point, radius: float, start_angle: float, end_angle: float) -> Line:
    """创建角度圆弧"""
    start_point = make_point(
        center.local_coords[0] + radius * math.cos(start_angle),
        center.local_coords[1] + radius * math.sin(start_angle),
        center.local_coords[2]
    )
    end_point = make_point(
        center.local_coords[0] + radius * math.cos(end_angle),
        center.local_coords[1] + radius * math.sin(end_angle),
        center.local_coords[2]
    )
    return Line([center, start_point, end_point], "arc")

def make_spline(points: List[Point]) -> Line:
    """创建样条曲线"""
    if len(points) < 2:
        raise ValueError("样条曲线至少需要2个控制点")
    return Line(points, "spline")


def make_sketch(lines: List[Line]) -> Sketch:
    """创建闭合草图"""
    return Sketch(lines)


def make_rectangle(width: float, height: float, center: bool = True) -> Sketch:
    """创建矩形草图"""
    if center:
        x1, y1 = -width/2, -height/2
        x2, y2 = width/2, height/2
    else:
        x1, y1 = 0, 0
        x2, y2 = width, height
    
    # 创建四个角点
    p1 = make_point(x1, y1, 0)
    p2 = make_point(x2, y1, 0)
    p3 = make_point(x2, y2, 0)
    p4 = make_point(x1, y2, 0)
    
    # 创建四条边
    lines = [
        make_line([p1, p2], "segment"),
        make_line([p2, p3], "segment"),
        make_line([p3, p4], "segment"),
        make_line([p4, p1], "segment")
    ]
    
    return make_sketch(lines)


def make_circle(radius: float, center_point: Optional[Point] = None) -> Sketch:
    """创建圆形草图"""
    if center_point is None:
        center_point = make_point(0, 0, 0)
    
    # 创建16边形近似圆
    points = []
    n_sides = 16
    
    cx, cy, cz = center_point.local_coords
    for i in range(n_sides):
        angle = 2 * math.pi * i / n_sides
        x = cx + radius * math.cos(angle)
        y = cy + radius * math.sin(angle)
        points.append(make_point(x, y, cz))
    
    # 创建线段
    lines = []
    for i in range(n_sides):
        p1 = points[i]
        p2 = points[(i + 1) % n_sides]
        lines.append(make_line([p1, p2], "segment"))
    
    return make_sketch(lines)

def make_triangle(p1: Point, p2: Point, p3: Point) -> Sketch:
    """创建三角形草图"""
    lines = [
        make_segment(p1, p2),
        make_segment(p2, p3),
        make_segment(p3, p1)
    ]
    return make_sketch(lines)

def make_ellipse(center: Point, major_axis: float, minor_axis: float, rotation: float = 0) -> Sketch:
    """创建椭圆草图"""
    # 椭圆近似为多边形
    n_sides = 32  # 较高的边数以提高精度
    points = []
    
    cx, cy, cz = center.local_coords
    for i in range(n_sides):
        angle = 2 * math.pi * i / n_sides + rotation
        x = cx + (major_axis / 2) * math.cos(angle)
        y = cy + (minor_axis / 2) * math.sin(angle)
        points.append(make_point(x, y, cz))
    
    # 创建线段
    lines = []
    for i in range(n_sides):
        p1 = points[i]
        p2 = points[(i + 1) % n_sides]
        lines.append(make_line([p1, p2], "segment"))

    return make_sketch(lines)


# ===== 三维建模操作 =====

def extrude(sketch: Sketch, 
            distance: Optional[float] = None) -> Body:
    """拉伸操作"""
    if distance is None:
        raise ValueError("必须指定拉伸距离")

    try:
        # 使用草图的工作平面进行拉伸
        wp = sketch.get_workplane()
        wire = sketch.to_cq_wire()
        
        # 在正确的工作平面上创建面并拉伸
        result = wp.add(wire).toPending().extrude(distance)
        
        if result.solids().size() > 0:
            return Body(result)
        else:
            raise ValueError("拉伸未产生有效实体")
        
            
    except Exception as e:
        raise ValueError(f"拉伸操作失败: {e}")


def revolve(sketch: Sketch, 
            axis_start: Point, 
            axis_end: Point, 
            angle: float) -> Body:
    """旋转操作"""
    try:
        wire = sketch.to_cq_wire()
        face = cq.Face.makeFromWires(wire)
        
        # 计算旋转轴
        axis_vec = axis_end.to_cq_vector().sub(axis_start.to_cq_vector())
        
        # 使用Workplane方式旋转
        wp = cq.Workplane().add(face)
        result = wp.revolve(angle * 180 / math.pi, axis_start.to_cq_vector(), axis_vec)
        
        if result.solids().size() > 0:
            return Body(result)
        else:
            raise ValueError("旋转未产生有效实体")
            
    except Exception as e:
        raise ValueError(f"旋转操作失败: {e}")


def loft(sketches: List[Sketch]) -> Body:
    """放样操作"""
    if len(sketches) < 2:
        raise ValueError("放样操作至少需要2个草图")
    
    try:
        wires = [sketch.to_cq_wire() for sketch in sketches]
        solid = cq.Solid.makeLoft(wires)
        # 统一返回Workplane对象
        wp = cq.Workplane().newObject([solid])
        return Body(wp)
    except Exception as e:
        raise ValueError(f"放样操作失败: {e}")


def sweep(profile: Sketch, path: Line, use_frenet: bool = False) -> Body:
    """扫掠操作
    
    Args:
        profile: 截面草图
        path: 扫掠路径
        use_frenet: 是否使用Frenet框架（用于螺旋扫掠等复杂路径）
    """
    try:
        profile_wire = profile.to_cq_wire()
        profile_face = cq.Face.makeFromWires(profile_wire)
        path_edge = path.to_cq_edge()
        
        if path_edge is None:
            raise ValueError("无法创建路径边")
        
        path_wire = cq.Wire.assembleEdges([path_edge])
        
        # 使用Workplane方式扫掠
        wp = cq.Workplane().add(profile_face)
        
        # 对于螺旋路径或复杂路径，使用isFrenet=True
        if use_frenet:
            result = wp.sweep(path_wire, isFrenet=True)
        else:
            result = wp.sweep(path_wire)
        
        if result.solids().size() > 0:
            return Body(result)
        else:
            raise ValueError("扫掠未产生有效实体")
            
    except Exception as e:
        raise ValueError(f"扫掠操作失败: {e}")


def shell(body: Body, thickness: float, face_tags: Optional[List[str]] = None) -> Body:
    """抽壳操作
    
    Args:
        body: 要抽壳的实体
        thickness: 壁厚
        face_tags: 要移除的面标签列表（这些面在抽壳后会被去掉，形成开口）
        
    Returns:
        抽壳后的实体
    """
    if not body.is_valid() or body.cq_solid is None:
        raise ValueError("输入实体无效")
    
    try:
        # 获取Workplane对象
        wp = body.cq_solid if hasattr(body.cq_solid, 'shell') else cq.Workplane().add(body.cq_solid)
        
        if face_tags is None or len(face_tags) == 0:
            # 标准抽壳，所有面都保留
            result = wp.shell(thickness)
        else:
            # 选择性抽壳，指定的面会被移除
            faces_to_remove = select_face_by_tag(body, face_tags)
            if not faces_to_remove:
                raise ValueError(f"未找到指定标签的面: {face_tags}")
            
            # 使用面选择器来抽壳
            # 先选择要移除的面，然后抽壳
            result = _shell_with_face_removal(wp, faces_to_remove, thickness)
        
        return Body(result)
    except Exception as e:
        raise ValueError(f"抽壳操作失败: {e}")


def _shell_with_face_removal(workplane, faces_to_remove, thickness):
    """带面移除的抽壳操作
    
    Args:
        workplane: CADQuery Workplane对象
        faces_to_remove: 要移除的面对象列表
        thickness: 壁厚
        
    Returns:
        抽壳后的Workplane对象
    """
    try:
        # 方法1：使用lambda选择器
        def face_filter(face):
            return face in faces_to_remove
        
        # 尝试使用lambda选择器
        selected_wp = workplane.faces(lambda obj: obj in faces_to_remove)
        result = selected_wp.shell(thickness)
        return result
        
    except Exception as e1:
        try:
            # 方法2：使用字符串选择器组合
            # 分析要移除的面的位置，生成字符串选择器
            face_selectors = []
            for face in faces_to_remove:
                try:
                    normal = face.normalAt()
                    
                    # 直接使用CADQuery坐标系的法向量生成选择器
                    # 不需要转换，因为CADQuery的选择器就是基于CADQuery坐标系的
                    if abs(normal.z) > 0.9:  # Z方向面
                        if normal.z > 0:
                            face_selectors.append("+Z")
                        else:
                            face_selectors.append("-Z")
                    elif abs(normal.y) > 0.9:  # Y方向面
                        if normal.y > 0:
                            face_selectors.append("+Y")
                        else:
                            face_selectors.append("-Y")
                    elif abs(normal.x) > 0.9:  # X方向面
                        if normal.x > 0:
                            face_selectors.append("+X")
                        else:
                            face_selectors.append("-X")
                except:
                    continue
            
            if face_selectors:
                # 组合选择器字符串
                selector_str = " or ".join(face_selectors)
                selected_wp = workplane.faces(selector_str)
                result = selected_wp.shell(thickness)
                return result
            else:
                raise ValueError("无法创建面选择器")
                
        except Exception as e2:
            # 方法3：使用索引选择
            try:
                # 获取所有面
                all_faces_wp = workplane.faces()
                all_faces = all_faces_wp.all()
                
                # 找到要移除面的索引
                indices_to_remove = []
                for i, face_wp in enumerate(all_faces):
                    face_obj = face_wp.val() if hasattr(face_wp, 'val') else face_wp
                    if face_obj in faces_to_remove:
                        indices_to_remove.append(i)
                
                if indices_to_remove:
                    # 使用索引选择面
                    if len(indices_to_remove) == 1:
                        selected_wp = workplane.faces().vals()[indices_to_remove[0]]
                        result = cq.Workplane().add(selected_wp).shell(thickness)
                    else:
                        # 多个面的情况
                        result = workplane
                        for idx in indices_to_remove:
                            face_wp = workplane.faces().vals()[idx]
                            temp_wp = cq.Workplane().add(face_wp)
                            if hasattr(temp_wp, 'shell'):
                                result = temp_wp.shell(thickness)
                            break  # 暂时只处理第一个面
                    return result
                else:
                    raise ValueError("找不到匹配的面索引")
                    
            except Exception as e3:
                raise ValueError(f"所有面选择方法都失败了: {e1}, {e2}, {e3}")


def fillet(body: Body, edges: List[Line], radius: float) -> Body:
    """圆角操作"""
    if not body.is_valid() or body.cq_solid is None:
        raise ValueError("输入实体无效")
    
    try:
        # 获取Workplane对象
        wp = body.cq_solid if hasattr(body.cq_solid, 'fillet') else cq.Workplane().add(body.cq_solid)
        result = wp.fillet(radius)
        return Body(result)
    except Exception as e:
        raise ValueError(f"圆角操作失败: {e}")


def chamfer(body: Body, edges: List[Line], distance: float) -> Body:
    """倒角操作"""
    if not body.is_valid() or body.cq_solid is None:
        raise ValueError("输入实体无效")
    
    try:
        # 获取Workplane对象
        wp = body.cq_solid if hasattr(body.cq_solid, 'chamfer') else cq.Workplane().add(body.cq_solid)
        result = wp.chamfer(distance)
        return Body(result)
    except Exception as e:
        raise ValueError(f"倒角操作失败: {e}")


# ===== 布尔运算 =====

def cut(target: Body, tool: Body) -> Body:
    """布尔减运算"""
    if not target.is_valid() or not tool.is_valid() or target.cq_solid is None or tool.cq_solid is None:
        raise ValueError("输入实体无效")
    
    try:
        # 确保使用Workplane对象
        target_wp = target.cq_solid if hasattr(target.cq_solid, 'cut') else cq.Workplane().add(target.cq_solid)
        tool_wp = tool.cq_solid if hasattr(tool.cq_solid, 'cut') else cq.Workplane().add(tool.cq_solid)
        
        result = target_wp.cut(tool_wp)
        return Body(result)
            
    except Exception as e:
        raise ValueError(f"布尔减运算失败: {e}")


def union(body1: Body, body2: Body) -> Body:
    """布尔并运算"""
    # 类型检查
    if not isinstance(body1, Body):
        raise ValueError(f"第一个参数必须是Body对象，实际为: {type(body1)}")
    if not isinstance(body2, Body):
        raise ValueError(f"第二个参数必须是Body对象，实际为: {type(body2)}")
    
    if not body1.is_valid() or not body2.is_valid() or body1.cq_solid is None or body2.cq_solid is None:
        raise ValueError("输入实体无效")
    
    try:
        # 确保使用Workplane对象
        body1_wp = body1.cq_solid if hasattr(body1.cq_solid, 'union') else cq.Workplane().add(body1.cq_solid)
        body2_wp = body2.cq_solid if hasattr(body2.cq_solid, 'union') else cq.Workplane().add(body2.cq_solid)
        
        result = body1_wp.union(body2_wp)
        return Body(result)
            
    except Exception as e:
        raise ValueError(f"布尔并运算失败: {e}")


def intersect(body1: Body, body2: Body) -> Body:
    """布尔交运算"""
    if not body1.is_valid() or not body2.is_valid() or body1.cq_solid is None or body2.cq_solid is None:
        raise ValueError("输入实体无效")
    
    try:
        # 确保使用Workplane对象
        body1_wp = body1.cq_solid if hasattr(body1.cq_solid, 'intersect') else cq.Workplane().add(body1.cq_solid)
        body2_wp = body2.cq_solid if hasattr(body2.cq_solid, 'intersect') else cq.Workplane().add(body2.cq_solid)
        
        result = body1_wp.intersect(body2_wp)
        return Body(result)
            
    except Exception as e:
        raise ValueError(f"布尔交运算失败: {e}")


# ===== 便利函数 =====

def make_box(width: float, height: float, depth: float, center: bool = True) -> Body:
    """创建立方体"""
    try:
        # 获取当前坐标系
        current_cs = get_current_cs()
        
        if center:
            result = cq.Workplane(current_cs.to_cq_plane()).box(width, height, depth)
        else:
            # 非中心对齐的立方体
            result = cq.Workplane(current_cs.to_cq_plane()).center(width/2, height/2).box(width, height, depth).translate((0, 0, depth/2))
        
        if result.solids().size() > 0:
            body = Body(result)
            # 自动添加面标签
            body.auto_tag_faces("box")
            return body
        else:
            raise ValueError("创建立方体失败")
    except Exception as e:
        raise ValueError(f"创建立方体失败: {e}")


def make_cylinder(radius: float, height: float) -> Body:
    """创建圆柱体"""
    try:
        # 获取当前坐标系
        current_cs = get_current_cs()
        
        result = cq.Workplane(current_cs.to_cq_plane()).cylinder(height, radius)
        
        if result.solids().size() > 0:
            body = Body(result)
            # 自动添加面标签
            body.auto_tag_faces("cylinder")
            return body
        else:
            raise ValueError("创建圆柱体失败")
    except Exception as e:
        raise ValueError(f"创建圆柱体失败: {e}")


def make_sphere(radius: float) -> Body:
    """创建球体"""
    try:
        # 获取当前坐标系
        current_cs = get_current_cs()
        
        result = cq.Workplane(current_cs.to_cq_plane()).sphere(radius)
        
        if result.solids().size() > 0:
            body = Body(result)
            # 自动添加面标签
            body.auto_tag_faces("sphere")
            return body
        else:
            raise ValueError("创建球体失败")
    except Exception as e:
        raise ValueError(f"创建球体失败: {e}")


# ===== 高级操作 =====

def make_linear_pattern(body: Body, 
                   direction: Tuple[float, float, float], 
                   count: int, 
                   spacing: float) -> Body:
    """线性阵列"""
    if not body.is_valid():
        raise ValueError("输入实体无效")
    
    if count < 1:
        raise ValueError("阵列数量必须大于0")
    
    try:
        # 获取第一个实体的Solid对象
        def get_solid(body):
            if hasattr(body.cq_solid, 'solids') and body.cq_solid.solids().size() > 0:
                return body.cq_solid.solids().first()
            elif hasattr(body.cq_solid, 'val'):
                return body.cq_solid.val()
            return body.cq_solid
        
        base_solid = get_solid(body)
        
        # 从第一个实体开始
        wp = cq.Workplane().newObject([base_solid])
        
        # 创建其他实体并合并
        for i in range(1, count):
            offset_x = direction[0] * spacing * i
            offset_y = direction[1] * spacing * i
            offset_z = direction[2] * spacing * i
            
            # 复制并平移实体
            translated = base_solid.translate(cq.Vector(offset_x, offset_z, offset_y))
            wp = wp.add(translated)
        
        if wp.solids().size() > 0:
            return Body(wp)
        else:
            raise ValueError("线性阵列未产生有效实体")
            
    except Exception as e:
        raise ValueError(f"线性阵列操作失败: {e}")


def make_2d_pattern(body: Body, 
               x_direction: Tuple[float, float, float], 
               y_direction: Tuple[float, float, float],
               x_count: int, 
               y_count: int,
               x_spacing: float, 
               y_spacing: float) -> Body:
    """2D阵列操作"""
    if not body.is_valid():
        raise ValueError("输入实体无效")
    
    if x_count < 1 or y_count < 1:
        raise ValueError("阵列数量必须大于0")
    
    try:
        # 获取基础实体的Solid对象
        def get_solid(body):
            if hasattr(body.cq_solid, 'solids') and body.cq_solid.solids().size() > 0:
                return body.cq_solid.solids().first()
            elif hasattr(body.cq_solid, 'val') and hasattr(body.cq_solid.val(), 'wrapped'):
                return body.cq_solid.val()
            elif hasattr(body.cq_solid, 'wrapped'):
                return body.cq_solid
            else:
                raise ValueError("无法从Body对象中提取Solid")
        
        base_solid = get_solid(body)
        
        # 收集所有实体
        all_solids = []
        
        # 创建2D网格阵列
        for j in range(y_count):
            for i in range(x_count):
                offset_x = x_direction[0] * x_spacing * i + y_direction[0] * y_spacing * j
                offset_y = x_direction[1] * x_spacing * i + y_direction[1] * y_spacing * j
                offset_z = x_direction[2] * x_spacing * i + y_direction[2] * y_spacing * j
                
                if i == 0 and j == 0:
                    # 第一个实体就是原始实体
                    all_solids.append(base_solid)
                else:
                    # 复制并平移实体
                    translated = base_solid.translate(cq.Vector(offset_x, offset_z, offset_y))
                    all_solids.append(translated)
        
        # 创建包含所有实体的Workplane
        wp = cq.Workplane()
        for solid in all_solids:
            wp = wp.add(solid)
        
        expected_count = x_count * y_count
        if wp.solids().size() == expected_count:
            return Body(wp)
        else:
            # 如果solids计数不对，尝试使用union合并所有实体
            result_wp = cq.Workplane().add(all_solids[0])
            for solid in all_solids[1:]:
                temp_wp = cq.Workplane().add(solid)
                result_wp = result_wp.union(temp_wp)
            
            return Body(result_wp)
            
    except Exception as e:
        raise ValueError(f"2D阵列操作失败: {e}")


def make_radial_pattern(body: Body, 
                   center: Point, 
                   axis: Tuple[float, float, float],
                   count: int, 
                   angle: float) -> Body:
    """径向/环形阵列操作"""
    if not body.is_valid():
        raise ValueError("输入实体无效")
    
    if count < 2:
        raise ValueError("阵列数量必须大于1")
    
    try:
        # 获取基础实体的Workplane
        base_wp = body.cq_solid
        
        # 收集所有实体，包括原始实体
        all_workplanes = [base_wp]
        
        # 创建径向阵列 - 正确的角度计算
        for i in range(1, count):
            # 对于完整圆形分布：每个实体旋转 angle * i / count
            # 对于部分扇形分布：每个实体旋转 angle * i / (count - 1)
            if abs(angle - 2 * math.pi) < 0.001:  # 完整圆形（360度）
                rotation_angle = angle * i / count
            else:  # 部分扇形
                rotation_angle = angle * i / (count - 1)
            
            # 旋转实体
            center_vec = center.to_cq_vector()
            axis_vec = cq.Vector(axis[0], axis[2], axis[1]).normalized()
            
            # 复制并旋转
            rotated_wp = base_wp.rotate(center_vec, axis_vec, math.degrees(rotation_angle))
            all_workplanes.append(rotated_wp)
        
        # 合并所有实体
        result = all_workplanes[0]
        for wp in all_workplanes[1:]:
            result = result.union(wp)
            
        return Body(result)
            
    except Exception as e:
        raise ValueError(f"径向阵列操作失败: {e}")


def export_step(body: Body, filename: str):
    """导出为STEP文件"""
    try:
        # 确保目录存在
        import os
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        from cadquery import exporters  
        
        exporters.export(
            body.cq_solid, 
            filename, 
            exportType='STEP'
        )
         
    except Exception as e:
        raise ValueError(f"STEP导出失败: {e}")


def export_stl(body: Body, filename: str, tolerance: float = 0.1):
    """导出为STL文件"""
    try:
        # 确保目录存在
        import os
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        from cadquery import exporters
        
        exporters.export(
            body.cq_solid, 
            filename, 
            exportType='STL', 
            tolerance=tolerance
        )
         
    except Exception as e:
        raise ValueError(f"STL导出失败: {e}")


def helical_sweep(profile: Sketch,
                          coil_radius: float, 
                          pitch: float, 
                          turns: float,
                          points_per_turn: int = 12,
                          smooth: bool = True) -> Body:
    """高级螺旋扫掠操作 - 可调节精度
    
    Args:
        profile: 扫掠截面草图
        coil_radius: 螺旋半径
        pitch: 螺距（每转上升的高度）
        turns: 圈数
        points_per_turn: 每圈的点数（6-32，默认12）
        smooth: 是否使用spline平滑（False使用polyline，更快但不够平滑）
    """
    import math
    
    try:
        # 限制点数量范围
        points_per_turn = max(6, min(32, points_per_turn))
        
        # 计算总长度
        length = int(turns * 2 * math.pi * points_per_turn)
        
        # 创建螺旋路径点（沿Z轴上升）
        pts = []
        for i in range(length):
            # 参数化螺旋：t从0到turns*2π
            t = i * turns * 2 * math.pi / length
            x = coil_radius * math.cos(t)
            y = coil_radius * math.sin(t)
            z = pitch * t / (2 * math.pi)  # Z方向上升
            pts.append([x, y, z])
        
        # 创建螺旋路径 - 可选平滑或直线
        if smooth:
            path = cq.Workplane("XY").spline(pts).wire()
        else:
            path = cq.Workplane("XY").polyline(pts).wire()
        
        # 使用给定的截面草图进行扫掠
        profile_wire = profile.to_cq_wire()
        profile_face = cq.Face.makeFromWires(profile_wire)
        
        # Profile在XY平面，移动到螺旋起始位置并扫掠
        wp = cq.Workplane("XY").add(profile_face).translate((coil_radius, 0, 0))
        result = wp.sweep(path, isFrenet=True)
        
        if result.solids().size() > 0:
            return Body(result)
        else:
            raise ValueError("高级螺旋扫掠未产生有效实体")
            
    except Exception as e:
        raise ValueError(f"高级螺旋扫掠操作失败: {e}")


# ===== 面选择操作 =====

def select_face_by_tag(body: Body, tags: List[str]):
    """根据标签选择面
    
    Args:
        body: 要选择面的实体
        tags: 要选择的面标签列表
        
    Returns:
        选中的面对象列表（CADQuery Face对象）
    """
    if not body.is_valid():
        raise ValueError("输入实体无效")
    
    selected_faces = []
    all_faces = body.get_all_faces()
    
    if not all_faces:
        return selected_faces
    
    # 遍历每个标签，收集对应的面
    for tag in tags:
        face_indices = body.get_faces_by_tag(tag)
        for index in face_indices:
            if 0 <= index < len(all_faces):
                face = all_faces[index]
                if face not in selected_faces:
                    selected_faces.append(face)
    
    return selected_faces


def create_workplane_from_face(body: Body, tag: str):
    """从标签面创建工作平面
    
    Args:
        body: 包含面的实体
        tag: 面标签
        
    Returns:
        CADQuery Workplane对象
    """
    if not body.is_valid():
        raise ValueError("输入实体无效")
    
    faces = select_face_by_tag(body, [tag])
    if not faces:
        raise ValueError(f"未找到标签为'{tag}'的面")
    
    # 使用第一个找到的面创建工作平面
    face = faces[0]
    try:
        # 直接从面创建工作平面
        wp = cq.Workplane().add(face)
        return wp
    except Exception as e:
        raise ValueError(f"创建工作平面失败: {e}")


def tag_faces_automatically(body: Body, geometry_type: str = "auto"):
    """自动为实体的面添加标签
    
    Args:
        body: 要添加标签的实体
        geometry_type: 几何体类型，'auto'表示自动检测
    """
    if not body.is_valid():
        raise ValueError("输入实体无效")
    
    if geometry_type == "auto":
        # 根据面数量自动判断几何体类型
        faces = body.get_all_faces()
        face_count = len(faces)
        
        if face_count == 6:
            geometry_type = "box"
        elif face_count == 3:
            geometry_type = "cylinder"
        elif face_count == 1:
            geometry_type = "sphere"
        else:
            # 复杂几何体，使用通用标记
            for i in range(face_count):
                body.tag_face(i, f"face_{i}")
            return
    
    body.auto_tag_faces(geometry_type)


def get_face_info(body: Body, tag: Optional[str] = None) -> dict:
    """获取面的信息
    
    Args:
        body: 实体对象
        tag: 面标签，None表示获取所有面信息
        
    Returns:
        面信息字典
    """
    if not body.is_valid():
        raise ValueError("输入实体无效")
    
    info = {
        "total_faces": len(body.get_all_faces()),
        "tagged_faces": {},
        "face_details": []
    }
    
    # 收集标签信息
    for face_tag, indices in body.face_tags.items():
        info["tagged_faces"][face_tag] = len(indices)
    
    # 如果指定了标签，返回该标签的详细信息
    if tag:
        faces = select_face_by_tag(body, [tag])
        for i, face in enumerate(faces):
            try:
                center = face.Center()
                normal = face.normalAt()
                area = face.Area()
                
                info["face_details"].append({
                    "index": i,
                    "tag": tag,
                    "center": (center.x, center.y, center.z),
                    "normal": (normal.x, normal.y, normal.z),
                    "area": area
                })
            except:
                info["face_details"].append({
                    "index": i,
                    "tag": tag,
                    "error": "无法获取面信息"
                })
    
    return info

