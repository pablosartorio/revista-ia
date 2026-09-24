# Editores de sección / corresponsales (9 beats)

Cada uno es un `agent()` independiente lanzado en `parallel()`. Reciben la línea
editorial relevante y devuelven **un solo ítem** con schema `SECCION`.

1. **LLMs y modelos fundacionales** — releases, benchmarks, open-weight vs propietario.
2. **Hardware e infraestructura** — chips, datacenters, energía.
3. **Regulación y política** — AI Act, export controls, IA militar.
4. **Seguridad y alineación** — interpretabilidad, incidentes, red-teaming.
5. **Ciencia y salud** — drug discovery, genómica, diagnóstico.
6. **Industria y robótica** — humanoides, coding agents, vehículos autónomos.
7. **Argentina** — CONICET, INVAP, política científica, data centers, startups.
8. **América Latina** — Brasil, Chile, México, Colombia, regulación y ecosistema.
9. **Ciencia y Espacio — Patagonia** *(nueva, ver abajo)*.

## Corresponsalía 9 en detalle: Ciencia y Espacio — Patagonia

Distinta de las otras 8: no busca en la web, consulta el **MCP `patagonia-espacial`**
(`listar_satelites`, `donde_esta`, `proximos_pasos`). Instrucción al agente:

> Consultá el catálogo de satélites disponible. Elegí uno relevante para la región
> (con foco en observación de la Tierra / Patagonia / Argentina si existe alguno de
> ese perfil en el catálogo — ej. SAOCOM, ARSAT — o el más interesante disponible).
> Usá `proximos_pasos` con `solo_visibles=True` para Bariloche u otra ciudad
> patagónica relevante, y armá una nota corta de "cielo de la semana": qué satélite,
> cuándo pasa, si es visible a ojo desnudo, por qué le importa a alguien en el
> ecosistema espacial/IA de INVAP. Datos en hora argentina (UTC-3).

Esto demuestra que la arquitectura no depende solo de búsqueda web — puede tener
corresponsalías alimentadas por fuentes de datos en vivo vía MCP.
