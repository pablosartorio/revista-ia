# Plan — Arquitectura de agentes para "Cóndor"

> **Versión actual: v2 (23/09/2026).** La v1 (Nº 00) está documentada más abajo, tal como se
> diseñó. La v2 agrega las tres mejoras que salieron del cierre del Nº 00.

## v2: qué cambió y por qué

| Problema del Nº 00 | Mejora v2 | Dónde |
|---|---|---|
| El fact-check daba **un veredicto por bloque**: no decía qué dato estaba mal | **Libro de afirmaciones**: cada bloque se descompone en afirmaciones atómicas verificadas una por una, con un modelo distinto al redactor | `pipeline/etapas/verificar.workflow.js`, `roles/07` |
| La misma cifra quedó "confirmada" en una sección y "no verificable" en la nota de fondo; nadie comparaba bloques | **Reconciliación cruzada**: detectores en código + 2 reconciliadores con lentes distintas; cada conflicto se resuelve por **debate** (defensor, escéptico, juez) | `pipeline/etapas/reconciliar.workflow.js`, `roles/08` |
| Las correcciones se aplicaron a mano; el corrector de estilo de v1 ni siquiera llegaba al número final | **Editor de cierre con guardas + auto-reparación**; corrector de estilo por bloque con guarda de cifras y nombres | `pipeline/etapas/cierre.workflow.js`, `pipeline/condor.workflow.js` |
| "Publicado" era sólo un disclaimer en el pie | **Checkpoint humano real**: aprobación por bloque con hash, decisiones firmadas con la frase secreta de quien revisa (un agente no puede fabricar una decisión que se publique), riesgos aceptados con nota, tapa cruzada contra lo publicado, publicación bloqueada hasta completar | `condor/estado.py`, `roles/10` |
| La tapa era una directiva de texto | **Tapas SVG**: 3 ilustradores, jurado visual de 2 lentes, ronda de corrección del ganador, elección humana | `pipeline/etapas/tapa.workflow.js`, `roles/09` |

### Pipeline v2

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
