"""Normalización de cifras.

Es el espejo en Python de `canonNum`/`nums`/`significativa`/`sinIds`, que están copiados
en cada `.workflow.js` de `pipeline/` (los workflows no pueden importar módulos). Las
implementaciones tienen que dar el mismo resultado: las guardas del workflow y las del
checkpoint comparan cifras con esta misma regla (`tests/test_paridad_js.py` lo controla).

Regla:
- "300.000" / "300,000" (agrupación de miles)  -> "300000"
- "1.234,5" (es) / "1,234.5" (en)               -> "1234.5"
- "97,9" / "0.30"                               -> "97.9" / "0.3"
- "09"                                          -> "9"
"""

import re
import unicodedata
from collections import Counter

_TOKEN = re.compile(r"[0-9]+(?:[.,][0-9]+)*")
_MILES_PUNTO = re.compile(r"[0-9]{1,3}(?:\.[0-9]{3})+")
_MILES_COMA = re.compile(r"[0-9]{1,3}(?:,[0-9]{3})+")
_MIXTO_ES = re.compile(r"([0-9]{1,3}(?:\.[0-9]{3})+),([0-9]+)")
_MIXTO_EN = re.compile(r"([0-9]{1,3}(?:,[0-9]{3})+)\.([0-9]+)")
_DECIMAL = re.compile(r"([0-9]+)[.,]([0-9]+)")
_MILES = re.compile(r"[0-9]{1,3}(?:[.,][0-9]{3})+")
_ID_LIBRO = re.compile(r"\b[a-z_]+#[0-9]+\b")


def _dec(entero: str, fraccion: str) -> str:
    fraccion = fraccion.rstrip("0")
    return str(int(entero)) + ("." + fraccion if fraccion else "")


def canon(token: str) -> str:
    if _MILES_PUNTO.fullmatch(token) or _MILES_COMA.fullmatch(token):
        return str(int(re.sub(r"[.,]", "", token)))
    m = _MIXTO_ES.fullmatch(token)
    if m:
        return _dec(m.group(1).replace(".", ""), m.group(2))
    m = _MIXTO_EN.fullmatch(token)
    if m:
        return _dec(m.group(1).replace(",", ""), m.group(2))
    m = _DECIMAL.fullmatch(token)
    if m:
        return _dec(m.group(1), m.group(2))
    if token.isdigit():
        return str(int(token))
    return token


def cifras(texto: str) -> list[str]:
    return [canon(t) for t in _TOKEN.findall(texto or "")]


def multiconjunto(texto: str) -> Counter:
    return Counter(cifras(texto))


def es_significativa(token: str) -> bool:
    """Cifras que vale la pena rastrear: descarta años sueltos y enteros chicos.

    Recibe el token crudo o ya canónico. Con agrupación de miles ("2.000", "1,950") nunca
    es un año: hay que decidirlo antes de `canon`, que pierde el separador.
    """
    if _MILES.fullmatch(token):
        return True
    c = canon(token)
    if "." in c:
        return True
    n = int(re.match(r"[0-9]+", c).group())  # como parseInt de JS: "10,11,12" -> 10
    if 1900 <= n <= 2100:
        return False
    return n >= 10


def significativas(texto: str) -> set[str]:
    return {canon(t) for t in _TOKEN.findall(texto or "") if es_significativa(t)}


def quitar_ids(texto: str) -> str:
    """Saca los ids del libro de afirmaciones ("feature#17") que los jueces citan en su prosa."""
    return _ID_LIBRO.sub(" ", texto or "")


def normalizar_texto(s: str) -> str:
    """Minúsculas, sin tildes, comillas unificadas, espacios colapsados."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"[“”«»\"„]", '"', s)
    s = re.sub(r"[‘’´`]", "'", s)
    s = re.sub(r"[—–]", "-", s)
    return re.sub(r"\s+", " ", s).strip().lower()
