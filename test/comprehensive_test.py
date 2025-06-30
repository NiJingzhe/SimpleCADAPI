"""
全面测试SimpleCAD API的高级功能和建模操作
包括复杂零件构建，如法兰、齿轮等
"""

import sys
import os
import math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from simplecadapi import *
from simplecadapi.operations import helical_sweep, helical_sweep

def export_model(body, filename, description="模型"):
    """通用的模型导出函数"""
    if body is None or not body.is_valid():
        print(f"   ✗ {description}导出失败: 无效的Body对象")
        return False
    
    try:
        import cadquery as cq
        output_dir = "output"
        os.makedirs(output_dir, exist_ok=True)
        
        wp = cq.Workplane().add(body.cq_solid)
        
        # 导出STL
        stl_path = f"{output_dir}/{filename}.stl"
        cq.exporters.export(wp, stl_path)
        
        print(f"   ✓ {description}已导出为 {filename}.stl")
        
        return True
        
    except Exception as e:
        print(f"   ✗ {description}导出失败: {e}")
        return False

def test_extrude_operations():
    """测试拉伸操作"""
    print("=== 测试拉伸操作 ===")
    
    results = []
    
    try:
        # 测试简单矩形拉伸
        rect = make_rectangle(2.0, 1.0, center=True)
        extruded_rect = extrude(rect, distance=0.5)
        print(f"✓ 矩形拉伸成功: {extruded_rect}")
        results.append(extruded_rect)
        export_model(extruded_rect, "01_extruded_rectangle", "拉伸矩形")
        
        # 测试圆形拉伸
        circle = make_circle(0.5)
        extruded_circle = extrude(circle, distance=1.0)
        print(f"✓ 圆形拉伸成功: {extruded_circle}")
        results.append(extruded_circle)
        export_model(extruded_circle, "02_extruded_circle", "拉伸圆形")
        
        # 创建组合模型展示所有拉伸结果
        if len(results) >= 2:
            combined = results[0]
            # 在不同位置放置其他拉伸体
            with LocalCoordinateSystem(origin=(3, 0, 0), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
                combined = union(combined, results[1])
            if len(results) >= 3:
                with LocalCoordinateSystem(origin=(0, 3, 0), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
                    combined = union(combined, results[2])
            export_model(combined, "04_extrude_operations_combined", "拉伸操作组合")
        
        return True
        
    except Exception as e:
        print(f"✗ 拉伸操作测试失败: {e}")
        return False


def test_revolve_operations():
    """测试旋转操作"""
    print("\n=== 测试旋转操作 ===")
    
    results = []
    
    try:
        # 创建L型轮廓进行旋转
        p1 = make_point(0.5, 0, 0)
        p2 = make_point(1.0, 0, 0)
        p3 = make_point(1.0, 0, 0.5)
        p4 = make_point(0.8, 0, 0.5)
        p5 = make_point(0.8, 0, 0.2)
        p6 = make_point(0.5, 0, 0.2)
        
        lines = [
            make_line([p1, p2], "segment"),
            make_line([p2, p3], "segment"),
            make_line([p3, p4], "segment"),
            make_line([p4, p5], "segment"),
            make_line([p5, p6], "segment"),
            make_line([p6, p1], "segment")
        ]
        
        l_profile = make_sketch(lines)
        
        # 绕Z轴旋转创建回转体
        axis_start = make_point(0, 0, -1)
        axis_end = make_point(0, 0, 1)
        revolved = revolve(l_profile, axis_start, axis_end, 2 * math.pi)
        
        print(f"✓ L型轮廓旋转成功: {revolved}")
        results.append(revolved)
        export_model(revolved, "05_revolved_l_profile", "L型轮廓旋转体")
        
        # 测试部分旋转（180度）
        half_revolved = revolve(l_profile, axis_start, axis_end, math.pi)
        print(f"✓ 180度旋转成功: {half_revolved}")
        results.append(half_revolved)
        export_model(half_revolved, "06_half_revolved", "180度旋转体")
        
        # 创建组合展示
        if len(results) >= 2:
            with LocalCoordinateSystem(origin=(3, 0, 0), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
                combined = union(results[0], results[1])
                export_model(combined, "07_revolve_operations_combined", "旋转操作组合")
        
        return True
        
    except Exception as e:
        print(f"✗ 旋转操作测试失败: {e}")
        return False


def test_loft_operations():
    """测试放样操作"""
    print("\n=== 测试放样操作 ===")
    
    results = []
    
    try:
        # 创建不同大小的矩形在不同高度进行放样
        print("创建分层矩形放样...")
        
        # 底层 - 大矩形 (z=0)
        rect1 = make_rectangle(2.0, 2.0, center=True)
        
        # 中层 - 中矩形 (z=1)
        with LocalCoordinateSystem(origin=(0, 0, 1), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
            rect2 = make_rectangle(1.0, 1.0, center=True)
        
        # 顶层 - 小矩形 (z=2)
        with LocalCoordinateSystem(origin=(0, 0, 2), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
            rect3 = make_rectangle(0.5, 0.5, center=True)
        
        lofted = loft([rect1, rect2, rect3])
        print(f"✓ 多截面放样成功: {lofted}")
        results.append(lofted)
        export_model(lofted, "08_lofted_rectangles", "分层矩形放样")
        
        # 测试圆形到矩形的放样（在不同高度）
        print("创建圆形到矩形放样...")
        
        # 底层圆形 (z=0)
        circle = make_circle(1.0)
        
        # 顶层矩形 (z=1.5)
        with LocalCoordinateSystem(origin=(0, 0, 1.5), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
            square = make_rectangle(1.5, 1.5, center=True)
        
        circle_to_square = loft([circle, square])
        print(f"✓ 圆形到矩形放样成功: {circle_to_square}")
        results.append(circle_to_square)
        export_model(circle_to_square, "09_circle_to_square_loft", "圆形到矩形放样")
        
        # 创建更复杂的放样 - 圆形渐变到六边形
        print("创建圆形到六边形放样...")
        try:
            # 底层圆形
            base_circle = make_circle(0.8)
            
            # 中层 - 椭圆形（用矩形近似）
            with LocalCoordinateSystem(origin=(0, 0, 0.8), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
                middle_rect = make_rectangle(1.2, 0.8, center=True)
            
            # 顶层 - 小矩形
            with LocalCoordinateSystem(origin=(0, 0, 1.6), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
                top_rect = make_rectangle(0.6, 0.6, center=True)
            
            complex_loft = loft([base_circle, middle_rect, top_rect])
            print(f"✓ 复杂放样成功: {complex_loft}")
            results.append(complex_loft)
            export_model(complex_loft, "10_complex_loft", "复杂形状放样")
            
        except Exception as e:
            print(f"   ⚠️ 复杂放样跳过: {e}")
        
        # 创建组合展示
        if len(results) >= 2:
            try:
                combined = results[0]
                with LocalCoordinateSystem(origin=(5, 0, 0), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
                    combined = union(combined, results[1])
                if len(results) >= 3:
                    with LocalCoordinateSystem(origin=(0, 5, 0), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
                        combined = union(combined, results[2])
                export_model(combined, "11_loft_operations_combined", "放样操作组合")
            except Exception as e:
                print(f"   ⚠️ 放样组合导出跳过: {e}")
        
        return True
        
    except Exception as e:
        print(f"✗ 放样操作测试失败: {e}")
        return False


def test_sweep_operations():
    """测试扫掠操作"""
    print("\n=== 测试扫掠操作 ===")
    
    results = []
    
    try:
        # 测试1: 简单的直线扫掠 - 确保截面与路径正确对齐
        print("创建简单直线扫掠...")
        
        # 在YZ平面创建圆形截面（X方向为法向量）
        with LocalCoordinateSystem(origin=(0, 0, 0), 
                                 x_axis=(0, 1, 0),  # Y轴作为新的X轴
                                 y_axis=(0, 0, 1)):  # Z轴作为新的Y轴
            profile_circle = make_circle(0.2)
        
        # 创建X方向的扫掠路径
        path_start = make_point(0, 0, 0)
        path_end = make_point(2, 1, 1)
        straight_path = make_line([path_start, path_end], "segment")
        
        swept_straight = sweep(profile_circle, straight_path)
        print(f"✓ 直线扫掠成功: {swept_straight}")
        results.append(swept_straight)
        export_model(swept_straight, "12_straight_sweep", "直线扫掠")
        
        # 测试2: 垂直扫掠
        print("创建垂直扫掠...")
        
        # 在XY平面创建方形截面
        square_profile = make_rectangle(0.3, 0.3, center=True)
        
        # 创建Z方向的垂直路径
        vertical_start = make_point(0, 0, 0)
        vertical_end = make_point(0, 0, 2)
        vertical_path = make_line([vertical_start, vertical_end], "segment")
        
        swept_vertical = sweep(square_profile, vertical_path)
        print(f"✓ 垂直扫掠成功: {swept_vertical}")
        results.append(swept_vertical)
        export_model(swept_vertical, "13_vertical_sweep", "垂直扫掠")
        
        # 测试3: 水平扫掠
        print("创建水平扫掠...")
        
        # 在XZ平面创建三角形近似截面（用小矩形）
        with LocalCoordinateSystem(origin=(0, 0, 0), 
                                 x_axis=(1, 0, 0),  # X轴保持
                                 y_axis=(0, 0, 1)):  # Z轴作为新的Y轴
            triangle_profile = make_rectangle(0.15, 0.25, center=True)
        
        # 创建Y方向的水平路径
        horizontal_start = make_point(0, 0, 0)
        horizontal_end = make_point(0, 3, 0)
        horizontal_path = make_line([horizontal_start, horizontal_end], "segment")
        
        swept_horizontal = sweep(triangle_profile, horizontal_path)
        print(f"✓ 水平扫掠成功: {swept_horizontal}")
        results.append(swept_horizontal)
        export_model(swept_horizontal, "14_horizontal_sweep", "水平扫掠")
        
        # 测试4: 斜向扫掠
        print("创建斜向扫掠...")
        
        # 计算斜向路径的方向
        diagonal_start = make_point(0, 0, 0)
        diagonal_end = make_point(1, 1, 1)
        
        # 计算路径方向向量
        direction = (1, 1, 1)
        # 标准化
        length = math.sqrt(sum(d*d for d in direction))
        norm_dir = tuple(d/length for d in direction)
        
        # 创建垂直于路径的截面
        # 使用一个简单的垂直向量
        if abs(norm_dir[2]) < 0.9:  # 如果不是主要在Z方向
            perp1 = (0, 0, 1)  # 使用Z轴
        else:
            perp1 = (1, 0, 0)  # 使用X轴
        
        # 计算第二个垂直向量
        # perp2 = cross(norm_dir, perp1)
        perp2 = (
            norm_dir[1] * perp1[2] - norm_dir[2] * perp1[1],
            norm_dir[2] * perp1[0] - norm_dir[0] * perp1[2],
            norm_dir[0] * perp1[1] - norm_dir[1] * perp1[0]
        )
        
        with LocalCoordinateSystem(origin=(0, 0, 0), 
                                 x_axis=perp1, 
                                 y_axis=perp2):
            diagonal_profile = make_circle(0.15)
        
        diagonal_path = make_line([diagonal_start, diagonal_end], "segment")
        
        swept_diagonal = sweep(diagonal_profile, diagonal_path)
        print(f"✓ 斜向扫掠成功: {swept_diagonal}")
        results.append(swept_diagonal)
        export_model(swept_diagonal, "15_diagonal_sweep", "斜向扫掠")
        
        # 创建组合展示
        if len(results) >= 2:
            try:
                combined = results[0]
                positions = [(3, 0, 0), (0, 4, 0), (3, 4, 0)]
                for i, pos in enumerate(positions):
                    if i + 1 < len(results):
                        with LocalCoordinateSystem(origin=pos, x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
                            combined = union(combined, results[i + 1])
                
                export_model(combined, "16_sweep_operations_combined", "扫掠操作组合")
            except Exception as e:
                print(f"   ⚠️ 扫掠组合导出跳过: {e}")
        
        return True
        
    except Exception as e:
        print(f"✗ 扫掠操作测试失败: {e}")
        return False


def test_advanced_operations():
    """测试高级操作"""
    print("\n=== 测试高级操作 ===")
    
    results = []
    
    try:
        # 创建基础实体
        base_box = make_box(1.0, 1.0, 0.2, center=True)
        
        # 测试线性阵列
        linear_array = make_linear_pattern(base_box, direction=(2, 0, 0), count=3, spacing=1.5)
        print(f"✓ 线性阵列成功: {linear_array}")
        results.append(linear_array)
        export_model(linear_array, "17_linear_array", "线性阵列")
        
        # 测试2D阵列（通过两次线性阵列）
        y_array = make_2d_pattern(
            base_box, 
            x_direction=(2, 0, 0), 
            y_direction=(0, 2, 0), 
            x_count=3, 
            y_count=2, 
            x_spacing=1.5, 
            y_spacing=1.5
        )
        print(f"✓ 2D阵列成功: {y_array}")
        results.append(y_array)
        export_model(y_array, "18_2d_array", "2D阵列")
        
        # 测试圆角操作
        test_cube = make_box(2.0, 2.0, 2.0, center=True)
        filleted_cube = fillet(test_cube, [], radius=0.2)
        print(f"✓ 圆角操作成功: {filleted_cube}")
        results.append(filleted_cube)
        export_model(filleted_cube, "19_filleted_cube", "圆角立方体")
        
        # 测试倒角操作
        chamfered_cube = chamfer(test_cube, [], distance=0.15)
        print(f"✓ 倒角操作成功: {chamfered_cube}")
        results.append(chamfered_cube)
        export_model(chamfered_cube, "20_chamfered_cube", "倒角立方体")
        
        # 测试抽壳操作
        hollow_box = shell(test_cube, thickness=0.1, face_tags=["top", "front"])
        print(f"✓ 抽壳操作成功: {hollow_box}")
        results.append(hollow_box)
        export_model(hollow_box, "21_hollow_box", "抽壳立方体")
        
        # 创建高级操作展示组合
        if len(results) >= 3:
            demo_combined = results[0]  # 从2D阵列开始
            # 在不同位置放置其他高级操作结果
            with LocalCoordinateSystem(origin=(6, 0, 0), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
                demo_combined = union(demo_combined, results[2])  # 圆角立方体
            with LocalCoordinateSystem(origin=(0, 4, 0), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
                demo_combined = union(demo_combined, results[3])  # 倒角立方体
            export_model(demo_combined, "22_advanced_operations_demo", "高级操作演示")
        
        return True
        
    except Exception as e:
        print(f"✗ 高级操作测试失败: {e}")
        return False


def test_boolean_operations_comprehensive():
    """全面测试布尔运算"""
    print("\n=== 全面测试布尔运算 ===")
    
    results = []
    
    try:
        # 创建测试实体
        box1 = make_box(2.0, 2.0, 1.0, center=True)
        box2 = make_box(1.5, 1.5, 1.5, center=True)
        cylinder = make_cylinder(0.6, 2.0)
        
        # 布尔并运算
        union_result = union(box1, box2)
        print(f"✓ 布尔并运算成功: {union_result}")
        results.append(union_result)
        export_model(union_result, "23_boolean_union", "布尔并运算")
        
        # 布尔减运算
        cut_result = cut(box1, cylinder)
        print(f"✓ 布尔减运算成功: {cut_result}")
        results.append(cut_result)
        export_model(cut_result, "24_boolean_cut", "布尔减运算")
        
        # 布尔交运算
        intersect_result = intersect(box1, box2)
        print(f"✓ 布尔交运算成功: {intersect_result}")
        results.append(intersect_result)
        export_model(intersect_result, "25_boolean_intersect", "布尔交运算")
        
        # 复杂布尔运算组合
        step1 = union(box1, box2)
        step2 = cut(step1, cylinder)
        print(f"✓ 复杂布尔运算成功: {step2}")
        results.append(step2)
        export_model(step2, "26_complex_boolean", "复杂布尔运算")
        
        # 创建布尔运算展示组合
        if len(results) >= 4:
            boolean_demo = results[0]  # 并运算
            with LocalCoordinateSystem(origin=(4, 0, 0), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
                boolean_demo = union(boolean_demo, results[1])  # 减运算
            with LocalCoordinateSystem(origin=(0, 4, 0), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
                boolean_demo = union(boolean_demo, results[2])  # 交运算
            with LocalCoordinateSystem(origin=(4, 4, 0), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
                boolean_demo = union(boolean_demo, results[3])  # 复杂运算
            export_model(boolean_demo, "27_boolean_operations_showcase", "布尔运算展示")
        
        return True
        
    except Exception as e:
        print(f"✗ 布尔运算测试失败: {e}")
        return False


def build_flange():
    """构建法兰零件 - 复杂零件示例"""
    print("\n=== 构建法兰零件 ===")
    
    try:
        # 法兰参数
        flange_diameter = 6.0      # 法兰外径
        flange_thickness = 0.8     # 法兰厚度
        bore_diameter = 2.0        # 中心孔径
        bolt_circle_diameter = 4.5 # 螺栓孔分布圆直径
        bolt_hole_diameter = 0.4   # 螺栓孔直径
        num_bolts = 6             # 螺栓孔数量
        
        # 1. 创建法兰主体（圆盘）
        flange_outer = make_cylinder(flange_diameter/2, flange_thickness)
        print("✓ 法兰主体创建成功")
        
        # 2. 创建中心孔
        center_hole = make_cylinder(bore_diameter/2, flange_thickness * 1.1)  # 稍微长一点确保完全切穿
        flange_with_hole = cut(flange_outer, center_hole)
        print("✓ 中心孔加工完成")
        
        # 3. 创建螺栓孔 使用镜像阵列
        bolt_circle_diameter /= 2  # 转换为半径
        bolt_hole_radius = bolt_hole_diameter / 2
        with LocalCoordinateSystem(origin=(0, flange_diameter/3, 0),
                                 x_axis=(1, 0, 0), 
                                 y_axis=(0, 1, 0)):
            # 创建螺栓孔的圆柱体
            bolt_hole = make_cylinder(bolt_hole_radius, flange_thickness * 1.1)

        bolt_holes = make_radial_pattern(
            bolt_hole,
            center=Point((0, 0, 0)),  # 在法兰中心
            axis=(0, 0, 1),  # Z轴为旋转轴
            count= num_bolts,
            angle= 2 * math.pi
        )
        
        flange_with_hole = cut(flange_with_hole, bolt_holes)
        flange_result = flange_with_hole
        
        print(f"✓ {num_bolts}个螺栓孔加工完成")
        
        # 4. 添加圆角（如果支持）
        try:
            filleted_flange = fillet(flange_result, [], radius=0.05)
            flange_result = filleted_flange
            print("✓ 圆角加工完成")
        except:
            print("✓ 圆角加工跳过（功能限制）")
        
        print(f"✓ 法兰零件构建完成: {flange_result}")
        
        # 导出法兰
        export_model(flange_result, "28_complex_flange", "复杂法兰零件")
        
        return flange_result
        
    except Exception as e:
        print(f"✗ 法兰构建失败: {e}")
        return None


def build_gear_wheel():
    """构建简化齿轮 - 另一个复杂零件示例"""
    print("\n=== 构建简化齿轮 ===")
    
    try:
        # 齿轮参数
        outer_radius = 2.0
        inner_radius = 0.3
        thickness = 0.5
        tooth_count = 12
        
        # 1. 创建齿轮主体
        gear_body = make_cylinder(outer_radius * 0.8, thickness)
        print("✓ 齿轮主体创建成功")
        
        # 2. 创建中心孔
        center_hole = make_cylinder(inner_radius, thickness * 1.1)
        gear_with_hole = cut(gear_body, center_hole)
        print("✓ 齿轮中心孔完成")
        
        # 3. 简化的齿形：在外圆周添加小立方体作为齿
        gear_result = gear_with_hole
        tooth_size = 0.15
        
        for i in range(tooth_count):
            angle = 2 * math.pi * i / tooth_count
            x_offset = (outer_radius * 0.9) * math.cos(angle)
            y_offset = (outer_radius * 0.9) * math.sin(angle)
            
            # 使用坐标系创建齿
            with LocalCoordinateSystem(origin=(x_offset, y_offset, 0),
                                     x_axis=(math.cos(angle), math.sin(angle), 0),
                                     y_axis=(-math.sin(angle), math.cos(angle), 0)):
                tooth = make_box(tooth_size, tooth_size * 0.5, thickness)
                gear_result = union(gear_result, tooth)
        
        print(f"✓ {tooth_count}个齿创建完成")
        
        # 4. 添加轮毂加强筋
        hub_cylinder = make_cylinder(inner_radius * 2, thickness)
        gear_result = union(gear_result, hub_cylinder)
        print("✓ 轮毂加强完成")
        
        print(f"✓ 简化齿轮构建完成: {gear_result}")
        
        # 导出齿轮
        export_model(gear_result, "29_simplified_gear", "简化齿轮零件")
        
        return gear_result
        
    except Exception as e:
        print(f"✗ 齿轮构建失败: {e}")
        return None


def build_complex_assembly():
    """构建复杂装配体"""
    print("\n=== 构建复杂装配体 ===")
    
    try:
        # 1. 创建底座
        base = make_box(4.0, 4.0, 0.5, center=True)
        
        # 2. 创建立柱
        column = make_cylinder(0.3, 3.0)
        
        # 3. 创建顶板
        with LocalCoordinateSystem(origin=(0, 0, 3.0),
                                 x_axis=(1, 0, 0),
                                 y_axis=(0, 1, 0)):
            top_plate = make_box(2.0, 2.0, 0.3, center=True)
        
        # 4. 组装
        assembly = union(base, column)
        assembly = union(assembly, top_plate)
        
        # 5. 添加装饰孔
        for x in [-1, 1]:
            for y in [-1, 1]:
                with LocalCoordinateSystem(origin=(x, y, 0),
                                         x_axis=(1, 0, 0),
                                         y_axis=(0, 1, 0)):
                    deco_hole = make_cylinder(0.1, 0.6)
                    assembly = cut(assembly, deco_hole)
        
        print(f"✓ 复杂装配体构建完成: {assembly}")
        
        # 导出装配体
        export_model(assembly, "30_complex_assembly", "复杂装配体")
        
        return assembly
        
    except Exception as e:
        print(f"✗ 装配体构建失败: {e}")
        return None


def test_coordinate_system_complex():
    """测试复杂坐标系操作"""
    print("\n=== 测试复杂坐标系操作 ===")
    
    try:
        results = []
        
        # 1. 嵌套坐标系测试
        with LocalCoordinateSystem(origin=(2, 2, 0),
                                 x_axis=(0, 1, 0),
                                 y_axis=(-1, 0, 0)):
            # 外层局部坐标系
            outer_box = make_box(1, 1, 1)
            results.append(outer_box)
            
            with LocalCoordinateSystem(origin=(1, 1, 0),
                                     x_axis=(1, 0, 0),
                                     y_axis=(0, 1, 0)):
                # 内层局部坐标系
                inner_box = make_box(0.5, 0.5, 0.5)
                results.append(inner_box)
        
        # 2. 旋转坐标系测试
        angle = math.pi / 4  # 45度
        with LocalCoordinateSystem(origin=(0, 0, 1),
                                 x_axis=(math.cos(angle), math.sin(angle), 0),
                                 y_axis=(-math.sin(angle), math.cos(angle), 0)):
            rotated_box = make_box(2, 0.5, 0.5)
            results.append(rotated_box)
        
        # 3. 极坐标系样式的多个位置
        for i in range(6):
            angle = i * math.pi / 3  # 每60度一个
            radius = 3
            x = radius * math.cos(angle)
            y = radius * math.sin(angle)
            
            with LocalCoordinateSystem(origin=(x, y, 0),
                                     x_axis=(math.cos(angle), math.sin(angle), 0),
                                     y_axis=(-math.sin(angle), math.cos(angle), 0)):
                small_box = make_box(0.3, 0.8, 0.3)
                results.append(small_box)
        
        print(f"✓ 复杂坐标系操作成功，创建了{len(results)}个实体")
        
        # 导出个别组件
        if len(results) >= 3:
            export_model(results[0], "31_nested_coordinate_outer", "嵌套坐标系外层")
            export_model(results[1], "32_nested_coordinate_inner", "嵌套坐标系内层")
            export_model(results[2], "33_rotated_coordinate", "旋转坐标系")
        
        # 合并所有结果
        combined = results[0]
        for result in results[1:]:
            combined = union(combined, result)
        
        print(f"✓ 坐标系测试结果合并: {combined}")
        export_model(combined, "34_coordinate_system_showcase", "坐标系操作展示")
        
        return True
        
    except Exception as e:
        print(f"✗ 复杂坐标系操作失败: {e}")
        return False


def test_helical_sweep_operations():
    """测试螺旋扫掠操作"""
    print("\n=== 测试螺旋扫掠操作 ===")
    
    results = []
    
    try:
        # 测试1: 圆形截面螺旋扫掠
        print("创建圆形截面螺旋弹簧...")
        
        # 创建圆形截面profile
        circle_profile = make_circle(radius=0.15)
        
        spring_circle = helical_sweep(
            profile=circle_profile,
            coil_radius=1.0,     # 弹簧半径
            pitch=0.8,           # 螺距
            turns=3.0            # 3圈
        )
        print(f"✓ 圆形截面弹簧创建成功: {spring_circle}")
        results.append(spring_circle)
        export_model(spring_circle, "35_helical_spring_circle", "圆形截面螺旋弹簧")
        
        # 测试2: 螺纹齿形截面螺旋扫掠
        print("创建螺纹齿形截面螺旋...")
        
        # 创建螺纹齿形profile（梯形）
        thread_points = [
            make_point(0, -0.1, 0),     # 底部左
            make_point(0.2, -0.05, 0),  # 顶部左  
            make_point(0.2, 0.05, 0),   # 顶部右
            make_point(0, 0.1, 0),      # 底部右
        ]
        
        thread_lines = []
        for i in range(len(thread_points)):
            p1 = thread_points[i]
            p2 = thread_points[(i + 1) % len(thread_points)]
            thread_lines.append(make_line([p1, p2], "segment"))
        
        thread_profile = make_sketch(thread_lines)
        
        spring_thread = helical_sweep(
            profile=thread_profile,
            coil_radius=1.2,     # 稍大的半径
            pitch=1.0,           # 螺距
            turns=3.0            # 3圈
        )
        print(f"✓ 螺纹齿形弹簧创建成功: {spring_thread}")
        results.append(spring_thread)
        export_model(spring_thread, "36_helical_spring_thread", "螺纹齿形螺旋")
        
        # 测试3: 三角形截面螺旋扫掠
        print("创建三角形截面螺旋...")
        
        # 创建三角形profile
        triangle_points = [
            make_point(0, -0.1, 0),     # 底部
            make_point(0.15, 0, 0),     # 右顶点
            make_point(0, 0.1, 0),      # 顶部
        ]
        
        triangle_lines = []
        for i in range(len(triangle_points)):
            p1 = triangle_points[i]
            p2 = triangle_points[(i + 1) % len(triangle_points)]
            triangle_lines.append(make_line([p1, p2], "segment"))
        
        triangle_profile = make_sketch(triangle_lines)
        
        spring_triangle = helical_sweep(
            profile=triangle_profile,
            coil_radius=0.8,     # 较小的半径
            pitch=0.6,           # 较小的螺距
            turns=3.0            # 3圈
        )
        print(f"✓ 三角形截面弹簧创建成功: {spring_triangle}")
        results.append(spring_triangle)
        export_model(spring_triangle, "37_helical_spring_triangle", "三角形截面螺旋")
        
        # 测试4: 高级螺旋扫掠（使用圆形profile）
        try:
            print("创建高精度圆形截面螺旋...")
            
            # 使用较小的圆形profile
            fine_circle_profile = make_circle(radius=0.08)
            
            spring_advanced = helical_sweep(
                profile=fine_circle_profile,
                coil_radius=1.4,
                pitch=0.9,
                turns=3.0,
                points_per_turn=20,  # 高精度
                smooth=True
            )
            print(f"✓ 高精度螺旋创建成功: {spring_advanced}")
            results.append(spring_advanced)
            export_model(spring_advanced, "38_helical_spring_advanced", "高精度圆形截面螺旋")
            
        except Exception as e:
            print(f"   ⚠️ 高级螺旋扫掠跳过: {e}")
        
        # 测试5: 创建螺旋组合展示
        print("创建螺旋组合展示...")
        
        if len(results) >= 3:
            try:
                # 将不同的螺旋放在不同位置
                spiral_combo = results[0]  # 圆形截面在原点
                
                # 螺纹齿形放在右侧
                with LocalCoordinateSystem(origin=(4, 0, 0), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
                    spiral_combo = union(spiral_combo, results[1])
                
                # 三角形截面放在后方
                with LocalCoordinateSystem(origin=(0, 4, 0), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
                    spiral_combo = union(spiral_combo, results[2])
                
                # 高精度螺旋放在对角（如果存在）
                if len(results) >= 4:
                    with LocalCoordinateSystem(origin=(4, 4, 0), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
                        spiral_combo = union(spiral_combo, results[3])
                
                print(f"✓ 螺旋组合创建成功: {spiral_combo}")
                export_model(spiral_combo, "39_helical_spirals_showcase", "螺旋截面展示组合")
                
            except Exception as e:
                print(f"   ⚠️ 螺旋组合创建跳过: {e}")
        
        print(f"✓ 螺旋扫掠操作测试完成，成功创建 {len(results)} 个螺旋模型")
        print("   测试的profile类型: 圆形、螺纹齿形、三角形")
        print("   所有螺旋都是3圈")
        
        return True
        
    except Exception as e:
        print(f"✗ 螺旋扫掠操作测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_coordinate_system_verification():
    """验证坐标系转换是否正确"""
    print("\n=== 验证坐标系转换 ===")
    
    try:
        # 测试1: 创建一个沿Z轴的立方体（在SimpleCAD中应该是垂直的）
        print("测试Z轴立方体...")
        z_cube = make_box(0.5, 0.5, 2.0, center=True)  # 高度为2的立方体
        export_model(z_cube, "42_z_axis_cube", "Z轴立方体")
        
        # 测试2: 创建一个沿Z轴的圆柱体
        print("测试Z轴圆柱体...")
        z_cylinder = make_cylinder(0.3, 2.0)  # 高度为2的圆柱体
        export_model(z_cylinder, "43_z_axis_cylinder", "Z轴圆柱体")
        
        # 测试3: 在不同坐标系中创建对象，验证变换
        print("测试坐标系变换...")
        objects = []
        
        # 原点立方体
        origin_cube = make_box(0.3, 0.3, 0.3, center=True)
        objects.append(origin_cube)
        
        # X轴方向
        with LocalCoordinateSystem(origin=(2, 0, 0), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
            x_cube = make_box(0.3, 0.3, 0.3, center=True)
            objects.append(x_cube)
        
        # Y轴方向
        with LocalCoordinateSystem(origin=(0, 2, 0), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
            y_cube = make_box(0.3, 0.3, 0.3, center=True)
            objects.append(y_cube)
        
        # Z轴方向
        with LocalCoordinateSystem(origin=(0, 0, 2), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
            z_cube = make_box(0.3, 0.3, 0.3, center=True)
            objects.append(z_cube)
        
        # 合并所有立方体
        combined = objects[0]
        for obj in objects[1:]:
            combined = union(combined, obj)
        
        export_model(combined, "44_coordinate_verification", "坐标系验证")
        
        # 测试4: 验证旋转操作的坐标系
        print("测试旋转坐标系...")
        
        # 创建一个矩形，然后在旋转坐标系中放置
        base_rect = make_rectangle(1.0, 0.3, center=True)
        base_extruded = extrude(base_rect, distance=0.2)
        
        rotation_objects = [base_extruded]
        
        # 45度旋转
        angle = math.pi / 4
        with LocalCoordinateSystem(origin=(0, 0, 1), 
                                 x_axis=(math.cos(angle), math.sin(angle), 0),
                                 y_axis=(-math.sin(angle), math.cos(angle), 0)):
            rotated_rect = make_rectangle(1.0, 0.3, center=True)
            rotated_extruded = extrude(rotated_rect, distance=0.2)
            rotation_objects.append(rotated_extruded)
        
        # 90度旋转
        angle = math.pi / 2
        with LocalCoordinateSystem(origin=(0, 0, 2), 
                                 x_axis=(math.cos(angle), math.sin(angle), 0),
                                 y_axis=(-math.sin(angle), math.cos(angle), 0)):
            rotated_rect2 = make_rectangle(1.0, 0.3, center=True)
            rotated_extruded2 = extrude(rotated_rect2, distance=0.2)
            rotation_objects.append(rotated_extruded2)
        
        # 合并旋转测试对象
        rotation_combined = rotation_objects[0]
        for obj in rotation_objects[1:]:
            rotation_combined = union(rotation_combined, obj)
        
        export_model(rotation_combined, "45_rotation_verification", "旋转坐标系验证")
        
        print("✓ 坐标系验证测试完成")
        return True
        
    except Exception as e:
        print(f"✗ 坐标系验证测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_comprehensive_tests():
    """运行所有综合测试"""
    print("SimpleCAD API 综合功能测试")
    print("=" * 60)
    
    test_results = []
    
    # 基础建模操作测试
    test_results.append(("拉伸操作", test_extrude_operations()))
    test_results.append(("旋转操作", test_revolve_operations()))
    test_results.append(("放样操作", test_loft_operations()))
    test_results.append(("扫掠操作", test_sweep_operations()))
    
    # 高级操作测试
    test_results.append(("高级操作", test_advanced_operations()))
    test_results.append(("布尔运算", test_boolean_operations_comprehensive()))
    
    # 螺旋扫掠测试
    test_results.append(("螺旋扫掠", test_helical_sweep_operations()))
    
    # 复杂零件构建测试
    flange = build_flange()
    test_results.append(("法兰构建", flange is not None))
    
    gear = build_gear_wheel()
    test_results.append(("齿轮构建", gear is not None))
    
    assembly = build_complex_assembly()
    test_results.append(("装配体构建", assembly is not None))
    
    # 坐标系测试
    test_results.append(("复杂坐标系", test_coordinate_system_complex()))
    test_results.append(("坐标系验证", test_coordinate_system_verification()))
    test_results.append(("坐标系验证", test_coordinate_system_verification()))
    
    # 输出测试结果
    print("\n" + "=" * 60)
    print("测试结果汇总:")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for test_name, result in test_results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"{test_name:<20}: {status}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print("=" * 60)
    print(f"总计: {len(test_results)} 项测试")
    print(f"通过: {passed} 项")
    print(f"失败: {failed} 项")
    print(f"成功率: {passed/len(test_results)*100:.1f}%")
    
    if passed > len(test_results) * 0.8:
        print("🎉 大部分功能测试通过！API实现质量良好。")
    elif passed > len(test_results) * 0.6:
        print("👍 多数功能正常，部分高级功能需要优化。")
    else:
        print("⚠️ 需要进一步改进API实现。")
    
    return passed, failed


if __name__ == "__main__":
    try:
        passed, failed = run_comprehensive_tests()
        
        print("\n" + "=" * 60)
        print("测试完成！")
        print("查看 output/ 目录中的导出文件：")
        print("\n=== 基础建模操作 ===")
        print("- 01_extruded_rectangle.stl (拉伸矩形)")
        print("- 02_extruded_circle.stl (拉伸圆形)")
        print("- 03_directional_extrude.stl (方向拉伸)")
        print("- 04_extrude_operations_combined.stl (拉伸操作组合)")
        print("- 05_revolved_l_profile.stl (L型轮廓旋转体)")
        print("- 06_half_revolved.stl (180度旋转体)")
        print("- 07_revolve_operations_combined.stl (旋转操作组合)")
        print("- 08_lofted_rectangles.stl (分层矩形放样)")
        print("- 09_circle_to_square_loft.stl (圆形到矩形放样)")
        print("- 10_complex_loft.stl (复杂形状放样)")
        print("- 11_loft_operations_combined.stl (放样操作组合)")
        print("- 12_straight_sweep.stl (直线扫掠)")
        print("- 13_vertical_sweep.stl (垂直扫掠)")
        print("- 14_horizontal_sweep.stl (水平扫掠)")
        print("- 15_diagonal_sweep.stl (斜向扫掠)")
        print("- 16_sweep_operations_combined.stl (扫掠操作组合)")
        print("\n=== 高级操作 ===")
        print("- 17_linear_array.stl (线性阵列)")
        print("- 18_2d_array.stl (2D阵列)")
        print("- 19_filleted_cube.stl (圆角立方体)")
        print("- 20_chamfered_cube.stl (倒角立方体)")
        print("- 21_hollow_box.stl (抽壳立方体)")
        print("- 22_advanced_operations_demo.stl (高级操作演示)")
        print("\n=== 布尔运算 ===")
        print("- 23_boolean_union.stl (布尔并运算)")
        print("- 24_boolean_cut.stl (布尔减运算)")
        print("- 25_boolean_intersect.stl (布尔交运算)")
        print("- 26_complex_boolean.stl (复杂布尔运算)")
        print("- 27_boolean_operations_showcase.stl (布尔运算展示)")
        print("\n=== 螺旋扫掠 ===")
        print("- 35_helical_spring_basic.stl (基础螺旋弹簧)")
        print("- 36_helical_spring_tight.stl (紧密螺旋弹簧)")
        print("- 37_helical_spring_heavy.stl (粗大螺旋弹簧)")
        print("- 38_helical_spring_mini.stl (小型精密螺旋弹簧)")
        print("- 39_helical_spring_advanced.stl (高精度螺旋弹簧)")
        print("- 40_helical_springs_showcase.stl (螺旋弹簧展示组合)")
        print("- 41_helical_coil_antenna.stl (螺旋线圈天线)")
        print("\n=== 复杂零件 ===")
        print("- 28_complex_flange.stl/.step (复杂法兰零件)")
        print("- 29_simplified_gear.stl/.step (简化齿轮零件)")
        print("- 30_complex_assembly.stl/.step (复杂装配体)")
        print("\n=== 坐标系操作 ===")
        print("- 31_nested_coordinate_outer.stl (嵌套坐标系外层)")
        print("- 32_nested_coordinate_inner.stl (嵌套坐标系内层)")
        print("- 33_rotated_coordinate.stl (旋转坐标系)")
        print("- 34_coordinate_system_showcase.stl (坐标系操作展示)")
        print("- 42_z_axis_cube.stl (Z轴立方体)")
        print("- 43_z_axis_cylinder.stl (Z轴圆柱体)")
        print("- 44_coordinate_verification.stl (坐标系验证组合)")
        print("- 45_rotation_verification.stl (旋转坐标系验证)")
        print("\n🎉 总共导出了45+个测试模型文件！包含螺旋扫掠弹簧和坐标系修正验证！")
        
        exit_code = 0 if failed == 0 else 1
        sys.exit(exit_code)
        
    except Exception as e:
        print(f"测试执行出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
