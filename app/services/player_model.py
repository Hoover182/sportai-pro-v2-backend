import requests
import numpy as np
import pandas as pd
from datetime import datetime

API_KEY = "7be9c4250da301a68726beedbe2b382a"
BASE_URL = "https://v3.football.api-sports.io"

MINUTOS_MIN_TEMPORADA = 200  # minimos minutos en temporada para considerar jugador

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
    except requests.exceptions.Timeout:
        print(f"  Timeout en {endpoint}")
        return {}
    except requests.exceptions.ConnectionError:
        print(f"  Error de conexion en {endpoint}")
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
        from datetime import timedelta
        if isinstance(fecha, str):
            fecha_dt = datetime.strptime(fecha[:10], "%Y-%m-%d")
        else:
            fecha_dt = datetime.now()
    except Exception:
        from datetime import timedelta
        fecha_dt = datetime.now()

    from datetime import timedelta
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


def obtener_squad_equipo(team_id, liga_id, temporada):
    """Obtiene el squad completo de un equipo en la temporada."""
    data = api_get("players", params={
        "team": team_id,
        "league": liga_id,
        "season": temporada
    })
    return data.get("response", [])


def obtener_team_id(liga_id, temporada, nombre_equipo):
    """Busca el team_id de un equipo por nombre."""
    data = api_get("teams", params={
        "league": liga_id,
        "season": temporada
    })
    nombre_lower = nombre_equipo.lower()
    for t in data.get("response", []):
        nombre_api = t.get("team", {}).get("name", "").lower()
        if nombre_lower[:8] in nombre_api or nombre_api[:8] in nombre_lower:
            return t["team"]["id"]
    return None


def simular_jugador(media, lineas):
    """Simula probabilidades con distribucion de Poisson."""
    media = max(float(media), 0.05)
    valores = np.random.poisson(media, 10000).astype(float)
    resultado = {}
    for linea in lineas:
        resultado[linea] = {
            "over":  float(np.mean(valores > linea)),
            "under": float(np.mean(valores < linea))
        }
    return resultado


def analizar_jugadores_partido(fixture_id, liga_id, temporada, equipo_local=None, equipo_visitante=None):
    """
    Analiza jugadores de un partido usando stats de TODA LA TEMPORADA.
    Obtiene el roster de ambos equipos y sus stats acumuladas en la temporada.
    """
    resultados = []

    # Obtener equipos del fixture
    data_fixture = api_get("fixtures", params={"id": fixture_id})
    equipos_info = []

    for f in data_fixture.get("response", []):
        home_id   = f.get("teams", {}).get("home", {}).get("id")
        home_name = f.get("teams", {}).get("home", {}).get("name", "")
        away_id   = f.get("teams", {}).get("away", {}).get("id")
        away_name = f.get("teams", {}).get("away", {}).get("name", "")
        if home_id:
            equipos_info.append({"id": home_id, "nombre": home_name})
        if away_id:
            equipos_info.append({"id": away_id, "nombre": away_name})

    if not equipos_info:
        print("  No se encontro informacion del fixture")
        return []

    for equipo in equipos_info:
        team_id      = equipo["id"]
        nombre_equipo = equipo["nombre"]

        print(f"  Obteniendo stats temporada de {nombre_equipo}...")

        # Obtener todos los jugadores del equipo en la temporada
        squad = obtener_squad_equipo(team_id, liga_id, temporada)

        for p in squad:
            info  = p.get("player", {})
            stats_list = p.get("statistics", [])
            if not stats_list:
                continue

            stats    = stats_list[0]
            games    = stats.get("games", {})
            pos      = games.get("position", "") or ""
            tipo_pos = clasificar_posicion(pos)

            # Excluir porteros
            if tipo_pos in ["portero", "otro"]:
                continue

            # Filtrar por minutos minimos jugados en temporada
            minutos = games.get("minutes") or 0
            if minutos < MINUTOS_MIN_TEMPORADA:
                continue

            partidos = max(games.get("appearences") or 1, 1)

            # Stats POR PARTIDO en la temporada
            goles_pg       = (stats.get("goals", {}).get("total")     or 0) / partidos
            asist_pg       = (stats.get("goals", {}).get("assists")   or 0) / partidos
            tiros_total_pg = (stats.get("shots", {}).get("total")     or 0) / partidos
            tiros_arco_pg  = (stats.get("shots", {}).get("on")        or 0) / partidos
            tarjetas_pg    = (stats.get("cards", {}).get("yellow")    or 0) / partidos
            faltas_pg      = (stats.get("fouls", {}).get("committed") or 0) / partidos
            fuera_juego_pg = (stats.get("offsides")                   or 0) / partidos

            # Minimos realistas
            tiros_arco_media  = max(tiros_arco_pg,  0.1)
            tiros_total_media = max(tiros_total_pg, 0.2)
            asist_media       = max(asist_pg,       0.05)
            tarjetas_media    = max(tarjetas_pg,    0.05)
            faltas_media      = max(faltas_pg,      0.3)
            fuera_juego_media = max(fuera_juego_pg, 0.05)

            resultados.append({
                "nombre":        info.get("name", "Desconocido"),
                "equipo":        nombre_equipo,
                "posicion":      pos,
                "posicion_tipo": tipo_pos,
                "minutos":       minutos,
                "partidos":      partidos,
                "goles_pg":      round(goles_pg, 2),
                "asist_pg":      round(asist_pg, 2),
                # Simulaciones con stats de temporada
                "tiros_arco":  simular_jugador(tiros_arco_media,  [0.5, 1.5, 2.5, 3.5]),
                "tiros_total": simular_jugador(tiros_total_media, [0.5, 1.5, 2.5, 3.5]),
                "asistencias": simular_jugador(asist_media,       [0.5, 1.5, 2.5]),
                "fuera_juego": simular_jugador(fuera_juego_media, [0.5, 1.5]),
                "tarjetas":    simular_jugador(tarjetas_media,    [0.5, 1.5]),
                "faltas":      simular_jugador(faltas_media,      [0.5, 1.5, 2.5, 3.5]),
            })

    return resultados


def imprimir_picks_jugadores(jugadores):
    if not jugadores:
        print("  No hay datos de jugadores disponibles.")
        return

    goleadores     = [j for j in jugadores if j["posicion_tipo"] in ["delantero", "medio"]]
    disciplinarios = [j for j in jugadores if j["posicion_tipo"] == "defensa"]

    if goleadores:
        print("\n┌─────────────────────────────────────────────────────────┐")
        print("│            ⚽ ESTADISTICAS GOLEADORAS (TEMPORADA)       │")
        print("└─────────────────────────────────────────────────────────┘")

        for j in goleadores:
            pos = f" [{j['posicion']}]" if j.get("posicion") else ""
            print(f"\n  👤 {j['nombre']}{pos} — {j['equipo']}")
            print(f"  📊 Temporada: {j['partidos']} partidos · {j['goles_pg']:.2f} goles/p · {j['asist_pg']:.2f} asist/p")
            print(f"  {'─'*55}")

            print(f"  🎯 TIROS AL ARCO")
            print(f"  {'LINEA':<8} {'OVER':>10} {'UNDER':>10}")
            for linea, vals in j["tiros_arco"].items():
                print(f"  {linea:<8} {vals['over']*100:>9.1f}% {vals['under']*100:>9.1f}%")

            print(f"\n  💥 DISPAROS TOTALES")
            print(f"  {'LINEA':<8} {'OVER':>10} {'UNDER':>10}")
            for linea, vals in j["tiros_total"].items():
                print(f"  {linea:<8} {vals['over']*100:>9.1f}% {vals['under']*100:>9.1f}%")

            print(f"\n  🅰️  ASISTENCIAS")
            print(f"  {'LINEA':<8} {'OVER':>10} {'UNDER':>10}")
            for linea, vals in j["asistencias"].items():
                print(f"  {linea:<8} {vals['over']*100:>9.1f}% {vals['under']*100:>9.1f}%")

            print(f"\n  🚫 FUERA DE JUEGO")
            print(f"  {'LINEA':<8} {'OVER':>10} {'UNDER':>10}")
            for linea, vals in j["fuera_juego"].items():
                print(f"  {linea:<8} {vals['over']*100:>9.1f}% {vals['under']*100:>9.1f}%")

    if disciplinarios:
        print("\n┌─────────────────────────────────────────────────────────┐")
        print("│            🟨 ESTADISTICAS DISCIPLINARIAS (TEMPORADA)  │")
        print("└─────────────────────────────────────────────────────────┘")

        for j in disciplinarios:
            pos = f" [{j['posicion']}]" if j.get("posicion") else ""
            print(f"\n  👤 {j['nombre']}{pos} — {j['equipo']}")
            print(f"  📊 Temporada: {j['partidos']} partidos")
            print(f"  {'─'*55}")

            print(f"  🟨 TARJETAS AMARILLAS")
            print(f"  {'LINEA':<8} {'OVER':>10} {'UNDER':>10}")
            for linea, vals in j["tarjetas"].items():
                print(f"  {linea:<8} {vals['over']*100:>9.1f}% {vals['under']*100:>9.1f}%")

            print(f"\n  🦵 FALTAS COMETIDAS")
            print(f"  {'LINEA':<8} {'OVER':>10} {'UNDER':>10}")
            for linea, vals in j["faltas"].items():
                print(f"  {linea:<8} {vals['over']*100:>9.1f}% {vals['under']*100:>9.1f}%")
