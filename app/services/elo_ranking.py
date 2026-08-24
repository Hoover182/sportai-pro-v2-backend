"""
Constantes y helpers del sistema de Elo casero de clubes, compartidos
entre el backfill historico (backfill_elo_historico.py) y la aplicacion
en vivo (simulator.py/futbol_service.py) -- tienen que usar los MISMOS
valores, si no el rating calculado no significa lo mismo que el rating
aplicado al simular un partido de hoy.

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


ELO_RATINGS_PATH = "elo_ratings.json"

# Cache en memoria, sin TTL -- mismo criterio que _cache_ranking_fifa en
# fifa_ranking.py: los ratings de Elo solo cambian una vez al dia (la
# actualizacion incremental del cron), no dentro de la vida de un mismo
# proceso. Sin esto, un endpoint que recorre todos los partidos del dia
# (ej. partidos-hoy, ~70+ partidos) releeria el mismo JSON del disco una
# vez por partido.
_cache_elo_ratings = None


def cargar_elo_ratings():
    """Lee el snapshot actual de ratings (equipo -> {rating, n_partidos})
    generado por backfill_elo_historico.py / la actualizacion incremental
    diaria. Devuelve {} si el archivo todavia no existe -- asi cualquier
    caller que no lo encuentre simplemente no aplica el ajuste de Elo
    (comportamiento identico al de antes de este sistema), en vez de
    romper."""
    global _cache_elo_ratings
    if _cache_elo_ratings is not None:
        return _cache_elo_ratings
    import json
    import os
    if not os.path.exists(ELO_RATINGS_PATH):
        _cache_elo_ratings = {}
        return _cache_elo_ratings
    try:
        with open(ELO_RATINGS_PATH, "r", encoding="utf-8") as f:
            _cache_elo_ratings = json.load(f)
    except Exception:
        _cache_elo_ratings = {}
    return _cache_elo_ratings


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
