import json

from scripts.semilla_desde_journal import semilla


def test_semilla_toma_secciones_y_feature_del_journal(tmp_path):
    sec = {"titulo": "T", "cuerpo": "c", "open_weight": "no aplica", "fuente_nombre": "F", "fuente_url": "https://e.com", "fecha": "2026-09-20"}
    eventos = [
        {"type": "launched"},
        {"type": "started", "key": "k1", "label": "seccion:llm"}, {"type": "result", "key": "k1", "result": sec},
        {"type": "started", "key": "k2", "label": "seccion:espacio"}, {"type": "result", "key": "k2", "result": sec},
        {"type": "started", "key": "k3", "label": "seccion:hardware"}, {"type": "failed", "key": "k3"},
        {"type": "started", "key": "k4", "label": "seccion:latam"}, {"type": "result", "key": "k4", "result": dict(sec, cuerpo="")},
        {"type": "started", "key": "k5", "label": "feature:nota-de-fondo"},
        {"type": "result", "key": "k5", "result": {"titulo": "F", "bajada": "b", "cuerpo": "x", "fuentes": []}},
        {"type": "started", "key": "k6", "label": "extraer:llm"}, {"type": "result", "key": "k6", "result": {"afirmaciones": []}},
    ]
    j = tmp_path / "wf_prueba" / "journal.jsonl"
    j.parent.mkdir()
    j.write_text("\n".join(json.dumps(e) for e in eventos), encoding="utf-8")
    s = semilla(j, excluir={"espacio"}, con_feature=True)
    assert list(s["secciones"]) == ["llm"]  # espacio excluida, hardware caída, latam incompleta
    assert s["feature"]["titulo"] == "F" and "wf_prueba" in s["origen"]
    assert semilla(j, excluir=set(), con_feature=False)["feature"] is None
