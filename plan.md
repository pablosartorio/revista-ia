# Plan — Arquitectura de agentes para "Cóndor"

> **Versión actual: v2.1 (24/09/2026).** Más abajo están la v2 (23/09/2026) y la v1 (Nº 00), tal
> como se diseñaron. La v2.1 sale de la regresión del Nº 00 y de la corrida del Nº 01, el primer
> número producido y publicado con la arquitectura completa. El plan de trabajo detallado de esta
> versión está en `plan-resvista-01.md`.

## v2.1: qué cambió y por qué

| Problema | Mejora v2.1 | Dónde |
|---|---|---|
| Dos jueces fallaban por separado sobre las mismas afirmaciones y se contradecían (regresión del Nº 00: C3 corregía la duración a "cuatro semanas" y C4 a "seis semanas") | **Etapa `consolidar`**: componentes de fallos que comparten afirmaciones → un juez de consolidación devuelve una sola resolución (`K1`…) con `conflictos_cubiertos`; guardas de cobertura y de cifras; si falla, quedan los originales y una guarda bloqueante | `pipeline/etapas/consolidar.workflow.js`, `roles/08` |
| La guarda de cierre exigía todas las cifras de `valor_correcto`, pero los jueces escriben prosa ahí (con la cifra vieja y ids como `feature#17`): **0 de 8 fallos aplicados** en la regresión | Se exigen sólo las cifras que están en `valor_correcto` **y** en `redaccion_sugerida` y no son valores viejos; los ids del libro no cuentan como cifras; el juez tiene que dar un `valor_correcto` corto | `cierre.workflow.js`, `reconciliar.workflow.js`, `condor/estado.py` |
| Segunda revisión adversarial (dimensión "guardas"): "2.000" se tomaba como año; las guardas usaban las cifras de la cita completa; corregir un nombre o un mes y matizar pasaban sin tocar el texto; la completitud daba por cubiertas cifras de citas ajenas; la bajada de secciones confundía la guarda de estilo; se protegían nombres ya corregidos | Agrupación de miles siempre significativa; cifras de una afirmación = las de su valor que están en su cita (`cifrasAf`); un valor viejo no numérico tiene que desaparecer y matizar tiene que agregar texto; completitud por valor; la guarda de estilo compara contra lo que se publica | los 4 `.workflow.js` con guardas, `condor/numeros.py` |
| Nº 01: un fallo se aplicaba a **todos** los bloques del conflicto aunque el juez nombrara afirmaciones de uno solo (C7 matizaba política, llegó a Espacio y el cierre de Espacio falló entero, arrastrando la corrección C2) | Cada fallo se aplica sólo en los bloques de sus afirmaciones o de sus cifras | `cierre.workflow.js` |
| Nº 01: la portada publicaba el `concepto_tapa`, una nota interna del director de arte para los ilustradores | El director de arte escribe un **copete** para lectores; la portada publica sólo ése y el concepto queda en la revisión | `condor.workflow.js`, `condor/templates/` |
| La primera corrida del Nº 01 se cortó por límite de sesión (28 de 52 agentes) y `resumeFromRunId` no sirve entre sesiones | **Semilla**: `args.semilla` reusa la investigación ya hecha (beats y nota de fondo) y lo registra en `meta.semilla`; `scripts/semilla_desde_journal.py` la saca del journal; `importar` acepta el `.output` del workflow tal cual | `condor.workflow.js`, `scripts/`, `condor/importar.py` |
| Las utilidades de cifras están copiadas en cada `.js` (los workflows no importan módulos) y nada controlaba que coincidieran | Test de paridad JS ↔ Python, y tests que corren las etapas con `node` y un `agent` simulado | `tests/test_paridad_js.py`, `tests/test_workflows_js.py`, `tests/js/` |

### Pipeline v2.1

```
 [args.semilla: beats y nota de fondo ya investigados → no se relanzan]
corresponsalías (9, paralelo) ──┬──► nota de fondo ──► verificar(feature)
                                └──► verificar(secciones)   [en paralelo con la nota de fondo]
                                              │
                          libro de afirmaciones (todas, con veredicto)
                                              │
                reconciliar: código + lente "hechos" + lente "cronología"
                                              │
                   conflictos ──► debate (defensor ‖ escéptico) ──► juez
                                              │
       consolidar: fallos que comparten afirmaciones ──► 1 juez por componente   (NUEVO)
                                              │
     cierre: aplica cada fallo en los bloques de sus afirmaciones, guardas, auto-reparación
                                              │
                        estilo (guarda: cifras y nombres intactos)
                                              │
        arte: título, copete para lectores, concepto (interno), brief de tapa, dato ancla
                                              │
          tapa: 3 ilustradores ‖ ──► jurado (editorial ‖ visual) ──► corrección
                                              │
                  data/numero-XX.json   (estado: borrador)
                                              │
      ═══════ CHECKPOINT HUMANO (decisiones firmadas con la frase de quien revisa; ningún agente la conoce) ═══════
            condor revision → aprobar / retirar por bloque → tapa → publicar
                                              │
                         output/numero-XX/index.html  (publicado)
```

Cada número corre desde una copia congelada del pipeline (`runs/numero-XX/pipeline/` + `SHA256SUMS`);
si hay que recongelarla, el motivo y el hash anterior van en `runs/numero-XX/NOTA.md`.

### Cómo se probó
1. **Tests** (`uv run pytest -q`, 93): además de los de v2, las guardas de cierre y la consolidación
   corridas con `node` y respuestas fijas (los tests nuevos de cierre fallan con el código de v2), la
   paridad de las utilidades de cifras entre los `.js` y `numeros.py`, la semilla y el orquestador con
   semilla.
2. **Ground truth del Nº 00 corregido** leyendo las fuentes: Oracle **sí** desplegó más de 300.000
   GPUs, y DSEwiki va del 24/5 al 22/6 (17.000 ediciones sobre ~18.000 en total). Pasó de 6 a 7 casos.
3. **Regresión barata desde el cierre** (`scripts/generar_regresion.py --desde-cierre`, 9 agentes):
   reusa el libro, los conflictos, los fallos y los debates de la regresión completa y corre sólo
   consolidar → cierre. Resultado: **7/7 casos OK** y 6/6 resoluciones aplicadas (antes 3 OK y 0/8).
4. **Nº 01 de punta a punta** (24/09/2026): 75 agentes, 0 errores, 148 afirmaciones (136
   confirmadas). En el checkpoint se corrigieron a mano, a pedido del revisor, las coordenadas de
   Espacio (el fallo que el bug de cierre no dejó aplicar) y una fecha relativa ("hoy jueves"), y se
   escribió el copete. Publicado el mismo día. Retro en `runs/numero-01/NOTA.md`.

### Pendiente
- Repensar el nombre de la revista; al cambiarlo, dejarlo en una sola constante.
- Restaurar el dato correcto de Oracle (más de 300.000 GPUs) en el Nº 00 publicado: decisión humana
  por el checkpoint.
- Que los beats en vivo no usen fechas relativas a la corrida ("hoy jueves") sino a la fecha del número.
- Dimensiones "checkpoint" y "workflows" de la revisión adversarial.
- Deuda técnica que sigue en pie: corridas reanudables entre sesiones más generales que la semilla,
  presupuesto de tokens por etapa, y una regresión con ground truth del Nº 01.

---

# v2 (23/09/2026)

> La v2 agrega las mejoras que salieron del cierre del Nº 00.

## v2: qué cambió y por qué

| Problema del Nº 00 | Mejora v2 | Dónde |
|---|---|---|
| El fact-check daba **un veredicto por bloque**: no decía qué dato estaba mal | **Libro de afirmaciones**: cada bloque se descompone en afirmaciones atómicas verificadas una por una, con un modelo distinto al redactor | `pipeline/etapas/verificar.workflow.js`, `roles/07` |
| La misma cifra quedó "confirmada" en una sección y "no verificable" en la nota de fondo; nadie comparaba bloques | **Reconciliación cruzada**: detectores en código + 2 reconciliadores con lentes distintas; cada conflicto se resuelve por **debate** (defensor, escéptico, juez) | `pipeline/etapas/reconciliar.workflow.js`, `roles/08` |
| Las correcciones se aplicaron a mano; el corrector de estilo de v1 ni siquiera llegaba al número final | **Editor de cierre con guardas + auto-reparación**; corrector de estilo por bloque con guarda de cifras y nombres | `pipeline/etapas/cierre.workflow.js`, `pipeline/condor.workflow.js` |
| "Publicado" era sólo un disclaimer en el pie | **Checkpoint humano real**: aprobación por bloque con hash, decisiones firmadas con la frase secreta de quien revisa (un agente no puede fabricar una decisión que se publique), riesgos aceptados con nota, tapa cruzada contra lo publicado, publicación bloqueada hasta completar | `condor/estado.py`, `roles/10` |
| La tapa era una directiva de texto | **Tapas SVG**: 3 ilustradores, jurado visual de 2 lentes, ronda de corrección del ganador, elección humana | `pipeline/etapas/tapa.workflow.js`, `roles/09` |

### Pipeline v2 (reemplazado por el de v2.1)

```
corresponsalías (9, paralelo) ──┬──► nota de fondo ──► verificar(feature)
                                └──► verificar(secciones)   [en paralelo con la nota de fondo]
                                              │
                          libro de afirmaciones (todas, con veredicto)
                                              │
                reconciliar: código + lente "hechos" + lente "cronología"
                                              │
                   conflictos ──► debate (defensor ‖ escéptico) ──► juez
                                              │
                       cierre: aplica fallos, guardas, auto-reparación
                                              │
                        estilo (guarda: cifras y nombres intactos)
                                              │
                 arte: título, concepto, brief de tapa, dato ancla confirmado
                                              │
          tapa: 3 ilustradores ‖ ──► jurado (editorial ‖ visual) ──► corrección
                                              │
                  data/numero-XX.json   (estado: borrador)
                                              │
      ═══════ CHECKPOINT HUMANO (decisiones firmadas con la frase de quien revisa; ningún agente la conoce) ═══════
            condor revision → aprobar / retirar por bloque → tapa → publicar
                                              │
                         output/numero-XX/index.html  (publicado)
```

### Cómo se probó
1. **Tests** (`uv run pytest`): normalización de cifras, validador de SVG, y el ciclo completo
   del checkpoint (sin TTY no se aprueba, hash vencido, riesgos que aparecen después de aprobar,
   dependencia de un bloque retirado, publicación bloqueada).
2. **Regresión sobre el Nº 00 original** (`pipeline/regresion-00.workflow.js`): los mismos textos
   con los errores que encontramos a mano, contra un ground truth de 6 casos
   (`tests/fixtures/numero-00-gt.json`, evaluado con `scripts/evaluar_regresion.py`).
3. **Revisión adversarial del código** (workflow de 4 revisores + 2 escépticos por hallazgo).
4. **Número 01 de punta a punta** con la arquitectura completa, hasta el checkpoint humano.

---

# v1 (Nº 00) — diseño original

Revista de IA, tecnología, investigación y ciencia asociada. Este documento define
explícitamente los agentes, sus prompts/responsabilidades, y las interacciones entre
ellos para el **Número 00 (piloto)**, un ensayo real de la arquitectura completa.

Nombre de trabajo: **Cóndor — Inteligencia en Foco** (propuesta; alternativas: *Nodo*,
*Umbral*). Elegido por la asociación con la mirada patagónica sobre la IA global —
se puede cambiar sin tocar la arquitectura.

---

## 0. Qué cambia respecto a `/ia-weekly-report`

La skill semanal ya resuelve bien "investigación en paralelo + compilación". Esta
arquitectura toma eso como piso y agrega las capas que faltaban:

1. **Línea editorial como documento separado**, no mezclada con la lógica de búsqueda.
2. **Feature / nota de fondo**: una pieza analítica larga que sintetiza varias noticias
   de la semana en un ángulo propio — periodismo de revista, no solo brief de noticias.
3. **Corresponsalía nueva de Ciencia y Espacio (Patagonia)**, alimentada por el MCP
   `patagonia-espacial` (datos en vivo de satélites) en vez de búsqueda web — primera
   sección "data-driven" de la revista.
4. **Corrector de estilo** como pasada separada sobre el borrador ya armado.
5. **Fact-checking adversarial real**: agentes independientes que intentan refutar cada
   afirmación con dato duro, no solo "no inventar si hay paywall".
6. **Dirección de arte** como agente propio: decide concepto de tapa, nota destacada y
   si el número rompe la plantilla estándar.
7. **Capa de "CMS" en Python** (no LLM): el armado final de `.md`/`.html` es código
   determinístico (Jinja2), no un agente — igual que en una redacción real, maquetar
   no es una decisión editorial.

## 1. Roles y agentes (ver `roles/` para el detalle de cada uno)

| # | Rol | Tipo | Corre como |
|---|---|---|---|
| — | Director/a editorial | línea fija, no ejecuta | archivo `roles/00-linea-editorial.md`, se inyecta como contexto en todos los prompts |
| — | Jefe/a de redacción | orquestador | el propio script de Workflow (lógica determinística de reparto y ensamblado) |
| 1-9 | Editores de sección / corresponsales (9 beats) | agente, `parallel()` | `agent()` con schema `SECCION` |
| 10 | Editor de nota de fondo (feature) | agente, después del barrier de investigación | `agent()` con schema `FEATURE`, recibe los 9 reportes como contexto |
| 11 | Corrector de estilo | agente, 1 pasada sobre el draft completo | `agent()` sin schema (devuelve texto) |
| 12-14 | Fact-checkers (3 grupos, adversariales) | agente, `parallel()` | `agent()` con schema `FACTCHECK`, cada uno intenta refutar ~3 bloques |
| 15 | Director/a de arte | agente, al final, con todo el material ya verificado | `agent()` con schema `ARTE` |
| — | Editor/a digital (CMS) | código Python, no agente | `scripts/build_issue.py` — Jinja2, arma `.md` y `.html` finales |

Total: **15 agentes** lanzados por el Workflow (9 + 1 + 1 + 3 + 1), dentro de la guía
de "workflow mediano" pero usando el pipeline completo.

## 2. Las 9 corresponsalías (beats)

1. Modelos fundacionales y LLMs
2. Hardware e infraestructura
3. Regulación y política de IA
4. Seguridad y alineación
5. IA aplicada — Ciencia y salud
6. IA aplicada — Industria y robótica
7. Argentina
8. América Latina
9. **Ciencia y Espacio — Patagonia** (nueva; usa el MCP `patagonia-espacial`: qué
   satélites pasan esta semana sobre Bariloche/la Patagonia, visibles u ocultos,
   como nota corta de "cielo de la semana" con datos reales, no búsqueda web)

Cada beat entrega **un solo ítem fuerte** (no 2-3 como en el semanal) — el piloto
prioriza probar la arquitectura completa, no volumen de noticias.

## 3. Interacciones (pipeline)

```
roles/00-linea-editorial.md  (fijo — se referencia en todos los prompts, no corre)
        │
   [Workflow script = jefe de redacción]
        │
        ├── FASE "Investigación" ── parallel(9 beats) ──► 9 reportes (schema SECCION)
        │                                                        │
        │                                    (barrier: la nota de fondo necesita
        │                                     ver los 9 reportes juntos)
        │                                                        ▼
        ├── FASE "Nota de fondo" ──────────────────────► 1 feature (schema FEATURE)
        │                                                        │
        │                              ensamblado determinístico (JS, sin agente):
        │                              draft = 9 reportes + feature en un solo texto
        │                                                        │
        ├── FASE "Edición" ── corrector de estilo (1 agente) ──► draft pulido
        │                              │
        │                  split en 3 grupos de contenido
        │                              │
        │              parallel(3 fact-checkers adversariales) ──► veredictos por afirmación
        │                                                        │
        ├── FASE "Diseño" ── director de arte (1 agente, ve draft pulido + veredictos)
        │                                                        │
        └── return { reportes, feature, draft_editado, factcheck, arte }
                                                                  │
                                            (fuera del workflow, en el hilo principal)
                                                                  ▼
                                    scripts/build_issue.py (Python + Jinja2)
                                                                  │
                                                    output/numero-00/index.md
                                                    output/numero-00/index.html
```

**Por qué el corte de fases es así:**
- La investigación es un `parallel()` puro: los 9 beats no dependen entre sí.
- La nota de fondo SÍ necesita el barrier — su ángulo depende de ver los 9 reportes
  juntos (ej: "esta semana la seguridad y la energía se cruzan").
- El fact-checking es adversarial y en paralelo, pero cada grupo verifica un
  subconjunto de afirmaciones vía búsqueda propia — no confía en las fuentes que
  citó el reportero original.
- La dirección de arte va al final porque necesita saber qué sobrevivió al
  fact-check (una nota contradicha no puede ser la de tapa).
- El armado final es código, no un agente: no hay ambigüedad editorial en poner
  un `<div>` en su lugar.

## 4. Esquemas de datos (resumen; ver script)

- `SECCION`: `{ seccion, color_acento, item: { titulo, cuerpo, open_weight?, fuente_nombre, fuente_url, fecha } }`
- `FEATURE`: `{ titulo, bajada, cuerpo, fuentes: [{nombre, url}] }`
- `FACTCHECK`: `{ veredictos: [{ afirmacion, seccion, estado: confirmado|no_verificable|contradicho, nota }] }`
- `ARTE`: `{ titulo_numero, concepto_tapa, nota_destacada, notas_diseno }`

## 4bis. Investigación previa: qué dice el estado del arte (sept. 2026) y cómo cambió el diseño

Antes de lanzar el ensayo, un agente de investigación externa buscó specificamente
qué se sabe hoy sobre orquestar pipelines editoriales multi-agente. Hallazgos que
modificaron este diseño:

- **El tamaño óptimo documentado es 3-5 agentes especializados**; pasados ~20 agentes
  el rendimiento cae de forma consistente, y el costo de tokens crece cuadrático si
  cada agente recibe el contexto acumulado completo (Arion Research / Codebridge,
  2026). Por eso cada corresponsalía recibe solo el fragmento de línea editorial que
  le compete, no el historial completo — y el total de 15 agentes se mantiene en
  "modo pipeline paralelo" (los 9 beats no se coordinan entre sí en una cadena de
  razonamiento, que es el escenario donde la degradación se documentó).
- **El patrón más citado para reducir alucinaciones en verificación de cifras es
  debate de 2 agentes con posturas opuestas + juez moderador**, no un solo
  verificador adversarial (paper "Debating Truth", ACM Web Conf. 2026). Este piloto
  usa una versión más liviana y barata (3 fact-checkers en paralelo, instruidos a
  *default a "no verificable"* antes que confirmar) — una concesión consciente de
  costo, documentada acá para no perderla de vista.
- **Dato incómodo y honesto**: un caso real documentado (dacharycarey.com, 20
  artículos publicados) encontró que el 100% de las notas necesitó correcciones
  post-publicación que la verificación automática no cazó — cifras desactualizadas,
  detalles fabricados sobre productos reales. Ningún medio grande (DMG Media, AP,
  India Today, NYT) publica sin un humano dando el visto bueno final. **Conclusión
  para este piloto: el fact-check reduce el riesgo, no lo elimina — el número 00
  sigue necesitando una revisión humana antes de considerarse "publicado" de
  verdad**, no solo "generado".
- **MCP en 2026** es ahora stateless (escala mejor) y tiene una extensión "Tasks"
  para trabajos largos vía polling, pero no hay soporte nativo para eventos/streaming
  en vivo todavía. Para esta arquitectura alcanza: la corresponsalía de Espacio
  consulta el MCP como una fuente de datos estructurados normal (no necesita push).
- Medios reales ya operan así en 2026 (DMG Media "Mail iQ", India Today "Pragya", AP
  "Rover", NYT "Echo") — todos con handoffs tipados entre roles y aprobación humana
  final, ninguno public a ciegas.

## 5. Qué NO está en este piloto (deuda técnica reconocida)

- No hay banco de imágenes/ilustrador real (el "director de arte" da directivas de
  texto, no genera imágenes).
- El fact-checker no tiene acceso a las fuentes originales del reportero, verifica
  de cero — es más caro pero más honesto; en producción real convendría que reciba
  también los links citados para no repetir búsquedas.
- La "gerencia" (presupuesto de tokens) no está automatizada — la puse manualmente
  en 15 agentes para este ensayo.
