export const meta = {
  name: 'condor-reconciliar',
  description: 'Cóndor: reconciliación cruzada — compara la nota de fondo con las secciones y resuelve conflictos por debate',
  whenToUse: 'Etapa hija del pipeline de Cóndor; args: {bloques, afirmaciones, modelo_verificador, max_debates}',
  phases: [
    { title: 'Detección', detail: 'detectores determinísticos + 2 reconciliadores con lentes distintas' },
    { title: 'Debate', detail: 'defensor y escéptico en paralelo por conflicto' },
    { title: 'Fallo', detail: 'un juez por conflicto decide con la evidencia presentada' },
  ],
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
function nums(s) { return ((s || '').match(/\d+(?:[.,]\d+)*/g) || []).map(canonNum) }
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
// cifras de una afirmación: las del valor que están en su cita (la cita puede traer datos ajenos)
function cifrasAf(a) {
  const enCita = sig(a.cita_textual)
  const propias = [...sig(a.valor)].filter((c) => enCita.has(c))
  return new Set(propias.length ? propias : enCita)
}
function norm(s) {
  return (s || '').normalize('NFKD').replace(/[\u0300-\u036f]/g, '').replace(/\s+/g, ' ').trim().toLowerCase()
}
function tokens(s) { return new Set(norm(s).split(/[^a-z0-9]+/).filter((t) => t.length >= 4)) }
function textoBloque(b) { return [b.titulo, b.bajada, b.cuerpo].filter(Boolean).join(' ') }
function uniq(xs) { return [...new Set(xs)] }
function fragmentoCifra(texto, c) {
  const re = /\d+(?:[.,]\d+)*/g
  let m
  while ((m = re.exec(texto)) !== null) {
    if (canonNum(m[0]) === c) return texto.slice(Math.max(0, m.index - 70), m.index + m[0].length + 70)
  }
  return ''
}

const bloques = args.bloques
const afirmaciones = args.afirmaciones
const porId = {}
for (const a of afirmaciones) porId[a.id] = a
const MAX_DEBATES = args.max_debates || 10
const guardas = []

// ------------------------------------------------------------ detectores determinísticos
phase('Detección')
const candidatos = []
const gruposDet = []
const features = bloques.filter((b) => b.tipo === 'feature')
const secciones = bloques.filter((b) => b.tipo !== 'feature')
const cifrasSecciones = new Set(secciones.flatMap((b) => [...sig(textoBloque(b))]))

for (const f of features) {
  for (const c of sig(textoBloque(f))) {
    if (cifrasSecciones.has(c)) continue
    const delBloque = afirmaciones.filter((a) => a.bloque === f.clave)
    let ids = delBloque.filter((a) => cifrasAf(a).has(c)).map((a) => a.id)
    if (!ids.length) ids = delBloque.filter((a) => nums(a.cita_textual).includes(c)).map((a) => a.id)
    candidatos.push({
      tipo: 'huerfana', afirmaciones: ids, bloques: [f.clave], cifras: [c],
      descripcion: `la nota de fondo usa la cifra ${c} que no aparece en ninguna sección: "…${fragmentoCifra(textoBloque(f), c)}…"`,
    })
  }
}

for (let i = 0; i < afirmaciones.length; i++) {
  for (let j = i + 1; j < afirmaciones.length; j++) {
    const a = afirmaciones[i], b = afirmaciones[j]
    if (a.bloque === b.bloque) continue
    const cifrasComunes = [...cifrasAf(a)].filter((c) => cifrasAf(b).has(c))
    const entidadComun = [...tokens(a.entidad)].some((t) => tokens(b.entidad).has(t))
    if (!cifrasComunes.length || !entidadComun) continue
    gruposDet.push({ afirmaciones: [a.id, b.id], descripcion: `${a.entidad}: ${cifrasComunes.join(', ')}` })
    if (a.veredicto.estado !== b.veredicto.estado) {
      candidatos.push({
        tipo: 'veredicto', afirmaciones: [a.id, b.id], bloques: [a.bloque, b.bloque],
        descripcion: `el mismo dato (${a.entidad}: ${cifrasComunes.join(', ')}) quedó "${a.veredicto.estado}" en ${a.bloque} y "${b.veredicto.estado}" en ${b.bloque}`,
      })
    }
  }
}
candidatos.forEach((c, i) => { c.id = `D${i + 1}` })
log(`Detectores determinísticos: ${candidatos.length} candidato(s) a conflicto, ${gruposDet.length} par(es) del mismo hecho.`)

// ------------------------------------------------------------ reconciliadores (2 lentes)
const LENS_SCHEMA = {
  type: 'object',
  properties: {
    grupos: {
      type: 'array', description: 'afirmaciones de DISTINTOS bloques que hablan del mismo hecho',
      items: { type: 'object', properties: { afirmaciones: { type: 'array', items: { type: 'string' } }, descripcion: { type: 'string' } }, required: ['afirmaciones', 'descripcion'] },
    },
    conflictos: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          tipo: { type: 'string', enum: ['valor', 'veredicto', 'huerfana', 'cronologia', 'interna'] },
          afirmaciones: { type: 'array', items: { type: 'string' } },
          bloques: { type: 'array', items: { type: 'string' }, description: 'claves de los bloques involucrados (las que aparecen entre corchetes en los textos)' },
          descripcion: { type: 'string' },
          gravedad: { type: 'string', enum: ['alta', 'media', 'baja'] },
        },
        required: ['tipo', 'afirmaciones', 'bloques', 'descripcion', 'gravedad'],
      },
    },
    candidatos: {
      type: 'array', description: 'tu juicio sobre cada candidato determinístico D1, D2…',
      items: { type: 'object', properties: { id: { type: 'string' }, real: { type: 'boolean' }, razon: { type: 'string' } }, required: ['id', 'real', 'razon'] },
    },
  },
  required: ['grupos', 'conflictos', 'candidatos'],
}

const tablaAf = afirmaciones.map((a) => `${a.id} | ${a.bloque} | ${a.veredicto.estado} | ${a.entidad} | ${a.valor} | ${a.texto}`).join('\n')
const tablaCand = candidatos.map((c) => `${c.id} (${c.tipo}): ${c.descripcion}`).join('\n') || '(ninguno)'
const textos = bloques.map((b) => `### [${b.clave}] ${b.titulo}\n${b.bajada ? b.bajada + '\n' : ''}${b.cuerpo}`).join('\n\n')

const LENTES = [
  { id: 'hechos', foco: 'POR HECHO Y ENTIDAD: agrupá afirmaciones de distintos bloques que hablan del mismo hecho (misma empresa/modelo/organismo y misma magnitud). Buscá: (a) el mismo hecho con VALORES distintos entre bloques; (b) el mismo hecho con VEREDICTOS distintos (confirmado en un bloque, no verificable en otro); (c) afirmaciones de la nota de fondo que no tienen respaldo en ninguna sección ni fuente propia (HUÉRFANAS).' },
  { id: 'cronologia', foco: 'CRONOLOGÍA Y CIFRAS DERIVADAS: revisá fechas, rangos, duraciones ("seis semanas", "42 días"), porcentajes, comparaciones ("el triple", "el 73%") y cálculos. Buscá inconsistencias entre bloques y DENTRO de un mismo bloque: una duración que no coincide con el rango de fechas, un porcentaje que no cierra con las cifras que lo componen, una fecha de un bloque que contradice la de otro.' },
]

function lensPrompt(l) {
  return `Sos reconciliador/a de una revista técnica. La nota de fondo y las secciones del número ya pasaron por verificación afirmación por afirmación. Tu trabajo es la verificación CRUZADA: encontrar inconsistencias ENTRE notas que los verificadores, cada uno mirando un solo bloque, no pueden ver. No hacés búsquedas web: trabajás sobre el material de abajo.

Tu lente: ${l.foco}

AFIRMACIONES (id | bloque | veredicto | entidad | valor | texto):
${tablaAf}

CANDIDATOS DETECTADOS POR CÓDIGO (juzgá cada uno: real=true si es un conflicto de verdad, false si es un falso positivo, p. ej. la misma cifra refiriéndose a cosas distintas):
${tablaCand}

TEXTOS COMPLETOS:
${textos}

Reglas: usá sólo ids de la tabla; en cada conflicto listá también las claves de los bloques involucrados (si la inconsistencia no tiene afirmación extraída, dejá afirmaciones vacía pero completá bloques). No reportes estilo ni opiniones, sólo inconsistencias fácticas. Si no encontrás conflictos, devolvé listas vacías: es mejor que inventar uno.`
}

const lentes = await parallel(LENTES.map((l) => () =>
  agent(lensPrompt(l), { label: `reconciliar:${l.id}`, phase: 'Detección', schema: LENS_SCHEMA }).then((r) => r && { ...r, lente: l.id })))
const lentesOk = lentes.filter(Boolean)
const claveFeature = features.length ? features[0].clave : null
if (!lentesOk.length) {
  // sin reconciliadores no hubo cruce entre nota de fondo y secciones: que lo decida una persona
  for (const clave of claveFeature ? [claveFeature] : bloques.map((b) => b.clave)) {
    guardas.push({ etapa: 'reconciliacion', bloque: clave, tipo: 'reconciliacion_caida', severidad: 'bloqueante', detalle: `no respondió ningún reconciliador (0/${LENTES.length}): sólo corrieron los detectores determinísticos` })
  }
} else if (lentesOk.length < LENTES.length) {
  guardas.push({ etapa: 'reconciliacion', bloque: claveFeature || '', tipo: 'lente_caida', severidad: 'aviso', detalle: `respondieron ${lentesOk.length}/${LENTES.length} reconciliadores` })
}
const clavesBloques = new Set(bloques.map((b) => b.clave))

function idsValidos(ids, origen) {
  const ok = (ids || []).filter((id) => porId[id])
  const malos = (ids || []).filter((id) => !porId[id])
  if (malos.length) guardas.push({ etapa: 'reconciliacion', bloque: '', tipo: 'id_desconocido', severidad: 'aviso', detalle: `${origen} citó ids inexistentes: ${malos.join(', ')}` })
  return ok
}

// ------------------------------------------------------------ fusión
const conflictos = []
const descartados = []
function agregar(c) {
  const key = [...c.afirmaciones].sort().join('|')
  const existente = conflictos.find((x) => {
    const k = [...x.afirmaciones].sort().join('|')
    if (key && k === key) return true
    const a = new Set(x.afirmaciones)
    return c.afirmaciones.length > 0 && x.afirmaciones.length > 0 &&
      (c.afirmaciones.every((id) => a.has(id)) || x.afirmaciones.every((id) => c.afirmaciones.includes(id)))
  })
  if (existente) {
    existente.origen = uniq([...existente.origen.split('+'), c.origen]).join('+')
    existente.descripcion += ` // ${c.descripcion}`
    existente.afirmaciones = uniq([...existente.afirmaciones, ...c.afirmaciones])
    existente.bloques = uniq([...existente.bloques, ...c.bloques])
    existente.cifras = uniq([...(existente.cifras || []), ...(c.cifras || [])])
    if (c.gravedad === 'alta') existente.gravedad = 'alta'
    return
  }
  conflictos.push(c)
}

for (const l of lentesOk) {
  for (const c of l.conflictos || []) {
    const ids = idsValidos(c.afirmaciones, `lente ${l.lente}`)
    const bloquesLente = (c.bloques || []).filter((k) => clavesBloques.has(k))
    const bs = uniq([...bloquesLente, ...ids.map((id) => porId[id].bloque)])
    if (!bs.length) {
      guardas.push({ etapa: 'reconciliacion', bloque: claveFeature || '', tipo: 'conflicto_sin_ancla', severidad: 'bloqueante', detalle: `la lente ${l.lente} reportó un conflicto sin ids ni bloques válidos: ${c.descripcion}` })
      continue
    }
    agregar({ tipo: c.tipo, afirmaciones: ids, bloques: bs, descripcion: c.descripcion, gravedad: c.gravedad, origen: `lente:${l.lente}` })
  }
}
for (const c of candidatos) {
  const juicios = lentesOk.map((l) => (l.candidatos || []).find((x) => x.id === c.id)).filter(Boolean)
  if (juicios.length && juicios.every((j) => !j.real)) {
    descartados.push({ descripcion: c.descripcion, razon: juicios.map((j) => j.razon).join(' / ') })
    continue
  }
  agregar({ ...c, gravedad: c.tipo === 'veredicto' ? 'alta' : 'media', origen: 'determinístico' })
}
for (const a of afirmaciones.filter((x) => x.veredicto.estado === 'contradicho')) {
  agregar({
    tipo: 'contradicho', afirmaciones: [a.id], bloques: [a.bloque], gravedad: 'alta', origen: 'verificación',
    descripcion: `el verificador encontró otro valor para "${a.texto}": ${a.veredicto.valor_encontrado || '(ver evidencia)'}`,
  })
}

const orden = { alta: 0, media: 1, baja: 2 }
conflictos.sort((x, y) => (orden[x.gravedad] ?? 1) - (orden[y.gravedad] ?? 1))
conflictos.forEach((c, i) => { c.id = `C${i + 1}` })
const aDebatir = conflictos.slice(0, MAX_DEBATES)
if (conflictos.length > MAX_DEBATES) {
  log(`${conflictos.length - MAX_DEBATES} conflicto(s) quedan SIN debate por el tope de ${MAX_DEBATES}: van al checkpoint humano como "sin resolver".`)
  guardas.push({ etapa: 'reconciliacion', bloque: '', tipo: 'tope_debates', severidad: 'aviso', detalle: `sin debatir: ${conflictos.slice(MAX_DEBATES).map((c) => c.id).join(', ')}` })
}

const grupos = []
for (const g of [...gruposDet, ...lentesOk.flatMap((l) => l.grupos || [])]) {
  const ids = idsValidos(g.afirmaciones, 'grupo')
  if (uniq(ids.map((id) => porId[id].bloque)).length < 2) continue
  if (!grupos.some((x) => ids.every((id) => x.afirmaciones.includes(id)))) grupos.push({ afirmaciones: ids, descripcion: g.descripcion })
}
log(`Reconciliación: ${conflictos.length} conflicto(s) (${aDebatir.length} a debate), ${descartados.length} descartado(s), ${grupos.length} grupo(s) del mismo hecho.`)

// ------------------------------------------------------------ debate + fallo
const ARG_SCHEMA = {
  type: 'object',
  properties: {
    valor_sostenido: { type: 'string', description: 'qué versión del dato sostenés al final' },
    argumento: { type: 'string' },
    evidencia: { type: 'array', items: { type: 'object', properties: { url: { type: 'string' }, cita: { type: 'string' } }, required: ['url', 'cita'] } },
    encontre_sustento: { type: 'boolean' },
  },
  required: ['valor_sostenido', 'argumento', 'evidencia', 'encontre_sustento'],
}
const RULING_SCHEMA = {
  type: 'object',
  properties: {
    decision: { type: 'string', enum: ['mantener', 'corregir', 'retirar', 'matizar', 'sin_consenso'] },
    valor_correcto: { type: 'string', description: 'SÓLO el dato correcto, corto, sin prosa, sin explicación y sin ids (p. ej. "2 de julio de 2026", "17.000 ediciones"); vacío si no es corregir. La explicación va en razonamiento' },
    redaccion_sugerida: { type: 'string', description: 'una oración lista para reemplazar o agregar (vacía si mantener); sin ids de afirmaciones' },
    afirmaciones_afectadas: { type: 'array', items: { type: 'string' } },
    confianza: { type: 'string', enum: ['alta', 'media', 'baja'] },
    razonamiento: { type: 'string' },
    evidencia: { type: 'array', items: { type: 'object', properties: { url: { type: 'string' }, cita: { type: 'string' } }, required: ['url', 'cita'] } },
  },
  required: ['decision', 'valor_correcto', 'redaccion_sugerida', 'afirmaciones_afectadas', 'confianza', 'razonamiento', 'evidencia'],
}

function contextoConflicto(c) {
  const afs = c.afirmaciones.map((id) => porId[id]).map((a) =>
    `- ${a.id} [${a.bloque}] "${a.texto}" (cita: "${a.cita_textual}") — veredicto: ${a.veredicto.estado}; ` +
    `evidencia: ${(a.veredicto.evidencia || []).map((e) => e.url).join(' ') || 'ninguna'}; nota: ${a.veredicto.nota || ''}`).join('\n')
  const fuentes = uniq(c.bloques.map((k) => bloques.find((b) => b.clave === k)).filter(Boolean)
    .flatMap((b) => [b.fuente_url, ...(b.fuentes || []).map((f) => f.url)]).filter((u) => u && u.startsWith('http')))
  return `CONFLICTO ${c.id} (${c.tipo}): ${c.descripcion}\nAFIRMACIONES INVOLUCRADAS:\n${afs || '(sin afirmación extraída: ver descripción)'}\nFUENTES CITADAS POR LOS AUTORES: ${fuentes.join(' ') || 'ninguna'}`
}

const debatido = await pipeline(
  aDebatir,
  (c) => parallel([
    () => agent(`Sos DEFENSOR/A en un debate de verificación de una revista técnica.\n\n${contextoConflicto(c)}\n\nSostené la versión publicada del dato (si hay dos versiones en conflicto, la mejor sustentada). Buscá evidencia a favor: leé con WebFetch las fuentes citadas y hacé COMO MÁXIMO 2 búsquedas web. Honestidad antes que ganar: si no encontrás sustento, poné encontre_sustento=false y decilo. Toda evidencia debe ser de una fuente que leíste, con cita literal.`,
      { label: `debate:${c.id}:defensor`, phase: 'Debate', schema: ARG_SCHEMA }),
    () => agent(`Sos ESCÉPTICO/A en un debate de verificación de una revista técnica.\n\n${contextoConflicto(c)}\n\nTu trabajo es intentar REFUTAR el dato publicado: encontrar el valor correcto, la fecha correcta, o mostrar que no hay fuente que lo sostenga. Leé las fuentes citadas con WebFetch y hacé COMO MÁXIMO 2 búsquedas web. Toda evidencia debe ser de una fuente que leíste, con cita literal. Si al final el dato resulta correcto, reconocelo.`,
      { label: `debate:${c.id}:esceptico`, phase: 'Debate', schema: ARG_SCHEMA, model: args.modelo_verificador || undefined }),
  ]),
  (par, c) => {
    const [def, esc] = par || [null, null]
    const alegato = (nombre, x) => x
      ? `${nombre} sostiene "${x.valor_sostenido}" (sustento encontrado: ${x.encontre_sustento}): ${x.argumento}\nEvidencia: ${(x.evidencia || []).map((e) => `${e.url} — "${e.cita}"`).join(' | ') || 'ninguna'}`
      : `${nombre}: no respondió.`
    return agent(`Sos JUEZ/A de verificación de una revista técnica. Decidís con la evidencia presentada; podés hacer como máximo UN WebFetch para comprobar que una cita dudosa existe de verdad.\n\n${contextoConflicto(c)}\n\n${alegato('DEFENSOR', def)}\n\n${alegato('ESCÉPTICO', esc)}\n\nReglas de decisión:\n- mantener: hay evidencia leída que sostiene el dato tal como está publicado.\n- corregir: la evidencia indica otro valor. Dá valor_correcto (sólo el dato, corto: "2 de julio de 2026", no una explicación) y una redaccion_sugerida.\n- retirar: nadie encontró sustento para el dato. Un dato sin fuente no se publica.\n- matizar: el dato está sustentado pero falta contexto o atribución ("según X"), o la parte involucrada lo niega. Dá la redaccion_sugerida.\n- sin_consenso: SÓLO si hay evidencia fuerte y contradictoria en ambos sentidos. Pasa a decisión humana.\nafirmaciones_afectadas: los ids a los que aplica tu decisión — si el mismo dato aparece en varios bloques (sección y nota de fondo), incluí todos para que se corrija en todos lados.`,
      { label: `juez:${c.id}`, phase: 'Fallo', schema: RULING_SCHEMA }).then((r) => ({ c, def, esc, r }))
  },
)

const debates = []
const resoluciones = []
for (const x of debatido.filter(Boolean)) {
  debates.push({ conflicto_id: x.c.id, defensor: x.def, esceptico: x.esc })
  if (!x.r) continue
  let afectadas = idsValidos(x.r.afirmaciones_afectadas, `juez ${x.c.id}`)
  if (!afectadas.length) afectadas = x.c.afirmaciones
  resoluciones.push({ ...x.r, conflicto_id: x.c.id, afirmaciones_afectadas: afectadas, cifras: x.c.cifras || [], bloques: uniq([...x.c.bloques, ...afectadas.map((id) => porId[id].bloque)]) })
}
const sinFallo = aDebatir.filter((c) => !resoluciones.some((r) => r.conflicto_id === c.id))
for (const c of sinFallo) guardas.push({ etapa: 'reconciliacion', bloque: c.bloques.join(','), tipo: 'sin_fallo', severidad: 'aviso', detalle: `${c.id}: el debate no llegó a un fallo` })

return { grupos, conflictos, resoluciones, debates, descartados, candidatos_deterministicos: candidatos, guardas }
