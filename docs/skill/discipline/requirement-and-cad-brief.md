# Discipline: Requirement and CAD Brief

Converting prose, reference images, and technical drawings into an actionable
modeling brief. The operational steps live in
`../domains/requirement-refinement.md`; this file carries reasoning and
evidence-handling guidance, not automatic SDK behavior.

## Every modality funnels into one brief

Prose, images, drawings, and conflicts all reduce to the same artifact: a
note-form brief with units, dimensions, features, positioning intent, paths,
and validation targets. The downstream workflow never changes based on input
modality.

## Evidence precedence

- A dimensioned source beats image proportions, always.
- Two dimensioned sources in conflict (prose says one value, a drawing callout
  another) → flag the conflict to the user; never silently choose.
- An image without dimensions is design intent, not a spec. Establish scale
  from one stated dimension or a known object in frame. If neither exists and
  fit matters, that is the one clarification question worth asking.
- Reproduction ("model this exactly") raises fidelity expectations and
  validation targets; inspiration ("something like this") leaves freedom.
  Record which one the request is.

## Reading a technical drawing

A drawing is a dimensioned contract:

1. Title block and notes first: units, projection convention, revision,
   disclaimers.
2. Map every view to model axes before extracting numbers — trust view labels
   and callouts, not layout conventions.
3. Section views are the source of truth for internal features: bores,
   counterbore/blind-hole depths, wall sections.
4. Every callout becomes a named parameter plus a validation target.
   Multiplicity (`4X`), `TYP.`, thread/counterbore callouts expand into
   features plus checks.
5. Never scale undimensioned geometry off the drawing; derive it from stated
   dimensions when constrained, otherwise assume and report.
6. Cross-check features across views; when views disagree, prefer the
   dimensioned view and flag the disagreement.

Success for a drawing-driven model: every drawing dimension is either verified
by a measurement after generation, or explicitly reported as not verified.

## Assumptions are load-bearing only when reported

An assumption silently applied is a future defect. Each one in the brief
should be one a reviewer would want to see: default wall thickness, assumed
clearance standard, chosen corner treatment. Trivia (an internal helper's
name) is noise.

## The one-question rule

Ask one focused question only when missing information affects fit, safety,
compliance, or makes the model impossible. Otherwise proceed with explicit
assumptions. A barrage of questions is a failure to apply defaults; a missing
question on a fit-critical dimension is a failure to ask.

## Brief quality gate

The brief is ready when it defines: source path(s), units, coordinate
convention, named parameters, feature plan, positioning intent, output paths,
and validation targets — and every assumption it carries is worth reporting.
