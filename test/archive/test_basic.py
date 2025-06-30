"""
测试SimpleCAD API的基本功能
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

try:
    # 测试基本导入
    from simplecadapi.core import Point, Line, Sketch, Body, CoordinateSystem, LocalCoordinateSystem
    from simplecadapi.operations import make_point, make_line, make_rectangle, make_box
    
    print("✓ 导入成功")
    
    # 测试基本点创建
    p1 = make_point(0, 0, 0)
    p2 = make_point(1, 0, 0)
    print(f"✓ 点创建成功: {p1}, {p2}")
    
    # 测试线创建
    line = make_line([p1, p2])
    print(f"✓ 线创建成功: {line}")
    
    # 测试矩形创建
    rect = make_rectangle(2.0, 1.0)
    print(f"✓ 矩形创建成功: {rect}")
    
    # 测试立方体创建
    box = make_box(1.0, 1.0, 1.0)
    print(f"✓ 立方体创建成功: {box}")
    print(f"立方体体积: {box.volume()}")
    
    # 测试坐标系
    with LocalCoordinateSystem(origin=(1, 1, 1), x_axis=(0, 1, 0), y_axis=(-1, 0, 0)):
        p3 = make_point(0, 0, 0)
        print(f"✓ 局部坐标系测试成功: {p3}")
        print(f"全局坐标: {p3.global_coords}")
    
    print("所有基本测试通过!")
    
except Exception as e:
    print(f"测试失败: {e}")
    import traceback
    traceback.print_exc()
