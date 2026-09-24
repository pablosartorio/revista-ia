// Evalúa canonNum/significativa/sig/sinIds de un .workflow.js sobre una tabla de casos.
// Entrada (stdin): {script, tokens, textos}. Salida: {canon, significativa, sig, sinIds}.
import { readFileSync } from 'fs'

const { script, tokens, textos } = JSON.parse(readFileSync(0, 'utf8'))
const src = readFileSync(script, 'utf8')
const fuente = ['dec', 'canonNum', 'significativa', 'sig', 'sinIds'].map((n) => {
  const m = src.match(new RegExp(`^function ${n}\\(.*?(?=^function |^//|^const |(?![\\s\\S]))`, 'ms'))
  if (!m) throw new Error(`${script}: no encuentro function ${n}`)
  return m[0]
}).join('\n')
const f = new Function(`${fuente}; return { canonNum, significativa, sig, sinIds }`)()
process.stdout.write(JSON.stringify({
  canon: tokens.map(f.canonNum),
  significativa: tokens.map(f.significativa),
  sig: textos.map((t) => [...f.sig(t)].sort()),
  sinIds: textos.map(f.sinIds),
}))
