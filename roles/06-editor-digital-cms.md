# Editor/a digital (CMS) — no es un agente, es código

`scripts/build_issue.py`, Python + Jinja2. Recibe el JSON que devuelve el Workflow
(ya con fact-check aplicado y directivas de arte) y renderiza:

- `output/numero-00/index.md`
- `output/numero-00/index.html` (plantilla dark-mode, mismo lenguaje visual que
  `ia-weekly-report`, pero parametrizada por las directivas del director de arte)

Ninguna decisión editorial se toma acá — si algo está mal en el contenido, el
problema está upstream (en el fact-checker o el corrector), no en esta capa. Esto
refleja la separación real entre "redacción" (juicio editorial) y "producción"
(ejecución mecánica) que existe en cualquier revista con un CMS real.
