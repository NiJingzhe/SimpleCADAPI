# stack

## API定义

```python
def stack(assembly: Assembly, parts: Sequence[Union[str, PartHandle]], axis: str = 'z', gap: float = 0.0, align: Literal['center', 'start', 'end'] = 'center', justify: Literal['start', 'center', 'end', 'space-between'] = 'start', bounds: Optional[Tuple[PointAnchor, PointAnchor]] = None) -> Assembly
```

*来源文件: constraints.py*

## API作用

沿指定轴将多个零件做声明式堆叠。

语义：
- 顺序堆叠：第i个零件贴在第i-1个零件之后，并留出 gap
- 横向对齐：在其余两个轴上按 align 对齐
- 主轴分布：通过 justify 控制整体在边界中的分布方式

BBox-first 说明：
- 本函数使用轴对齐包围盒（AABB）锚点（如 `bbox.top` / `bbox.bottom`）
来近似 Flexbox 的盒模型语义。
- 对发生大角度旋转的零件，AABB 会随姿态变化，布局结果也会随之变化。
这是当前 MVP 阶段的预期行为。

注意：
- 这是容器语法糖，内部会编译成若干 `offset(...)` 约束。
