import React, { useEffect, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { degrees, quaternion, withSourceUpAxis, type Assembly, type Vec3 } from './transforms'
import { Viewport } from './viewport'
import './style.css'

type Snapshot = { name: string; assembly: Assembly; revision: number; configured: boolean; preview_ready: boolean; preview_choices?: string[] }
type Job = { status: string; kind: string; error?: string }

async function api<T>(url: string, method = 'GET', body?: unknown): Promise<T> {
  const response = await fetch(`/api/${url}`, {
    method, headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!response.ok) {
    const error = await response.json()
    throw new Error(typeof error.detail === 'string' ? error.detail : JSON.stringify(error.detail))
  }
  return response.json()
}

function App() {
  const host = useRef<HTMLDivElement>(null)
  const viewport = useRef<Viewport | undefined>(undefined)
  const [saved, setSaved] = useState<Snapshot>()
  const [assembly, setAssembly] = useState<Assembly>()
  const [history, setHistory] = useState<Assembly[]>([])
  const current = useRef<Assembly | undefined>(undefined)
  const [message, setMessage] = useState('正在加载场景…')
  const [busy, setBusy] = useState(false)
  const dirty = assembly && saved && JSON.stringify(assembly) !== JSON.stringify(saved.assembly)

  function change(next: Assembly) {
    if (current.current) setHistory(h => [...h.slice(-39), structuredClone(current.current!)])
    current.current = next
    setAssembly(next)
  }

  useEffect(() => {
    let alive = true
    try {
      const view = new Viewport(host.current!, placement => {
        if (current.current) change({ ...current.current, background: { ...current.current.background, placement } })
      }, e => setMessage(String(e)))
      viewport.current = view
      api<Snapshot>('scene').then(snapshot => {
        if (!alive) return
        setSaved(snapshot); setAssembly(snapshot.assembly); current.current = snapshot.assembly
        setMessage(snapshot.configured ? '米制 · Z-up · 仅调整背景' : '尚未保存组装。请先检查源坐标方向。')
        if (snapshot.preview_ready) view.loadInteractive().catch(e => setMessage(String(e)))
        else runJob('preview')
      }).catch(e => setMessage(String(e)))
    } catch (e) { setMessage(String(e)) }
    return () => { alive = false; viewport.current?.dispose() }
  }, [])

  useEffect(() => {
    if (!assembly || !viewport.current) return
    viewport.current.setAssembly(assembly)
    const key = encodeURIComponent(assembly.background.preview_asset ?? 'default')
    viewport.current.loadBackground(`/api/assets/background?source=${key}`).catch(e => setMessage(String(e)))
  }, [assembly])

  useEffect(() => {
    if (!dirty) return
    const warn = (e: BeforeUnloadEvent) => { e.preventDefault(); e.returnValue = '' }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [dirty])

  async function save() {
    try {
      const next = await api<Snapshot>('assembly', 'PUT', { assembly, revision: saved?.revision })
      setSaved(next); setMessage('已保存到 specs/scene.yaml')
    } catch (e) { setMessage(String(e)) }
  }

  async function alignFloor() {
    if (!current.current) return
    const initial = structuredClone(current.current)
    setBusy(true)
    setMessage('正在估算背景地面…')
    try {
      const result = await api<{ delta_z_m: number; floor_z_m: number; warning: string }>(
        'estimate-floor', 'POST', { assembly: initial, revision: saved?.revision })
      if (JSON.stringify(current.current) !== JSON.stringify(initial)) {
        setMessage('估算期间参数已改变，请重新估算。'); return
      }
      const p = initial.background.placement
      p.position_m[2] += result.delta_z_m
      change(initial)
      setMessage(`估算地面 Z=${result.floor_z_m.toFixed(3)} m，背景已移动 ${result.delta_z_m.toFixed(3)} m。${result.warning}`)
    } catch (e) { setMessage(String(e)) }
    finally { setBusy(false) }
  }

  async function reload() {
    try {
      const next = await api<Snapshot>('scene')
      setSaved(next); change(next.assembly); setMessage('已恢复文件中的设置')
    } catch (e) { setMessage(String(e)) }
  }

  async function runJob(kind: string) {
    setBusy(true)
    setMessage(kind === 'preview' ? '正在生成预览…' : '正在导出组合 USD…')
    try {
      await api<Job>(kind, 'POST')
      let job: Job
      do {
        await new Promise(resolve => setTimeout(resolve, 700))
        job = await api<Job>('job')
      } while (job.status === 'running')
      if (job.status === 'error') throw new Error(job.error)
      if (kind === 'preview') await viewport.current?.loadInteractive()
      setMessage(kind === 'preview' ? '预览已就绪' : '已导出 exports/scene.usdc；动态验证待完成')
    } catch (e) { setMessage(String(e)) }
    finally { setBusy(false) }
  }

  const p = assembly?.background.placement
  function placement(field: string, value: unknown) {
    if (!assembly || !p) return
    change({ ...assembly, background: { ...assembly.background, placement: { ...p, [field]: value } } })
  }

  return <main>
    <div className="viewport" ref={host} />
    <aside>
      <h1>场景组装</h1><small>{saved?.name}</small>
      <p>世界坐标：米 · Z 向上 · 台面固定</p>
      <p>背景横躺或倒置时，请先设置源坐标适配，再调整摆放。</p>
      <label>显示<select onChange={e => viewport.current?.setVisibility(e.target.value)}>
        <option value="combined">背景与交互场景</option><option value="background">仅背景</option><option value="interactive">仅交互场景</option>
      </select></label>
      <div className="row">{[['perspective','透视'],['front','正视'],['side','侧视'],['top','顶视']].map(([key,label]) =>
        <button key={key} onClick={() => viewport.current?.setView(key)}>{label}</button>)}</div>
      <fieldset disabled={busy || !assembly}>
        <legend>背景摆放</legend>
        {assembly && !!saved?.preview_choices?.length && <label>预览分辨率<select value={assembly.background.preview_asset ?? saved.preview_choices.at(-1)} onChange={e => change({ ...assembly, background: { ...assembly.background, preview_asset: e.target.value } })}>
          {saved.preview_choices.map(path => <option key={path} value={path}>{path.split('/').at(-1)}</option>)}
        </select></label>}
        <div className="row"><button onClick={() => viewport.current?.setMode('translate')}>平移</button><button onClick={() => viewport.current?.setMode('rotate')}>旋转</button></div>
        {p && <>
          <VectorInput label="位置 (m)" value={p.position_m} step={0.01} onChange={v => placement('position_m', v)} />
          <VectorInput label="旋转 XYZ (°)" value={degrees(p.orientation_xyzw)} step={1} onChange={v => placement('orientation_xyzw', quaternion(v))} />
          <label>等比尺度<NumberInput value={p.uniform_scale} min={0.001} step={0.01} onChange={v => placement('uniform_scale', v)} /></label>
          <button onClick={alignFloor}>估算地面并对齐 Z=0</button>
          <small>先校正源轴向；仅移动背景高度，可撤销，点击保存后生效于导出。</small>
        </>}
        <details open><summary>源坐标适配</summary><p>选择背景原始向上方向。预设会替换源轴旋转；不改变摆放或尺度。</p>
          {assembly && <>
            <div className="row">
              <button onClick={() => change(withSourceUpAxis(assembly, 'y-down'))}>源 −Y 向上</button>
              <button onClick={() => change(withSourceUpAxis(assembly, 'y-up'))}>源 +Y 向上</button>
              <button onClick={() => change(withSourceUpAxis(assembly, 'z-up'))}>源 +Z 向上</button>
            </div>
            <VectorInput label="源轴旋转 XYZ (°)" value={degrees(assembly.background.source_to_world.orientation_xyzw)} step={90} onChange={v => change({ ...assembly, background: { ...assembly.background, source_to_world: { ...assembly.background.source_to_world, orientation_xyzw: quaternion(v) } } })} />
            <label>米 / 源单位<NumberInput min={0.000001} step={0.01} value={assembly.background.source_to_world.meters_per_source_unit} onChange={v => change({ ...assembly, background: { ...assembly.background, source_to_world: { ...assembly.background.source_to_world, meters_per_source_unit: v } } })} /></label>
          </>}
        </details>
      </fieldset>
      <div className="row"><button disabled={!history.length || busy} onClick={() => {
        const previous = history.at(-1)!
        setHistory(history.slice(0, -1)); current.current = previous; setAssembly(previous)
      }}>撤销</button><button disabled={busy} onClick={reload}>恢复文件</button>
        <button disabled={busy || !assembly} onClick={save}>保存{dirty ? ' *' : ''}</button></div>
      <div className="row"><button disabled={busy} onClick={() => runJob('preview')}>更新预览</button>
        <button disabled={busy || !!dirty || !saved?.configured} onClick={() => runJob('export')}>导出 USD</button></div>
      <p role="status">{message}</p>
      <details><summary>背景参考图</summary><img src="/api/assets/reference" alt="背景参考" /></details>
      <small>预览灯光仅用于摆放；正式灯光和物理属性由导出管线保留。</small>
    </aside>
  </main>
}

function NumberInput({ value, onChange, step, min }: { value: number; onChange: (v: number) => void; step: number; min?: number }) {
  const [text, setText] = useState(String(value))
  useEffect(() => setText(String(Number(value.toFixed(5)))), [value])
  return <input type="number" step={step} min={min} value={text} onChange={e => setText(e.target.value)} onBlur={() => {
    const number = Number(text)
    if (text.trim() && Number.isFinite(number) && (min === undefined || number >= min)) onChange(number)
    else setText(String(value))
  }} onKeyDown={e => { if (e.key === 'Enter') e.currentTarget.blur() }} />
}

function VectorInput({ label, value, onChange, step }: { label: string; value: Vec3; onChange: (v: Vec3) => void; step: number }) {
  return <label>{label}<div className="row">{value.map((v, i) => <NumberInput key={i} value={v} step={step} onChange={n => {
    const next = [...value] as Vec3; next[i] = n; onChange(next)
  }} />)}</div></label>
}

createRoot(document.getElementById('root')!).render(<App />)
