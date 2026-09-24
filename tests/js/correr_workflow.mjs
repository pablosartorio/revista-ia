// Corre un .workflow.js con el runtime simulado: `agent` devuelve respuestas fijas por label.
// Entrada (stdin): {script, args, respuestas: {label: respuesta}}. Salida (stdout): {result, logs, labels}.
import { readFileSync } from 'fs'

const entrada = JSON.parse(readFileSync(0, 'utf8'))
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor
const logs = [], labels = []
const agent = async (_prompt, opts) => { labels.push(opts.label); return entrada.respuestas[opts.label] ?? null }
const parallel = (thunks) => Promise.all(thunks.map((t) => Promise.resolve().then(t).catch(() => null)))
const pipeline = (items, ...etapas) => Promise.all(items.map(async (item) => {
  try {
    let v = await etapas[0](item)
    for (const e of etapas.slice(1)) v = await e(v, item)
    return v
  } catch { return null }
}))
// las etapas hijas corren con el mismo runtime simulado
const workflow = async ({ scriptPath }, args) => correr(scriptPath, args)
async function correr(script, args) {
  const src = readFileSync(script, 'utf8').replace(/^export const meta = /m, 'const meta = ')
  const fn = new AsyncFunction('args', 'agent', 'parallel', 'pipeline', 'workflow', 'log', 'phase', src)
  return fn(args, agent, parallel, pipeline, workflow, (m) => logs.push(m), () => {})
}
const result = await correr(entrada.script, entrada.args)
process.stdout.write(JSON.stringify({ result, logs, labels }))
