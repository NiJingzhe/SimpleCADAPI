---
label: boolean
category: solid
api:
  - union_rsolid
  - cut_rsolid
  - intersect_rsolid
reads:
  - operand overlap regions
  - resulting seam edges
doc_refs:
  - docs/skill/references/domains/part-modeling.md
  - docs/skill/references/discipline/feature-tree-convention.md
---

FTC dataflow: `body = op(body, tools)`. Watch `skip_non_intersecting=True`
silently dropping tangent tools, and tag seam edges immediately after the
boolean if a blend follows.
