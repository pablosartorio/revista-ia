export const meta = {
  name: 'condor-numero',
  description: 'Cóndor v2: redacción multi-agente con libro de afirmaciones, reconciliación cruzada, tapas y checkpoint humano',
  whenToUse: 'Producir un número de Cóndor. args: {numero, fecha_larga, semana_iso, ventana, raiz, modelo_verificador, ciudad_espacio, etapas?, semilla?}',
  phases: [
    { title: 'Investigación', detail: '9 corresponsalías en paralelo (8 vía web + espacio vía MCP)' },
    { title: 'Nota de fondo', detail: 'feature transversal; en paralelo se verifican las secciones' },
    { title: 'Estilo', detail: 'corrección de estilo con guarda de cifras y nombres' },
    { title: 'Arte', detail: 'dirección de arte: título, concepto y brief de tapa' },
  ],
}

const R = args.raiz
// args.etapas permite correr desde una copia congelada del pipeline (runs/numero-XX/pipeline)
const E = args.etapas || `${R}/pipeline/etapas`
// mismo formato que el CLI (`condor ... 01`): dos dígitos, para que rutas y "Nº XX" coincidan con Python
const N = /^\d+$/.test(String(args.numero || '')) ? String(args.numero).padStart(2, '0') : null
if (!N) throw new Error(`args.numero tiene que ser un número de ejemplar (p. ej. "01"); llegó ${JSON.stringify(args.numero)}`)
const MV = args.modelo_verificador
const guardas = []
// args.semilla = {origen, secciones: {clave: SECTION}, feature: FEATURE|null}: investigación ya hecha
// (p. ej. de una corrida cortada). Los beats que trae no lanzan agente; la verificación corre igual.
const SEM = args.semilla || null
const semSec = Object.fromEntries(Object.entries((SEM && SEM.secciones) || {}).filter(([, s]) => s && s.titulo && s.cuerpo && s.fuente_url))
const semFeat = SEM && SEM.feature && SEM.feature.titulo && SEM.feature.cuerpo ? SEM.feature : null

// Un workflow hijo que falla no tira abajo el número: se reemplaza por un resultado neutro
// y se deja una guarda bloqueante en los bloques afectados, para que decida el checkpoint.
async function hijo(etapa, script, a, neutro, afectados) {
  let r = null, error = ''
  try { r = await workflow({ scriptPath: `${E}/${script}` }, a) } catch (e) { error = String(e) }
  if (r) return r
  log(`La etapa ${etapa} falló (${error || 'sin resultado'}); se sigue con un resultado neutro.`)
  for (const clave of afectados) guardas.push({ etapa, bloque: clave, tipo: 'etapa_caida', severidad: 'bloqueante', detalle: `la etapa ${etapa} no devolvió resultado${error ? ': ' + error.slice(0, 200) : ''}` })
  return neutro
}
const VER_VACIA = { afirmaciones: [], contexto_omitido: [], guardas: [] }

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
function norm(s) {
  return (s || '').normalize('NFKD').replace(/[\u0300-\u036f]/g, '').replace(/\s+/g, ' ').trim().toLowerCase()
}
function textoBloque(b) { return [b.titulo, b.bajada, b.cuerpo].filter(Boolean).join(' ') }
function uniq(xs) { return [...new Set(xs)] }
function multiset(xs) { const m = {}; for (const x of xs) m[x] = (m[x] || 0) + 1; return m }
function mismoMultiset(a, b) {
  const ma = multiset(a), mb = multiset(b)
  const ks = new Set([...Object.keys(ma), ...Object.keys(mb)])
  return [...ks].every((k) => ma[k] === mb[k])
}

const LINEA = `Audiencia: lector con formación técnica en ciencia de datos/ML (nivel junior en un equipo de Data Science & AI, base física), interesado en IA global con foco en Argentina/LatAm. Registro: MIT Technology Review / The Gradient — técnico pero legible. Reglas: síntesis, no resumen (qué pasó + dato concreto + por qué importa); dato concreto siempre que exista (parámetros, benchmark, USD, fecha); sin lenguaje marketinero; términos técnicos en inglés cuando no hay equivalente establecido; para LLMs aclarar si es open-weight o propietario; nombres consistentes (Anthropic, Meta AI); nunca inventar información detrás de paywall; preferir fuentes primarias y medios especializados.`

const SECTION_SCHEMA = {
  type: 'object',
  properties: {
    titulo: { type: 'string', description: 'título concreto, no genérico' },
    cuerpo: { type: 'string', description: '1-2 párrafos separados por línea en blanco' },
    open_weight: { type: 'string', description: 'para LLMs "open-weight" o "propietario"; si no aplica, "no aplica"' },
    fuente_nombre: { type: 'string' },
    fuente_url: { type: 'string' },
    fecha: { type: 'string', description: 'fecha de publicación de la fuente, AAAA-MM-DD' },
  },
  required: ['titulo', 'cuerpo', 'open_weight', 'fuente_nombre', 'fuente_url', 'fecha'],
}

function beatPrompt(seccion, tema) {
  return `Sos corresponsal de la sección "${seccion}" de Cóndor, revista de IA, tecnología y ciencia. Línea editorial: ${LINEA}

Buscá en la web (entre 2 y 4 búsquedas; el cupo de la redacción es limitado) UNA noticia real, verificable y con dato concreto, publicada entre el ${args.ventana}, sobre: ${tema}. Preferí fuentes primarias o medios especializados, y leé la nota con WebFetch antes de escribir.
Escribí título y cuerpo (1-2 párrafos). Cada cifra, fecha y nombre que uses tiene que estar en la fuente que leíste: después un verificador independiente va a chequear cada dato contra ella. No inventes URLs ni redondees cifras. Si la parte involucrada niega o discute el hecho, decilo.`
}

const BEATS = [
  { clave: 'llm', seccion: 'Modelos fundacionales y LLMs', tema: 'un release, benchmark o cambio de licencia relevante de un LLM (aclará si es open-weight o propietario)' },
  { clave: 'hardware', seccion: 'Hardware e infraestructura', tema: 'chips, data centers, energía o memoria para IA' },
  { clave: 'politica', seccion: 'Regulación y política', tema: 'legislación, export controls, o IA militar/gubernamental' },
  { clave: 'safety', seccion: 'Seguridad y alineación', tema: 'interpretabilidad, incidentes de seguridad, red-teaming o evaluaciones de riesgo' },
  { clave: 'ciencia_salud', seccion: 'IA aplicada — Ciencia y salud', tema: 'drug discovery, genómica, diagnóstico o clima con IA' },
  { clave: 'industria_robotica', seccion: 'IA aplicada — Industria y robótica', tema: 'robots humanoides, coding agents empresariales o vehículos autónomos' },
  { clave: 'argentina', seccion: 'Argentina', tema: 'política científica de IA, CONICET, INVAP, CONAE, data centers o startups argentinas de IA' },
  { clave: 'latam', seccion: 'América Latina', tema: 'Brasil, Chile, México, Colombia o Uruguay: regulación, inversión o ecosistema de IA (no Argentina)' },
]
const ESPACIO = {
  clave: 'espacio', seccion: 'Ciencia y Espacio — Patagonia',
  prompt: `Sos corresponsal de la sección "Ciencia y Espacio — Patagonia" de Cóndor. Línea editorial: ${LINEA}

NO uses búsqueda web. Usá ToolSearch para cargar las herramientas del servidor MCP "patagonia-espacial" (listar_satelites, donde_esta, proximos_pasos) y llamalas. Elegí un satélite relevante para el ecosistema espacial argentino (perfil SAOCOM, ARSAT, SAC-D o similar) que NO sea el SAOCOM 1A si hay otra opción interesante (ya fue nota en el número anterior). Consultá proximos_pasos con solo_visibles=True para ${args.ciudad_espacio || 'Bariloche'} en los próximos días, y escribí una nota corta: qué satélite, para qué sirve, cuándo pasa (hora argentina), si se ve a ojo desnudo, y por qué le importa a alguien que trabaja con datos satelitales. Usá sólo datos que devolvió el MCP. Como fuente_nombre poné "MCP patagonia-espacial" y como fuente_url "mcp://patagonia-espacial".`,
}

// ------------------------------------------------------------ investigación
phase('Investigación')
const todasBeats = [...BEATS.map((b) => ({ ...b, prompt: beatPrompt(b.seccion, b.tema) })), ESPACIO]
const reusados = todasBeats.filter((b) => semSec[b.clave]).map((b) => b.clave)
log(`Cóndor Nº ${N}: lanzando ${todasBeats.length - reusados.length} corresponsalías (ventana ${args.ventana})${reusados.length ? `; de la semilla (${(SEM && SEM.origen) || 'sin origen'}): ${reusados.join(', ')}` : ''}.`)
const beatRaw = await parallel(todasBeats.map((b) => () => semSec[b.clave]
  ? Promise.resolve(semSec[b.clave])
  : agent(b.prompt, { label: `seccion:${b.clave}`, phase: 'Investigación', schema: SECTION_SCHEMA })))
const secciones = todasBeats.map((b, i) => beatRaw[i] ? {
  clave: b.clave, tipo: 'seccion', seccion: b.seccion, titulo: beatRaw[i].titulo, bajada: '', cuerpo: beatRaw[i].cuerpo,
  fuente_nombre: beatRaw[i].fuente_nombre, fuente_url: beatRaw[i].fuente_url, fecha: beatRaw[i].fecha,
  open_weight: beatRaw[i].open_weight, fuentes: [],
} : null).filter(Boolean)
for (const b of todasBeats) if (!secciones.some((s) => s.clave === b.clave)) {
  guardas.push({ etapa: 'investigacion', bloque: b.clave, tipo: 'corresponsalia_caida', severidad: 'aviso', detalle: 'la corresponsalía no entregó nota; la sección queda fuera del número' })
}
log(`${secciones.length}/9 corresponsalías entregaron. Nota de fondo + verificación de secciones en paralelo.`)

// ------------------------------------------------------------ nota de fondo || verificación de secciones
phase('Nota de fondo')
const FEATURE_SCHEMA = {
  type: 'object',
  properties: {
    titulo: { type: 'string' },
    bajada: { type: 'string', description: 'subtítulo de una línea' },
    cuerpo: { type: 'string', description: '4-6 párrafos separados por línea en blanco' },
    fuentes: { type: 'array', items: { type: 'object', properties: { nombre: { type: 'string' }, url: { type: 'string' } }, required: ['nombre', 'url'] } },
  },
  required: ['titulo', 'bajada', 'cuerpo', 'fuentes'],
}
const reportes = secciones.map((s) => `[${s.clave} · ${s.seccion}] ${s.titulo}\n${s.cuerpo}\nFuente: ${s.fuente_nombre} ${s.fuente_url}`).join('\n\n')
const featurePrompt = `Sos editor/a de la nota de fondo de Cóndor Nº ${N} (${args.fecha_larga}). Línea editorial: ${LINEA}

Abajo están los reportes de las corresponsalías. NO los resumas uno por uno: elegí UN ángulo transversal que conecte 2 o más de ellos (una tensión, una causa común, una implicancia que ninguno señala por separado) y escribí una pieza analítica de 4-6 párrafos.

Reglas de datos (después se verifica todo, afirmación por afirmación, y se compara contra las secciones):
- Toda cifra, fecha o nombre que uses tiene que venir TAL CUAL de un reporte de abajo, o de una fuente nueva que leas y cites en "fuentes".
- No calcules duraciones, porcentajes ni comparaciones nuevas ("el triple", "seis semanas") salvo que salgan directo de un dato citado.
- Si un dato de un reporte te parece dudoso, no lo uses.
Citá en "fuentes" las URLs reales que sostienen tu nota (pueden ser las de los reportes).

REPORTES:
${reportes}`

if (semFeat) log('Nota de fondo: se reusa la de la semilla.')
let [featRaw, verSec] = await Promise.all([
  semFeat ? Promise.resolve(semFeat) : agent(featurePrompt, { label: 'feature:nota-de-fondo', phase: 'Nota de fondo', schema: FEATURE_SCHEMA }).catch(() => null),
  workflow({ scriptPath: `${E}/verificar.workflow.js` }, { bloques: secciones, modelo_verificador: MV }).catch((e) => ({ error: String(e) })),
])
if (!verSec || verSec.error) {
  log(`La verificación en paralelo falló (${verSec && verSec.error}); se reintenta en serie.`)
  verSec = await hijo('verificacion', 'verificar.workflow.js', { bloques: secciones, modelo_verificador: MV }, VER_VACIA, secciones.map((s) => s.clave))
}
const bloques = [...secciones]
if (featRaw) {
  bloques.unshift({
    clave: 'feature', tipo: 'feature', seccion: 'Nota de fondo', titulo: featRaw.titulo, bajada: featRaw.bajada, cuerpo: featRaw.cuerpo,
    fuente_nombre: '', fuente_url: '', fecha: args.fecha_larga, open_weight: 'no aplica', fuentes: featRaw.fuentes || [],
  })
} else {
  guardas.push({ etapa: 'nota_de_fondo', bloque: 'feature', tipo: 'feature_caida', severidad: 'aviso', detalle: 'no se escribió nota de fondo; el número sale sin feature' })
}
const investigacion = Object.fromEntries(bloques.map((b) => [b.clave, { titulo: b.titulo, bajada: b.bajada, cuerpo: b.cuerpo }]))

const verFeat = featRaw
  ? await hijo('verificacion', 'verificar.workflow.js', { bloques: [bloques[0]], modelo_verificador: MV }, VER_VACIA, ['feature'])
  : VER_VACIA
const afirmaciones = [...verSec.afirmaciones, ...verFeat.afirmaciones]
const contexto_omitido = [...verSec.contexto_omitido, ...verFeat.contexto_omitido]
guardas.push(...verSec.guardas, ...verFeat.guardas)
const cuenta = (est) => afirmaciones.filter((a) => a.veredicto.estado === est).length
log(`Libro de afirmaciones: ${afirmaciones.length} (confirmadas ${cuenta('confirmado')}, no verificables ${cuenta('no_verificable')}, contradichas ${cuenta('contradicho')}).`)

// ------------------------------------------------------------ reconciliación cruzada + cierre
const rec = await hijo('reconciliacion', 'reconciliar.workflow.js', { bloques, afirmaciones, modelo_verificador: MV, max_debates: 10 },
  { grupos: [], conflictos: [], resoluciones: [], debates: [], descartados: [], candidatos_deterministicos: [], guardas: [] },
  bloques.map((b) => b.clave))
guardas.push(...rec.guardas)
// fallos que editan y comparten afirmaciones con otro fallo: los que consolidar tiene que unir
const EDITAN = ['corregir', 'retirar', 'matizar']
const usos = {}
for (const r of rec.resoluciones) if (EDITAN.includes(r.decision)) for (const id of r.afirmaciones_afectadas) usos[id] = (usos[id] || 0) + 1
const bloquesCompartidos = uniq(rec.resoluciones.filter((r) => EDITAN.includes(r.decision) && r.afirmaciones_afectadas.some((id) => usos[id] > 1)).flatMap((r) => r.bloques))
const con = await hijo('consolidacion', 'consolidar.workflow.js', {
  bloques, afirmaciones, conflictos: rec.conflictos, resoluciones: rec.resoluciones, debates: rec.debates,
}, { resoluciones: rec.resoluciones, reemplazadas: [], componentes: [], guardas: [] }, bloquesCompartidos)
guardas.push(...con.guardas)
const cie = await hijo('cierre', 'cierre.workflow.js', {
  bloques, afirmaciones, resoluciones: con.resoluciones, conflictos: rec.conflictos, contexto_omitido,
}, {
  bloques, guardas: [], correcciones: [],
  afirmaciones: afirmaciones.map((a) => ({ ...a, estado_final: a.veredicto.estado })),
  resoluciones: con.resoluciones.map((r) => ({ ...r, bloques_pendientes: EDITAN.includes(r.decision) ? r.bloques : [], aplicada: false })),
}, uniq([...con.resoluciones.filter((r) => EDITAN.includes(r.decision)).flatMap((r) => r.bloques), ...contexto_omitido.map((c) => c.bloque)]))
guardas.push(...cie.guardas)
const cierre = Object.fromEntries(cie.bloques.map((b) => [b.clave, { titulo: b.titulo, bajada: b.bajada, cuerpo: b.cuerpo }]))

// ------------------------------------------------------------ estilo
phase('Estilo')
const ESTILO_SCHEMA = {
  type: 'object',
  properties: {
    bloques: { type: 'array', items: { type: 'object', properties: { clave: { type: 'string' }, titulo: { type: 'string' }, bajada: { type: 'string' }, cuerpo: { type: 'string' } }, required: ['clave', 'titulo', 'bajada', 'cuerpo'] } },
    observaciones: { type: 'array', items: { type: 'string' } },
  },
  required: ['bloques', 'observaciones'],
}
// un nombre corregido o retirado conserva el valor viejo en `valor`: no hay que protegerlo
const nombresProtegidos = cie.afirmaciones.filter((a) => ['nombre', 'atribucion'].includes(a.tipo) && !['retirado', 'corregido'].includes(a.estado_final)).map((a) => a.valor)
const estilo = await agent(`Sos corrector/a de estilo de Cóndor. Línea editorial: ${LINEA}

Recibís el número completo, ya verificado y corregido. Homogeneizá tono, longitud de párrafo, nombres de empresas/modelos según la línea editorial, y sacá lenguaje marketinero. PROHIBIDO: cambiar, agregar, quitar o redondear cifras y fechas; cambiar nombres propios o atribuciones ("X reveló", "según Y"); agregar información. Si algo te parece factualmente raro, no lo toques: anotalo en observaciones. Devolvé TODOS los bloques con su clave exacta; si un bloque no necesita cambios, devolvelo igual.

${cie.bloques.map((b) => `### clave=${b.clave}\nTITULO: ${b.titulo}\nBAJADA: ${b.bajada || ''}\nCUERPO:\n${b.cuerpo}`).join('\n\n')}`,
{ label: 'estilo:corrector', phase: 'Estilo', schema: ESTILO_SCHEMA })

const bloquesFinales = cie.bloques.map((b) => {
  const e = estilo && (estilo.bloques || []).find((x) => x.clave === b.clave)
  if (!e) {
    guardas.push({ etapa: 'estilo', bloque: b.clave, tipo: 'sin_edicion', severidad: 'aviso', detalle: 'el corrector no devolvió este bloque; queda la versión de cierre' })
    return b
  }
  // se compara contra lo que se publicaría: las secciones no publican bajada, así que la del corrector no cuenta
  const editado = { ...b, titulo: e.titulo, bajada: b.tipo === 'feature' ? e.bajada : (b.bajada || ''), cuerpo: e.cuerpo }
  const antes = textoBloque(b), despues = textoBloque(editado)
  const problemas = []
  if (!mismoMultiset(nums(antes), nums(despues))) problemas.push('cambió cifras o fechas')
  const ratio = despues.length / Math.max(1, antes.length)
  if (ratio < 0.75 || ratio > 1.25) problemas.push(`cambió demasiado el largo (${Math.round(ratio * 100)}%)`)
  const perdidos = nombresProtegidos.filter((n) => n && norm(antes).includes(norm(n)) && !norm(despues).includes(norm(n)))
  if (perdidos.length) problemas.push(`perdió nombres o atribuciones: ${perdidos.join(', ')}`)
  if (problemas.length) {
    guardas.push({ etapa: 'estilo', bloque: b.clave, tipo: 'edicion_rechazada', severidad: 'aviso', detalle: `se descartó la corrección de estilo (${problemas.join('; ')}); queda la versión de cierre` })
    return b
  }
  return editado
})

// ------------------------------------------------------------ dirección de arte
phase('Arte')
const ART_SCHEMA = {
  type: 'object',
  properties: {
    titulo_numero: { type: 'string' },
    concepto_tapa: { type: 'string', description: '2-3 líneas: qué conecta al número' },
    nota_destacada: { type: 'string', description: 'clave del bloque destacado y por qué' },
    notas_diseno: { type: 'string' },
    brief_tapa: {
      type: 'object',
      properties: {
        concepto: { type: 'string' }, metafora_visual: { type: 'string' }, paleta: { type: 'string' },
        composicion: { type: 'string' }, evitar: { type: 'string' },
        dato_ancla_id: { type: 'string', description: 'id de UNA afirmación confirmada para la tapa data-driven, o vacío' },
      },
      required: ['concepto', 'metafora_visual', 'paleta', 'composicion', 'evitar', 'dato_ancla_id'],
    },
  },
  required: ['titulo_numero', 'concepto_tapa', 'nota_destacada', 'notas_diseno', 'brief_tapa'],
}
const finales = cie.afirmaciones
// Mismo criterio que riesgos_bloque() del checkpoint: un bloque con cualquiera de estos riesgos
// no puede ser nota destacada ni aportar el dato ancla ni una línea de tapa.
const ESTADOS_RIESGO = ['no_verificable', 'contradicho', 'sin_consenso', 'no_aplicado']
// un conflicto está resuelto si tiene fallo propio o si quedó cubierto por uno consolidado
const conFallo = new Set(cie.resoluciones.flatMap((r) => [r.conflicto_id, ...(r.conflictos_cubiertos || [])]))
const riesgosas = new Set([
  ...finales.filter((a) => ESTADOS_RIESGO.includes(a.estado_final)).map((a) => a.bloque),
  ...cie.resoluciones.flatMap((r) => r.decision === 'sin_consenso' ? r.bloques : (r.bloques_pendientes || [])),
  ...rec.conflictos.filter((c) => !conFallo.has(c.id)).flatMap((c) => c.bloques),
  ...guardas.filter((g) => g.severidad === 'bloqueante' && g.bloque).map((g) => g.bloque),
])
// sólo un dato confirmado tal como está publicado puede ir a la tapa (un "corregido" conserva el valor viejo en `valor`)
const confirmadas = finales.filter((a) => a.estado_final === 'confirmado' && !riesgosas.has(a.bloque))
const arte = await agent(`Sos director/a de arte de Cóndor Nº ${N}. No escribís contenido: decidís cómo se presenta el número y escribís el brief para los ilustradores de tapa.

NOTAS DEL NÚMERO (bloques con riesgos abiertos: ${[...riesgosas].join(', ') || 'ninguno'} — esos NO pueden ser la nota destacada ni aportar datos o líneas a la tapa):
${bloquesFinales.map((b) => `- [${b.clave}] ${b.titulo} — ${(b.cuerpo || '').split('\n')[0].slice(0, 280)}`).join('\n')}

AFIRMACIONES CONFIRMADAS disponibles como dato ancla para una tapa data-driven (usá el id):
${confirmadas.slice(0, 60).map((a) => `${a.id}: ${a.texto} (${a.valor})`).join('\n')}

Decidí: título del número (llamativo, no sensacionalista), concepto de tapa, nota destacada, notas de diseño, y un brief de tapa concreto (metáfora visual dibujable con formas geométricas, paleta, composición, qué evitar — nada de robots genéricos ni logos reales).`,
{ label: 'arte:director', phase: 'Arte', schema: ART_SCHEMA })

let datoAncla = null
if (arte && arte.brief_tapa && arte.brief_tapa.dato_ancla_id) {
  const a = confirmadas.find((x) => x.id === arte.brief_tapa.dato_ancla_id)
  if (a && !riesgosas.has(a.bloque)) datoAncla = { id: a.id, texto: a.texto, valor: a.valor }
  else guardas.push({ etapa: 'arte', bloque: '', tipo: 'dato_ancla_invalido', severidad: 'aviso', detalle: `el dato ancla ${arte.brief_tapa.dato_ancla_id} no es una afirmación confirmada de un bloque sin riesgos: la tapa no lleva cifras` })
}

// ------------------------------------------------------------ tapa
const titulares = bloquesFinales.filter((b) => !riesgosas.has(b.clave)).map((b) => b.titulo)
const tapa = await hijo('tapa', 'tapa.workflow.js', {
  numero: N, dir: `${R}/output/numero-${N}/tapa`, raiz: R, brief: (arte && arte.brief_tapa) || {},
  titulo_numero: (arte && arte.titulo_numero) || `Cóndor Nº ${N}`, fecha_larga: args.fecha_larga,
  titulares, dato_ancla: datoAncla,
}, { candidatos: [], ganador: null, jueces: [], correccion: 'etapa caída', guardas: [] }, [])
if (!tapa.candidatos.length && !(tapa.guardas || []).some((g) => g.tipo === 'sin_tapa')) guardas.push({ etapa: 'tapa', bloque: '', tipo: 'sin_tapa', severidad: 'bloqueante', detalle: 'no hay candidatos de tapa: el número no se puede publicar hasta que haya una' })
guardas.push(...(tapa.guardas || []))

return {
  version: 2,
  numero: N,
  meta: {
    titulo_numero: arte ? arte.titulo_numero : `Cóndor Nº ${N}`,
    concepto_tapa: arte ? arte.concepto_tapa : '',
    nota_destacada: arte ? arte.nota_destacada : '',
    notas_diseno: arte ? arte.notas_diseno : '',
    brief_tapa: arte ? arte.brief_tapa : null,
    dato_ancla: datoAncla,
    fecha: args.fecha_larga,
    semana_iso: args.semana_iso,
    ventana: args.ventana,
    modelo_verificador: MV,
    semilla: SEM ? { origen: SEM.origen || '', beats_reusados: reusados, feature_reusada: !!semFeat } : null,
  },
  bloques: bloquesFinales,
  versiones: { investigacion, cierre },
  afirmaciones: finales,
  grupos: rec.grupos,
  conflictos: rec.conflictos,
  resoluciones: cie.resoluciones,
  debates: rec.debates,
  consolidacion: { componentes: con.componentes, reemplazadas: con.reemplazadas },
  descartados: rec.descartados,
  candidatos_deterministicos: rec.candidatos_deterministicos,
  correcciones: cie.correcciones,
  contexto_omitido,
  guardas,
  estilo: { observaciones: (estilo && estilo.observaciones) || [] },
  tapa: { candidatos: tapa.candidatos, ganador: tapa.ganador, jueces: tapa.jueces, correccion: tapa.correccion },
}
