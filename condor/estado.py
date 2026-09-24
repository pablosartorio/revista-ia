"""Checkpoint humano: estado de un número y decisiones de revisión.

Ciclo de vida:  borrador -> en_revision -> aprobado -> publicado

- El workflow deja `data/numero-XX.json` (contenido + libro de afirmaciones + tapas).
- `condor revision XX` arma el paquete de revisión y pasa el número a `en_revision`.
- Una persona decide bloque por bloque (`aprobar` / `retirar`) y elige la tapa.
  Cada aprobación guarda el hash del contenido aprobado: si el texto cambia después,
  la aprobación vence sola y el bloque vuelve a quedar pendiente.
- `condor publicar XX` sólo corre si no queda nada pendiente, los hashes coinciden y
  todas las decisiones tienen una firma válida.

Quién decide: cada decisión se firma (HMAC) con una clave derivada de la frase secreta
de la persona que revisa (`condor clave`). La frase se tipea en la terminal y no queda
guardada en ningún lado, así que un agente que corre comandos puede escribir en
`revision.json` pero no puede producir una decisión que `publicar` acepte. La terminal
interactiva y el número tipeado son una segunda barrera, contra errores de dedo.
"""

import fcntl
import getpass
import hashlib
import hmac
import json
import os
import re
import secrets
import sys
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from . import DATA, OUTPUT
from .numeros import normalizar_texto, quitar_ids, significativas

VERSION_DATOS = 2

CAMPOS_PUBLICABLES = (
    "titulo", "bajada", "cuerpo", "fuente_nombre", "fuente_url", "fecha", "open_weight", "fuentes",
    "seccion", "tipo",
)

ESTADOS_RIESGO = {"no_verificable", "contradicho", "sin_consenso", "no_aplicado"}
DECISIONES_QUE_EDITAN = {"corregir", "retirar", "matizar"}

CONFIG = Path(os.environ.get("CONDOR_CONFIG") or Path.home() / ".config" / "condor")


class ErrorCheckpoint(Exception):
    """Error de uso del checkpoint: el mensaje es para la persona que revisa."""


# --------------------------------------------------------------------------- rutas / IO

def ruta_numero(numero: str) -> Path:
    return DATA / f"numero-{numero}.json"


def ruta_revision(numero: str) -> Path:
    return DATA / f"numero-{numero}.revision.json"


def dir_salida(numero: str) -> Path:
    return OUTPUT / f"numero-{numero}"


def cargar(numero: str) -> dict:
    ruta = ruta_numero(numero)
    if not ruta.exists():
        raise ErrorCheckpoint(f"no existe {ruta}")
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    if datos.get("version") != VERSION_DATOS:
        raise ErrorCheckpoint(
            f"{ruta.name} es versión {datos.get('version', 1)}; el checkpoint requiere versión {VERSION_DATOS}"
        )
    return datos


def revision_vacia(numero: str) -> dict:
    return {"numero": numero, "decisiones": {}, "tapa": None, "publicacion": None, "historial": []}


def cargar_revision(numero: str) -> dict | None:
    ruta = ruta_revision(numero)
    if not ruta.exists():
        return None
    return json.loads(ruta.read_text(encoding="utf-8"))


def guardar_revision(numero: str, rev: dict) -> None:
    ruta = ruta_revision(numero)
    tmp = ruta.with_suffix(".tmp")
    tmp.write_text(json.dumps(rev, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(ruta)


@contextmanager
def _bloqueo(numero: str):
    """Serializa leer-modificar-escribir de revision.json entre procesos."""
    DATA.mkdir(parents=True, exist_ok=True)
    with open(DATA / f"numero-{numero}.revision.lock", "w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def ahora() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


# --------------------------------------------------------------------------- hashes

def _json_canonico(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha(obj) -> str:
    return hashlib.sha256(_json_canonico(obj).encode("utf-8")).hexdigest()


def hash_bloque(bloque: dict, datos: dict | None = None) -> str:
    """Hash de todo lo que se publica de un bloque.

    Con `datos`, incluye también las afirmaciones del bloque y su estado: son las que
    muestra la caja "Cómo verificamos este número".
    """
    publicable = {k: bloque.get(k) for k in CAMPOS_PUBLICABLES}
    if datos is not None:
        publicable["_afirmaciones"] = sorted(
            [a.get("id", ""), a.get("texto", ""), estado_final(a)]
            for a in datos.get("afirmaciones", []) if a.get("bloque") == bloque.get("clave")
        )
    return _sha(publicable)


def hash_meta(datos: dict) -> str:
    """Título del número, concepto de tapa, fecha…: se aprueban junto con la tapa."""
    return _sha(datos.get("meta") or {})


def hash_archivo(ruta: Path) -> str:
    return hashlib.sha256(Path(ruta).read_bytes()).hexdigest()


# --------------------------------------------------------------------------- consultas

def bloque(datos: dict, clave: str) -> dict:
    for b in datos["bloques"]:
        if b["clave"] == clave:
            return b
    raise ErrorCheckpoint(f"no hay bloque {clave!r}; bloques: {', '.join(b['clave'] for b in datos['bloques'])}")


def _texto_bloque(b: dict) -> str:
    return " ".join(str(b.get(k) or "") for k in ("titulo", "bajada", "cuerpo"))


def estado_final(afirmacion: dict) -> str:
    return afirmacion.get("estado_final") or afirmacion.get("veredicto", {}).get("estado", "no_verificable")


def cifras_afirmacion(a: dict) -> set[str]:
    """Cifras de una afirmación: las de su valor que están en la cita (la cita puede traer datos ajenos).

    Mismo criterio que `cifrasAf` de los workflows.
    """
    en_cita = significativas(a.get("cita_textual", ""))
    propias = significativas(a.get("valor", "")) & en_cita
    return propias or en_cita


def _cifras_correccion(r: dict) -> set[str]:
    """Cifras que trae un fallo, sin los ids del libro ("feature#17") que el juez cita en la prosa."""
    return significativas(quitar_ids(f"{r.get('valor_correcto', '')} {r.get('redaccion_sugerida', '')}"))


def indice_resoluciones(datos: dict) -> dict[str, dict]:
    """Conflicto -> resolución que lo resuelve: la propia o la consolidada que lo cubre."""
    indice: dict[str, dict] = {}
    for r in datos.get("resoluciones", []):
        indice[r["conflicto_id"]] = r
        for cid in r.get("conflictos_cubiertos") or []:
            indice.setdefault(cid, r)
    return indice


def clave_riesgo(r: dict) -> str:
    """Identidad de un riesgo aceptado: tipo, referencia y un resumen de su contenido.

    Si el mismo id pasa a describir otra cosa (otra afirmación, otras cifras), la clave
    cambia y la aprobación que lo había aceptado vence.
    """
    return f"{r['tipo']}:{r['ref']}:{_sha(r)[:10]}"


def _retirados(rev: dict) -> set[str]:
    return {c for c, d in rev["decisiones"].items() if d["accion"] == "retirar"}


def riesgos_bloque(datos: dict, clave: str, retirados: frozenset | set = frozenset()) -> list[dict]:
    """Motivos por los que un bloque no puede aprobarse "en bloque" sin una decisión explícita.

    `retirados` son los bloques que la revisión humana sacó del número: si este bloque
    comparte hechos con alguno de ellos (según los grupos del reconciliador o por cifras
    en común), queda en riesgo porque estaría publicando algo que se decidió no publicar.
    """
    b = bloque(datos, clave)
    texto = _texto_bloque(b)
    texto_norm = normalizar_texto(texto)
    cifras_propias = significativas(texto)
    riesgos: list[dict] = []

    for a in datos.get("afirmaciones", []):
        if a.get("bloque") != clave:
            continue
        ef = estado_final(a)
        if ef in ESTADOS_RIESGO:
            riesgos.append({"tipo": f"afirmacion_{ef}", "ref": a["id"], "detalle": a.get("texto", ""),
                            "cita": a.get("cita_textual", "")})
        if ef == "retirado" and a.get("cita_textual"):
            if normalizar_texto(a["cita_textual"]) in texto_norm:
                riesgos.append({
                    "tipo": "retirada_sigue_en_texto", "ref": a["id"],
                    "detalle": f"la afirmación retirada sigue en el texto: {a['cita_textual']!r}",
                })

    resoluciones = indice_resoluciones(datos)
    for c in datos.get("conflictos", []):
        if clave not in c.get("bloques", []):
            continue
        r = resoluciones.get(c["id"])
        if r is None:
            riesgos.append({"tipo": "conflicto_sin_resolver", "ref": c["id"], "detalle": c.get("descripcion", "")})
        elif r.get("decision") == "sin_consenso":
            riesgos.append({"tipo": "conflicto_sin_consenso", "ref": c["id"], "detalle": r.get("razonamiento", "")})
        elif r.get("decision") in DECISIONES_QUE_EDITAN and clave in r.get("bloques_pendientes", []):
            riesgos.append({
                "tipo": "resolucion_no_aplicada", "ref": c["id"],
                "detalle": f"el juez decidió {r['decision']!r} pero la corrección no pudo aplicarse con las guardas",
            })

    # Un fallo de retirar/corregir que trae las cifras en cuestión (p. ej. una cifra huérfana
    # de la nota de fondo): esas cifras no pueden seguir en el texto.
    for r in datos.get("resoluciones", []):
        if clave not in r.get("bloques", []) or r.get("decision") not in ("retirar", "corregir"):
            continue
        nuevas = _cifras_correccion(r)
        siguen = sorted(set(r.get("cifras") or []) & cifras_propias - nuevas)
        if siguen:
            riesgos.append({
                "tipo": "fallo_cifra_sigue_en_texto", "ref": r["conflicto_id"],
                "detalle": f"el juez decidió {r['decision']!r} sobre {', '.join(siguen)}, pero sigue en el texto",
            })

    for g in datos.get("guardas", []):
        if g.get("bloque") == clave and g.get("severidad") == "bloqueante":
            riesgos.append({"tipo": f"guarda_{g.get('tipo', '?')}", "ref": g.get("etapa", ""), "detalle": g.get("detalle", "")})

    otros_retirados = set(retirados) - {clave}
    if otros_retirados:
        dependencias: list[dict] = []
        propias = {a["id"] for a in datos.get("afirmaciones", []) if a.get("bloque") == clave}
        de_retirados = {a["id"]: a for a in datos.get("afirmaciones", []) if a.get("bloque") in otros_retirados}
        for grupo in datos.get("grupos", []):
            ids = set(grupo.get("afirmaciones", []))
            if ids & propias and ids & set(de_retirados):
                origen = sorted({de_retirados[i]["bloque"] for i in ids & set(de_retirados)})
                dependencias.append({
                    "tipo": "depende_de_bloque_retirado", "ref": ",".join(origen),
                    "detalle": f"comparte el hecho {grupo.get('descripcion', '')!r} con un bloque retirado",
                })
        for a in de_retirados.values():
            comunes = cifras_propias & significativas(a.get("cita_textual", ""))
            if comunes:
                dependencias.append({
                    "tipo": "depende_de_bloque_retirado", "ref": a["bloque"],
                    "detalle": f"usa cifras ({', '.join(sorted(comunes))}) de una afirmación del bloque retirado: {a.get('texto', '')!r}",
                })
        # además del libro de afirmaciones, el texto completo del bloque retirado (y su versión
        # original): una cifra que el extractor no tomó también cuenta
        originales = datos.get("versiones", {}).get("investigacion", {})
        for otro in sorted(otros_retirados):
            try:
                texto_otro = _texto_bloque(bloque(datos, otro)) + " " + _texto_bloque(originales.get(otro, {}))
            except ErrorCheckpoint:
                continue
            comunes = cifras_propias & significativas(texto_otro)
            if comunes:
                dependencias.append({
                    "tipo": "depende_de_bloque_retirado", "ref": otro,
                    "detalle": f"comparte cifras ({', '.join(sorted(comunes))}) con el texto del bloque retirado",
                })
        # un riesgo por bloque retirado alcanza
        vistos = set()
        for r in dependencias:
            if r["ref"] not in vistos:
                vistos.add(r["ref"])
                riesgos.append(r)

    # Defensa en profundidad: toda cifra publicada tiene que venir de la investigación
    # original o de una corrección con evidencia. Si una etapa de edición "inventó" un
    # número, aparece acá aunque todas las guardas del workflow hayan pasado.
    original = datos.get("versiones", {}).get("investigacion", {}).get(clave, {})
    permitidas = significativas(_texto_bloque(original))
    for corr in datos.get("correcciones", []):
        if corr.get("bloque") == clave:
            permitidas |= significativas(corr.get("despues", ""))
    for r in datos.get("resoluciones", []):
        if clave in r.get("bloques", []):
            permitidas |= _cifras_correccion(r)
    for ctx in datos.get("contexto_omitido", []):
        if ctx.get("bloque") == clave:
            permitidas |= significativas(ctx.get("descripcion", ""))
    nuevas = sorted(cifras_propias - permitidas)
    if nuevas:
        riesgos.append({
            "tipo": "cifras_sin_trazabilidad", "ref": "",
            "detalle": "cifras que no vienen de la investigación ni de una corrección con evidencia: " + ", ".join(nuevas),
        })
    return riesgos


def candidatos_tapa(datos: dict) -> list[dict]:
    return (datos.get("tapa") or {}).get("candidatos", [])


def ruta_candidato(numero: str, candidato: dict) -> Path:
    ruta = Path(candidato["svg"])
    return ruta if ruta.is_absolute() else dir_salida(numero) / ruta


def _tokens(s: str) -> set[str]:
    return {t for t in re.split(r"[^a-z0-9]+", normalizar_texto(s)) if len(t) >= 5}


def riesgos_tapa(numero: str, datos: dict, ruta_svg: Path, retirados: set[str]) -> list[dict]:
    """Lo que la tapa promete tiene que estar en el número que se publica.

    - toda cifra de la tapa tiene que aparecer en algún bloque que no esté retirado, y no
      sólo en afirmaciones con riesgo;
    - el dato ancla no puede venir de un bloque retirado ni de una afirmación en riesgo;
    - una línea de tapa no puede ser el título de un bloque retirado.
    """
    from .svg import validar

    textos = validar(ruta_svg)["textos"]
    riesgos: list[dict] = []
    meta = datos.get("meta") or {}
    vivos = [b for b in datos["bloques"] if b["clave"] not in retirados]

    permitidas = significativas(" ".join(str(meta.get(k) or "") for k in ("fecha", "semana_iso")) + f" {numero}")
    en_texto = set().union(*(significativas(_texto_bloque(b)) for b in vivos)) if vivos else set()
    sanas = set()
    for a in datos.get("afirmaciones", []):
        if a.get("bloque") not in retirados and estado_final(a) not in ESTADOS_RIESGO | {"retirado"}:
            sanas |= cifras_afirmacion(a)
    en_riesgo = set()
    for a in datos.get("afirmaciones", []):
        if a.get("bloque") not in retirados and estado_final(a) in ESTADOS_RIESGO:
            en_riesgo |= significativas(a.get("cita_textual", ""))

    cifras_tapa = significativas(textos) - permitidas
    sin_respaldo = sorted(cifras_tapa - en_texto)
    if sin_respaldo:
        riesgos.append({"tipo": "tapa_cifra_sin_respaldo", "ref": "",
                        "detalle": f"cifras de la tapa que no están en ninguna nota publicada: {', '.join(sin_respaldo)}"})
    dudosas = sorted((cifras_tapa & en_riesgo) - sanas)
    if dudosas:
        riesgos.append({"tipo": "tapa_cifra_en_riesgo", "ref": "",
                        "detalle": f"cifras de la tapa que sólo respaldan afirmaciones sin verificar: {', '.join(dudosas)}"})

    ancla = meta.get("dato_ancla") or {}
    if ancla.get("id"):
        a = next((x for x in datos.get("afirmaciones", []) if x.get("id") == ancla["id"]), None)
        if a is None or a.get("bloque") in retirados:
            riesgos.append({"tipo": "tapa_dato_ancla_retirado", "ref": ancla["id"],
                            "detalle": f"el dato ancla de la tapa ({ancla.get('valor', '')}) es de un bloque retirado"})
        elif estado_final(a) != "confirmado":
            riesgos.append({"tipo": "tapa_dato_ancla_en_riesgo", "ref": ancla["id"],
                            "detalle": f"el dato ancla de la tapa quedó {estado_final(a)!r}"})

    norm_tapa = normalizar_texto(textos)
    tokens_tapa = _tokens(textos)
    for b in datos["bloques"]:
        if b["clave"] not in retirados:
            continue
        tokens_titulo = _tokens(b.get("titulo", ""))
        comunes = tokens_titulo & tokens_tapa
        if normalizar_texto(b.get("titulo", "")) in norm_tapa or (
            tokens_titulo and len(comunes) >= max(3, 0.6 * len(tokens_titulo))
        ):
            riesgos.append({"tipo": "tapa_titulo_retirado", "ref": b["clave"],
                            "detalle": f"la tapa parece anunciar la nota retirada: {b.get('titulo', '')!r}"})
    return riesgos


def _estado_tapa(numero: str, datos: dict, rev: dict, retirados: set[str]) -> tuple[bool, str, list[dict]]:
    t = rev.get("tapa")
    if not t:
        return False, "sin elegir", []
    if not t.get("archivo"):
        return False, "elegida con una versión anterior del checkpoint: volvé a elegirla", []
    ruta = dir_salida(numero) / t["archivo"]
    if not ruta.exists() or hash_archivo(ruta) != t.get("hash_svg"):
        return False, "el archivo de la tapa elegida cambió o no existe", []
    if t.get("hash_meta") != hash_meta(datos):
        return False, "cambiaron el título del número o los metadatos de tapa después de elegirla", []
    riesgos = riesgos_tapa(numero, datos, ruta, retirados)
    nuevos = {clave_riesgo(r) for r in riesgos} - set(t.get("riesgos_aceptados", []))
    if nuevos:
        return False, "aparecieron riesgos nuevos en la tapa: " + ", ".join(sorted(nuevos)), riesgos
    return True, "", riesgos


def resumen(numero: str, datos: dict | None = None, rev: dict | None = None) -> dict:
    datos = datos or cargar(numero)
    rev_en_disco = cargar_revision(numero)
    rev = rev if rev is not None else (rev_en_disco or revision_vacia(numero))

    retirados = _retirados(rev)
    filas = []
    for b in datos["bloques"]:
        h = hash_bloque(b, datos)
        riesgos = riesgos_bloque(datos, b["clave"], retirados)
        decision = rev["decisiones"].get(b["clave"])
        motivo_vencida = ""
        if not decision:
            vigente = False
        elif decision["accion"] == "retirar":
            vigente = True
        elif decision.get("hash") != h:
            vigente, motivo_vencida = False, "el texto cambió después de aprobarse"
        else:
            nuevos = {clave_riesgo(r) for r in riesgos} - set(decision.get("riesgos_aceptados", []))
            vigente = not nuevos
            if nuevos:
                motivo_vencida = "aparecieron riesgos nuevos después de aprobarse: " + ", ".join(sorted(nuevos))
        filas.append({
            "clave": b["clave"],
            "seccion": b.get("seccion", b["clave"]),
            "hash": h,
            "riesgos": riesgos,
            "decision": decision,
            "vigente": vigente,
            "vencida": bool(decision) and not vigente,
            "motivo_vencida": motivo_vencida,
        })

    tapa_ok, tapa_motivo, tapa_riesgos = _estado_tapa(numero, datos, rev, retirados)

    pendientes = [f for f in filas if not f["vigente"]]
    publicados = {f["clave"]: f["hash"] for f in filas if f["vigente"] and f["decision"]["accion"] == "aprobar"}

    publicacion = rev.get("publicacion")
    publicacion_vigente = (
        bool(publicacion) and not pendientes and tapa_ok
        and publicacion.get("hashes") == publicados
        and publicacion.get("candidato") == rev["tapa"]["candidato"]
        and publicacion.get("hash_tapa") == rev["tapa"]["hash_svg"]
        and publicacion.get("hash_meta") == hash_meta(datos)
    )

    if publicacion_vigente:
        estado = "publicado"
    elif not pendientes and tapa_ok and publicados:
        estado = "aprobado"
    elif rev_en_disco is not None or rev["decisiones"]:
        estado = "en_revision"
    else:
        estado = "borrador"

    return {
        "numero": numero,
        "estado": estado,
        "filas": filas,
        "pendientes": pendientes,
        "bloqueantes": [f for f in pendientes if f["riesgos"]],
        "tapa_ok": tapa_ok,
        "tapa_motivo": tapa_motivo,
        "tapa_riesgos": tapa_riesgos,
        "tapa_elegida": rev.get("tapa"),
        "tapa_sugerida": (datos.get("tapa") or {}).get("ganador"),
        "publicacion_desactualizada": bool(publicacion) and not publicacion_vigente,
    }


# --------------------------------------------------------------------------- guarda humana

# Puntos de entrada de la terminal; los tests los reemplazan.
def _es_tty() -> bool:
    return sys.stdin.isatty()


def _pedir(prompt: str) -> str:
    return input(prompt)


def _pedir_secreto(prompt: str) -> str:
    return getpass.getpass(prompt)


def ruta_clave() -> Path:
    return CONFIG / "revisor.json"


def _derivar(frase: str, sal: bytes) -> bytes:
    return hashlib.scrypt(frase.encode("utf-8"), salt=sal, n=2**14, r=8, p=1, dklen=32)


def _mac(clave: bytes, mensaje: str) -> str:
    return hmac.new(clave, mensaje.encode("utf-8"), hashlib.sha256).hexdigest()


def huella(clave: bytes) -> str:
    return _mac(clave, "condor:huella")[:16]


def _exigir_terminal(accion: str) -> None:
    if not _es_tty():
        raise ErrorCheckpoint(
            f"'{accion}' registra una decisión editorial y requiere una terminal interactiva.\n"
            "Corré el comando vos, en tu terminal: un agente (incluido Claude) no puede aprobar un número."
        )


def _clave_desde_frase(cfg: dict, prompt: str) -> bytes:
    clave = _derivar(_pedir_secreto(prompt), bytes.fromhex(cfg["sal"]))
    if not hmac.compare_digest(_mac(clave, "condor:verificador"), cfg["verificador"]):
        raise ErrorCheckpoint("frase incorrecta: no se registró ninguna decisión")
    return clave


def configurar_clave(revisor: str | None) -> str:
    """Crea (o cambia) la frase secreta de quien revisa. Devuelve la huella de la clave."""
    revisor = _revisor(revisor)
    _exigir_terminal("configurar la clave de revisor/a")
    ruta = ruta_clave()
    if ruta.exists():
        _clave_desde_frase(json.loads(ruta.read_text(encoding="utf-8")), "Frase actual: ")
    frase = _pedir_secreto("Frase secreta nueva (no la compartas con ningún agente): ")
    if len(frase) < 8:
        raise ErrorCheckpoint("la frase tiene que tener al menos 8 caracteres")
    if _pedir_secreto("Repetila: ") != frase:
        raise ErrorCheckpoint("las frases no coinciden")
    sal = secrets.token_bytes(16)
    clave = _derivar(frase, sal)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_suffix(".tmp")
    tmp.write_text(json.dumps({
        "revisor": revisor, "sal": sal.hex(), "verificador": _mac(clave, "condor:verificador"),
        "huella": huella(clave), "fecha": ahora(),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(ruta)
    return huella(clave)


def exigir_humano(numero: str, accion: str) -> bytes:
    """Toda decisión de checkpoint la toma una persona: frase secreta + número tipeado.

    Devuelve la clave con la que se firma la decisión.
    """
    _exigir_terminal(accion)
    ruta = ruta_clave()
    if not ruta.exists():
        raise ErrorCheckpoint(
            "no hay clave de revisor/a configurada. Creala una vez, en tu terminal:\n"
            "  uv run condor clave --revisor \"Tu Nombre\""
        )
    clave = _clave_desde_frase(json.loads(ruta.read_text(encoding="utf-8")), f"Frase de revisor/a para '{accion}': ")
    respuesta = _pedir(f"Para confirmar '{accion}' escribí el número del ejemplar ({numero}): ")
    if respuesta.strip() != numero:
        raise ErrorCheckpoint("confirmación incorrecta: no se registró ninguna decisión")
    return clave


def _mensaje_firma(numero: str, objeto: str, decision: dict) -> str:
    return _json_canonico({"numero": numero, "objeto": objeto,
                           "decision": {k: v for k, v in decision.items() if k != "firma"}})


def _firmar(clave: bytes, numero: str, objeto: str, decision: dict) -> dict:
    decision["huella"] = huella(clave)
    decision["firma"] = _mac(clave, _mensaje_firma(numero, objeto, decision))
    return decision


def _firma_ok(clave: bytes, numero: str, objeto: str, decision: dict) -> bool:
    firma = decision.get("firma") or ""
    return hmac.compare_digest(_mac(clave, _mensaje_firma(numero, objeto, decision)), firma)


def verificar_firmas(clave: bytes, numero: str, rev: dict) -> list[str]:
    malas = [f"bloque {c}" for c, d in rev["decisiones"].items() if not _firma_ok(clave, numero, f"bloque:{c}", d)]
    if rev.get("tapa") and not _firma_ok(clave, numero, "tapa", rev["tapa"]):
        malas.append("tapa")
    return malas


def _revisor(revisor: str | None) -> str:
    revisor = (revisor or os.environ.get("USER") or "").strip()
    if not revisor:
        raise ErrorCheckpoint("indicá quién revisa con --revisor")
    return revisor


def _revision_iniciada(numero: str) -> dict:
    rev = cargar_revision(numero)
    if rev is None:
        raise ErrorCheckpoint(f"primero generá el paquete de revisión: condor revision {numero}")
    return rev


# --------------------------------------------------------------------------- acciones
#
# Cada acción valida primero (para no pedir la frase en vano), después exige a la persona
# y recién ahí, bajo el lock, relee datos y revisión, vuelve a validar y escribe: lo que se
# registra es lo que había en disco en el momento de la decisión, no antes del prompt.

def iniciar_revision(numero: str) -> dict:
    datos = cargar(numero)
    with _bloqueo(numero):
        rev = cargar_revision(numero)
        if rev is None:
            rev = revision_vacia(numero)
            rev["historial"].append({"fecha": ahora(), "accion": "iniciar_revision"})
            guardar_revision(numero, rev)
    return resumen(numero, datos, rev)


def _decidir_aprobaciones(datos: dict, rev: dict, claves: list[str], todo: bool, nota: str):
    retirados = _retirados(rev)
    objetivos = list(dict.fromkeys(claves + ([b["clave"] for b in datos["bloques"]] if todo else [])))
    objetivos = [c for c in objetivos if c in claves or c not in retirados]
    aprobar_, salteados = [], []
    for clave in objetivos:
        riesgos = riesgos_bloque(datos, clave, retirados)
        if riesgos and clave not in claves:
            salteados.append({"clave": clave, "riesgos": riesgos})
            continue
        if riesgos and not nota.strip():
            raise ErrorCheckpoint(
                f"el bloque {clave!r} tiene {len(riesgos)} riesgo(s) abierto(s); aprobarlo exige --nota "
                "explicando por qué se publica igual (o retiralo con: condor retirar)"
            )
        aprobar_.append((clave, riesgos))
    return aprobar_, salteados


def aprobar(numero: str, claves: list[str], todo: bool, revisor: str | None, nota: str = "") -> dict:
    datos = cargar(numero)
    rev = _revision_iniciada(numero)
    if not claves and not todo:
        raise ErrorCheckpoint("indicá --bloque CLAVE (uno o más) o --todo")
    for c in claves:
        bloque(datos, c)  # valida que exista
    revisor = _revisor(revisor)
    _decidir_aprobaciones(datos, rev, claves, todo, nota)

    clave_firma = exigir_humano(numero, "aprobar")
    with _bloqueo(numero):
        datos = cargar(numero)
        rev = _revision_iniciada(numero)
        a_aprobar, salteados = _decidir_aprobaciones(datos, rev, claves, todo, nota)
        for clave, riesgos in a_aprobar:
            rev["decisiones"][clave] = _firmar(clave_firma, numero, f"bloque:{clave}", {
                "accion": "aprobar",
                "hash": hash_bloque(bloque(datos, clave), datos),
                "revisor": revisor,
                "fecha": ahora(),
                "nota": nota,
                "riesgos_aceptados": [clave_riesgo(r) for r in riesgos],
            })
        aprobados = [c for c, _ in a_aprobar]
        rev["historial"].append({"fecha": ahora(), "accion": "aprobar", "revisor": revisor, "bloques": aprobados})
        guardar_revision(numero, rev)
    return {"aprobados": aprobados, "salteados": salteados}


def retirar(numero: str, clave: str, revisor: str | None, motivo: str) -> dict:
    datos = cargar(numero)
    _revision_iniciada(numero)
    bloque(datos, clave)
    if not motivo.strip():
        raise ErrorCheckpoint("retirar un bloque exige --motivo")
    revisor = _revisor(revisor)
    clave_firma = exigir_humano(numero, f"retirar {clave}")
    with _bloqueo(numero):
        rev = _revision_iniciada(numero)
        rev["decisiones"][clave] = _firmar(clave_firma, numero, f"bloque:{clave}", {
            "accion": "retirar", "revisor": revisor, "fecha": ahora(), "motivo": motivo,
        })
        rev["historial"].append({"fecha": ahora(), "accion": "retirar", "revisor": revisor, "bloque": clave})
        guardar_revision(numero, rev)
    publicado = clave in ((rev.get("publicacion") or {}).get("hashes") or {})
    return {"sigue_publicado": publicado}


def _candidato(datos: dict, candidato_id: str) -> dict:
    cand = next((c for c in candidatos_tapa(datos) if c["id"] == candidato_id), None)
    if cand is None:
        ids = ", ".join(c["id"] for c in candidatos_tapa(datos)) or "(ninguno)"
        raise ErrorCheckpoint(f"no hay candidato de tapa {candidato_id!r}; candidatos: {ids}")
    return cand


def _validar_tapa(numero: str, datos: dict, rev: dict, ruta: Path, candidato_id: str,
                  requeridos: tuple[str, ...], nota: str) -> tuple[dict, list[dict]]:
    from .svg import validar

    resultado = validar(ruta, requeridos or ("Cóndor", numero))
    if not resultado["ok"]:
        raise ErrorCheckpoint(f"la tapa {candidato_id} no pasa la validación: " + "; ".join(resultado["errores"]))
    riesgos = riesgos_tapa(numero, datos, ruta, _retirados(rev))
    if riesgos and not nota.strip():
        raise ErrorCheckpoint(
            f"la tapa {candidato_id} tiene riesgos: " + "; ".join(r["detalle"] for r in riesgos)
            + ".\nElegí otra, o elegila igual con --nota explicando por qué."
        )
    return resultado, riesgos


def elegir_tapa(numero: str, candidato_id: str, revisor: str | None, requeridos: tuple[str, ...] = (),
                nota: str = "") -> dict:
    datos = cargar(numero)
    rev = _revision_iniciada(numero)
    _validar_tapa(numero, datos, rev, ruta_candidato(numero, _candidato(datos, candidato_id)),
                  candidato_id, requeridos, nota)
    revisor = _revisor(revisor)

    clave_firma = exigir_humano(numero, f"elegir tapa {candidato_id}")
    with _bloqueo(numero):
        datos = cargar(numero)
        rev = _revision_iniciada(numero)
        # se leen los bytes una sola vez y se guarda una copia con nombre por contenido:
        # lo que se valida, se hashea y se publica es exactamente el mismo archivo
        contenido = ruta_candidato(numero, _candidato(datos, candidato_id)).read_bytes()
        sha = hashlib.sha256(contenido).hexdigest()
        relativa = Path("tapa") / f"elegida-{sha[:16]}.svg"
        destino = dir_salida(numero) / relativa
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(contenido)
        resultado, riesgos = _validar_tapa(numero, datos, rev, destino, candidato_id, requeridos, nota)
        rev["tapa"] = _firmar(clave_firma, numero, "tapa", {
            "candidato": candidato_id, "archivo": str(relativa), "hash_svg": sha, "hash_meta": hash_meta(datos),
            "riesgos_aceptados": [clave_riesgo(r) for r in riesgos], "nota": nota,
            "revisor": revisor, "fecha": ahora(),
        })
        rev["historial"].append({"fecha": ahora(), "accion": "elegir_tapa", "revisor": revisor, "candidato": candidato_id})
        guardar_revision(numero, rev)
    return resultado


def verificar_publicable(numero: str, datos: dict | None = None, rev: dict | None = None) -> dict:
    res = resumen(numero, datos, rev)
    problemas = []
    for f in res["pendientes"]:
        motivo = f"aprobación vencida ({f['motivo_vencida']})" if f["vencida"] else "sin decisión"
        problemas.append(f"bloque {f['clave']}: {motivo}")
    if not res["tapa_ok"]:
        problemas.append(f"tapa: {res['tapa_motivo']}")
    if not any(f["vigente"] and f["decision"]["accion"] == "aprobar" for f in res["filas"]):
        problemas.append("no hay ningún bloque aprobado")
    if problemas:
        raise ErrorCheckpoint("no se puede publicar todavía:\n  - " + "\n  - ".join(problemas))
    return res


def publicar(numero: str, revisor: str | None) -> list[Path]:
    from .render import render_final

    verificar_publicable(numero)
    revisor = _revisor(revisor)
    clave_firma = exigir_humano(numero, "publicar")
    with _bloqueo(numero):
        # una sola lectura: se verifica y se publica exactamente lo mismo
        datos = cargar(numero)
        rev = _revision_iniciada(numero)
        malas = verificar_firmas(clave_firma, numero, rev)
        if malas:
            raise ErrorCheckpoint(
                "hay decisiones sin una firma válida de tu clave (¿las escribió alguien más, o se editó "
                "revision.json a mano?): " + ", ".join(malas) + ". Volvé a tomarlas vos."
            )
        res = verificar_publicable(numero, datos, rev)
        archivos = render_final(numero, datos, rev, revisor)
        rev["publicacion"] = _firmar(clave_firma, numero, "publicacion", {
            "revisor": revisor,
            "fecha": ahora(),
            "hashes": {f["clave"]: f["hash"] for f in res["filas"] if f["vigente"] and f["decision"]["accion"] == "aprobar"},
            "candidato": rev["tapa"]["candidato"],
            "hash_tapa": rev["tapa"]["hash_svg"],
            "hash_meta": hash_meta(datos),
            "archivos": {str(a.relative_to(dir_salida(numero))): hash_archivo(a) for a in archivos},
        })
        rev["historial"].append({"fecha": ahora(), "accion": "publicar", "revisor": revisor})
        guardar_revision(numero, rev)
    return archivos
