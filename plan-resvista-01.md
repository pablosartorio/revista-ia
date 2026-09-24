# Cóndor — plan para terminar el Nº 01 y arquitectura del sistema

> Escrito el 24/09/2026, a partir de lo que hay en el repo (`plan.md`, `roles/`, `pipeline/`, `condor/`),
> la regresión del Nº 00 (`data/regresion-00.json`) y el diario de la corrida cortada del Nº 01
> (`~/.claude/projects/-home-psartorio-revista-ia/ed6fdb27-…/subagents/workflows/wf_c573cb47-18c/journal.jsonl`).

## 1. Dónde estamos

| Qué | Estado |
|---|---|
| Arquitectura v2 (libro de afirmaciones, reconciliación con debate, cierre con guardas, tapas SVG, checkpoint firmado) | Hecha. 61 tests pasan |
| Regresión del Nº 00 | 3 OK / 3 FALLA. **Las 8 resoluciones quedaron sin aplicar** (`aplicada: false`) y 15 afirmaciones quedaron `no_aplicado`: la guarda de `cierre` es imposible de cumplir (ver 3.1.1) |
| Ground truth de la regresión | 2 casos mal: Oracle >300.000 GPUs **es correcto**, y las fechas de DSEwiki eran otras (ver 3.1.3) |
| Nº 01 | Corrida cortada por límite de sesión: 52 agentes lanzados, 28 respondieron, 23 cayeron. **Se salvaron** las 9 corresponsalías, la nota de fondo, 9 extracciones y 5 verificaciones. No hay `data/numero-01.json` ni `output/numero-01/` |
| Segunda revisión adversarial | Sólo corrió la dimensión "guardas" (6 hallazgos sin verificar). Faltan "checkpoint" y "workflows" |

Para publicar el Nº 01 hay que: arreglar el cierre, sumar la consolidación de fallos, validar con una
regresión barata, relanzar el número en una sesión nueva (reusando la investigación que ya se hizo) y
llegar al checkpoint humano.

---

## 2. Arquitectura del sistema

### 2.1 Principios de diseño
1. **Los agentes redactan y juzgan; el código decide qué pasa.** Todo lo que un agente devuelve pasa
   por guardas determinísticas (cifras, citas literales, ids, largos). Un resultado que no pasa se
   degrada a un estado de riesgo, nunca se publica a medias.
2. **Modelos distintos para escribir y para verificar** (`modelo_verificador`, hoy `sonnet`):
   verificadores, escépticos del debate y la redacción no comparten sesgos.
3. **Nada se cae en silencio.** Si falla un agente o una etapa entera, queda una **guarda** (`aviso` o
   `bloqueante`) atada al bloque. Las bloqueantes obligan a una decisión humana explícita.
4. **Checkpoint humano con firma.** Ningún agente aprueba, retira, elige tapa ni publica: los comandos
   piden TTY y la frase secreta de quien revisa, y las decisiones van firmadas con HMAC.
5. **Reproducibilidad.** Cada número corre desde una copia congelada del pipeline
   (`runs/numero-XX/pipeline/` + `SHA256SUMS`). Hay una regresión contra un número con errores conocidos.
6. **El armado es código, no un agente** (Jinja2 en `condor/render.py`): maquetar no es una decisión editorial.

### 2.2 Vista general (v2.1, con la etapa `consolidar` que falta)

```
                        roles/00-linea-editorial.md  (se inyecta como LINEA en los prompts)
                                          │
 condor.workflow.js (jefe de redacción: orquestador determinístico)
   │
   ├─ Investigación ── parallel(9 corresponsalías: 8 web + espacio vía MCP patagonia-espacial)
   │                                   │                 [o: args.semilla, investigación ya hecha]
   ├─ Nota de fondo ── feature ‖ verificar(secciones)
   │                        └──► verificar(feature)
   │                                   │
   │                 libro de afirmaciones (id bloque#n, veredicto + evidencia)
   │                                   │
   ├─ reconciliar ── detectores en código + lente "hechos" ‖ lente "cronología"
   │                   └─ por conflicto: defensor ‖ escéptico ──► juez  (tope 10)
   │                                   │
   ├─ consolidar (NUEVA) ── fallos que comparten afirmaciones ──► 1 juez de consolidación por componente
   │                                   │
   ├─ cierre ── editor por bloque + guardas + 1 ronda de auto-reparación
   │                                   │
   ├─ Estilo ── corrector (guarda: mismas cifras, nombres protegidos, largo ±25%)
   ├─ Arte ──── título, concepto, nota destacada, brief de tapa, dato ancla confirmado
   └─ tapa ──── 3 ilustradores ‖ ──► jurado editorial ‖ visual ──► corrección del ganador ──► confirmación
                                       │
                      resultado v2 (JSON)  ──  uv run condor importar
                                       │
                      data/numero-XX.json (borrador)
                                       │
  ════════ CHECKPOINT HUMANO: condor revision → aprobar/retirar por bloque → tapa → publicar ════════
                                       │
                      output/numero-XX/index.html (publicado, con registro firmado)
```

### 2.3 Workflows

| Archivo | Entrada (`args`) | Devuelve | Agentes |
|---|---|---|---|
| `pipeline/condor.workflow.js` | `numero, fecha_larga, semana_iso, ventana, raiz, modelo_verificador, ciudad_espacio, etapas` (+ `semilla`, nuevo) | resultado v2 completo | 9 + 1 + estilo 1 + arte 1, más las etapas hijas |
| `etapas/verificar.workflow.js` | `bloques, modelo_verificador` | `afirmaciones, contexto_omitido, guardas` | por bloque: extractor (+ reintento) + completitud si faltan cifras + verificador |
| `etapas/reconciliar.workflow.js` | `bloques, afirmaciones, modelo_verificador, max_debates` | `grupos, conflictos, resoluciones, debates, descartados, candidatos_deterministicos, guardas` | 2 lentes + 3 por conflicto debatido |
| `etapas/consolidar.workflow.js` (**nueva**) | `afirmaciones, conflictos, resoluciones, debates` | `resoluciones` consolidadas + `guardas` | 1 por componente con ≥2 fallos |
| `etapas/cierre.workflow.js` | `bloques, afirmaciones, resoluciones, conflictos, contexto_omitido` | `bloques, afirmaciones (estado_final), resoluciones (aplicada, bloques_pendientes), correcciones, guardas` | 1 por bloque afectado (+1 de reparación) |
| `etapas/tapa.workflow.js` | `numero, dir, raiz, brief, titulo_numero, fecha_larga, titulares, dato_ancla` | `candidatos, ganador, jueces, correccion, guardas` | 3 + 2 + 1 + 1 |
| `pipeline/regresion-00.workflow.js` | `raiz, modelo_verificador` | verificar → reconciliar → cierre sobre el fixture | ~50 |

`hijo()` envuelve cada etapa: si una falla devuelve un resultado neutro y deja guardas bloqueantes
en los bloques afectados, así la corrida sigue.

### 2.4 Inventario de agentes (número de 10 bloques)

| Rol | Etapa | Modelo | Herramientas | Schema | Cantidad |
|---|---|---|---|---|---|
| Corresponsal (8 beats) | Investigación | redacción | WebSearch (2-4), WebFetch | `SECTION_SCHEMA` | 8 |
| Corresponsal de Espacio | Investigación | redacción | MCP `patagonia-espacial` (sin web) | `SECTION_SCHEMA` | 1 |
| Editor de nota de fondo | Nota de fondo | redacción | opcional web | `FEATURE_SCHEMA` | 1 |
| Extractor de afirmaciones | verificar | redacción | ninguna | `CLAIMS_SCHEMA` | 10 (+ reintentos) |
| Extractor de completitud | verificar | redacción | ninguna | `CLAIMS_SCHEMA` | 0-10 |
| Verificador | verificar | **verificador** | WebFetch + ≤3 búsquedas / MCP | `VERDICTS_SCHEMA` | 10 |
| Reconciliador "hechos" y "cronología" | reconciliar | redacción | ninguna | `LENS_SCHEMA` | 2 |
| Defensor | reconciliar | redacción | WebFetch + ≤2 búsquedas | `ARG_SCHEMA` | ≤10 |
| Escéptico | reconciliar | **verificador** | WebFetch + ≤2 búsquedas | `ARG_SCHEMA` | ≤10 |
| Juez | reconciliar | redacción | ≤1 WebFetch | `RULING_SCHEMA` | ≤10 |
| Juez de consolidación (**nuevo**) | consolidar | redacción | ≤1 WebFetch | `RULING_SCHEMA` + `conflictos_cubiertos` | 0-3 |
| Editor de cierre (+ reparación) | cierre | redacción | ninguna | `CIERRE_SCHEMA` | ≤10 (+≤10) |
| Corrector de estilo | Estilo | redacción | ninguna | `ESTILO_SCHEMA` | 1 |
| Director/a de arte | Arte | redacción | ninguna | `ART_SCHEMA` | 1 |
| Ilustrador A/B/C (tipográfica, metáfora, data-driven) | tapa | redacción | Write, Bash (`condor tapa-validar`/`tapa-render`), Read de PNG | `COVER_SCHEMA` | 3 |
| Jurado editorial y visual | tapa | redacción | Read de PNG | `JUDGE_SCHEMA` | 2 |
| Corrección del ganador + confirmador | tapa | redacción | idem | `COVER_SCHEMA` / `{mejor, razon}` | 2 |

Total típico: **55-70 agentes**; peor caso ~105 (10 debates y todas las reparaciones). Con la semilla
de investigación (3.3) son 10 menos. Roles humanos, fuera del código: la línea editorial (`roles/00`) y
quien revisa en el checkpoint (`roles/10`).

### 2.5 Estados de una afirmación

```
veredicto del verificador:  confirmado | no_verificable | contradicho
        │  (un "confirmado" sin url de evidencia baja a no_verificable)
        ▼  fallo del juez (consolidado) + cierre
estado_final:  confirmado | corregido (valor_final) | matizado | retirado
               | no_verificable | contradicho | sin_consenso | no_aplicado     ← ESTADOS_RIESGO
```
`ESTADOS_RIESGO` tiene que ser el mismo en `condor.workflow.js`, `condor/estado.py` y
`scripts/evaluar_regresion.py` (hoy a este último le falta `no_aplicado`).

### 2.6 Guardas determinísticas

| Etapa | Guarda |
|---|---|
| verificar | la cita tiene que ser literal (o todas sus cifras estar en el bloque); completitud: toda cifra significativa tiene que tener una afirmación; confirmado sin url → no_verificable; ids desconocidos o sin veredicto |
| reconciliar | cifras huérfanas de la feature; mismo dato con veredictos distintos; conflicto sin ancla → bloqueante; sin lentes → la feature queda bloqueada; tope de debates registrado |
| cierre | lo retirado no puede seguir en el texto (ni literal ni sus cifras); el valor viejo corregido tiene que desaparecer y el nuevo aparecer; no puede haber cifras inventadas; matizar no achica el texto; si falla dos veces → texto original + `no_aplicado` + bloqueante |
| estilo | mismo multiconjunto de cifras, largo 75-125%, nombres protegidos; si falla se descarta la edición |
| arte / tapa | sólo afirmaciones confirmadas de bloques sin riesgo como dato ancla; titulares sólo de bloques sin riesgo; validador SVG (`condor/svg.py`); el puntaje lo suma el código |
| checkpoint (`estado.py`) | recalcula riesgos por bloque (cifras sin trazabilidad, retiradas que siguen en el texto, dependencias de bloques retirados), aprobación atada al hash del contenido, tapa atada al SHA del SVG, firmas HMAC |

### 2.7 Capa Python (`condor/`)
- `numeros.py`: normalización de cifras. **Tiene que dar el mismo resultado que `canonNum`/`sig`**, que
  están copiados en los 5 `.js` (los workflows no importan módulos). El docstring menciona un
  `_comun.js` que no existe.
- `estado.py`: ciclo `borrador → en_revision → aprobado → publicado`, riesgos, firmas, lock y publicación.
- `render.py` + `templates/`: `borrador.html`, `revision.html` y los `index.html`/`index.md` finales.
- `importar.py`: valida `version == 2`, normaliza el número y hace relativas las rutas de las tapas.
- `svg.py`: validación y rasterizado de tapas. `cli.py`: `uv run condor …`.

### 2.8 Límites operativos conocidos
- **Presupuesto de sesión:** una corrida completa consume buena parte del límite. Los workflows grandes
  van **en serie** y cada uno en una sesión fresca.
- **`resumeFromRunId` sólo funciona dentro de la misma sesión.** Entre sesiones se relanza desde cero, o
  con la semilla de 3.3.
- **Los workflows no leen disco:** todo lo que entra lo hace por `args` (por eso el fixture de la
  regresión va embebido en el script).
- El `.output` de un workflow es un envoltorio `{summary, logs, result}` y es enorme. Para inspeccionar
  se usa `journal.jsonl`.

---

## 3. Plan para terminar el Nº 01

### Fase 0 — Decisiones humanas (Pablo, antes de correr)
- **D1. Oracle >300.000 GPUs en el Nº 00 publicado:** ¿se restaura el dato que se retiró por error? Es
  una edición de un número publicado, así que pasa por el checkpoint (`retirar`/`aprobar` + `publicar`),
  no por Claude. Es independiente del Nº 01.
- **D2. Reusar la investigación de la corrida cortada** (recomendado; ahorra 10 agentes y mantiene la
  ventana 14-23/09) **o relanzar todo desde cero**.
- **D3. Nota de Espacio:** los pasos del SAOCOM 1B eran "esta semana" respecto del 23/09. Si el número
  sale después de esas fechas, conviene rehacer sólo esa corresponsalía (la semilla la excluye y el
  beat corre en vivo).
- **D4. Hallazgos de la segunda revisión:** ¿se arreglan antes del Nº 01 (recomendado para los que
  tocan guardas, 3.1.5) o después?

### Fase 1 — Arreglos de código (misma sesión, sin workflows grandes)

**3.1.1 Guarda de `cierre` imposible de cumplir** — `pipeline/etapas/cierre.workflow.js` (`guardar()`, ~l.140)
- Hoy exige *todas* las cifras de `valor_correcto`, que los jueces escriben en prosa (con la cifra vieja
  adentro). En la regresión, las 8 resoluciones fallaron.
- Cambio: `requeridas = sig(valor_correcto) ∩ sig(redaccion_sugerida) − cifras viejas de las
  afirmaciones afectadas`. Antes de extraer cifras, sacar los ids tipo `feature#17`
  (`/\b[a-z_]+#\d+\b/g`), también en `permitidas` y en `deLaCorreccion`.
- `RULING_SCHEMA` (`reconciliar.workflow.js`): `valor_correcto` pasa a pedir "el dato correcto, corto,
  sin prosa ni ids (p. ej. '2 de julio de 2026', '17.000 ediciones')". La explicación va en `razonamiento`.
- Espejo en el checkpoint: `riesgos_bloque()` en `condor/estado.py` (`fallo_cifra_sigue_en_texto` y
  `permitidas`) tiene que sacar los ids con la misma regla. Hay que sumar un test.

**3.1.2 Etapa `consolidar`** — nuevo `pipeline/etapas/consolidar.workflow.js`
- Toma los fallos `corregir/retirar/matizar` y arma componentes conexos (union-find) sobre
  `afirmaciones_afectadas`. En la regresión: C1-C3-C4 comparten `feature#13`/`feature#14`.
- Por cada componente con ≥2 fallos, un juez de consolidación recibe los fallos, las evidencias de los
  debates y las afirmaciones. Devuelve **una** resolución coherente con `conflictos_cubiertos: [C1, C3, C4]`.
  Si los fallos se contradicen y la evidencia no alcanza para elegir, devuelve `sin_consenso` (va al checkpoint).
- Guarda en código: la resolución consolidada tiene que cubrir la unión de las afirmaciones del
  componente, y un componente sin respuesta queda con los fallos originales + una guarda bloqueante
  `consolidacion_caida` en sus bloques.
- Integración:
  - `condor.workflow.js`: llamar `hijo('consolidacion', 'consolidar.workflow.js', …)` entre
    `reconciliar` y `cierre`.
  - `conFallo` (l.243) = ids de `conflicto_id` ∪ `conflictos_cubiertos`.
  - `cierre.workflow.js`: sin cambios de lógica (recibe las resoluciones ya consolidadas), pero hay que
    preservar `conflictos_cubiertos`.
  - `condor/estado.py` `riesgos_bloque()`: un conflicto cuenta como resuelto si está en `conflicto_id`
    **o** en algún `conflictos_cubiertos`.
  - `condor/render.py` (l.143) y `templates/revision.html.j2` (l.95): el mapa `resoluciones` indexa
    también por cada id cubierto, y la revisión muestra "consolidado en K1".
  - `regresion-00.workflow.js` (plantilla de `scripts/generar_regresion.py`): sumar la etapa.
  - Documentar en `roles/08-reconciliacion-y-cierre.md` y en `plan.md` (v2.1).
- Tests: un fixture con 2 fallos contradictorios sobre la misma afirmación → `riesgos_bloque` no marca
  `conflicto_sin_resolver` para el cubierto.

**3.1.3 Ground truth y evaluador** — `tests/fixtures/numero-00-gt.json`, `scripts/evaluar_regresion.py`
- `RIESGO` pasa a incluir `no_aplicado`.
- `oracle_300k_gpus`: esperado = mantener (confirmado; fuente CryptoBriefing 11/09/2026 "deployed
  more than 300,000 GPUs"). La lógica del caso pasa a ser como la de `oracle_850mw`.
- `dsewiki_fecha_fin`: corte abrupto el 22/6 (lo publicado era correcto en eso) y el inicio de DSEwiki
  es el 24/5, no el 11/5. Reescribir el caso para que falle si aparece "11 de mayo" como inicio de DSEwiki.
- `feature_duracion`: rehacer los textos malos con la cronología verdadera (24/5-22/6 ≈ 4 semanas):
  "42 días"/"seis semanas" siguen mal, "cuatro semanas" pasa a estar bien.
- Nuevo caso `dsewiki_ediciones`: ~17.000 en DSEwiki sobre ~18.000 en total.
- Actualizar `origen` del GT con la fecha de la corrección y las fuentes.

**3.1.4 `importar` del envoltorio** — `condor/importar.py`
- Si el JSON tiene `result` y no `version`, desenvolver `result`. Así se importa el `.output`
  directamente, sin leerlo a mano. Sumar un test.

**3.1.5 Hallazgos de la segunda revisión (verificar cada uno contra el código; arreglar los reales)**
1. `significativa()` trata "2.000"/"1.950" como años (el separador se pierde en `canonNum`). Arreglo:
   un token con agrupación de miles siempre es significativo. Hay que cambiarlo en los 5 `.js` y en
   `numeros.py`, con test.
2. Las guardas usan las cifras de la cita completa (`sig(a.cita_textual)`) en vez de las del valor:
   una cita con dos datos arrastra cifras ajenas. Usar `sig(a.valor)`, y la cita sólo si el valor no
   tiene cifras.
3. `corregir` de un nombre o un mes, y `matizar`, pasan sin tocar el texto. Arreglo: si el valor viejo
   no es numérico, exigir que desaparezca `norm(a.valor)`. Para matizar, exigir que el texto cambie y
   que aparezca algún token de `redaccion_sugerida`.
4. La completitud da por cubiertas cifras que sólo aparecen en citas ajenas → cubrir por `valor`.
5. Bajada de secciones en `estilo`: excluirla del cálculo de la guarda (las secciones no la publican).
6. `nombresProtegidos` toma valores viejos → usar `valor_final` si existe y excluir `corregido`/`retirado`.

**3.1.6 Paridad JS/Python**
- Nuevo test `tests/test_paridad_js.py`: extrae `canonNum`/`significativa` de cada `.js` y compara que
  sean idénticos entre sí. Si hay `node`, también corre una tabla de casos contra `numeros.py`.
- Corregir el docstring de `numeros.py` (no existe `_comun.js`).

### Fase 2 — Validación
1. `uv run pytest -q` → todo verde (61 + nuevos).
2. Chequeo de sintaxis de cada `.workflow.js` envolviéndolo en una `AsyncFunction` (sin `export const meta`).
3. **Regresión barata desde el cierre** (recomendado, ~12 agentes): script nuevo
   `scripts/generar_regresion.py --desde-cierre` que embebe `afirmaciones`/`conflictos`/`resoluciones`/`debates`
   de `data/regresion-00.json` y corre sólo `consolidar → cierre`. Criterio: ≥6 de 8 resoluciones
   `aplicada: true`, C3/C4 consolidados en una sola cronología, 0 cifras inventadas.
   `uv run python scripts/evaluar_regresion.py <resultado>` con el GT nuevo.
4. (Opcional, otra sesión) Regresión completa del Nº 00 (~50 agentes) para medir de punta a punta.

### Fase 3 — Preparar la corrida del Nº 01
1. **Rescatar la corrida cortada:** copiar el `journal.jsonl` de `wf_c573cb47-18c` a
   `runs/numero-01/corrida-interrumpida/journal.jsonl` (trazabilidad; el directorio de la sesión vieja
   puede limpiarse).
2. **Semilla:** nuevo `scripts/semilla_desde_journal.py <journal> <salida>` extrae los resultados de
   `seccion:*` y `feature:nota-de-fondo` a `runs/numero-01/semilla-investigacion.json`. Si se decide D3,
   excluir `espacio`.
3. `condor.workflow.js`: aceptar `args.semilla = {secciones: {clave: SECTION}, feature: FEATURE|null}`.
   Los beats que están en la semilla no lanzan agente (`log` lo dice) y la feature se reusa si viene. El
   resultado registra `meta.semilla = {origen, beats_reusados}` para que la revisión humana lo vea.
4. **Recongelar el pipeline:** como la corrida anterior no produjo resultado, se reemplaza
   `runs/numero-01/pipeline/` por la versión arreglada (incluye `consolidar.workflow.js`), se regenera
   `SHA256SUMS` y se deja `runs/numero-01/NOTA.md` con el motivo y el hash anterior.

### Fase 4 — Correr el Nº 01 (sesión nueva, sin otros workflows en paralelo)
```
Workflow scriptPath=/home/psartorio/revista-ia/runs/numero-01/pipeline/condor.workflow.js
args = {numero:"01", fecha_larga:"23 de septiembre de 2026", semana_iso:"2026-W39",
        ventana:"14 al 23 de septiembre de 2026", raiz:"/home/psartorio/revista-ia",
        modelo_verificador:"sonnet", ciudad_espacio:"Bariloche",
        etapas:"/home/psartorio/revista-ia/runs/numero-01/pipeline/etapas",
        semilla:<contenido de runs/numero-01/semilla-investigacion.json>}
```
- Seguimiento sólo por `journal.jsonl` (contar `started/result/failed` por label), nunca leyendo el `.output`.
- Si se corta otra vez: se puede retomar con `resumeFromRunId` **sólo en esa misma sesión**. Si la
  sesión muere, ampliar la semilla con lo nuevo que haya en el journal y relanzar.

### Fase 5 — Importar y armar la revisión (Claude)
```
uv run condor importar <ruta del .output>     # desenvuelve result (3.1.4) → data/numero-01.json
uv run condor revision 01                     # output/numero-01/revision.html + borrador.html
uv run condor estado 01
```
- Informe para Pablo: bloques con riesgos, guardas bloqueantes, conflictos y cómo se resolvieron,
  candidatos de tapa con puntajes. Todo sale de `condor estado`/`revision.html`; Claude no decide nada.

### Fase 6 — Checkpoint humano (Pablo; Claude no ejecuta estos comandos)
```
uv run condor aprobar 01 --todo --revisor "Pablo Sartorio"
uv run condor aprobar 01 --bloque <C> --nota "..." --revisor "Pablo Sartorio"
uv run condor retirar 01 --bloque <C> --motivo "..." --revisor "Pablo Sartorio"
uv run condor tapa 01 <A|B|C|X2> --revisor "Pablo Sartorio"
uv run condor publicar 01 --revisor "Pablo Sartorio"      # → output/numero-01/index.html
```

### Fase 7 — Cierre
- Actualizar `CLAUDE.md` ("Estado y próximos pasos"), `plan.md` (v2.1: consolidar, semilla) y
  `roles/08`. Retro breve en `runs/numero-01/NOTA.md`: agentes usados, guardas disparadas, qué
  corrigió la revisión humana (insumo para el GT de una regresión del Nº 01).
- Commit/push sólo cuando se pida.
- Después: correr las dimensiones "checkpoint" y "workflows" de la revisión adversarial (sesión propia).

## 4. Sesiones sugeridas

| Sesión | Contenido | Agentes aprox. |
|---|---|---|
| A | Fase 1 + Fase 2.1-2.3 + Fase 3 | ~12 (regresión desde cierre) |
| B | Fase 4 (Nº 01) + Fase 5 | 45-60 |
| — | Fase 6 (Pablo, en su terminal) | 0 |
| C (opcional) | regresión completa del Nº 00 / revisión adversarial restante | ~50 / ~15 |

## 5. Definición de terminado
- [ ] Tests verdes, incluidos los nuevos (cierre, consolidar, importar, paridad JS/Python, significativas).
- [ ] Regresión desde el cierre: ≥6/8 resoluciones aplicadas y ninguna contradicción entre fallos
      sobre las mismas afirmaciones.
- [ ] `runs/numero-01/pipeline` recongelado con `SHA256SUMS` válido y `NOTA.md`.
- [ ] `data/numero-01.json` importado; `revision.html` generado.
- [ ] Checkpoint humano completo y `output/numero-01/index.html` publicado con el registro firmado.

## 6. Riesgos
- **Presupuesto:** otra corrida cortada. Mitigación: semilla, sesión fresca, nada en paralelo; si hace
  falta, bajar `max_debates` (lo que exceda va al checkpoint como "sin resolver").
- **El juez de consolidación introduce errores nuevos.** Mitigación: pasa por las mismas guardas del
  cierre, y ante la duda devuelve `sin_consenso`.
- **Semilla desactualizada** (sobre todo Espacio) → D3.
- **Los arreglos de `significativa` cambian qué cifras se rastrean** → más afirmaciones y más costo de
  verificación. Aceptable, pero hay que mirarlo en la regresión.

## 7. Deuda técnica (fuera de este plan)
- Utilidades duplicadas en 5 `.js` (mitigado con el test de paridad).
- Corrida en tramos reanudables entre sesiones (`args.desde` con estado intermedio), más general que la semilla.
- Presupuesto de tokens por etapa automatizado (`plan.md` §5).
- Regresión del Nº 01 una vez que esté publicado (segundo ground truth).

