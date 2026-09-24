# Tapa: ilustradores, jurado y ronda de corrección (v2)

`pipeline/etapas/tapa.workflow.js`. Sin GPU no hay difusión local, así que las tapas son
**SVG vectoriales** dibujados por agentes, con `rsvg-convert` para rasterizar y las fuentes
instaladas (Archivo Black, Inter, EB Garamond…).

## Ilustradores (3, en paralelo, enfoques distintos)
- **A · editorial tipográfica**: la tipografía resuelve la tapa.
- **B · metáfora visual**: ilustración geométrica de la metáfora del brief.
- **C · data-driven**: visualiza el *dato ancla* del brief, que tiene que ser una afirmación
  **confirmada tal como se publica** (no "corregida": su valor viejo no puede llegar a la tapa) de
  un bloque sin ningún riesgo abierto (lo chequea el código; si no, la tapa no lleva cifras). Las
  líneas de tapa también salen sólo de bloques sin riesgos.

Cada uno escribe el SVG, lo valida con `condor tapa-validar` (sin scripts, sin recursos externos,
textos obligatorios "Cóndor" y el número), lo rasteriza con `condor tapa-render` (1200 px +
miniatura de 300 px) y **mira los PNG** para corregir texto cortado, superposiciones o
problemas de legibilidad. Hasta 3 iteraciones. Las líneas de tapa sólo pueden ser títulos de
notas reales del número.

## Jurado (2 jueces, lentes distintas)
- **editorial**: ¿comunica el concepto? ¿promete sólo lo que el número tiene?
- **visual**: legibilidad en miniatura, contraste, jerarquía, errores de render.
Puntúan 5 criterios de 1 a 10; **el puntaje lo calcula el código** (promedio sobre los jueces que
efectivamente puntuaron: un puntaje faltante no cuenta como cero y queda una guarda). Desempata la
lente editorial. Si no responde ningún juez, no se sugiere ganador.

## Ronda de corrección
El ganador corrige los problemas concretos que marcaron los jueces (en un archivo nuevo, sin
pisar el original) y un juez compara ambas versiones: sólo se adopta la corregida si es
claramente mejor y sin regresiones.

La elección final es humana: `condor tapa XX <candidato>` (ver `10-checkpoint-humano.md`), y el
checkpoint vuelve a cruzar la tapa contra lo que efectivamente se publica.
