from condor.svg import validar

from .conftest import SVG_OK


def _svg(tmp_path, contenido):
    p = tmp_path / "t.svg"
    p.write_text(contenido, encoding="utf-8")
    return p


def test_svg_valido(tmp_path):
    r = validar(_svg(tmp_path, SVG_OK), ("Cóndor", "99"))
    assert r["ok"], r["errores"]


def test_falta_texto_obligatorio(tmp_path):
    r = validar(_svg(tmp_path, SVG_OK), ("Cóndor", "07"))
    assert not r["ok"] and any("07" in e for e in r["errores"])


def test_rechaza_script(tmp_path):
    r = validar(_svg(tmp_path, SVG_OK.replace("</svg>", "<script>alert(1)</script></svg>")))
    assert not r["ok"] and any("script" in e for e in r["errores"])


def test_rechaza_href_externo(tmp_path):
    malo = SVG_OK.replace("</svg>", '<use href="https://evil.example/x.svg#a"/></svg>')
    r = validar(_svg(tmp_path, malo))
    assert not r["ok"] and any("externa" in e for e in r["errores"])


def test_rechaza_imagen_embebida(tmp_path):
    malo = SVG_OK.replace("</svg>", '<image href="#x" width="10" height="10"/></svg>')
    assert not validar(_svg(tmp_path, malo))["ok"]


def test_rechaza_evento(tmp_path):
    malo = SVG_OK.replace('<rect ', '<rect onclick="x()" ')
    assert not validar(_svg(tmp_path, malo))["ok"]


def test_xml_mal_formado(tmp_path):
    r = validar(_svg(tmp_path, "<svg><text>sin cerrar</svg>"))
    assert not r["ok"] and "XML" in r["errores"][0]


def test_entidades_peligrosas(tmp_path):
    bomba = '<?xml version="1.0"?><!DOCTYPE s [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;">]><svg viewBox="0 0 1 1"><text>&b;</text></svg>'
    assert not validar(_svg(tmp_path, bomba))["ok"]


def test_sin_viewbox(tmp_path):
    r = validar(_svg(tmp_path, SVG_OK.replace(' viewBox="0 0 1200 1600"', "")))
    assert not r["ok"]


def test_aviso_fuente_no_instalada(tmp_path):
    r = validar(_svg(tmp_path, SVG_OK.replace("Archivo Black", "Helvetica Neue")), ("Cóndor",))
    assert r["ok"] and r["avisos"]
