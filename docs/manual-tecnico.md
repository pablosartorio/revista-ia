# Manual técnico de Cóndor

Este manual explica cómo producir y publicar un número de Cóndor de punta a punta: instalar el
entorno, correr la redacción multi-agente, importar el resultado, pasar el checkpoint humano y
publicar. Está pensado para alguien técnico que tiene que operar el sistema.

Para entender qué es la revista y cómo trabaja la redacción, empezá por el [README](../README.md).
Las razones detrás de la arquitectura están en [Decisiones y mejoras](decisiones-y-mejoras.md). El
diseño completo está en [`plan.md`](../plan.md) (v2.1 arriba) y en
[`plan-resvista-01.md`](../plan-resvista-01.md), y cada rol tiene su ficha en [`roles/`](../roles/).

> **Regla de oro.** El checkpoint es humano. Ningún agente, Claude incluido, aprueba, retira, elige
> tapa ni publica. Los comandos que registran decisiones exigen una terminal interactiva y la frase
> secreta de quien revisa, y las decisiones van firmadas con HMAC. No intentes sortearlo.

## Contenido

1. [Requisitos e instalación](#1-requisitos-e-instalación)
2. [Mapa del repositorio](#2-mapa-del-repositorio)
3. [El ciclo de un número en una página](#3-el-ciclo-de-un-número-en-una-página)
4. [Producir un número](#4-producir-un-número)
5. [Importar y armar la revisión](#5-importar-y-armar-la-revisión)
6. [Checkpoint humano](#6-checkpoint-humano)
7. [Herramientas de tapa](#7-herramientas-de-tapa)
8. [Regresión sobre el Nº 00](#8-regresión-sobre-el-nº-00)
9. [Tests](#9-tests)
10. [Formatos de datos](#10-formatos-de-datos)
11. [Solución de problemas](#11-solución-de-problemas)
12. [Referencia rápida](#12-referencia-rápida)

---

## 1. Requisitos e instalación

| Qué | Para qué | Versión / nota |
|---|---|---|
| [uv](https://docs.astral.sh/uv/) | entorno Python, dependencias y todos los comandos (`uv run …`) | probado con uv 0.11.8 |
| Python | paquete `condor` y scripts | `>=3.12` (`pyproject.toml`); `.python-version` fija `3.12` |
| Claude Code con Workflows | corre la redacción (`pipeline/*.workflow.js`) | el Workflow lo lanza Claude desde una sesión |
| MCP `patagonia-espacial` | corresponsalía de Espacio y su verificación (`listar_satelites`, `donde_esta`, `proximos_pasos`) | no viene en el repo: se registra a nivel usuario y tiene que estar conectado en la sesión que lanza el workflow ([ver abajo](#el-servidor-mcp-patagonia-espacial)) |
| `rsvg-convert` (librsvg) | rasterizar tapas SVG a PNG (`condor tapa-render` y `condor publicar`) | probado con 2.61.3 |
| Fuentes tipográficas | que las tapas se vean como se diseñaron | las que acepta `condor/svg.py`: Inter, Inter Display, Archivo, Archivo Black, EB Garamond, Lato, Fira Code, DejaVu, Liberation |
| Node.js | tests que corren los workflows con un runtime simulado y chequeo de sintaxis | probado con v22; sin `node`, esos tests se saltean |

Python usa siempre `uv`. Nunca instales con `pip` directo.

### Instalación

```bash
git clone https://github.com/pablosartorio/revista-ia.git
cd revista-ia
uv sync            # crea .venv con jinja2, defusedxml y el grupo dev (pytest)
uv run pytest -q   # tienen que pasar los 93 tests
uv run condor --help
```

`uv sync` instala el paquete `condor` en modo proyecto (`[tool.uv] package = true`), así que
`uv run condor …` funciona desde la raíz del repo. Los ilustradores de tapa lo invocan con
`uv run --project <raiz> condor …`, así que el repo tiene que estar sincronizado antes de correr un
número.

### Rutas de los ejemplos

Los ejemplos usan `/home/psartorio/revista-ia`, la ruta del clon con el que se produjo el Nº 01.
Reemplazala por la ruta absoluta de tu clon (`pwd` en la raíz del repo). En las tablas de `args`
aparece como `<raiz>`. `raiz` y `etapas` tienen que ser rutas absolutas.

La carpeta donde Claude Code guarda el journal de un workflow se nombra a partir de esa ruta, con
cada `/` cambiada por `-`:

```
~/.claude/projects/<tu ruta con / cambiadas por ->/<sesión>/subagents/workflows/<runId>/journal.jsonl
```

Para `/home/psartorio/revista-ia` queda `~/.claude/projects/-home-psartorio-revista-ia/…`.

### El servidor MCP `patagonia-espacial`

El servidor `patagonia-espacial` no está en este repo y el repo no trae `.mcp.json`. Es un servidor
MCP stdio que se registra a nivel usuario en Claude Code, apuntando al proyecto donde lo tengas:

```bash
claude mcp add --scope user patagonia-espacial -- uv run --directory <ruta del servidor> patagonia-espacial
claude mcp list    # tiene que figurar patagonia-espacial conectado
```

Dentro de una sesión también podés mirarlo con `/mcp`. Lo usan dos agentes: la corresponsalía de
Espacio (`pipeline/condor.workflow.js`) y su verificador (`pipeline/etapas/verificar.workflow.js`).
Los dos tienen prohibida la búsqueda web, así que sin el MCP la nota de Espacio sale sin datos
verificables o no sale. Si no está conectado tenés dos opciones: no lanzar hasta conectarlo, o
lanzar igual sabiendo que Espacio va a llegar al checkpoint con riesgos (o caída) y que quien
revisa lo va a tener que retirar o aprobar con nota.

En Debian/Ubuntu, `rsvg-convert` viene en el paquete `librsvg2-bin`. Chromium no hace falta: el
rasterizado es sólo con `rsvg-convert`. Si falta, `tapa-render` falla (los ilustradores no pueden
mirar sus PNG) y `publicar` publica sólo el SVG de la tapa.

Para chequear las fuentes:

```bash
fc-list : family | grep -i -E "archivo|inter|garamond|lato|fira code"
```

### Clave de quien revisa

La persona que va a revisar crea una sola vez su frase secreta, **en su propia terminal**:

```bash
uv run condor clave --revisor "Tu Nombre"
```

Se guarda un verificador (no la frase) en `~/.config/condor/revisor.json` con permisos `600`. La
variable de entorno `CONDOR_CONFIG` cambia ese directorio. Ver [6.1](#61-clave).

---

## 2. Mapa del repositorio

```
revista-ia/
├── pipeline/                     redacción multi-agente (Workflows de Claude Code, JavaScript)
│   ├── condor.workflow.js        orquestador de un número (jefe de redacción)
│   ├── etapas/                   workflows hijos
│   │   ├── verificar.workflow.js     libro de afirmaciones: extractor + completitud + verificador
│   │   ├── reconciliar.workflow.js   detectores en código + 2 lentes + debate + juez
│   │   ├── consolidar.workflow.js    une fallos que comparten afirmaciones (v2.1)
│   │   ├── cierre.workflow.js        aplica los fallos con guardas y auto-reparación
│   │   └── tapa.workflow.js          3 ilustradores + jurado + corrección del ganador
│   ├── regresion-00.workflow.js        regresión completa sobre el Nº 00 (generado)
│   └── regresion-00-cierre.workflow.js regresión barata: consolidar → cierre (generado)
├── condor/                       paquete Python (CMS y checkpoint; se corre con uv run condor)
│   ├── cli.py                    comandos
│   ├── estado.py                 ciclo del número, riesgos, hashes, firmas, lock, publicación
│   ├── importar.py               resultado del workflow → data/numero-XX.json
│   ├── render.py + templates/    borrador.html, revision.html, index.html, index.md (Jinja2)
│   ├── numeros.py                normalización de cifras (espejo de canonNum/sig de los .js)
│   └── svg.py                    validación y rasterizado de tapas
├── scripts/
│   ├── semilla_desde_journal.py  arma args.semilla desde el journal de una corrida
│   ├── generar_regresion.py      genera los workflows de regresión (y el fixture)
│   ├── evaluar_regresion.py      evalúa una regresión contra el ground truth
│   └── build_issue.py            CMS del piloto v1 (sólo para el Nº 00)
├── tests/                        pytest + tests/js/ (runtime simulado para node) + fixtures/
├── data/                         números (numero-XX.json), decisiones (numero-XX.revision.json),
│                                 resultados de regresión
├── output/numero-XX/             borrador, paquete de revisión, tapas y número publicado
├── runs/numero-XX/               copia congelada del pipeline con que se corrió cada número,
│                                 SHA256SUMS, NOTA.md, journal y resultado de la corrida
├── roles/                        fichas de cada rol (00 línea editorial … 10 checkpoint humano)
├── plan.md, plan-resvista-01.md  diseño y arquitectura
└── CLAUDE.md                     instrucciones y estado del proyecto para Claude Code
```

Dos cosas que conviene tener presentes:

- **Los workflows no importan módulos ni leen disco.** Todo lo que entra lo hace por `args`, y las
  utilidades de cifras (`canonNum`, `significativa`, `sig`, `sinIds`) están copiadas en las cuatro
  etapas con guardas de cifras (verificar, reconciliar, consolidar, cierre); el orquestador sólo usa
  `canonNum`.
  `condor/numeros.py` tiene que dar exactamente lo mismo; `tests/test_paridad_js.py` lo controla.
- **Lo que se congela por número es sólo `pipeline/`.** El paquete `condor/` (validador de tapas,
  checkpoint, render) es siempre el del repo.

---

## 3. El ciclo de un número en una página

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="img/recorrido-oscuro.png">
  <img alt="Recorrido de un número de Cóndor: investigación, nota de fondo, verificación, reconciliación, consolidación, cierre, estilo, arte, tapa, importación, checkpoint humano y publicación" src="img/recorrido-claro.png">
</picture>

Versión interactiva: [`diagramas/recorrido.html`](diagramas/recorrido.html).

| Paso | Quién lo hace | Comando o herramienta | Deja |
|---|---|---|---|
| 1. Congelar el pipeline | operador (o Claude a pedido) | `cp` + `sha256sum` | `runs/numero-XX/pipeline/` + `SHA256SUMS` |
| 2. Correr la redacción | Claude Code (Workflow) | `condor.workflow.js` con `args` | resultado v2 (`.output`) + `journal.jsonl` |
| 3. Importar | operador (o Claude) | `uv run condor importar` | `data/numero-XX.json` (borrador) |
| 4. Armar la revisión | operador (o Claude) | `uv run condor revision XX` | `output/numero-XX/borrador.html` y `revision.html` |
| 5. Decidir | **sólo la persona que revisa** | `aprobar`, `retirar`, `tapa` | `data/numero-XX.revision.json` firmado |
| 6. Publicar | **sólo la persona que revisa** | `uv run condor publicar XX` | `output/numero-XX/index.html`, `index.md`, `tapa.svg`, `tapa.png` |

---

## 4. Producir un número

### 4.1 Elegir los parámetros

Antes de lanzar, definí las fechas. Van a los prompts y a la tapa, y los workflows no pueden leer el
reloj (`Date.now()` y `new Date()` sin argumentos están prohibidos en un script de Workflow).

| `args` | Obligatorio | Ejemplo (Nº 01) | Qué hace |
|---|---|---|---|
| `numero` | sí | `"01"` | número de ejemplar. Sólo dígitos; se normaliza a dos (`"1"` → `"01"`). Si no es numérico, el workflow falla de entrada |
| `fecha_larga` | sí | `"23 de septiembre de 2026"` | fecha del número: `meta.fecha`, fecha de la nota de fondo y fecha que se pide escribir en la tapa (el validador no la exige: sólo "Cóndor" y el número) |
| `semana_iso` | sí | `"2026-W39"` | se guarda en `meta.semana_iso` |
| `ventana` | sí | `"14 al 23 de septiembre de 2026"` | rango de publicación que buscan las corresponsalías |
| `raiz` | sí | `"<raiz>"` (absoluta) | ruta absoluta del repo: etapas por defecto, carpeta de tapas (`output/numero-XX/tapa`) y `uv run --project` de los ilustradores |
| `modelo_verificador` | sí | `"sonnet"` | modelo de verificadores y escépticos, distinto del de la redacción |
| `ciudad_espacio` | no | `"Bariloche"` | lugar para `proximos_pasos` del MCP (por defecto Bariloche) |
| `etapas` | no, pero usalo | `"<raiz>/runs/numero-01/pipeline/etapas"` (absoluta) | de dónde se cargan las etapas hijas. Sin él, `${raiz}/pipeline/etapas` (el pipeline vivo, no el congelado) |
| `semilla` | no | contenido de `runs/numero-01/semilla-investigacion.json` | investigación ya hecha que no se relanza (ver [4.5](#45-si-la-corrida-se-corta)) |

El tope de debates (`max_debates: 10`) está fijo en el orquestador. Los conflictos que lo excedan
quedan registrados con la guarda `tope_debates` y llegan al checkpoint sin resolver.

### 4.2 Congelar el pipeline

Cada número corre desde una copia congelada de `pipeline/`, para que se pueda saber exactamente con
qué código se hizo. Para un número nuevo (por ejemplo, el 02):

```bash
cd /home/psartorio/revista-ia
mkdir -p runs/numero-02/pipeline/etapas
cp pipeline/condor.workflow.js runs/numero-02/pipeline/
cp pipeline/etapas/*.workflow.js runs/numero-02/pipeline/etapas/
(cd runs/numero-02/pipeline && sha256sum condor.workflow.js etapas/*.workflow.js > SHA256SUMS)
(cd runs/numero-02/pipeline && sha256sum -c SHA256SUMS)
```

Congelá siempre desde `pipeline/`, no desde la copia de un número anterior: por ejemplo, el arreglo
que aplica cada fallo sólo en los bloques de sus afirmaciones está en `pipeline/` y no en
`runs/numero-01/pipeline/`.

**Recongelar.** Si después de congelar cambia el pipeline y la corrida todavía no produjo un
número, podés reemplazar la copia. Antes, guardá el hash del `SHA256SUMS` viejo y dejá el motivo en
`runs/numero-XX/NOTA.md` (así se hizo en el Nº 01):

```bash
cd /home/psartorio/revista-ia/runs/numero-02
sha256sum pipeline/SHA256SUMS          # anotá este hash en NOTA.md
cp ../../pipeline/condor.workflow.js pipeline/
cp ../../pipeline/etapas/*.workflow.js pipeline/etapas/
(cd pipeline && sha256sum condor.workflow.js etapas/*.workflow.js > SHA256SUMS)
sha256sum pipeline/SHA256SUMS          # y también el nuevo
```

Antes de congelar, corré los tests y el chequeo de sintaxis ([sección 9](#9-tests)).

### 4.3 Lanzar el workflow

El workflow se lanza desde una sesión de Claude Code, con la herramienta Workflow, pasando
`scriptPath` y `args`. En la práctica se le pide a Claude, por ejemplo:

```text
Corré el Workflow con scriptPath=/home/psartorio/revista-ia/runs/numero-02/pipeline/condor.workflow.js
y args = {numero:"02", fecha_larga:"…", semana_iso:"2026-W40", ventana:"…",
          raiz:"/home/psartorio/revista-ia", modelo_verificador:"sonnet", ciudad_espacio:"Bariloche",
          etapas:"/home/psartorio/revista-ia/runs/numero-02/pipeline/etapas"}
```

Los `args` tienen que viajar como objeto JSON, no como un string con JSON adentro. Si hay semilla,
Claude tiene que leer el archivo y pasar su contenido como valor de `semilla`: el workflow no puede
abrirlo.

Condiciones para que la corrida salga bien:

- **Sesión fresca y nada más corriendo.** Una corrida completa consume buena parte del límite de la
  sesión. Los workflows grandes van **en serie**, nunca en paralelo. La primera corrida del Nº 01 se
  cortó por límite de sesión con 28 de 52 agentes respondidos.
- **MCP `patagonia-espacial` conectado.** La corresponsalía de Espacio no usa la web: carga las
  herramientas del MCP con ToolSearch. Su verificador también. Chequealo antes con `claude mcp list`
  (ver [§1](#el-servidor-mcp-patagonia-espacial)).
- **Repo sincronizado** (`uv sync`), `rsvg-convert` y las fuentes instaladas: los ilustradores
  validan y rasterizan con el CLI.

Qué esperar: el orquestador llama a las etapas hijas con `workflow()`. Un número típico lanza entre
55 y 70 agentes, y el peor caso ronda los 105 (10 debates y todas las reparaciones). El Nº 01, con
8 corresponsalías y la nota de fondo tomadas de la semilla, usó 75 agentes, 0 errores, en unos
23 minutos.

Si una etapa hija falla, `hijo()` sigue con un resultado neutro y deja una guarda bloqueante
(`etapa_caida`) en cada bloque afectado: la corrida no se cae y nada pasa sin revisión humana.

### 4.4 Seguir la corrida

No abras el `.output` de la tarea: es un envoltorio `{summary, logs, result}` enorme (el del Nº 01
pesa 537 KB). Para ver el progreso, usá el `journal.jsonl` del workflow:

```
~/.claude/projects/<carpeta del proyecto>/<sesión>/subagents/workflows/<runId>/journal.jsonl
```

La carpeta del proyecto sale de la ruta del repo (ver [Rutas de los ejemplos](#rutas-de-los-ejemplos));
para el clon de los ejemplos es `-home-psartorio-revista-ia`.

Cada línea es un evento (`launched`, `started` con `label`, `result`, `failed`). Este script cuenta
agentes por etapa:

```bash
uv run python - ~/.claude/projects/-home-psartorio-revista-ia/<sesión>/subagents/workflows/<runId>/journal.jsonl <<'EOF'
import json, sys, collections
etiqueta, estado = {}, {}
for linea in open(sys.argv[1], encoding="utf-8"):
    e = json.loads(linea)
    if e.get("type") == "started":
        etiqueta[e["key"]] = e["label"]; estado[e["key"]] = "corriendo"
    elif e.get("type") in ("result", "failed"):
        estado[e["key"]] = "ok" if e["type"] == "result" else "falló"
por_etapa = collections.defaultdict(collections.Counter)
for k, s in estado.items():
    por_etapa[etiqueta.get(k, k).split(":")[0]][s] += 1
for etapa, c in por_etapa.items():
    print(f"{etapa:<14} " + "  ".join(f"{s}={n}" for s, n in sorted(c.items())))
print("total:", sum(sum(c.values()) for c in por_etapa.values()))
EOF
```

Las etiquetas de los agentes indican la etapa:

| Etiqueta | Agente |
|---|---|
| `seccion:<clave>` | corresponsal (`llm`, `hardware`, `politica`, `safety`, `ciencia_salud`, `industria_robotica`, `argentina`, `latam`, `espacio`) |
| `feature:nota-de-fondo` | editor/a de la nota de fondo |
| `extraer:<clave>`, `extraer:<clave>:reintento`, `extraer+:<clave>` | extractor de afirmaciones, su reintento y la ronda de completitud |
| `verificar:<clave>` | verificador (modelo verificador) |
| `reconciliar:<lente>` | reconciliadores "hechos" y "cronología" |
| `debate:<C>:defensor`, `debate:<C>:esceptico`, `juez:<C>` | debate y fallo de cada conflicto |
| `consolidar:<K>` | juez de consolidación |
| `cierre:<clave>`, `cierre+:<clave>` | editor de cierre y su ronda de auto-reparación |
| `estilo:corrector`, `arte:director` | corrector de estilo y director/a de arte |
| `tapa:ilustrador-<A/B/C>`, `tapa:juez-<lente>`, `tapa:correccion-<id>`, `tapa:confirmar-<id>` | etapa de tapa |

Cuando termine, guardá la corrida junto al pipeline congelado, como en el Nº 01:

```bash
cp <journal.jsonl> runs/numero-02/journal-<runId>.jsonl
cp <ruta del .output> runs/numero-02/resultado-<runId>.output.json
```

### 4.5 Si la corrida se corta

- **Misma sesión.** Relanzá con el mismo `scriptPath`, los mismos `args` y
  `resumeFromRunId: "<runId>"`. Los agentes que ya respondieron se devuelven del caché y la corrida
  sigue desde el primero que falta. **Sólo funciona dentro de la misma sesión.**
- **Sesión nueva.** Armá una semilla con la investigación ya hecha y relanzá en una sesión fresca.
  La semilla reusa las corresponsalías y la nota de fondo. La verificación y todo lo demás corre
  igual.

```bash
uv run python scripts/semilla_desde_journal.py \
  ~/.claude/projects/-home-psartorio-revista-ia/<sesión>/subagents/workflows/<runId>/journal.jsonl \
  runs/numero-02/semilla-investigacion.json \
  --excluir espacio
```

| Opción | Qué hace |
|---|---|
| `--excluir clave1,clave2` | beats que se vuelven a correr en vivo. Espacio conviene rehacerlo casi siempre: sus pasos de satélite son "esta semana" respecto de la corrida |
| `--sin-feature` | no reusa la nota de fondo |

La semilla toma el último resultado de cada `seccion:*` y de `feature:nota-de-fondo`, y descarta
secciones a las que les falte algún campo. El campo `origen` toma el nombre de la carpeta del
journal, así que corré el script sobre el journal en su carpeta original (`wf_…`) para que quede
registrado de qué corrida salió. Guardá también una copia del journal cortado en
`runs/numero-XX/corrida-interrumpida/journal.jsonl`.

El resultado registra `meta.semilla = {origen, beats_reusados, feature_reusada}`.

### 4.6 Límites del runtime de Workflows

- **Anidamiento de un nivel.** El orquestador puede llamar a `workflow()`; una etapa hija no. Por eso
  las etapas no se llaman entre sí y todo el encadenamiento vive en `condor.workflow.js` (y en los
  scripts de regresión).
- **Sin disco.** Los workflows reciben todo por `args`. Por eso el fixture de la regresión va
  embebido en el script, y la semilla viaja como objeto.
- **Sin reloj ni azar.** `Date.now()`, `Math.random()` y `new Date()` sin argumentos rompen el
  resume y están prohibidos. Las fechas entran por `args`.
- **En serie.** Dos workflows grandes en paralelo agotan el límite de la sesión.

---

## 5. Importar y armar la revisión

### 5.1 Importar

```bash
uv run condor importar runs/numero-02/resultado-<runId>.output.json
# -> /home/psartorio/revista-ia/data/numero-02.json
```

`importar`:

- acepta el `.output` tal cual: si el JSON trae `result` y no `version`, desenvuelve `result`.
  También tolera texto antes del objeto JSON;
- exige `version == 2` y un `numero` numérico, que normaliza a dos dígitos;
- convierte en relativas a `output/numero-XX/` las rutas de las tapas candidatas;
- se niega a pisar un `data/numero-XX.json` existente, o un número que ya tiene decisiones de
  revisión, salvo con `--forzar`. Al forzar, las aprobaciones de los bloques que cambien vencen
  solas.

**Ojo:** `--forzar` reemplaza el archivo entero con el resultado del workflow, sin mezclar nada del
anterior. Se pierden las correcciones manuales ([6.8](#68-pedir-correcciones-de-texto-antes-de-aprobar)):
textos editados, entradas de `correcciones` con `ref: "revisor"` y el copete escrito a mano. Si
hubo, volvé a aplicarlas después de reimportar.

```bash
uv run condor importar <resultado.json> --forzar
```

### 5.2 Armar el paquete de revisión

```bash
uv run condor revision 02
```

Crea `data/numero-02.revision.json` si no existe (el número pasa a `en_revision`), imprime el
estado y genera dos archivos:

- **`output/numero-02/borrador.html`**: el número como se vería publicado, con una banda de
  BORRADOR arriba, los bloques retirados marcados y la caja "Cómo verificamos este número".
- **`output/numero-02/revision.html`**: el paquete para quien revisa:
  - copete de portada (se publica) y concepto de tapa (nota interna, no se publica);
  - "Qué tenés que decidir", con los comandos exactos para ese número;
  - candidatos de tapa con los puntajes y fundamentos del jurado;
  - conflictos entre notas, con el debate completo, el fallo y si quedó consolidado en un `K…`;
  - bloque por bloque: riesgos, diff contra la investigación original y libro de afirmaciones con
    la evidencia;
  - correcciones aplicadas, contexto que encontraron los verificadores y guardas disparadas.

Podés volver a correr `condor revision` todas las veces que quieras (por ejemplo, después de una
corrección de texto). No toca las decisiones.

Dos cosas que `revision.html` no muestra y conviene mirar en `data/numero-XX.json`: las
observaciones del corrector de estilo (`estilo.observaciones`, donde el corrector anota lo que le
pareció raro y no tocó) y `meta.semilla`. En el Nº 01, una de esas observaciones ya señalaba el
"hoy jueves" de Espacio.

### 5.3 Ver el estado

```bash
uv run condor estado 02
```

Muestra el estado del número (`borrador`, `en_revision`, `aprobado`, `publicado`) y, por bloque,
`✓` decisión vigente, `●` pendiente o `✗` aprobación vencida con el motivo, más los riesgos abiertos
de cada bloque pendiente y el estado de la tapa. Si lo publicado en `output/` ya no coincide con las
decisiones, avisa que hay que volver a publicar.

---

## 6. Checkpoint humano

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="img/checkpoint-oscuro.png">
  <img alt="Estados de un número en la revisión humana: borrador, en revisión, aprobado y publicado, con los vencimientos que lo devuelven a revisión" src="img/checkpoint-claro.png">
</picture>

Versión interactiva: [`diagramas/checkpoint.html`](diagramas/checkpoint.html).

Estos comandos los corre **la persona que revisa, en su terminal**. Si se corren sin TTY (por
ejemplo, desde la herramienta Bash de un agente), fallan con este mensaje:

```text
condor: 'aprobar' registra una decisión editorial y requiere una terminal interactiva.
Corré el comando vos, en tu terminal: un agente (incluido Claude) no puede aprobar un número.
```

Cada decisión pide dos cosas: la frase secreta y el número del ejemplar tipeado (`02`, con los dos
dígitos). La primera firma la decisión. La segunda es una barrera contra errores de dedo.

`--revisor` indica quién decide; si falta, se usa `$USER`. Cada acción valida primero (para no
pedirte la frase en vano), después te pide la frase y recién ahí, bajo un lock, vuelve a leer datos
y revisión, revalida y escribe. Dos decisiones simultáneas no se pisan.

### 6.1 `clave`

```bash
uv run condor clave --revisor "Tu Nombre"
```

Crea o cambia la frase secreta (mínimo 8 caracteres, se pide dos veces). Para cambiarla hay que
tipear la actual. De la frase se deriva una clave con scrypt; en `~/.config/condor/revisor.json`
queda sólo la sal, un verificador y la huella. **Si cambiás la frase, las decisiones firmadas con la
anterior dejan de validar** y `publicar` las rechaza: hay que volver a tomarlas. La frase no se puede
recuperar; si la perdés, la única salida es borrar `revisor.json`, crear una nueva y volver a decidir.

### 6.2 `aprobar`

```bash
uv run condor aprobar 02 --todo --revisor "Tu Nombre"
uv run condor aprobar 02 --bloque espacio --nota "por qué se publica igual" --revisor "Tu Nombre"
uv run condor aprobar 02 --bloque llm --bloque latam --revisor "Tu Nombre"
```

| Opción | Qué hace |
|---|---|
| `--todo` | aprueba todos los bloques **sin riesgos abiertos** que no estén retirados. Los que tienen riesgos se saltean y se listan |
| `--bloque CLAVE` | aprueba ese bloque. Se puede repetir |
| `--nota "…"` | obligatoria si algún bloque nombrado con `--bloque` tiene riesgos. Queda registrada |
| `--revisor NOMBRE` | quién aprueba |

Hace falta `--todo` o al menos un `--bloque`. Cada aprobación guarda el hash de todo lo publicable
del bloque (título, bajada, cuerpo, fuente, fecha, sección, tipo, `open_weight`, fuentes) y de sus
afirmaciones con su estado, más la lista de riesgos aceptados.

### 6.3 `retirar`

```bash
uv run condor retirar 02 --bloque hardware --motivo "la fuente no alcanza" --revisor "Tu Nombre"
```

`--bloque` (uno solo) y `--motivo` son obligatorios. Retirar un bloque puede abrir riesgos nuevos en
otros: los que comparten un hecho (según los grupos del reconciliador) o cifras con el retirado
quedan con `depende_de_bloque_retirado`, y si ya estaban aprobados, esa aprobación vence. Si el
bloque ya estaba publicado, sigue en `output/` hasta que vuelvas a publicar.

### 6.4 `tapa`

```bash
uv run condor tapa 02 A2 --revisor "Tu Nombre"
uv run condor tapa 02 B --nota "la cifra está en la nota de hardware" --revisor "Tu Nombre"
```

El candidato es el id que figura en `revision.html`: `A`, `B`, `C`, o la versión corregida del
ganador (por ejemplo `A2`). Al elegir:

1. se valida el SVG con `condor/svg.py`, con los textos obligatorios "Cóndor" y el número;
2. se calculan los riesgos de tapa; si hay, hace falta `--nota`;
3. se guarda una copia con nombre por contenido, `output/numero-XX/tapa/elegida-<sha16>.svg`, y la
   decisión firmada guarda el SHA-256 del SVG y el hash de `meta` (título, copete, concepto de tapa…).

**Elegir la tapa también aprueba los metadatos del número.** Si después cambia algo de `meta`, la
elección vence. Por eso el copete y el título se corrigen antes de elegir tapa.

### 6.5 `publicar`

```bash
uv run condor publicar 02 --revisor "Tu Nombre"
```

Sólo corre si:

- todas las decisiones (bloques y tapa) tienen una firma válida de tu clave;
- todos los bloques tienen una decisión vigente (aprobación con el hash actual y sin riesgos nuevos,
  o retiro);
- la tapa está vigente;
- hay al menos un bloque aprobado.

Genera en `output/numero-XX/`: `index.html`, `index.md`, `tapa.svg` (copia exacta del SVG aprobado)
y `tapa.png` (rasterizado de ese SVG a 1200 px; sin `rsvg-convert` se publica sólo el SVG). Nunca se
copia un PNG hecho por los agentes. En `revision.json` queda un registro firmado de la publicación:
revisor, fecha, hashes de los bloques publicados, candidato y hash de tapa, hash de `meta` y hash de
cada archivo generado.

### 6.6 Vencimientos

Nada queda aprobado "para siempre". Una decisión vence sola si cambia lo que se aprobó:

| Qué vence | Cuándo |
|---|---|
| Aprobación de un bloque | cambia el hash del bloque (texto, fuente, sección, afirmaciones o su estado) |
| Aprobación de un bloque | aparece un riesgo que no estaba entre los aceptados, o un riesgo aceptado pasa a describir otra cosa (la identidad del riesgo incluye un resumen de su contenido) |
| Elección de tapa | cambia el SVG elegido, cambia `meta` o aparece un riesgo de tapa nuevo |
| Publicación | cambian los hashes publicados, la tapa o `meta`, o se retira un bloque: `estado` avisa que hay que volver a publicar |

Una aprobación vencida vuelve a `●`/`✗` en `condor estado` y hay que tomarla de nuevo.

### 6.7 Riesgos

`condor/estado.py` recalcula los riesgos por su cuenta, aunque las guardas del workflow hayan
pasado. Un bloque con cualquiera de estos riesgos no entra con `--todo`: exige `--bloque` y `--nota`,
o retirarlo.

| Riesgo | Significa |
|---|---|
| `afirmacion_no_verificable`, `afirmacion_contradicho`, `afirmacion_sin_consenso`, `afirmacion_no_aplicado` | una afirmación del bloque quedó en un estado de riesgo |
| `retirada_sigue_en_texto` | una afirmación retirada sigue literal en el texto |
| `conflicto_sin_resolver` | un conflicto del bloque no tiene fallo propio ni consolidado |
| `conflicto_sin_consenso` | el juez (o el de consolidación) no pudo decidir |
| `resolucion_no_aplicada` | el juez decidió corregir, retirar o matizar, pero el cierre no pudo aplicarlo con las guardas |
| `fallo_cifra_sigue_en_texto` | el fallo mandó retirar o corregir una cifra que sigue en el texto |
| `guarda_<tipo>` | una guarda bloqueante del workflow sobre el bloque (ver [10.5](#105-guardas-por-etapa)) |
| `depende_de_bloque_retirado` | comparte un hecho o cifras con un bloque retirado |
| `cifras_sin_trazabilidad` | hay cifras que no vienen de la investigación original, de una corrección registrada, de un fallo ni del contexto omitido |

Riesgos de tapa (exigen `--nota` al elegirla): `tapa_cifra_sin_respaldo` (una cifra de la tapa no
está en ninguna nota publicada), `tapa_cifra_en_riesgo` (sólo la respaldan afirmaciones sin
verificar), `tapa_dato_ancla_retirado`, `tapa_dato_ancla_en_riesgo` y `tapa_titulo_retirado` (la
tapa anuncia una nota retirada).

### 6.8 Pedir correcciones de texto antes de aprobar

El checkpoint no tiene un comando para editar texto. Cuando quien revisa pide un cambio, se edita el
bloque en `data/numero-XX.json` y se deja registrado en `correcciones`. En el Nº 01 se hizo así, en
parte después de una primera publicación (ver [6.9](#69-cambiar-un-número-ya-publicado)): el revisor
pidió corregir las coordenadas de Espacio (el fallo C2 que el cierre no había podido aplicar) y
cambiar "hoy jueves" por "jueves 24/09", y escribió el copete a mano. Espacio se volvió a aprobar y
se republicó; la tapa se volvió a elegir por el cambio de copete y hubo una tercera publicación.

Estas correcciones viven sólo en `data/numero-XX.json`: un `condor importar --forzar` posterior las
borra ([5.1](#51-importar)).

1. Editá el campo (`titulo`, `bajada` o `cuerpo`) del bloque en `data/numero-XX.json`.
2. Agregá una entrada a `correcciones`:

   ```json
   {"bloque": "espacio", "ref": "revisor",
    "antes": "…fragmento original…", "despues": "…fragmento nuevo…",
    "motivo": "corrección manual pedida por el revisor: …"}
   ```

   Usá como `ref` el id del conflicto si la corrección aplica un fallo (en el Nº 01, `C2`). Las
   cifras de `despues` pasan a ser trazables; una cifra nueva que no esté en ninguna corrección
   registrada aparece como `cifras_sin_trazabilidad`.
3. Si el cambio es del copete o del título del número, editá `meta.copete` o `meta.titulo_numero`
   **antes** de elegir la tapa.
4. Regenerá el paquete y revisá:

   ```bash
   uv run condor revision XX
   uv run condor estado XX
   ```

La aprobación del bloque editado vence sola (cambió su hash) y hay que volver a aprobarlo. Editar el
texto no cambia el estado de las afirmaciones ni de los fallos: en el Nº 01, Espacio siguió con
`afirmacion_no_aplicado`, `resolucion_no_aplicada` (C2 y C7) y `guarda_correccion_no_aplicada`, y se
aprobó con `--nota`. Ciencia y salud también se aprobó con nota, por una afirmación no verificable.

### 6.9 Cambiar un número ya publicado

Cualquier cambio en un número publicado pasa por el mismo checkpoint: editar y registrar la
corrección, `condor revision`, volver a aprobar o retirar los bloques afectados y `condor publicar`.
Hasta que se vuelve a publicar, `condor estado` avisa que `output/` quedó desactualizado.

El Nº 00 es un caso aparte: salió con el piloto v1 (`data/numero-00.json` no es versión 2) y se armó
con `scripts/build_issue.py`, así que el checkpoint no lo abre (ver
[Solución de problemas](#11-solución-de-problemas)).

---

## 7. Herramientas de tapa

Los usan los ilustradores dentro del workflow, pero también sirven a mano.

```bash
uv run condor tapa-validar output/numero-02/tapa/candidato-A.svg --requerido "Cóndor" --requerido "02"
uv run condor tapa-render  output/numero-02/tapa/candidato-A.svg --ancho 1200
```

**`tapa-validar SVG [--requerido TEXTO]...`** imprime un JSON `{ok, errores, avisos, textos, bytes}`
y sale con código 0 si está bien o 1 si no. Rechaza: más de 800.000 bytes, XML mal formado o con
entidades peligrosas, raíz que no sea `<svg>`, falta de `viewBox`, elementos `script`,
`foreignObject`, `iframe`, `object`, `embed`, `audio`, `video` e `image`, atributos `on*`, `href`
que no empiece con `#`, `url(http…)` o `@import` en estilos, y textos obligatorios ausentes (la
comparación ignora mayúsculas y tildes). Una fuente fuera de la lista instalada es un aviso, no un
error.

**`tapa-render SVG [--ancho N]`** rasteriza con `rsvg-convert` sobre fondo `#0a0f1e`: genera
`<nombre>.png` al ancho pedido (por defecto 1200) y `<nombre>-mini.png` a 300 px, al lado del SVG.
Imprime las dos rutas en JSON.

La tapa del número se pide en el workflow a 1200 × 1600 (`viewBox="0 0 1200 1600"`), con masthead
"CÓNDOR", "Nº XX", la fecha y el título del número, y como máximo tres líneas de tapa tomadas de
notas sin riesgo.

---

## 8. Regresión sobre el Nº 00

La regresión corre las etapas de verificación y cierre sobre el Nº 00 **tal como lo escribió** la
redacción v1, antes de la corrección manual del 13/09/2026, y compara el resultado con un ground
truth de 7 casos (`tests/fixtures/numero-00-gt.json`).

| Caso | Qué se espera |
|---|---|
| `oracle_300k_gpus` | Oracle desplegó más de 300.000 GPUs en el Q1 FY27: dato correcto, no se tiene que perder |
| `oracle_850mw` | 850 MW está confirmado: no se tiene que perder |
| `dsewiki_fechas` | DSEwiki se usó del 24 de mayo al 22 de junio de 2026: el 11 de mayo como inicio está mal |
| `nightingale` | el nombre del grupo es correcto: marcarlo dudoso es un falso positivo |
| `openai_niega` | el bloque tiene que incluir que OpenAI niega la cláusula |
| `feature_duracion` | "42 días" y "seis semanas" están mal |
| `dsewiki_ediciones` | unas 17.000 ediciones en DSEwiki sobre unas 18.000 en total |

### 8.1 Generar los workflows

```bash
# regresión completa: verificar → reconciliar → consolidar → cierre (~50 agentes)
uv run python scripts/generar_regresion.py

# regresión barata desde el cierre: consolidar → cierre (9 agentes en la corrida de v2.1)
uv run python scripts/generar_regresion.py --desde-cierre                 # usa data/regresion-00.json
uv run python scripts/generar_regresion.py --desde-cierre otra-corrida.json
```

Sin opciones, regenera `tests/fixtures/numero-00-original.json` desde `data/raw_by_label.json` y lo
embebe en `pipeline/regresion-00.workflow.js`. Con `--desde-cierre`, genera
`pipeline/regresion-00-cierre.workflow.js`, que embebe el libro, los conflictos, los fallos y los
debates de una corrida completa (sin lo que agregó su cierre) y corre sólo `consolidar → cierre`.
Sirve para probar cambios en esas dos etapas sin pagar la verificación otra vez.

### 8.2 Correr y evaluar

Lanzalos con Workflow igual que un número, cada uno en su sesión y en serie:

| Script | `args` |
|---|---|
| `pipeline/regresion-00.workflow.js` | `{raiz: "<raiz>", modelo_verificador: "sonnet"}` |
| `pipeline/regresion-00-cierre.workflow.js` | `{raiz: "<raiz>"}` |

Ojo: los dos usan `${raiz}/pipeline/etapas`, el pipeline vivo.

El evaluador lee el objeto que devuelve el workflow, no el envoltorio. Extraé `result` del
`.output` y evaluá:

```bash
uv run python -c "import json,sys; d=json.load(open(sys.argv[1])); json.dump(d.get('result', d), open(sys.argv[2],'w'), ensure_ascii=False, indent=2)" <ruta del .output> data/regresion-00-cierre-<runId>.json
uv run python scripts/evaluar_regresion.py data/regresion-00-cierre-<runId>.json
```

Usá un nombre nuevo: `data/regresion-00.json` y `data/regresion-00-cierre.json` son resultados
versionados (el segundo es el de v2.1, run `wf_7acbbbf3-b25`) y el comando los pisaría. El resultado
de la regresión completa también guardalo con nombre propio y pasáselo a
`generar_regresion.py --desde-cierre <archivo>`; sin argumento, usa `data/regresion-00.json`.

La salida da un veredicto por caso (`OK`, `PARCIAL` si el error sigue pero marcado en un estado de
riesgo, o `FALLA`) y un resumen de estados, conflictos, resoluciones, correcciones y guardas. Con el
resultado guardado de v2.1 da `7 OK · 0 PARCIAL · 0 FALLA`.

---

## 9. Tests

```bash
uv run pytest -q          # 93 tests
```

| Archivo | Tests | Qué cubre |
|---|---|---|
| `tests/test_checkpoint.py` | 20 | ciclo del checkpoint: sin TTY no se aprueba, frase o confirmación incorrecta, clave sin configurar, `--todo` saltea bloques con riesgo, `--nota` obligatoria, vencimiento por edición, publicación bloqueada, retiro y dependencias, tapa modificada o inválida, cifras sin trazabilidad, render del borrador |
| `tests/test_revision_segura.py` | 15 | hallazgos de la revisión adversarial del checkpoint: decisiones escritas por un agente o editadas a mano no se publican, decisiones concurrentes, riesgos de tapa, PNG publicado desde el SVG aprobado, retiro después de publicar, riesgos aceptados que cambian de contenido, `importar` normaliza el número |
| `tests/test_v21.py` | 10 | v2.1: agrupación de miles nunca es un año, ids del libro en la prosa de los jueces, cifras por valor, conflictos cubiertos por una consolidada, `importar` desenvuelve el `.output`, la portada publica el copete y no el concepto |
| `tests/test_workflows_js.py` | 12 | corre `cierre`, `consolidar` y el orquestador con `node` y un `agent` simulado: guardas de cierre, consolidación, orquestador con semilla, fallo aplicado sólo donde están sus afirmaciones. Se saltea sin `node` |
| `tests/test_paridad_js.py` | 9 | las utilidades de cifras son idénticas en todos los `.workflow.js` y dan lo mismo que `condor/numeros.py` |
| `tests/test_numeros.py` | 16 | normalización de cifras (`canon`, significativas, años, nombres de modelo, texto) |
| `tests/test_svg.py` | 10 | validador de tapas: SVG válido, textos obligatorios, scripts, href externos, imágenes, eventos, XML roto, entidades, `viewBox`, fuentes |
| `tests/test_semilla.py` | 1 | `semilla_desde_journal.py` toma secciones y feature del journal y descarta lo incompleto |

Los tests del checkpoint corren sobre un número mínimo (`numero-99`) en un directorio temporal, con
la terminal y la frase simuladas (`tests/conftest.py`). No tocan `data/`, `output/` ni tu clave.

### 9.1 Runtime simulado para los workflows

`tests/js/correr_workflow.mjs` corre un `.workflow.js` en `node` con `agent`, `parallel`,
`pipeline`, `workflow`, `log` y `phase` simulados: `agent` devuelve respuestas fijas por `label`.
Recibe por stdin `{script, args, respuestas}` y devuelve `{result, logs, labels}`.
`tests/js/numeros.mjs` extrae `canonNum`, `significativa`, `sig` y `sinIds` de un script para el test
de paridad.

### 9.2 Chequeo de sintaxis de un workflow

Un script de Workflow empieza con `export const meta = …` y usa `await` en el nivel superior, así que
`node --check` no sirve. El chequeo es envolver el cuerpo en una `AsyncFunction`:

```bash
cd /home/psartorio/revista-ia
for f in pipeline/*.workflow.js pipeline/etapas/*.workflow.js; do
  node -e '
    const fs = require("fs")
    const src = fs.readFileSync(process.argv[1], "utf8").replace(/^export const meta = /m, "const meta = ")
    const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor
    new AsyncFunction("args", "agent", "parallel", "pipeline", "workflow", "log", "phase", "budget", src)
    console.log("ok  ", process.argv[1])
  ' "$f" || echo "MAL  $f"
done
```

Recordá también que `meta` tiene que ser un literal puro (sin variables ni interpolaciones) y que el
script es JavaScript, no TypeScript.

### 9.3 Si tocás las utilidades de cifras

`canonNum`, `significativa`, `sig` y `sinIds` están copiadas en los `.workflow.js` con guardas de
cifras. Si cambiás una, cambiala igual en todos y en `condor/numeros.py`, y corré
`uv run pytest -q tests/test_paridad_js.py`.

---

## 10. Formatos de datos

### 10.1 `data/numero-XX.json`

Es el resultado del workflow normalizado por `importar`. Claves de primer nivel:

| Clave | Contenido |
|---|---|
| `version` | `2` (el checkpoint rechaza cualquier otra) |
| `numero` | `"01"`, dos dígitos |
| `meta` | `titulo_numero`, `copete` (se publica), `concepto_tapa` (interno), `nota_destacada`, `notas_diseno`, `brief_tapa`, `dato_ancla` (`{id, texto, valor}` o `null`), `fecha`, `semana_iso`, `ventana`, `modelo_verificador`, `semilla` |
| `bloques` | la versión final de cada bloque: `clave`, `tipo` (`feature` o `seccion`), `seccion`, `titulo`, `bajada`, `cuerpo`, `fuente_nombre`, `fuente_url`, `fecha`, `open_weight`, `fuentes` |
| `versiones` | `investigacion` (texto original de cada bloque) y `cierre` (después de aplicar los fallos, antes de estilo) |
| `afirmaciones` | el libro de afirmaciones (ver 10.2) |
| `grupos` | afirmaciones del mismo hecho en distintos bloques (`afirmaciones`, `descripcion`); el checkpoint las usa para las dependencias |
| `conflictos` | `id` (`C1`…), `tipo` (`valor`, `veredicto`, `huerfana`, `cronologia`, `interna`, o `contradicho` para las contradichas del verificador), `afirmaciones`, `bloques`, `gravedad`, `origen`, `descripcion` |
| `resoluciones` | los fallos (ver 10.3) |
| `debates` | `conflicto_id`, `defensor`, `esceptico` |
| `consolidacion` | `componentes` y `reemplazadas` (los fallos originales que reemplazó un `K…`) |
| `descartados`, `candidatos_deterministicos` | conflictos que los reconciliadores descartaron y candidatos de los detectores en código |
| `correcciones` | cada edición aplicada: `bloque`, `antes`, `despues`, `motivo`, `ref` (id de conflicto, `revisor`, o `contexto`, a veces con una descripción libre como `"[contexto] MATIZAR 3 (Forbes, industria_robotica#4)"`) |
| `contexto_omitido` | contexto que encontraron los verificadores y faltaba en la nota |
| `guardas` | `etapa`, `bloque`, `tipo`, `severidad` (`aviso` o `bloqueante`), `detalle` |
| `estilo` | `observaciones` del corrector de estilo |
| `tapa` | `candidatos` (con `svg`, `png`, `png_mini`, `descripcion`, `textos_en_tapa`, `puntajes`, `problemas`, `total`…), `ganador`, `jueces`, `correccion` |

### 10.2 Afirmaciones y sus estados

Cada afirmación tiene `id` (`bloque#n`, por ejemplo `safety#7`), `bloque`, `texto`, `tipo` (`cifra`,
`fecha`, `nombre`, `evento`, `atribucion`), `entidad`, `valor`, `cita_textual` (literal del bloque),
`central`, `veredicto` (`{id, estado, valor_encontrado, evidencia: [{url, cita}], nota}`) y
`estado_final`.

```
veredicto del verificador:  confirmado | no_verificable | contradicho
        │   (un "confirmado" sin url de evidencia baja a no_verificable)
        ▼   fallo del juez (o consolidado) + cierre
estado_final:  confirmado | corregido | matizado | retirado
               | no_verificable | contradicho | sin_consenso | no_aplicado   ← estados de riesgo
```

Los cuatro estados de riesgo (`no_verificable`, `contradicho`, `sin_consenso`, `no_aplicado`) tienen
que ser los mismos en `condor.workflow.js`, `condor/estado.py` y `scripts/evaluar_regresion.py`. Una
afirmación `corregido` conserva el valor viejo en `valor`, por eso sólo una `confirmado` puede ser
dato ancla de tapa.

En el Nº 01: 148 afirmaciones, 136 confirmadas, 9 matizadas, 1 corregida, 1 no verificable y 1 no
aplicada.

### 10.3 Resoluciones

`conflicto_id`, `decision` (`mantener`, `corregir`, `retirar`, `matizar`, `sin_consenso`),
`valor_correcto` (el dato, corto), `redaccion_sugerida`, `afirmaciones_afectadas`, `confianza`
(`alta`, `media`, `baja`), `razonamiento`, `evidencia`, `cifras`, `bloques`, y lo que agrega el
cierre: `bloques_pendientes` (donde no se pudo aplicar) y `aplicada`. Una resolución consolidada
tiene id `K1`, `K2`… y `conflictos_cubiertos`. Un conflicto cuenta como resuelto si tiene fallo
propio o si está cubierto por uno consolidado.

### 10.4 `data/numero-XX.revision.json`

Lo escribe sólo el checkpoint.

```json
{
  "numero": "01",
  "decisiones": {
    "feature": {"accion": "aprobar", "hash": "…", "revisor": "…", "fecha": "…", "nota": "",
                "riesgos_aceptados": [], "huella": "…", "firma": "…"},
    "otro":    {"accion": "retirar", "revisor": "…", "fecha": "…", "motivo": "…", "huella": "…", "firma": "…"}
  },
  "tapa": {"candidato": "A2", "archivo": "tapa/elegida-<sha16>.svg", "hash_svg": "…", "hash_meta": "…",
           "riesgos_aceptados": [], "nota": "", "revisor": "…", "fecha": "…", "huella": "…", "firma": "…"},
  "publicacion": {"revisor": "…", "fecha": "…", "hashes": {"feature": "…"}, "candidato": "A2",
                  "hash_tapa": "…", "hash_meta": "…", "archivos": {"index.html": "…"}, "huella": "…", "firma": "…"},
  "historial": [{"fecha": "…", "accion": "iniciar_revision"}, {"fecha": "…", "accion": "aprobar", "revisor": "…", "bloques": ["…"]}]
}
```

`firma` es un HMAC-SHA256 sobre el JSON canónico de `{numero, objeto, decision}` con la clave
derivada de la frase; `huella` identifica la clave. No edites este archivo a mano: `publicar`
rechaza cualquier decisión cuya firma no valide. `data/numero-XX.revision.lock` es el lock del
checkpoint y está en `.gitignore`.

### 10.5 Guardas por etapa

Las guardas son controles en código sobre lo que devuelve cada agente. Las `bloqueante` se
convierten en el riesgo `guarda_<tipo>` del bloque y obligan a una decisión explícita.

| Etapa | Qué controla | Guardas que puede dejar |
|---|---|---|
| investigación / nota de fondo | que cada corresponsalía y la feature entreguen | `corresponsalia_caida` y `feature_caida` (aviso: el bloque queda fuera) |
| verificar | la cita tiene que ser literal (o todas sus cifras estar en el bloque); toda cifra significativa tiene que tener una afirmación (ronda de completitud); un confirmado sin url baja a no verificable | `cita_no_literal`, `extraccion_reintentada`, `confirmado_sin_evidencia`, `id_desconocido`, `sin_veredicto` (aviso); `cifras_sin_afirmacion`, `extraccion_caida`, `sin_afirmaciones`, `etapa_caida` (bloqueante: la extracción o verificación del bloque no devolvió resultado) |
| reconciliar | cifras huérfanas de la feature, mismo dato con veredictos distintos, conflictos anclados a afirmaciones y bloques, tope de 10 debates | `lente_caida`, `id_desconocido`, `tope_debates`, `sin_fallo` (aviso); `conflicto_sin_ancla`, `reconciliacion_caida` (bloqueante) |
| consolidar | la resolución única cubre todas las afirmaciones del componente y no trae cifras que no estén en los fallos, las evidencias o los textos | `fallos_consolidados` (aviso); `consolidacion_caida` (bloqueante: quedan los fallos originales) |
| cierre | lo retirado no sigue en el texto; el valor viejo desaparece y el nuevo aparece (sólo cifras que están en `valor_correcto` y en `redaccion_sugerida` y no son viejas, sin contar ids como `feature#17`); un valor viejo no numérico tiene que desaparecer; matizar cambia el texto e incorpora la redacción sugerida; ninguna cifra inventada; cada fallo sólo en los bloques de sus afirmaciones o cifras; una ronda de auto-reparación | `auto_reparacion` (aviso); `correccion_no_aplicada` (bloqueante: texto original y afirmaciones `no_aplicado`), `fallo_sin_ancla` (bloqueante: un retirar sin nada con qué comprobarlo), `etapa_caida` (bloqueante: el agente de cierre de ese bloque no devolvió resultado) |
| estilo | mismo multiconjunto de cifras, largo entre 75 % y 125 %, nombres y atribuciones protegidos; si falla se descarta la edición | `edicion_rechazada`, `sin_edicion` (aviso) |
| arte | el dato ancla tiene que ser una afirmación confirmada de un bloque sin riesgos; las líneas de tapa salen sólo de bloques sin riesgos | `dato_ancla_invalido` (aviso: la tapa no lleva cifras) |
| tapa | validador SVG, puntaje calculado por el código (promedio de los jueces que puntuaron) | `ilustrador_caido`, `tapa_invalida`, `jurado_caido`, `puntaje_faltante` (aviso); `sin_tapa` (bloqueante) |
| cualquier etapa hija | si el workflow hijo entero falla, `hijo()` sigue con un resultado neutro (verificar y cierre además la emiten por bloque, ver arriba) | `etapa_caida` (bloqueante en cada bloque afectado) |
| checkpoint (`estado.py`) | riesgos recalculados por bloque y de tapa, aprobación atada al hash, tapa atada al SHA del SVG y a `meta`, firmas HMAC | ver [6.7](#67-riesgos) |

En el Nº 01 saltaron dos: una `auto_reparacion` en la nota de fondo (aviso) y una `correccion_no_aplicada` en Espacio (bloqueante).

### 10.6 Qué queda en `output/numero-XX/`

| Archivo | Lo genera |
|---|---|
| `tapa/candidato-<id>.svg`, `.png`, `-mini.png` | ilustradores (workflow) |
| `borrador.html`, `revision.html` | `condor revision` |
| `tapa/elegida-<sha16>.svg` | `condor tapa` |
| `index.html`, `index.md`, `tapa.svg`, `tapa.png` | `condor publicar` |

---

## 11. Solución de problemas

| Síntoma | Causa y solución |
|---|---|
| `… requiere una terminal interactiva` | el comando se corrió sin TTY (por ejemplo, desde un agente). Corrélo vos en tu terminal. Es intencional |
| `no hay clave de revisor/a configurada` | falta `uv run condor clave --revisor "Tu Nombre"` |
| `frase incorrecta: no se registró ninguna decisión` | la frase no coincide con la de `~/.config/condor/revisor.json` (o con `CONDOR_CONFIG`) |
| `confirmación incorrecta` | hay que tipear el número exactamente como el ejemplar, con dos dígitos (`01`, no `1`) |
| `primero generá el paquete de revisión` | corré `uv run condor revision XX` antes de decidir |
| `el bloque 'x' tiene N riesgo(s) abierto(s); aprobarlo exige --nota` | aprobalo con `--bloque x --nota "…"` o retiralo |
| `--todo` no aprobó algunos bloques | tienen riesgos: el comando los lista. Decidilos uno por uno |
| `no se puede publicar todavía` | el mensaje lista qué falta: bloques sin decisión, aprobaciones vencidas, tapa |
| `hay decisiones sin una firma válida de tu clave` | alguien escribió o editó `revision.json`, o cambiaste la frase. Volvé a tomar esas decisiones |
| `la tapa X no pasa la validación` | corré `condor tapa-validar` sobre el SVG para ver los errores, o elegí otro candidato |
| `la tapa X tiene riesgos` | elegí otra o agregá `--nota` explicando por qué |
| tapa: `cambiaron el título del número o los metadatos de tapa` | se editó `meta` (copete, título…) después de elegirla. Volvé a elegirla |
| `⚠ lo publicado en output/ ya no coincide` | cambió algo después de publicar. Revisá, decidí y volvé a publicar |
| `numero-00.json es versión 1; el checkpoint requiere versión 2` | el Nº 00 salió con el piloto v1 y se arma con `uv run scripts/build_issue.py data/numero-00.json`. El checkpoint sólo abre números v2. Ojo: ese script regenera `output/numero-00/index.md` e `index.html`, que son el Nº 00 publicado y están versionados; no hace falta correrlo salvo que quieras reconstruir el Nº 00 |
| `numero-XX.json ya existe o tiene decisiones de revisión; usá --forzar` | reimportar pisa el número: usá `--forzar` sabiendo que las aprobaciones de bloques que cambien vencen y que se pierden las correcciones manuales y el copete escrito a mano (volvé a aplicarlos) |
| `el resultado no es versión 2` | se importó otra cosa (un resultado v1, o de una regresión) |
| `rsvg-convert no está instalado` | instalá librsvg (`librsvg2-bin`). Sin él, los ilustradores no pueden mirar sus PNG y `publicar` publica sólo el SVG |
| aviso `fuente no instalada (rsvg usará un reemplazo)` | el SVG usa una fuente fuera de la lista de `condor/svg.py`; instalala o cambiala |
| la corrida se cortó por límite de sesión | en la misma sesión, `resumeFromRunId`; en una nueva, semilla con `semilla_desde_journal.py` ([4.5](#45-si-la-corrida-se-corta)). Corré los workflows grandes en serie y en sesiones frescas |
| el workflow falla con `args.numero tiene que ser un número de ejemplar` | `numero` tiene que ser sólo dígitos, como string (`"02"`) |
| una etapa hija tira error al llamar a `workflow()` | el anidamiento es de un nivel: una etapa no puede lanzar otro workflow |
| la nota de Espacio habla de "hoy" o "esta semana" | el beat escribe fechas relativas a la corrida, no a la fecha del número (pasó en el Nº 01). Corregilo en el checkpoint (6.8) o rehacé Espacio en vivo con `--excluir espacio` |
| se saltean tests de `test_workflows_js.py` y la comparación JS↔Python de `test_paridad_js.py` (`test_js_y_python_dan_lo_mismo`) | falta `node` |
| falla `test_paridad_js.py` | se cambió una utilidad de cifras en un `.js` y no en los demás o en `numeros.py` ([9.3](#93-si-tocás-las-utilidades-de-cifras)) |
| `sha256sum -c SHA256SUMS` falla | la copia congelada cambió después de congelarla. Si fue a propósito, recongelá y documentalo en `NOTA.md` ([4.2](#42-congelar-el-pipeline)) |

---

## 12. Referencia rápida

```bash
# instalación y chequeos
uv sync
uv run pytest -q

# congelar (número 02)
mkdir -p runs/numero-02/pipeline/etapas
cp pipeline/condor.workflow.js runs/numero-02/pipeline/ && cp pipeline/etapas/*.workflow.js runs/numero-02/pipeline/etapas/
(cd runs/numero-02/pipeline && sha256sum condor.workflow.js etapas/*.workflow.js > SHA256SUMS)

# (Claude Code) Workflow scriptPath=<raiz>/runs/numero-02/pipeline/condor.workflow.js
#   args={…, raiz:"<raiz>", etapas:"<raiz>/runs/numero-02/pipeline/etapas"}   (rutas absolutas)

# semilla si la corrida se cortó y la sesión murió
uv run python scripts/semilla_desde_journal.py <journal.jsonl> runs/numero-02/semilla-investigacion.json --excluir espacio

# importar y revisar
uv run condor importar <resultado.output.json> [--forzar]
uv run condor revision 02
uv run condor estado 02

# checkpoint: sólo la persona que revisa, en su terminal
uv run condor clave    --revisor "Tu Nombre"                       # una vez
uv run condor aprobar  02 --todo --revisor "Tu Nombre"
uv run condor aprobar  02 --bloque CLAVE --nota "…" --revisor "Tu Nombre"
uv run condor retirar  02 --bloque CLAVE --motivo "…" --revisor "Tu Nombre"
uv run condor tapa     02 CANDIDATO [--nota "…"] --revisor "Tu Nombre"
uv run condor publicar 02 --revisor "Tu Nombre"

# tapas
uv run condor tapa-validar SVG --requerido "Cóndor" --requerido "02"
uv run condor tapa-render  SVG [--ancho 1200]

# regresión
uv run python scripts/generar_regresion.py [--desde-cierre [corrida.json]]
uv run python scripts/evaluar_regresion.py data/regresion-00-cierre-<runId>.json
```
