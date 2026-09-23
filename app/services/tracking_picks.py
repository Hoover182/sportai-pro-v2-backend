"""Picks Top3 REALES del sistema de tracking -- los que se registraron
una sola vez antes del partido en el repo privado
Hoover182/sportai-top3-registro (top3_registro.csv) y su resultado
marcado despues (top3_resultados.csv), cruzados por
(fixture_id, posicion). NO recalcula nada: el "top3" de
get_analisis_partido() se vuelve a simular en cada llamada (y para un
partido ya terminado la simulacion incluye ese mismo partido en el
historial), asi que no sirve para mostrar lo que el modelo dijo.

Los repos siguen separados: el backend lee el de tracking via la API
de GitHub con un fine-grained token de solo lectura en la variable de
entorno TRACKING_REPO_TOKEN. Los 4 CSV se leen del MISMO commit (evita
cruzar un registro nuevo con resultados viejos si el workflow commitea
en el medio) y el indice armado se cachea en memoria: el SHA de main se
vuelve a chequear cada TTL_SEGUNDOS (pedido condicional con ETag), y
solo se descargan los archivos si hubo un commit nuevo.

Reglas espejadas del repo de tracking (no se importa su codigo):
- "Pendiente" = ausencia de fila en top3_resultados.csv.
- Clave 1:1 (fixture_id, posicion): una clave duplicada o un resultado
  sin pick registrado es un error visible, nunca se elige una fila.
- top3_contaminados.csv: picks sin base real, se EXCLUYEN de la
  respuesta (se informa cuantos en picks_excluidos).
"""
import io
import os
import threading
import time
from collections import Counter
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests

REPO = "Hoover182/sportai-top3-registro"
RAMA = "main"
API = "https://api.github.com"
ARCHIVOS = {
    "registro": "datos/top3_registro.csv",
    "resultados": "datos/top3_resultados.csv",
    "contaminados": "datos/top3_contaminados.csv",
    "omitidos": "datos/top3_omitidos.csv",
}
# Pueden no existir todavia en el repo sin que sea un error (el esquema
# del tracking trata un resultados.csv ausente como "todo pendiente").
OPCIONALES = {"resultados", "contaminados", "omitidos"}

TTL_SEGUNDOS = 600        # el workflow commitea como mucho 2 veces por dia
REINTENTO_FALLO = 60      # tras un fallo, no martillar GitHub en cada request
TIMEOUT = 15

# Mismos valores que el repo de tracking: DIAS_MARGEN_STATS
# (resultados_schema.py) y DIAS_POSTERGADO (marcar_resultados.py).
DIAS_MARGEN_STATS = 7
DIAS_POSTERGADO = 21
# El marcado corre 2 veces por dia: 1 dia de holgura despues del plazo
# mas largo antes de considerar que un pick sin resultado esta atrasado.
DIAS_ATRASADO = DIAS_POSTERGADO + 1

FMT_TS = "%Y-%m-%dT%H:%M:%SZ"
RESULTADOS_MARCADOS = ("ACIERTO", "FALLO", "NO_EVALUABLE", "ANULADO", "NO_PARSEABLE")
CLAVES_RESUMEN = {
    "ACIERTO": "aciertos", "FALLO": "fallos", "PENDIENTE": "pendientes",
    "NO_EVALUABLE": "no_evaluables", "ANULADO": "anulados", "NO_PARSEABLE": "no_parseables",
}


class TrackingError(Exception):
    """Datos del tracking inconsistentes o ilegibles."""


# ----------------------------------------------------------------------------- funciones puras
def _ts_a_dt(s):
    return datetime.strptime(s, FMT_TS).replace(tzinfo=timezone.utc)


def _dt_a_ts(dt):
    return dt.strftime(FMT_TS)


def _num(s):
    if s is None or str(s).strip() == "":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _texto(s):
    return None if s is None or str(s).strip() == "" else str(s)


def _claves(df, nombre):
    try:
        return [(int(f), int(p)) for f, p in zip(df["fixture_id"], df["posicion"])]
    except (KeyError, ValueError) as e:
        raise TrackingError(f"{nombre}: fixture_id/posicion ilegible ({e})")


def construir_indice(registro, resultados, contaminados, omitidos):
    """DataFrames (dtype=str, sin NaN) -> indice por fixture_id. Valida la
    clave 1:1 igual que unir_con_registro() del repo de tracking."""
    claves_reg = _claves(registro, "registro")
    claves_res = _claves(resultados, "resultados")
    for nombre, claves in (("registro", claves_reg), ("resultados", claves_res)):
        duplicadas = sorted(c for c, n in Counter(claves).items() if n > 1)
        if duplicadas:
            raise TrackingError(f"{nombre}: claves (fixture_id, posicion) duplicadas {duplicadas[:5]}")
    huerfanos = sorted(set(claves_res) - set(claves_reg))
    if huerfanos:
        raise TrackingError(f"resultados sin pick en el registro: {huerfanos[:5]}")
    invalidos = sorted(set(resultados["resultado"]) - set(RESULTADOS_MARCADOS)) if len(resultados) else []
    if invalidos:
        raise TrackingError(f"resultados con valor invalido: {invalidos[:5]}")

    por_fixture = {}
    for clave, fila in zip(claves_reg, registro.to_dict("records")):
        por_fixture.setdefault(clave[0], []).append(fila)
    for filas in por_fixture.values():
        filas.sort(key=lambda f: int(f["posicion"]))

    omitidos_por_fixture = {}
    for fila in omitidos.to_dict("records"):
        # Si el registrador lo omitio en mas de una corrida, vale la ultima.
        omitidos_por_fixture[int(fila["fixture_id"])] = fila

    return {
        "registro": por_fixture,
        "resultados": dict(zip(claves_res, resultados.to_dict("records"))),
        "contaminados": set(_claves(contaminados, "contaminados")),
        "omitidos": omitidos_por_fixture,
    }


def _pendiente_motivo(kickoff, ahora):
    if ahora < kickoff:
        return "partido_no_jugado"
    if ahora < kickoff + timedelta(days=DIAS_ATRASADO):
        return "esperando_marcado"
    return "atrasado"


def _armar_pick(fila_reg, fila_res, ahora):
    kickoff = _ts_a_dt(fila_reg["fecha_partido_utc"])
    pick = {
        "posicion": int(fila_reg["posicion"]),
        "nombre_pick": fila_reg["nombre_pick"],
        "prob_pct": _num(fila_reg["prob_pct"]),
        "cuota": _num(fila_reg["cuota"]),
        "fuente_cuota": _texto(fila_reg["fuente_real"]),
        "resultado": "PENDIENTE",
        "pendiente_motivo": None,
        "margen_hasta_utc": None,
        "motivo": None,
        "valor_real": None,
        "mercado_id": None,
        "ambito": None,
        "lado": None,
        "linea": None,
        "estado_partido": None,
        "resuelto_en_utc": None,
    }
    if fila_res is None:
        pick["pendiente_motivo"] = _pendiente_motivo(kickoff, ahora)
        pick["margen_hasta_utc"] = _dt_a_ts(kickoff + timedelta(days=DIAS_MARGEN_STATS))
        return pick
    pick.update({
        "resultado": fila_res["resultado"],
        "motivo": _texto(fila_res["motivo"]),
        # Texto tal cual lo escribio el marcado: un numero ("2") en O/U,
        # un marcador ("2-1") en mercados de resultado.
        "valor_real": _texto(fila_res["valor_real"]),
        "mercado_id": _texto(fila_res["mercado_id"]),
        "ambito": _texto(fila_res["ambito"]),
        "lado": _texto(fila_res["lado"]),
        "linea": _num(fila_res["linea"]),
        "estado_partido": _texto(fila_res["estado_partido"]),
        "resuelto_en_utc": _texto(fila_res["resuelto_en_utc"]),
    })
    return pick


def _respuesta_vacia(fixture_id, estado):
    return {
        "fixture_id": fixture_id,
        "estado_tracking": estado,
        "motivo_omision": None,
        "liga": None,
        "local": None,
        "visitante": None,
        "fecha_partido_utc": None,
        "registrado_en_utc": None,
        "picks": [],
        "picks_excluidos": 0,
        "resumen": {v: 0 for v in CLAVES_RESUMEN.values()},
    }


def armar_picks_fixture(indice, fixture_id, ahora):
    """Respuesta de un fixture. indice=None -> tracking_no_disponible.
    estado_tracking distingue: registrado / omitido (el registrador lo
    vio pero no genero picks) / sin_registro (nunca entro al tracking) /
    tracking_no_disponible (no se pudo leer, NO es "sin picks")."""
    if indice is None:
        return _respuesta_vacia(fixture_id, "tracking_no_disponible")

    filas = indice["registro"].get(fixture_id)
    if not filas:
        omitido = indice["omitidos"].get(fixture_id)
        if omitido is None:
            return _respuesta_vacia(fixture_id, "sin_registro")
        r = _respuesta_vacia(fixture_id, "omitido")
        r.update({
            "motivo_omision": _texto(omitido["motivo"]),
            "liga": omitido["liga"],
            "local": omitido["local"],
            "visitante": omitido["visitante"],
            "fecha_partido_utc": omitido["fecha_partido_utc"],
            "registrado_en_utc": omitido["registrado_en_utc"],
        })
        return r

    r = _respuesta_vacia(fixture_id, "registrado")
    primera = filas[0]
    r.update({
        "liga": primera["liga"],
        "local": primera["local"],
        "visitante": primera["visitante"],
        "fecha_partido_utc": primera["fecha_partido_utc"],
        "registrado_en_utc": primera["registrado_en_utc"],
    })
    for fila in filas:
        clave = (fixture_id, int(fila["posicion"]))
        if clave in indice["contaminados"]:
            r["picks_excluidos"] += 1
            continue
        pick = _armar_pick(fila, indice["resultados"].get(clave), ahora)
        r["picks"].append(pick)
        r["resumen"][CLAVES_RESUMEN[pick["resultado"]]] += 1
    return r


# ----------------------------------------------------------------------------- lectura desde GitHub
_lock = threading.Lock()
_cache = {
    "indice": None,
    "sha": None,
    "etag": None,
    "leido_en_utc": None,
    "proximo_chequeo": 0.0,   # time.monotonic()
    "desactualizado": False,
}


def _headers(token, accept):
    return {
        "Authorization": f"Bearer {token}",
        "Accept": accept,
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _sha_main(token, etag):
    """-> (sha, etag) o (None, etag) si no cambio desde etag (304: con
    token, un 304 no consume cuota de la API)."""
    headers = _headers(token, "application/vnd.github.sha")
    if etag:
        headers["If-None-Match"] = etag
    resp = requests.get(f"{API}/repos/{REPO}/commits/{RAMA}", headers=headers, timeout=TIMEOUT)
    if resp.status_code == 304:
        return None, etag
    resp.raise_for_status()
    return resp.text.strip(), resp.headers.get("ETag")


def _leer_csv(token, clave, sha):
    resp = requests.get(
        f"{API}/repos/{REPO}/contents/{ARCHIVOS[clave]}",
        headers=_headers(token, "application/vnd.github.raw"),
        params={"ref": sha},
        timeout=TIMEOUT,
    )
    if resp.status_code == 404 and clave in OPCIONALES:
        return pd.DataFrame(columns=["fixture_id", "posicion"])
    resp.raise_for_status()
    texto = resp.content.decode("utf-8-sig")
    return pd.read_csv(io.StringIO(texto), dtype=str, keep_default_na=False)


def _descargar_indice(token, sha):
    dfs = {clave: _leer_csv(token, clave, sha) for clave in ARCHIVOS}
    return construir_indice(dfs["registro"], dfs["resultados"], dfs["contaminados"], dfs["omitidos"])


def obtener_indice():
    """-> (indice o None, meta de la fuente). Nunca lanza: un fallo de red,
    token o datos deja el ultimo indice bueno marcado como desactualizado,
    o None si nunca se pudo leer."""
    with _lock:
        ahora = time.monotonic()
        if ahora >= _cache["proximo_chequeo"]:
            token = os.environ.get("TRACKING_REPO_TOKEN", "")
            try:
                if not token:
                    raise TrackingError("falta la variable de entorno TRACKING_REPO_TOKEN")
                sha, etag = _sha_main(token, _cache["etag"] if _cache["indice"] is not None else None)
                if sha is not None and sha != _cache["sha"]:
                    _cache["indice"] = _descargar_indice(token, sha)
                    _cache["sha"] = sha
                    _cache["leido_en_utc"] = _dt_a_ts(datetime.now(timezone.utc))
                _cache["etag"] = etag
                _cache["desactualizado"] = False
                _cache["proximo_chequeo"] = ahora + TTL_SEGUNDOS
            except Exception as e:
                print(f"AVISO tracking_picks: no se pudo leer {REPO}: {type(e).__name__}: {e}")
                _cache["desactualizado"] = _cache["indice"] is not None
                _cache["proximo_chequeo"] = ahora + REINTENTO_FALLO
        meta = {
            "commit_tracking": _cache["sha"][:7] if _cache["sha"] else None,
            "leido_en_utc": _cache["leido_en_utc"],
            "datos_desactualizados": _cache["desactualizado"],
        }
        return _cache["indice"], meta


def get_picks_registrados(fixture_id):
    indice, meta = obtener_indice()
    respuesta = armar_picks_fixture(indice, int(fixture_id), datetime.now(timezone.utc))
    respuesta["fuente"] = meta
    return respuesta
