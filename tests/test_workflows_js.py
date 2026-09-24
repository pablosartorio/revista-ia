"""Las etapas cierre y consolidar corridas con node y un `agent` simulado (respuestas fijas por label)."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(not shutil.which("node"), reason="sin node")


def correr(etapa: str, args: dict, respuestas: dict) -> dict:
    entrada = {"script": str(RAIZ / f"pipeline/etapas/{etapa}.workflow.js"), "args": args, "respuestas": respuestas}
    out = subprocess.run(["node", str(RAIZ / "tests/js/correr_workflow.mjs")], input=json.dumps(entrada),
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def bloque(clave, cuerpo, titulo="Título", tipo="seccion"):
    return {"clave": clave, "tipo": tipo, "titulo": titulo, "bajada": "", "cuerpo": cuerpo}


def af(id_, valor, cita, tipo="cifra", estado="confirmado"):
    return {"id": id_, "bloque": id_.split("#")[0], "texto": cita, "tipo": tipo, "entidad": "x", "valor": valor,
            "cita_textual": cita, "veredicto": {"estado": estado, "evidencia": [{"url": "https://e.com", "cita": "c"}]}}


def fallo(cid, decision, ids, bloques, vc="", rs="", cifras=()):
    return {"conflicto_id": cid, "decision": decision, "afirmaciones_afectadas": ids, "bloques": bloques,
            "cifras": list(cifras), "valor_correcto": vc, "redaccion_sugerida": rs, "razonamiento": "r",
            "confianza": "alta", "evidencia": []}


def editor(b, cuerpo):
    return {"titulo": b["titulo"], "bajada": b["bajada"], "cuerpo": cuerpo, "cambios": []}


def cierre(bloques, afirmaciones, resoluciones, respuestas, contexto=()):
    return correr("cierre", {"bloques": bloques, "afirmaciones": afirmaciones, "resoluciones": resoluciones,
                             "conflictos": [], "contexto_omitido": list(contexto)}, respuestas)["result"]


def bloqueantes(res):
    return [g for g in res["guardas"] if g["severidad"] == "bloqueante"]


# --------------------------------------------------------------------------- cierre

FEAT = bloque("feature", "Los 18.000 edits que los agentes hicieron en DseWiki muestran el patrón. Los data centers suman más de 1.000 MW.", tipo="feature")
AF_FEAT = [af("feature#13", "18.000 edits", "Los 18.000 edits que los agentes hicieron en DseWiki"),
           af("feature#17", "más de 1.000 MW", "más de 1.000 MW")]
# el juez escribe prosa en valor_correcto, con la cifra vieja adentro y un id del libro
C1 = fallo("C1", "corregir", ["feature#13"], ["feature"],
           vc="Unas 17.000 ediciones en DseWiki. Las cerca de 18.000 son el total de todos los sitios (no confundir con feature#17).",
           rs="Los agentes hicieron unas 17.000 ediciones en DseWiki, dentro de un total de cerca de 18.000.")


def test_cierre_acepta_valor_correcto_en_prosa():
    nuevo = "Las unas 17.000 ediciones que los agentes hicieron en DseWiki, de cerca de 18.000 en total, muestran el patrón. Los data centers suman más de 1.000 MW."
    res = cierre([FEAT], AF_FEAT, [C1], {"cierre:feature": editor(FEAT, nuevo)})
    assert not bloqueantes(res), res["guardas"]
    assert res["resoluciones"][0]["aplicada"]
    assert next(a for a in res["afirmaciones"] if a["id"] == "feature#13")["estado_final"] == "corregido"


def test_cierre_sin_el_valor_correcto_no_se_aplica():
    res = cierre([FEAT], AF_FEAT, [C1], {"cierre:feature": editor(FEAT, FEAT["cuerpo"]), "cierre+:feature": editor(FEAT, FEAT["cuerpo"])})
    g = bloqueantes(res)
    assert g and "17000" in g[0]["detalle"] and "17," not in g[0]["detalle"].replace("17000", "")
    assert next(a for a in res["afirmaciones"] if a["id"] == "feature#13")["estado_final"] == "no_aplicado"


SAFETY = bloque("safety", "El grupo Nightingale Collective publicó el informe con 120 páginas.")
AF_NOMBRE = [af("safety#1", "Nightingale Collective", "El grupo Nightingale Collective publicó el informe", tipo="nombre")]
C2 = fallo("C2", "corregir", ["safety#1"], ["safety"], vc="Nightingale Research", rs="El grupo Nightingale Research publicó el informe.")


def test_corregir_un_nombre_exige_que_cambie():
    res = cierre([SAFETY], AF_NOMBRE, [C2], {"cierre:safety": editor(SAFETY, SAFETY["cuerpo"]), "cierre+:safety": editor(SAFETY, SAFETY["cuerpo"])})
    assert bloqueantes(res) and "Nightingale Collective" in bloqueantes(res)[0]["detalle"]
    ok = cierre([SAFETY], AF_NOMBRE, [C2], {"cierre:safety": editor(SAFETY, SAFETY["cuerpo"].replace("Collective", "Research"))})
    assert not bloqueantes(ok)


POL = bloque("politica", "El contrato incluye una cláusula de tasas de rechazo mínimas, según documentos del Pentágono.")
CTX = {"bloque": "politica", "descripcion": "OpenAI niega haber aceptado la cláusula de tasas de rechazo mínimas", "url": "https://e.com"}


def test_matizar_exige_agregar_el_contexto():
    res = cierre([POL], [], [], {"cierre:politica": editor(POL, POL["cuerpo"]), "cierre+:politica": editor(POL, POL["cuerpo"])}, [CTX])
    assert bloqueantes(res)
    ok = cierre([POL], [], [], {"cierre:politica": editor(POL, POL["cuerpo"] + " OpenAI niega haberla aceptado.")}, [CTX])
    assert not bloqueantes(ok)


def test_retirar_no_se_salva_por_la_cita_ajena_de_otra_afirmacion():
    hw = bloque("hardware", "Oracle sumó 850 MW y 300.000 GPUs en el trimestre.")
    afs = [af("hardware#1", "850 MW", "sumó 850 MW"),
           # el extractor copió la oración entera como cita de otro dato
           af("hardware#2", "300.000 GPUs", "Oracle sumó 850 MW y 300.000 GPUs")]
    r = fallo("C3", "retirar", ["hardware#1"], ["hardware"])
    quedo = "Oracle informó 850 MW y 300.000 GPUs en el trimestre."
    res = cierre([hw], afs, [r], {"cierre:hardware": editor(hw, quedo), "cierre+:hardware": editor(hw, quedo)})
    assert bloqueantes(res) and "850" in bloqueantes(res)[0]["detalle"]


# --------------------------------------------------------------------------- consolidar

AFS_DSE = [af("feature#3", "seis semanas", "durante seis semanas"), af("feature#14", "42 días", "durante 42 días"),
           af("safety#4", "11 de mayo al 22 de junio", "entre el 11 de mayo y el 22 de junio"),
           af("hardware#1", "850 MW", "850 MW")]
BLOQUES_DSE = [bloque("feature", "Usaron la wiki durante seis semanas. Evadió el sandbox durante 42 días.", tipo="feature"),
               bloque("safety", "Usaron la wiki entre el 11 de mayo y el 22 de junio."),
               bloque("hardware", "Oracle sumó 850 MW.")]
FALLOS_DSE = [
    fallo("C3", "corregir", ["feature#3", "feature#14", "safety#4"], ["feature", "safety"], vc="24 de mayo al 22 de junio",
          rs="Usaron la wiki durante unas cuatro semanas, del 24 de mayo al 22 de junio."),
    fallo("C4", "corregir", ["feature#14"], ["feature"], vc="seis semanas", rs="Durante unas seis semanas, del 11 de mayo al 22 de junio."),
    fallo("C5", "corregir", ["hardware#1"], ["hardware"], vc="870 MW", rs="Oracle sumó 870 MW."),
    fallo("C6", "mantener", ["feature#3"], ["feature"]),
]


def consolidar(respuestas):
    return correr("consolidar", {"bloques": BLOQUES_DSE, "afirmaciones": AFS_DSE, "conflictos": [],
                                 "resoluciones": FALLOS_DSE, "debates": []}, respuestas)


def juez(**cambios):
    r = {"decision": "corregir", "valor_correcto": "24 de mayo al 22 de junio de 2026",
         "redaccion_sugerida": "Usaron la wiki durante unas cuatro semanas, del 24 de mayo al 22 de junio de 2026.",
         "afirmaciones_afectadas": ["feature#3", "feature#14", "safety#4"], "confianza": "alta",
         "razonamiento": "C3 tiene la cronología con evidencia", "evidencia": []}
    r.update(cambios)
    return r


def test_consolidar_une_los_fallos_que_comparten_afirmaciones():
    out = consolidar({"consolidar:K1": juez()})
    assert out["labels"] == ["consolidar:K1"]
    res = out["result"]
    assert [r["conflicto_id"] for r in res["resoluciones"]] == ["K1", "C5", "C6"]
    k1 = res["resoluciones"][0]
    assert k1["conflictos_cubiertos"] == ["C3", "C4"] and set(k1["bloques"]) == {"feature", "safety"}
    assert [r["consolidado_en"] for r in res["reemplazadas"]] == ["K1", "K1"]
    assert not bloqueantes(res)


def test_consolidacion_que_no_cubre_todo_deja_los_originales_y_bloquea():
    res = consolidar({"consolidar:K1": juez(afirmaciones_afectadas=["feature#3", "feature#14"])})["result"]
    assert [r["conflicto_id"] for r in res["resoluciones"]] == ["C3", "C4", "C5", "C6"]
    assert {g["bloque"] for g in bloqueantes(res)} == {"feature", "safety"}
    assert "safety#4" in bloqueantes(res)[0]["detalle"]


def test_consolidacion_con_cifras_inventadas_no_se_usa():
    res = consolidar({"consolidar:K1": juez(redaccion_sugerida="Usaron la wiki durante 35 días.")})["result"]
    assert "K1" not in [r["conflicto_id"] for r in res["resoluciones"]]
    assert "35" in bloqueantes(res)[0]["detalle"]


def test_consolidacion_caida_deja_los_originales():
    res = consolidar({})["result"]
    assert [r["conflicto_id"] for r in res["resoluciones"]] == ["C3", "C4", "C5", "C6"]
    assert bloqueantes(res)


def test_sin_fallos_compartidos_no_lanza_agentes():
    out = correr("consolidar", {"bloques": BLOQUES_DSE, "afirmaciones": AFS_DSE, "conflictos": [],
                                "resoluciones": FALLOS_DSE[2:], "debates": []}, {})
    assert out["labels"] == [] and len(out["result"]["resoluciones"]) == 2


# --------------------------------------------------------------------------- orquestador con semilla

def test_orquestador_con_semilla_no_relanza_lo_investigado():
    sec = {"titulo": "T", "cuerpo": "Oracle sumó 850 MW.", "open_weight": "no aplica", "fuente_nombre": "F",
           "fuente_url": "https://e.com", "fecha": "2026-09-20"}
    args = {"numero": "1", "fecha_larga": "f", "semana_iso": "2026-W39", "ventana": "v", "raiz": str(RAIZ),
            "modelo_verificador": "sonnet", "etapas": str(RAIZ / "pipeline/etapas"),
            "semilla": {"origen": "prueba", "secciones": {"hardware": sec, "llm": dict(sec, fuente_url="")},
                        "feature": {"titulo": "F", "bajada": "b", "cuerpo": "Oracle sumó 850 MW.", "fuentes": []}}}
    entrada = {"script": str(RAIZ / "pipeline/condor.workflow.js"), "args": args, "respuestas": {}}
    out = json.loads(subprocess.run(["node", str(RAIZ / "tests/js/correr_workflow.mjs")], input=json.dumps(entrada),
                                    capture_output=True, text=True, check=True).stdout)
    lanzadas = {l for l in out["labels"] if l.startswith(("seccion:", "feature:"))}
    # hardware viene de la semilla; llm no (le falta fuente_url) y se investiga; la feature se reusa
    assert "seccion:hardware" not in lanzadas and "seccion:llm" in lanzadas and "feature:nota-de-fondo" not in lanzadas
    assert out["result"]["numero"] == "01"
    assert out["result"]["meta"]["semilla"] == {"origen": "prueba", "beats_reusados": ["hardware"], "feature_reusada": True}


def test_fallo_se_aplica_solo_donde_estan_sus_afirmaciones():
    # C7 del Nº 01: el conflicto listaba politica y espacio, pero el juez matizó sólo politica#1;
    # mandarle el matiz a espacio lo hacía fallar y arrastraba la corrección propia de espacio (C2)
    pol = bloque("politica", "El jueves, dos representantes presentaron un proyecto.")
    esp = bloque("espacio", "El SAOCOM 1B estaba sobre 76,83°S.")
    afs = [af("politica#1", "el jueves", "El jueves, dos representantes presentaron", tipo="fecha"),
           af("espacio#2", "76,83°S", "sobre 76,83°S")]
    c7 = fallo("C7", "matizar", ["politica#1"], ["politica", "espacio"], rs="El jueves 17 de septiembre, dos representantes presentaron un proyecto.")
    c2 = fallo("C2", "corregir", ["espacio#2"], ["espacio"], vc="77,11°S", rs="El SAOCOM 1B estaba sobre 77,11°S.")
    out = correr("cierre", {"bloques": [pol, esp], "afirmaciones": afs, "resoluciones": [c7, c2], "conflictos": [], "contexto_omitido": []}, {
        "cierre:politica": editor(pol, "El jueves 17 de septiembre, dos representantes presentaron un proyecto."),
        "cierre:espacio": editor(esp, "El SAOCOM 1B estaba sobre 77,11°S."),
    })
    res = out["result"]
    assert not bloqueantes(res), res["guardas"]
    assert all(r["aplicada"] for r in res["resoluciones"])
    assert "cierre+:espacio" not in out["labels"]
