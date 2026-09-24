#!/usr/bin/env python3
"""
Editor/a digital (CMS) de Cóndor.

No toma decisiones editoriales: recibe el JSON ya redactado, verificado (fact-check)
y con directivas de dirección de arte, y renderiza el número final en Markdown y HTML.

Uso:
    uv run scripts/build_issue.py data/numero-00.json
"""
import json
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parent.parent

ACCENT_BY_SECTION = {
    "llm": "#6366f1",
    "hardware": "#f59e0b",
    "politica": "#ef4444",
    "safety": "#f97316",
    "ciencia_salud": "#10b981",
    "industria_robotica": "#3b82f6",
    "argentina": "#8b5cf6",
    "latam": "#14b8a6",
    "espacio": "#0ea5e9",
}

SIGLA_BY_SECTION = {
    "llm": "LLM",
    "hardware": "HW",
    "politica": "POL",
    "safety": "SEC",
    "ciencia_salud": "SCI",
    "industria_robotica": "IND",
    "argentina": "AR",
    "latam": "LATAM",
    "espacio": "ESP",
}

ESTADO_LABEL = {
    "confirmado": "✓ verificado",
    "no_verificable": "⚠ no verificable de forma independiente",
    "contradicho": "✗ contradicho — excluido",
}


def load_issue(json_path: Path) -> dict:
    data = json.loads(json_path.read_text(encoding="utf-8"))
    return data


def enrich(data: dict) -> dict:
    """Agrega color de acento / sigla a cada sección, y descarta ítems contradichos."""
    secciones_ok = []
    for s in data.get("secciones", []):
        key = s.get("clave", "")
        estado = (s.get("factcheck") or {}).get("estado", "no_verificable")
        if estado == "contradicho":
            # se excluye del número, pero queda registrado para el log editorial
            data.setdefault("descartados", []).append(s)
            continue
        s["color_acento"] = ACCENT_BY_SECTION.get(key, "#94a3b8")
        s["sigla"] = SIGLA_BY_SECTION.get(key, "?")
        s["estado_label"] = ESTADO_LABEL.get(estado, estado)
        secciones_ok.append(s)
    data["secciones"] = secciones_ok

    if data.get("feature"):
        fc = data["feature"].get("factcheck") or []
        contradichos = [v for v in fc if v.get("estado") == "contradicho"]
        data["feature"]["tiene_contradichos"] = bool(contradichos)

    return data


def main():
    if len(sys.argv) != 2:
        print("Uso: build_issue.py <ruta-al-json-del-numero>", file=sys.stderr)
        sys.exit(1)

    json_path = Path(sys.argv[1])
    numero_id = json_path.stem  # ej: "numero-00"

    data = enrich(load_issue(json_path))

    env = Environment(
        loader=FileSystemLoader(str(ROOT / "scripts" / "templates")),
        trim_blocks=True,
        lstrip_blocks=True,
    )

    out_dir = ROOT / "output" / numero_id
    out_dir.mkdir(parents=True, exist_ok=True)

    md = env.get_template("issue.md.j2").render(**data)
    (out_dir / "index.md").write_text(md, encoding="utf-8")

    html = env.get_template("issue.html.j2").render(**data)
    (out_dir / "index.html").write_text(html, encoding="utf-8")

    print(f"OK -> {out_dir}/index.md")
    print(f"OK -> {out_dir}/index.html")
    if data.get("descartados"):
        print(f"Nota: {len(data['descartados'])} sección(es) excluida(s) por fact-check contradicho:")
        for s in data["descartados"]:
            print(f"  - {s.get('seccion')}: {s.get('factcheck', {}).get('nota')}")


if __name__ == "__main__":
    main()
