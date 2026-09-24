# Jefe/a de redacción

**No es un agente separado** — es la lógica del script de Workflow (y, en última
instancia, yo como orquestador leyendo el resultado). Sus responsabilidades se
implementan como código determinístico, no como prompt:

- Reparte los 9 beats en paralelo (fase "Investigación").
- Decide cuándo hay barrier (la nota de fondo espera a los 9 reportes).
- Ensambla el draft (concatenación + orden, no reescritura de contenido).
- Divide el draft en 3 grupos para fact-checking en paralelo.
- Si un fact-checker marca "contradicho", ese ítem se excluye del ensamblado final
  o se marca explícitamente como disputado — no se oculta el problema.
- Entrega el material final (post fact-check) a dirección de arte.
- Corta contenido si no llega a estándar (ej: un beat que no encontró nada
  verificable esta semana se omite, no se rellena con relleno).

Reporta, en el organigrama humano, a la dirección editorial (línea fija) y en
términos de "negocio" al límite de agentes/tokens que yo (el operador humano) fije
por número.
