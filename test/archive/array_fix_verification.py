"""
SimpleCAD API 阵列操作修复验证
总结测试：验证所有阵列功能都已正确实现并正常工作
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

try:
    from simplecadapi import *
    import math
    
    print("=" * 60)
    print("SimpleCAD API 阵列操作修复验证")
    print("=" * 60)
    
    # 创建基础测试几何体
    test_box = make_box(0.2, 0.2, 0.2)
    test_cylinder = make_cylinder(0.1, 0.3)
    
    print(f"✓ 基础几何体创建成功")
    
    # 1. 线性阵列测试
    print("\n1. 线性阵列测试...")
    
    tests = [
        # (名称, 方向, 数量, 间距, 期望实体数)
        ("X方向", (1, 0, 0), 5, 0.3, 5),
        ("Y方向", (0, 1, 0), 3, 0.4, 3),
        ("Z方向", (0, 0, 1), 4, 0.5, 4),
        ("XY对角", (1, 1, 0), 3, 0.4, 3),
        ("XYZ对角", (1, 1, 1), 2, 0.6, 2),
    ]
    
    linear_results = []
    for name, direction, count, spacing, expected in tests:
        try:
            result = pattern_linear(test_box, direction=direction, count=count, spacing=spacing)
            actual = result.cq_solid.solids().size()
            success = actual == expected
            status = "✓" if success else "✗"
            print(f"  {status} {name}: {actual}/{expected} 实体")
            linear_results.append(success)
        except Exception as e:
            print(f"  ✗ {name}: 失败 - {e}")
            linear_results.append(False)
    
    # 2. 2D阵列测试
    print("\n2. 2D阵列测试...")
    
    d2_tests = [
        # (名称, x方向, y方向, x数量, y数量, x间距, y间距, 期望实体数)
        ("正交网格", (1, 0, 0), (0, 1, 0), 3, 2, 0.3, 0.4, 6),
        ("倾斜网格", (1, 0.5, 0), (0, 1, 0.2), 2, 3, 0.4, 0.3, 6),
        ("大网格", (1, 0, 0), (0, 1, 0), 4, 3, 0.5, 0.5, 12),
    ]
    
    d2_results = []
    for name, x_dir, y_dir, x_count, y_count, x_spacing, y_spacing, expected in d2_tests:
        try:
            result = pattern_2d(
                body=test_cylinder,
                x_direction=x_dir, y_direction=y_dir,
                x_count=x_count, y_count=y_count,
                x_spacing=x_spacing, y_spacing=y_spacing
            )
            actual = result.cq_solid.solids().size()
            success = actual == expected
            status = "✓" if success else "✗"
            print(f"  {status} {name}: {actual}/{expected} 实体")
            d2_results.append(success)
        except Exception as e:
            print(f"  ✗ {name}: 失败 - {e}")
            d2_results.append(False)
    
    # 3. 径向阵列测试
    print("\n3. 径向阵列测试...")
    
    radial_tests = [
        # (名称, 轴向, 数量, 角度, 期望实体数)
        ("完整圆周", (0, 0, 1), 8, 2*math.pi, 8),
        ("半圆", (0, 0, 1), 4, math.pi, 4),
        ("四分之一圆", (0, 0, 1), 3, math.pi/2, 3),
        ("绕X轴", (1, 0, 0), 6, 2*math.pi, 6),
    ]
    
    radial_results = []
    center = make_point(0, 0, 0)
    for name, axis, count, angle, expected in radial_tests:
        try:
            result = pattern_radial(
                body=test_box,
                center=center,
                axis=axis,
                count=count,
                angle=angle
            )
            actual = result.cq_solid.solids().size()
            success = actual == expected
            status = "✓" if success else "✗"
            print(f"  {status} {name}: {actual}/{expected} 实体")
            radial_results.append(success)
        except Exception as e:
            print(f"  ✗ {name}: 失败 - {e}")
            radial_results.append(False)
    
    # 4. 导出验证测试
    print("\n4. 导出验证测试...")
    
    export_tests = [
        (pattern_linear(test_box, (1, 0, 0), 3, 0.4), "output/final_test_linear.stl"),
        (pattern_2d(test_cylinder, (1, 0, 0), (0, 1, 0), 2, 2, 0.4, 0.4), "output/final_test_2d.stl"),
        (pattern_radial(test_box, center, (0, 0, 1), 6, 2*math.pi), "output/final_test_radial.stl"),
    ]
    
    export_results = []
    for i, (body, filename) in enumerate(export_tests, 1):
        try:
            import cadquery as cq
            cq.exporters.export(body.cq_solid, filename)
            print(f"  ✓ 导出测试 {i}: {filename}")
            export_results.append(True)
        except Exception as e:
            print(f"  ✗ 导出测试 {i}: 失败 - {e}")
            export_results.append(False)
    
    # 总结报告
    print("\n" + "=" * 60)
    print("修复验证总结报告")
    print("=" * 60)
    
    linear_success = sum(linear_results)
    d2_success = sum(d2_results)
    radial_success = sum(radial_results)
    export_success = sum(export_results)
    
    print(f"线性阵列: {linear_success}/{len(linear_results)} 通过")
    print(f"2D阵列: {d2_success}/{len(d2_results)} 通过")
    print(f"径向阵列: {radial_success}/{len(radial_results)} 通过")
    print(f"导出测试: {export_success}/{len(export_results)} 通过")
    
    total_tests = len(linear_results) + len(d2_results) + len(radial_results) + len(export_results)
    total_success = linear_success + d2_success + radial_success + export_success
    
    print(f"\n总计: {total_success}/{total_tests} 测试通过")
    
    if total_success == total_tests:
        print("\n🎉 所有阵列操作修复验证通过！")
        print("✓ 阵列功能现在已完全正常工作")
        print("✓ 实体数量统计正确")
        print("✓ 支持线性、2D和径向阵列")
        print("✓ 导出功能正常")
    else:
        print(f"\n⚠️  有 {total_tests - total_success} 个测试失败")
        print("需要进一步调试和修复")
    
    print("=" * 60)
    
except Exception as e:
    print(f"验证测试失败: {e}")
    import traceback
    traceback.print_exc()
