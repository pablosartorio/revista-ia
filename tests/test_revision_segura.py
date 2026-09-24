"""Hallazgos de la revisión adversarial del checkpoint (v2.1): cada test reproduce un escenario."""

import json
import shutil

import pytest

from condor import estado
from condor.estado import ErrorCheckpoint
from condor.importar import importar

from .conftest import SVG_OK


def _datos(entorno):
    return json.loads((entorno["data"] / "numero-99.json").read_text(encoding="utf-8"))


def _guardar(entorno, d):
    (entorno["data"] / "numero-99.json").write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")


def _tapa(entorno, extra_texto):
    svg = entorno["out"] / "numero-99" / "tapa" / "candidato-A.svg"
    svg.write_text(SVG_OK.replace(
        "</svg>", f'<text x="80" y="1400" font-family="Inter" font-size="40" fill="#ccc">{extra_texto}</text></svg>'
    ), encoding="utf-8")


def _publicable(entorno):
    """Número 99 con llm retirado y todo lo demás aprobado: listo para publicar."""
    d = _datos(entorno)
    d["bloques"][0]["cuerpo"] = "Oracle sumó 850 MW."  # la nota de fondo ya no usa la cifra de llm
    _guardar(entorno, d)
    estado.iniciar_revision("99")
    estado.retirar("99", "llm", "Pablo", "no verificable")
    estado.aprobar("99", [], True, "Pablo")
    estado.elegir_tapa("99", "A", "Pablo")


# --------------------------------------------------------------------------- firma de decisiones

def test_decision_escrita_por_un_agente_no_se_publica(entorno):
    _publicable(entorno)
    # un agente (sin la frase) escribe una aprobación directamente en revision.json
    ruta = estado.ruta_revision("99")
    rev = json.loads(ruta.read_text(encoding="utf-8"))
    rev["decisiones"]["llm"] = dict(rev["decisiones"]["hardware"], hash=estado.resumen("99")["filas"][2]["hash"],
                                    riesgos_aceptados=[estado.clave_riesgo(r) for r in estado.riesgos_bloque(estado.cargar("99"), "llm")])
    ruta.write_text(json.dumps(rev), encoding="utf-8")
    with pytest.raises(ErrorCheckpoint, match="firma válida.*bloque llm"):
        estado.publicar("99", "Pablo")


def test_decision_editada_a_mano_invalida_la_firma(entorno):
    _publicable(entorno)
    ruta = estado.ruta_revision("99")
    rev = json.loads(ruta.read_text(encoding="utf-8"))
    rev["tapa"]["nota"] = "cambiada después"
    ruta.write_text(json.dumps(rev), encoding="utf-8")
    with pytest.raises(ErrorCheckpoint, match="tapa"):
        estado.publicar("99", "Pablo")


def test_no_se_pierden_decisiones_concurrentes(entorno, monkeypatch):
    estado.iniciar_revision("99")
    real = estado._pedir

    def pedir_mientras_otro_retira(prompt):
        # mientras la persona tipea, otro proceso registra un retiro
        monkeypatch.setattr(estado, "_pedir", real)
        estado.retirar("99", "llm", "Pablo", "otro proceso")
        return "99"

    monkeypatch.setattr(estado, "_pedir", pedir_mientras_otro_retira)
    estado.aprobar("99", ["hardware"], False, "Pablo")
    decisiones = estado.cargar_revision("99")["decisiones"]
    assert decisiones["llm"]["accion"] == "retirar" and decisiones["hardware"]["accion"] == "aprobar"


# --------------------------------------------------------------------------- tapa

def test_tapa_que_anuncia_un_bloque_retirado_no_queda_vigente(entorno):
    _tapa(entorno, "Un modelo con 552B parámetros")
    estado.iniciar_revision("99")
    # 552 sólo lo respalda una afirmación no verificable: elegirla exige nota
    with pytest.raises(ErrorCheckpoint, match="sin verificar"):
        estado.elegir_tapa("99", "A", "Pablo")
    estado.elegir_tapa("99", "A", "Pablo", nota="la línea de tapa es de llm")
    estado.retirar("99", "llm", "Pablo", "552B no verificable")
    res = estado.resumen("99")
    assert not res["tapa_ok"]
    assert "tapa_titulo_retirado" in {r["tipo"] for r in res["tapa_riesgos"]}
    # si además se retira la nota de fondo, la cifra de la tapa ya no está en ninguna nota
    estado.retirar("99", "feature", "Pablo", "dependía de llm")
    assert "tapa_cifra_sin_respaldo" in {r["tipo"] for r in estado.resumen("99")["tapa_riesgos"]}


def test_tapa_con_cifra_sin_respaldo_exige_nota(entorno):
    _tapa(entorno, "300.000 GPUs")
    estado.iniciar_revision("99")
    with pytest.raises(ErrorCheckpoint, match="300000"):
        estado.elegir_tapa("99", "A", "Pablo")
    estado.elegir_tapa("99", "A", "Pablo", nota="decisión editorial")
    assert estado.resumen("99")["tapa_ok"]


def test_dato_ancla_de_bloque_retirado(entorno):
    d = _datos(entorno)
    d["meta"]["dato_ancla"] = {"id": "hardware#1", "texto": "Oracle sumó 850 MW", "valor": "850 MW"}
    _guardar(entorno, d)
    riesgos = estado.riesgos_tapa("99", estado.cargar("99"), entorno["out"] / "numero-99/tapa/candidato-A.svg", {"hardware"})
    assert any(r["tipo"] == "tapa_dato_ancla_retirado" for r in riesgos)


def test_cambiar_el_titulo_del_numero_vence_la_tapa(entorno):
    estado.iniciar_revision("99")
    estado.elegir_tapa("99", "A", "Pablo")
    d = _datos(entorno)
    d["meta"]["titulo_numero"] = "Otro título"
    _guardar(entorno, d)
    res = estado.resumen("99")
    assert not res["tapa_ok"] and "título" in res["tapa_motivo"]


@pytest.mark.skipif(not shutil.which("rsvg-convert"), reason="requiere rsvg-convert")
def test_el_png_publicado_sale_del_svg_aprobado(entorno):
    # un PNG del candidato que no corresponde al SVG (p. ej. reemplazado después de elegir)
    (entorno["out"] / "numero-99" / "tapa" / "candidato-A.png").write_bytes(b"no es la tapa aprobada")
    _publicable(entorno)
    archivos = estado.publicar("99", "Pablo")
    png = entorno["out"] / "numero-99" / "tapa.png"
    assert png in archivos and png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


# --------------------------------------------------------------------------- estado publicado

def test_retirar_despues_de_publicar_desactualiza_la_publicacion(entorno):
    _publicable(entorno)
    estado.publicar("99", "Pablo")
    assert estado.resumen("99")["estado"] == "publicado"
    r = estado.retirar("99", "hardware", "Pablo", "error detectado después")
    res = estado.resumen("99")
    assert r["sigue_publicado"] and res["estado"] != "publicado" and res["publicacion_desactualizada"]


# --------------------------------------------------------------------------- riesgos

def test_riesgo_aceptado_que_cambia_de_contenido_vence_la_aprobacion(entorno):
    estado.iniciar_revision("99")
    estado.aprobar("99", ["llm"], False, "Pablo", nota="riesgo bajo")
    d = _datos(entorno)
    d["afirmaciones"][1]["cita_textual"] = "8B activos"  # mismo id, otra afirmación
    _guardar(entorno, d)
    fila = next(f for f in estado.resumen("99")["filas"] if f["clave"] == "llm")
    assert fila["vencida"] and "riesgos nuevos" in fila["motivo_vencida"]


def test_dependencia_por_texto_del_bloque_retirado(entorno):
    d = _datos(entorno)
    d["bloques"][0]["cuerpo"] = "El RPO de Oracle llegó a USD 664.000 millones."  # cifra sin afirmación extraída
    _guardar(entorno, d)
    riesgos = estado.riesgos_bloque(estado.cargar("99"), "feature", {"hardware"})
    assert any(r["tipo"] == "depende_de_bloque_retirado" and r["ref"] == "hardware" and "664000" in r["detalle"]
               for r in riesgos)


def test_fallo_con_cifra_que_sigue_en_el_texto(entorno):
    d = _datos(entorno)
    d["conflictos"].append({"id": "C1", "tipo": "huerfana", "bloques": ["feature"], "afirmaciones": [], "cifras": ["552"],
                            "descripcion": "cifra huérfana"})
    d["resoluciones"].append({"conflicto_id": "C1", "decision": "retirar", "bloques": ["feature"], "cifras": ["552"],
                              "valor_correcto": "", "redaccion_sugerida": "", "bloques_pendientes": []})
    _guardar(entorno, d)
    tipos = [r["tipo"] for r in estado.riesgos_bloque(estado.cargar("99"), "feature")]
    assert "fallo_cifra_sigue_en_texto" in tipos


def test_correccion_no_aplicada_es_riesgo(entorno):
    d = _datos(entorno)
    d["afirmaciones"][0]["estado_final"] = "no_aplicado"
    _guardar(entorno, d)
    tipos = [r["tipo"] for r in estado.riesgos_bloque(estado.cargar("99"), "hardware")]
    assert "afirmacion_no_aplicado" in tipos


def test_cambiar_la_seccion_vence_la_aprobacion(entorno):
    estado.iniciar_revision("99")
    estado.aprobar("99", ["hardware"], False, "Pablo")
    d = _datos(entorno)
    d["bloques"][1]["seccion"] = "Otra sección"
    _guardar(entorno, d)
    assert next(f for f in estado.resumen("99")["filas"] if f["clave"] == "hardware")["vencida"]


# --------------------------------------------------------------------------- importar

def test_importar_normaliza_el_numero(entorno, tmp_path):
    d = _datos(entorno)
    d["numero"] = 7
    ruta = tmp_path / "resultado.json"
    ruta.write_text("resultado del workflow:\n" + json.dumps(d), encoding="utf-8")
    destino = importar(ruta)
    assert destino.name == "numero-07.json"
    assert json.loads(destino.read_text(encoding="utf-8"))["numero"] == "07"
