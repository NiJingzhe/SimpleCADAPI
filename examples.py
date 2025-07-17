#!/usr/bin/env python3
"""
SimpleCAD API 复杂操作示例
展示高级CAD建模技术，包括连续放样、复杂扫掠、螺旋扫掠、局部坐标系、样条曲线等
"""

import sys
import os
import math

from simplecadapi.operations import make_cylinder_rsolid

sys.path.insert(0, "src")

import simplecadapi as scad


def create_output_dir():
    """创建输出目录"""
    output_dir = "output"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    return output_dir


def example_naca_blade():
    """示例1: NACA 0016桨叶 - 使用NACA翼型创建螺旋桨叶"""
    print("=== 示例1: NACA 0016桨叶 ===")

    def naca_0016_profile(chord_length, num_points=50):
        """生成NACA 0016翼型的坐标点

        Args:
            chord_length: 弦长
            num_points: 点的数量

        Returns:
            翼型坐标点列表 [(x, y), ...]
        """
        # NACA 0016: 对称翼型，最大厚度16%
        thickness = 0.16  # 16%厚度

        # 上表面和下表面的x坐标
        x_coords = []
        for i in range(num_points):
            # 使用余弦分布获得更好的前缘形状
            beta = math.pi * i / (num_points - 1)
            x = chord_length * (1 - math.cos(beta)) / 2
            x_coords.append(x)

        profile_points = []

        # 计算上表面
        for x in x_coords:
            x_norm = x / chord_length
            # NACA 0016厚度分布公式
            yt = (
                thickness
                * chord_length
                * (
                    0.2969 * math.sqrt(x_norm)
                    - 0.1260 * x_norm
                    - 0.3516 * x_norm**2
                    + 0.2843 * x_norm**3
                    - 0.1015 * x_norm**4  # 修正系数，使尾缘闭合
                )
            )
            profile_points.append((x, yt))

        # 计算下表面（从后往前）
        for x in reversed(x_coords[1:]):  # 跳过重复的尾缘点
            x_norm = x / chord_length
            yt = (
                thickness
                * chord_length
                * (
                    0.2969 * math.sqrt(x_norm)
                    - 0.1260 * x_norm
                    - 0.3516 * x_norm**2
                    + 0.2843 * x_norm**3
                    - 0.1015 * x_norm**4
                )
            )
            profile_points.append((x, -yt))

        return profile_points

    # 创建多个不同尺寸的NACA 0016翼型截面
    profiles = []

    # 桨叶参数
    blade_length = 5  # 桨叶长度
    root_chord = 1.5  # 减小根部弦长
    tip_chord = 0.3  # 减小尖部弦长
    twist_angle = 45  # 增加扭转角度

    # 创建沿桨叶径向的多个截面
    for i, position in enumerate([0, 0.3, 0.6, 0.8, 1.0]):
        # 计算当前位置的弦长（线性变化）
        current_chord = root_chord + (tip_chord - root_chord) * position

        # 计算当前位置的扭转角度（螺旋角）
        current_twist = twist_angle * position  # 直接使用角度

        # 计算当前位置的攻角（迎风面角度）
        attack_angle = 15 * (1 - position * 0.5)  # 根部15度，叶尖7.5度，使用角度

        # 生成NACA 0016翼型
        airfoil_points = naca_0016_profile(current_chord, 40)

        # 转换为3D点并应用变换
        section_points = []
        x_position = position * blade_length  # 沿X轴方向（径向）

        for x, z in airfoil_points:
            # 翼型原始坐标：x是弦向，z是厚度方向
            # 重新映射坐标：让翼型在XZ平面内，厚度方向沿Z轴
            # x坐标保持不变（径向位置）
            # 翼型的弦向映射到Z轴方向
            # 翼型的厚度方向映射到Y轴方向（垂直）

            # 应用扭转变换（螺旋角）- 在XZ平面内旋转
            z_twisted = x * math.cos(math.radians(current_twist)) - z * math.sin(
                math.radians(current_twist)
            )
            y_twisted = x * math.sin(math.radians(current_twist)) + z * math.cos(
                math.radians(current_twist)
            )

            # 应用攻角变换（使迎风面面向旋转方向）
            z_final = z_twisted * math.cos(math.radians(attack_angle))
            y_final = y_twisted + z_twisted * math.sin(math.radians(attack_angle))

            # 构建3D点：(径向位置, 垂直方向, 切向方向)
            section_points.append((x_position, y_final, z_final))

        # 在XZ平面上创建翼型轮廓（在x_position位置，Y=0平面）
        with scad.SimpleWorkplane(
            (x_position, 0, 0), normal=(0, 1, 0)
        ) as wp:  # 法向量改为Y轴
            # 创建多段线轮廓（封闭的）
            profile_wire = scad.make_spline_rwire(section_points, closed=True)
            profiles.append(profile_wire)
            print(
                f"  创建第{i+1}个截面，位置: {x_position:.1f}, 弦长: {current_chord:.2f}, 扭转: {current_twist:.1f}°, 攻角: {attack_angle:.1f}°"
            )

    # 执行放样生成桨叶
    print("  执行放样操作...")
    blade_solid = scad.loft_rsolid(profiles, ruled=True)

    # 给桨叶一个整体的攻角调整，使其更符合螺旋桨的形状
    # 先绕Y轴旋转，调整桨叶的整体攻角
    blade_solid = scad.rotate_shape(
        blade_solid, 0, (0, 1, 0), (0, 0, 0)
    )  # 使用角度而非弧度

    # 创建一个中心轴
    with scad.SimpleWorkplane((0, 0, 0), normal=(0, 0, 1)) as wp:
        central_axis = scad.make_cylinder_rsolid(
            1.3, 1, axis=(0, 0, 1)
        )  # 进一步减小半径

    central_axis = scad.translate_shape(
        central_axis, (0, 0, -0.5)
    )  # 将中心轴放置在桨叶中心

    assert isinstance(central_axis, scad.Solid), "中心轴创建失败，未返回有效的Solid对象"

    print("中心轴创建完成, 体积:", central_axis.get_volume())

    # 创建三个桨叶，每个间隔120度（绕Z轴旋转）
    blade_angles = [0, 120, 240]  # 度数
    blade_solids = []

    for i, angle in enumerate(blade_angles):
        # 绕Z轴旋转桨叶，使其在XY平面内展开
        rotated_blade = scad.rotate_shape(blade_solid, angle, (0, 0, 1), (0, 0, 0))

        if isinstance(rotated_blade, scad.Solid):
            blade_solids.append(rotated_blade)
            print(
                f"  创建第{i+1}个桨叶，角度: {angle}°，体积: {rotated_blade.get_volume():.2f}"
            )
        else:
            print(f"  警告: 第{i+1}个桨叶旋转失败，类型: {type(rotated_blade)}")

    print(len(blade_solids), "个桨叶被创建")

    # 改进的合并策略：先检查是否有重叠
    for i, blade in enumerate(blade_solids):
        if isinstance(blade, scad.Solid):
            old_volume = central_axis.get_volume()
            blade_volume = blade.get_volume()
            print(f"  准备合并第{i+1}个桨叶，桨叶体积: {blade_volume:.2f}")

            try:
                # 使用更安全的合并方法
                merged_axis = scad.union_rsolid(central_axis, blade)
                new_volume = merged_axis.get_volume()
                print(f"  合并后体积: {old_volume:.2f} -> {new_volume:.2f}")

                # 检查合并是否成功
                expected_min_volume = (
                    old_volume + blade_volume * 0.1
                )  # 至少增加10%的桨叶体积
                if new_volume >= expected_min_volume:
                    central_axis = merged_axis
                    print(f"  第{i+1}个桨叶合并成功")
                else:
                    print(f"  警告: 第{i+1}个桨叶合并异常，体积增加不足")
                    # 仍然使用合并结果，但输出警告
                    central_axis = merged_axis

            except Exception as e:
                print(f"  错误: 合并第{i+1}个桨叶失败: {e}")
                break
        else:
            print(f"  警告: 第{i+1}个桨叶不是Solid类型: {type(blade)}")

    # 导出结果
    output_dir = create_output_dir()
    scad.export_stl(central_axis, os.path.join(output_dir, "naca_blade.stl"))

    assert isinstance(central_axis, scad.Solid), "放样操作未返回有效的Solid对象"

    print(f"NACA 0016桨叶体积: {central_axis.get_volume():.2f}")
    print(f"  桨叶长度: {blade_length}")
    print(f"  根部弦长: {root_chord}")
    print(f"  尖部弦长: {tip_chord}")
    print(f"  扭转角度: {twist_angle}°")


def example_swept_shape():
    """示例2: 扫掠操作 - 创建沿路径的扫掠体"""
    print("\n=== 示例2: 扫掠操作 ===")

    # 创建扫掠轮廓（圆形）
    with scad.SimpleWorkplane((0, 2, 0)) as wp:
        profile = scad.make_rectangle_rface(
            width=1, height=0.5, center=(0, 0, 0), normal=(1, 0, 0)
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
    swept_solid = scad.sweep_rsolid(profile=profile, path=path_spline, is_frenet=True)

    assert isinstance(swept_solid, scad.Solid), "扫掠操作未返回有效的Solid对象"

    # 导出结果
    output_dir = create_output_dir()
    scad.export_stl(swept_solid, os.path.join(output_dir, "swept_shape.stl"))
    print(f"扫掠体积: {swept_solid.get_volume():.2f}")


def example_helical_sweep():
    """示例2b: 螺旋扫掠操作 - 创建螺旋形状"""
    print("\n=== 示例2b: 螺旋扫掠操作 ===")

    # 示例1: 创建螺旋弹簧
    print("  创建螺旋弹簧...")
    with scad.SimpleWorkplane((0, 0, 0)) as wp:
        # 创建圆形轮廓作为弹簧的截面
        spring_profile = scad.make_circle_rwire((0, 0, 0), 0.3)

    # 螺旋扫掠参数
    pitch = 1.5  # 螺距：每转一圈的高度
    height = 8.0  # 总高度
    radius = 2.0  # 螺旋半径

    # 执行螺旋扫掠
    spring_solid = scad.helical_sweep_rsolid(
        profile=spring_profile,
        pitch=pitch,
        height=height,
        radius=radius,
        center=(0, 0, 0),
        dir=(0, 0, 1),
    )

    assert isinstance(spring_solid, scad.Solid), "螺旋扫掠操作未返回有效的Solid对象"

    # 导出螺旋弹簧
    output_dir = create_output_dir()
    scad.export_stl(spring_solid, os.path.join(output_dir, "helical_spring.stl"))
    print(f"  螺旋弹簧体积: {spring_solid.get_volume():.2f}")
    print(f"  螺距: {pitch}, 高度: {height}, 半径: {radius}")

    # 示例2: 创建方形截面的螺旋管
    print("  创建方形截面螺旋管...")
    with scad.SimpleWorkplane((0, 0, 0)) as wp:
        # 创建方形轮廓
        square_profile = scad.make_rectangle_rwire(0.6, 0.6)

    # 不同的螺旋参数
    spiral_tube = scad.helical_sweep_rsolid(
        profile=square_profile,
        pitch=2.0,
        height=6.0,
        radius=1.5,
        center=(0, 0, 0),
        dir=(0, 0, 1),
    )

    # 导出螺旋管
    scad.export_stl(spiral_tube, os.path.join(output_dir, "helical_tube.stl"))
    print(f"  螺旋管体积: {spiral_tube.get_volume():.2f}")

    # 示例3: 创建多重螺旋结构
    print("  创建多重螺旋结构...")

    # 创建多个不同半径的螺旋
    helical_parts = []

    for i, r in enumerate([1.0, 1.8, 2.6]):
        with scad.SimpleWorkplane((0, 0, 0)) as wp:
            # 每个螺旋使用不同大小的圆形截面
            profile_radius = 0.2 - i * 0.05
            helix_profile = scad.make_circle_rwire((0, 0, 0), profile_radius)

        # 创建螺旋，每个具有不同的螺距
        helix_pitch = 1.2 + i * 0.3
        helix_solid = scad.helical_sweep_rsolid(
            profile=helix_profile,
            pitch=helix_pitch,
            height=7.0,
            radius=r,
            center=(0, 0, 0),
            dir=(0, 0, 1),
        )

        helical_parts.append(helix_solid)
        print(
            f"    螺旋{i+1}: 半径={r}, 螺距={helix_pitch:.1f}, 截面半径={profile_radius:.2f}"
        )

    # 合并所有螺旋
    combined_helix = helical_parts[0]
    for part in helical_parts[1:]:
        combined_helix = scad.union_rsolid(combined_helix, part)

    # 导出多重螺旋结构
    scad.export_stl(combined_helix, os.path.join(output_dir, "multi_helix.stl"))
    print(f"  多重螺旋体积: {combined_helix.get_volume():.2f}")

    # 示例4: 创建螺旋楼梯状结构
    print("  创建螺旋楼梯...")

    with scad.SimpleWorkplane((0, 0, 0)) as wp:
        # 创建楼梯踏步的轮廓（矩形）
        step_profile = scad.make_rectangle_rwire(1.2, 0.2)

    # 螺旋楼梯参数
    stair_solid = scad.helical_sweep_rsolid(
        profile=step_profile,
        pitch=3.0,  # 较大的螺距，模拟楼梯的层高
        height=12.0,  # 楼梯总高度
        radius=3.0,  # 楼梯半径
        center=(0, 0, 0),
        dir=(0, 0, 1),
    )

    # 导出螺旋楼梯
    scad.export_stl(stair_solid, os.path.join(output_dir, "helical_stair.stl"))
    print(f"  螺旋楼梯体积: {stair_solid.get_volume():.2f}")

    print("螺旋扫掠示例完成！")


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
    center_hole = scad.make_cylinder_rsolid(1.5, 5)
    # 移动到中心
    base = scad.cut_rsolid(base, center_hole)

    # 创建侧面的通孔
    with scad.SimpleWorkplane(origin=(0, 0, 2)) as wp:
        # X方向的孔
        hole_x = scad.make_cylinder_rsolid(radius=0.8, height=20)
        # 由于中心点在圆柱底面的中心，所以需要平移一下
        hole_x = scad.translate_shape(hole_x, (0, 0, -10))
        # 要沿着X轴，就要绕Y轴转动
        rotated_hole_x = scad.rotate_shape(
            shape=hole_x, angle=90, axis=(0, 1, 0), origin=(0, 0, 0)
        )
        if isinstance(rotated_hole_x, scad.Solid):
            base = scad.cut_rsolid(base, rotated_hole_x)

        hole_y = scad.make_cylinder_rsolid(radius=0.8, height=20)
        hole_y = scad.translate_shape(hole_y, (0, 0, -10))
        rotated_hole_y = scad.rotate_shape(
            shape=hole_y, angle=90, axis=(1, 0, 0), origin=(0, 0, 0)
        )
        if isinstance(rotated_hole_y, scad.Solid):
            base = scad.cut_rsolid(base, rotated_hole_y)

    # 添加加强筋
    with scad.SimpleWorkplane((0, 0, 4)) as wp:
        for angle in [0, 45, 90, 135, 180, 225, 270, 315]:
            x = 2.5 * math.cos(math.radians(angle))
            y = 2.5 * math.sin(math.radians(angle))

            with scad.SimpleWorkplane((x, y, 0)) as wp_rib:
                rib = scad.make_box_rsolid(0.5, 0.5, 1)
                base = scad.union_rsolid(base, rib)

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
    linear_array = scad.linear_pattern_rsolidlist(base_unit, (2, 0, 0), 5, 2.0)

    # 对基础单元进行径向阵列（而不是线性阵列）
    radial_array = scad.radial_pattern_rsolidlist(
        base_unit, (0, 0, 0), (0, 0, 1), 6, 360
    )

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
        rotated_hole = scad.rotate_shape(handle_hole, math.pi / 2, (0, 1, 0), (0, 0, 0))
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
    tooth_height = 0.5  # 增加齿的径向高度
    tooth_width = 0.5  # 增加齿的切向宽度
    tooth_count = 18  # 减少齿数使其更明显

    # 创建更明显的齿轮齿
    # 齿轮齿应该部分重叠基础圆盘
    tooth_radius = base_radius - tooth_height / 4  # 调整位置使齿轮齿部分重叠圆盘内侧

    # 创建齿轮齿，初始位置在X轴正方向
    # 使用径向朝外的设计
    single_tooth = scad.make_box_rsolid(width=tooth_height, height=tooth_width, depth=1)

    # 将齿移动到正确的径向位置
    positioned_tooth = scad.translate_shape(single_tooth, (tooth_radius, 0, 0))

    if isinstance(positioned_tooth, scad.Solid):
        print(f"  单个齿体积: {positioned_tooth.get_volume():.2f}")

        # 首先测试单个齿的合并
        test_gear = scad.union_rsolid(base_disk, positioned_tooth)
        print(f"  单个齿合并后体积: {test_gear.get_volume():.2f}")

        # 如果单个齿合并成功，再使用径向阵列
        if test_gear.get_volume() > base_disk.get_volume():
            print("  单个齿合并成功，创建径向阵列...")

            # 使用径向阵列创建所有齿
            teeth_array = scad.radial_pattern_rsolidlist(
                positioned_tooth,
                (0, 0, 0),  # 旋转中心
                (0, 0, 1),  # 旋转轴（Z轴）
                tooth_count,  # 齿数
                360,  # 完整的360度
            )

            print(f"  径向阵列类型: {type(teeth_array)}")
            print(f"  径向阵列是否为列表: {isinstance(teeth_array, list)}")
            if isinstance(teeth_array, list) and len(teeth_array) > 0:
                print(f"  数组长度: {len(teeth_array)}")
                print(f"  第一个元素类型: {type(teeth_array[0])}")

            # 合并齿轮和齿
            gear = base_disk
            if isinstance(teeth_array, list):
                print(f"  复合体中的实体数量: {len(teeth_array)}")

                for i, tooth_solid in enumerate(teeth_array):
                    if isinstance(tooth_solid, scad.Solid):
                        old_volume = gear.get_volume()
                        gear = scad.union_rsolid(gear, tooth_solid)
                        new_volume = gear.get_volume()
                        print(
                            f"    合并第{i+1}个齿: {old_volume:.2f} -> {new_volume:.2f}"
                        )

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


def example_tagged_array_operations():
    """示例10: 标签化阵列操作 - 线性阵列后对每个实体进行标签化操作"""
    print("\n=== 示例10: 标签化阵列操作 ===")

    # 创建基础单元 - 一个带有圆柱孔的立方体
    print("  创建基础单元...")
    base_unit = scad.make_box_rsolid(3, 3, 2)

    # 为基础单元自动标记面
    base_unit.auto_tag_faces("box")
    print(f"  基础单元体积: {base_unit.get_volume():.2f}")

    # 创建线性阵列 - 沿X轴创建5个单元
    print("  创建线性阵列...")
    array_solids = scad.linear_pattern_rsolidlist(base_unit, (4, 0, 0), 5, 4.0)
    print(f"  阵列创建完成，共 {len(array_solids)} 个实体")

    # 为每个阵列单元重新标记面和边
    for i, solid in enumerate(array_solids):
        print(f"\n  处理第 {i+1} 个实体:")

        # 自动标记面
        solid.auto_tag_faces("box")

        # 打印面标签信息
        faces = solid.get_faces()
        print(f"    面数量: {len(faces)}")
        for j, face in enumerate(faces):
            face_tags = [tag for tag in face._tags] if hasattr(face, "_tags") else []
            area = face.get_area()
            print(f"      面 {j}: 标签={face_tags}, 面积={area:.2f}")

        # 打印边标签信息
        edges = solid.get_edges()
        print(f"    边数量: {len(edges)}")
        for j, edge in enumerate(edges[:6]):  # 只显示前6条边，避免输出过多
            edge_tags = [tag for tag in edge._tags] if hasattr(edge, "_tags") else []
            length = edge.get_length()
            print(f"      边 {j}: 标签={edge_tags}, 长度={length:.2f}")
        if len(edges) > 6:
            print(f"      ... 还有 {len(edges) - 6} 条边")

    # 对不同的实体应用不同的操作
    processed_solids = []

    for i, solid in enumerate(array_solids):
        print(f"\n  对第 {i+1} 个实体应用操作:")

        if i == 0:
            # 第1个实体: 抽壳 - 去除顶面
            print("    操作: 抽壳 (去除顶面)")
            try:
                faces = solid.get_faces()
                # 寻找顶面 (Z方向最大的面)
                top_faces = []
                max_z = -float("inf")
                for face in faces:
                    center = face.cq_face.Center()
                    if center.z > max_z:
                        max_z = center.z
                        top_faces = [face]
                    elif abs(center.z - max_z) < 1e-6:
                        top_faces.append(face)

                if top_faces:
                    shelled_solid = scad.shell_rsolid(solid, top_faces, 0.2)
                    processed_solids.append(shelled_solid)
                    print(
                        f"      抽壳成功，壁厚: 0.2, 新体积: {shelled_solid.get_volume():.2f}"
                    )
                else:
                    processed_solids.append(solid)
                    print("      未找到顶面，保持原状")
            except Exception as e:
                print(f"      抽壳失败: {e}")
                processed_solids.append(solid)

        elif i == 1:
            # 第2个实体: 圆角 - 对前4条边进行圆角
            print("    操作: 圆角 (前4条边)")
            try:
                edges = solid.get_edges()
                if len(edges) >= 4:
                    filleted_solid = scad.fillet_rsolid(solid, edges[:4], 0.3)
                    processed_solids.append(filleted_solid)
                    print(
                        f"      圆角成功，半径: 0.3, 新体积: {filleted_solid.get_volume():.2f}"
                    )
                else:
                    processed_solids.append(solid)
                    print("      边数不足，保持原状")
            except Exception as e:
                print(f"      圆角失败: {e}")
                processed_solids.append(solid)

        elif i == 2:
            # 第3个实体: 倒角 - 对顶部边进行倒角
            print("    操作: 倒角 (顶部边)")
            try:
                edges = solid.get_edges()
                # 寻找顶部边 (Z坐标较大的边)
                top_edges = []
                for edge in edges:
                    # 获取边的起始和结束顶点
                    start_vertex = edge.get_start_vertex()
                    end_vertex = edge.get_end_vertex()
                    start_coords = start_vertex.get_coordinates()
                    end_coords = end_vertex.get_coordinates()
                    mid_z = (start_coords[2] + end_coords[2]) / 2
                    if mid_z > 1.5:  # 顶部边的Z坐标应该接近2
                        top_edges.append(edge)

                if top_edges and len(top_edges) >= 2:
                    chamfered_solid = scad.chamfer_rsolid(solid, top_edges[:4], 0.2)
                    processed_solids.append(chamfered_solid)
                    print(
                        f"      倒角成功，距离: 0.2, 处理了 {min(4, len(top_edges))} 条边, 新体积: {chamfered_solid.get_volume():.2f}"
                    )
                else:
                    processed_solids.append(solid)
                    print("      未找到合适的顶部边，保持原状")
            except Exception as e:
                print(f"      倒角失败: {e}")
                processed_solids.append(solid)

        elif i == 3:
            # 第4个实体: 组合操作 - 先圆角再部分抽壳
            print("    操作: 组合 (圆角 + 部分抽壳)")
            try:

                # 再抽壳，去除一个侧面
                faces = filleted_solid.get_faces()
                side_faces = []
                for face in faces:
                    normal = face.get_normal_at()
                    # 寻找X方向的面
                    if abs(normal.x) > 0.8:
                        side_faces.append(face)
                        break

                if side_faces:
                    final_solid = scad.shell_rsolid(filleted_solid, side_faces, 0.15)
                    processed_solids.append(final_solid)
                    print(f"      组合操作成功，新体积: {final_solid.get_volume():.2f}")
                else:
                    processed_solids.append(filleted_solid)
                    print(
                        f"      只完成圆角，新体积: {filleted_solid.get_volume():.2f}"
                    )
            except Exception as e:
                print(f"      组合操作失败: {e}")
                processed_solids.append(solid)

        else:
            # 第5个实体: 保持原状作为对比
            print("    操作: 保持原状 (对比参考)")
            processed_solids.append(solid)
            print(f"      原始体积: {solid.get_volume():.2f}")

    # 合并所有处理后的实体用于导出
    print("\n  合并所有处理后的实体...")
    combined_result = processed_solids[0]
    for solid in processed_solids[1:]:
        combined_result = scad.union_rsolid(combined_result, solid)

    # 导出结果
    output_dir = create_output_dir()
    scad.export_stl(
        combined_result, os.path.join(output_dir, "tagged_array_operations.stl")
    )

    # 也分别导出每个处理后的实体
    for i, solid in enumerate(processed_solids):
        filename = f"array_unit_{i+1}.stl"
        scad.export_stl(solid, os.path.join(output_dir, filename))
        print(f"    已导出: {filename}")

    print(f"标签化阵列操作完成，总体积: {combined_result.get_volume():.2f}")


def main():
    """主函数 - 运行所有示例"""
    print("SimpleCAD API 复杂操作示例")
    print("=" * 50)

    try:
        # 运行所有示例
        example_naca_blade()
        example_swept_shape()
        example_helical_sweep()  # 新增螺旋扫掠示例
        example_nested_workplanes()
        example_spline_curves()
        example_boolean_operations()
        example_pattern_operations()
        example_mirror_operations()
        example_advanced_features()
        example_gear_like_shape()
        example_tagged_array_operations()  # 新增示例

        print("\n" + "=" * 50)
        print("所有示例已完成！检查 examples_output 文件夹查看生成的STL文件。")

    except Exception as e:
        print(f"示例运行失败: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
