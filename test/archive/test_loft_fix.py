#!/usr/bin/env python3
"""
测试放样操作修复
"""

from src.simplecadapi.operations import *

def test_loft_operations():
    """测试放样操作"""
    print("=== 测试放样操作 ===")
    
    try:
        # 创建底部矩形 (2x2)
        bottom_rect = make_rectangle(2, 2)
        print(f"✓ 底部矩形创建成功: {bottom_rect}")
        
        # 创建顶部矩形 (1x1，偏移在Z=3处)
        top_rect = make_rectangle(1, 1)
        print(f"✓ 顶部矩形创建成功: {top_rect}")
        
        # 执行放样
        lofted_body = loft([bottom_rect, top_rect])
        print(f"✓ 放样操作成功: {lofted_body}")
        
        # 创建另一个实体用于布尔运算
        cube = make_box(1.5, 1.5, 1.5)
        print(f"✓ 立方体创建成功: {cube}")
        
        # 测试布尔并运算
        union_result = union(lofted_body, cube)
        print(f"✓ 布尔并运算成功: {union_result}")
        
        # 测试布尔减运算
        cut_result = cut(lofted_body, cube)
        print(f"✓ 布尔减运算成功: {cut_result}")
        
        # 测试布尔交运算
        intersect_result = intersect(lofted_body, cube)
        print(f"✓ 布尔交运算成功: {intersect_result}")
        
        print("✓ 所有测试通过！")
        return True
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        return False

def test_multiple_loft():
    """测试多层放样"""
    print("\n=== 测试多层放样 ===")
    
    try:
        # 创建多个截面
        sections = []
        
        # 底部: 大矩形 (4x4)
        sections.append(make_rectangle(4, 4))
        
        # 中部: 中等矩形 (2x2)
        sections.append(make_rectangle(2, 2))
        
        # 顶部: 小矩形 (1x1)
        sections.append(make_rectangle(1, 1))
        
        print(f"✓ 创建了 {len(sections)} 个截面")
        
        # 执行多层放样
        multi_loft = loft(sections)
        print(f"✓ 多层放样成功: {multi_loft}")
        
        # 与另一个实体进行布尔运算
        cylinder = make_cylinder(1.0, 5.0)
        print(f"✓ 圆柱体创建成功: {cylinder}")
        
        # 布尔运算
        final_result = union(multi_loft, cylinder)
        print(f"✓ 复杂布尔运算成功: {final_result}")
        
        print("✓ 多层放样测试通过！")
        return True
        
    except Exception as e:
        print(f"✗ 多层放样测试失败: {e}")
        return False

if __name__ == "__main__":
    print("测试放样操作修复\n" + "="*50)
    
    success1 = test_loft_operations()
    success2 = test_multiple_loft()
    
    if success1 and success2:
        print(f"\n{'='*50}")
        print("✓ 所有测试都通过了！放样操作修复成功。")
    else:
        print(f"\n{'='*50}")
        print("✗ 某些测试失败，需要进一步调试。")
