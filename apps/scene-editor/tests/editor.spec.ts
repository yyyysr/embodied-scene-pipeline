import { test, expect } from '@playwright/test'
import { gzipSync } from 'node:zlib'

// Same asymmetric source Gaussian as tests/test_assembly.py, encoded as SPZ v3.
function spz() {
  const b = Buffer.alloc(36)
  b.writeUInt32LE(0x5053474e, 0); b.writeUInt32LE(3, 4); b.writeUInt32LE(1, 8)
  b[13] = 12
  ;[1, 2, 3].forEach((v, i) => b.writeIntLE(v * 4096, 16 + 3 * i, 3))
  Buffer.from([200, 128, 128, 128, 144, 152, 160]).copy(b, 25)
  b.writeUInt32LE(3 * 2 ** 30 + 181, 32)
  return gzipSync(b)
}

test('Spark source coordinates, Z-up transform and save/reload contract', async ({ page }) => {
  let assembly = { version: 1, background: {
    source_to_world: { orientation_xyzw: [0, 0, 0, 1], meters_per_source_unit: 1 },
    placement: { position_m: [0, 0, 0], orientation_xyzw: [0, 0, 0, 1], uniform_scale: 1 },
  } }
  const errors: string[] = []
  page.on('pageerror', e => errors.push(String(e)))
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname
    if (path === '/api/assets/background') return route.fulfill({ body: spz(), contentType: 'application/octet-stream' })
    if (path === '/api/assets/interactive') {
      // Empty glTF is enough here: real Blender GLB is checked separately.
      return route.fulfill({ json: { asset: { version: '2.0' }, scenes: [{ nodes: [] }], scene: 0, nodes: [] } })
    }
    if (path === '/api/assets/reference') return route.fulfill({ status: 204 })
    if (path === '/api/assembly') assembly = route.request().postDataJSON().assembly
    return route.fulfill({ json: { name: 'coordinate_fixture', assembly, revision: 1, configured: true, preview_ready: true } })
  })
  await page.goto('/')
  await expect(page.locator('canvas')).toBeVisible()
  const result = await page.evaluate(async () => {
    // Exercise the installed Spark loader, not a second SPZ implementation.
    const { SplatMesh } = await import('/node_modules/.vite/deps/@sparkjsdev_spark.js')
    const { assemblyMatrix } = await import('/src/transforms.ts')
    const splat = new SplatMesh({ url: '/api/assets/background' })
    await splat.initialized
    const decoded = splat.packedSplats?.getSplat(0) ?? splat.extSplats.getSplat(0)
    const raw = decoded.center.toArray()
    const s = Math.sqrt(0.5)
    const m = assemblyMatrix({ version: 1, background: {
      source_to_world: { orientation_xyzw: [s, 0, 0, s], meters_per_source_unit: 0.5 },
      placement: { position_m: [4, 5, 6], orientation_xyzw: [0, 0, s, s], uniform_scale: 2 },
    } })
    const world = decoded.center.applyMatrix4(m).toArray()
    const orientation = decoded.quaternion.toArray()
    const scales = decoded.scales.toArray()
    splat.dispose()
    return { raw, world, orientation, scales }
  })
  expect(result.raw).toEqual([1, 2, 3])
  result.world.forEach((v: number, i: number) => expect(v).toBeCloseTo([7, 6, 8][i], 5))
  expect(Math.abs(result.orientation[2])).toBeCloseTo(181 * Math.SQRT1_2 / 511, 2)
  expect(Math.abs(result.orientation[3])).toBeCloseTo(Math.sqrt(1 - (181 * Math.SQRT1_2 / 511) ** 2), 2)
  result.scales.forEach((v: number, i: number) => expect(v).toBeCloseTo(Math.exp([-1, -0.5, 0][i]), 1))
  const x = page.locator('input[type=number]').first()
  await x.fill('1.25'); await x.press('Enter')
  await page.getByRole('button', { name: '保存' }).click()
  await expect(page.getByRole('status')).toContainText('已保存')
  expect(assembly.background.placement.position_m[0]).toBe(1.25)
  await page.reload()
  await expect(page.locator('input[type=number]').first()).toHaveValue('1.25')
  expect(errors).toEqual([])
})
