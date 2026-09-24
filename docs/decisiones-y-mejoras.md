# Decisiones de arquitectura y posibles mejoras

Este documento explica por qué la redacción de Cóndor funciona como funciona y qué se podría
mejorar. Está pensado para quien ya leyó el [README](../README.md) y quiere entender el
razonamiento detrás de cada pieza antes de tocarla. Para correr el sistema, andá al
[manual técnico](manual-tecnico.md).

Tiene tres partes:

1. **Historia breve**: v1 → v2 → v2.1, y qué problema concreto motivó cada salto.
2. **Registro de decisiones** (D-01 a D-17): contexto, decisión, alternativas y costos.
3. **Posibles mejoras** (M-01 a M-19), priorizadas por impacto y esfuerzo.

Convenciones:

- Cada afirmación sobre el sistema lleva la ruta del archivo que la respalda.
- En la parte 2, las alternativas que el repo documenta llevan su ruta. Las demás son las opciones
  obvias que la decisión descarta, reconstruidas para este documento.
- En la parte 3, **Verificado** quiere decir comprobado el 24/09/2026, sobre el commit `59b1bde`,
  leyendo el código o los datos o corriendo el comando indicado. **Propuesta** es lo que se sugiere
  hacer, y todavía no está probado. El código cambia: una verificación vale para esa versión.
- "Cóndor" es un nombre de trabajo (ver M-03).

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="img/recorrido-oscuro.png">
  <img alt="Recorrido de un número de Cóndor, de la investigación a la publicación" src="img/recorrido-claro.png">
</picture>

*Recorrido de un número. Versión interactiva: [diagramas/recorrido.html](diagramas/recorrido.html).*

---

## Parte 1. Cómo se llegó a la arquitectura actual

### Línea de tiempo

| Fecha | Hito | Fuente |
|---|---|---|
| 12-13/09/2026 | Nº 00, piloto con la arquitectura v1: 15 agentes, ~765.000 tokens, ~27,5 min | `output/numero-00/notas-del-ensayo.md`, `output/run.log` |
| 13/09/2026 | Cierre manual del Nº 00: un agente de verificación dedicado y revisión humana | `output/numero-00/notas-del-ensayo.md` |
| 23/09/2026 | Arquitectura v2. Primera corrida del Nº 01, cortada por límite de sesión | `plan.md` (v2), `runs/numero-01/NOTA.md` |
| 24/09/2026 | v2.1: regresión del Nº 00 arreglada (7/7). Nº 01 corrido, revisado y publicado | `plan.md` (v2.1), `runs/numero-01/NOTA.md` |

El historial de git arranca el 24/09 (commit `fa50bad`): la v1 y la v2 no tienen commits propios y
se reconstruyen desde `plan.md`, que las conserva tal como se diseñaron.

### v1: el piloto del Nº 00

**Diseño** (`plan.md`, sección "v1"). Quince agentes en una sola corrida: 9 corresponsalías en
paralelo, una nota de fondo que espera a las nueve, un corrector de estilo, 3 fact-checkers
adversariales en paralelo (cada uno con unos 3 bloques) y un director de arte. El armado era
código: `scripts/build_issue.py` con Jinja2. La tapa era una directiva de texto.

**Qué funcionó** (`output/numero-00/notas-del-ensayo.md`). Los 15 agentes terminaron sin errores.
La corresponsalía de Espacio funcionó de punta a punta con el MCP `patagonia-espacial`, sin
búsqueda web. El director de arte excluyó de la tapa a la nota de fondo, que tenía un veredicto
`no_verificable`.

**Qué falló**, y es lo que motivó la v2:

1. **El fact-check daba un veredicto por bloque.** No podía decir cuál dato de la nota estaba mal
   (`plan.md`, tabla de v2).
2. **El mismo dato recibió dos veredictos.** Oracle, 300.000 GPUs y 850 MW: el fact-checker del
   grupo 1 lo confirmó en Hardware; el del grupo 3, que revisaba la nota de fondo, no lo pudo
   confirmar en sus búsquedas y marcó todo el bloque como `no_verificable`. Nadie comparaba
   bloques entre sí (`output/numero-00/notas-del-ensayo.md`, `roles/08-reconciliacion-y-cierre.md`).
3. **Las correcciones se aplicaron a mano.** El corrector de estilo trabajaba sobre el borrador y
   no llegaba al número final (`plan.md`, tabla de v2).
4. **"Publicado" era un aviso en el pie.** No había aprobación real (`plan.md`, tabla de v2).

Hay un quinto hallazgo, menos visible, que pesó mucho después. **El cierre manual también se
equivocó.** Retiró la cifra de 300.000 GPUs por no encontrarla, y cambió el rango de DSEwiki a
"11 de mayo al 2 de julio" (`output/numero-00/notas-del-ensayo.md`). Al releer las fuentes el
24/09 se comprobó que Oracle sí desplegó más de 300.000 GPUs y que DSEwiki va del 24/5 al 22/6
(`tests/fixtures/numero-00-gt.json`, campo `origen`). El Nº 00 publicado todavía muestra la
corrección equivocada (`output/numero-00/index.md`, línea 45). La lección: ni una segunda pasada
dedicada ni la revisión humana son verdad absoluta. Por eso la v2 muestra la evidencia de cada
dato en la revisión (D-08) y compara contra un ground truth explícito y corregible (D-12).

### v2: lo que salió del cierre manual del Nº 00

`plan.md` (sección "v2") responde a cada falla de la v1:

| Problema del Nº 00 | Respuesta v2 | Decisión |
|---|---|---|
| Un veredicto por bloque | Libro de afirmaciones atómicas, verificadas por otro modelo | D-02, D-03 |
| Mismo dato, veredictos distintos | Reconciliación cruzada: detectores, 2 lentes y debate | D-04 |
| Correcciones a mano | Editor de cierre con guardas y auto-reparación | D-06 |
| "Publicado" era un aviso | Checkpoint humano con firma y hash | D-08 |
| Tapa de texto | Tapas SVG: 3 ilustradores, jurado y elección humana | D-09 |

**Cómo se probó** (`plan.md`, v2; la cifra de tests sale de `plan-resvista-01.md`, §1): 61
tests, una regresión sobre el Nº 00 original contra un ground truth de 6 casos y una revisión
adversarial del código.

**Qué quedó mal.** La regresión dio 3 OK y 3 FALLA, y **las 8 resoluciones quedaron sin
aplicar**, con 15 afirmaciones en `no_aplicado` (`plan-resvista-01.md`, sección 1). La primera
corrida del Nº 01 se cortó por límite de sesión: 52 agentes lanzados, 28 respondieron y 23
cayeron, sin resultado final (`runs/numero-01/NOTA.md`). Además, 2 de los 6 casos del ground
truth estaban mal (ver arriba).

### v2.1: la regresión y el Nº 01

`plan.md` (sección "v2.1") y `plan-resvista-01.md` detallan cada cambio:

| Problema | Respuesta v2.1 | Decisión |
|---|---|---|
| Dos jueces se contradecían sobre las mismas afirmaciones (C3 "cuatro semanas", C4 "seis semanas") | Etapa `consolidar` | D-05 |
| La guarda de cierre exigía todas las cifras de `valor_correcto`, que los jueces escriben en prosa: 0 de 8 fallos aplicados | Se exigen las cifras que están en `valor_correcto` y en `redaccion_sugerida` y no son valores viejos; los ids del libro no cuentan; `valor_correcto` corto en el schema | D-06 |
| Segunda revisión adversarial (dimensión "guardas"): 6 hallazgos | Se aplicó un arreglo para cada uno de los 6 (`plan.md`, tabla v2.1; `runs/numero-01/NOTA.md`) | D-01, D-14 |
| Corrida cortada y `resumeFromRunId` no sirve entre sesiones | Semilla de investigación | D-13 |
| Utilidades de cifras copiadas en cada `.js` sin control | Test de paridad JS ↔ Python y etapas corridas con `node` | D-14 |

**Cómo se probó** (`plan.md`, v2.1). Se llegó a 91 tests antes de congelar
(`runs/numero-01/NOTA.md`). Se corrigió el ground truth del Nº 00, que pasó de 6 a 7 casos. La
regresión barata desde el cierre (`pipeline/regresion-00-cierre.workflow.js`, 9 agentes) dio
**7/7 casos OK y 6/6 resoluciones aplicadas**, con C1, C3 y C4 consolidados en K1. Se reprodujo
el 24/09/2026 con `uv run python scripts/evaluar_regresion.py data/regresion-00-cierre.json`: 7 OK,
0 PARCIAL, 0 FALLA.

**El Nº 01** (`runs/numero-01/NOTA.md`). Corrida `wf_74b3799f-f3a` desde la copia congelada, con la
semilla (8 secciones y la nota de fondo; Espacio en vivo): 75 agentes, 0 errores, ~23 minutos.
Resultado: 148 afirmaciones (136 confirmadas, 9 matizadas, 1 corregida, 1 no verificable, 1 no
aplicada), 8 conflictos, 8 fallos y 6 aplicados. Coincide con `data/numero-01.json`.

La corrida destapó dos problemas más, arreglados en `pipeline/` pero no en la copia congelada:

- **Un fallo se aplicaba a todos los bloques del conflicto.** C7 matizaba `politica#1`, llegó a
  Espacio, la guarda lo rechazó y el cierre de Espacio falló entero, arrastrando la corrección
  C2 (coordenadas del SAOCOM 1B). Ahora cada fallo se aplica sólo donde están sus afirmaciones o
  sus cifras (`pipeline/etapas/cierre.workflow.js`; test
  `test_fallo_se_aplica_solo_donde_estan_sus_afirmaciones` en `tests/test_workflows_js.py`).
- **La portada publicaba el `concepto_tapa`**, una nota interna para los ilustradores. Ahora hay
  un copete para lectores (D-15).

En el checkpoint, el revisor pidió dos correcciones a mano en Espacio: las coordenadas de C2 y
"hoy jueves" → "jueves 24/09". También escribió el copete. Las dos correcciones están registradas
en `correcciones` de `data/numero-01.json`, con el motivo "corrección manual pedida por el
revisor". Con esos arreglos quedaron 93 tests (`uv run pytest -q`: 93 passed).

---

## Parte 2. Registro de decisiones

Cada entrada tiene el mismo formato: contexto, decisión, alternativas consideradas, consecuencias
y costos, y dónde está implementada. Todas están vigentes en v2.1.

### D-01. Los agentes redactan y juzgan; el código decide

**Contexto.** En el Nº 00 los agentes decidían solos qué pasaba con su trabajo: un fact-checker
podía confirmar un dato por un titular indexado sin leer la nota
(`output/numero-00/index.md`, línea 49). El dato resultó correcto (ver parte 1), pero el veredicto
se apoyó en un titular y no en la nota leída: el problema es el proceso, no el resultado. La
investigación previa documentó un caso con 20 artículos
publicados donde el 100% necesitó correcciones que la verificación automática no cazó
(`plan.md`, §4bis).

**Decisión.** Todo lo que devuelve un agente pasa por **guardas determinísticas** en código: cifras,
citas literales, ids, largos. Lo que no pasa se degrada a un estado de riesgo y nunca se publica a
medias (`plan-resvista-01.md`, §2.1, principio 1). La lógica del jefe de redacción (reparto,
barreras, ensamblado) también es código, no un agente (`roles/01-jefe-redaccion.md`,
`pipeline/condor.workflow.js`). El catálogo de guardas por etapa está en `plan-resvista-01.md`, §2.6.
Ejemplos:

- verificar: la `cita_textual` se busca literal en el bloque; un `confirmado` sin url baja a
  `no_verificable` (`pipeline/etapas/verificar.workflow.js`, `normalizarAfirmaciones` y `fusionar`).
- estilo: mismo multiconjunto de cifras, largo entre 75% y 125% y nombres protegidos; si falla, se
  descarta la edición (`pipeline/condor.workflow.js`).
- tapa: el puntaje del jurado lo suma el código, no el juez (`pipeline/etapas/tapa.workflow.js`).

**Alternativas consideradas.**
- Confiar en la autoevaluación del agente ("¿aplicaste bien la corrección?"). Es lo que hacía la
  v1 y produjo veredictos inconsistentes (`output/numero-00/notas-del-ensayo.md`).
- Un agente revisor de cada salida. Suma costo y hereda el mismo problema: otro juicio no
  determinístico.

**Consecuencias y costos.**
- Las guardas trabajan sobre cifras y cadenas, no sobre sentido. Tienen falsos negativos: un
  cambio de sentido sin tocar cifras pasa. Por eso existe el checkpoint (D-08).
- Tienen falsos positivos que bloquean correcciones válidas. En v2 la guarda de cierre era
  imposible de cumplir y dejó 0 de 8 fallos aplicados (`plan.md`, v2.1). Cada guarda nueva
  necesita tests con casos reales (`tests/test_workflows_js.py`).
- La lógica de cifras tiene que ser idéntica en JS y en Python (D-14).

### D-02. Modelos distintos para redactar y para verificar

**Contexto.** La investigación previa documentó sesgo de auto-preferencia cuando un modelo
verifica su propio texto (`roles/07-libro-de-afirmaciones.md`).

**Decisión.** Los verificadores del libro y los escépticos del debate corren con
`modelo_verificador` (hoy `sonnet`, pasado por `args`). Los corresponsales, extractores,
defensores, jueces, el editor de cierre y el arte usan el modelo de la sesión
(`pipeline/etapas/verificar.workflow.js` y `pipeline/etapas/reconciliar.workflow.js`, opción
`model`). El prompt del verificador le dice que el bloque lo redactó "otro agente (de otro
modelo)".

**Alternativas consideradas.**
- Mismo modelo en todos los roles, con prompts adversariales. Es la v1: 3 fact-checkers "instruidos
  a default a no verificable" (`plan.md`, §4bis y `roles/04-fact-checker.md`).
- Proveedores distintos. No hay nada en el repo que lo contemple.

**Consecuencias y costos.**
- La independencia es parcial: los dos modelos son de la misma familia.
- El juez del debate usa el modelo de redacción, igual que el defensor. El escéptico es el único
  con el otro modelo en ese trío (`pipeline/etapas/reconciliar.workflow.js`).
- Cambiar `modelo_verificador` cambia resultados: queda registrado en `meta.modelo_verificador`
  de cada número (`pipeline/condor.workflow.js`).

### D-03. Libro de afirmaciones atómicas

**Contexto.** El fact-check por bloque de la v1 no podía decir cuál dato estaba mal
(`roles/07-libro-de-afirmaciones.md`).

**Decisión.** Un extractor por bloque descompone el texto en afirmaciones atómicas (cifra, fecha,
nombre, evento, atribución) con `cita_textual`. Cada una recibe un id estable (`bloque#n`) y un
veredicto propio de un verificador que lee la fuente y hace hasta 3 búsquedas. Si quedan cifras
del bloque sin afirmación, corre una **ronda de completitud**. Las que ni así se extraen quedan
como guarda bloqueante (`pipeline/etapas/verificar.workflow.js`).

**Alternativas consideradas.**
- Veredicto por bloque (v1, `roles/04-fact-checker.md`).
- Verificar el bloque entero con una lista libre de problemas. No da ids estables para cruzar
  entre notas, ni para aplicar correcciones, ni para mostrar en la revisión.

**Consecuencias y costos.**
- Todo lo de abajo se apoya en los ids: reconciliación, fallos, cierre, riesgos del checkpoint y la
  caja "Cómo verificamos" (`condor/templates/issue.md.j2`).
- Es caro: en el Nº 01 hubo 10 extractores, 7 rondas de completitud y 10 verificadores, 27 de los
  75 agentes (conteo por `label` en `runs/numero-01/journal-wf_74b3799f-f3a.jsonl`). Ver M-16.
- Los ids se cuelan en la prosa de los jueces (`feature#17`) y hay que quitarlos antes de contar
  cifras (`sinIds` en los `.js`, `quitar_ids` en `condor/numeros.py`).

### D-04. Reconciliación cruzada: detectores, dos lentes y debate

**Contexto.** En el Nº 00 la misma cifra quedó confirmada en una sección y no verificable en la
nota de fondo, porque cada fact-checker miraba su bloque (`roles/08-reconciliacion-y-cierre.md`).

**Investigación previa** (`plan.md`, §4bis). Antes del piloto, un agente de investigación buscó qué
se sabía sobre pipelines editoriales multi-agente. Tres hallazgos marcaron el diseño:

- El tamaño óptimo documentado es de 3 a 5 agentes especializados, y el rendimiento cae pasados
  unos 20 cuando se coordinan en cadena (Arion Research / Codebridge, 2026). `plan.md`, §4bis,
  proponía darle a cada corresponsalía sólo su fragmento de línea editorial. En la práctica todas
  reciben el mismo resumen (`LINEA` en `pipeline/condor.workflow.js`). Lo que sí se mantuvo es que
  los beats corren en paralelo y no se coordinan entre sí. El Nº 01 usó 75 agentes, muy por encima
  de los ~20 que cita la investigación; el diseño lo compensa porque los agentes no se coordinan en
  cadena: cada uno recibe su tarea y el código junta los resultados.
- El patrón más citado para reducir alucinaciones al verificar cifras es un debate de 2 agentes
  con posturas opuestas y un juez (paper "Debating Truth", ACM Web Conf. 2026). La v1 usó una
  versión más barata (3 fact-checkers en paralelo) y lo dejó anotado como "concesión consciente
  de costo".
- Ningún medio grande (DMG Media, AP, India Today, NYT) publica sin visto bueno humano final.

**Decisión** (`pipeline/etapas/reconciliar.workflow.js`).

1. **Detectores en código**: cifras de la nota de fondo que no están en ninguna sección
   (huérfanas), y pares de afirmaciones de distintos bloques con la misma cifra y entidad pero
   veredictos distintos.
2. **Dos reconciliadores con lentes distintas**, en paralelo: "hechos" (mismo hecho, valores o
   veredictos distintos) y "cronología" (fechas, rangos, duraciones derivadas, porcentajes).
   También juzgan los candidatos del código, y los descartados quedan registrados.
3. **Debate por conflicto**: defensor (modelo de redacción) y escéptico (modelo verificador) en
   paralelo, con hasta 2 búsquedas cada uno. Después un juez decide `mantener`, `corregir`,
   `retirar`, `matizar` o `sin_consenso`.
4. Toda afirmación `contradicho` entra como conflicto. Tope de 10 debates: lo que exceda va al
   checkpoint como "sin resolver" y queda logueado.

**Alternativas consideradas.**
- 3 fact-checkers en paralelo con sesgo a "no verificable" (v1, `plan.md`, §4bis).
- Un solo verificador adversarial por conflicto. La investigación citada favorece el debate
  (`plan.md`, §4bis).
- Una sola lente. Las lentes separan tipos de error que un solo agente mezcla: la duración
  "seis semanas" contra el rango de fechas es un error de cronología, no de hecho
  (`roles/08-reconciliacion-y-cierre.md`).

**Consecuencias y costos.**
- Es la etapa más cara: en el Nº 01, 2 lentes, 16 alegatos y 8 jueces, 26 agentes
  (`runs/numero-01/journal-wf_74b3799f-f3a.jsonl`).
- Cada juez falla sin ver los otros conflictos, y eso produjo fallos contradictorios (D-05).
- Devuelve **grupos** (mismo hecho en varios bloques) que el checkpoint usa para detectar
  dependencias de bloques retirados (`riesgos_bloque` en `condor/estado.py`).
- El juez decide con la evidencia de los alegatos y puede hacer un solo WebFetch. Si ambos se
  equivocan igual, el juez hereda el error.

### D-05. Consolidación de fallos

**Contexto.** En la regresión del Nº 00, C3 corregía una duración a "cuatro semanas" y C4 a "seis
semanas", sobre las mismas afirmaciones (`plan.md`, v2.1).

**Decisión** (`pipeline/etapas/consolidar.workflow.js`, entre reconciliar y cierre).

- El código arma componentes conexos (union-find) de los fallos que editan (`corregir`,
  `retirar`, `matizar`) y comparten `afirmaciones_afectadas`.
- Por cada componente con 2 o más fallos, un juez de consolidación recibe fallos, alegatos,
  afirmaciones y textos. Devuelve una resolución `K1`, `K2`… con `conflictos_cubiertos`. Ante la
  duda, `sin_consenso`.
- Guardas: la resolución tiene que cubrir todas las afirmaciones del componente y no puede traer
  cifras que no estén en lo que el juez tuvo delante. Si no pasa, quedan los fallos originales y
  una guarda bloqueante `consolidacion_caida`.
- Un conflicto cubierto cuenta como resuelto en el orquestador (`conFallo`), en el checkpoint
  (`indice_resoluciones` en `condor/estado.py`) y en la revisión ("Consolidado en K1").

**Alternativas consideradas.** El diseño está en `plan-resvista-01.md`, §3.1.2; estas
alternativas no están ahí, son reconstruidas.
- Un solo juez para todos los conflictos. Pierde el paralelismo y mezcla evidencia de hechos que
  no se tocan.
- Dejar que el editor de cierre resuelva la contradicción. Eso le daría un juicio editorial que
  no le corresponde: sólo aplica fallos (`roles/08-reconciliacion-y-cierre.md`).

**Consecuencias y costos.**
- Si no hay fallos compartidos no lanza agentes: en el Nº 01 no hubo consolidaciones
  (`runs/numero-01/NOTA.md`; test `test_sin_fallos_compartidos_no_lanza_agentes`).
- Riesgo documentado: el juez de consolidación puede introducir errores nuevos. La mitigación son
  las mismas guardas del cierre y el `sin_consenso` (`plan-resvista-01.md`, §6).
- Sólo está probada contra la regresión del Nº 00, con un único caso real (K1).

### D-06. Cierre con guardas, una ronda de auto-reparación y `no_aplicado`

**Contexto.** En la v1 las correcciones se aplicaron a mano (`plan.md`, tabla de v2).

**Decisión** (`pipeline/etapas/cierre.workflow.js`).

- Un editor de cierre por bloque afectado aplica los fallos con el mínimo cambio, sin investigar
  ni mejorar el estilo.
- Guardas después de cada edición: lo retirado no puede seguir (ni literal ni sus cifras); el
  valor viejo corregido tiene que desaparecer y el nuevo aparecer; un valor viejo no numérico
  tiene que desaparecer; matizar tiene que agregar texto; no puede aparecer ninguna cifra que no
  esté en el original o en la corrección.
- Si falla, hay **una** ronda de auto-reparación con la lista de errores. Si vuelve a fallar, se
  conserva el texto original, las afirmaciones quedan `no_aplicado` y el bloque recibe una guarda
  bloqueante. **Nunca se publica una corrección a medio aplicar.**
- Después del Nº 01 (arreglo en `pipeline/`, no incluido en su copia congelada), cada fallo se
  aplica sólo en los bloques de sus afirmaciones o de sus cifras.

**Alternativas consideradas.**
- Aplicar las correcciones con reemplazo de cadenas en código. Los jueces dan una redacción
  sugerida, no un parche exacto, y el texto alrededor suele necesitar ajuste (la instrucción de
  "ajustá lo que dependa de él" en `cierrePrompt`).
- Reintentar hasta que pase. Sin tope, el costo no está acotado y el editor puede terminar
  "forzando" el texto para cumplir la guarda.
- Publicar la mejor versión aunque falle alguna guarda. Contradice D-01.

**Consecuencias y costos.**
- `no_aplicado` es un estado de riesgo: no cuenta como verificado, no puede llegar a la tapa y
  obliga a una decisión humana (`ESTADOS_RIESGO` en `pipeline/condor.workflow.js`,
  `condor/estado.py` y `scripts/evaluar_regresion.py`).
- En el Nº 01, el cierre de Espacio falló por el bug de C7 y la corrección C2 se hizo a mano en el
  checkpoint (`runs/numero-01/NOTA.md`). La degradación funcionó como se diseñó: nada se publicó a
  medias. Pero trasladó trabajo al revisor.
- La guarda depende de que `valor_correcto` sea corto. El schema lo pide, pero un juez puede no
  cumplirlo, y por eso la guarda también tolera prosa (`guardar()` en `cierre.workflow.js`).

### D-07. Nada se cae en silencio

**Contexto.** Una corrida tiene decenas de agentes. Alguno va a fallar, y la primera corrida del
Nº 01 perdió 23 (`runs/numero-01/NOTA.md`).

**Decisión.**

- `hijo()` envuelve cada etapa hija: si falla, devuelve un **resultado neutro** y deja una guarda
  bloqueante `etapa_caida` en cada bloque afectado. La corrida sigue (`pipeline/condor.workflow.js`).
- Cada etapa convierte sus propias fallas en guardas: extractor caído dos veces, reconciliadores
  caídos, consolidación caída, cierre caído (en las etapas de `pipeline/etapas/`).
- Los topes se registran: el de debates deja un `log` y una guarda `tope_debates`
  (`pipeline/etapas/reconciliar.workflow.js`).
- El checkpoint convierte toda guarda bloqueante de un bloque en un riesgo que exige `--nota` para
  aprobar (`riesgos_bloque` en `condor/estado.py`).

**Alternativas consideradas.**
- Abortar la corrida ante cualquier falla. Se pierde todo lo hecho, y con corridas de más de 20
  minutos y límites de sesión eso es caro (`plan-resvista-01.md`, §2.8).
- Seguir sin marcar nada. Es la "falla silenciosa" que esta decisión evita.

**Consecuencias y costos.**
- Un número puede llegar al checkpoint con muchos bloques bloqueados. Eso es correcto, pero la
  persona que revisa tiene que entender cada guarda (las muestra `revision.html`).
- El resultado neutro de cierre copia las afirmaciones con su veredicto original y marca las
  resoluciones como no aplicadas (`pipeline/condor.workflow.js`, llamada a `hijo('cierre', …)`).
- Queda al menos un tope sin registrar: el arte recibe como máximo 60 afirmaciones confirmadas
  (`confirmadas.slice(0, 60)`), sin log (ver M-18).

### D-08. Checkpoint humano: terminal, frase secreta, firma HMAC y hash

**Contexto.** En la v1, "publicado" era un aviso en el pie (`plan.md`, tabla de v2). La
investigación previa concluyó que el fact-check reduce el riesgo pero no lo elimina (`plan.md`,
§4bis), y el cierre manual del Nº 00 mostró que también la revisión se equivoca (parte 1).

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="img/checkpoint-oscuro.png">
  <img alt="Estados de un número en la revisión humana" src="img/checkpoint-claro.png">
</picture>

*Estados de un número. Versión interactiva: [diagramas/checkpoint.html](diagramas/checkpoint.html).*

**Decisión** (`condor/estado.py`, `condor/cli.py`, `roles/10-checkpoint-humano.md`).

- Ciclo `borrador → en_revision → aprobado → publicado`.
- `aprobar`, `retirar`, `tapa` y `publicar` exigen **terminal interactiva**, la **frase secreta**
  de quien revisa y tipear el número del ejemplar (`exigir_humano`). `clave` exige terminal y, para
  cambiar una clave existente, la frase actual (`configurar_clave`); no pide número.
- La frase no se guarda. Se deriva una clave con scrypt y en `~/.config/condor/revisor.json` queda
  sólo un verificador (`configurar_clave`). Cada decisión se **firma con HMAC**, y `publicar`
  rechaza cualquier decisión sin firma válida (`verificar_firmas`).
- **La aprobación queda atada al hash** de todo lo publicable del bloque y de sus afirmaciones
  (`hash_bloque`). Si algo cambia, vence sola.
- Un bloque con riesgos no entra con `--todo`: exige `--bloque` y `--nota`. Los riesgos aceptados
  se identifican por contenido (`clave_riesgo`); si aparece uno nuevo, la aprobación vence.
- El checkpoint recalcula los riesgos por su cuenta (defensa en profundidad): cifras sin
  trazabilidad, retiradas que siguen en el texto, dependencias de bloques retirados.
- Un lock (`_bloqueo`, con `fcntl`) serializa las decisiones, y cada acción revalida bajo el lock
  después de pedir la frase.

**Alternativas consideradas.**
- Una confirmación simple ("¿publicar? s/n"). Un agente con acceso a la terminal la puede
  responder.
- Sólo exigir TTY. Es una barrera contra errores, no contra un agente que edita
  `data/numero-XX.revision.json`. La firma es lo que hace que una decisión fabricada no se
  publique (`tests/test_revision_segura.py`, `test_decision_escrita_por_un_agente_no_se_publica`).
- Aprobar el número entero de una vez. Pierde granularidad: en el Nº 01 se aprobaron 8 bloques
  sin nota y 2 con nota y riesgos aceptados (`data/numero-01.revision.json`).

**Consecuencias y costos.**
- **Límite honesto**, documentado en `roles/10-checkpoint-humano.md`: un agente que corre con el
  mismo usuario Unix podría, con intención, reemplazar la clave o modificar `condor/`. El diseño
  garantiza que no pase por accidente ni sin rastro, porque la huella de la clave queda en cada
  decisión.
- Cualquier cambio posterior obliga a volver a decidir. El historial del Nº 01 registra tres
  `publicar` el mismo día, intercalados con nuevas aprobaciones y elecciones de tapa
  (`data/numero-01.revision.json`, campo `historial`).
- Quedan huecos que conviene revisar en la dimensión "checkpoint" de la revisión adversarial
  (M-04).

### D-09. Tapa SVG y tapa atada al SHA del archivo aprobado

**Contexto.** En la v1 la tapa era una directiva de texto (`plan.md`, §5). No hay GPU para
difusión local (`roles/09-tapa.md`).

**Decisión** (`pipeline/etapas/tapa.workflow.js`, `condor/svg.py`, `condor/estado.py`).

- 3 ilustradores en paralelo con enfoques distintos (tipográfico, metáfora visual, data-driven).
  Cada uno escribe un SVG, lo valida con `condor tapa-validar`, lo rasteriza con
  `condor tapa-render` y **mira los PNG** para corregirse, hasta 3 iteraciones.
- Jurado de 2 lentes (editorial y visual). El puntaje lo calcula el código. El ganador tiene una
  ronda de corrección y un juez confirma que mejoró.
- El dato ancla sólo puede ser una afirmación confirmada de un bloque sin riesgos; las líneas de
  tapa sólo salen de bloques sin riesgos (`pipeline/condor.workflow.js`).
- La elección es humana. Elegir guarda una copia con nombre por contenido
  (`tapa/elegida-<sha>.svg`); se publica esa copia y el PNG se genera desde ella al publicar
  (`elegir_tapa` en `condor/estado.py`, `render_final` en `condor/render.py`). Elegir la tapa
  también aprueba los metadatos del número (`hash_meta`).
- El checkpoint vuelve a validar el SVG al elegirlo y cruza sus cifras contra lo que se publica
  (`riesgos_tapa`).

**Alternativas consideradas.**
- Generación de imágenes con difusión. Sin GPU local (`roles/09-tapa.md`).
- Un solo ilustrador. Sin alternativas, el jurado no tiene con qué comparar.
- Copiar el PNG de los agentes. Un PNG no se puede validar como un SVG, y podría no corresponder
  al SVG aprobado (`tests/test_revision_segura.py`, `test_el_png_publicado_sale_del_svg_aprobado`).

**Consecuencias y costos.**
- Son 7 agentes por número (`runs/numero-01/journal-wf_74b3799f-f3a.jsonl`).
- El `validacion_ok` del ilustrador es autodeclarado. Lo compensa la revalidación del checkpoint.
- Las tapas son geométricas y tipográficas por diseño: el brief prohíbe robots genéricos, logos
  reales y caras (`pipeline/condor.workflow.js`, `pipeline/etapas/tapa.workflow.js`).

### D-10. Armado con Jinja2: maquetar no es una decisión editorial

**Contexto.** Desde la v1 se separó "redacción" (juicio) de "producción" (ejecución mecánica)
(`plan.md`, v1 §0 punto 7; `roles/06-editor-digital-cms.md`).

**Decisión.** El armado de `borrador.html`, `revision.html`, `index.html` e `index.md` es código
Python con Jinja2 (`condor/render.py`, `condor/templates/`). No toma decisiones: todo sale de
`data/numero-XX.json` y de las decisiones de revisión.

**Alternativas consideradas.**
- Un agente maquetador. No hay ambigüedad editorial en poner un `<div>` en su lugar (`plan.md`,
  v1 §3), y un agente podría alterar el contenido al maquetar.

**Consecuencias y costos.**
- Lo publicado es reproducible desde los datos y las decisiones. `publicar` guarda el hash de cada
  archivo generado (`publicar` en `condor/estado.py`).
- Los errores de presentación son bugs de plantilla, no de contenido. Hay uno en el Markdown del
  Nº 01 (M-15).
- Conviven dos juegos de plantillas: los de v1 (`scripts/build_issue.py`, `scripts/templates/`) y
  los de v2 (`condor/templates/`). Ver M-17.

### D-11. Copia congelada del pipeline por número

**Contexto.** El pipeline cambia entre números. Sin registro, no se puede saber con qué código se
produjo un número publicado.

**Decisión.** Cada número corre desde `runs/numero-XX/pipeline/`, con `SHA256SUMS`, pasando
`args.etapas`. Si hay que recongelar, el motivo y el hash anterior van en `runs/numero-XX/NOTA.md`
(`plan.md`, v2.1).

**Alternativas consideradas.**
- Un tag o commit de git por número. Hubiera servido, pero el historial arranca en v2.1 y la copia
  no depende de git para correr.
- Correr siempre desde `pipeline/`. Mezcla arreglos posteriores con lo que efectivamente se corrió.

**Consecuencias y costos.**
- Verificado: `sha256sum -c SHA256SUMS` en `runs/numero-01/pipeline/` da OK en los 6 archivos.
- Diverge a propósito: `cierre.workflow.js` y `condor.workflow.js` de la copia no tienen los
  arreglos posteriores al Nº 01 (el bug de C7 y el copete). `diff` lo confirma, y
  `runs/numero-01/NOTA.md` lo documenta.
- La copia se recongeló una vez, porque la corrida anterior no produjo número. Queda el hash del
  `SHA256SUMS` anterior en la nota.

### D-12. Regresión contra un número con errores conocidos

**Contexto.** Para saber si un cambio mejora la verificación hace falta un caso con respuestas
conocidas. El Nº 00 original tenía errores encontrados a mano (`plan.md`, v2).

**Decisión.**

- `tests/fixtures/numero-00-original.json` guarda el Nº 00 tal como lo escribió la v1.
  `scripts/generar_regresion.py` lo embebe en `pipeline/regresion-00.workflow.js`, porque los
  workflows no leen disco.
- `tests/fixtures/numero-00-gt.json` es el ground truth: 7 casos, con un campo `origen` que dice de
  dónde sale y que "no es verdad absoluta".
- `scripts/evaluar_regresion.py` puntúa una corrida caso por caso.
- Hay una variante barata desde el cierre (`--desde-cierre`, 9 agentes) que reusa libro,
  conflictos y fallos de una corrida completa.

**Alternativas consideradas.**
- Sólo tests unitarios. Prueban las guardas, no si el pipeline encuentra y corrige errores reales.
- Evaluar a ojo cada número nuevo. Sin casos fijos no se puede comparar entre versiones.

**Consecuencias y costos.**
- El ground truth también se equivocó: 2 de los 6 casos originales estaban mal, porque heredaban
  el cierre manual (parte 1). Hubo que corregirlo leyendo las fuentes.
- La regresión completa cuesta unos 50 agentes (`plan-resvista-01.md`, §2.3). Por eso la v2.1 se
  validó con la variante desde el cierre, que no vuelve a correr verificar ni reconciliar.
  `data/regresion-00.json` es de v2 (no tiene la clave `consolidacion`): la regresión completa no
  se corrió con v2.1 (M-07).
- Re-evaluando `data/regresion-00.json` con el ground truth actual da 4 OK, 3 PARCIAL y 0 FALLA. El
  "3 OK / 3 FALLA" de `plan-resvista-01.md` es con el ground truth viejo de 6 casos.

### D-13. Semilla de investigación

**Contexto.** La primera corrida del Nº 01 se cortó con 28 de 52 agentes. `resumeFromRunId` sólo
funciona dentro de la misma sesión (`plan-resvista-01.md`, §2.8).

**Decisión.** `args.semilla = {origen, secciones, feature}` reusa beats y nota de fondo ya
investigados: esos beats no lanzan agente y la verificación corre igual. El resultado lo registra
en `meta.semilla` para que la revisión lo vea (`pipeline/condor.workflow.js`).
`scripts/semilla_desde_journal.py` arma la semilla desde el journal, e `importar` acepta el
`.output` del workflow tal cual (`condor/importar.py`, `desenvolver`).

**Alternativas consideradas** (`plan-resvista-01.md`, Fase 0, D2).
- Relanzar todo desde cero: más caro y con otra ventana de noticias.
- Corridas en tramos reanudables (`args.desde` con estado intermedio). Más general, queda como deuda
  (`plan-resvista-01.md`, §7; M-05).

**Consecuencias y costos.**
- El Nº 01 reusó 8 beats y la nota de fondo (`data/numero-01.json`, `meta.semilla`).
- Lo que depende de la fecha envejece. Espacio se excluyó de la semilla y se rehízo en vivo porque
  sus pasos eran "esta semana" respecto del 23/09 (`runs/numero-01/NOTA.md`). Aun así, el beat en
  vivo escribió "hoy jueves" (M-02).
- La semilla sólo cubre la investigación. Una corrida cortada en reconciliar pierde todo lo demás.

### D-14. Utilidades duplicadas en cada `.js`, con test de paridad

**Contexto.** Los workflows no importan módulos ni leen disco (`plan-resvista-01.md`, §2.8). Según
la referencia del runtime de Workflows, el anidamiento es de un solo nivel: `workflow()` dentro de
una etapa hija falla. Esta restricción no está escrita en el repo, pero se ve en la estructura: el
orquestador llama a las etapas y ninguna etapa llama a otra, y las regresiones llaman a las etapas
directamente en vez de pasar por `condor.workflow.js` (`pipeline/regresion-00.workflow.js`).

**Decisión.** `significativa`, `sig` y `sinIds` están copiadas en las cuatro etapas con guardas de
cifras (verificar, reconciliar, consolidar y cierre); `cifrasAf`, en tres de ellas (todas menos
consolidar). El orquestador tiene sólo `canonNum`, `nums`, `norm` y `dec`, y tapa y las regresiones
no tienen ninguna. `condor/numeros.py` es su espejo en Python. `tests/test_paridad_js.py`
comprueba que sean idénticas entre los `.js` y que den lo mismo que Python (con `node`).
`tests/test_workflows_js.py` corre etapas con un `agent` simulado (`tests/js/correr_workflow.mjs`).

**Alternativas consideradas.**
- Un `_comun.js` compartido. No se puede importar. El docstring de `numeros.py` lo mencionaba y se
  corrigió (`plan-resvista-01.md`, §2.7 y §3.1.6).
- Generar los `.js` desde una plantilla con las utilidades insertadas. No está en el repo.
- Pasar las utilidades como texto por `args` y evaluarlas. No está en el repo.

**Consecuencias y costos.**
- Un cambio en la regla de cifras hay que hacerlo en varios `.js` y en Python: `canonNum` vive en
  5 `.js`, `significativa`, `sig` y `sinIds` en 4. El test lo detecta, pero no lo evita.
- La paridad no cubre todo: `norm` difiere entre archivos (M-10).
- Los tests con `node` cubren cierre, consolidar y el orquestador con semilla, pero no verificar,
  reconciliar ni tapa (M-11).

### D-15. Copete para lectores, separado del concepto interno de tapa

**Contexto.** En el Nº 01 la portada publicaba el `concepto_tapa`, una nota del director de arte
para los ilustradores, con jerga interna (`runs/numero-01/NOTA.md`).

**Decisión.** El director de arte escribe un `copete` para lectores (1-2 oraciones, sin claves de
bloque ni "dato ancla", sin cifras de notas con riesgo). La portada publica sólo el copete y el
concepto queda en la revisión como nota interna (`ART_SCHEMA` en `pipeline/condor.workflow.js`;
`condor/templates/issue.html.j2`, `issue.md.j2` y `revision.html.j2`; test
`test_la_portada_publica_el_copete_y_no_el_concepto_interno` en `tests/test_v21.py`).

**Alternativas consideradas.**
- Reescribir el concepto como texto para lectores. Mezcla dos audiencias en un campo.
- Sin copete. La revisión lo resalta como aviso visual ("sin copete: la portada sale sin bajada",
  `condor/templates/revision.html.j2`), pero el checkpoint no lo bloquea: ni `riesgos_bloque` ni
  `riesgos_tapa` miran `meta.copete` (`condor/estado.py`).

**Consecuencias y costos.**
- El copete entra en `meta`, así que elegir la tapa lo aprueba (`hash_meta` cubre todo `meta`).
- Ninguna guarda en código revisa sus cifras: la regla está sólo en el prompt (M-08).
- El copete del Nº 01 lo escribió el revisor, porque el campo no existía en la copia congelada.

### D-16. Python siempre con `uv`

**Contexto.** El proyecto tiene un paquete (`condor`) con dependencias fijadas (`uv.lock`) y un CLI.

**Decisión.** Todo se corre con `uv` (`uv run pytest -q`, `uv run condor …`), nunca con `pip`
directo (`CLAUDE.md`, "Reglas"). El paquete declara el script `condor = "condor.cli:main"` y
`[tool.uv] package = true` (`pyproject.toml`). Los ilustradores de tapa llaman al CLI con
`uv run --project <raiz> condor` (`pipeline/etapas/tapa.workflow.js`).

**Alternativas consideradas.**
- `pip` con un virtualenv manual: sin lockfile, y el entorno de los agentes podría diferir del
  humano.

**Consecuencias y costos.**
- El entorno se recrea con `uv sync` (`.gitignore`). Dependencias mínimas: `jinja2` y `defusedxml`,
  más `pytest` en desarrollo (`pyproject.toml`).
- `tapa-render` además necesita `rsvg-convert` y las fuentes instaladas (`roles/09-tapa.md`,
  `condor/svg.py`), que `uv` no gestiona.

### D-17. Una corresponsalía alimentada por datos, no por la web

**Contexto.** Desde la v1 se buscó que la revista no dependa sólo de búsqueda web (`plan.md`, v1 §0
punto 3; `roles/02-corresponsalias.md`).

**Decisión.** La corresponsalía "Ciencia y Espacio: Patagonia" no busca en la web: consulta el MCP
`patagonia-espacial` (`listar_satelites`, `donde_esta`, `proximos_pasos`) y cita
`mcp://patagonia-espacial`. Su verificador vuelve a consultar el MCP en vez de buscar en la web
(`pipeline/condor.workflow.js`, `ESPACIO`; `pipeline/etapas/verificar.workflow.js`, `verifyPrompt`).

**Alternativas consideradas.**
- Una novena corresponsalía web más. Pierde la sección con datos en vivo, que la v1 planteó como
  prueba de que la arquitectura admite otras fuentes.

**Consecuencias y costos.**
- Los datos son relativos al momento de la corrida (pasos "en los próximos días"), así que la nota
  envejece y no se puede reusar en una semilla (D-13).
- El prompt no recibe la fecha del número (sólo `ciudad_espacio`), y así apareció "hoy jueves" en
  un número fechado el 23/09 (M-02).
- El prompt tiene memoria escrita a mano: "que NO sea el SAOCOM 1A … (ya fue nota en el número
  anterior)" (M-12).

---

## Parte 3. Posibles mejoras

### Tabla priorizada

Impacto: cuánto reduce el riesgo de publicar algo mal o el trabajo del revisor. Esfuerzo: estimado
a partir del código que hay que tocar. La tabla está ordenada por impacto y, dentro de cada nivel,
por esfuerzo. Origen: **pendiente** si ya figura en `plan.md` (v2.1, "Pendiente") o en
`plan-resvista-01.md`, §7; **detectada** si salió de leer el código, los datos o la retro para
este documento.

| # | Mejora | Impacto | Esfuerzo | Origen |
|---|---|---|---|---|
| M-02 | Fechas absolutas en beats en vivo, con guarda | Alto | Bajo | Pendiente |
| M-01 | Restaurar el dato correcto de Oracle en el Nº 00 publicado | Alto | Medio | Pendiente |
| M-09 | Comando firmado para las correcciones del checkpoint | Alto | Medio | Detectada |
| M-04 | Dimensiones "checkpoint" y "workflows" de la revisión adversarial | Alto | Medio | Pendiente |
| M-07 | Regresión con ground truth del Nº 01 y regresión completa del Nº 00 con v2.1 | Alto | Medio | Pendiente |
| M-08 | Guarda de cifras sobre copete y título del número | Medio | Bajo | Detectada |
| M-19 | Actualizar `CLAUDE.md` a v2.1 | Medio | Bajo | Detectada |
| M-10 | Paridad de `norm` entre workflows | Medio | Bajo | Detectada |
| M-12 | Memoria entre números por `args` | Medio | Bajo | Detectada |
| M-11 | Tests con `node` para verificar, reconciliar y tapa | Medio | Medio | Detectada |
| M-03 | Nombre de la revista en una sola constante | Medio | Medio | Pendiente |
| M-06 | Presupuesto de tokens por etapa | Medio | Medio | Pendiente |
| M-05 | Corridas reanudables entre sesiones | Medio | Alto | Pendiente |
| M-13 | Línea editorial y claves de beats en una sola fuente | Bajo | Bajo | Detectada |
| M-14 | Actualizar los roles que siguen describiendo la v1 | Bajo | Bajo | Detectada |
| M-15 | Arreglar la plantilla Markdown | Bajo | Bajo | Detectada |
| M-16 | Ajustar el tope del extractor para no depender de la completitud | Bajo | Bajo | Detectada |
| M-17 | Marcar como legado el CMS de v1 | Bajo | Bajo | Detectada |
| M-18 | Registrar el tope de 60 afirmaciones del arte | Bajo | Bajo | Detectada |

### Primero: alto impacto, esfuerzo bajo o medio

**M-02. Fechas absolutas en beats en vivo.**
- *Verificado.* El prompt de Espacio no recibe `fecha_larga`: pide pasos "en los próximos días"
  (`pipeline/condor.workflow.js`, `ESPACIO`). Los prompts de los otros beats reciben sólo la
  `ventana`. No hay ninguna guarda sobre expresiones relativas (búsqueda de "hoy", "mañana" y "esta
  semana" en `pipeline/`: ninguna guarda ni prompt las menciona; sólo aparecen en el texto de los
  fixtures embebidos en las regresiones). En el Nº 01 hubo que corregir a mano "hoy jueves"
  (`data/numero-01.json`, `correcciones`).
- *Propuesta.* Pasar la fecha del número a todos los prompts y pedir fechas absolutas. Sumar en el
  orquestador una guarda de aviso que detecte "hoy", "ayer", "mañana", "esta semana" y "el próximo
  <día>" en los textos finales, y un riesgo equivalente en `riesgos_bloque`.

**M-01. Restaurar el dato de Oracle en el Nº 00.**
- *Verificado.* El Nº 00 publicado dice que las 300.000 GPUs "no pudo confirmarse" y se retiró
  (`output/numero-00/index.md`, líneas 20 y 45). El ground truth corregido dice que el dato es
  correcto (`tests/fixtures/numero-00-gt.json`, caso `oracle_300k_gpus`). También el rango de
  DSEwiki publicado ("11 de mayo al 2 de julio") contradice el ground truth (caso
  `dsewiki_fechas`).
- *Verificado.* `data/numero-00.json` es formato v1 (no tiene `version`). El checkpoint exige
  versión 2 (`cargar` en `condor/estado.py`), así que hoy `condor` no puede revisar ni republicar el
  Nº 00.
- *Propuesta.* Es una decisión humana (`plan-resvista-01.md`, Fase 0, D1). Hay dos caminos: migrar
  el Nº 00 a v2 (bloques, afirmaciones mínimas, `versiones.investigacion`) para pasarlo por el
  checkpoint, o publicar una fe de erratas firmada fuera del flujo. El primero sirve además para
  cualquier edición futura de números viejos.

**M-09. Comando firmado para las correcciones del checkpoint.**
- *Verificado.* Las correcciones que pidió el revisor en el Nº 01 se aplicaron editando
  `data/numero-01.json` a mano y registrándolas en `correcciones` (`runs/numero-01/NOTA.md`). En
  `riesgos_bloque`, las cifras del campo `despues` de una corrección pasan a ser "permitidas" para
  la trazabilidad (`condor/estado.py`). La aprobación posterior cubre el texto final por hash,
  pero el registro de la corrección no lleva firma.
- *Propuesta.* Un `condor corregir XX --bloque C --antes "…" --despues "…" --motivo "…"` con
  terminal, frase y firma, que aplique el reemplazo, lo registre firmado y deje vencer la
  aprobación del bloque. Así las correcciones humanas quedan en el mismo régimen que las demás
  decisiones y no hay que editar JSON a mano.

**M-04. Dimensiones "checkpoint" y "workflows" de la revisión adversarial.**
- *Pendiente* en `plan.md` (v2.1, "Pendiente"): sólo corrió la dimensión "guardas".
- Insumos que salieron de leer el código, para que esa revisión los confirme o descarte:
  - *Verificado.* `resumen()` declara `publicado` comparando hashes de `rev["publicacion"]` sin
    verificar su firma, y `condor estado` muestra las decisiones como vigentes sin verificar firmas
    (`condor/estado.py`). Las firmas sólo se chequean dentro de `publicar`, y
    `verificar_firmas` no incluye la firma de la publicación. Un `revision.json` editado podría
    mostrar "publicado" en `condor estado` aunque `publicar` después lo rechazaría. *Propuesta:*
    un `condor verificar XX` que pida la frase y verifique todas las firmas, incluida la de
    publicación, o al menos que `estado` compare la huella de cada decisión con la de
    `revisor.json`.
  - *Verificado.* M-08 y M-09 caen en esta dimensión.
  - *Verificado.* Para "workflows": M-10, M-11 y M-18.

**M-07. Regresiones que faltan.**
- *Pendiente.* Regresión con ground truth del Nº 01. `runs/numero-01/NOTA.md` ya lista los casos:
  C2/C7 (fallo aplicado fuera de su bloque), "hoy jueves" (fecha relativa a la corrida) y
  `ciencia_salud#5` ("núcleo del acuerdo", aceptado con nota en `data/numero-01.revision.json`).
- *Verificado.* `data/regresion-00.json` es de v2 y no tiene `consolidacion`. Los cambios de v2.1 en
  verificar y reconciliar (agrupación de miles, `cifrasAf`, completitud por valor) no se midieron
  de punta a punta contra el Nº 00.
- *Propuesta.* Correr la regresión completa del Nº 00 con v2.1 (unos 50 agentes, en una sesión
  propia y en serie, como pide `CLAUDE.md`), y armar `tests/fixtures/numero-01-gt.json` con
  los tres casos de la retro.

### Después: impacto medio

**M-08. Guarda de cifras sobre copete y título del número.**
- *Verificado.* Ni `condor/estado.py` ni `pipeline/condor.workflow.js` revisan las cifras de
  `meta.copete` ni de `meta.titulo_numero`. La regla "sin cifras que no estén en notas sin riesgo"
  vive sólo en la descripción del schema (`ART_SCHEMA`). `riesgos_tapa` revisa los textos del SVG,
  no los de la portada HTML.
- *Propuesta.* Aplicar la lógica de `riesgos_tapa` (cifras sin respaldo, cifras en riesgo, títulos
  de bloques retirados) también a copete y título, como riesgos de tapa que exijan `--nota`.

**M-19. Actualizar `CLAUDE.md` a v2.1.**
- *Verificado.* `CLAUDE.md` es el archivo de instrucciones que leen los agentes que trabajan en el
  repo, y su sección "Estado al 24/09/2026" sigue describiendo el estado previo a v2.1: "61 tests
  pasan", regresión "3 OK / 3 FALLA", "Nº 01: corrida cortada por límite de sesión" y "6 hallazgos
  sin verificar". `plan.md` (v2.1) y `runs/numero-01/NOTA.md` dicen otra cosa: 93 tests (`uv run
  pytest -q`: 93 passed), Nº 01 publicado, regresión desde el cierre 7/7 y un arreglo aplicado para
  cada hallazgo. Quien llega por primera vez recibe información contradictoria.
- *Propuesta.* Reescribir esa sección con el estado de v2.1 y los pendientes de `plan.md`. Mientras
  tanto, tomar `plan.md` y `runs/numero-01/NOTA.md` como fuente de estado, no `CLAUDE.md`.

**M-10. Paridad de `norm`.**
- *Verificado.* `norm` unifica comillas y guiones en `verificar.workflow.js` y `cierre.workflow.js`,
  pero no en `condor.workflow.js` ni en `reconciliar.workflow.js`. `normalizar_texto` de Python sí
  los unifica (`condor/numeros.py`). `tests/test_paridad_js.py` no incluye `norm` en `FUNCIONES`.
  La guarda de nombres protegidos del estilo usa la versión corta (`pipeline/condor.workflow.js`).
- *Propuesta.* Unificar `norm` en los cuatro archivos, sumarla a `FUNCIONES` y agregar una prueba
  contra `normalizar_texto`.

**M-12. Memoria entre números.**
- *Verificado.* El prompt de Espacio dice "que NO sea el SAOCOM 1A … (ya fue nota en el número
  anterior)" (`pipeline/condor.workflow.js`). Eso era cierto para el Nº 01; para el Nº 02 el número
  anterior cubrió el SAOCOM 1B (`output/numero-01/index.md`).
- *Propuesta.* Un `args.anteriores` con los títulos y temas de los últimos números, generado desde
  `data/numero-*.json`, que usen todos los beats para no repetir.

**M-11. Tests con `node` para las otras etapas.**
- *Verificado.* `tests/test_workflows_js.py` corre cierre, consolidar y el orquestador con semilla.
  No hay tests con `agent` simulado para verificar (cita no literal, completitud, confirmado sin
  url), reconciliar (huérfanas, tope de debates, conflicto sin ancla) ni tapa (puntaje con juez
  faltante, corrección no adoptada).
- *Propuesta.* Sumar esos casos con el mismo arnés (`tests/js/correr_workflow.mjs`).

**M-03. Nombre de la revista en una sola constante.**
- *Pendiente* (`plan.md`, v2.1, "Pendiente").
- *Verificado.* "Cóndor" o "CÓNDOR" aparece 53 veces en 22 archivos de `pipeline/`, `condor/`,
  `scripts/` y `tests/` (`grep -ro 'Cóndor\|CÓNDOR' pipeline condor scripts tests
  --exclude-dir=__pycache__ | wc -l`). Algunos usos son funcionales: el texto
  obligatorio de la tapa (`requeridos` en `tapa.workflow.js`, `_validar_tapa` en `estado.py`) y el
  título por defecto del número (`condor.workflow.js`).
- *Propuesta.* Una constante en `condor/__init__.py` para Python y plantillas, y `args.nombre` para
  los workflows (que no pueden importarla), con un test que falle si queda el nombre escrito a mano
  fuera de esos dos lugares.

**M-06. Presupuesto de tokens por etapa.**
- *Pendiente* (`plan.md`; `plan-resvista-01.md`, §7).
- *Verificado.* El journal del Nº 01 no registra tokens: tiene sólo un evento `launched` inicial y
  `started`/`result` por agente (75 de cada uno), sin tokens
  (`runs/numero-01/journal-wf_74b3799f-f3a.jsonl`). El único consumo medido es el del Nº 00:
  ~765.000 tokens de subagentes (`output/run.log`).
- *Propuesta.* Según la referencia del runtime de Workflows, los scripts tienen un objeto `budget`
  con `spent()`, que devuelve los tokens **de salida** gastados en todo el turno: el pool es
  compartido entre el loop principal y todos los workflows, no es por workflow. Para medir una etapa
  hay que registrar en `meta` la diferencia de `budget.spent()` antes y después de ella, sabiendo
  que no cuenta los tokens de entrada y que incluye todo lo que corre en paralelo en el mismo turno
  (por ejemplo, `verificar` de las secciones mientras se escribe la nota de fondo). `budget.total`
  es el objetivo que quien corre fija para el turno (o `null`), no un tope por etapa. Un tope por
  etapa habría que implementarlo en el script, comparando esas diferencias contra una constante
  propia y mandando al checkpoint lo que no entre, como ya se hace con el tope de debates.

**M-05. Corridas reanudables entre sesiones.**
- *Pendiente* (`plan-resvista-01.md`, §7): `args.desde` con estado intermedio, más general que la
  semilla.
- *Propuesta.* Que el orquestador acepte el resultado de cualquier etapa ya corrida (libro,
  reconciliación, cierre) y arranque desde la siguiente, y un script que lo extraiga del journal
  como hace `scripts/semilla_desde_journal.py`. El riesgo es mezclar etapas de copias distintas del
  pipeline: el estado intermedio debería llevar el hash del `SHA256SUMS` con que se produjo.

### Al final: bajo impacto, esfuerzo bajo

**M-13. Una sola fuente para la línea editorial y los beats.**
- *Verificado.* La línea editorial está en `roles/00-linea-editorial.md` y, resumida a mano, en la
  constante `LINEA` de `pipeline/condor.workflow.js`. Las claves de los beats están en `BEATS` y
  repetidas en `ACENTO` y `SIGLA` de `condor/render.py`.
- *Propuesta.* Un test que compare las claves de `BEATS` con las de `ACENTO`, y un marcador en
  `roles/00` que diga que `LINEA` es su resumen operativo, para revisarlo cuando cambie.

**M-14. Roles que siguen describiendo la v1.**
- *Verificado.* `roles/01-jefe-redaccion.md` habla de dividir el borrador en 3 grupos de
  fact-checking; `roles/03-corrector-estilo.md` dice que el corrector no tiene schema;
  `roles/04-fact-checker.md` describe los 3 fact-checkers; `roles/05-director-arte.md` no menciona
  brief, copete ni dato ancla; `roles/06-editor-digital-cms.md` apunta a `scripts/build_issue.py`.
  El código actual hace otra cosa en los cinco casos.
- *Propuesta.* Actualizarlos a v2.1 o marcar al principio de cada uno qué parte es histórica y cuál
  la reemplaza (`roles/07` a `roles/10`).

**M-15. Plantilla Markdown.**
- *Verificado* en `output/numero-01/index.md`. El copete va seguido de `---` sin línea en blanco,
  y en Markdown eso convierte al copete en un título de nivel 2 (líneas 6-7). Lo mismo pasa con la
  línea de "Fuentes" de la nota de fondo (líneas 23-24). La bajada de la nota de fondo queda pegada
  al primer párrafo, porque `trim_blocks` se come el salto de línea después de `{% endif %}`
  (`condor/templates/issue.md.j2`).
- *Propuesta.* Agregar líneas en blanco en la plantilla y un test que renderice un número de
  prueba y verifique que no hay setext headings.

**M-16. Tope del extractor.**
- *Verificado.* En el Nº 01 corrió la ronda de completitud en 7 de 10 bloques (`extraer+:` en el
  journal): el extractor, con tope de 3 a 12 afirmaciones (`extractPrompt`), deja cifras sin
  cubrir en la mayoría de los bloques.
- *Propuesta.* Subir el tope o sacarlo para la nota de fondo, y medir en la regresión si baja la
  cantidad de rondas sin empeorar la calidad.

**M-17. CMS de v1.**
- *Verificado.* `scripts/build_issue.py` y `scripts/templates/` son el CMS de v1, con el que se armó
  el Nº 00 (`roles/06-editor-digital-cms.md`). El CMS vigente es `condor/render.py`.
- *Propuesta.* Moverlos a `runs/numero-00/` como la "copia congelada" del Nº 00, o marcarlos como
  legado en su docstring.

**M-18. Tope silencioso del arte.**
- *Verificado.* El director de arte recibe `confirmadas.slice(0, 60)` sin `log` de cuántas quedaron
  afuera (`pipeline/condor.workflow.js`). `confirmadas` excluye los bloques con riesgo: en el Nº 01 había
  unas 106 confirmadas de bloques sin riesgo (de 136 en total; `espacio` y `ciencia_salud` tenían
  riesgos), así que unas 46 quedaron afuera sin aviso (recalculado sobre `data/numero-01.json`).
- *Propuesta.* Registrar el recorte con `log`, como el tope de debates, o priorizar las afirmaciones
  `central`.

---

## Documentos relacionados

- [README](../README.md): qué es la revista y cómo trabaja la redacción.
- [Manual técnico](manual-tecnico.md): instalación, comandos y operación.
- [Página del proyecto](index.html).
- Fuentes de este documento: `plan.md`, `plan-resvista-01.md`, `roles/`, `runs/numero-01/NOTA.md`,
  `output/numero-00/notas-del-ensayo.md`, `pipeline/`, `condor/` y `tests/`.
