import { Euler, Matrix4, Object3D, Quaternion, Vector3 } from 'three'

export type Vec3 = [number, number, number]
export type Quat = [number, number, number, number]
export type Placement = { position_m: Vec3; orientation_xyzw: Quat; uniform_scale: number }
export type Assembly = {
  version: 1
  background: {
    preview_asset?: string
    source_to_world: { orientation_xyzw: Quat; meters_per_source_unit: number }
    placement: Placement
  }
}

// Blender export_yup=True: (x,y,z) -> (x,z,-y). This inverse is applied ONCE.
export const GLTF_TO_Z_UP = new Quaternion().setFromAxisAngle(new Vector3(1, 0, 0), Math.PI / 2)

export function applyPlacement(object: Object3D, p: Placement) {
  object.position.fromArray(p.position_m)
  object.quaternion.fromArray(p.orientation_xyzw)
  object.scale.setScalar(p.uniform_scale)
  object.updateMatrixWorld(true)
}

export function readPlacement(object: Object3D): Placement {
  return {
    position_m: object.position.toArray() as Vec3,
    orientation_xyzw: object.quaternion.clone().normalize().toArray() as Quat,
    uniform_scale: object.scale.x,
  }
}

export function assemblyMatrix(a: Assembly) {
  const { placement: p, source_to_world: c } = a.background
  const outer = new Matrix4().compose(new Vector3(...p.position_m),
    new Quaternion(...p.orientation_xyzw), new Vector3().setScalar(p.uniform_scale))
  const inner = new Matrix4().compose(new Vector3(), new Quaternion(...c.orientation_xyzw),
    new Vector3().setScalar(c.meters_per_source_unit))
  return outer.multiply(inner)
}

export function degrees(q: Quat): Vec3 {
  const e = new Euler().setFromQuaternion(new Quaternion(...q), 'XYZ')
  return [e.x, e.y, e.z].map(v => v * 180 / Math.PI) as Vec3
}

export function quaternion(deg: Vec3): Quat {
  return new Quaternion().setFromEuler(new Euler(...deg.map(v => v * Math.PI / 180) as Vec3, 'XYZ'))
    .toArray() as Quat
}
