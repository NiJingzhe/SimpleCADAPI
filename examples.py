#!/usr/bin/env python3
"""
SimpleCAD API 复杂操作示例
展示高级CAD建模技术，包括连续放样、复杂扫掠、局部坐标系、样条曲线等
"""

import sys
import os
import math
sys.path.insert(0, 'src')

import simplecadapi as scad
import numpy as np

def create_output_dir():
    """创建输出目录"""
    output_dir = 'output'
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    return output_dir

def example_complex_loft():
    """示例1: 复杂连续放样 - 创建一个渐变的多边形到圆形的过渡"""
    print("=== 示例1: 复杂连续放样 ===")
    
    # 创建多个不同形状的轮廓
    profiles = []
    
    # 轮廓1: 底部正方形
    with scad.SimpleWorkplane((0, 0, 0)) as wp1:
        square = scad.make_rectangle_rwire(4, 4)
        profiles.append(square)
    
    # 轮廓2: 中间矩形（稍小）
    with scad.SimpleWorkplane((0, 0, 2)) as wp2:
        rect = scad.make_rectangle_rwire(3, 3)
        profiles.append(rect)
    
    # 轮廓3: 顶部圆形
    with scad.SimpleWorkplane((0, 0, 4)) as wp3:
        circle = scad.make_circle_rwire((0, 0, 0), 2)
        profiles.append(circle)
    
    # 执行放样
    lofted_solid = scad.loft_rsolid(profiles)
    
    # 导出结果
    output_dir = create_output_dir()
    scad.export_stl(lofted_solid, os.path.join(output_dir, "complex_loft.stl"))
    print(f"复杂放样体积: {lofted_solid.get_volume():.2f}")

def example_swept_shape():
    """示例2: 扫掠操作 - 创建沿路径的扫掠体"""
    print("\n=== 示例2: 扫掠操作 ===")
    
    # 创建扫掠轮廓（圆形）
    with scad.SimpleWorkplane((0, 2, 0)) as wp:
        profile = scad.make_rectangle_rface(
            width=1,
            height=0.5,
            center=(0, 0, 0),
            normal=(1, 0, 0)
        )

    # 创建扫掠路径（曲线）
    path_points = []
    
    # 创建一个螺旋扫掠路径
    for i in range(20):
        angle = i * 0.2 * math.pi  # 每次增加0.2π弧度
        x = 5 * math.cos(angle)  # 半径5的圆
        y = 5 * math.sin(angle)
        z = i * 0.1  # 每次增加高度0.1
        path_points.append((x, y, z)) 
    
    # 创建样条曲线作为扫掠路径
    path_spline = scad.make_spline_rwire(path_points)
    
    # 执行扫掠 - 修正API调用
    swept_solid = scad.sweep_rsolid(
        profile=profile,
        path=path_spline,
        is_frenet=True
    )

    assert isinstance(swept_solid, scad.Solid), "扫掠操作未返回有效的Solid对象"
    
    # 导出结果
    output_dir = create_output_dir()
    scad.export_stl(swept_solid, os.path.join(output_dir, "swept_shape.stl"))
    print(f"扫掠体积: {swept_solid.get_volume():.2f}")

def example_nested_workplanes():
    """示例3: 嵌套工作平面 - 创建复杂的多级结构"""
    print("\n=== 示例3: 嵌套工作平面 ===")
    
    parts = []
    
    # 基础平台
    base = scad.make_box_rsolid(10, 10, 1)
    parts.append(base)
    
    # 在基础平台上创建第一层结构
    with scad.SimpleWorkplane((0, 0, 1)) as wp1:
        # 创建四个支柱
        for x in [-3, 3]:
            for y in [-3, 3]:
                with scad.SimpleWorkplane((x, y, 0)) as wp2:
                    pillar = scad.make_cylinder_rsolid(0.5, 3)
                    parts.append(pillar)
    
    # 在支柱顶部创建第二层平台
    with scad.SimpleWorkplane((0, 0, 4)) as wp3:
        platform = scad.make_box_rsolid(6, 6, 0.5)
        parts.append(platform)
        
        # 在第二层平台上创建中心塔
        with scad.SimpleWorkplane((0, 0, 0.5)) as wp4:
            tower = scad.make_cylinder_rsolid(1, 2)
            parts.append(tower)
            
            # 在塔顶创建装饰
            with scad.SimpleWorkplane((0, 0, 2)) as wp5:
                decoration = scad.make_sphere_rsolid(0.8)
                parts.append(decoration)
    
    # 合并所有部件
    combined = parts[0]
    for part in parts[1:]:
        combined = scad.union_rsolid(combined, part)
    
    # 导出结果
    output_dir = create_output_dir()
    scad.export_stl(combined, os.path.join(output_dir, "nested_structure.stl"))
    print(f"嵌套结构体积: {combined.get_volume():.2f}")

def example_spline_curves():
    """示例4: 样条曲线 - 创建复杂的3D曲线"""
    print("\n=== 示例4: 样条曲线 ===")
    
    # 创建复杂的3D样条曲线点
    curve_points = []
    for i in range(15):
        t = i / 14.0 * 2 * math.pi
        x = 3 * math.cos(t)
        y = 3 * math.sin(t)
        z = 2 * math.sin(2 * t)  # 波浪形高度变化
        curve_points.append((x, y, z))
    
    # 创建主样条曲线
    main_curve = scad.make_spline_redge(curve_points)
    
    # 创建几个不同的截面轮廓，放置在不同的Z高度
    profiles = []
    
    # 底部轮廓
    with scad.SimpleWorkplane((0, 0, 0)) as wp1:
        profile1 = scad.make_circle_rwire((0, 0, 0), 0.8)
        profiles.append(profile1)
    
    # 中间轮廓
    with scad.SimpleWorkplane((0, 0, 2)) as wp2:
        profile2 = scad.make_rectangle_rwire(1.2, 0.8)
        profiles.append(profile2)
    
    # 顶部轮廓
    with scad.SimpleWorkplane((0, 0, 4)) as wp3:
        profile3 = scad.make_circle_rwire((0, 0, 0), 0.4)
        profiles.append(profile3)
    
    # 通过截面创建放样体
    spline_solid = scad.loft_rsolid(profiles)
    
    # 导出结果
    output_dir = create_output_dir()
    scad.export_stl(spline_solid, os.path.join(output_dir, "spline_shape.stl"))
    print(f"样条形状体积: {spline_solid.get_volume():.2f}")

def example_boolean_operations():
    """示例5: 复杂布尔运算 - 创建复杂的机械零件"""
    print("\n=== 示例5: 复杂布尔运算 ===")
    
    # 创建基础块
    base = scad.make_box_rsolid(8, 6, 4)
    
    # 创建中心孔
    center_hole = scad.make_cylinder_rsolid(1.5, 4)
    base = scad.cut_rsolid(base, center_hole)
    
    # 创建侧面的通孔
    with scad.SimpleWorkplane((0, 0, 2)) as wp:
        # X方向的孔
        hole_x = scad.make_cylinder_rsolid(0.8, 10)
        rotated_hole_x = scad.rotate_shape(hole_x, math.pi/2, (0, 1, 0), (0, 0, 0))
        if isinstance(rotated_hole_x, scad.Solid):
            base = scad.cut_rsolid(base, rotated_hole_x)
        
        # Y方向的孔
        hole_y = scad.make_cylinder_rsolid(0.6, 8)
        rotated_hole_y = scad.rotate_shape(hole_y, math.pi/2, (1, 0, 0), (0, 0, 0))
        if isinstance(rotated_hole_y, scad.Solid):
            base = scad.cut_rsolid(base, rotated_hole_y)
    
    # 添加加强筋
    with scad.SimpleWorkplane((0, 0, 4)) as wp:
        for angle in [0, 45, 90, 135]:
            x = 2.5 * math.cos(math.radians(angle))
            y = 2.5 * math.sin(math.radians(angle))
            
            with scad.SimpleWorkplane((x, y, 0)) as wp_rib:
                rib = scad.make_box_rsolid(0.5, 0.5, 1)
                base = scad.union_rsolid(base, rib)
    
    # 添加圆角 - 获取所有边
    all_edges = base.get_edges()
    base = scad.fillet_rsolid(base, all_edges[:4], 0.5)  # 只对前4条边进行圆角
    
    # 导出结果
    output_dir = create_output_dir()
    scad.export_stl(base, os.path.join(output_dir, "mechanical_part.stl"))
    print(f"机械零件体积: {base.get_volume():.2f}")

def example_pattern_operations():
    """示例6: 阵列操作 - 创建复杂的阵列结构"""
    print("\n=== 示例6: 阵列操作 ===")
    
    # 创建基础单元
    base_unit = scad.make_box_rsolid(1, 1, 2)
    
    # 在顶部添加装饰
    with scad.SimpleWorkplane((0, 0, 2)) as wp:
        decoration = scad.make_sphere_rsolid(0.4)
        base_unit = scad.union_rsolid(base_unit, decoration)
    
    # 线性阵列
    linear_array = scad.linear_pattern_rcompound(base_unit, (2, 0, 0), 5, 2.0)
    
    # 对基础单元进行径向阵列（而不是线性阵列）
    radial_array = scad.radial_pattern_rcompound(base_unit, (0, 0, 0), (0, 0, 1), 6, 2*math.pi)
    
    # 导出结果
    output_dir = create_output_dir()
    scad.export_stl(radial_array, os.path.join(output_dir, "pattern_array.stl"))
    print("阵列结构创建完成")

def example_mirror_operations():
    """示例7: 镜像操作 - 创建对称结构"""
    print("\n=== 示例7: 镜像操作 ===")
    
    # 创建非对称的基础形状
    base = scad.make_box_rsolid(4, 2, 3)
    
    # 添加一个偏移的特征
    with scad.SimpleWorkplane((1, 0, 3)) as wp:
        feature = scad.make_cylinder_rsolid(0.8, 1)
        base = scad.union_rsolid(base, feature)
    
    # 添加侧面的切口
    with scad.SimpleWorkplane((2, 0, 1.5)) as wp:
        cutout = scad.make_sphere_rsolid(1)
        base = scad.cut_rsolid(base, cutout)
    
    # 镜像到另一半
    mirrored = scad.mirror_shape(base, (0, 0, 0), (1, 0, 0))
    
    # 合并原始和镜像 - 确保镜像结果是Solid类型
    if isinstance(mirrored, scad.Solid):
        symmetric_part = scad.union_rsolid(base, mirrored)
    else:
        print("警告: 镜像操作没有返回Solid类型")
        symmetric_part = base
    
    # 导出结果
    output_dir = create_output_dir()
    scad.export_stl(symmetric_part, os.path.join(output_dir, "symmetric_part.stl"))
    print(f"对称零件体积: {symmetric_part.get_volume():.2f}")

def example_advanced_features():
    """示例8: 高级特征 - 抽壳、倒角、圆角的综合应用"""
    print("\n=== 示例8: 高级特征 ===")
    
    # 创建基础容器
    container = scad.make_box_rsolid(6, 6, 4)
    
    # 抽壳操作 - 简化为移除一个面
    all_faces = container.get_faces()
    # 选择顶面进行移除
    faces_to_remove = [all_faces[0]]  # 简单选择第一个面
    container = scad.shell_rsolid(container, faces_to_remove, 0.3)
    
    # 添加底部支撑
    with scad.SimpleWorkplane((0, 0, -0.15)) as wp:
        support = scad.make_box_rsolid(5, 5, 0.3)
        container = scad.union_rsolid(container, support)
    
    # 添加把手
    with scad.SimpleWorkplane((3, 0, 2)) as wp:
        handle_main = scad.make_box_rsolid(1, 2, 0.5)
        handle_hole = scad.make_cylinder_rsolid(0.3, 1)
        rotated_hole = scad.rotate_shape(handle_hole, math.pi/2, (0, 1, 0), (0, 0, 0))
        if isinstance(rotated_hole, scad.Solid):
            handle = scad.cut_rsolid(handle_main, rotated_hole)
        else:
            handle = handle_main
        container = scad.union_rsolid(container, handle)
    
    # 应用圆角
    all_edges = container.get_edges()
    container = scad.fillet_rsolid(container, all_edges[:4], 0.2)  # 只对前4条边圆角
    
    # 导出结果
    output_dir = create_output_dir()
    scad.export_stl(container, os.path.join(output_dir, "advanced_container.stl"))
    print(f"高级容器体积: {container.get_volume():.2f}")

def example_gear_like_shape():
    """示例9: 类似齿轮的形状 - 展示旋转成型和布尔运算"""
    print("\n=== 示例9: 类似齿轮的形状 ===")
    
    # 创建基础圆盘
    base_disk = scad.make_cylinder_rsolid(2.0, 1)  # 进一步减小基础半径
    print(f"  基础圆盘体积: {base_disk.get_volume():.2f}")
    
    # 创建中心孔
    center_hole = scad.make_cylinder_rsolid(0.5, 1)
    base_disk = scad.cut_rsolid(base_disk, center_hole)
    print(f"  打孔后圆盘体积: {base_disk.get_volume():.2f}")
    
    # 创建齿轮齿 - 使用径向阵列的正确方法
    print("  创建齿轮齿...")
    
    # 齿轮参数
    base_radius = 2.0
    tooth_height = 0.5   # 增加齿的径向高度
    tooth_width = 0.5    # 增加齿的切向宽度
    tooth_count = 18      # 减少齿数使其更明显
    
    # 创建更明显的齿轮齿
    # 齿轮齿应该部分重叠基础圆盘
    tooth_radius = base_radius - tooth_height / 4  # 调整位置使齿轮齿部分重叠圆盘内侧
    
    # 创建齿轮齿，初始位置在X轴正方向
    # 使用径向朝外的设计
    single_tooth = scad.make_box_rsolid(tooth_height, tooth_width, 1)
    
    # 将齿移动到正确的径向位置
    positioned_tooth = scad.translate_shape(single_tooth, (tooth_radius, -tooth_width / 2, 0))

    if isinstance(positioned_tooth, scad.Solid):
        print(f"  单个齿体积: {positioned_tooth.get_volume():.2f}")
        
        # 首先测试单个齿的合并
        test_gear = scad.union_rsolid(base_disk, positioned_tooth)
        print(f"  单个齿合并后体积: {test_gear.get_volume():.2f}")
        
        # 如果单个齿合并成功，再使用径向阵列
        if test_gear.get_volume() > base_disk.get_volume():
            print("  单个齿合并成功，创建径向阵列...")
            
            # 使用径向阵列创建所有齿
            teeth_array = scad.radial_pattern_rcompound(
                positioned_tooth, 
                (0, 0, 0),      # 旋转中心
                (0, 0, 1),      # 旋转轴（Z轴）
                tooth_count,    # 齿数
                360     # 完整的360度
            )
            
            print(f"  径向阵列类型: {type(teeth_array)}")
            print(f"  径向阵列是否为复合体: {isinstance(teeth_array, scad.Compound)}")
            
            # 合并齿轮和齿
            gear = base_disk
            if isinstance(teeth_array, scad.Compound):
                solids = teeth_array.get_solids()
                print(f"  复合体中的实体数量: {len(solids)}")
                
                for i, tooth_solid in enumerate(solids):
                    if isinstance(tooth_solid, scad.Solid):
                        old_volume = gear.get_volume()
                        gear = scad.union_rsolid(gear, tooth_solid)
                        new_volume = gear.get_volume()
                        print(f"    合并第{i+1}个齿: {old_volume:.2f} -> {new_volume:.2f}")
            
            # 导出结果
            output_dir = create_output_dir()
            scad.export_stl(gear, os.path.join(output_dir, "gear_shape.stl"))
            print(f"齿轮形状体积: {gear.get_volume():.2f}")
        else:
            print("  警告: 单个齿合并失败，可能齿轮设计有问题")
            # 导出基础圆盘
            output_dir = create_output_dir()
            scad.export_stl(base_disk, os.path.join(output_dir, "gear_shape.stl"))
            print(f"只导出基础圆盘，体积: {base_disk.get_volume():.2f}")
    else:
        print(f"  错误: 定位后的齿不是Solid类型: {type(positioned_tooth)}")

def main():
    """主函数 - 运行所有示例"""
    print("SimpleCAD API 复杂操作示例")
    print("=" * 50)
    
    try:
        # 运行所有示例
        example_complex_loft()
        example_swept_shape()
        example_nested_workplanes()
        example_spline_curves()
        example_boolean_operations()
        example_pattern_operations()
        example_mirror_operations()
        example_advanced_features()
        example_gear_like_shape()
        
        print("\n" + "=" * 50)
        print("所有示例已完成！检查 examples_output 文件夹查看生成的STL文件。")
        
    except Exception as e:
        print(f"示例运行失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
