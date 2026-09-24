# Cóndor — revista de IA producida por una redacción multi-agente

Revista de IA, tecnología y ciencia (foco Argentina/LatAm) escrita por agentes orquestados con
Workflows de Claude Code, con verificación afirmación por afirmación, reconciliación cruzada entre
notas, tapas SVG y un **checkpoint humano** antes de publicar. Diseño completo en `plan.md` (v2.1 arriba, después v2 y v1) y por rol en `roles/`.

## Mapa
- `pipeline/condor.workflow.js` — orquestador de un número. Etapas hijas en `pipeline/etapas/`:
  `verificar` (libro de afirmaciones), `reconciliar` (detectores + 2 lentes + debate), `consolidar`
  (une fallos que comparten afirmaciones), `cierre` (aplica fallos con guardas), `tapa` (3
  ilustradores + jurado).
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
Plan vigente: `plan-resvista-01.md`. **Sesión A hecha** (Fases 1-3):
- v2.1: etapa `consolidar` (entre reconciliar y cierre), guarda de `cierre` con `valor_correcto` en
  prosa (requeridas = sig(vc) ∩ sig(rs) − viejas; `sinIds` saca `feature#17`), `cifrasAf` (cifras por
  valor), agrupación de miles siempre significativa, corregir nombres/meses y matizar exigen cambiar
  el texto, `importar` desenvuelve el `.output`, `args.semilla` en el orquestador. Los 6 hallazgos de
  la dimensión "guardas" eran reales y están arreglados.
- 91 tests (`uv run pytest -q`), incluidos `tests/test_workflows_js.py` (corre etapas con `node` y un
  `agent` simulado: `tests/js/correr_workflow.mjs`) y `tests/test_paridad_js.py`.
- GT del Nº 00 corregido (Oracle 300k GPUs correcto; DSEwiki 24/5-22/6, 17.000 de ~18.000).
  Regresión desde el cierre (`scripts/generar_regresion.py --desde-cierre` →
  `pipeline/regresion-00-cierre.workflow.js`, 9 agentes): **7/7 OK**, 6/6 resoluciones aplicadas.
- `runs/numero-01/pipeline/` recongelado (ver `runs/numero-01/NOTA.md`); semilla en
  `runs/numero-01/semilla-investigacion.json` (8 secciones + nota de fondo; Espacio en vivo).

**Nº 01 publicado** (24/09/2026, `output/numero-01/index.html`): run `wf_74b3799f-f3a`, 75 agentes;
retro en `runs/numero-01/NOTA.md`. Después de la corrida se arreglaron en `pipeline/` (no en la copia
congelada del Nº 01): cierre aplica cada fallo sólo en los bloques de sus afirmaciones (bug C7→Espacio)
y el director de arte escribe un `copete` para lectores (la portada ya no publica `concepto_tapa`).
93 tests.

Pendiente: repensar el nombre de la revista (hoy "Cóndor"; al cambiarlo, dejarlo en una sola
constante); D1 (restaurar Oracle >300.000 GPUs en el Nº 00 publicado: decisión humana por el
checkpoint); fechas relativas ("hoy jueves") en notas de beats en vivo; dimensiones "checkpoint" y
"workflows" de la revisión adversarial.
