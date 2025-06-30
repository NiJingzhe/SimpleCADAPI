# get_face_info

## 定义
```python
def get_face_info(body: Body, tag: Optional[str] = None) -> dict
```

## 作用
获取实体面的详细信息。该函数用于查询实体的面数量、标签分布、以及特定面的几何属性（如中心点、法向量、面积等）。这是CAD模型分析和调试的重要工具。

**参数说明：**
- `body`: 要查询的实体
- `tag`: 可选，指定面标签，None表示获取所有面信息

**返回值：**
- 返回包含面信息的字典，包含以下键：
  - `total_faces`: 总面数
  - `tagged_faces`: 各标签对应的面数量
  - `face_details`: 特定标签面的详细信息（如指定tag时）

## 示例代码

### 基础面信息查询
```python
from simplecadapi.operations import *

# 创建立方体
cube = make_box(20, 20, 20, center=True)

# 查询未标记状态的面信息
info_before = get_face_info(cube)
print("未标记状态:")
print(f"总面数: {info_before['total_faces']}")
print(f"已标记面: {info_before['tagged_faces']}")

# 标记面后查询
tag_faces_automatically(cube, "box")
info_after = get_face_info(cube)
print("\n标记后状态:")
print(f"总面数: {info_after['total_faces']}")
print(f"标记分布: {info_after['tagged_faces']}")
```

### 圆柱体面信息分析
```python
from simplecadapi.operations import *

# 创建圆柱体
cylinder = make_cylinder(radius=12, height=25)
tag_faces_automatically(cylinder, "cylinder")

# 获取完整面信息
cylinder_info = get_face_info(cylinder)
print("圆柱体面信息:")
print(f"总面数: {cylinder_info['total_faces']}")
print("各标签面数:")
for tag, count in cylinder_info['tagged_faces'].items():
    print(f"  {tag}: {count} 个")

export_stl(cylinder, "output/analyzed_cylinder.stl")
```

### 特定面详细信息
```python
from simplecadapi.operations import *

# 创建并标记立方体
detailed_cube = make_box(30, 20, 15, center=True)
tag_faces_automatically(detailed_cube, "box")

# 获取顶面详细信息
top_info = get_face_info(detailed_cube, "top")
print("顶面详细信息:")
print(f"总面数: {top_info['total_faces']}")
print(f"面详情数量: {len(top_info['face_details'])}")

# 显示面的几何属性
for detail in top_info['face_details']:
    if 'center' in detail:
        center = detail['center']
        normal = detail['normal']
        area = detail['area']
        print(f"  中心点: ({center[0]:.2f}, {center[1]:.2f}, {center[2]:.2f})")
        print(f"  法向量: ({normal[0]:.2f}, {normal[1]:.2f}, {normal[2]:.2f})")
        print(f"  面积: {area:.2f}")
```

### 复杂几何体分析
```python
from simplecadapi.operations import *

# 创建复杂几何体
base_box = make_box(40, 30, 10, center=True)
top_cylinder = make_cylinder(radius=12, height=15)
complex_body = union(base_box, top_cylinder)

# 标记复杂几何体
tag_faces_automatically(complex_body, "auto")

# 分析复杂几何体
complex_info = get_face_info(complex_body)
print("复杂几何体分析:")
print(f"总面数: {complex_info['total_faces']}")
print(f"标记标签数: {len(complex_info['tagged_faces'])}")
print("标签分布:")
for tag, count in complex_info['tagged_faces'].items():
    print(f"  {tag}: {count} 个面")

export_stl(complex_body, "output/analyzed_complex.stl")
```

### 面信息对比分析
```python
from simplecadapi.operations import *

# 创建不同几何体进行对比
geometries = {
    "cube": make_box(20, 20, 20, center=True),
    "rectangle": make_box(30, 20, 10, center=True),
    "cylinder": make_cylinder(radius=10, height=20),
    "sphere": make_sphere(radius=12)
}

print("几何体面信息对比:")
print("-" * 50)

for name, geo in geometries.items():
    # 标记面
    tag_faces_automatically(geo, "auto")
    
    # 获取信息
    info = get_face_info(geo)
    
    print(f"{name.upper()}:")
    print(f"  总面数: {info['total_faces']}")
    print(f"  标签类型: {list(info['tagged_faces'].keys())}")
    print(f"  标记面总数: {sum(info['tagged_faces'].values())}")
    print()
```

### 面积分析
```python
from simplecadapi.operations import *

# 创建测试立方体
analysis_cube = make_box(25, 25, 25, center=True)
tag_faces_automatically(analysis_cube, "box")

# 分析各面的面积
face_tags = ["top", "bottom", "front", "back", "left", "right"]
total_area = 0

print("立方体各面面积分析:")
for tag in face_tags:
    face_info = get_face_info(analysis_cube, tag)
    
    if face_info['face_details']:
        for detail in face_info['face_details']:
            if 'area' in detail:
                area = detail['area']
                total_area += area
                print(f"{tag}面: {area:.2f} 平方单位")

print(f"总表面积: {total_area:.2f} 平方单位")
print(f"理论面积: {6 * 25 * 25} 平方单位")  # 6个25x25的面
```

### 法向量分析
```python
from simplecadapi.operations import *

# 创建圆柱体进行法向量分析
vector_cylinder = make_cylinder(radius=15, height=30)
tag_faces_automatically(vector_cylinder, "cylinder")

# 分析各面的法向量
face_types = ["top", "bottom", "side"]
print("圆柱体法向量分析:")

for face_type in face_types:
    face_info = get_face_info(vector_cylinder, face_type)
    
    if face_info['face_details']:
        for i, detail in enumerate(face_info['face_details']):
            if 'normal' in detail:
                normal = detail['normal']
                print(f"{face_type}面 {i}: 法向量({normal[0]:.3f}, {normal[1]:.3f}, {normal[2]:.3f})")
```

### 面信息验证
```python
from simplecadapi.operations import *

# 创建验证几何体
validation_box = make_box(20, 15, 10, center=True)

# 验证标记前后的信息变化
print("验证面信息变化:")

# 标记前
before_info = get_face_info(validation_box)
print("标记前:")
print(f"  总面数: {before_info['total_faces']}")
print(f"  已标记: {sum(before_info['tagged_faces'].values())}")

# 标记
tag_faces_automatically(validation_box, "box")

# 标记后
after_info = get_face_info(validation_box)
print("标记后:")
print(f"  总面数: {after_info['total_faces']}")
print(f"  已标记: {sum(after_info['tagged_faces'].values())}")
print(f"  标签: {list(after_info['tagged_faces'].keys())}")

# 验证面数一致性
if before_info['total_faces'] == after_info['total_faces']:
    print("✓ 面数一致")
else:
    print("✗ 面数不一致")
```

### 错误和异常处理
```python
from simplecadapi.operations import *

# 创建测试几何体
error_test = make_cylinder(radius=8, height=16)
tag_faces_automatically(error_test, "cylinder")

# 测试正常查询
try:
    normal_info = get_face_info(error_test)
    print("正常查询成功:")
    print(f"  总面数: {normal_info['total_faces']}")
except Exception as e:
    print(f"正常查询失败: {e}")

# 测试无效标签查询
try:
    invalid_info = get_face_info(error_test, "nonexistent_tag")
    print("无效标签查询:")
    print(f"  面详情: {len(invalid_info['face_details'])}")  # 应该为空
except Exception as e:
    print(f"无效标签查询失败: {e}")

# 测试存在标签查询
try:
    valid_info = get_face_info(error_test, "top")
    print("有效标签查询:")
    print(f"  面详情: {len(valid_info['face_details'])}")
except Exception as e:
    print(f"有效标签查询失败: {e}")
```

### 批量面信息统计
```python
from simplecadapi.operations import *

# 创建多个几何体
batch_geometries = [
    make_box(10, 10, 10, center=True),
    make_box(20, 15, 8, center=True),
    make_cylinder(radius=6, height=12),
    make_cylinder(radius=10, height=20),
    make_sphere(radius=8),
    make_sphere(radius=15)
]

# 批量分析
print("批量面信息统计:")
print("-" * 60)

total_faces = 0
total_tagged = 0

for i, geo in enumerate(batch_geometries):
    tag_faces_automatically(geo, "auto")
    info = get_face_info(geo)
    
    faces = info['total_faces']
    tagged = sum(info['tagged_faces'].values())
    
    total_faces += faces
    total_tagged += tagged
    
    print(f"几何体 {i+1}: {faces} 个面, {tagged} 个已标记, "
          f"标签: {list(info['tagged_faces'].keys())}")

print("-" * 60)
print(f"总计: {total_faces} 个面, {total_tagged} 个已标记")
print(f"标记率: {total_tagged/total_faces*100:.1f}%")
```

### 面信息导出
```python
from simplecadapi.operations import *

# 创建分析对象
export_analysis = make_box(30, 25, 20, center=True)
tag_faces_automatically(export_analysis, "box")

# 获取完整信息
full_info = get_face_info(export_analysis)

# 模拟导出面信息报告
print("面信息报告:")
print("=" * 40)
print(f"模型总面数: {full_info['total_faces']}")
print(f"标记面统计: {full_info['tagged_faces']}")
print()

# 详细面分析
for tag in full_info['tagged_faces']:
    tag_info = get_face_info(export_analysis, tag)
    print(f"{tag.upper()}面详情:")
    
    for detail in tag_info['face_details']:
        if 'center' in detail:
            print(f"  中心: {detail['center']}")
            print(f"  法向: {detail['normal']}")
            print(f"  面积: {detail['area']:.2f}")
        print()

export_stl(export_analysis, "output/face_analyzed_model.stl")
```

## 注意事项
1. 返回的信息依赖于面是否已被标记
2. 未标记的面不会出现在 `face_details` 中
3. 几何属性计算可能因面的复杂程度而失败
4. `tag` 参数为 None 时返回总体信息，指定标签时返回该标签面的详情
5. 复杂曲面的法向量可能不准确
6. 面积计算使用CADQuery的内置方法
7. 函数主要用于调试和模型验证
8. 对于大型复杂模型，信息查询可能较慢
