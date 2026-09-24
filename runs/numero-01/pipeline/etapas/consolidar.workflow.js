export const meta = {
  name: 'condor-consolidar',
  description: 'Cóndor: consolidación de fallos — une en una sola resolución los fallos que tocan las mismas afirmaciones',
  whenToUse: 'Etapa hija del pipeline de Cóndor, entre reconciliar y cierre; args: {bloques, afirmaciones, conflictos, resoluciones, debates}',
  phases: [{ title: 'Consolidación', detail: 'un juez por grupo de fallos que comparten afirmaciones' }],
}

function dec(i, f) { f = f.replace(/0+$/, ''); return String(parseInt(i, 10)) + (f ? '.' + f : '') }
function canonNum(t) {
  if (/^\d{1,3}(\.\d{3})+$/.test(t) || /^\d{1,3}(,\d{3})+$/.test(t)) return String(parseInt(t.replace(/[.,]/g, ''), 10))
  let m = t.match(/^(\d{1,3}(?:\.\d{3})+),(\d+)$/); if (m) return dec(m[1].replace(/\./g, ''), m[2])
  m = t.match(/^(\d{1,3}(?:,\d{3})+)\.(\d+)$/); if (m) return dec(m[1].replace(/,/g, ''), m[2])
  m = t.match(/^(\d+)[.,](\d+)$/); if (m) return dec(m[1], m[2])
  if (/^\d+$/.test(t)) return String(parseInt(t, 10))
  return t
}
// recibe el token crudo o ya canónico; con agrupación de miles ("2.000", "1,950") nunca es un año
function significativa(t) {
  if (/^\d{1,3}([.,]\d{3})+$/.test(t)) return true
  const c = canonNum(t)
  if (c.includes('.')) return true
  const n = parseInt(c, 10); return !(n >= 1900 && n <= 2100) && n >= 10
}
function sig(s) { return new Set(((s || '').match(/\d+(?:[.,]\d+)*/g) || []).filter(significativa).map(canonNum)) }
// los jueces citan ids del libro ("feature#17") en su prosa: esos números no son cifras
function sinIds(s) { return (s || '').replace(/\b[a-z_]+#\d+\b/g, ' ') }
function textoBloque(b) { return [b.titulo, b.bajada, b.cuerpo].filter(Boolean).join(' ') }
function uniq(xs) { return [...new Set(xs)] }

const EDITAN = ['corregir', 'retirar', 'matizar']
const porId = {}
for (const a of args.afirmaciones) porId[a.id] = a
const conflictoPorId = {}
for (const c of args.conflictos || []) conflictoPorId[c.id] = c
const debatePorId = {}
for (const d of args.debates || []) debatePorId[d.conflicto_id] = d
const resoluciones = args.resoluciones
const guardas = []

// ------------------------------------------------------------ componentes (union-find sobre afirmaciones)
const padre = resoluciones.map((_, i) => i)
function raiz(i) { while (padre[i] !== i) { padre[i] = padre[padre[i]]; i = padre[i] } return i }
const duenio = {}
resoluciones.forEach((r, i) => {
  if (!EDITAN.includes(r.decision)) return
  for (const id of r.afirmaciones_afectadas || []) {
    if (duenio[id] === undefined) duenio[id] = i
    else padre[raiz(i)] = raiz(duenio[id])
  }
})
const grupos = {}
resoluciones.forEach((r, i) => { if (EDITAN.includes(r.decision)) (grupos[raiz(i)] = grupos[raiz(i)] || []).push(i) })
const componentes = Object.values(grupos).filter((g) => g.length >= 2).sort((a, b) => a[0] - b[0])
  .map((g, k) => {
    const rs = g.map((i) => resoluciones[i])
    return {
      id: `K${k + 1}`, indices: g, fallos: rs,
      conflictos: rs.map((r) => r.conflicto_id),
      afirmaciones: uniq(rs.flatMap((r) => r.afirmaciones_afectadas)),
      bloques: uniq(rs.flatMap((r) => r.bloques || [])),
    }
  })
log(`Consolidación: ${componentes.length} grupo(s) de fallos que comparten afirmaciones${componentes.length ? ': ' + componentes.map((c) => `${c.id}=${c.conflictos.join('+')}`).join(', ') : ''}.`)
if (!componentes.length) return { resoluciones, reemplazadas: [], componentes: [], guardas }

// ------------------------------------------------------------ juez de consolidación
const RULING_SCHEMA = {
  type: 'object',
  properties: {
    decision: { type: 'string', enum: ['mantener', 'corregir', 'retirar', 'matizar', 'sin_consenso'] },
    valor_correcto: { type: 'string', description: 'SÓLO el dato correcto, corto, sin prosa, sin explicación y sin ids (p. ej. "24 de mayo al 22 de junio de 2026", "17.000 ediciones"); vacío si no es corregir. La explicación va en razonamiento' },
    redaccion_sugerida: { type: 'string', description: 'el texto coherente que integra todas las correcciones (puede ser más de una oración); sin ids de afirmaciones' },
    afirmaciones_afectadas: { type: 'array', items: { type: 'string' } },
    confianza: { type: 'string', enum: ['alta', 'media', 'baja'] },
    razonamiento: { type: 'string', description: 'qué versión elegiste de cada dato y por qué, citando la evidencia' },
    evidencia: { type: 'array', items: { type: 'object', properties: { url: { type: 'string' }, cita: { type: 'string' } }, required: ['url', 'cita'] } },
  },
  required: ['decision', 'valor_correcto', 'redaccion_sugerida', 'afirmaciones_afectadas', 'confianza', 'razonamiento', 'evidencia'],
}

function evid(xs) { return (xs || []).map((e) => `${e.url} — "${e.cita}"`).join(' | ') || 'ninguna' }
function describirFallo(r) {
  const c = conflictoPorId[r.conflicto_id]
  const d = debatePorId[r.conflicto_id]
  const alegato = (nombre, x) => x ? `  ${nombre} sostuvo "${x.valor_sostenido}" (sustento: ${x.encontre_sustento}). Evidencia: ${evid(x.evidencia)}` : `  ${nombre}: no respondió.`
  return `[${r.conflicto_id}] ${c ? `conflicto (${c.tipo}): ${c.descripcion}` : ''}
  Fallo: ${r.decision} (confianza ${r.confianza}) sobre ${r.afirmaciones_afectadas.join(', ')}
  valor correcto según ese juez: ${r.valor_correcto || '(vacío)'}
  redacción sugerida: ${r.redaccion_sugerida || '(vacía)'}
  razonamiento: ${r.razonamiento}
  evidencia del juez: ${evid(r.evidencia)}
${d ? `${alegato('Defensor', d.defensor)}\n${alegato('Escéptico', d.esceptico)}` : '  (sin debate registrado)'}`
}

function consolidarPrompt(k) {
  const afs = k.afirmaciones.map((id) => porId[id]).filter(Boolean).map((a) =>
    `- ${a.id} [${a.bloque}] "${a.texto}" (cita: "${a.cita_textual}") — veredicto: ${a.veredicto.estado}${a.veredicto.valor_encontrado ? `; valor encontrado: ${a.veredicto.valor_encontrado}` : ''}; evidencia: ${evid(a.veredicto.evidencia)}`).join('\n')
  const textos = k.bloques.map((clave) => args.bloques.find((b) => b.clave === clave)).filter(Boolean)
    .map((b) => `### [${b.clave}] ${b.titulo}\n${b.bajada ? b.bajada + '\n' : ''}${b.cuerpo}`).join('\n\n')
  return `Sos JUEZ/A DE CONSOLIDACIÓN de una revista técnica. Varios jueces fallaron por separado sobre conflictos que tocan las MISMAS afirmaciones, y sus fallos no se pueden aplicar juntos tal como están (p. ej. uno corrige una duración a "cuatro semanas" y otro la corrige a "seis semanas"). Tu trabajo es dejar UNA resolución coherente que reemplace a todos. Podés hacer como máximo UN WebFetch, sólo para comprobar que una cita dudosa existe de verdad.

FALLOS A CONSOLIDAR:
${k.fallos.map(describirFallo).join('\n\n')}

AFIRMACIONES INVOLUCRADAS:
${afs}

TEXTOS ACTUALES DE LOS BLOQUES AFECTADOS:
${textos}

Reglas:
- Una sola decisión que aplique a TODAS estas afirmaciones: ${k.afirmaciones.join(', ')}. afirmaciones_afectadas tiene que incluirlas todas.
- Para cada dato elegí la versión mejor sustentada por evidencia LEÍDA (las citas literales de arriba). No promedies ni mezcles versiones incompatibles; si dos fallos dan valores distintos para el mismo dato, quedate con uno y explicá por qué en razonamiento.
- corregir: valor_correcto corto (sólo el dato); redaccion_sugerida integra TODAS las correcciones que sobreviven, de forma que un editor pueda aplicarla sin contradecirse en ningún bloque.
- retirar: si ninguna versión del dato tiene sustento.
- matizar: si el dato está sustentado pero falta contexto o atribución.
- sin_consenso: si los fallos se contradicen y la evidencia no alcanza para elegir. Pasa a decisión humana. Ante la duda, sin_consenso.
- Toda cifra de valor_correcto y redaccion_sugerida tiene que estar en los fallos, las evidencias o los textos de arriba: no inventes ni recalcules números. No uses ids de afirmaciones en el texto.`
}

// cifras que el juez de consolidación puede usar: todo lo que tuvo delante
function permitidasDe(k) {
  const xs = []
  for (const r of k.fallos) {
    xs.push(sinIds(`${r.valor_correcto} ${r.redaccion_sugerida}`), ...(r.evidencia || []).map((e) => e.cita))
    const d = debatePorId[r.conflicto_id]
    for (const x of d ? [d.defensor, d.esceptico] : []) if (x) xs.push(x.valor_sostenido, ...(x.evidencia || []).map((e) => e.cita))
  }
  for (const id of k.afirmaciones) {
    const a = porId[id]
    if (a) xs.push(a.cita_textual, a.valor, a.veredicto.valor_encontrado, ...(a.veredicto.evidencia || []).map((e) => e.cita))
  }
  for (const clave of k.bloques) { const b = args.bloques.find((x) => x.clave === clave); if (b) xs.push(textoBloque(b)) }
  return new Set(xs.flatMap((s) => [...sig(s)]))
}

const fallos = await parallel(componentes.map((k) => () =>
  agent(consolidarPrompt(k), { label: `consolidar:${k.id}`, phase: 'Consolidación', schema: RULING_SCHEMA })))

// ------------------------------------------------------------ guardas y armado
const reemplazo = {}  // índice de la primera resolución del componente -> resolución consolidada
const reemplazadas = []
const resumenComp = []
componentes.forEach((k, n) => {
  const r = fallos[n]
  let problema = ''
  let ids = []
  if (!r) problema = 'el juez de consolidación no respondió'
  else {
    ids = uniq((r.afirmaciones_afectadas || []).filter((id) => porId[id]))
    const faltan = k.afirmaciones.filter((id) => !ids.includes(id))
    const permitidas = permitidasDe(k)
    const inventadas = [...sig(sinIds(`${r.valor_correcto} ${r.redaccion_sugerida}`))].filter((c) => !permitidas.has(c))
    if (faltan.length) problema = `la resolución consolidada no cubre ${faltan.join(', ')}`
    else if (inventadas.length) problema = `la resolución consolidada trae cifras que no están en los fallos, las evidencias ni los textos: ${inventadas.join(', ')}`
  }
  if (problema) {
    // quedan los fallos originales (que se contradicen): el cierre los intenta igual y decide una persona
    for (const clave of k.bloques) guardas.push({ etapa: 'consolidacion', bloque: clave, tipo: 'consolidacion_caida', severidad: 'bloqueante', detalle: `${k.conflictos.join(', ')} comparten afirmaciones y no se pudieron consolidar (${problema}): quedan los fallos originales` })
    resumenComp.push({ id: k.id, conflictos: k.conflictos, afirmaciones: k.afirmaciones, resultado: 'caido', detalle: problema })
    return
  }
  const bloques = uniq([...k.bloques, ...ids.map((id) => porId[id].bloque)])
  reemplazo[k.indices[0]] = {
    ...r, conflicto_id: k.id, conflictos_cubiertos: k.conflictos, afirmaciones_afectadas: ids,
    cifras: uniq(k.fallos.flatMap((x) => x.cifras || [])), bloques,
  }
  reemplazadas.push(...k.fallos.map((x) => ({ ...x, consolidado_en: k.id })))
  resumenComp.push({ id: k.id, conflictos: k.conflictos, afirmaciones: k.afirmaciones, resultado: r.decision, detalle: '' })
  guardas.push({ etapa: 'consolidacion', bloque: bloques.join(','), tipo: 'fallos_consolidados', severidad: 'aviso', detalle: `${k.conflictos.join(', ')} → ${k.id} (${r.decision})` })
})

const consolidados = new Set(componentes.filter((k) => reemplazo[k.indices[0]]).flatMap((k) => k.indices))
const salida = []
resoluciones.forEach((r, i) => {
  if (reemplazo[i]) salida.push(reemplazo[i])
  else if (!consolidados.has(i)) salida.push(r)
})

return { resoluciones: salida, reemplazadas, componentes: resumenComp, guardas }
