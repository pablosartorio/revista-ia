export const meta = {
  name: 'condor-tapa',
  description: 'Cóndor: tapa del número — 3 ilustradores, panel de 2 jueces visuales, ronda de corrección del ganador',
  whenToUse: 'Etapa hija del pipeline de Cóndor; args: {numero, dir, raiz, brief, titulo_numero, fecha_larga, titulares, dato_ancla}',
  phases: [
    { title: 'Ilustración', detail: '3 candidatos SVG con enfoques distintos, cada uno validado, rasterizado y autorevisado' },
    { title: 'Jurado', detail: '2 jueces con lentes distintas miran los PNG y puntúan' },
    { title: 'Corrección', detail: 'el ganador corrige lo que señalaron los jueces; un juez confirma que mejoró' },
  ],
}

const N = args.numero
const DIR = args.dir
const CLI = `uv run --project ${args.raiz} condor`
const brief = args.brief || {}
const requeridos = ['Cóndor', N]

const ENFOQUES = [
  { id: 'A', angulo: 'editorial tipográfica', desc: 'La tapa la resuelve la tipografía: masthead fuerte, título del número grande, jerarquía clara, un único elemento gráfico abstracto de apoyo. Referencias: tapas de MIT Technology Review, The Gradient, revistas suizas.' },
  { id: 'B', angulo: 'metáfora visual', desc: 'Una ilustración vectorial conceptual que traduce la metáfora del brief en formas geométricas simples (sin intentar realismo). Poco texto además del masthead y el título.' },
  { id: 'C', angulo: 'data-driven', desc: 'La tapa se construye visualizando un dato REAL del número (el dato ancla del brief): una escala, una curva, una órbita, una proporción. El dato tiene que dibujarse con su valor exacto y figurar escrito una vez.' },
]

const COVER_SCHEMA = {
  type: 'object',
  properties: {
    svg: { type: 'string', description: 'ruta absoluta del SVG final' },
    png: { type: 'string' },
    png_mini: { type: 'string' },
    descripcion: { type: 'string', description: 'qué muestra la tapa y por qué, en 1-2 oraciones' },
    textos_en_tapa: { type: 'array', items: { type: 'string' } },
    validacion_ok: { type: 'boolean', description: 'true sólo si el último `condor tapa-validar` salió ok' },
    iteraciones: { type: 'integer' },
    autoevaluacion: { type: 'string', description: 'qué mejoraste mirando el PNG y qué limitación queda' },
  },
  required: ['svg', 'png', 'png_mini', 'descripcion', 'textos_en_tapa', 'validacion_ok', 'iteraciones', 'autoevaluacion'],
}

function reglasComunes(archivo) {
  return `Especificación técnica (obligatoria):
- Escribí un SVG de tapa de revista vertical en ${archivo}: <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 1600" width="1200" height="1600">. Creá el directorio si no existe.
- Sin <image>, <script>, <foreignObject>, sin href externos, sin atributos on*. Sólo formas, gradientes, patrones y <text>.
- Fuentes instaladas que podés usar en font-family: "Archivo Black", "Archivo", "Inter", "Inter Display", "EB Garamond", "Lato", "Fira Code". Otras se reemplazan y rompen el diseño.
- Textos obligatorios: el masthead "CÓNDOR" (con tilde), "Nº ${N}", la fecha "${args.fecha_larga}", y el título del número: "${args.titulo_numero}". Ortografía castellana impecable (tildes, Nº).
- Líneas de tapa: como máximo 3, y cada una tiene que corresponder a una nota REAL del número. Títulos disponibles (podés acortarlos sin cambiar el sentido ni los datos):
${(args.titulares || []).map((t) => `  · ${t}`).join('\n')}
- Prohibido: inventar datos o cifras, logos de empresas reales, caras de personas reales, texto en inglés salvo nombres propios.
- Tiene que leerse en miniatura: el masthead y el título legibles a 300 px de ancho.

Procedimiento (iterá hasta 3 veces):
1. Escribí el SVG.
2. Validá: ${CLI} tapa-validar ${archivo} --requerido "Cóndor" --requerido "${N}"
3. Rasterizá: ${CLI} tapa-render ${archivo}   (genera el .png de 1200 px y el -mini.png de 300 px)
4. MIRÁ los dos PNG con la herramienta Read. Buscá: texto cortado o que se sale del lienzo, superposiciones, contraste pobre, algo ilegible en la miniatura, tildes mal renderizadas, composición desequilibrada.
5. Corregí y repetí. Devolvé las rutas absolutas finales.`
}

function ilustradorPrompt(e) {
  const archivo = `${DIR}/candidato-${e.id}.svg`
  return `Sos ilustrador/a de tapas de "Cóndor", revista de IA, tecnología y ciencia con mirada patagónica (dark, técnica, sobria; paleta base azul noche #0a0f1e con acentos violeta #8b5cf6 y celeste #0ea5e9, salvo que el brief pida otra).

BRIEF DEL DIRECTOR DE ARTE:
- Concepto: ${brief.concepto || ''}
- Metáfora visual: ${brief.metafora_visual || ''}
- Paleta: ${brief.paleta || '(base de la revista)'}
- Composición sugerida: ${brief.composicion || ''}
- Evitar: ${brief.evitar || ''}
${args.dato_ancla ? `- Dato ancla (confirmado por verificación): ${args.dato_ancla.texto} — valor: ${args.dato_ancla.valor}` : '- No hay dato ancla confirmado: no pongas cifras en la tapa.'}

TU ENFOQUE (${e.id} · ${e.angulo}): ${e.desc}
${e.id === 'C' && !args.dato_ancla ? 'Como no hay dato ancla confirmado, visualizá una estructura real del número (p. ej. cuántas notas por sección) sin inventar cifras.' : ''}

${reglasComunes(archivo)}`
}

phase('Ilustración')
const candidatosRaw = await parallel(ENFOQUES.map((e) => () =>
  agent(ilustradorPrompt(e), { label: `tapa:ilustrador-${e.id}`, phase: 'Ilustración', schema: COVER_SCHEMA })
    .then((r) => r && { ...r, id: e.id, angulo: e.angulo })))
const candidatos = candidatosRaw.filter(Boolean)
const guardas = []
if (candidatos.length < ENFOQUES.length) guardas.push({ etapa: 'tapa', bloque: '', tipo: 'ilustrador_caido', severidad: 'aviso', detalle: `entregaron ${candidatos.length}/${ENFOQUES.length}` })
for (const c of candidatos.filter((x) => !x.validacion_ok)) guardas.push({ etapa: 'tapa', bloque: '', tipo: 'tapa_invalida', severidad: 'aviso', detalle: `el candidato ${c.id} no pasó la validación` })
const validos = candidatos.filter((c) => c.validacion_ok)
if (!validos.length) {
  guardas.push({ etapa: 'tapa', bloque: '', tipo: 'sin_tapa', severidad: 'bloqueante', detalle: 'ningún candidato pasó la validación' })
  return { candidatos, ganador: null, jueces: [], guardas }
}

// ------------------------------------------------------------ jurado
phase('Jurado')
const CRITERIOS = ['fidelidad_al_brief', 'jerarquia', 'legibilidad_miniatura', 'oficio', 'honestidad']
const JUDGE_SCHEMA = {
  type: 'object',
  properties: {
    puntajes: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          candidato: { type: 'string' },
          ...Object.fromEntries(CRITERIOS.map((k) => [k, { type: 'integer', minimum: 1, maximum: 10 }])),
          problemas: { type: 'array', items: { type: 'string' }, description: 'problemas concretos y corregibles, en orden de importancia' },
        },
        required: ['candidato', ...CRITERIOS, 'problemas'],
      },
    },
    preferido: { type: 'string' },
    razon: { type: 'string' },
  },
  required: ['puntajes', 'preferido', 'razon'],
}
const LENTES = [
  { id: 'editorial', foco: 'EDITORIAL: ¿la tapa comunica el concepto del número? ¿Promete sólo lo que el número tiene (honestidad: sin datos inventados, líneas de tapa que corresponden a notas reales)? ¿Tiene voz propia de revista técnica seria, sin clichés de "robot IA"?' },
  { id: 'visual', foco: 'VISUAL: legibilidad en miniatura (mirá los -mini.png), contraste, jerarquía tipográfica, composición, errores de render (texto cortado, superposiciones, tildes rotas, fuentes reemplazadas), oficio de diseño.' },
]
const listado = validos.map((c) => `- Candidato ${c.id} (${c.angulo}): ${c.png} y miniatura ${c.png_mini}. Autor: "${c.descripcion}"`).join('\n')
const jueces = (await parallel(LENTES.map((l) => () =>
  agent(`Sos jurado de tapas de "Cóndor" (revista de IA y ciencia). Lente: ${l.foco}

Brief: ${brief.concepto || ''} — metáfora: ${brief.metafora_visual || ''}
Título del número: "${args.titulo_numero}". Notas reales del número: ${(args.titulares || []).join(' | ')}

Candidatos (mirá TODOS los PNG, en tamaño completo y miniatura, con la herramienta Read):
${listado}

Puntuá cada candidato de 1 a 10 en: ${CRITERIOS.join(', ')}. En "problemas" listá defectos concretos y corregibles ("el subtítulo se corta en el borde derecho", "la fecha es ilegible en miniatura"). Elegí un preferido. Sé exigente: un 9 es una tapa publicable tal cual.`,
    { label: `tapa:juez-${l.id}`, phase: 'Jurado', schema: JUDGE_SCHEMA }).then((r) => r && { ...r, lente: l.id })))).filter(Boolean)

if (jueces.length < LENTES.length) guardas.push({ etapa: 'tapa', bloque: '', tipo: 'jurado_caido', severidad: 'aviso', detalle: `respondieron ${jueces.length}/${LENTES.length} jueces` })
for (const c of validos) {
  c.puntajes = {}
  c.problemas = []
  let suma = 0, n = 0
  for (const j of jueces) {
    const p = (j.puntajes || []).find((x) => x.candidato === c.id)
    if (!p) {
      guardas.push({ etapa: 'tapa', bloque: '', tipo: 'puntaje_faltante', severidad: 'aviso', detalle: `el juez ${j.lente} no puntuó al candidato ${c.id}` })
      continue
    }
    // el total lo calcula el código, no el juez; se promedia sobre los jueces que puntuaron
    suma += CRITERIOS.reduce((acc, k) => acc + (Number.isFinite(p[k]) ? p[k] : 0), 0)
    n += 1
    c.puntajes[j.lente] = Object.fromEntries(CRITERIOS.map((k) => [k, p[k]]))
    c.problemas.push(...(p.problemas || []))
  }
  c.jueces_que_puntuaron = n
  c.total = n ? Math.round((suma / n) * 10) / 10 : 0
}
if (!jueces.length) {
  log('Jurado: no respondió ningún juez; no se sugiere tapa (la elige la persona en el checkpoint).')
  return { candidatos: candidatos.map((c) => ({ ...c, validacion: { ok: !!c.validacion_ok } })), ganador: null, jueces: [], correccion: 'sin jurado', guardas }
}
const editorial = jueces.find((j) => j.lente === 'editorial')
validos.sort((a, b) => b.total - a.total || ((editorial && editorial.preferido === b.id) ? 1 : 0) - ((editorial && editorial.preferido === a.id) ? 1 : 0))
let ganador = validos[0]
log(`Jurado: ${validos.map((c) => `${c.id}=${c.total}`).join(', ')} (promedio por juez, máx. ${CRITERIOS.length * 10}) → ganador ${ganador.id}`)

// ------------------------------------------------------------ corrección del ganador
phase('Corrección')
let correccion = 'no hizo falta'
if (ganador.problemas.length) {
  const archivo = `${DIR}/candidato-${ganador.id}2.svg`
  const v2 = await agent(`Sos el/la ilustrador/a de la tapa ganadora de "Cóndor" Nº ${N}. Partí de tu SVG ${ganador.svg} (leelo) y corregí estos problemas que señaló el jurado, sin cambiar el concepto ni agregar elementos nuevos:
${ganador.problemas.slice(0, 8).map((p) => `- ${p}`).join('\n')}

Guardá la versión corregida como ${archivo} (no pises el original).

${reglasComunes(archivo)}`, { label: `tapa:correccion-${ganador.id}`, phase: 'Corrección', schema: COVER_SCHEMA })
  if (v2 && v2.validacion_ok) {
    const veredicto = await agent(`Compará dos versiones de la tapa de "Cóndor" Nº ${N}. Mirá los cuatro PNG con Read:
- ORIGINAL: ${ganador.png} (miniatura ${ganador.png_mini})
- CORREGIDA: ${v2.png} (miniatura ${v2.png_mini})
Problemas que debía corregir: ${ganador.problemas.slice(0, 8).join(' | ')}
¿La corregida resuelve los problemas sin introducir otros nuevos? Respondé mejor=true sólo si es claramente mejor o igual y sin regresiones.`,
    { label: `tapa:confirmar-${ganador.id}`, phase: 'Corrección', schema: { type: 'object', properties: { mejor: { type: 'boolean' }, razon: { type: 'string' } }, required: ['mejor', 'razon'] } })
    if (veredicto && veredicto.mejor) {
      const nuevo = { ...ganador, ...v2, id: `${ganador.id}2`, angulo: `${ganador.angulo} (corregida)`, total: ganador.total, puntajes: ganador.puntajes, problemas: [] }
      candidatos.push(nuevo)
      validos.unshift(nuevo)
      correccion = `se corrigió ${ganador.id} → ${nuevo.id}: ${veredicto.razon}`
      ganador = nuevo
    } else {
      correccion = `se intentó corregir ${ganador.id} pero la versión nueva no fue mejor: ${veredicto ? veredicto.razon : 'sin veredicto'}`
    }
  } else {
    correccion = `se intentó corregir ${ganador.id} pero la versión nueva no pasó la validación`
  }
}
log(`Tapa: ${correccion}`)

return {
  candidatos: candidatos.map((c) => ({ ...c, validacion: { ok: !!c.validacion_ok } })),
  ganador: ganador.id,
  jueces: jueces.map((j) => ({ lente: j.lente, preferido: j.preferido, razon: j.razon })),
  correccion,
  guardas,
}
