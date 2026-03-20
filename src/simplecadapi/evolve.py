from simplecadapi import *
import math


def make_n_hole_flange_rsolid(
    flange_outer_diameter=120.0,
    flange_inner_diameter=60.0,
    flange_thickness=15.0,
    boss_outer_diameter=80.0,
    boss_height=5.0,
    hole_diameter=8.0,
    hole_circle_diameter=100.0,
    hole_count=8,
    chamfer_size=1.0,
) -> Solid:
    """Create an n-hole flange with a raised boss ring and optional chamfers. The center of the bottom face is placed at the origin."""

    print(f"开始创建{hole_count}孔法兰...")

    from typing import cast
    import math

    try:
        # 步骤1: 创建法兰主体圆盘
        print("  步骤1: 创建法兰主体圆盘...")

        # 创建外圆柱体
        outer_cylinder = make_cylinder_rsolid(
            radius=flange_outer_diameter / 2,
            height=flange_thickness,
            bottom_face_center=(0, 0, 0),
        )
        print(
            f"    法兰外圆柱创建成功，直径: {flange_outer_diameter}mm, 厚度: {flange_thickness}mm"
        )

        # 创建内孔圆柱体
        inner_cylinder = make_cylinder_rsolid(
            radius=flange_inner_diameter / 2,
            height=flange_thickness + 2,  # 确保完全切穿
            bottom_face_center=(0, 0, -1),
        )
        print(f"    法兰内孔圆柱创建成功，直径: {flange_inner_diameter}mm")

        # 从外圆柱中减去内孔形成法兰主体
        flange_body_results = cut_rsolidlist(outer_cylinder, inner_cylinder)
        if len(flange_body_results) != 1:
            raise ValueError("法兰主体切割结果不是单个实体，请检查参数设置。")
        flange_body = flange_body_results[0]
        body_volume = flange_body.get_volume()
        print(f"    法兰主体创建完成，体积: {body_volume:.2f} mm³")

    except Exception as e:
        print(f"    错误: 步骤1创建法兰主体失败 - {e}")
        raise ValueError(f"法兰主体创建失败") from e

    try:
        # 步骤2: 创建中心凸起圆环（保持中心通孔）
        print("  步骤2: 创建中心凸起圆环...")

        # 创建凸起圆环的实心部分（位于法兰顶部）
        boss_outer_solid = make_cylinder_rsolid(
            radius=boss_outer_diameter / 2,
            height=boss_height,
            bottom_face_center=(0, 0, flange_thickness),
        )
        print(
            f"    凸起圆环外圆柱创建成功，直径: {boss_outer_diameter}mm，高度: {boss_height}mm"
        )

        # 创建凸起圆环的内孔（与法兰内孔保持一致）
        boss_inner_hole = make_cylinder_rsolid(
            radius=flange_inner_diameter / 2,
            height=boss_height + 2,  # 确保完全切穿凸起圆环
            bottom_face_center=(0, 0, flange_thickness - 1),
        )
        print(f"    凸起圆环内孔创建成功，直径: {flange_inner_diameter}mm")

        # 从凸起圆环中减去内孔，形成环形凸起
        boss_ring_results = cut_rsolidlist(boss_outer_solid, boss_inner_hole)
        if len(boss_ring_results) != 1:
            raise ValueError("凸起圆环切割结果不是单个实体，请检查参数设置。")
        boss_ring = boss_ring_results[0]
        print("    凸起圆环内孔切割完成，形成环形凸起")

        # 合并法兰主体和凸起圆环
        union_results = union_rsolidlist([flange_body, boss_ring])
        if len(union_results) != 1:
            raise ValueError("法兰主体与凸起圆环无法合并成一个整体，请检查几何参数。")

        flange_with_boss = union_results[0]
        boss_volume = flange_with_boss.get_volume()
        print(f"    法兰主体与凸起圆环合并完成，体积: {boss_volume:.2f} mm³")

    except Exception as e:
        print(f"    错误: 步骤2创建中心凸起圆环失败 - {e}")
        raise ValueError(f"中心凸起圆环创建失败") from e

    try:
        # 步骤3: 创建连接孔
        print("  步骤3: 创建连接孔...")

        hole_radius = hole_diameter / 2
        hole_circle_radius = hole_circle_diameter / 2
        total_height = flange_thickness + boss_height + 2  # 确保完全穿透

        print(
            f"    连接孔参数：孔径{hole_diameter}mm，分布圆直径{hole_circle_diameter}mm，孔数{hole_count}"
        )

        # 逐个创建每个孔并切割
        current_flange = flange_with_boss
        angle_step = 360.0 / hole_count

        for i in range(hole_count):
            angle = i * angle_step
            x = hole_circle_radius * math.cos(math.radians(angle))
            y = hole_circle_radius * math.sin(math.radians(angle))

            # 创建单个孔
            hole = make_cylinder_rsolid(
                radius=hole_radius,
                height=total_height,
                bottom_face_center=(x, y, -1),  # 从底部向上切割
            )

            # 切割孔
            current_flange_results = cut_rsolidlist(current_flange, hole)
            if len(current_flange_results) != 1:
                raise ValueError("连接孔切割结果不是单个实体，请检查参数设置。")
            current_flange = current_flange_results[0]
            print(f"    第{i + 1}个孔位置: ({x:.2f}, {y:.2f}), 角度: {angle:.1f}°")

        flange_with_holes = current_flange
        final_volume_holes = flange_with_holes.get_volume()
        print(f"    所有连接孔切割完成，最终体积: {final_volume_holes:.2f} mm³")
        print(f"    总体积减少: {boss_volume - final_volume_holes:.2f} mm³")

    except Exception as e:
        print(f"    错误: 步骤3创建连接孔失败 - {e}")
        raise ValueError(f"连接孔创建失败") from e

    try:
        # 步骤4: 添加倒角处理
        print("  步骤4: 添加倒角处理...")

        # 获取所有边
        all_edges = flange_with_holes.get_edges()
        print(f"    找到{len(all_edges)}条边")

        # 尝试对主要边进行倒角
        try:
            chamfered_flange = chamfer_rsolid(
                flange_with_holes, all_edges, chamfer_size
            )
            print(f"    倒角处理完成，倒角尺寸: {chamfer_size}mm")
        except:
            print("    倒角处理失败，使用无倒角版本")
            chamfered_flange = flange_with_holes

    except Exception as e:
        print(f"    警告: 步骤4倒角处理失败，使用无倒角版本 - {e}")
        chamfered_flange = flange_with_holes

    try:
        # 步骤5: 验证最终结果
        print("  步骤5: 验证最终结果...")

        if not isinstance(chamfered_flange, Solid):
            raise ValueError("最终结果不是有效的Solid对象")

        volume = chamfered_flange.get_volume()
        print(f"    最终法兰体积: {volume:.2f} mm³")
        print(f"    法兰外径: {flange_outer_diameter}mm")
        print(f"    法兰内径: {flange_inner_diameter}mm")
        print(f"    法兰厚度: {flange_thickness}mm")
        print(f"    凸起圆环外径: {boss_outer_diameter}mm")
        print(f"    凸起圆环高度: {boss_height}mm")
        print(f"    连接孔: {hole_count}个，直径{hole_diameter}mm")

    except Exception as e:
        print(f"    错误: 步骤5验证失败 - {e}")
        raise ValueError(f"最终结果验证失败") from e

    print(f"{hole_count}孔法兰创建完成！")
    return chamfered_flange


def make_naca_propeller_blade_rsolid(
    blade_length=5.0,
    root_chord=1.5,
    tip_chord=0.3,
    total_twist_angle=45.0,
    num_sections=7,
    t_c=0.16,
) -> Solid:
    """Create a single propeller blade solid from a twisted NACA 0016 profile. The blade root starts at the origin and extends along +Z."""

    import math

    print(f"  参数: 长度={blade_length}, 根部弦长={root_chord}, 叶尖弦长={tip_chord}")
    print(f"  扭转角度={total_twist_angle}°, 截面数={num_sections}")

    def generate_naca_0016_points(chord_length=1.0, num_points=50):
        """Generate sample points for a NACA 0016 airfoil profile."""
        print(f"    生成NACA 0016翼型点，弦长={chord_length:.3f}")

        # NACA 0016翼型厚度分布函数
        # y/c = 0.16 * (0.2969*sqrt(x/c) - 0.1260*(x/c) - 0.3516*(x/c)^2 + 0.2843*(x/c)^3 - 0.1015*(x/c)^4)
        def naca_0016_thickness(x_c):
            """Return the NACA 0016 half-thickness at a given x/c position."""
            if x_c < 0 or x_c > 1:
                return 0.0
            return t_c * (
                0.2969 * math.sqrt(x_c)
                - 0.1260 * x_c
                - 0.3516 * x_c**2
                + 0.2843 * x_c**3
                - 0.1015 * x_c**4
            )

        points = []

        # 生成上表面点（从前缘到后缘）
        for i in range(num_points + 1):
            x_c = i / num_points  # x/c从0到1
            y_c = naca_0016_thickness(x_c)  # 上表面半厚度
            x = x_c * chord_length
            y = y_c * chord_length
            points.append((x, y, 0.0))

        # 生成下表面点（从后缘到前缘，排除重复的后缘点）
        for i in range(num_points - 1, -1, -1):
            x_c = i / num_points
            y_c = -naca_0016_thickness(x_c)  # 下表面负半厚度
            x = x_c * chord_length
            y = y_c * chord_length
            points.append((x, y, 0.0))

        print(f"    生成了 {len(points)} 个翼型点")
        return points

    try:
        # 步骤1: 生成各个径向位置的翼型截面
        print("  步骤1: 生成各个径向位置的翼型截面...")

        section_wires = []

        for i in range(num_sections):
            print(f"    创建第 {i + 1}/{num_sections} 个截面...")

            # 计算径向位置 (0到blade_length)
            r_i = (i / (num_sections - 1)) * blade_length
            print(f"      径向位置: {r_i:.3f}")

            # 计算当前弦长（线性插值）
            chord_ratio = r_i / blade_length
            chord_i = root_chord - chord_ratio * (root_chord - tip_chord)
            print(f"      弦长: {chord_i:.3f}")

            # 计算当前扭转角度（线性插值）
            twist_angle_i = chord_ratio * total_twist_angle
            print(f"      扭转角度: {twist_angle_i:.1f}°")

            # 生成当前弦长的NACA 0016翼型点
            airfoil_points = generate_naca_0016_points(chord_i, num_points=30)

            # 创建基础翼型线
            airfoil_wire = make_spline_rwire(airfoil_points, closed=True)
            print(f"      基础翼型线创建成功")

            # 先绕Z轴旋转（扭转角度）
            if abs(twist_angle_i) > 1e-6:  # 如果扭转角度不为零
                airfoil_wire = rotate_shape(
                    airfoil_wire, twist_angle_i, (0, 0, 1), (0, 0, 0)
                )  # type: ignore
                print(f"      翼型扭转完成: {twist_angle_i:.1f}°")

            # 然后平移到径向位置
            airfoil_wire = translate_shape(airfoil_wire, (0, 0, r_i))  # type: ignore
            print(f"      翼型平移到径向位置: Z={r_i:.3f}")

            section_wires.append(airfoil_wire)

    except Exception as e:
        print(f"    错误: 步骤1生成翼型截面失败 - {e}")
        raise ValueError(f"翼型截面生成失败，可能是NACA翼型计算或几何变换失败") from e

    try:
        # 步骤2: 通过放样创建桨叶实体
        print("  步骤2: 通过放样创建桨叶实体...")

        # 验证截面数量
        if len(section_wires) < 2:
            raise ValueError(
                f"截面数量不足：需要至少2个截面，当前有{len(section_wires)}个"
            )

        print(f"    准备放样 {len(section_wires)} 个截面...")

        # 使用放样创建实体
        blade_solid = loft_rsolid(section_wires, ruled=False)
        print(f"    放样完成")

        # 验证结果
        if not isinstance(blade_solid, Solid):
            raise ValueError("放样结果不是有效的Solid对象")

        print(f"    桨叶体积: {blade_solid.get_volume():.6f}")

    except Exception as e:
        print(f"    错误: 步骤2放样创建实体失败 - {e}")
        raise ValueError(f"放样操作失败，可能是截面几何不兼容或放样算法失败") from e

    print("螺旋桨叶片创建完成！")
    print(f"最终参数总结:")
    print(f"  - 叶片长度: {blade_length}")
    print(f"  - 根部弦长: {root_chord} -> 叶尖弦长: {tip_chord}")
    print(f"  - 总扭转: {total_twist_angle}°")
    print(f"  - 截面数: {num_sections}")
    print(f"  - 厚度比: {t_c}")

    return blade_solid


def make_threaded_rod_rsolid(
    thread_diameter=8.0,
    thread_length=20.0,
    total_length=30.0,
    thread_pitch=1.25,
    thread_start_position=0.0,
    chamfer_size=0.5,
) -> Solid:
    """Create a threaded rod with configurable rod length, thread span, and pitch. The top center is placed at the origin and the rod extends in -Z."""
    print(f"开始创建螺杆...")
    print(f"  参数: 直径={thread_diameter}mm, 总长度={total_length}mm")
    print(
        f"  螺纹: 长度={thread_length}mm, 螺距={thread_pitch}mm, 起始位置={thread_start_position}mm"
    )

    from typing import cast
    import math

    # 参数验证
    if thread_diameter <= 0:
        raise ValueError("螺纹直径必须大于0")
    if total_length <= 0:
        raise ValueError("螺杆总长度必须大于0")
    if thread_length <= 0:
        raise ValueError("螺纹长度必须大于0")
    if thread_pitch <= 0:
        raise ValueError("螺纹螺距必须大于0")
    if thread_length > total_length:
        raise ValueError("螺纹长度不能大于螺杆总长度")
    if (
        thread_start_position < 0
        or thread_start_position + thread_length > total_length
    ):
        raise ValueError("螺纹起始位置或结束位置超出螺杆范围")

    try:
        # 步骤1: 创建螺杆主体
        print("  步骤1: 创建螺杆主体...")

        thread_radius = thread_diameter / 2.0
        thread_face = make_circle_rface((0, 0, 0), thread_radius)
        thread_solid = extrude_rsolid(thread_face, (0, 0, 1), total_length)
        print(
            f"    螺杆主体创建成功，直径: {thread_diameter}mm，长度: {total_length}mm"
        )

    except Exception as e:
        print(f"    错误: 步骤1创建螺杆主体失败 - {e}")
        raise ValueError(f"螺杆主体创建失败，可能是螺杆参数无效") from e

    try:
        # 步骤2: 创建螺纹切割体
        print("  步骤2: 创建螺纹切割体...")

        # 计算螺纹深度（根据标准螺纹深度约为螺距的0.613倍）
        thread_depth = thread_pitch * 0.613  # 约0.766mm for M8

        # 定义V型螺纹切割轮廓的顶点
        thread_points = [
            (float(thread_radius), 0.0, 0.0),  # 螺纹大径处，轴向位置0
            (
                float(thread_radius - thread_depth),
                float(thread_pitch * 0.5),
                0.0,
            ),  # 螺纹根部，轴向偏移pitch/2
            (
                float(thread_radius),
                float(thread_pitch),
                0.0,
            ),  # 螺纹大径处，轴向偏移pitch
        ]

        # 创建V型螺纹切割轮廓
        thread_cut_wire = make_polyline_rwire(thread_points, closed=True)
        print(f"    V型螺纹切割轮廓创建成功，螺纹深度: {thread_depth:.3f}mm")

        # 使用螺旋扫掠创建螺纹切割体
        helical_cut_solid = helical_sweep_rsolid(
            thread_cut_wire, thread_pitch, thread_length, thread_radius
        )

        # 调整螺旋切割体位置到螺纹起始位置
        translated_helical_cut = translate_shape(
            helical_cut_solid, (0, 0, -thread_length - thread_start_position)
        )
        helical_cut_solid = cast(Solid, translated_helical_cut)
        print(
            f"    螺旋切割体创建成功，螺距: {thread_pitch}mm，起始位置: {thread_start_position}mm"
        )

    except Exception as e:
        print(f"    错误: 步骤2创建螺纹切割体失败 - {e}")
        raise ValueError(f"螺纹切割体创建失败，可能是螺纹参数无效或螺旋扫掠失败") from e

    try:
        # 步骤3: 从螺杆中减去螺纹切割体形成螺纹
        print("  步骤3: 切割螺纹...")

        thread_solid_results = cut_rsolidlist(thread_solid, helical_cut_solid)
        if len(thread_solid_results) != 1:
            raise ValueError("螺纹切割结果不是单个实体，请检查参数设置。")
        thread_solid = thread_solid_results[0]
        print("    螺纹切割完成")

    except Exception as e:
        print(f"    错误: 步骤3切割螺纹失败 - {e}")
        raise ValueError(f"螺纹切割失败，可能是几何运算失败") from e

    try:
        # 步骤4: 添加螺杆末端倒角
        print("  步骤4: 添加螺杆末端倒角...")

        # 获取螺杆的边进行倒角
        thread_edges = thread_solid.get_edges()
        # 选择螺杆底端的边进行倒角（通常是圆形边）
        bottom_edges = thread_edges[:1]  # 简单选择前几条边

        # 对螺杆末端进行倒角处理
        thread_solid = chamfer_rsolid(thread_solid, bottom_edges, chamfer_size)
        print(f"    螺杆末端倒角完成，倒角尺寸: {chamfer_size}mm")

    except Exception as e:
        print(f"    错误: 步骤4添加螺杆末端倒角失败 - {e}")
        print(f"    跳过倒角处理，继续使用原始螺杆")
        # 倒角失败时继续使用原始螺杆

    try:
        # 步骤5: 验证最终结果
        print("  步骤5: 验证最终结果...")

        if not isinstance(thread_solid, Solid):
            raise ValueError("最终结果不是有效的Solid对象")

        volume = thread_solid.get_volume()
        print(f"    最终螺杆体积: {volume:.2f} mm³")
        print(f"    螺杆直径: {thread_diameter}mm")
        print(f"    螺杆总长度: {total_length}mm")
        print(f"    螺纹长度: {thread_length}mm")
        print(f"    螺纹螺距: {thread_pitch}mm")
        print(f"    螺纹起始位置: {thread_start_position}mm")

    except Exception as e:
        print(f"    错误: 步骤5验证失败 - {e}")
        raise ValueError(f"最终结果验证失败") from e

    print("螺杆创建完成！")
    return thread_solid
