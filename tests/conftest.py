import json

import pytest

from condor import estado

SVG_OK = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 1600" width="1200" height="1600">
<rect width="1200" height="1600" fill="#0a0f1e"/>
<text x="80" y="160" font-family="Archivo Black" font-size="120" fill="#fff">CÓNDOR</text>
<text x="80" y="260" font-family="Inter" font-size="48" fill="#ccc">Nº 99 · prueba</text>
</svg>"""


def numero_minimo() -> dict:
    sec_a = {
        "clave": "hardware", "tipo": "seccion", "seccion": "Hardware", "titulo": "Oracle suma 850 MW",
        "cuerpo": "Oracle sumó 850 MW en el trimestre y un RPO de USD 664.000 millones.",
        "fuente_nombre": "InfotechLead", "fuente_url": "https://example.com/a", "fecha": "2026-09-11",
        "open_weight": "no aplica",
    }
    sec_b = {
        "clave": "llm", "tipo": "seccion", "seccion": "LLMs", "titulo": "Un modelo con 552B parámetros",
        "cuerpo": "El modelo tiene 552B parámetros y 8B activos.", "fuente_nombre": "HF",
        "fuente_url": "https://example.com/b", "fecha": "2026-09-10", "open_weight": "open-weight",
    }
    feat = {
        "clave": "feature", "tipo": "feature", "seccion": "Nota de fondo", "titulo": "La gobernanza llega tarde",
        "bajada": "Tres historias, un patrón.", "cuerpo": "Oracle sumó 850 MW. El modelo usa 552B parámetros.",
        "fuente_nombre": "", "fuente_url": "", "fecha": "2026-09-12", "open_weight": "no aplica", "fuentes": [],
    }

    def af(id_, bloque, texto, cita, estado_v, estado_f=None):
        a = {"id": id_, "bloque": bloque, "texto": texto, "cita_textual": cita,
             "veredicto": {"estado": estado_v, "evidencia": [{"url": "https://example.com", "cita": "x"}], "nota": ""}}
        if estado_f:
            a["estado_final"] = estado_f
        return a

    return {
        "version": 2,
        "numero": "99",
        "meta": {"titulo_numero": "Prueba", "concepto_tapa": "c", "fecha": "12 de septiembre de 2026", "semana_iso": "2026-W37"},
        "bloques": [feat, sec_a, sec_b],
        "versiones": {"investigacion": {b["clave"]: {"titulo": b["titulo"], "cuerpo": b["cuerpo"], "bajada": b.get("bajada", "")}
                                         for b in (feat, sec_a, sec_b)}},
        "afirmaciones": [
            af("hardware#1", "hardware", "Oracle sumó 850 MW", "Oracle sumó 850 MW", "confirmado"),
            af("llm#1", "llm", "552B parámetros", "552B parámetros", "no_verificable"),
            af("feature#1", "feature", "Oracle sumó 850 MW", "Oracle sumó 850 MW", "confirmado"),
        ],
        "conflictos": [], "resoluciones": [], "debates": [], "correcciones": [], "guardas": [],
        "contexto_omitido": [], "descartados": [],
        "tapa": {"candidatos": [{"id": "A", "angulo": "editorial", "svg": "tapa/candidato-A.svg",
                                 "png": "tapa/candidato-A.png", "descripcion": "d", "total": 30}],
                 "ganador": "A", "jueces": []},
    }


FRASE = "frase de prueba larga"


@pytest.fixture
def humano(monkeypatch):
    """La persona que revisa: terminal interactiva, sabe su frase y tipea el número."""
    h = {"tty": True, "frase": FRASE, "numero": "99"}
    monkeypatch.setattr(estado, "_es_tty", lambda: h["tty"])
    monkeypatch.setattr(estado, "_pedir", lambda _prompt: h["numero"])
    monkeypatch.setattr(estado, "_pedir_secreto", lambda _prompt: h["frase"])
    return h


@pytest.fixture
def entorno(tmp_path, monkeypatch, humano):
    data = tmp_path / "data"
    out = tmp_path / "output"
    data.mkdir()
    out.mkdir()
    monkeypatch.setattr(estado, "DATA", data)
    monkeypatch.setattr(estado, "OUTPUT", out)
    monkeypatch.setattr(estado, "CONFIG", tmp_path / "config")
    estado.configurar_clave("Pablo")
    numero = numero_minimo()
    (data / "numero-99.json").write_text(json.dumps(numero, ensure_ascii=False), encoding="utf-8")
    tapa_dir = out / "numero-99" / "tapa"
    tapa_dir.mkdir(parents=True)
    (tapa_dir / "candidato-A.svg").write_text(SVG_OK, encoding="utf-8")
    return {"data": data, "out": out, "numero": "99", "humano": humano}
