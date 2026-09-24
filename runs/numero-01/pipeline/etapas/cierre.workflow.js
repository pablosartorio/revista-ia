export const meta = {
  name: 'condor-cierre',
  description: 'Cóndor: editor/a de cierre — aplica los fallos de la reconciliación con guardas determinísticas',
  whenToUse: 'Etapa hija del pipeline de Cóndor; args: {bloques, afirmaciones, resoluciones, conflictos, contexto_omitido}',
  phases: [{ title: 'Cierre', detail: 'un editor por bloque afectado, con una ronda de auto-reparación si fallan las guardas' }],
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
  return (s || '').normalize('NFKD').replace(/[\u0300-\u036f]/g, '').replace(/[“”«»"„]/g, '"')
    .replace(/[‘’´`]/g, "'").replace(/[—–]/g, '-').replace(/\s+/g, ' ').trim().toLowerCase()
}
function tokens(s) { return new Set(norm(s).split(/[^a-z0-9]+/).filter((t) => t.length >= 4)) }
function textoBloque(b) { return [b.titulo, b.bajada, b.cuerpo].filter(Boolean).join(' ') }
function escRe(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') }
function palabra(textoN, v) { return new RegExp(`(^|[^a-z0-9])${escRe(v)}($|[^a-z0-9])`).test(textoN) }
function uniq(xs) { return [...new Set(xs)] }

const porId = {}
for (const a of args.afirmaciones) porId[a.id] = a
const resoluciones = args.resoluciones.map((r) => ({ ...r, bloques_pendientes: [] }))
const guardas = []

// ------------------------------------------------------------ acciones por bloque
const acciones = {}
const sinAncla = []
function sumar(clave, acc) { (acciones[clave] = acciones[clave] || []).push(acc) }
for (const r of resoluciones) {
  if (!['corregir', 'retirar', 'matizar'].includes(r.decision)) continue
  const propias = r.afirmaciones_afectadas.map((id) => porId[id]).filter(Boolean)
  const bloquesDeAf = uniq(propias.map((a) => a.bloque))
  // cifras que el fallo manda sacar o cambiar: las del conflicto (p. ej. una huérfana) y las de las afirmaciones afectadas
  const cifrasFallo = uniq([...(r.cifras || []), ...propias.flatMap((a) => [...cifrasAf(a)])])
  for (const clave of uniq([...bloquesDeAf, ...r.bloques])) {
    const b = args.bloques.find((x) => x.clave === clave)
    if (!b) continue
    const afs = propias.filter((a) => a.bloque === clave)
    const sigBloque = sig(textoBloque(b))
    const cifras = cifrasFallo.filter((c) => sigBloque.has(c))
    if (r.decision === 'retirar' && !afs.length && !cifras.length) {
      // sin afirmación ni cifra en este bloque el código no puede comprobar el retiro
      if (!propias.length && !(r.cifras || []).length) sinAncla.push({ r, clave })
      continue  // si el dato tiene ancla en otro bloque, acá no aparece: no hay nada que retirar
    }
    sumar(clave, {
      tipo: r.decision, ref: r.conflicto_id, afirmaciones: afs, cifras,
      valor_correcto: r.valor_correcto, redaccion_sugerida: r.redaccion_sugerida, razonamiento: r.razonamiento,
    })
  }
}
for (const c of args.contexto_omitido || []) {
  sumar(c.bloque, { tipo: 'matizar', ref: 'contexto', afirmaciones: [], valor_correcto: '', redaccion_sugerida: c.descripcion, razonamiento: `contexto que encontró el verificador (${c.url})` })
}

const afectados = args.bloques.filter((b) => acciones[b.clave])
log(`Cierre: ${afectados.length} bloque(s) con correcciones a aplicar.`)

const CIERRE_SCHEMA = {
  type: 'object',
  properties: {
    titulo: { type: 'string' },
    bajada: { type: 'string' },
    cuerpo: { type: 'string' },
    cambios: {
      type: 'array',
      items: {
        type: 'object',
        properties: { antes: { type: 'string' }, despues: { type: 'string' }, motivo: { type: 'string' }, ref: { type: 'string' } },
        required: ['antes', 'despues', 'motivo', 'ref'],
      },
    },
  },
  required: ['titulo', 'bajada', 'cuerpo', 'cambios'],
}

function describir(acc) {
  const afs = acc.afirmaciones.map((a) => `"${a.texto}" (texto actual: "${a.cita_textual}")`).join('; ') ||
    ((acc.cifras || []).length ? `el dato con la cifra ${acc.cifras.join(', ')}` : '')
  switch (acc.tipo) {
    case 'retirar': return `[${acc.ref}] RETIRAR ${afs || acc.razonamiento}. Sacá ese dato del texto (título incluido) sin dejar rastro del valor; reescribí lo mínimo para que el párrafo siga leyéndose bien. Motivo: ${acc.razonamiento}`
    case 'corregir': return `[${acc.ref}] CORREGIR ${afs || ''} → el valor correcto es: ${acc.valor_correcto}. Redacción sugerida: "${acc.redaccion_sugerida}". Reemplazá el valor viejo en todos lados donde aparezca (título incluido) y ajustá lo que dependa de él (p. ej. una duración calculada con la fecha vieja). Motivo: ${acc.razonamiento}`
    case 'matizar': return `[${acc.ref}] MATIZAR ${afs || ''}: agregá el contexto/atribución: "${acc.redaccion_sugerida}". Motivo: ${acc.razonamiento}`
  }
  return ''
}

function cierrePrompt(b, accs, errores) {
  return `Sos editor/a de cierre de una revista técnica. Aplicás correcciones ya decididas por un juez de verificación. NO investigás, NO agregás datos nuevos, NO mejorás el estilo: cambiás lo mínimo necesario para aplicar cada corrección.

Bloque "${b.clave}":
TITULO: ${b.titulo}
BAJADA: ${b.bajada || ''}
CUERPO:
${b.cuerpo}

CORRECCIONES A APLICAR:
${accs.map(describir).join('\n')}
${errores ? `\nTU INTENTO ANTERIOR NO PASÓ LAS GUARDAS AUTOMÁTICAS. Arreglá esto:\n- ${errores.join('\n- ')}\n` : ''}
Reglas: toda cifra del texto final tiene que estar en el texto original o en las correcciones de arriba (no inventes ni redondees números). Conservá párrafos (separados por línea en blanco). Si la bajada está vacía, devolvela vacía. En "cambios" listá cada modificación con un fragmento corto antes/después y la ref de la corrección.`
}

// cifras que trae la corrección (sin los ids del libro que los jueces citan en la prosa)
function deLaCorreccion(acc) { return sig(sinIds(`${acc.valor_correcto} ${acc.redaccion_sugerida}`)) }

function guardar(b, accs, res) {
  const errores = []
  const original = textoBloque(b)
  const originalN = norm(original)
  const nuevo = textoBloque(res)
  const nuevoN = norm(nuevo)
  const nuevoSig = sig(nuevo)
  if (!res.cuerpo || res.cuerpo.length < 0.4 * b.cuerpo.length) errores.push('el cuerpo quedó vacío o demasiado recortado')
  const idsAccion = new Set(accs.flatMap((a) => a.afirmaciones.map((x) => x.id)))
  const retenidas = args.afirmaciones.filter((a) => a.bloque === b.clave && !idsAccion.has(a.id))
  const cifrasRetenidas = new Set(retenidas.flatMap((a) => [...cifrasAf(a)]))
  const permitidas = new Set([...sig(original), ...accs.flatMap((a) => [...deLaCorreccion(a)])])

  for (const acc of accs) {
    const correccion = deLaCorreccion(acc)
    const textoCorreccionN = norm(sinIds(`${acc.valor_correcto} ${acc.redaccion_sugerida}`))
    for (const a of acc.afirmaciones) {
      const propias = [...cifrasAf(a)].filter((c) => !cifrasRetenidas.has(c) && !correccion.has(c))
      if (acc.tipo === 'retirar') {
        if (nuevoN.includes(norm(a.cita_textual))) errores.push(`la afirmación a retirar sigue textual: "${a.cita_textual}"`)
        const quedan = propias.filter((c) => nuevoSig.has(c))
        if (quedan.length) errores.push(`quedan cifras de la afirmación retirada ${a.id}: ${quedan.join(', ')}`)
      }
      if (acc.tipo === 'corregir') {
        const quedan = propias.filter((c) => nuevoSig.has(c))
        if (quedan.length) errores.push(`sigue el valor viejo de ${a.id}: ${quedan.join(', ')}`)
        if (!sig(a.valor).size) {
          // valor no numérico (un nombre, "2 de julio"): tiene que desaparecer, o al menos cambiar el fragmento
          const v = norm(a.valor)
          if (v.length >= 3 && palabra(originalN, v) && !palabra(textoCorreccionN, v)) {
            if (palabra(nuevoN, v)) errores.push(`sigue el valor viejo de ${a.id}: "${a.valor}"`)
          } else if (originalN.includes(norm(a.cita_textual)) && nuevoN.includes(norm(a.cita_textual))) {
            errores.push(`${a.id}: el fragmento a corregir quedó igual: "${a.cita_textual}"`)
          }
        }
      }
    }
    if (acc.tipo === 'retirar' || acc.tipo === 'corregir') {
      const quedan = (acc.cifras || []).filter((c) => nuevoSig.has(c) && !cifrasRetenidas.has(c) && !correccion.has(c))
      if (quedan.length) errores.push(`${acc.ref}: siguen en el texto cifras que el fallo manda ${acc.tipo === 'retirar' ? 'retirar' : 'corregir'}: ${quedan.join(', ')}`)
    }
    if (acc.tipo === 'corregir' && acc.valor_correcto) {
      // los jueces suelen escribir prosa en valor_correcto (con la cifra vieja adentro): se exigen sólo
      // las cifras que también están en la redacción sugerida y que no son valores viejos
      const vc = sig(sinIds(acc.valor_correcto))
      const rs = sig(sinIds(acc.redaccion_sugerida))
      const viejas = new Set(acc.afirmaciones.flatMap((a) => [...cifrasAf(a)]))
      if (vc.size) {
        const faltan = [...vc].filter((c) => (!rs.size || rs.has(c)) && !viejas.has(c) && !nuevoSig.has(c))
        if (faltan.length) errores.push(`no aparece el valor correcto (${acc.ref}): ${faltan.join(', ')}`)
      } else {
        const nuevosTok = [...tokens(sinIds(acc.valor_correcto))].filter((t) => !tokens(original).has(t))
        if (nuevosTok.length && !nuevosTok.some((t) => nuevoN.includes(t))) errores.push(`no aparece el valor correcto (${acc.ref}): "${acc.valor_correcto}"`)
      }
    }
    if (acc.tipo === 'matizar') {
      if (nuevoN === originalN) errores.push(`${acc.ref}: matizar exige agregar el contexto, pero el texto quedó igual`)
      const nuevosTok = [...tokens(sinIds(acc.redaccion_sugerida))].filter((t) => !tokens(original).has(t))
      if (nuevosTok.length && !nuevosTok.some((t) => tokens(nuevo).has(t))) errores.push(`${acc.ref}: no aparece nada del contexto a agregar ("${acc.redaccion_sugerida.slice(0, 120)}")`)
      if (!accs.some((x) => x.tipo === 'retirar') && nuevo.length <= original.length - 20) errores.push(`${acc.ref}: matizar agrega contexto, pero el texto se achicó`)
    }
  }
  const inventadas = [...nuevoSig].filter((c) => !permitidas.has(c))
  if (inventadas.length) errores.push(`aparecen cifras que no están ni en el original ni en las correcciones: ${inventadas.join(', ')}`)
  return errores
}

const aplicados = await pipeline(
  afectados,
  (b) => agent(cierrePrompt(b, acciones[b.clave]), { label: `cierre:${b.clave}`, phase: 'Cierre', schema: CIERRE_SCHEMA }),
  async (res, b) => {
    const accs = acciones[b.clave]
    let errores = res ? guardar(b, accs, res) : ['el editor de cierre no respondió']
    if (errores.length) {
      log(`cierre:${b.clave} no pasó las guardas (${errores.length}); ronda de auto-reparación`)
      const res2 = await agent(cierrePrompt(b, accs, errores), { label: `cierre+:${b.clave}`, phase: 'Cierre', schema: CIERRE_SCHEMA })
      const errores2 = res2 ? guardar(b, accs, res2) : ['el editor de cierre no respondió']
      if (!errores2.length) return { clave: b.clave, res: res2, ok: true, intentos: 2 }
      return { clave: b.clave, res: null, ok: false, errores: errores2 }
    }
    return { clave: b.clave, res, ok: true, intentos: 1 }
  },
)

const bloquesFinales = args.bloques.map((b) => ({ ...b }))
const correcciones = []
const fallidos = new Set()
for (const x of aplicados.filter(Boolean)) {
  const b = bloquesFinales.find((y) => y.clave === x.clave)
  if (!x.ok) {
    fallidos.add(x.clave)
    guardas.push({ etapa: 'cierre', bloque: x.clave, tipo: 'correccion_no_aplicada', severidad: 'bloqueante', detalle: `se conserva el texto original; errores: ${x.errores.join(' | ')}` })
    continue
  }
  b.titulo = x.res.titulo
  b.cuerpo = x.res.cuerpo
  if (b.tipo === 'feature' || x.res.bajada) b.bajada = x.res.bajada
  for (const c of x.res.cambios || []) correcciones.push({ ...c, bloque: x.clave })
  if (x.intentos > 1) guardas.push({ etapa: 'cierre', bloque: x.clave, tipo: 'auto_reparacion', severidad: 'aviso', detalle: 'la primera versión no pasó las guardas; la segunda sí' })
}
for (const b of afectados) {
  if (!aplicados.some((x) => x && x.clave === b.clave)) {
    fallidos.add(b.clave)
    guardas.push({ etapa: 'cierre', bloque: b.clave, tipo: 'etapa_caida', severidad: 'bloqueante', detalle: 'el cierre de este bloque no devolvió resultado' })
  }
}
for (const { r, clave } of sinAncla) {
  if (!r.bloques_pendientes.includes(clave)) r.bloques_pendientes.push(clave)
  guardas.push({ etapa: 'cierre', bloque: clave, tipo: 'fallo_sin_ancla', severidad: 'bloqueante', detalle: `${r.conflicto_id}: el juez decidió retirar, pero no hay afirmación ni cifra con la que comprobar el retiro; queda para la revisión humana` })
}

// ------------------------------------------------------------ estado final de cada afirmación
const ESTADO = { retirar: 'retirado', corregir: 'corregido', matizar: 'matizado' }
const afirmaciones = args.afirmaciones.map((a) => ({ ...a, estado_final: a.veredicto.estado }))
const porIdFinal = {}
for (const a of afirmaciones) porIdFinal[a.id] = a
for (const r of resoluciones) {
  for (const id of r.afirmaciones_afectadas) {
    const a = porIdFinal[id]
    if (!a) continue
    a.resolucion = { conflicto_id: r.conflicto_id, decision: r.decision }
    if (r.decision === 'mantener') {
      if ((r.evidencia || []).some((e) => e.url)) a.estado_final = 'confirmado'
    } else if (r.decision === 'sin_consenso') {
      a.estado_final = 'sin_consenso'
    } else if (fallidos.has(a.bloque)) {
      // la corrección no se aplicó: el dato sigue publicado tal como estaba, no puede contar como verificado
      a.estado_final = 'no_aplicado'
      if (!r.bloques_pendientes.includes(a.bloque)) r.bloques_pendientes.push(a.bloque)
    } else {
      a.estado_final = ESTADO[r.decision]
      if (r.decision === 'corregir' && r.valor_correcto) a.valor_final = r.valor_correcto
    }
  }
  for (const clave of r.bloques) if (fallidos.has(clave) && ['corregir', 'retirar', 'matizar'].includes(r.decision) && !r.bloques_pendientes.includes(clave)) r.bloques_pendientes.push(clave)
  r.aplicada = r.bloques_pendientes.length === 0
}

return { bloques: bloquesFinales, afirmaciones, resoluciones, correcciones, guardas }
