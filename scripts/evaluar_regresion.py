"""Evalúa una corrida de regresión de Cóndor v2 contra el ground truth del Nº 00.

Uso:  uv run python scripts/evaluar_regresion.py data/regresion-00.json
"""

import json
import re
import sys
from pathlib import Path

from condor.numeros import normalizar_texto, significativas

RAIZ = Path(__file__).resolve().parent.parent
# mismo conjunto que ESTADOS_RIESGO de condor/estado.py y de condor.workflow.js
RIESGO = {"no_verificable", "contradicho", "sin_consenso", "no_aplicado"}
SANO = {"confirmado", "matizado"}


def texto(b: dict) -> str:
    return " ".join(str(b.get(k) or "") for k in ("titulo", "bajada", "cuerpo"))


def estados_cifra(afs: list[dict], clave: str, cifra: str) -> set:
    return {a.get("estado_final") for a in afs if a["bloque"] == clave and cifra in significativas(a.get("cita_textual", ""))}


def evaluar(res: dict, gt: dict) -> list[dict]:
    finales = {b["clave"]: b for b in res["bloques"]}
    afs = res["afirmaciones"]
    salida = []
    for caso in gt["casos"]:
        veredicto, detalle = "FALLA", ""
        if caso["id"] in ("oracle_300k_gpus", "oracle_850mw"):
            # datos correctos: tienen que seguir publicados y confirmados
            perdidos, dudosos = [], []
            for clave in caso["bloques"]:
                estados = estados_cifra(afs, clave, caso["cifra"])
                if caso["cifra"] not in significativas(texto(finales[clave])):
                    perdidos.append(clave)
                elif not estados or not estados <= SANO:
                    dudosos.append(f"{clave}: {sorted(estados) or 'sin afirmación'}")
            if perdidos:
                detalle = f"se perdió un dato correcto en {', '.join(perdidos)}"
            elif dudosos:
                veredicto, detalle = "PARCIAL", f"presente pero {'; '.join(dudosos)} (falso positivo que va al checkpoint)"
            else:
                veredicto, detalle = "OK", "presente y confirmado"
        elif caso["id"] == "dsewiki_fechas":
            originales = {b["clave"]: b for b in res.get("bloques_originales", [])}
            malos, sin_bueno = [], []
            for clave in caso["bloques"]:
                t = normalizar_texto(texto(finales[clave]))
                if re.search(caso["patron_malo"], t):
                    estados = {a.get("estado_final") for a in afs if a["bloque"] == clave
                               and re.search(caso["patron_malo"], normalizar_texto(a.get("cita_textual", "")))}
                    malos.append((clave, estados))
                elif re.search(caso["patron_malo"], normalizar_texto(texto(originales.get(clave, {})))) and caso["texto_bueno"] not in t:
                    sin_bueno.append(clave)
            if malos and all(e and e <= RIESGO for _, e in malos):
                veredicto, detalle = "PARCIAL", "sigue el 11 de mayo como inicio pero marcado " + "; ".join(f"{c}: {sorted(e)}" for c, e in malos)
            elif malos:
                detalle = "sigue el 11 de mayo como inicio de DSEwiki: " + "; ".join(f"{c}: {sorted(e) or 'sin afirmación'}" for c, e in malos)
            elif sin_bueno:
                veredicto, detalle = "PARCIAL", f"sacó el inicio equivocado pero no puso el 24 de mayo en {', '.join(sin_bueno)}"
            else:
                veredicto, detalle = "OK", "inicio corregido al 24 de mayo"
        elif caso["id"] == "dsewiki_ediciones":
            malos = []
            for clave in caso["bloques"]:
                sig_t = significativas(texto(finales[clave]))
                if caso["cifra_mala"] in sig_t and caso["cifra_buena"] not in sig_t:
                    malos.append((clave, estados_cifra(afs, clave, caso["cifra_mala"])))
            if not malos:
                veredicto, detalle = "OK", "17.000 en DSEwiki (o las 18.000 ya no se atribuyen sólo a DSEwiki)"
            elif all(e and e <= RIESGO for _, e in malos):
                veredicto, detalle = "PARCIAL", "siguen las 18.000 solas pero marcadas " + "; ".join(f"{c}: {sorted(e)}" for c, e in malos)
            else:
                detalle = "siguen las 18.000 atribuidas a DSEwiki: " + "; ".join(f"{c}: {sorted(e) or 'sin afirmación'}" for c, e in malos)
        elif caso["id"] == "nightingale":
            t = texto(finales["safety"])
            estados = {a.get("estado_final") for a in afs if a["bloque"] == "safety" and "nightingale" in normalizar_texto(a.get("cita_textual", "") + a.get("valor", ""))}
            if caso["texto_bueno"] in t and estados and estados <= SANO:
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
