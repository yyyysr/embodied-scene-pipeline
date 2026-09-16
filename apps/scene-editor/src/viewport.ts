import * as THREE from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'
import { TransformControls } from 'three/addons/controls/TransformControls.js'
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js'
import { SparkRenderer, SplatMesh } from '@sparkjsdev/spark'
import { applyPlacement, GLTF_TO_Z_UP, readPlacement, type Assembly, type Placement } from './transforms'

export class Viewport {
  scene = new THREE.Scene()
  camera = new THREE.PerspectiveCamera(50, 1, 0.01, 1000)
  renderer = new THREE.WebGLRenderer({ antialias: true })
  background = new THREE.Group()
  source = new THREE.Group()
  interactive = new THREE.Group()
  controls: OrbitControls
  gizmo: TransformControls
  splat?: SplatMesh
  spark: SparkRenderer
  observer: ResizeObserver
  disposed = false
  backgroundUrl = ''
  meshRevision = 0
  editing = false

  constructor(host: HTMLElement, onChange: (p: Placement) => void, onError: (e: unknown) => void) {
    this.scene.background = new THREE.Color('#283038')
    this.renderer.setPixelRatio(Math.min(devicePixelRatio, 2))
    this.renderer.outputColorSpace = THREE.SRGBColorSpace
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping
    host.appendChild(this.renderer.domElement)
    this.camera.up.set(0, 0, 1)
    this.controls = new OrbitControls(this.camera, this.renderer.domElement)
    this.setView('perspective')
    this.scene.add(this.background, this.interactive)
    this.background.add(this.source)
    this.interactive.quaternion.copy(GLTF_TO_Z_UP)
    const grid = new THREE.GridHelper(12, 24, '#81949e', '#47535d')
    grid.rotation.x = Math.PI / 2
    this.scene.add(grid, new THREE.AxesHelper(1))
    this.scene.add(new THREE.HemisphereLight(0xffffff, 0x888888, 2))
    const sun = new THREE.DirectionalLight(0xffffff, 3)
    sun.position.set(2, -3, 6)
    this.scene.add(sun)
    this.spark = new SparkRenderer({ renderer: this.renderer })
    this.scene.add(this.spark)
    this.gizmo = new TransformControls(this.camera, this.renderer.domElement)
    this.gizmo.setSpace('world')
    this.gizmo.attach(this.background)
    this.scene.add(this.gizmo.getHelper())
    this.gizmo.addEventListener('dragging-changed', (event) => {
      this.controls.enabled = !event.value
      this.editing = Boolean(event.value)
      if (!event.value) onChange(readPlacement(this.background))
    })
    this.observer = new ResizeObserver(() => {
      const width = Math.max(host.clientWidth, 1), height = Math.max(host.clientHeight, 1)
      this.camera.aspect = width / height
      this.camera.updateProjectionMatrix()
      this.renderer.setSize(width, height)
    })
    this.observer.observe(host)
    this.renderer.setAnimationLoop(() => {
      try {
        this.controls.update()
        this.renderer.render(this.scene, this.camera)
      } catch (e) {
        this.renderer.setAnimationLoop(null)
        onError(e)
      }
    })
  }

  setView(name: string) {
    const positions: Record<string, [number, number, number]> = {
      perspective: [3, -4, 3], front: [0, -5, 0.9], side: [5, 0, 0.9], top: [0, 0, 6],
    }
    this.camera.position.set(...positions[name])
    // A top view needs a non-parallel camera up vector.
    this.camera.up.set(0, name === 'top' ? 1 : 0, name === 'top' ? 0 : 1)
    this.controls.target.set(0, 0, 0.9)
    this.controls.update()
  }

  setAssembly(a: Assembly) {
    if (this.editing) return
    applyPlacement(this.background, a.background.placement)
    this.source.quaternion.fromArray(a.background.source_to_world.orientation_xyzw)
    this.source.scale.setScalar(a.background.source_to_world.meters_per_source_unit)
  }

  async loadBackground(url: string) {
    if (this.backgroundUrl === url) return
    this.backgroundUrl = url
    if (this.splat) { this.source.remove(this.splat); this.splat.dispose() }
    const splat = new SplatMesh({ url })
    this.splat = splat
    // No implicit flip/centering: source_to_world is the single source adapter.
    this.source.add(splat)
    await splat.initialized
  }

  async loadInteractive() {
    const revision = ++this.meshRevision
    const { scene } = await new GLTFLoader().loadAsync(`/api/assets/interactive?v=${revision}`)
    if (this.disposed || revision !== this.meshRevision) { this.releaseMeshes(scene); return }
    this.releaseMeshes(this.interactive)
    this.interactive.clear()
    this.interactive.add(scene)
  }

  setMode(mode: 'translate' | 'rotate') { this.gizmo.setMode(mode) }

  setVisibility(mode: string) {
    this.background.visible = mode !== 'interactive'
    this.interactive.visible = mode !== 'background'
    this.gizmo.getHelper().visible = this.background.visible
    this.gizmo.enabled = this.background.visible
  }

  releaseMeshes(root: THREE.Object3D) {
    const textures = new Set<THREE.Texture>()
    root.traverse(o => {
      if (!(o instanceof THREE.Mesh)) return
      o.geometry.dispose()
      for (const material of Array.isArray(o.material) ? o.material : [o.material]) {
        for (const value of Object.values(material)) if (value instanceof THREE.Texture) textures.add(value)
        material.dispose()
      }
    })
    textures.forEach(texture => texture.dispose())
  }

  dispose() {
    this.disposed = true
    this.renderer.setAnimationLoop(null)
    this.observer.disconnect()
    this.controls.dispose()
    this.gizmo.dispose()
    if (this.splat) { this.source.remove(this.splat); this.splat.dispose() }
    this.releaseMeshes(this.scene)
    this.spark.dispose()
    this.renderer.dispose()
    this.renderer.domElement.remove()
  }
}
