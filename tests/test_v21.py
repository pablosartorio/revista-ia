"""v2.1: consolidación de fallos, ids del libro en la prosa de los jueces, cifras por valor, importar del envoltorio."""

import json

from condor import estado
from condor.importar import importar
from condor.numeros import es_significativa, quitar_ids, significativas
from condor.render import render_borrador


def _datos(entorno):
    return json.loads((entorno["data"] / "numero-99.json").read_text(encoding="utf-8"))


def _guardar(entorno, d):
    (entorno["data"] / "numero-99.json").write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")


def _tipos(clave):
    return [r["tipo"] for r in estado.riesgos_bloque(estado.cargar("99"), clave)]


# --------------------------------------------------------------------------- números

def test_agrupacion_de_miles_nunca_es_un_anio():
    assert es_significativa("2.000") and es_significativa("1,950")
    assert not es_significativa("1950")
    assert significativas("En 1950 hubo 1.950 casos y 2.000 heridos") == {"1950", "2000"}


def test_quitar_ids_del_libro():
    assert significativas(quitar_ids("feature#17: más de 1.000 MW; ver ciencia_salud#3")) == {"1000"}


def test_cifras_de_una_afirmacion_salen_del_valor():
    a = {"valor": "850 MW", "cita_textual": "Oracle sumó 850 MW y 300.000 GPUs"}
    assert estado.cifras_afirmacion(a) == {"850"}
    # si el valor no tiene cifras de la cita (paráfrasis), cuenta la cita
    assert estado.cifras_afirmacion({"valor": "5 mil millones", "cita_textual": "USD 5.000 millones"}) == {"5000"}


# --------------------------------------------------------------------------- ids en la prosa del juez

def test_id_en_la_prosa_no_habilita_una_cifra_a_retirar(entorno):
    d = _datos(entorno)
    d["bloques"][0]["cuerpo"] = "Oracle sumó 850 MW. Hay 17 proyectos en carpeta."
    d["versiones"]["investigacion"]["feature"]["cuerpo"] = d["bloques"][0]["cuerpo"]
    d["resoluciones"].append({"conflicto_id": "C1", "decision": "retirar", "bloques": ["feature"], "cifras": ["17"],
                              "valor_correcto": "", "redaccion_sugerida": "Sacar el dato de feature#17.",
                              "afirmaciones_afectadas": [], "bloques_pendientes": []})
    _guardar(entorno, d)
    assert "fallo_cifra_sigue_en_texto" in _tipos("feature")


def test_id_en_la_prosa_no_hace_trazable_una_cifra(entorno):
    d = _datos(entorno)
    d["bloques"][1]["cuerpo"] = "Oracle sumó 850 MW en 17 sitios."
    d["resoluciones"].append({"conflicto_id": "C1", "decision": "matizar", "bloques": ["hardware"],
                              "valor_correcto": "", "redaccion_sugerida": "Aclarar la fuente (hardware#17).",
                              "afirmaciones_afectadas": [], "bloques_pendientes": []})
    _guardar(entorno, d)
    assert "cifras_sin_trazabilidad" in _tipos("hardware")


# --------------------------------------------------------------------------- consolidación

def _con_consolidacion(entorno, decision="corregir"):
    d = _datos(entorno)
    d["conflictos"] += [
        {"id": "C1", "tipo": "cronologia", "bloques": ["feature", "hardware"], "afirmaciones": ["feature#1"], "descripcion": "a"},
        {"id": "C2", "tipo": "valor", "bloques": ["feature"], "afirmaciones": ["feature#1"], "descripcion": "b"},
    ]
    d["resoluciones"].append({"conflicto_id": "K1", "conflictos_cubiertos": ["C1", "C2"], "decision": decision,
                              "bloques": ["feature", "hardware"], "afirmaciones_afectadas": ["feature#1"],
                              "valor_correcto": "850 MW", "redaccion_sugerida": "Oracle sumó 850 MW.",
                              "razonamiento": "r", "confianza": "alta", "bloques_pendientes": [], "aplicada": True})
    d["consolidacion"] = {"componentes": [{"id": "K1", "conflictos": ["C1", "C2"]}], "reemplazadas": [
        {"conflicto_id": "C1", "decision": "corregir", "valor_correcto": "cuatro semanas", "consolidado_en": "K1"},
        {"conflicto_id": "C2", "decision": "corregir", "valor_correcto": "seis semanas", "consolidado_en": "K1"},
    ]}
    _guardar(entorno, d)


def test_conflicto_cubierto_por_una_consolidada_esta_resuelto(entorno):
    _con_consolidacion(entorno)
    assert "conflicto_sin_resolver" not in _tipos("feature")
    assert "conflicto_sin_resolver" not in _tipos("hardware")


def test_consolidada_sin_consenso_sigue_siendo_riesgo(entorno):
    _con_consolidacion(entorno, decision="sin_consenso")
    assert _tipos("feature").count("conflicto_sin_consenso") == 2


def test_revision_muestra_la_consolidacion(entorno):
    _con_consolidacion(entorno)
    estado.iniciar_revision("99")
    revision = render_borrador("99")[1].read_text(encoding="utf-8")
    assert "Consolidado en K1" in revision and "seis semanas" in revision


# --------------------------------------------------------------------------- importar

def test_importar_desenvuelve_el_output_del_workflow(entorno, tmp_path):
    d = _datos(entorno)
    d["numero"] = "8"
    ruta = tmp_path / "tarea.output"
    ruta.write_text(json.dumps({"summary": "ok", "logs": ["a", "b"], "result": d}), encoding="utf-8")
    destino = importar(ruta)
    assert destino.name == "numero-08.json"
