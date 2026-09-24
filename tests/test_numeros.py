import pytest

from condor.numeros import canon, cifras, multiconjunto, normalizar_texto, significativas


@pytest.mark.parametrize("token,esperado", [
    ("300.000", "300000"), ("300,000", "300000"), ("1.000.000", "1000000"),
    ("1.234,5", "1234.5"), ("1,234.5", "1234.5"),
    ("97,9", "97.9"), ("0.30", "0.3"), ("4.0", "4"), ("09", "9"), ("552", "552"),
])
def test_canon(token, esperado):
    assert canon(token) == esperado


def test_mismas_cifras_con_distinto_formato():
    assert multiconjunto("USD 5.000 millones y 97,9%") == multiconjunto("USD 5000 millones y 97.9 %")


def test_cifra_cambiada_se_detecta():
    assert multiconjunto("850 MW") != multiconjunto("580 MW")


def test_significativas_descarta_anios_y_chicos():
    assert significativas("En 2026 sumó 850 MW, 3 veces más, 1.8x") == {"850", "1.8"}


def test_cifras_en_nombres_de_modelo():
    assert cifras("GPT-5.6 y V4.1") == ["5.6", "4.1"]


def test_normalizar_texto():
    assert normalizar_texto("“Cóndor”  —  NÚMERO") == '"condor" - numero'


def test_varias_comas_como_parseint_de_js():
    # JS: significativa('10,11,12') -> parseInt = 10 -> true; Python no puede lanzar ValueError
    from condor.numeros import es_significativa, significativas
    assert es_significativa("10,11,12")
    assert "10,11,12" in significativas("los ítems 10,11,12 del anexo")
