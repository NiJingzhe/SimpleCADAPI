"""
SimpleCAD API 使用示例
展示README中描述的API设计理念和使用方法
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from simplecadapi import *
import math

def basic_geometry_example():
    """基础几何操作示例"""
    print("=== 基础几何操作示例 ===")
    
    # 创建点
    p1 = make_point(0, 0, 0)
    p2 = make_point(1, 1, 0)
    print(f"创建点: {p1}, {p2}")
    
    # 创建线段
    line = make_line([p1, p2], "segment")
    print(f"创建线段: {line}")
    
    # 创建矩形草图
    rect = make_rectangle(2.0, 1.0, center=True)
    print(f"创建矩形草图: {rect}")
    
    # 创建圆形草图
    circle = make_circle(0.5)
    print(f"创建圆形草图: {circle}")


def primitive_solids_example():
    """基本实体创建示例"""
    print("\n=== 基本实体创建示例 ===")
    
    # 创建立方体
    box = make_box(2.0, 1.0, 0.5, center=True)
    print(f"创建立方体: {box}, 体积: {box.volume()}")
    
    # 创建圆柱体
    cylinder = make_cylinder(0.5, 2.0)
    print(f"创建圆柱体: {cylinder}, 体积: {cylinder.volume()}")
    
    # 创建球体
    sphere = make_sphere(1.0)
    print(f"创建球体: {sphere}, 体积: {sphere.volume()}")


def modeling_operations_example():
    """建模操作示例"""
    print("\n=== 建模操作示例 ===")
    
    try:
        # 拉伸操作
        rect = make_rectangle(1.0, 1.0)
        extruded = extrude(rect, distance=2.0)
        print(f"拉伸矩形创建立方体: {extruded}")
        
        # 旋转操作
        # 创建一个半圆轮廓进行旋转
        center = make_point(0, 0, 0)
        edge = make_point(1, 0, 0) 
        top = make_point(0.5, 0, 1)
        
        # 创建半圆弧（简化为三角形）
        half_circle_lines = [
            make_line([center, edge], "segment"),
            make_line([edge, top], "segment"),
            make_line([top, center], "segment")
        ]
        half_circle = make_sketch(half_circle_lines)
        
        # 绕Z轴旋转
        axis_start = make_point(0, 0, -1)
        axis_end = make_point(0, 0, 1)
        revolved = revolve(half_circle, axis_start, axis_end, math.pi)
        print(f"旋转半圆创建实体: {revolved}")
        
    except Exception as e:
        print(f"建模操作示例出错: {e}")


def coordinate_system_example():
    """坐标系使用示例"""
    print("\n=== 坐标系使用示例 ===")
    
    # 在世界坐标系中创建点
    world_point = make_point(1, 2, 3)
    print(f"世界坐标系中的点: {world_point}")
    print(f"全局坐标: {world_point.global_coords}")
    
    # 使用局部坐标系
    with LocalCoordinateSystem(origin=(10, 5, 0), 
                             x_axis=(0, 1, 0), 
                             y_axis=(-1, 0, 0)) as local_cs:
        
        # 在局部坐标系中创建点
        local_point = make_point(0, 0, 0)  # 局部原点
        local_point2 = make_point(3, 2, 0)  # 局部坐标 (3,2,0)
        
        print(f"局部坐标系中的点1: {local_point}")
        print(f"全局坐标: {local_point.global_coords}")
        print(f"局部坐标系中的点2: {local_point2}")
        print(f"全局坐标: {local_point2.global_coords}")
        
        # 在局部坐标系中创建几何体
        local_box = make_box(1.0, 1.0, 1.0, center=True)
        print(f"局部坐标系中的立方体: {local_box}")


def boolean_operations_example():
    """布尔运算示例"""
    print("\n=== 布尔运算示例 ===")
    
    try:
        # 创建两个立方体
        box1 = make_box(2.0, 2.0, 2.0, center=True)
        box2 = make_box(1.0, 1.0, 3.0, center=True)
        
        # 布尔并运算
        union_result = union(box1, box2)
        print(f"布尔并运算结果: {union_result}")
        
        # 布尔减运算
        cut_result = cut(box1, box2)
        print(f"布尔减运算结果: {cut_result}")
        
        # 布尔交运算
        intersect_result = intersect(box1, box2)
        print(f"布尔交运算结果: {intersect_result}")
        
    except Exception as e:
        print(f"布尔运算示例出错: {e}")


def advanced_operations_example():
    """高级操作示例"""
    print("\n=== 高级操作示例 ===")
    
    try:
        # 创建基础实体
        base_box = make_box(0.5, 0.5, 0.5, center=True)
        
        # 线性阵列
        array_result = pattern_linear(base_box, direction=(1, 0, 0), count=3, spacing=1.0)
        print(f"线性阵列结果: {array_result}, 实体数: {array_result.cq_solid.solids().size()}")
        
        # 2D阵列
        array_2d = pattern_2d(
            body=base_box,
            x_direction=(1, 0, 0),
            y_direction=(0, 1, 0),
            x_count=3, y_count=2,
            x_spacing=0.8, y_spacing=0.8
        )
        print(f"2D阵列结果: {array_2d}, 实体数: {array_2d.cq_solid.solids().size()}")
        
        # 径向阵列
        center_point = make_point(0, 0, 0)
        radial_array = pattern_radial(
            body=base_box,
            center=center_point,
            axis=(0, 0, 1),
            count=6,
            angle=2 * math.pi
        )
        print(f"径向阵列结果: {radial_array}, 实体数: {radial_array.cq_solid.solids().size()}")
        
        # 圆角操作
        filleted = fillet(base_box, [], radius=0.1)
        print(f"圆角操作结果: {filleted}")
        
        # 倒角操作  
        chamfered = chamfer(base_box, [], distance=0.1)
        print(f"倒角操作结果: {chamfered}")
        
    except Exception as e:
        print(f"高级操作示例出错: {e}")


def design_principle_demonstration():
    """设计原则演示"""
    print("\n=== 设计原则演示 ===")
    
    print("1. 开放封闭原则 (OCP):")
    print("   - 核心几何类 (Point, Line, Sketch, Body) 封闭修改")
    print("   - 操作函数开放扩展")
    print("   - 所有操作都是独立函数，不修改核心类")
    
    print("\n2. 坐标系管理:")
    print("   - 显式的坐标系上下文管理")
    print("   - 局部坐标自动转换为全局坐标")
    print("   - 支持嵌套坐标系")
    
    print("\n3. 类型安全:")
    print("   - 严格的几何类型分离")
    print("   - 点→线→草图→实体的递进构造")
    print("   - 类型检查防止无效操作")
    
    print("\n4. 可扩展性:")
    print("   - 基于CADQuery的强大底层")
    print("   - 简化的高层API")
    print("   - 易于添加新操作")


if __name__ == "__main__":
    print("SimpleCAD API 使用示例演示")
    print("=" * 50)
    
    try:
        basic_geometry_example()
        primitive_solids_example()
        modeling_operations_example()
        coordinate_system_example()
        boolean_operations_example()
        advanced_operations_example()
        design_principle_demonstration()
        
        print("\n" + "=" * 50)
        print("✓ 所有示例运行完成！")
        
    except Exception as e:
        print(f"\n示例运行出错: {e}")
        import traceback
        traceback.print_exc()
