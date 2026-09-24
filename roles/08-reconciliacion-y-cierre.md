# Reconciliación cruzada, debate, consolidación y editor de cierre (v2.1)

El problema que resuelve: en el Nº 00 la **misma cifra** (Oracle, 300.000 GPUs) quedó
"confirmada" en la sección de Hardware y "no verificable" en la nota de fondo. Cada
fact-checker miraba su bloque; nadie comparaba bloques entre sí.

## Detección — `pipeline/etapas/reconciliar.workflow.js`
Tres detectores independientes, cuyos hallazgos se unen y deduplican:
1. **Código** (determinístico): cifras de la nota de fondo que no aparecen en ninguna sección
   (*huérfanas*); pares de afirmaciones de distintos bloques con la misma cifra y entidad pero
   **veredictos distintos**.
2. **Reconciliador "hechos"**: agrupa afirmaciones del mismo hecho entre bloques; busca valores
   distintos, veredictos distintos y afirmaciones huérfanas.
3. **Reconciliador "cronología"**: fechas, rangos, duraciones derivadas ("seis semanas" vs. el
   rango de fechas), porcentajes y comparaciones que no cierran.

Los reconciliadores también juzgan los candidatos del código (descartan falsos positivos, que
quedan registrados). Anclan cada conflicto por afirmación **y por bloque**: una inconsistencia sin
afirmación extraída igual llega al debate. Si no responde ningún reconciliador, la nota de fondo
queda bloqueada para decisión humana (no hubo cruce). Una cifra huérfana viaja como dato
estructurado (`cifras`) hasta el cierre y el checkpoint. Toda afirmación `contradicho` entra como conflicto. Tope de debates: 10;
lo que exceda va al checkpoint como "sin resolver" (y queda logueado, sin topes silenciosos).

Además devuelve **grupos** (mismo hecho en distintos bloques), que el checkpoint usa para saber
qué bloques dependen de cuáles.

## Debate (por conflicto)
Patrón con mejor evidencia en la investigación previa (*Debating Truth*, 2026):
- **Defensor** (modelo de la redacción): sostiene la versión publicada, con evidencia leída.
- **Escéptico** (modelo verificador): intenta refutarla.
- **Juez**: decide `mantener` / `corregir` / `retirar` / `matizar` / `sin_consenso`, y lista
  *todas* las afirmaciones afectadas (si el mismo dato está en la sección y en la nota de
  fondo, se corrige en los dos lados). `valor_correcto` es sólo el dato, corto ("2 de julio de
  2026"); la explicación va en `razonamiento`.

## Consolidación — `pipeline/etapas/consolidar.workflow.js` (v2.1)
Cada juez falla sobre un conflicto sin ver los otros, así que dos fallos pueden tocar las mismas
afirmaciones y contradecirse (en la regresión del Nº 00: C3 corregía la duración a "cuatro semanas" y
C4 a "seis semanas"). Entre reconciliar y cierre:
- el código arma componentes conexos (union-find) de los fallos `corregir`/`retirar`/`matizar` que
  comparten `afirmaciones_afectadas`;
- por cada componente con 2 o más fallos, un **juez de consolidación** recibe los fallos, la evidencia
  de los debates, las afirmaciones y los textos, y devuelve **una** resolución (`K1`, `K2`…) con
  `conflictos_cubiertos`. Si la evidencia no alcanza para elegir entre versiones: `sin_consenso`;
- guardas: la resolución tiene que cubrir todas las afirmaciones del componente y no puede traer
  cifras que no estén en los fallos, las evidencias o los textos. Si no pasa (o el juez no responde),
  quedan los fallos originales y una guarda bloqueante `consolidacion_caida` en sus bloques.

Un conflicto cuenta como resuelto si tiene fallo propio o si está en los `conflictos_cubiertos` de uno
consolidado (`conFallo` del orquestador, `indice_resoluciones()` del checkpoint). Los fallos
reemplazados quedan en `consolidacion.reemplazadas` y la revisión muestra "Consolidado en K1".

## Editor de cierre — `pipeline/etapas/cierre.workflow.js`
Aplica los fallos con el mínimo cambio. Guardas en código después de cada edición:
- lo retirado no puede seguir en el texto (ni literal ni sus cifras propias),
- el valor corregido tiene que aparecer y el viejo desaparecer. Como los jueces escriben prosa, se
  exigen sólo las cifras que están a la vez en `valor_correcto` y en `redaccion_sugerida` y no son
  valores viejos; los ids del libro (`feature#17`) no cuentan como cifras. Un valor viejo no numérico
  (un nombre, "2 de julio") tiene que desaparecer, o al menos cambiar el fragmento,
- matizar tiene que cambiar el texto e incorporar algo de la redacción sugerida,
- las cifras de una afirmación son las de su `valor` que están en su cita (una cita con dos datos no
  arrastra cifras ajenas),
- no puede aparecer ninguna cifra que no esté en el original o en la corrección,
- las cifras que el fallo manda retirar o corregir (las de la huérfana y las de las afirmaciones
  afectadas, aunque estén en otro bloque) no pueden seguir en el texto.

Un "retirar" sin afirmación ni cifra con la que comprobarlo no se da por aplicado: va al checkpoint.
Si falla: **una ronda de auto-reparación** con la lista de errores; si vuelve a fallar, se
conserva el texto original, las afirmaciones afectadas quedan `no_aplicado` (estado de riesgo: no
cuentan como verificadas ni pueden llegar a la tapa) y el bloque va al checkpoint como bloqueante.
Nunca se publica una corrección a medio aplicar.

Si una etapa entera falla (un workflow hijo), el orquestador sigue con un resultado neutro y deja
una guarda bloqueante en cada bloque afectado: la corrida no se cae y nada pasa sin revisión.
