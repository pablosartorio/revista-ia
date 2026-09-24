# Fact-checkers (3 agentes adversariales, en paralelo)

Patrón: **verificación adversarial independiente** — cada fact-checker recibe ~3 de
los 10 bloques de contenido (9 secciones + feature) y para cada afirmación con dato
duro (cifra, fecha, benchmark, nombre propio) hace su propia búsqueda para
confirmarla o refutarla. No confía en la fuente citada por el corresponsal: la
verifica de cero.

Instrucción explícita (para evitar sesgo de confirmación): *"Tu trabajo es intentar
tirar abajo cada afirmación, no confirmarla. Si no podés verificarla de forma
independiente en 2-3 búsquedas, marcala como 'no_verificable', no como
'confirmada' por default."*

Salida por afirmación: `confirmado` / `no_verificable` / `contradicho`, con nota
breve. Un ítem con una afirmación central marcada `contradicho` se excluye del
ensamblado final (lo decide la lógica del script, no el fact-checker).

Esto es el equivalente al patrón "adversarial verify" de auditorías de código: N
verificadores independientes, sesgo hacia refutar antes que confirmar.
