"""Alineaciones de un partido para la pestana "Alineacion" -- endpoint
propio (/futbol/alineaciones), independiente de /partido-detalle (cuyo
campo "alineaciones" queda intacto).

Fuente: UNA llamada a api-football /fixtures?id=, que en la misma
respuesta trae el estado del partido, que equipo es local (teams.home)
y las alineaciones (mismo formato que fixtures/lineups: team, coach,
formation, startXI, substitutes). Posicion: api-football solo da una
letra (G/D/M/F); se normaliza a texto para la vista simple y se
conserva la letra original en posicion_original.

Cobertura real medida en 20 partidos de 18 ligas: 70% completa, 20%
parcial (un equipo sin formacion/grid/tecnico, o sin posiciones), 10%
sin alineacion. Por eso cada equipo trae su propia "cobertura" con lo
que falta, en vez de un solo booleano "lista vacia".

Cache en memoria por fixture_id:
- partido terminado + los 2 equipos completos -> permanente (sin TTL):
  un partido terminado no cambia.
- partido terminado sin alineacion o parcial -> TTL_INCOMPLETA:
  api-football a veces completa las alineaciones horas despues.
- partido no terminado -> TTL_NO_TERMINADO, sin alineaciones: la
  pantalla es post-partido; el TTL evita gastar una llamada por cada
  vista de un partido que todavia no se jugo.
- error de la API/red -> nunca se cachea.
"""
import os
import threading
import time
from datetime import datetime, timezone

import requests

BASE_URL = "https://v3.football.api-sports.io"
TIMEOUT = 15
ESTADOS_TERMINALES = ("FT", "AET", "PEN")
TTL_INCOMPLETA = 6 * 3600
TTL_NO_TERMINADO = 600

POSICIONES = {"G": "arquero", "D": "defensor", "M": "mediocampista", "F": "delantero"}


def _jugador(entrada, titular):
    p = (entrada or {}).get("player") or {}
    pos = p.get("pos")
    jugador = {
        "id": p.get("id"),
        "nombre": p.get("name"),
        "dorsal": p.get("number"),
        "posicion": POSICIONES.get(pos),
        "posicion_original": pos,
    }
    if titular:
        grid = p.get("grid")
        fila = columna = None
        try:
            fila, columna = (int(x) for x in grid.split(":"))
        except (AttributeError, ValueError):
            pass
        jugador.update({"grid": grid, "fila": fila, "columna": columna})
    return jugador


def _cobertura_equipo(equipo):
    titulares = equipo["titulares"]
    faltantes = []
    if len(titulares) != 11:
        faltantes.append("titulares")
    if not equipo["suplentes"]:
        faltantes.append("suplentes")
    if not equipo["formacion"]:
        faltantes.append("formacion")
    if not titulares or any(j["posicion"] is None for j in titulares):
        faltantes.append("posiciones")
    if not titulares or any(j["fila"] is None for j in titulares):
        faltantes.append("grid")
    if not equipo["tecnico"]:
        faltantes.append("tecnico")
    return {"completa": not faltantes, "faltantes": faltantes}


def formatear_alineaciones(fixture):
    """Un elemento de /fixtures?id= -> (estado, estado_partido, equipos).
    Funcion pura: sin red ni cache."""
    estado_partido = ((fixture.get("fixture") or {}).get("status") or {}).get("short")
    if estado_partido not in ESTADOS_TERMINALES:
        return "partido_no_terminado", estado_partido, []
    id_local = ((fixture.get("teams") or {}).get("home") or {}).get("id")
    equipos = []
    for e in fixture.get("lineups") or []:
        team = e.get("team") or {}
        equipo = {
            "lado": None if id_local is None else ("local" if team.get("id") == id_local else "visitante"),
            "equipo": team.get("name"),
            "equipo_id": team.get("id"),
            "tecnico": (e.get("coach") or {}).get("name"),
            "formacion": e.get("formation"),
            "titulares": [_jugador(j, True) for j in e.get("startXI") or []],
            "suplentes": [_jugador(j, False) for j in e.get("substitutes") or []],
        }
        equipo["cobertura"] = _cobertura_equipo(equipo)
        equipos.append(equipo)
    equipos.sort(key=lambda eq: eq["lado"] != "local")
    if not equipos:
        return "sin_alineacion", estado_partido, []
    return "disponible", estado_partido, equipos


def _armar_respuesta(fixture_id, estado, estado_partido, equipos):
    completa = len(equipos) == 2 and all(eq["cobertura"]["completa"] for eq in equipos)
    return {
        "fixture_id": fixture_id,
        "estado": estado,
        "estado_partido": estado_partido,
        "cobertura_completa": completa,
        "equipos": equipos,
    }


_lock = threading.Lock()
_cache = {}  # fixture_id -> (respuesta, vence_en monotonic o None = permanente)


def _consultar_api(fixture_id):
    key = os.environ.get("APIFOOTBALL_KEY", "")
    if not key:
        raise RuntimeError("falta la variable de entorno APIFOOTBALL_KEY")
    resp = requests.get(f"{BASE_URL}/fixtures", headers={"x-apisports-key": key},
                        params={"id": fixture_id}, timeout=TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    # api-football responde 200 con "errors" no vacio ante key invalida o
    # cuota agotada -- eso es una falla, no "partido sin alineacion".
    if data.get("errors"):
        raise RuntimeError(f"api-football: {data['errors']}")
    return data.get("response") or []


def get_alineaciones(fixture_id):
    fixture_id = int(fixture_id)
    with _lock:
        entrada = _cache.get(fixture_id)
        if entrada and (entrada[1] is None or time.monotonic() < entrada[1]):
            return {**entrada[0], "fuente": {**entrada[0]["fuente"], "cacheado": True}}
    try:
        response = _consultar_api(fixture_id)
    except Exception as e:
        print(f"AVISO alineaciones: fixture {fixture_id}: {type(e).__name__}: {e}")
        r = _armar_respuesta(fixture_id, "fuente_no_disponible", None, [])
        r["fuente"] = {"consultado_en_utc": None, "cacheado": False}
        return r
    if not response:
        estado, estado_partido, equipos = "partido_no_encontrado", None, []
    else:
        estado, estado_partido, equipos = formatear_alineaciones(response[0])
    r = _armar_respuesta(fixture_id, estado, estado_partido, equipos)
    r["fuente"] = {"consultado_en_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "cacheado": False}
    if estado == "disponible" and r["cobertura_completa"]:
        vence = None
    elif estado in ("disponible", "sin_alineacion"):
        vence = time.monotonic() + TTL_INCOMPLETA
    else:  # partido_no_terminado / partido_no_encontrado
        vence = time.monotonic() + TTL_NO_TERMINADO
    with _lock:
        _cache[fixture_id] = (r, vence)
    return r
