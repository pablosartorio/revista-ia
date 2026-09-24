"""Importa el resultado del workflow a `data/numero-XX.json`."""

import json
from pathlib import Path

from .estado import VERSION_DATOS, ErrorCheckpoint, cargar_revision, dir_salida, ruta_numero


def _extraer_json(texto: str) -> dict:
    texto = texto.strip()
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        pass
    # tolera un envoltorio (p. ej. texto antes del objeto)
    inicio = texto.find("{")
    if inicio < 0:
        raise ErrorCheckpoint("el archivo no contiene un objeto JSON")
    obj, _ = json.JSONDecoder().raw_decode(texto[inicio:])
    return obj


def desenvolver(datos: dict) -> dict:
    """El `.output` de una tarea de Workflow es `{summary, logs, result}`: el número está en `result`."""
    if "version" not in datos and isinstance(datos.get("result"), dict):
        return datos["result"]
    return datos


def normalizar(datos: dict) -> dict:
    datos = desenvolver(datos)
    if datos.get("version") != VERSION_DATOS:
        raise ErrorCheckpoint(f"el resultado no es versión {VERSION_DATOS} (¿es un número del pipeline v1?)")
    numero = str(datos.get("numero", ""))
    if not numero.isdigit():
        raise ErrorCheckpoint(f"número de ejemplar inválido en el resultado: {datos.get('numero')!r}")
    numero = datos["numero"] = numero.zfill(2)  # mismo formato que el CLI
    salida = dir_salida(numero)
    for c in (datos.get("tapa") or {}).get("candidatos", []):
        for k in ("svg", "png", "png_mini"):
            if c.get(k):
                p = Path(c[k])
                if p.is_absolute():
                    try:
                        c[k] = str(p.relative_to(salida))
                    except ValueError:
                        pass
    return datos


def importar(ruta: Path, forzar: bool = False) -> Path:
    datos = normalizar(_extraer_json(Path(ruta).read_text(encoding="utf-8")))
    numero = datos["numero"]
    destino = ruta_numero(numero)
    rev = cargar_revision(numero)
    if not forzar and (destino.exists() or (rev and rev.get("decisiones"))):
        raise ErrorCheckpoint(
            f"{destino.name} ya existe o tiene decisiones de revisión; usá --forzar para reemplazarlo "
            "(las aprobaciones de bloques que cambien van a vencer solas)"
        )
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    return destino
