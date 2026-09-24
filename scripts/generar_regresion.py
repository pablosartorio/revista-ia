"""Genera tests/fixtures/numero-00-original.json y pipeline/regresion-00.workflow.js.

El fixture es el Nº 00 TAL COMO LO ESCRIBIÓ la redacción v1 (antes de la corrección manual
del 13/09), tomado de data/raw_by_label.json. Se embebe en el script del workflow para no
transcribirlo a mano (los workflows no tienen acceso a disco).

Uso: uv run python scripts/generar_regresion.py
"""
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
TIT = {"llm": "Modelos fundacionales y LLMs", "hardware": "Hardware e infraestructura",
       "politica": "Regulación y política", "safety": "Seguridad y alineación"}


def main():
    raw = json.loads((RAIZ / "data/raw_by_label.json").read_text(encoding="utf-8"))
    f = raw["feature:nota-de-fondo"][0]
    bloques = [{"clave": "feature", "tipo": "feature", "seccion": "Nota de fondo", "titulo": f["titulo"],
                "bajada": f["bajada"], "cuerpo": f["cuerpo"], "fuente_nombre": "", "fuente_url": "",
                "fecha": "12 de septiembre de 2026", "open_weight": "no aplica", "fuentes": f.get("fuentes", [])}]
    for clave in ("hardware", "safety", "politica", "llm"):
        it = raw[f"seccion:{clave}"][0]
        bloques.append({"clave": clave, "tipo": "seccion", "seccion": TIT[clave], "titulo": it["titulo"], "bajada": "",
                        "cuerpo": it["cuerpo"], "fuente_nombre": it["fuente_nombre"], "fuente_url": it["fuente_url"],
                        "fecha": it["fecha"], "open_weight": it["open_weight"], "fuentes": []})
    fixture = {"descripcion": "Nº 00 original (pre-corrección manual del 13/09), bloques con errores conocidos + un control (llm)",
               "bloques": bloques}
    (RAIZ / "tests/fixtures/numero-00-original.json").write_text(json.dumps(fixture, ensure_ascii=False, indent=2), encoding="utf-8")
    plantilla = (RAIZ / "pipeline/regresion-00.workflow.js").read_text(encoding="utf-8")
    inicio = plantilla.index("const FIXTURE = ")
    fin = plantilla.index("\n", inicio)
    nuevo = plantilla[:inicio] + "const FIXTURE = " + json.dumps(fixture, ensure_ascii=False) + plantilla[fin:]
    (RAIZ / "pipeline/regresion-00.workflow.js").write_text(nuevo, encoding="utf-8")
    print("ok")


if __name__ == "__main__":
    main()
