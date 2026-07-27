/** Deterministic rigid-transform primitives used by Scene validation. */

type JsonRecord = Record<string, unknown>;

export function composeRigidTransforms(left: JsonRecord, right: JsonRecord): JsonRecord {
  const origin = left.origin as number[];
  const xAxis = left.x_axis as number[];
  const yAxis = left.y_axis as number[];
  const zAxis = left.z_axis as number[];
  const rotate = (vector: number[]): number[] => [0, 1, 2].map((index) =>
    (xAxis[index] * vector[0] + yAxis[index] * vector[1]) + zAxis[index] * vector[2]
  );
  const rotatedOrigin = rotate(right.origin as number[]);
  return {
    origin: origin.map((component, index) => component + rotatedOrigin[index]),
    x_axis: rotate(right.x_axis as number[]),
    y_axis: rotate(right.y_axis as number[]),
    z_axis: rotate(right.z_axis as number[]),
  };
}

export function rigidTransformsEqual(actual: JsonRecord, expected: JsonRecord): boolean {
  const actualOrigin = actual.origin as number[];
  const expectedOrigin = expected.origin as number[];
  const originEpsilon = Math.max(
    1e-9,
    1e-12 * Math.max(1, ...actualOrigin.map(Math.abs), ...expectedOrigin.map(Math.abs)),
  );
  return actualOrigin.every((component, index) => Math.abs(component - expectedOrigin[index]) <= originEpsilon) &&
    ["x_axis", "y_axis", "z_axis"].every((key) =>
      (actual[key] as number[]).every((component, index) =>
        Math.abs(component - (expected[key] as number[])[index]) <= 1e-12
      )
    );
}
