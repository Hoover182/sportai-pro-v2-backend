"""
Constantes y helpers del sistema de Elo casero de clubes, compartidos
del sistema de Elo casero de clubes. Desde el 29/10/2026 el rating se
calcula aca mismo desde el CSV (calcular_elo), con la formula de
backfill_elo_historico.py de analista-futbol.

El ajuste de Elo SOLO influye en 1X2 (prob_local/prob_empate/
prob_visitante) -- no toca goles proyectados, corners, tarjetas, over/
under ni ningun otro mercado. Ver conversacion de diseno: Elo redistribuye
el balance local/visitante DENTRO de "no empate" (la probabilidad de
empate la sigue dando Dixon-Coles tal cual, sin tocar -- Elo clasico no
tiene concepto de empate, inventar una formula propia para eso hubiera
sido un numero mas sin medir).
"""

VENTAJA_LOCAL_ELO = 100  # puntos de Elo que se le suman al local SOLO para
                          # el calculo de probabilidad esperada, no al rating

ESCALA_ELO = 400  # misma constante de escala que la formula clasica de Elo

# Peso maximo del ajuste de Elo sobre 1X2 cuando ambos equipos tienen Elo
# bien establecido (no provisional). Mas chico que el +/-30% de
# ajuste_liga_clubes() en liga_ranking.py porque ahi se compara una liga
# ENTERA contra otra (brecha tipicamente mas extrema); aca se compara club
# contra club dentro de un contexto ya acotado.
PESO_ELO_MAX = 0.20

# Partidos de historial de Elo a partir de los cuales un equipo deja de
# considerarse "provisional" para efectos de CUANTO PESA en el blend de
# 1X2 -- mismo umbral que N_PARTIDOS_PROVISIONAL en el backfill (que
# regula el K-factor de la actualizacion del rating en si), pero es un
# concepto distinto: aca es "cuanto confiar en este rating ya calculado",
# no "que tan rapido debe moverse el rating".
N_PARTIDOS_ELO_CONFIANZA = 20


# Calculo del Elo (29/10/2026). Antes se leia elo_ratings.json, una foto
# unica generada a mano el 24/08 por backfill_elo_historico.py (analista-
# futbol) que nunca se actualizo: ni el cron lo recalculaba ni el sync lo
# copiaba. Ahora el backend lo calcula solo desde el CSV que ya tiene, con la
# MISMA formula del backfill, cada vez que cambia el CSV.
RATING_BASE = 1500
K_BASE = 20
K_PROVISIONAL = 40
N_PARTIDOS_PROVISIONAL = 20

# Cache por version del CSV (clave que arma futbol_service.cargar_df): se
# recalcula solo cuando llega un CSV nuevo, no en cada request.
_cache_elo = {"clave": None, "ratings": {}}


def rating_inicial(liga):
    """Igual que backfill_elo_historico.py: nivel de la liga en
    NIVEL_LIGA_CLUBES, 1500 si la liga no esta en la tabla."""
    from liga_ranking import NIVEL_LIGA_CLUBES
    nivel = NIVEL_LIGA_CLUBES.get(liga)
    if nivel is None:
        return float(RATING_BASE)
    return float(RATING_BASE + (nivel - 65) * 4)


def multiplicador_goles(diferencia):
    diferencia = abs(diferencia)
    if diferencia <= 1:
        return 1.0
    if diferencia == 2:
        return 1.5
    return (11 + diferencia) / 8


def partidos_para_elo(df_validas):
    """Mismo filtro que cargar_partidos_para_elo() del backfill, sobre el df
    ya filtrado por ligas validas: terminados con goles, sin selecciones,
    en orden cronologico."""
    from football_model import TORNEOS_SELECCIONES
    from fifa_ranking import es_seleccion_nacional
    df = df_validas[df_validas["estado"].isin(["FT", "AET", "PEN"])]
    df = df[df["goles_local"].notna() & df["goles_visitante"].notna()]
    df = df[~df["liga"].isin(TORNEOS_SELECCIONES)]
    selecciones = {
        eq for eq in set(df["equipo_local"].unique()) | set(df["equipo_visitante"].unique())
        if es_seleccion_nacional(eq)
    }
    if selecciones:
        df = df[~df["equipo_local"].isin(selecciones) & ~df["equipo_visitante"].isin(selecciones)]
    return df.sort_values("fecha", kind="stable")


def calcular_elo(df_validas, con_historico=False):
    """(ratings, historico). ratings: equipo -> {"rating" (2 decimales, como
    el viejo elo_ratings.json), "n_partidos"}. historico (si se pide): lista
    (equipo, fecha, rating, n_partidos) despues de cada partido -- lo usa el
    backtest para saber el Elo de un equipo antes de una fecha."""
    ratings = {}
    historico = [] if con_historico else None
    df = partidos_para_elo(df_validas)
    for local, visitante, liga, gl, gv, fecha in zip(
            df["equipo_local"], df["equipo_visitante"], df["liga"],
            df["goles_local"], df["goles_visitante"], df["fecha"]):
        gl, gv = float(gl), float(gv)
        if local not in ratings:
            ratings[local] = {"rating": rating_inicial(liga), "n_partidos": 0}
        if visitante not in ratings:
            ratings[visitante] = {"rating": rating_inicial(liga), "n_partidos": 0}
        r_local = ratings[local]["rating"]
        r_visit = ratings[visitante]["rating"]
        e_local = 1.0 / (1.0 + 10 ** (-((r_local + VENTAJA_LOCAL_ELO) - r_visit) / 400.0))
        e_visit = 1.0 - e_local
        if gl > gv:
            s_local, s_visit = 1.0, 0.0
        elif gl < gv:
            s_local, s_visit = 0.0, 1.0
        else:
            s_local, s_visit = 0.5, 0.5
        g = multiplicador_goles(gl - gv)
        k_local = K_PROVISIONAL if ratings[local]["n_partidos"] < N_PARTIDOS_PROVISIONAL else K_BASE
        k_visit = K_PROVISIONAL if ratings[visitante]["n_partidos"] < N_PARTIDOS_PROVISIONAL else K_BASE
        ratings[local]["rating"] = r_local + k_local * g * (s_local - e_local)
        ratings[local]["n_partidos"] += 1
        ratings[visitante]["rating"] = r_visit + k_visit * g * (s_visit - e_visit)
        ratings[visitante]["n_partidos"] += 1
        if con_historico:
            historico.append((local, fecha, ratings[local]["rating"], ratings[local]["n_partidos"]))
            historico.append((visitante, fecha, ratings[visitante]["rating"], ratings[visitante]["n_partidos"]))
    snapshot = {eq: {"rating": round(d["rating"], 2), "n_partidos": d["n_partidos"]}
                for eq, d in ratings.items()}
    return snapshot, historico


def asegurar_elo(df_validas, clave):
    """Recalcula el Elo si el CSV cambio (clave distinta). Lo llama
    futbol_service.cargar_df() en cada carga."""
    if _cache_elo["clave"] != clave:
        _cache_elo["ratings"], _ = calcular_elo(df_validas)
        _cache_elo["clave"] = clave


def cargar_elo_ratings():
    """Ratings actuales (equipo -> {rating, n_partidos}), calculados desde
    el CSV en la ultima carga. {} si todavia no se cargo ningun CSV: en ese
    caso simplemente no se aplica el ajuste de Elo."""
    return _cache_elo["ratings"]


def peso_elo_confianza(n_partidos_a, n_partidos_b):
    """Peso final del ajuste de Elo sobre 1X2, escalado por cuanta muestra
    real respalda el rating de AMBOS equipos -- el que tiene menos
    historial de los dos manda (mismo criterio de "eslabon mas debil" que
    ya se usa en el resto del pipeline, ej. el k de tarjetas en la mezcla
    Gamma-Poisson usa el minimo de los dos equipos). Devuelve 0.0 si
    cualquiera de los dos no tiene ningun partido de Elo."""
    if n_partidos_a is None or n_partidos_b is None:
        return 0.0
    n_min = min(n_partidos_a, n_partidos_b)
    if n_min <= 0:
        return 0.0
    return PESO_ELO_MAX * min(n_min / N_PARTIDOS_ELO_CONFIANZA, 1.0)
