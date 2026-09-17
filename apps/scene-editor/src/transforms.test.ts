import { describe, expect, it } from 'vitest'
import { Quaternion, Vector3 } from 'three'
import { assemblyMatrix, GLTF_TO_Z_UP, withSourceUpAxis, type Assembly, type SourceUpAxis } from './transforms'

describe('meter/Z-up contract shared with tests/test_assembly.py', () => {
  it.each<[SourceUpAxis, [number, number, number]]>([
    ['y-down', [0, -1, 0]], ['y-up', [0, 1, 0]], ['z-up', [0, 0, 1]],
  ])('maps %s vertical to +Z without changing placement or accumulating rotation', (axis, up) => {
    const original: Assembly = { version: 1, background: {
      source_to_world: { orientation_xyzw: [0, 0, 1, 0], meters_per_source_unit: 0.5 },
      placement: { position_m: [4, 5, 6], orientation_xyzw: [0, 0, 0, 1], uniform_scale: 2 },
    } }
    const corrected = withSourceUpAxis(original, axis)
    const q = new Quaternion(...corrected.background.source_to_world.orientation_xyzw)
    expect(new Vector3(...up).applyQuaternion(q).distanceTo(new Vector3(0, 0, 1))).toBeLessThan(1e-10)
    expect(corrected.background.placement).toEqual(original.background.placement)
    expect(corrected.background.source_to_world.meters_per_source_unit).toBe(0.5)
    expect(withSourceUpAxis(corrected, axis)).toEqual(corrected)
    expect(original.background.source_to_world.orientation_xyzw).toEqual([0, 0, 1, 0])
    if (axis === 'y-down') {
      expect(new Vector3(1, 2, 3).applyMatrix4(assemblyMatrix(corrected)).distanceTo(new Vector3(5, 8, 4))).toBeLessThan(1e-10)
    }
  })
  it('applies source correction before placement, matching USD (7,6,8)', () => {
    const s = Math.sqrt(0.5)
    const assembly: Assembly = { version: 1, background: {
      source_to_world: { orientation_xyzw: [s, 0, 0, s], meters_per_source_unit: 0.5 },
      placement: { position_m: [4, 5, 6], orientation_xyzw: [0, 0, s, s], uniform_scale: 2 },
    } }
    const point = new Vector3(1, 2, 3).applyMatrix4(assemblyMatrix(assembly))
    point.toArray().forEach((value, i) => expect(value).toBeCloseTo([7, 6, 8][i], 6))
  })
  it('reverses Blender glTF Y-up conversion exactly once', () => {
    const original = new Vector3(1, 2, 3)
    const gltf = new Vector3(1, 3, -2)
    expect(gltf.applyQuaternion(GLTF_TO_Z_UP).distanceTo(original)).toBeLessThan(1e-10)
  })
})
