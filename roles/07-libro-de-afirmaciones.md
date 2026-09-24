# Libro de afirmaciones: extractor y verificador (v2)

Reemplaza al fact-check "por grupo de bloques" del Nº 00, que daba **un solo veredicto por
bloque** y por eso no podía decir *cuál* dato de la nota estaba mal.

## Extractor (un agente por bloque) — `pipeline/etapas/verificar.workflow.js`
Descompone cada bloque (secciones y nota de fondo) en **afirmaciones atómicas** con dato duro:
cifras, fechas, duraciones derivadas, nombres, atribuciones. Cada afirmación trae una
`cita_textual` que el código busca literal en el texto: si no aparece (y tampoco sus cifras),
se descarta y queda una guarda. Si quedan cifras del bloque sin ninguna afirmación que las
cubra, corre una **ronda de completitud** que extrae sólo esas (sin tope). Las cifras que ni así
se extraen quedan como guarda **bloqueante**: nadie las verificó. Si el extractor no responde, se
reintenta una vez; si vuelve a fallar, el bloque queda bloqueado.

## Verificador (un agente por bloque, **otro modelo**)
Verifica cada afirmación de cero: primero lee la fuente citada (WebFetch), después hasta 3
búsquedas propias para lo que la fuente no confirma y para lo central. Estados:
`confirmado` (con url + cita literal obligatoria), `contradicho` (con el valor encontrado),
`no_verificable` (default ante la duda). También reporta **contexto omitido**: por ejemplo,
una desmentida de la parte involucrada que la nota no menciona.

Usa un modelo distinto al que redactó (`modelo_verificador`, por defecto `sonnet`): la
investigación previa documentó sesgo de auto-preferencia cuando un modelo verifica su propio
texto.

Guarda determinística: un "confirmado" sin url de evidencia se baja a `no_verificable`.
