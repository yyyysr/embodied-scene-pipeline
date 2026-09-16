import { describe, expect, it } from 'vitest'
import { Vector3 } from 'three'
import { assemblyMatrix, GLTF_TO_Z_UP, type Assembly } from './transforms'

describe('meter/Z-up contract shared with tests/test_assembly.py', () => {
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
