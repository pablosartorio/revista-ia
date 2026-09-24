"""Validación y rasterizado de tapas SVG.

Las tapas las dibujan agentes; este módulo es la guarda determinística que decide
si un SVG es embebible (sin scripts, sin recursos externos, bien formado) y si
contiene los textos obligatorios de la tapa.
"""

import shutil
import subprocess
from pathlib import Path

from defusedxml import ElementTree as ET

from .numeros import normalizar_texto

MAX_BYTES = 800_000

FUENTES_INSTALADAS = {
    "inter", "inter display", "archivo", "archivo black", "eb garamond", "lato",
    "fira code", "dejavu sans", "dejavu serif", "dejavu sans mono", "liberation sans",
    "liberation serif", "sans-serif", "serif", "monospace",
}

_PROHIBIDOS = {"script", "foreignobject", "iframe", "object", "embed", "audio", "video", "image"}


def _local(nombre: str) -> str:
    return nombre.rsplit("}", 1)[-1] if "}" in nombre else nombre


def validar(ruta: str | Path, requeridos: tuple[str, ...] = ()) -> dict:
    ruta = Path(ruta)
    errores: list[str] = []
    avisos: list[str] = []
    if not ruta.exists():
        return {"ok": False, "errores": [f"no existe: {ruta}"], "avisos": [], "textos": "", "bytes": 0}
    datos = ruta.read_bytes()
    if len(datos) > MAX_BYTES:
        errores.append(f"pesa {len(datos)} bytes (máximo {MAX_BYTES})")
    try:
        raiz = ET.fromstring(datos)
    except Exception as e:  # XML mal formado o entidades peligrosas (defusedxml)
        return {"ok": False, "errores": [f"XML inválido: {e}"], "avisos": [], "textos": "", "bytes": len(datos)}

    if _local(raiz.tag).lower() != "svg":
        errores.append(f"el elemento raíz es <{_local(raiz.tag)}>, no <svg>")
    if "viewBox" not in raiz.attrib:
        errores.append("falta viewBox en <svg>")

    textos = []
    for el in raiz.iter():
        nombre = _local(el.tag).lower()
        if nombre in _PROHIBIDOS:
            errores.append(f"elemento no permitido: <{nombre}>")
        if nombre == "text":
            textos.append("".join(el.itertext()))
        if nombre == "style" and el.text and ("url(http" in el.text or "@import" in el.text):
            errores.append("<style> con recurso externo")
        for k, v in el.attrib.items():
            lk = _local(k).lower()
            if lk.startswith("on"):
                errores.append(f"atributo de evento no permitido: {lk}")
            if lk == "href" and not v.startswith("#"):
                errores.append(f"referencia externa no permitida: {v[:60]}")
            if lk == "style" and "url(http" in v:
                errores.append("estilo inline con recurso externo")
            if lk == "font-family":
                for fam in v.split(","):
                    fam = fam.strip().strip("'\"").lower()
                    if fam and fam not in FUENTES_INSTALADAS:
                        avisos.append(f"fuente no instalada (rsvg usará un reemplazo): {fam}")

    texto_total = " ".join(textos)
    norm_total = normalizar_texto(texto_total)
    for req in requeridos:
        if normalizar_texto(req) not in norm_total:
            errores.append(f"falta el texto obligatorio: {req!r}")

    return {
        "ok": not errores,
        "errores": errores,
        "avisos": sorted(set(avisos)),
        "textos": texto_total,
        "bytes": len(datos),
    }


def rasterizar(ruta_svg: str | Path, ancho: int = 900, sufijo: str = "") -> Path:
    ruta_svg = Path(ruta_svg)
    if not shutil.which("rsvg-convert"):
        raise RuntimeError("rsvg-convert no está instalado")
    salida = ruta_svg.with_name(f"{ruta_svg.stem}{sufijo}.png")
    subprocess.run(
        ["rsvg-convert", "-w", str(ancho), "-b", "#0a0f1e", str(ruta_svg), "-o", str(salida)],
        check=True, capture_output=True, text=True,
    )
    return salida
