"""Evalúa una corrida de regresión de Cóndor v2 contra el ground truth del Nº 00.

Uso:  uv run python scripts/evaluar_regresion.py data/regresion-00.json
"""

import json
import sys
from pathlib import Path

from condor.numeros import normalizar_texto, significativas

RAIZ = Path(__file__).resolve().parent.parent
RIESGO = {"no_verificable", "contradicho", "sin_consenso"}


def texto(b: dict) -> str:
    return " ".join(str(b.get(k) or "") for k in ("titulo", "bajada", "cuerpo"))


def evaluar(res: dict, gt: dict) -> list[dict]:
    finales = {b["clave"]: b for b in res["bloques"]}
    afs = res["afirmaciones"]
    salida = []
    for caso in gt["casos"]:
        veredicto, detalle = "FALLA", ""
        if caso["id"] == "oracle_300k_gpus":
            problemas = []
            for clave in caso["bloques"]:
                if caso["cifra"] in significativas(texto(finales[clave])):
                    estados = {a.get("estado_final") for a in afs if a["bloque"] == clave and caso["cifra"] in significativas(a.get("cita_textual", ""))}
                    if not estados or not estados <= RIESGO:
                        problemas.append(f"{clave}: sigue publicada con estado {sorted(estados) or 'sin afirmación'}")
                    else:
                        problemas.append(f"{clave}: sigue en el texto pero marcada {sorted(estados)} (va al checkpoint)")
            if not problemas:
                veredicto, detalle = "OK", "retirada del texto en todos los bloques"
            elif all("va al checkpoint" in p for p in problemas):
                veredicto, detalle = "PARCIAL", "; ".join(problemas)
            else:
                detalle = "; ".join(problemas)
        elif caso["id"] == "oracle_850mw":
            clave = caso["bloques"][0]
            presente = caso["cifra"] in significativas(texto(finales[clave]))
            estados = {a.get("estado_final") for a in afs if a["bloque"] == clave and caso["cifra"] in significativas(a.get("cita_textual", ""))}
            if presente and estados and estados <= {"confirmado", "matizado"}:
                veredicto, detalle = "OK", f"presente, {sorted(estados)}"
            elif presente:
                veredicto, detalle = "PARCIAL", f"presente pero {sorted(estados)} (falso positivo que va al checkpoint)"
            else:
                detalle = "se perdió un dato correcto"
        elif caso["id"] == "dsewiki_fecha_fin":
            t = normalizar_texto(texto(finales["safety"]))
            malo, bueno = normalizar_texto(caso["texto_malo"]), normalizar_texto(caso["texto_bueno"])
            if bueno in t and malo not in t:
                veredicto, detalle = "OK", "corregida a 2 de julio"
            elif malo in t:
                estados = {a.get("estado_final") for a in afs if a["bloque"] == "safety" and malo in normalizar_texto(a.get("cita_textual", ""))}
                if estados and estados <= RIESGO:
                    veredicto, detalle = "PARCIAL", f"sigue '22 de junio' pero marcada {sorted(estados)}"
                else:
                    detalle = f"sigue '22 de junio' con estado {sorted(estados) or 'sin afirmación'}"
            else:
                veredicto, detalle = "PARCIAL", "sacó la fecha equivocada pero no puso la correcta"
        elif caso["id"] == "nightingale":
            t = texto(finales["safety"])
            estados = {a.get("estado_final") for a in afs if a["bloque"] == "safety" and "nightingale" in normalizar_texto(a.get("cita_textual", "") + a.get("valor", ""))}
            if caso["texto_bueno"] in t and estados and estados <= {"confirmado", "matizado"}:
                veredicto, detalle = "OK", f"se mantiene, {sorted(estados)}"
            elif caso["texto_bueno"] in t:
                veredicto, detalle = "PARCIAL", f"se mantiene pero {sorted(estados) or 'sin afirmación'} (falsa alarma al checkpoint)"
            else:
                detalle = "se retiró un dato correcto"
        elif caso["id"] == "openai_niega":
            t = normalizar_texto(texto(finales["politica"]))
            if any(m in t for m in caso["marcadores"]):
                veredicto, detalle = "OK", "el bloque incluye la negación de OpenAI"
            else:
                detalle = "falta la contraparte"
        elif caso["id"] == "feature_duracion":
            t = normalizar_texto(texto(finales["feature"]))
            quedan = [m for m in caso["textos_malos"] if normalizar_texto(m) in t]
            if not quedan:
                veredicto, detalle = "OK", "duración corregida o retirada"
            else:
                estados = {a.get("estado_final") for a in afs if a["bloque"] == "feature" and any(normalizar_texto(m) in normalizar_texto(a.get("cita_textual", "")) for m in quedan)}
                if estados and estados <= RIESGO:
                    veredicto, detalle = "PARCIAL", f"siguen {quedan} pero marcadas {sorted(estados)}"
                else:
                    detalle = f"siguen {quedan} con estado {sorted(estados) or 'sin afirmación'}"
        salida.append({"id": caso["id"], "veredicto": veredicto, "detalle": detalle, "descripcion": caso["descripcion"]})
    return salida


def main():
    res = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    gt = json.loads((RAIZ / "tests/fixtures/numero-00-gt.json").read_text(encoding="utf-8"))
    filas = evaluar(res, gt)
    for f in filas:
        print(f"{f['veredicto']:<8} {f['id']:<20} {f['detalle']}")
    ok = sum(f["veredicto"] == "OK" for f in filas)
    parcial = sum(f["veredicto"] == "PARCIAL" for f in filas)
    print(f"\n{ok} OK · {parcial} PARCIAL · {len(filas) - ok - parcial} FALLA  (de {len(filas)})")
    est = {}
    for a in res["afirmaciones"]:
        est[a.get("estado_final")] = est.get(a.get("estado_final"), 0) + 1
    print(f"afirmaciones: {len(res['afirmaciones'])} {est}")
    print(f"conflictos: {len(res['conflictos'])} · resoluciones: {len(res['resoluciones'])} · correcciones: {len(res['correcciones'])} · guardas: {len(res['guardas'])}")


if __name__ == "__main__":
    main()
