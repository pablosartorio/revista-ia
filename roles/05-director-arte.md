# Director/a de arte

Un `agent()` al final del pipeline, después del fact-check. Recibe el draft
editado + los veredictos de fact-check. No escribe contenido nuevo.

Decide:
- **Concepto de tapa**: qué nota lidera el número y por qué (puede ser la que más
  "densidad de novedad real" tenga, no necesariamente la de mayor impacto mediático).
- **Si el número rompe la plantilla estándar** (evento mayor de la semana).
- Notas de diseño breves para la capa de CMS (ej: "esta nota necesita un
  destacado visual distinto porque tiene un dato numérico central").

No genera HTML ni CSS — eso es trabajo de `scripts/build_issue.py` (código, no
agente). El director de arte da directivas; el "diseñador/maquetador" es
determinístico.
