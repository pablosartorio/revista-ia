"""Editor/a digital (CMS): arma borrador, paquete de revisión y versión publicada.

No toma decisiones editoriales. Todo lo que muestra sale de `data/numero-XX.json`
(lo que produjo el workflow) y de `data/numero-XX.revision.json` (lo que decidió
la persona que revisa).
"""

import difflib
import html
import re
import subprocess
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .estado import (
    ESTADOS_RIESGO, ErrorCheckpoint, candidatos_tapa, cargar, cargar_revision, dir_salida, estado_final,
    hash_archivo, resumen, revision_vacia,
)

PLANTILLAS = Path(__file__).resolve().parent / "templates"

ACENTO = {
    "llm": "#6366f1", "hardware": "#f59e0b", "politica": "#ef4444", "safety": "#f97316",
    "ciencia_salud": "#10b981", "industria_robotica": "#3b82f6", "argentina": "#8b5cf6",
    "latam": "#14b8a6", "espacio": "#0ea5e9", "feature": "#e2e8f0",
}
SIGLA = {
    "llm": "LLM", "hardware": "HW", "politica": "POL", "safety": "SEC", "ciencia_salud": "SCI",
    "industria_robotica": "IND", "argentina": "AR", "latam": "LATAM", "espacio": "ESP", "feature": "TAPA",
}
ETIQUETA_ESTADO = {
    "confirmado": "confirmada", "corregido": "corregida", "matizado": "matizada", "retirado": "retirada",
    "no_verificable": "no verificable", "contradicho": "contradicha", "sin_consenso": "sin consenso",
    "no_aplicado": "con corrección no aplicada",
}


def _env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(PLANTILLAS)),
        autoescape=select_autoescape(["html.j2", "html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["parrafos"] = lambda s: [p.strip() for p in re.split(r"\n\s*\n", s or "") if p.strip()]
    return env


def diff_html(antes: str, despues: str) -> str:
    """Diff por palabras, listo para insertar (ya escapado)."""
    a = re.split(r"(\s+)", antes or "")
    b = re.split(r"(\s+)", despues or "")
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if op == "equal":
            out.append(html.escape("".join(a[i1:i2])))
        if op in ("delete", "replace"):
            out.append(f"<del>{html.escape(''.join(a[i1:i2]))}</del>")
        if op in ("insert", "replace"):
            out.append(f"<ins>{html.escape(''.join(b[j1:j2]))}</ins>")
    return "".join(out)


def _contexto(numero: str, datos: dict, rev: dict, borrador: bool) -> dict:
    res = resumen(numero, datos, rev)
    decisiones = rev.get("decisiones", {})
    retirados = {c for c, d in decisiones.items() if d["accion"] == "retirar"}

    afirmaciones_por_bloque: dict[str, list] = {}
    for a in datos.get("afirmaciones", []):
        a = dict(a, estado_final=estado_final(a))
        afirmaciones_por_bloque.setdefault(a["bloque"], []).append(a)

    bloques = []
    for b in datos["bloques"]:
        if not borrador and b["clave"] in retirados:
            continue
        bloques.append(dict(
            b,
            acento=ACENTO.get(b["clave"], "#94a3b8"),
            sigla=SIGLA.get(b["clave"], "?"),
            afirmaciones=afirmaciones_por_bloque.get(b["clave"], []),
            retirado=b["clave"] in retirados,
        ))
    feature = next((b for b in bloques if b.get("tipo") == "feature"), None)
    secciones = [b for b in bloques if b.get("tipo") != "feature"]

    publicadas = [a for b in bloques for a in b["afirmaciones"]]
    conteo = {}
    for a in publicadas:
        conteo[a["estado_final"]] = conteo.get(a["estado_final"], 0) + 1
    aceptadas = [a for a in publicadas if a["estado_final"] in ESTADOS_RIESGO]

    return {
        "numero": numero,
        "meta": datos.get("meta", {}),
        "feature": feature,
        "secciones": secciones,
        "borrador": borrador,
        "resumen": res,
        "verificacion": {
            "total": len(publicadas),
            "conteo": conteo,
            "etiquetas": ETIQUETA_ESTADO,
            "aceptadas_por_editor": aceptadas,
            "conflictos": len(datos.get("conflictos", [])),
        },
    }


def render_borrador(numero: str) -> list[Path]:
    datos = cargar(numero)
    rev = cargar_revision(numero) or revision_vacia(numero)
    salida = dir_salida(numero)
    salida.mkdir(parents=True, exist_ok=True)
    env = _env()

    ctx = _contexto(numero, datos, rev, borrador=True)
    sugerida = next((c for c in candidatos_tapa(datos) if c["id"] == (datos.get("tapa") or {}).get("ganador")), None)
    elegida_id = (rev.get("tapa") or {}).get("candidato")
    elegida = next((c for c in candidatos_tapa(datos) if c["id"] == elegida_id), None) or sugerida
    ctx["tapa_src"] = elegida["png"] if elegida else None
    (salida / "borrador.html").write_text(env.get_template("issue.html.j2").render(**ctx), encoding="utf-8")

    originales = datos.get("versiones", {}).get("investigacion", {})
    diffs = {}
    for b in datos["bloques"]:
        o = originales.get(b["clave"])
        if o:
            diffs[b["clave"]] = {
                "titulo": diff_html(o.get("titulo", ""), b.get("titulo", "")),
                "bajada": diff_html(o.get("bajada", ""), b.get("bajada", "")),
                "cuerpo": diff_html(o.get("cuerpo", ""), b.get("cuerpo", "")),
                "cambio": tuple(o.get(k) or "" for k in ("titulo", "bajada", "cuerpo"))
                != tuple(b.get(k) or "" for k in ("titulo", "bajada", "cuerpo")),
            }
    filas = {f["clave"]: f for f in ctx["resumen"]["filas"]}
    ctx.update(
        todos=[dict(b, fila=filas[b["clave"]], diff=diffs.get(b["clave"])) for b in
               ([ctx["feature"]] if ctx["feature"] else []) + ctx["secciones"]],
        conflictos=datos.get("conflictos", []),
        resoluciones={r["conflicto_id"]: r for r in datos.get("resoluciones", [])},
        debates={d["conflicto_id"]: d for d in datos.get("debates", [])},
        correcciones=datos.get("correcciones", []),
        guardas=datos.get("guardas", []),
        descartados=datos.get("descartados", []),
        contexto_omitido=datos.get("contexto_omitido", []),
        tapa=datos.get("tapa") or {},
        tapa_elegida_id=elegida_id,
    )
    (salida / "revision.html").write_text(env.get_template("revision.html.j2").render(**ctx), encoding="utf-8")
    return [salida / "borrador.html", salida / "revision.html"]


def render_final(numero: str, datos: dict | None = None, rev: dict | None = None,
                 revisor: str | None = None) -> list[Path]:
    from .svg import rasterizar

    datos = datos or cargar(numero)
    rev = rev or cargar_revision(numero)
    salida = dir_salida(numero)
    salida.mkdir(parents=True, exist_ok=True)
    env = _env()

    # la tapa publicada sale de los bytes aprobados (copia con nombre por contenido), y el PNG
    # se genera acá desde ese SVG: nunca se copia un PNG que nadie aprobó
    elegida = salida / rev["tapa"]["archivo"]
    contenido = elegida.read_bytes()
    svg = salida / "tapa.svg"
    svg.write_bytes(contenido)
    if hash_archivo(svg) != rev["tapa"]["hash_svg"]:
        raise ErrorCheckpoint("la tapa a publicar no coincide con la aprobada")
    png = salida / "tapa.png"
    png.unlink(missing_ok=True)
    try:
        rasterizar(svg, 1200)
    except (RuntimeError, OSError, subprocess.CalledProcessError):
        pass  # sin rsvg-convert se publica sólo el SVG

    ctx = _contexto(numero, datos, rev, borrador=False)
    ctx["tapa_src"] = "tapa.png" if png.exists() else "tapa.svg"
    ctx["revisor"] = revisor
    (salida / "index.html").write_text(env.get_template("issue.html.j2").render(**ctx), encoding="utf-8")
    (salida / "index.md").write_text(env.get_template("issue.md.j2").render(**ctx), encoding="utf-8")
    return [salida / "index.html", salida / "index.md", svg] + ([png] if png.exists() else [])
