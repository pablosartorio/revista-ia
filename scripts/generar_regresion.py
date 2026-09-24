"""Genera tests/fixtures/numero-00-original.json y pipeline/regresion-00.workflow.js.

El fixture es el Nº 00 TAL COMO LO ESCRIBIÓ la redacción v1 (antes de la corrección manual
del 13/09), tomado de data/raw_by_label.json. Se embebe en el script del workflow para no
transcribirlo a mano (los workflows no tienen acceso a disco).

Con --desde-cierre genera en cambio pipeline/regresion-00-cierre.workflow.js: una regresión
barata (~12 agentes) que reusa el libro de afirmaciones, los conflictos, los fallos y los
debates de una corrida completa (data/regresion-00.json) y corre sólo consolidar → cierre.

Uso: uv run python scripts/generar_regresion.py [--desde-cierre [corrida.json]]
"""
import json
import sys
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


# lo que agregó el cierre de la corrida anterior: se descarta para volver a correrlo
_DE_CIERRE_AF = ("estado_final", "resolucion", "valor_final")
_DE_CIERRE_RES = ("bloques_pendientes", "aplicada")


def desde_cierre(corrida: Path):
    res = json.loads(corrida.read_text(encoding="utf-8"))
    semilla = {
        "origen": f"{corrida.relative_to(RAIZ)} (consolidar + cierre sobre su libro, conflictos, fallos y debates)",
        "bloques": res["bloques_originales"],
        "afirmaciones": [{k: v for k, v in a.items() if k not in _DE_CIERRE_AF} for a in res["afirmaciones"]],
        "conflictos": res["conflictos"],
        "resoluciones": [{k: v for k, v in r.items() if k not in _DE_CIERRE_RES} for r in res["resoluciones"]],
        "debates": res["debates"],
        "contexto_omitido": res["contexto_omitido"],
    }
    script = f"""export const meta = {{
  name: 'condor-regresion-00-cierre',
  description: 'Regresión barata de Cóndor v2.1 sobre el Nº 00: consolidar → cierre con los fallos de una corrida completa',
  phases: [{{ title: 'Regresión', detail: 'consolidar → cierre sobre el libro y los fallos guardados' }}],
}}

// generado por scripts/generar_regresion.py --desde-cierre — no editar a mano
const S = {json.dumps(semilla, ensure_ascii=False)}
const E = `${{args.raiz}}/pipeline/etapas`
phase('Regresión')
log(`Regresión desde el cierre: ${{S.resoluciones.length}} fallos, ${{S.afirmaciones.length}} afirmaciones (${{S.origen}}).`)
const con = await workflow({{ scriptPath: `${{E}}/consolidar.workflow.js` }}, {{ bloques: S.bloques, afirmaciones: S.afirmaciones, conflictos: S.conflictos, resoluciones: S.resoluciones, debates: S.debates }})
const cie = await workflow({{ scriptPath: `${{E}}/cierre.workflow.js` }}, {{ bloques: S.bloques, afirmaciones: S.afirmaciones, resoluciones: con.resoluciones, conflictos: S.conflictos, contexto_omitido: S.contexto_omitido }})
return {{
  bloques_originales: S.bloques,
  bloques: cie.bloques,
  afirmaciones: cie.afirmaciones,
  contexto_omitido: S.contexto_omitido,
  grupos: [], conflictos: S.conflictos, resoluciones: cie.resoluciones, debates: S.debates,
  consolidacion: {{ componentes: con.componentes, reemplazadas: con.reemplazadas }},
  descartados: [], candidatos_deterministicos: [],
  correcciones: cie.correcciones,
  guardas: [...con.guardas, ...cie.guardas],
}}
"""
    destino = RAIZ / "pipeline/regresion-00-cierre.workflow.js"
    destino.write_text(script, encoding="utf-8")
    print(f"ok: {destino.relative_to(RAIZ)} ({len(script) // 1024} KB)")


if __name__ == "__main__":
    if "--desde-cierre" in sys.argv:
        resto = sys.argv[sys.argv.index("--desde-cierre") + 1:]
        desde_cierre(Path(resto[0]).resolve() if resto else RAIZ / "data/regresion-00.json")
    else:
        main()
