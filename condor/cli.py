"""CLI de Cóndor.

  condor clave     --revisor NOMBRE           crea (una vez) tu frase secreta de revisor/a
  condor revision  XX                         arma el paquete de revisión y el borrador
  condor estado    XX                         muestra qué falta para publicar
  condor aprobar   XX --todo | --bloque C...  [--nota "..."] --revisor NOMBRE
  condor retirar   XX --bloque C --motivo "..." --revisor NOMBRE
  condor tapa      XX CANDIDATO --revisor NOMBRE [--nota "..."]
  condor publicar  XX --revisor NOMBRE
  condor importar  RESULTADO.json            normaliza la salida del workflow a data/numero-XX.json
  condor tapa-validar SVG [--requerido T]...  (lo usan los agentes ilustradores)
  condor tapa-render  SVG [--ancho N]         (lo usan los agentes ilustradores)

clave / aprobar / retirar / tapa / publicar exigen una terminal interactiva, y las decisiones
se firman con tu frase secreta: publicar rechaza cualquier decisión que no tenga tu firma.
"""

import argparse
import json
import sys
from pathlib import Path

from . import estado as est
from .estado import ErrorCheckpoint


def _numero(n: str) -> str:
    return n.zfill(2) if n.isdigit() else n


def cmd_clave(a):
    h = est.configurar_clave(a.revisor)
    print(f"Clave de revisor/a guardada en {est.ruta_clave()} (huella {h}). La frase no se guarda: no la pierdas.")


def cmd_revision(a):
    est.iniciar_revision(a.numero)
    from .render import render_borrador
    archivos = render_borrador(a.numero)
    _imprimir_estado(est.resumen(a.numero))
    for f in archivos:
        print(f"-> {f}")


def _imprimir_estado(res: dict):
    print(f"Cóndor Nº {res['numero']} — estado: {res['estado']}")
    for f in res["filas"]:
        if f["vigente"]:
            d = f["decision"]
            marca = f"✓ {d['accion']} ({d.get('revisor', '?')})"
        elif f["vencida"]:
            marca = f"✗ aprobación vencida: {f['motivo_vencida'][:100]}"
        else:
            marca = "● pendiente"
        riesgos = f" · {len(f['riesgos'])} riesgo(s)" if f["riesgos"] and not f["vigente"] else ""
        print(f"  {f['clave']:<20} {marca}{riesgos}")
        if not f["vigente"]:
            for r in f["riesgos"]:
                print(f"      - {r['tipo']} {('[' + r['ref'] + ']') if r['ref'] else ''}: {r['detalle'][:140]}")
    if res["tapa_ok"]:
        print(f"  tapa                 ✓ candidato {res['tapa_elegida']['candidato']}")
    else:
        print(f"  tapa                 ● {res['tapa_motivo']} (sugerida por los jueces: {res['tapa_sugerida']})")
    for r in res["tapa_riesgos"]:
        print(f"      - {r['tipo']}: {r['detalle'][:140]}")
    if res["publicacion_desactualizada"]:
        print("  ⚠ lo publicado en output/ ya no coincide con las decisiones actuales: volvé a publicar")


def cmd_estado(a):
    _imprimir_estado(est.resumen(a.numero))


def cmd_aprobar(a):
    r = est.aprobar(a.numero, a.bloque or [], a.todo, a.revisor, a.nota or "")
    print(f"Aprobados: {', '.join(r['aprobados']) or '(ninguno)'}")
    if r["salteados"]:
        print("No aprobados por tener riesgos abiertos (decidilos uno por uno con --bloque):")
        for s in r["salteados"]:
            print(f"  - {s['clave']}: " + "; ".join(x["tipo"] for x in s["riesgos"]))


def cmd_retirar(a):
    r = est.retirar(a.numero, a.bloque, a.revisor, a.motivo or "")
    print(f"Bloque {a.bloque} retirado del número {a.numero}.")
    if r["sigue_publicado"]:
        print("⚠ el bloque figura en la versión ya publicada: sigue en output/ hasta que vuelvas a publicar.")


def cmd_tapa(a):
    r = est.elegir_tapa(a.numero, a.candidato, a.revisor, nota=a.nota or "")
    print(f"Tapa {a.candidato} elegida. Avisos del validador: {r['avisos'] or 'ninguno'}")


def cmd_publicar(a):
    archivos = est.publicar(a.numero, a.revisor)
    print(f"Cóndor Nº {a.numero} publicado:")
    for f in archivos:
        print(f"  -> {f}")


def cmd_importar(a):
    from .importar import importar
    ruta = importar(Path(a.resultado), forzar=a.forzar)
    print(f"-> {ruta}")


def cmd_tapa_validar(a):
    from .svg import validar
    r = validar(a.svg, tuple(a.requerido or ()))
    print(json.dumps(r, ensure_ascii=False, indent=2))
    sys.exit(0 if r["ok"] else 1)


def cmd_tapa_render(a):
    from .svg import rasterizar
    grande = rasterizar(a.svg, a.ancho)
    mini = rasterizar(a.svg, 300, sufijo="-mini")
    print(json.dumps({"png": str(grande), "png_mini": str(mini)}))


def main(argv=None):
    p = argparse.ArgumentParser(prog="condor", description="CMS y checkpoint humano de Cóndor")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("clave"); s.add_argument("--revisor"); s.set_defaults(f=cmd_clave)

    s = sub.add_parser("revision"); s.add_argument("numero", type=_numero); s.set_defaults(f=cmd_revision)
    s = sub.add_parser("estado"); s.add_argument("numero", type=_numero); s.set_defaults(f=cmd_estado)

    s = sub.add_parser("aprobar"); s.add_argument("numero", type=_numero)
    s.add_argument("--bloque", action="append"); s.add_argument("--todo", action="store_true")
    s.add_argument("--revisor"); s.add_argument("--nota"); s.set_defaults(f=cmd_aprobar)

    s = sub.add_parser("retirar"); s.add_argument("numero", type=_numero)
    s.add_argument("--bloque", required=True); s.add_argument("--motivo"); s.add_argument("--revisor")
    s.set_defaults(f=cmd_retirar)

    s = sub.add_parser("tapa"); s.add_argument("numero", type=_numero); s.add_argument("candidato")
    s.add_argument("--revisor"); s.add_argument("--nota"); s.set_defaults(f=cmd_tapa)

    s = sub.add_parser("publicar"); s.add_argument("numero", type=_numero); s.add_argument("--revisor")
    s.set_defaults(f=cmd_publicar)

    s = sub.add_parser("importar"); s.add_argument("resultado"); s.add_argument("--forzar", action="store_true")
    s.set_defaults(f=cmd_importar)

    s = sub.add_parser("tapa-validar"); s.add_argument("svg"); s.add_argument("--requerido", action="append")
    s.set_defaults(f=cmd_tapa_validar)
    s = sub.add_parser("tapa-render"); s.add_argument("svg"); s.add_argument("--ancho", type=int, default=1200)
    s.set_defaults(f=cmd_tapa_render)

    a = p.parse_args(argv)
    try:
        a.f(a)
    except ErrorCheckpoint as e:
        print(f"condor: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
