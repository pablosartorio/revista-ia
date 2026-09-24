import json

import pytest

from condor import estado
from condor.estado import ErrorCheckpoint
from condor.render import render_borrador



def _editar_bloque(entorno, clave, **cambios):
    ruta = entorno["data"] / "numero-99.json"
    d = json.loads(ruta.read_text(encoding="utf-8"))
    for b in d["bloques"]:
        if b["clave"] == clave:
            b.update(cambios)
    ruta.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")


def test_sin_terminal_no_se_aprueba(entorno):
    estado.iniciar_revision("99")
    entorno["humano"]["tty"] = False
    with pytest.raises(ErrorCheckpoint, match="terminal interactiva"):
        estado.aprobar("99", [], True, "Pablo")
    assert estado.cargar_revision("99")["decisiones"] == {}


def test_confirmacion_incorrecta_no_registra(entorno):
    estado.iniciar_revision("99")
    entorno["humano"]["numero"] = "01"
    with pytest.raises(ErrorCheckpoint, match="confirmación incorrecta"):
        estado.aprobar("99", [], True, "Pablo")
    assert estado.cargar_revision("99")["decisiones"] == {}


def test_frase_incorrecta_no_registra(entorno):
    estado.iniciar_revision("99")
    entorno["humano"]["frase"] = "otra frase cualquiera"
    with pytest.raises(ErrorCheckpoint, match="frase incorrecta"):
        estado.aprobar("99", [], True, "Pablo")
    assert estado.cargar_revision("99")["decisiones"] == {}


def test_sin_clave_configurada_no_se_decide(entorno):
    estado.ruta_clave().unlink()
    estado.iniciar_revision("99")
    with pytest.raises(ErrorCheckpoint, match="condor clave"):
        estado.aprobar("99", [], True, "Pablo")


def test_cambiar_la_clave_exige_la_frase_actual(entorno):
    entorno["humano"]["frase"] = "no es la frase"
    with pytest.raises(ErrorCheckpoint, match="frase incorrecta"):
        estado.configurar_clave("Pablo")


def test_aprobar_requiere_revision_iniciada(entorno):
    with pytest.raises(ErrorCheckpoint, match="condor revision"):
        estado.aprobar("99", [], True, "Pablo")


def test_todo_saltea_bloques_con_riesgo(entorno):
    estado.iniciar_revision("99")
    r = estado.aprobar("99", [], True, "Pablo")
    assert set(r["aprobados"]) == {"feature", "hardware"}
    assert [s["clave"] for s in r["salteados"]] == ["llm"]


def test_bloque_con_riesgo_exige_nota(entorno):
    estado.iniciar_revision("99")
    with pytest.raises(ErrorCheckpoint, match="--nota"):
        estado.aprobar("99", ["llm"], False, "Pablo")
    r = estado.aprobar("99", ["llm"], False, "Pablo", nota="la ficha oficial lo dice; riesgo bajo")
    assert r["aprobados"] == ["llm"]
    d = estado.cargar_revision("99")["decisiones"]["llm"]
    assert len(d["riesgos_aceptados"]) == 1
    assert d["riesgos_aceptados"][0].startswith("afirmacion_no_verificable:llm#1:")


def test_editar_despues_de_aprobar_vence_la_aprobacion(entorno):
    estado.iniciar_revision("99")
    estado.aprobar("99", [], True, "Pablo")
    _editar_bloque(entorno, "hardware", cuerpo="Oracle sumó 850 MW en el trimestre.")
    fila = next(f for f in estado.resumen("99")["filas"] if f["clave"] == "hardware")
    assert fila["vencida"] and not fila["vigente"]


def test_publicar_bloqueado_hasta_completar(entorno):
    estado.iniciar_revision("99")
    estado.aprobar("99", [], True, "Pablo")
    with pytest.raises(ErrorCheckpoint) as e:
        estado.publicar("99", "Pablo")
    assert "llm" in str(e.value) and "tapa" in str(e.value)


def test_ciclo_completo_y_retiro(entorno):
    estado.iniciar_revision("99")
    estado.aprobar("99", [], True, "Pablo")
    estado.retirar("99", "llm", "Pablo", "no se pudo verificar la cifra central")
    estado.elegir_tapa("99", "A", "Pablo")

    # la nota de fondo usa la cifra 552 del bloque retirado: su aprobación vence sola
    feature = next(f for f in estado.resumen("99")["filas"] if f["clave"] == "feature")
    assert feature["vencida"] and "depende_de_bloque_retirado" in feature["motivo_vencida"]
    with pytest.raises(ErrorCheckpoint, match="feature"):
        estado.publicar("99", "Pablo")

    # la persona edita la nota de fondo para sacar el dato y la vuelve a aprobar
    _editar_bloque(entorno, "feature", cuerpo="Oracle sumó 850 MW.")
    estado.aprobar("99", ["feature"], False, "Pablo")
    archivos = estado.publicar("99", "Pablo")
    assert all(a.exists() for a in archivos)
    html = (entorno["out"] / "numero-99" / "index.html").read_text(encoding="utf-8")
    assert "Oracle suma 850 MW" in html
    assert "552B" not in html  # ni el bloque retirado ni la cifra que dependía de él
    assert estado.resumen("99")["estado"] == "publicado"
    # tocar un bloque publicado saca al número de "publicado"
    _editar_bloque(entorno, "hardware", titulo="Otro título")
    assert estado.resumen("99")["estado"] != "publicado"


def test_dependencia_por_grupo_del_reconciliador(entorno):
    ruta = entorno["data"] / "numero-99.json"
    d = json.loads(ruta.read_text(encoding="utf-8"))
    d["grupos"] = [{"afirmaciones": ["hardware#1", "feature#1"], "descripcion": "capacidad sumada por Oracle"}]
    ruta.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    riesgos = estado.riesgos_bloque(estado.cargar("99"), "feature", {"hardware"})
    assert any(r["tipo"] == "depende_de_bloque_retirado" and r["ref"] == "hardware" for r in riesgos)


def test_todo_no_reaprueba_bloques_retirados(entorno):
    estado.iniciar_revision("99")
    estado.retirar("99", "hardware", "Pablo", "motivo")
    r = estado.aprobar("99", [], True, "Pablo")
    assert "hardware" not in r["aprobados"]
    assert estado.cargar_revision("99")["decisiones"]["hardware"]["accion"] == "retirar"


def test_tapa_modificada_despues_de_elegida(entorno):
    estado.iniciar_revision("99")
    estado.elegir_tapa("99", "A", "Pablo")
    assert estado.resumen("99")["tapa_ok"]
    # tocar el candidato no cambia lo elegido: se publica la copia con nombre por contenido
    candidato = entorno["out"] / "numero-99" / "tapa" / "candidato-A.svg"
    candidato.write_text(candidato.read_text(encoding="utf-8").replace("prueba", "otra"), encoding="utf-8")
    assert estado.resumen("99")["tapa_ok"]
    # tocar la copia elegida sí invalida la elección
    elegida = entorno["out"] / "numero-99" / estado.cargar_revision("99")["tapa"]["archivo"]
    elegida.write_text(elegida.read_text(encoding="utf-8").replace("prueba", "otra"), encoding="utf-8")
    assert not estado.resumen("99")["tapa_ok"]


def test_tapa_invalida_no_se_elige(entorno):
    svg = entorno["out"] / "numero-99" / "tapa" / "candidato-A.svg"
    svg.write_text(svg.read_text(encoding="utf-8").replace("</svg>", "<script/></svg>"), encoding="utf-8")
    estado.iniciar_revision("99")
    with pytest.raises(ErrorCheckpoint, match="validación"):
        estado.elegir_tapa("99", "A", "Pablo")


def test_riesgo_afirmacion_retirada_sigue_en_texto(entorno):
    ruta = entorno["data"] / "numero-99.json"
    d = json.loads(ruta.read_text(encoding="utf-8"))
    d["afirmaciones"][0]["estado_final"] = "retirado"
    ruta.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    tipos = [r["tipo"] for r in estado.riesgos_bloque(estado.cargar("99"), "hardware")]
    assert "retirada_sigue_en_texto" in tipos


def test_riesgo_cifra_sin_trazabilidad(entorno):
    _editar_bloque(entorno, "hardware", cuerpo="Oracle sumó 850 MW y 300.000 GPUs.")
    tipos = [r["tipo"] for r in estado.riesgos_bloque(estado.cargar("99"), "hardware")]
    assert "cifras_sin_trazabilidad" in tipos


def test_cifra_de_correccion_con_evidencia_es_trazable(entorno):
    ruta = entorno["data"] / "numero-99.json"
    d = json.loads(ruta.read_text(encoding="utf-8"))
    d["bloques"][1]["cuerpo"] = "Oracle sumó 870 MW en el trimestre."
    d["correcciones"].append({"bloque": "hardware", "antes": "850 MW", "despues": "870 MW", "motivo": "fallo C1"})
    ruta.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    tipos = [r["tipo"] for r in estado.riesgos_bloque(estado.cargar("99"), "hardware")]
    assert "cifras_sin_trazabilidad" not in tipos


def test_conflicto_sin_consenso_es_riesgo(entorno):
    ruta = entorno["data"] / "numero-99.json"
    d = json.loads(ruta.read_text(encoding="utf-8"))
    d["conflictos"].append({"id": "C1", "tipo": "veredicto", "bloques": ["feature", "hardware"], "descripcion": "x"})
    d["resoluciones"].append({"conflicto_id": "C1", "decision": "sin_consenso", "bloques": ["feature", "hardware"]})
    ruta.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    tipos = [r["tipo"] for r in estado.riesgos_bloque(estado.cargar("99"), "feature")]
    assert "conflicto_sin_consenso" in tipos


def test_render_borrador(entorno):
    estado.iniciar_revision("99")
    archivos = render_borrador("99")
    borrador = archivos[0].read_text(encoding="utf-8")
    revision = archivos[1].read_text(encoding="utf-8")
    assert "BORRADOR" in borrador
    assert "condor aprobar 99" in revision and "llm#1" in revision
