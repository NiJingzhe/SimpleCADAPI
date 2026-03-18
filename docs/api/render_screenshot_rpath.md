# render_screenshot_rpath

## API Definition

```python
def render_screenshot_rpath(shapes: Union[Solid, Sequence[Solid]], output_path: str, highlight_tags: Optional[Sequence[str]] = None, tag_labels: Optional[Dict[str, str]] = None, image_size: Tuple[int, int] = (1400, 900), view: Union[Tuple[float, float], str] = 'auto', show_axes: bool = True, show_legend: bool = True, zoom: float = 4.0) -> str
```

*Source: operations.py*

## Description

渲染几何体截图并保存到文件。

生成截图并高亮指定标签。

## Parameters

### shapes

- **Description**: 要渲染的实体或实体列表。

### output_path

- **Description**: 输出图片路径（PNG）。

### highlight_tags

- **Description**: 需要高亮的标签列表（对Solid或Face生效）。

### tag_labels

- **Description**: 标签显示名映射。

### image_size

- **Description**: 输出图片尺寸 (width, height)。

### view

- **Description**: 视角 (elev, azim) 或预设名称（auto/iso/top/bottom/front/back/left/right）。

### show_axes

- **Description**: 是否显示XYZ正方向。

### show_legend

- **Description**: 是否在左上角显示标签图例。

### zoom

- **Description**: 视图边距缩放倍率（>1 减少边距使模型更大，仍保持不裁剪）。

## Returns

str: 输出文件路径。

## Raises

- **ValueError**: 当输入几何体无效或渲染失败时抛出异常。

## Examples

```python
box = make_box_rsolid(4, 3, 2)
render_screenshot_rpath(box, "preview.png", highlight_tags=["top"])
```
