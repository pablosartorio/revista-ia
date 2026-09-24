export const meta = {
  name: 'condor-verificar',
  description: 'Cóndor: libro de afirmaciones — extrae afirmaciones atómicas por bloque y las verifica una por una',
  whenToUse: 'Etapa hija del pipeline de Cóndor; args: {bloques, modelo_verificador}',
  phases: [
    { title: 'Extracción', detail: 'afirmaciones atómicas con dato duro, más ronda de completitud' },
    { title: 'Verificación', detail: 'un verificador por bloque, modelo distinto al redactor' },
  ],
}

// ---- utilidades compartidas (mismas reglas que condor/numeros.py) ----
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
function significativa(c) { if (c.includes('.')) return true; const n = parseInt(c, 10); return !(n >= 1900 && n <= 2100) && n >= 10 }
function sig(s) { return new Set(nums(s).filter(significativa)) }
function norm(s) {
  return (s || '').normalize('NFKD').replace(/[\u0300-\u036f]/g, '').replace(/[“”«»"„]/g, '"')
    .replace(/[‘’´`]/g, "'").replace(/[—–]/g, '-').replace(/\s+/g, ' ').trim().toLowerCase()
}
function textoBloque(b) { return [b.titulo, b.bajada, b.cuerpo].filter(Boolean).join(' ') }

const CLAIMS_SCHEMA = {
  type: 'object',
  properties: {
    afirmaciones: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          texto: { type: 'string', description: 'la afirmación, autocontenida (se entiende sin leer el resto del bloque)' },
          tipo: { type: 'string', enum: ['cifra', 'fecha', 'nombre', 'evento', 'atribucion'] },
          entidad: { type: 'string', description: 'de quién o de qué habla (empresa, modelo, organismo, persona)' },
          valor: { type: 'string', description: 'el dato duro tal cual (ej. "850 MW", "2 de julio de 2026", "Nightingale Collective")' },
          cita_textual: { type: 'string', description: 'el fragmento EXACTO del bloque donde aparece, copiado carácter por carácter' },
          central: { type: 'boolean', description: 'true si la nota se cae sin esta afirmación' },
        },
        required: ['texto', 'tipo', 'entidad', 'valor', 'cita_textual', 'central'],
      },
    },
  },
  required: ['afirmaciones'],
}

const VERDICTS_SCHEMA = {
  type: 'object',
  properties: {
    veredictos: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          id: { type: 'string' },
          estado: { type: 'string', enum: ['confirmado', 'no_verificable', 'contradicho'] },
          valor_encontrado: { type: 'string', description: 'el valor que dice la evidencia (vacío si no hay)' },
          evidencia: {
            type: 'array',
            items: {
              type: 'object',
              properties: { url: { type: 'string' }, cita: { type: 'string', description: 'fragmento literal de la fuente' } },
              required: ['url', 'cita'],
            },
          },
          nota: { type: 'string' },
        },
        required: ['id', 'estado', 'valor_encontrado', 'evidencia', 'nota'],
      },
    },
    contexto_omitido: {
      type: 'array',
      description: 'información importante que encontraste y el bloque no menciona (p. ej. una desmentida de la parte involucrada)',
      items: {
        type: 'object',
        properties: { descripcion: { type: 'string' }, url: { type: 'string' } },
        required: ['descripcion', 'url'],
      },
    },
  },
  required: ['veredictos', 'contexto_omitido'],
}

function extractPrompt(b, tope = true) {
  return `Sos extractor/a de afirmaciones del libro de verificación de una revista técnica. No verificás nada: sólo descomponés.

Bloque "${b.clave}" (${b.seccion}):
TITULO: ${b.titulo}
${b.bajada ? 'BAJADA: ' + b.bajada + '\n' : ''}CUERPO:
${b.cuerpo}

Descomponé el bloque en afirmaciones ATÓMICAS verificables con dato duro: cifras, fechas, duraciones, nombres propios de organizaciones o personas, atribuciones ("X dijo/reveló Y"), eventos concretos. Reglas:
- Una afirmación por dato. "Oracle sumó 850 MW y 300.000 GPUs" son DOS afirmaciones.
- Incluí también los datos del TÍTULO y la BAJADA.
- cita_textual debe ser un fragmento copiado EXACTAMENTE del texto de arriba (lo vamos a buscar literal).
- Las duraciones y fechas derivadas ("durante seis semanas", "42 días") son afirmaciones propias.
- No incluyas opiniones ni análisis sin dato.${tope ? '\n- Entre 3 y 12 afirmaciones, priorizando las centrales.' : ''}`
}

function extraPrompt(b, faltantes) {
  return `${extractPrompt(b, false)}

Ya se extrajeron otras afirmaciones de este bloque. Ahora extraé SOLO las afirmaciones que contienen estas cifras, que quedaron sin cubrir: ${faltantes.join(', ')}. Una afirmación por cada cifra listada, sin tope.`
}

function verifyPrompt(b, claims) {
  const tabla = claims.map((c) => `- ${c.id}${c.central ? ' [CENTRAL]' : ''}: ${c.texto} (cita: "${c.cita_textual}")`).join('\n')
  const esMcp = (b.fuente_url || '').startsWith('mcp://')
  return `Sos verificador/a independiente de una revista técnica. Otro agente (de otro modelo) redactó el bloque; tu trabajo es verificar cada afirmación de cero, sin confiar en el texto del bloque como evidencia.

Bloque "${b.clave}" — fuente citada por el autor: ${b.fuente_nombre} ${b.fuente_url}
${b.fuentes && b.fuentes.length ? 'Otras fuentes citadas: ' + b.fuentes.map((f) => f.url).join(' ') + '\n' : ''}
AFIRMACIONES:
${tabla}

Procedimiento, en este orden:
${esMcp
    ? `1. La fuente es el servidor MCP "patagonia-espacial". Usá ToolSearch para cargar sus herramientas (listar_satelites, donde_esta, proximos_pasos) y volvé a consultarlo para comparar cada dato (satélite, horarios en hora argentina, elevación, visibilidad). No uses búsqueda web.`
    : `1. Leé la fuente citada con WebFetch (y las otras fuentes citadas, si hay). Para cada afirmación, fijate si la fuente la dice, con qué valor exacto.
2. Para las afirmaciones que la fuente citada NO confirma, y para las marcadas CENTRAL aunque la fuente las confirme, buscá confirmación independiente: COMO MÁXIMO 3 búsquedas web en total para todo el bloque (el cupo de búsquedas de la redacción es limitado). Priorizá las centrales.`}
3. Asigná estado a cada id:
   - "confirmado": una fuente que LEÍSTE en esta sesión dice lo mismo. Obligatorio: evidencia con url y cita literal de esa fuente.
   - "contradicho": encontraste evidencia de que el dato es otro. Poné el valor correcto en valor_encontrado, con evidencia.
   - "no_verificable": no lo encontraste en ninguna fuente leída. ES EL DEFAULT ANTE LA DUDA. No confirmes "porque suena razonable" ni "porque es consistente".
   Atención a detalles finos: un dígito, una fecha de cierre, un rango, quién hizo el hallazgo.
4. contexto_omitido: si al leer encontraste algo importante que el bloque no dice y cambia cómo se lee la nota (una desmentida o negación de la parte involucrada, una rectificación de la propia fuente, una cifra que el medio corrigió), anotalo con su url. Si no hay, lista vacía.
Devolvé un veredicto por CADA id de la lista, con el id exacto.`
}

function normalizarAfirmaciones(b, ext, desde, guardas) {
  const textoN = norm(textoBloque(b))
  const salida = []
  for (const [i, a] of ((ext && ext.afirmaciones) || []).entries()) {
    const id = `${b.clave}#${desde + salida.length + 1}`
    let citaOk = textoN.includes(norm(a.cita_textual))
    if (!citaOk) {
      // tolerancia: todas las cifras de la cita aparecen en el bloque
      const cs = nums(a.cita_textual)
      const bs = new Set(nums(textoBloque(b)))
      citaOk = cs.length > 0 && cs.every((c) => bs.has(c))
      guardas.push({
        etapa: 'extraccion', bloque: b.clave, tipo: 'cita_no_literal', severidad: 'aviso',
        // una afirmación descartada no recibe id del libro: ese id pasa a la siguiente
        detalle: `${citaOk ? id : `${b.clave} (respuesta ${desde ? 'de completitud' : 'del extractor'}, ítem ${i + 1})`}: la cita no aparece literal en el bloque${citaOk ? ' (sus cifras sí)' : ' y sus cifras tampoco — se descarta'}: "${a.cita_textual}"`,
      })
    }
    if (!citaOk) continue
    salida.push({ ...a, id, bloque: b.clave })
  }
  return salida
}

function cifrasSinCubrir(b, claims) {
  const cubiertas = new Set(claims.flatMap((c) => nums(c.cita_textual + ' ' + c.valor)))
  return [...sig(textoBloque(b))].filter((c) => !cubiertas.has(c))
}

function fusionar(b, claims, v, guardas) {
  const porId = {}
  for (const x of (v && v.veredictos) || []) porId[x.id] = x
  const ids = new Set(claims.map((c) => c.id))
  for (const id of Object.keys(porId)) {
    if (!ids.has(id)) guardas.push({ etapa: 'verificacion', bloque: b.clave, tipo: 'id_desconocido', severidad: 'aviso', detalle: `el verificador devolvió un id que no existe: ${id}` })
  }
  const afirmaciones = claims.map((c) => {
    let ver = porId[c.id]
    if (!ver) {
      ver = { id: c.id, estado: 'no_verificable', valor_encontrado: '', evidencia: [], nota: 'el verificador no devolvió veredicto para esta afirmación' }
      guardas.push({ etapa: 'verificacion', bloque: b.clave, tipo: 'sin_veredicto', severidad: 'aviso', detalle: c.id })
    }
    const conUrl = (ver.evidencia || []).filter((e) => e.url && (e.url.startsWith('http') || e.url.startsWith('mcp://')))
    if (ver.estado === 'confirmado' && conUrl.length === 0) {
      guardas.push({ etapa: 'verificacion', bloque: b.clave, tipo: 'confirmado_sin_evidencia', severidad: 'aviso', detalle: `${c.id} venía "confirmado" sin url de evidencia: se baja a no_verificable` })
      ver = { ...ver, estado: 'no_verificable', nota: `[guarda] confirmado sin evidencia citada. ${ver.nota || ''}` }
    }
    return { ...c, veredicto: ver }
  })
  const contexto = ((v && v.contexto_omitido) || []).filter((x) => x.descripcion).map((x) => ({ ...x, bloque: b.clave }))
  return { afirmaciones, contexto }
}

const resultados = await pipeline(
  args.bloques,
  (b) => agent(extractPrompt(b), { label: `extraer:${b.clave}`, phase: 'Extracción', schema: CLAIMS_SCHEMA }),
  async (ext, b) => {
    const guardas = []
    if (!ext) {
      ext = await agent(extractPrompt(b), { label: `extraer:${b.clave}:reintento`, phase: 'Extracción', schema: CLAIMS_SCHEMA })
      guardas.push(ext
        ? { etapa: 'extraccion', bloque: b.clave, tipo: 'extraccion_reintentada', severidad: 'aviso', detalle: 'el extractor no respondió la primera vez; el reintento sí' }
        : { etapa: 'extraccion', bloque: b.clave, tipo: 'extraccion_caida', severidad: 'bloqueante', detalle: 'el extractor no respondió (dos intentos): el bloque sólo tiene las afirmaciones que haya aportado la ronda de completitud' })
    }
    let claims = normalizarAfirmaciones(b, ext, 0, guardas)
    const faltan = cifrasSinCubrir(b, claims)
    if (faltan.length) {
      log(`${b.clave}: ${faltan.length} cifra(s) sin afirmación — ronda de completitud (${faltan.join(', ')})`)
      const extra = await agent(extraPrompt(b, faltan), { label: `extraer+:${b.clave}`, phase: 'Extracción', schema: CLAIMS_SCHEMA })
      claims = claims.concat(normalizarAfirmaciones(b, extra, claims.length, guardas))
      const siguen = cifrasSinCubrir(b, claims)
      if (siguen.length) guardas.push({ etapa: 'extraccion', bloque: b.clave, tipo: 'cifras_sin_afirmacion', severidad: 'bloqueante', detalle: `cifras que nadie verificó (no se pudieron extraer como afirmación): ${siguen.join(', ')}` })
    }
    if (!claims.length) {
      guardas.push({ etapa: 'extraccion', bloque: b.clave, tipo: 'sin_afirmaciones', severidad: 'bloqueante', detalle: 'no se pudo extraer ninguna afirmación verificable' })
      return { bloque: b.clave, afirmaciones: [], contexto: [], guardas }
    }
    const v = await agent(verifyPrompt(b, claims), {
      label: `verificar:${b.clave}`, phase: 'Verificación', schema: VERDICTS_SCHEMA,
      model: args.modelo_verificador || undefined,
    })
    return { bloque: b.clave, ...fusionar(b, claims, v, guardas), guardas }
  },
)

const ok = resultados.filter(Boolean)
const caidos = args.bloques.filter((b) => !ok.some((r) => r.bloque === b.clave)).map((b) => b.clave)
const guardas = ok.flatMap((r) => r.guardas)
for (const c of caidos) guardas.push({ etapa: 'verificacion', bloque: c, tipo: 'etapa_caida', severidad: 'bloqueante', detalle: 'la extracción o verificación de este bloque no devolvió resultado' })

return {
  afirmaciones: ok.flatMap((r) => r.afirmaciones),
  contexto_omitido: ok.flatMap((r) => r.contexto),
  guardas,
}
