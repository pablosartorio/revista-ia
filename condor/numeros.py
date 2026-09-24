"""Normalización de cifras.

Es el espejo en Python de `canonNum`/`nums` de los scripts de Workflow
(`pipeline/etapas/_comun.js` documenta la versión JS). Las dos implementaciones
tienen que dar el mismo resultado: las guardas del workflow y las del checkpoint
comparan cifras con esta misma regla.

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


def es_significativa(c: str) -> bool:
    """Cifras que vale la pena rastrear: descarta años sueltos y enteros chicos."""
    if "." in c:
        return True
    n = int(re.match(r"[0-9]+", c).group())  # como parseInt de JS: "10,11,12" -> 10
    if 1900 <= n <= 2100:
        return False
    return n >= 10


def significativas(texto: str) -> set[str]:
    return {c for c in cifras(texto) if es_significativa(c)}


def normalizar_texto(s: str) -> str:
    """Minúsculas, sin tildes, comillas unificadas, espacios colapsados."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"[“”«»\"„]", '"', s)
    s = re.sub(r"[‘’´`]", "'", s)
    s = re.sub(r"[—–]", "-", s)
    return re.sub(r"\s+", " ", s).strip().lower()
