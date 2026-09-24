"""Las utilidades de cifras están copiadas en cada .workflow.js: tienen que ser idénticas entre sí
y dar lo mismo que condor/numeros.py."""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from condor.numeros import canon, es_significativa, quitar_ids, significativas

RAIZ = Path(__file__).resolve().parent.parent
SCRIPTS = sorted((RAIZ / "pipeline").glob("**/*.workflow.js"))
FUNCIONES = ("dec", "canonNum", "nums", "significativa", "sig", "sinIds", "cifrasAf")

TOKENS = ["300.000", "300,000", "1.000.000", "1.234,5", "1,234.5", "97,9", "0.30", "4.0", "09", "552",
          "2.000", "1,950", "1950", "2026", "2100", "10,11,12", "7", "10", "1.8"]
TEXTOS = [
    "En 2026 sumó 850 MW, 3 veces más, 1.8x",
    "En 1950 hubo 1.950 casos y 2.000 heridos",
    "feature#17: más de 1.000 MW; ver ciencia_salud#3 y el 97,9%",
    "GPT-5.6 y V4.1, USD 664.000 millones",
]


def _funcion(src: str, nombre: str) -> str | None:
    m = re.search(rf"^function {nombre}\(.*?(?=^function |^//|^const |\Z)", src, re.S | re.M)
    return m.group(0).strip() if m else None


@pytest.mark.parametrize("nombre", FUNCIONES)
def test_utilidades_identicas_en_todos_los_workflows(nombre):
    versiones = {}
    for s in SCRIPTS:
        f = _funcion(s.read_text(encoding="utf-8"), nombre)
        if f is not None:
            versiones.setdefault(f, []).append(s.name)
    assert len(versiones) <= 1, f"{nombre} difiere entre workflows: {list(versiones.values())}"


def test_etapas_con_guardas_de_cifras_tienen_todas_las_utilidades():
    for nombre in ("verificar", "reconciliar", "consolidar", "cierre"):
        src = (RAIZ / f"pipeline/etapas/{nombre}.workflow.js").read_text(encoding="utf-8")
        for f in ("canonNum", "significativa", "sig", "sinIds"):
            assert _funcion(src, f), f"{nombre}.workflow.js no define {f}"


@pytest.mark.skipif(not shutil.which("node"), reason="sin node")
def test_js_y_python_dan_lo_mismo():
    entrada = {"script": str(RAIZ / "pipeline/etapas/cierre.workflow.js"), "tokens": TOKENS, "textos": TEXTOS}
    out = subprocess.run(["node", str(RAIZ / "tests/js/numeros.mjs")], input=json.dumps(entrada),
                         capture_output=True, text=True, check=True)
    js = json.loads(out.stdout)
    assert js["canon"] == [canon(t) for t in TOKENS]
    assert js["significativa"] == [es_significativa(t) for t in TOKENS]
    assert js["sig"] == [sorted(significativas(t)) for t in TEXTOS]
    assert [significativas(t) for t in js["sinIds"]] == [significativas(quitar_ids(t)) for t in TEXTOS]
