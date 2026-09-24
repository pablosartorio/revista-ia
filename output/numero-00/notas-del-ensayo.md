# Notas del ensayo — Número 00 (piloto)

**Corrida:** Workflow `condor-numero-00`, run `wf_bb65a6bd-a67`, 12-13 de septiembre de 2026.
**Stats:** 15/15 agentes completados sin errores · ~765.000 tokens de subagentes · 272 usos de herramienta · ~27,5 min de wall-clock.

## Qué funcionó

- Las 9 corresponsalías en paralelo entregaron ítem con fuente real y verificable en el primer intento (0 reintentos salvo un reinicio interno de `seccion:hardware` que el propio framework manejó solo).
- La corresponsalía de Espacio (MCP `patagonia-espacial`, sin búsqueda web) funcionó de punta a punta: encontró SAOCOM 1A, calculó pasadas visibles sobre Bariloche con horarios y elevación, y conectó el dato con INVAP/CONAE — exactamente el objetivo de tener una fuente "data-driven" además de las 8 basadas en web.
- El fact-check adversarial (3 agentes en paralelo, "default a no_verificable") marcó **9 de 9 secciones como "confirmado"** tras verificación independiente (no solo re-chequear la fuente citada, sino buscar de cero).
- El director de arte usó los veredictos de fact-check para decidir la nota destacada — explícitamente excluyó la nota de fondo (con verdict "no_verificable") de ser la tapa, tal como estaba previsto en el diseño.

## Lo más interesante: el fact-check se contradijo a sí mismo

El mismo dato (Oracle: 300.000 GPUs y 850 MW desplegados en el trimestre) aparece dos veces en el número: una vez tal cual en la sección de Hardware, y otra vez parafraseado dentro de la nota de fondo. **El fact-checker del grupo 1 lo confirmó** citando DataCenterDynamics, Tech Times, Seeking Alpha e InfotechLead. **El fact-checker del grupo 3 (que revisó la nota de fondo) no lo pudo confirmar** — no encontró esas cifras en sus propias búsquedas — y por eso marcó todo el bloque de la nota de fondo como "no_verificable".

Es el mismo hallazgo que había señalado la investigación previa (caso dacharycarey.com): la verificación automática de IA-sobre-IA no es determinística ni completa — dos pasadas independientes sobre el mismo hecho, con el mismo objetivo, llegaron a veredictos distintos. Confirma por qué el número lleva la advertencia de "borrador, no publicación" en el pie: el fact-check bajó el riesgo, no lo eliminó.

## Lo que un humano debería revisar antes de llamar a esto "publicado"

1. La atribución del hallazgo de DseWiki al "Nightingale Collective" — ningún fact-checker pudo confirmar ese nombre de forma independiente.
2. Las cifras exactas de Oracle citadas en la nota de fondo (300.000 GPUs / 850 MW / 73%) — confirmadas en la sección de Hardware, no confirmadas en la nota de fondo; conviene cotejar cuál redacción es más precisa antes de dejarlas ambas en el mismo número.
3. La sección `argentina` generó una nota del sistema: el clasificador de seguridad automático que revisa el comportamiento de los subagentes no estuvo disponible para ese caso puntual. Revisé el contenido a mano — no encontré nada problemático (es cobertura geopolítica sobre data centers, sin datos sensibles ni contenido dañino) — pero lo dejo registrado acá por transparencia.

## Cierre (13/09): correcciones aplicadas

Se lanzó un agente de verificación dedicado (no parte del pipeline original) específicamente
sobre los dos puntos más dudosos del número. Resultado y correcciones:

- **Oracle "300.000 GPUs"**: NO se pudo confirmar en ninguna fuente primaria ni especializada
  (se buscó explícitamente el dato, cruzando Reuters/Bloomberg/DCD/Tech Times/Seeking Alpha/
  InfotechLead). Se **retiró** la cifra del título y del cuerpo de la sección Hardware y de la
  nota de fondo, con una nota de "Corrección editorial" visible en el número. El dato de
  **850 MW sí quedó re-confirmado** de forma independiente (InfotechLead, 11/09/2026).
- **"Nightingale Collective"**: confirmado como nombre correcto del grupo (liderado por Sydney
  Von Arx), vía The Hacker News y AIWeekly — el nombre NO era el problema.
- **Rango de fechas del incidente DSEwiki**: la redacción original decía "11 de mayo al 22 de
  junio de 2026"; el rango real reportado por las fuentes es **11 de mayo al 2 de julio de
  2026** (casi 8 semanas, no 6/42 días como decía el texto original). Corregido en la sección
  Safety y en la nota de fondo. Se sumó además precisión del dataset (14.666 edits en 4.584
  páginas, 3.103 nombres de agente) que no estaba en la redacción original.
- **Pentágono-OpenAI**: por pedido explícito del director de arte (que lo señaló al revisar
  el fact-check), se incorporó al cuerpo de la sección Política que OpenAI niega haber
  aceptado la cláusula de "tasas de rechazo mínimas" tal como aparece en el documento
  filtrado — el texto original la presentaba como hecho consumado sin esa contraparte.

**Nota sobre el proceso de cierre en sí**: la verificación de "300.000 GPUs" tuvo dos
resultados distintos según qué tan a fondo se buscó — el fact-checker original del pipeline
(grupo 1) dijo haber confirmado esa cifra citando un titular de DataCenterDynamics; una
segunda pasada de verificación, dedicada y más profunda, no la encontró en ningún lado y
la mandó a retirar. Es el mismo patrón de "brecha de verificación" que ya había aparecido
entre secciones (ver arriba) — ahora también apareció **entre dos rondas de chequeo del
mismo hecho**. Ninguna cantidad de fact-checking automático en una sola pasada garantiza
que el resultado sea estable; conviene tratarlo como reductor de riesgo, no como garantía.

Con estas correcciones aplicadas, el número 00 queda cerrado y revisado a mano en los
puntos que el propio pipeline señaló como dudosos.
