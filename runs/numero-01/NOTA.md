# Nº 01 — notas de la corrida

## Recongelado del pipeline (24/09/2026)

La primera corrida (`wf_c573cb47-18c`, 23/09/2026) se cortó por límite de sesión: 52 agentes
lanzados, 28 respondieron, 23 cayeron, sin resultado final. Su journal quedó en
`corrida-interrumpida/journal.jsonl` y de ahí salió `semilla-investigacion.json` (8 corresponsalías
y la nota de fondo; Espacio se rehace en vivo porque sus pasos eran "esta semana" respecto del 23/09).

Como esa corrida no produjo número, se reemplazó `pipeline/` por la versión v2.1:
- etapa nueva `consolidar` (fallos que comparten afirmaciones → una resolución);
- guarda de `cierre` que acepta `valor_correcto` en prosa e ignora ids del libro (`feature#17`);
- cifras por valor de la afirmación, agrupación de miles siempre significativa, `corregir` de
  nombres/meses y `matizar` exigen cambiar el texto, completitud por valor, bajada de secciones fuera
  de la guarda de estilo, nombres protegidos sin valores corregidos;
- `args.semilla` en el orquestador.

Validación antes de congelar: 91 tests; regresión desde el cierre sobre el Nº 00
(`data/regresion-00-cierre.json`, run `wf_7acbbbf3-b25`, 9 agentes): 7/7 casos OK con el ground truth
corregido, 6/6 resoluciones aplicadas (C1+C3+C4 consolidados en K1), 0 guardas bloqueantes.

SHA256 del `SHA256SUMS` anterior: `3df09ff139ea3ae26afc08f846cee672e680dcc61235d73d76abd25884b4547e`
```
41b2c69708d14d47729520d3cf253b7a7944ef3bbaf05ef93e512491b84e4ac6  condor.workflow.js
749f5b1e41fbc6b1f3c64f61b0054e5f6d18591d56e681a9f54090e14d4a25a1  etapas/cierre.workflow.js
52b2ddbe0d8aedc75b590df354214890250f05cbf4b1aef63203f0eaa4f90c48  etapas/reconciliar.workflow.js
a4569ad6f62eecceb00a0818c5015934a3640bae28014b11bff4e68424fb33c2  etapas/tapa.workflow.js
abacfd9edd973bf5006405d005b6247ef094286d613b1a136df2f7413bcb4808  etapas/verificar.workflow.js
```
SHA256 del `SHA256SUMS` nuevo: `fe79963e34816af4b953c1c3bc5cff4604fe1e14c03eae5ea081271a8d6e87f3`
