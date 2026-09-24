# Cóndor — revista de IA producida por una redacción multi-agente

Revista de IA, tecnología y ciencia (foco Argentina/LatAm) escrita por agentes orquestados con
Workflows de Claude Code, con verificación afirmación por afirmación, reconciliación cruzada entre
notas, tapas SVG y un **checkpoint humano** antes de publicar. Diseño completo en `plan.md` (v2
arriba, v1 abajo) y por rol en `roles/`.

## Mapa
- `pipeline/condor.workflow.js` — orquestador de un número. Etapas hijas en `pipeline/etapas/`:
  `verificar` (libro de afirmaciones), `reconciliar` (detectores + 2 lentes + debate), `cierre`
  (aplica fallos con guardas), `tapa` (3 ilustradores + jurado).
- `pipeline/regresion-00.workflow.js` — regresión sobre el Nº 00 original (generada por
  `scripts/generar_regresion.py`; evaluar con `scripts/evaluar_regresion.py data/regresion-00.json`).
- `condor/` — paquete Python: `estado.py` (checkpoint), `render.py` + `templates/`, `importar.py`,
  `numeros.py` (debe coincidir con `canonNum` de los .js), `svg.py`, `cli.py` (`uv run condor …`).
- `runs/numero-XX/pipeline/` — copia congelada del pipeline con la que se corrió cada número
  (`args.etapas` apunta ahí), con `SHA256SUMS`.
- `data/` — números (`numero-XX.json`), decisiones de revisión (`numero-XX.revision.json`),
  resultado de la regresión. `output/` — borradores, paquetes de revisión y números publicados.

## Reglas
- Python siempre con `uv` (`uv run pytest -q`, `uv run condor …`); nunca `pip` directo.
- **El checkpoint es humano.** Claude nunca aprueba, retira, elige tapa ni publica: los comandos
  exigen TTY y la frase secreta del revisor, y las decisiones van firmadas. No intentar sortearlo.
- Commits y push sólo cuando se pidan. No leer los `.output` de tareas de agentes enteros (son
  enormes): usar el `journal.jsonl` del workflow o inspeccionar tamaño/primeros bytes.
- Correr los workflows grandes **en serie**: en paralelo agotan el límite de sesión.
- Chequeo de sintaxis de un workflow: envolver el script en una `AsyncFunction` (ver historia).

## Estado al 24/09/2026 y próximos pasos
Hecho: arquitectura v2 + arreglos de la primera revisión adversarial (firma HMAC de decisiones,
lock, tapa atada al SVG aprobado, riesgos de tapa, `no_aplicado`, cifras de huérfanas, hijo()
con resultado neutro, etc.). 61 tests pasan.

Regresión del Nº 00 (`data/regresion-00.json`): 3 OK / 3 FALLA, pero:
- **El ground truth tiene 2 casos mal** (verificado leyendo las fuentes):
  - Oracle **sí** desplegó >300.000 GPUs en Q1 FY27 (CryptoBriefing 11/09/2026: "deployed more
    than 300,000 GPUs"). El Nº 00 publicado retiró ese dato correcto: pendiente decidir si se restaura.
  - DSEwiki (collusion.wiki): primera escritura 24/5 (el 11/5 fue otra wiki), "abruptly stop" el
    22/6, sólo ediciones sueltas 1-2/7; ~17.000 ediciones en DSEwiki sobre ~18.000 en total.
- Fallas reales del pipeline:
  1. La guarda de `cierre` exige todas las cifras de `valor_correcto`, pero los jueces escriben
     prosa ahí (incluye la cifra vieja) → imposible de cumplir. Arreglo: requeridas =
     sig(valor_correcto) ∩ sig(redaccion_sugerida) − cifras viejas; ignorar ids tipo `feature#17`;
     y pedir en RULING_SCHEMA un `valor_correcto` corto.
  2. Dos fallos sobre las mismas afirmaciones se contradicen (C3 "cuatro semanas" vs C4 "seis
     semanas"). Arreglo: etapa `consolidar` entre reconciliar y cierre (componentes de fallos que
     comparten afirmaciones → un juez de consolidación; `conflictos_cubiertos` en la resolución,
     que estado.py/render/`conFallo` deben respetar).
  3. `evaluar_regresion.py`: sumar `no_aplicado` a RIESGO y actualizar los casos del GT.

Nº 01: corrida cortada por límite de sesión (28/51 agentes). Retomar con `resumeFromRunId`
sólo funciona dentro de la misma sesión; en una sesión nueva, relanzar desde
`runs/numero-01/pipeline/condor.workflow.js` (actualizando antes la copia con los arreglos) con
args `{numero:"01", fecha_larga:"23 de septiembre de 2026", semana_iso:"2026-W39",
ventana:"14 al 23 de septiembre de 2026", raiz:"/home/psartorio/revista-ia",
modelo_verificador:"sonnet", ciudad_espacio:"Bariloche", etapas:".../runs/numero-01/pipeline/etapas"}`.
Después: `uv run condor importar <resultado>` (el `.output` del workflow es un envoltorio
`{summary, logs, result}`: importar `result`) → `uv run condor revision 01` → checkpoint humano.

Segunda revisión adversarial: sólo corrió la dimensión "guardas"; 6 hallazgos sin verificar
(significativa() trata "2.000"/"1.950" como años; cifras de la cita completa en vez del valor;
corregir de nombre/mes y matizar pasan sin tocar el texto; completitud cubre cifras por citas
ajenas; bajada de secciones en estilo; nombres protegidos toman valores viejos). Faltan las
dimensiones "checkpoint" y "workflows".
