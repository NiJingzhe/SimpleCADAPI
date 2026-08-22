# Task Domain: Requirement Refinement

Convert a user request — prose, reference images, technical drawings, or a
combination — into an actionable modeling brief before any geometry is written.

## Use when

- Every task starts here: any modeling, assembly, reconstruction, or export
  request is refined into a brief first.
- Inputs conflict, are ambiguous, or mix modalities.

## Do not use

- As a user-facing form: the brief is internal Markdown notes; never ask the
  user to fill out a schema.
- As a substitute for asking the one focused question that actually blocks the
  work.

## The brief must answer

- What is being modeled: part, assembly, modification, inspection, or export
  task.
- Units and coordinate convention (SDK evaluates lengths in millimeters and
  angles in degrees while preserving declared units in model JSON).
- Overall dimensions and which missing dimensions are inferable.
- Required features: holes, slots, bosses, ribs, pockets, shells, threads,
  patterns.
- Positioning control: faces, axes, origins, connectors, constraints,
  interfaces.
- Output files requested: package, STEP, STL, OBJ, MJCF, FCStd, scripts.
- Validation targets: bounding box, solid count, labels/tags, dimensions,
  mesh relations, replay count.

## Brief format

```text
CAD brief:
- Model: <name>, <part | assembly | modification | inspection | export>
- Inputs: <prose | reference images | drawing views used>
- Units: <explicit or assumed>
- Coordinate convention: <origin, base plane, up axis>
- Overall dimensions: <W x D x H or equivalent>
- Functional features: <list>
- Positioning/mating: <interfaces, datums, connectors, constraints>
- Parameters: <named parameters that must be Var-exposed>
- Paths: <source file(s), package/export targets>
- Validation targets: <measurable checks>
- Assumptions: <meaningful inferred choices only>
```

## Input precedence

- Dimensioned sources win over image proportions.
- When two dimensioned sources conflict, flag the conflict; never silently
  choose.
- An image without stated dimensions is design intent, not a spec: establish
  scale from one stated dimension or a known object, or ask the one scaling
  question when fit matters.
- Distinguish reproduction ("model this part") from inspiration ("something
  like this"): reproduction raises fidelity expectations.

## Technical drawings

A drawing is a dimensioned contract:

- Read the title block first: units, projection convention, revision.
- Identify each view and its model axes before extracting numbers; section
  views are the source of truth for internal features.
- Convert every callout into a named parameter and a validation target;
  expand `4X`, `TYP.`, thread/counterbore callouts into features plus checks.
- Never scale undimensioned geometry off the image.
- Cross-check features across views; prefer the dimensioned view and flag
  disagreements.

## Clarification policy

Ask one focused question only when missing information affects fit, safety,
compliance, or makes the model impossible. Otherwise proceed with explicit,
reported assumptions.

Ask when: no dimensions and no scale reference for a physical object; a mating
interface is described but unspecified; the part is safety-, load-, or
pressure-critical; output depends on a missing source file.

Do not ask when: a default clearance or cosmetic radius suffices;
origin/orientation can be chosen and reported; the user asked for a first-pass
conceptual model.

## Success criteria

The brief is ready when it defines source path(s), units, coordinate system,
named parameters, feature plan, positioning intent, output paths, and
validation targets — and every assumption it carries is one worth reporting.

Read `discipline/requirement-and-cad-brief.md` for the full discipline.
