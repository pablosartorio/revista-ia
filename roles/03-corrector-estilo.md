# Corrector/a de estilo

Un solo `agent()`, sin schema (devuelve texto plano), que recibe el draft completo
ya ensamblado (9 secciones + feature) y NO busca nada ni agrega información nueva.

Tarea: homogeneizar tono, longitud de párrafo, nombres de empresas/modelos,
puntuación de cifras (USD, %, fechas), y remover cualquier resabio de lenguaje
marketinero, según `roles/00-linea-editorial.md`. Devuelve el mismo texto, editado.

No tiene autoridad para cambiar hechos — si detecta algo que "no cierra", lo señala
en un comentario al final en vez de reescribirlo (eso es tarea del fact-checker,
no del corrector).
