"""Arma la semilla de investigación (`args.semilla` de condor.workflow.js) desde el journal de una corrida.

Toma los resultados de las corresponsalías (`seccion:*`) y de la nota de fondo (`feature:nota-de-fondo`)
que ya entregaron, para relanzar el número sin volver a investigar. La verificación corre igual.

Uso:
  uv run python scripts/semilla_desde_journal.py <journal.jsonl> <salida.json> [--excluir espacio,...] [--sin-feature]
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

CAMPOS_SECCION = ("titulo", "cuerpo", "open_weight", "fuente_nombre", "fuente_url", "fecha")
CAMPOS_FEATURE = ("titulo", "bajada", "cuerpo", "fuentes")


def resultados_por_label(journal: Path) -> dict[str, dict]:
    etiquetas, resultados = {}, {}
    for linea in journal.read_text(encoding="utf-8").splitlines():
        if not linea.strip():
            continue
        e = json.loads(linea)
        if e.get("type") == "started":
            etiquetas[e["key"]] = e["label"]
        elif e.get("type") == "result" and e.get("result") is not None:
            resultados[etiquetas.get(e["key"], e["key"])] = e["result"]  # si hubo reintentos, gana el último
    return resultados


def semilla(journal: Path, excluir: set[str], con_feature: bool) -> dict:
    res = resultados_por_label(journal)
    secciones = {}
    for label, r in res.items():
        if not label.startswith("seccion:"):
            continue
        clave = label.split(":", 1)[1]
        faltan = [k for k in CAMPOS_SECCION if not r.get(k)]
        if clave in excluir or faltan:
            continue
        secciones[clave] = {k: r[k] for k in CAMPOS_SECCION}
    feature = res.get("feature:nota-de-fondo") if con_feature else None
    if feature and all(feature.get(k) for k in ("titulo", "cuerpo")):
        feature = {k: feature.get(k, [] if k == "fuentes" else "") for k in CAMPOS_FEATURE}
    else:
        feature = None
    fecha = datetime.fromtimestamp(journal.stat().st_mtime).strftime("%d/%m/%Y %H:%M")
    return {
        "origen": f"corrida interrumpida {journal.parent.name} ({fecha})",
        "secciones": dict(sorted(secciones.items())),
        "feature": feature,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("journal", type=Path)
    ap.add_argument("salida", type=Path)
    ap.add_argument("--excluir", default="", help="claves de beats a correr en vivo, separadas por coma")
    ap.add_argument("--sin-feature", action="store_true", help="no reusar la nota de fondo")
    a = ap.parse_args()
    s = semilla(a.journal, {x.strip() for x in a.excluir.split(",") if x.strip()}, not a.sin_feature)
    a.salida.parent.mkdir(parents=True, exist_ok=True)
    a.salida.write_text(json.dumps(s, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{a.salida}: {len(s['secciones'])} secciones ({', '.join(s['secciones'])})"
          f"{' + nota de fondo' if s['feature'] else ''} · origen: {s['origen']}")


if __name__ == "__main__":
    main()
