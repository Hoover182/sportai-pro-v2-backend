import requests
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

API_KEY = "7be9c4250da301a68726beedbe2b382a"
BASE_URL = "https://v3.football.api-sports.io"

MINUTOS_MIN_TEMPORADA = 90
MAX_JUGADORES_POR_SECCION = 5

POSICIONES_PORTERO   = ["goalkeeper", "gk", "g", "portero"]
POSICIONES_DEFENSA   = ["defender", "d", "cb", "lb", "rb", "wb", "defensa"]
POSICIONES_MEDIO     = ["midfielder", "m", "cm", "dm", "am", "mediocampista", "medio"]
POSICIONES_DELANTERO = ["attacker", "forward", "f", "lw", "rw", "ss", "cf", "st", "delantero"]


def api_get(endpoint, params=None):
    headers = {"x-apisports-key": API_KEY}
    url = f"{BASE_URL}/{endpoint}"
    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        if response.status_code == 200:
            return response.json()
        return {}
    except Exception as e:
        print(f"  Error en {endpoint}: {e}")
        return {}


def clasificar_posicion(pos):
    pos_lower = (pos or "").lower().strip()
    if not pos_lower:
        return "otro"
    if any(p in pos_lower for p in POSICIONES_PORTERO):
        return "portero"
    if any(p in pos_lower for p in POSICIONES_DEFENSA):
        return "defensa"
    if any(p in pos_lower for p in POSICIONES_MEDIO):
        return "medio"
    if any(p in pos_lower for p in POSICIONES_DELANTERO):
        return "delantero"
    return "otro"


def simular_jugador(media, lineas):
    media = max(float(media), 0.05)
    valores = np.random.poisson(media, 10000).astype(float)
    resultado = {}
    for linea in lineas:
        resultado[str(linea)] = {
            "over":  round(float(np.mean(valores > linea)) * 100, 1),
            "under": round(float(np.mean(valores < linea)) * 100, 1)
        }
    return resultado


def obtener_fixture_id(liga_id, temporada, equipo_local, equipo_visitante, fecha, df=None):
    if df is not None and "fixture_id" in df.columns:
        try:
            partido = df[
                (df["equipo_local"] == equipo_local) &
                (df["equipo_visitante"] == equipo_visitante)
            ].sort_values("fecha", ascending=False)
            if not partido.empty:
                fid = partido.iloc[0]["fixture_id"]
                if fid and not pd.isna(fid):
                    return int(fid)
        except Exception:
            pass

    try:
        if isinstance(fecha, str):
            fecha_dt = datetime.strptime(fecha[:10], "%Y-%m-%d")
        else:
            fecha_dt = datetime.now()
    except Exception:
        fecha_dt = datetime.now()

    date_from = (fecha_dt - timedelta(days=1)).strftime("%Y-%m-%d")
    date_to   = (fecha_dt + timedelta(days=1)).strftime("%Y-%m-%d")

    data = api_get("fixtures", params={
        "league": liga_id,
        "season": temporada,
        "from": date_from,
        "to": date_to
    })

    local_lower = equipo_local.lower()
    visit_lower = equipo_visitante.lower()

    for f in data.get("response", []):
        home = f.get("teams", {}).get("home", {}).get("name", "").lower()
        away = f.get("teams", {}).get("away", {}).get("name", "").lower()
        if (local_lower[:6] in home or home[:6] in local_lower) and \
           (visit_lower[:6] in away or away[:6] in visit_lower):
            return f["fixture"]["id"]

    return None


import os
import json
from datetime import datetime, timedelta

CACHE_JUGADORES_DIR = os.path.join(os.path.dirname(__file__), "cache_jugadores")
CACHE_DIAS_VALIDEZ = 3

def _cache_path(team_id, liga_id, temporada):
    os.makedirs(CACHE_JUGADORES_DIR, exist_ok=True)
    return os.path.join(CACHE_JUGADORES_DIR, f"team_{team_id}_{liga_id}_{temporada}.json")


def _leer_cache_jugadores(team_id, liga_id, temporada):
    path = _cache_path(team_id, liga_id, temporada)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        fecha_guardado = datetime.fromisoformat(data["_fecha_cache"])
        if datetime.now() - fecha_guardado > timedelta(days=CACHE_DIAS_VALIDEZ):
            return None
        return data["response"]
    except Exception:
        return None


def _guardar_cache_jugadores(team_id, liga_id, temporada, response):
    path = _cache_path(team_id, liga_id, temporada)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"_fecha_cache": datetime.now().isoformat(), "response": response}, f)
    except Exception:
        pass


JUGADORES_DATA_DIR = os.path.join(os.path.dirname(__file__), "jugadores_data")

def _leer_jugadores_data_por_nombre(nombre_equipo):
    """Busca el archivo descargado masivamente por nombre de equipo."""
    path = os.path.join(JUGADORES_DATA_DIR, f"{nombre_equipo.replace('/', '_')}.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("jugadores", [])
    except Exception:
        return None


def _cache_path_fixture_players(fixture_id):
    return os.path.join(CACHE_JUGADORES_DIR, f"fixture_{fixture_id}_players.json")


def obtener_stats_jugadores_fixture(fixture_id):
    """Devuelve las estadisticas reales de todos los jugadores de un partido especifico."""
    path = _cache_path_fixture_players(fixture_id)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    data = api_get("fixtures/players", params={"fixture": fixture_id})
    response = data.get("response", [])
    try:
        os.makedirs(CACHE_JUGADORES_DIR, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(response, f)
    except Exception:
        pass
    return response


def _normalizar_nombre(nombre):
    """Quita acentos y pasa a minusculas para comparar nombres de forma flexible."""
    import unicodedata
    nfkd = unicodedata.normalize("NFKD", nombre)
    sin_acentos = "".join(c for c in nfkd if not unicodedata.combining(c))
    return sin_acentos.lower().strip()


def _nombres_coinciden(nombre_a, nombre_b):
    """Compara nombres de forma flexible: exacto, o coincidencia de apellido
    (util cuando un lado tiene nombre abreviado tipo 'J. Ordonez' y el otro
    tiene el nombre completo 'Jorge Ordonez')."""
    a = _normalizar_nombre(nombre_a)
    b = _normalizar_nombre(nombre_b)
    if a == b:
        return True
    partes_a = a.replace(".", "").split()
    partes_b = b.replace(".", "").split()
    if not partes_a or not partes_b:
        return False
    apellido_a = partes_a[-1]
    apellido_b = partes_b[-1]
    if apellido_a != apellido_b or len(apellido_a) < 3:
        return False
    inicial_a = partes_a[0][0] if partes_a[0] else ""
    inicial_b = partes_b[0][0] if partes_b[0] else ""
    return inicial_a == inicial_b


def obtener_historial_jugador(nombre_jugador, fixture_ids, n=5):
    """Busca el desglose real de un jugador especifico en una lista de fixture_ids.
    Devuelve lista de dicts: [{fixture_id, rival, tiros_total, tiros_arco, goles, asistencias, tarjetas_amarillas}, ...]"""
    resultado = []
    for fid in fixture_ids[:n]:
        datos_fixture = obtener_stats_jugadores_fixture(fid)
        nombres_equipos = [eq.get("team", {}).get("name", "") for eq in datos_fixture]
        for equipo in datos_fixture:
            equipo_jugador = equipo.get("team", {}).get("name", "")
            rival = next((n for n in nombres_equipos if n != equipo_jugador), "")
            for j in equipo.get("players", []):
                nombre = j.get("player", {}).get("name", "")
                if not _nombres_coinciden(nombre, nombre_jugador):
                    continue
                stats = j.get("statistics", [{}])[0] if j.get("statistics") else {}
                shots = stats.get("shots", {}) or {}
                goals = stats.get("goals", {}) or {}
                cards = stats.get("cards", {}) or {}
                resultado.append({
                    "fixture_id": fid,
                    "rival": rival,
                    "tiros_total": shots.get("total"),
                    "tiros_arco": shots.get("on"),
                    "goles": goals.get("total"),
                    "asistencias": goals.get("assists"),
                    "tarjetas_amarillas": cards.get("yellow"),
                    "minutos": (stats.get("games", {}) or {}).get("minutes"),
                })
    return resultado


def obtener_squad_equipo(team_id, liga_id, temporada, nombre_equipo=None):
    if nombre_equipo:
        datos_masivos = _leer_jugadores_data_por_nombre(nombre_equipo)
        if datos_masivos:
            return datos_masivos
    cacheado = _leer_cache_jugadores(team_id, liga_id, temporada)
    if cacheado is not None:
        return cacheado
    data = api_get("players", params={
        "team": team_id,
        "league": liga_id,
        "season": temporada
    })
    response = data.get("response", [])
    if response:
        _guardar_cache_jugadores(team_id, liga_id, temporada, response)
    return response
    data = api_get("players", params={
        "team": team_id,
        "league": liga_id,
        "season": temporada
    })
    return data.get("response", [])


def _procesar_jugador(p, nombre_equipo):
    info = p.get("player", {})
    stats_list = p.get("statistics", [])
    if not stats_list:
        return None

    stats = stats_list[0]
    games = stats.get("games", {})
    pos = games.get("position", "") or ""
    tipo_pos = clasificar_posicion(pos)

    if tipo_pos in ["portero", "otro"]:
        return None

    minutos = games.get("minutes") or 0
    if minutos < MINUTOS_MIN_TEMPORADA:
        return None

    partidos = max(games.get("appearences") or 1, 1)

    goles_pg       = (stats.get("goals", {}).get("total")     or 0) / partidos
    asist_pg       = (stats.get("goals", {}).get("assists")   or 0) / partidos
    tiros_total_pg = (stats.get("shots", {}).get("total")     or 0) / partidos
    tiros_arco_pg  = (stats.get("shots", {}).get("on")        or 0) / partidos
    tarjetas_pg    = (stats.get("cards", {}).get("yellow")    or 0) / partidos
    faltas_pg      = (stats.get("fouls", {}).get("committed") or 0) / partidos
    fuera_juego_pg = (stats.get("offsides")                   or 0) / partidos

    return {
        "nombre":        info.get("name", "Desconocido"),
        "equipo":        nombre_equipo,
        "posicion":      pos,
        "posicion_tipo": tipo_pos,
        "minutos":       minutos,
        "partidos":      partidos,
        "goles_pg":      round(goles_pg, 2),
        "asist_pg":      round(asist_pg, 2),
        "tarjetas_pg":   round(tarjetas_pg, 2),
        "faltas_pg":     round(faltas_pg, 2),
        "_score_ataque":   goles_pg + asist_pg,
        "_score_defensa":  tarjetas_pg + faltas_pg,
        "_tiros_arco_media":  max(tiros_arco_pg,  0.1),
        "_tiros_total_media": max(tiros_total_pg, 0.2),
        "_asist_media":       max(asist_pg,       0.05),
        "_tarjetas_media":    max(tarjetas_pg,    0.05),
        "_faltas_media":      max(faltas_pg,      0.3),
        "_fuera_juego_media": max(fuera_juego_pg, 0.05),
    }


def _agregar_simulaciones_ataque(j):
    return {
        "nombre":   j["nombre"],
        "posicion": j["posicion"],
        "partidos": j["partidos"],
        "minutos":  j["minutos"],
        "goles_pg": j["goles_pg"],
        "asist_pg": j["asist_pg"],
        "tiros_arco":  simular_jugador(j["_tiros_arco_media"],  [0.5, 1.5, 2.5, 3.5]),
        "tiros_total": simular_jugador(j["_tiros_total_media"], [0.5, 1.5, 2.5, 3.5]),
        "asistencias": simular_jugador(j["_asist_media"],       [0.5, 1.5, 2.5]),
        "fuera_juego": simular_jugador(j["_fuera_juego_media"], [0.5, 1.5]),
    }


def _agregar_simulaciones_defensa(j):
    return {
        "nombre":      j["nombre"],
        "posicion":    j["posicion"],
        "partidos":    j["partidos"],
        "minutos":     j["minutos"],
        "tarjetas_pg": j["tarjetas_pg"],
        "faltas_pg":   j["faltas_pg"],
        "tarjetas": simular_jugador(j["_tarjetas_media"], [0.5, 1.5]),
        "faltas":   simular_jugador(j["_faltas_media"],   [0.5, 1.5, 2.5, 3.5]),
    }


def obtener_jugadores_partido(fixture_id, liga_id, temporada, nombre_local=None, nombre_visitante=None):
    """
    Devuelve TODOS los jugadores del partido (sin limite, sin separar ataque/defensa).
    Cada jugador trae TODAS las stats: tiros arco, totales, asistencias, fuera juego, tarjetas, faltas.
    Formato: {equipo_local: {jugadores: [...]}, equipo_visitante: {jugadores: [...]}}
    """
    data_fixture = api_get("fixtures", params={"id": fixture_id})
    equipos_info = []

    for f in data_fixture.get("response", []):
        home_id   = f.get("teams", {}).get("home", {}).get("id")
        home_name = f.get("teams", {}).get("home", {}).get("name", "")
        away_id   = f.get("teams", {}).get("away", {}).get("id")
        away_name = f.get("teams", {}).get("away", {}).get("name", "")
        if home_id:
            equipos_info.append({"id": home_id, "nombre": nombre_local or home_name})
        if away_id:
            equipos_info.append({"id": away_id, "nombre": nombre_visitante or away_name})

    if not equipos_info:
        return {}

    resultado = {}
    for equipo in equipos_info:
        team_id = equipo["id"]
        nombre_equipo = equipo["nombre"]

        squad = obtener_squad_equipo(team_id, liga_id, temporada, nombre_equipo=nombre_equipo)
        jugadores_equipo = []
        for p in squad:
            j = _procesar_jugador(p, nombre_equipo)
            if j:
                # Combinar TODAS las stats: ataque + defensa
                jugador_completo = {
                    "nombre":      j["nombre"],
                    "posicion":    j["posicion"],
                    "posicion_tipo": j["posicion_tipo"],
                    "partidos":    j["partidos"],
                    "minutos":     j["minutos"],
                    "goles_pg":    j["goles_pg"],
                    "asist_pg":    j["asist_pg"],
                    "tarjetas_pg": j["tarjetas_pg"],
                    "faltas_pg":   j["faltas_pg"],
                    "tiros_arco":  simular_jugador(j["_tiros_arco_media"],  [0.5, 1.5, 2.5, 3.5]),
                    "tiros_total": simular_jugador(j["_tiros_total_media"], [0.5, 1.5, 2.5, 3.5]),
                    "asistencias": simular_jugador(j["_asist_media"],       [0.5, 1.5, 2.5]),
                    "fuera_juego": simular_jugador(j["_fuera_juego_media"], [0.5, 1.5]),
                    "tarjetas":    simular_jugador(j["_tarjetas_media"],    [0.5, 1.5]),
                    "faltas":      simular_jugador(j["_faltas_media"],      [0.5, 1.5, 2.5, 3.5]),
                }
                jugadores_equipo.append(jugador_completo)

        # Ordenar por minutos (titulares primero) para que el listado sea util
        jugadores_equipo.sort(key=lambda x: x["minutos"], reverse=True)

        resultado[nombre_equipo] = {"jugadores": jugadores_equipo}

    return resultado


def analizar_jugadores_partido(fixture_id, liga_id, temporada, equipo_local=None, equipo_visitante=None):
    """Wrapper para compatibilidad con CLI antiguo."""
    data = obtener_jugadores_partido(fixture_id, liga_id, temporada)
    lista_plana = []
    for equipo_nombre, secciones in data.items():
        for j in secciones["atacantes"]:
            lista_plana.append({**j, "equipo": equipo_nombre, "posicion_tipo": "atacante"})
        for j in secciones["defensivos"]:
            lista_plana.append({**j, "equipo": equipo_nombre, "posicion_tipo": "defensa"})
    return lista_plana
