# Checkpoint humano (v2)

**Rol humano, no agente.** Es la única etapa que no puede ejecutar la redacción: el código lo
impide (`condor/estado.py`).

## Ciclo de vida de un número
`borrador` → `en_revision` → `aprobado` → `publicado`

```
uv run condor clave --revisor "Nombre"                 # UNA vez: tu frase secreta de revisor/a
uv run condor importar <resultado-del-workflow>.json   # -> data/numero-XX.json  (borrador)
uv run condor revision XX                              # paquete de revisión + borrador.html
uv run condor estado XX                                # qué falta
uv run condor aprobar XX --todo --revisor "Nombre"     # aprueba SÓLO bloques sin riesgos
uv run condor aprobar XX --bloque C --nota "..." --revisor "Nombre"   # bloque con riesgos
uv run condor retirar XX --bloque C --motivo "..." --revisor "Nombre"
uv run condor tapa XX B --revisor "Nombre"             # (--nota si la tapa tiene riesgos)
uv run condor publicar XX --revisor "Nombre"           # -> output/numero-XX/index.html
```

## Reglas que impone el código
- **Decisiones firmadas.** Cada aprobación, retiro, elección de tapa y publicación se firma
  (HMAC) con una clave derivada de tu frase secreta (scrypt). La frase se tipea en la terminal y
  no se guarda en ningún lado; en `~/.config/condor/revisor.json` sólo queda un verificador.
  `publicar` vuelve a pedir la frase y **rechaza cualquier decisión sin tu firma**: un agente puede
  escribir en `revision.json`, pero no puede fabricar una decisión que se publique.
- **Terminal interactiva** + tipear el número del ejemplar: segunda barrera, contra errores de dedo.
- **Límite honesto:** un agente que corre con tu mismo usuario Unix podría, con intención, reemplazar
  tu clave por una suya o modificar el código de `condor/`. Eso no se puede impedir desde adentro del
  proceso; lo que sí garantiza el diseño es que no puede pasar *por accidente* ni sin dejar rastro
  (la huella de la clave queda en cada decisión).
- **Aprobación por hash de contenido.** Se hashea todo lo publicable del bloque (texto, fuente,
  sección) y las afirmaciones que muestra la caja "Cómo verificamos". Si algo cambia después de
  aprobarlo, la aprobación vence sola. Los riesgos aceptados se identifican también por contenido:
  si el mismo id pasa a describir otra cosa, vence.
- **Lecturas consistentes.** Cada acción valida antes de pedir la frase y vuelve a leer y validar
  después, bajo un lock: dos decisiones simultáneas no se pisan.
- **Riesgos aceptados explícitamente.** Un bloque con riesgos (afirmación no verificable o
  contradicha, conflicto sin consenso, corrección no aplicada, cifra sin trazabilidad,
  dependencia de un bloque retirado) no entra con `--todo`: exige `--bloque` + `--nota`, y la
  nota queda registrada. Si después aparece un riesgo **nuevo** (p. ej. se retira otro bloque
  del que este depende), la aprobación vence.
- **Defensa en profundidad:** el checkpoint recalcula por su cuenta que toda cifra publicada
  venga de la investigación original o de una corrección con evidencia, y que lo retirado no
  siga en el texto — aunque las guardas del workflow hayan pasado.
- **La tapa es parte de la decisión.** Elegirla guarda una copia con nombre por contenido
  (`tapa/elegida-<sha>.svg`); se publica esa copia y el PNG se genera desde ella al publicar (nunca
  se copia un PNG de los agentes). Elegir la tapa también aprueba el título del número y el concepto:
  si cambian, la elección vence. Riesgos de tapa: cifras que no están en ninguna nota publicada o que
  sólo respaldan afirmaciones sin verificar, dato ancla de un bloque retirado, línea de tapa que anuncia
  una nota retirada. Con riesgos, elegirla exige `--nota`.
- **Publicar** exige: todas las firmas válidas, todos los bloques decididos con aprobación vigente,
  tapa vigente y al menos un bloque aprobado. Queda un registro firmado con revisor, fecha, hashes
  publicados y hash de cada archivo generado. Si después se retira un bloque o cambia algo, el
  número deja de figurar como `publicado` y `condor estado` avisa que hay que volver a publicar.

## Qué mira la persona
`output/numero-XX/revision.html`: por bloque, los riesgos, el diff contra la investigación
original, el libro de afirmaciones con la evidencia de cada una; los conflictos entre notas con
el debate completo y el fallo del juez; las correcciones aplicadas; el contexto omitido; las
guardas disparadas; y los candidatos de tapa con los puntajes del jurado.
