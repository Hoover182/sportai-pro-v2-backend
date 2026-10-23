"""
Modelo de partido NBA: proyeccion de puntos por equipo + Monte Carlo.

Port de los scripts de consola del usuario (C:\\Users\\hoove\\NBA\\
"import matplotlib.py": estadisticas_equipo_ultimos10,
ultimos_enfrentamientos_directos, ajustar_medias_con_rival,
simular_partido_equipos, proyectar_cuartos), con funciones que devuelven
datos en vez de imprimir, y leyendo nba_partidos.csv en vez de nba_api.

Cambios respecto del original, aprobados el 23/10/2026:
- H2H: el original le asignaba a "A" los puntos del equipo que aparecia
  primero en el ultimo cruce (orden arbitrario de la API), asi que ~la
  mitad de las veces mezclaba los puntos H2H del rival. Ahora cada lado
  toma los suyos.
- Pretemporada afuera: el CSV ya no la trae (ver scripts/sync_nba.py).
- Ventana de ultimos 10 cruzando temporadas: el original fijaba
  season="2025-26"; a principio de temporada habia 1-2 partidos.
- Monte Carlo con semilla fija: el mismo partido da la misma probabilidad
  en cada request.
- Todo se calcula con partidos ANTERIORES a la fecha del partido, asi el
  backtest no ve el futuro.

Variantes para el backtest (apagadas por defecto, el backtest decide):
- ventaja_local: puntos de localia (el original no la tenia: A/B era el
  orden de las filas, no local/visitante).
- factor_fatiga: multiplica la media de un equipo que jugo el dia anterior
  (back-to-back). El script original de jugador usaba 0.85 sin validar.
"""
from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
import pandas as pd

N_ULTIMOS = 10
N_H2H = 10
PESO_H2H = 0.2
STD_MIN = 5.0
PESOS_CUARTOS = [0.24, 0.25, 0.25, 0.26]   # fijos como en el original; calibrar es para despues
SIMS = 10000
SEMILLA = 2026


@dataclass(frozen=True)
class Params:
    ventaja_local: float = 0.0   # puntos de diferencia a favor del local (mitad y mitad)
    factor_fatiga: float = 1.0   # 1.0 = sin ajuste
    sims: int = SIMS
    semilla: int = SEMILLA


def normalizar_std(std, minimo=1.0):
    if pd.isna(std) or std <= 0:
        return minimo
    return max(float(std), minimo)


def partidos_por_equipo(partidos):
    """nba_partidos.csv (una fila por partido) -> una fila por equipo y
    partido, ordenado por fecha. Columnas: game_id, fecha, temporada, tipo,
    team_id, rival_id, local, pts, pts_rival."""
    comunes = ["game_id", "fecha", "temporada", "tipo"]
    loc = partidos[comunes].assign(
        team_id=partidos["id_local"].astype(int), rival_id=partidos["id_visitante"].astype(int),
        local=True, pts=partidos["puntos_local"].astype(float),
        pts_rival=partidos["puntos_visitante"].astype(float))
    vis = partidos[comunes].assign(
        team_id=partidos["id_visitante"].astype(int), rival_id=partidos["id_local"].astype(int),
        local=False, pts=partidos["puntos_visitante"].astype(float),
        pts_rival=partidos["puntos_local"].astype(float))
    largo = pd.concat([loc, vis], ignore_index=True)
    largo["fecha"] = largo["fecha"].astype(str)
    return largo.sort_values(["fecha", "game_id"], kind="stable").reset_index(drop=True)


def ultimos_partidos(largo, team_id, antes_de, n=N_ULTIMOS):
    """Ultimos n partidos del equipo antes de la fecha (ISO), mas nuevo primero."""
    u = largo[(largo["team_id"] == team_id) & (largo["fecha"] < antes_de)]
    return u.iloc[::-1].head(n)


def estadisticas_equipo(largo, team_id, antes_de):
    """Equivalente a estadisticas_equipo_ultimos10. puntos_permitidos sale
    del marcador del rival (el original lo aproximaba con PTS - PLUS_MINUS,
    que da lo mismo)."""
    u = ultimos_partidos(largo, team_id, antes_de)
    if u.empty:
        return None
    return {
        "partidos": u,
        "puntos": u["pts"].mean(),
        "std_puntos": normalizar_std(u["pts"].std(), STD_MIN),
        "puntos_permitidos": u["pts_rival"].mean(),
    }


def enfrentamientos_directos(largo, team_a, team_b, antes_de, temporada, n=N_H2H):
    """Cruces A vs B de la misma temporada antes de la fecha, desde el lado
    de A (pts = A, pts_rival = B). Misma temporada como el original."""
    h = largo[(largo["team_id"] == team_a) & (largo["rival_id"] == team_b)
              & (largo["fecha"] < antes_de) & (largo["temporada"] == temporada)]
    return h.iloc[::-1].head(n)


def ajustar_medias_con_rival(stats_a, stats_b, h2h):
    """Media de cada equipo = promedio entre lo que anota y lo que permite
    el rival, mezclada 80/20 con sus puntos en los cruces directos."""
    media_a = (stats_a["puntos"] + stats_b["puntos_permitidos"]) / 2
    media_b = (stats_b["puntos"] + stats_a["puntos_permitidos"]) / 2
    if not h2h.empty:
        media_a = media_a * (1 - PESO_H2H) + h2h["pts"].mean() * PESO_H2H
        media_b = media_b * (1 - PESO_H2H) + h2h["pts_rival"].mean() * PESO_H2H
    return media_a, media_b


def jugo_ayer(largo, team_id, fecha):
    ayer = (date.fromisoformat(fecha) - timedelta(days=1)).isoformat()
    return bool(((largo["team_id"] == team_id) & (largo["fecha"] == ayer)).any())


def simular_partido(media_a, media_b, std_a, std_b, sims=SIMS, semilla=SEMILLA):
    std_a = normalizar_std(std_a, STD_MIN)
    std_b = normalizar_std(std_b, STD_MIN)
    rng = np.random.default_rng(semilla)
    sim_a = rng.normal(media_a, std_a, sims)
    sim_b = rng.normal(media_b, std_b, sims)
    prob_a = float(np.mean(sim_a > sim_b))
    return prob_a, 1 - prob_a, float(sim_a.mean()), float(sim_b.mean())


def proyectar_cuartos(puntos_a, puntos_b):
    return {"local": [puntos_a * p for p in PESOS_CUARTOS],
            "visitante": [puntos_b * p for p in PESOS_CUARTOS]}


def analizar_partido(largo, local_id, visitante_id, fecha, temporada, params=Params()):
    """Proyeccion de un partido. None si algun equipo no tiene partidos
    previos en el historial."""
    stats_l = estadisticas_equipo(largo, local_id, fecha)
    stats_v = estadisticas_equipo(largo, visitante_id, fecha)
    if stats_l is None or stats_v is None:
        return None

    h2h = enfrentamientos_directos(largo, local_id, visitante_id, fecha, temporada)
    media_l, media_v = ajustar_medias_con_rival(stats_l, stats_v, h2h)

    fatiga_l = jugo_ayer(largo, local_id, fecha)
    fatiga_v = jugo_ayer(largo, visitante_id, fecha)
    if fatiga_l:
        media_l *= params.factor_fatiga
    if fatiga_v:
        media_v *= params.factor_fatiga
    media_l += params.ventaja_local / 2
    media_v -= params.ventaja_local / 2

    prob_l, prob_v, proy_l, proy_v = simular_partido(
        media_l, media_v, stats_l["std_puntos"], stats_v["std_puntos"],
        params.sims, params.semilla)

    return {
        "prob_local": prob_l,
        "prob_visitante": prob_v,
        "proy_local": proy_l,
        "proy_visitante": proy_v,
        "total": proy_l + proy_v,
        "margen_local": proy_l - proy_v,
        "cuartos": proyectar_cuartos(proy_l, proy_v),
        "back_to_back_local": fatiga_l,
        "back_to_back_visitante": fatiga_v,
        "ultimos_local": stats_l["partidos"],
        "ultimos_visitante": stats_v["partidos"],
        "h2h": h2h,
    }
