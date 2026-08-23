import math

import numpy as np
from collections import Counter
from value_bet import normalizar_std


# Minimos y maximos realistas para cualquier liga profesional
GOLES_MIN = 0.7       # ningun equipo profesional promedia menos de 0.7 goles
GOLES_MAX = 3.5       # ningun equipo promedia mas de 3.5 goles
CORNERS_MIN = 3.0     # minimo realista de corners por equipo
CORNERS_MAX = 8.0     # maximo realista de corners por equipo
TARJETAS_MIN = 1.5    # minimo realista de tarjetas totales
TARJETAS_MAX = 6.0    # maximo realista de tarjetas totales

# Correccion Dixon-Coles (1997) sobre la correlacion de goles entre ambos
# equipos en marcadores bajos. Bajo Poisson independiente puro (lo que se
# usaba antes de esto), 0-0 y 1-1 salen levemente subestimados y 1-0/0-1
# levemente sobreestimados frente a lo que se ve en partidos reales. RHO
# es el valor estandar de la literatura, fijo -- no depende de un fit por
# liga ni de ningun dato externo nuevo, es puramente matematico sobre los
# goles esperados que el modelo ya calcula.
RHO_DIXON_COLES = -0.13
MAX_GOLES_GRID = 10  # de sobra para cualquier media realista (0.7 a 3.5)


def _poisson_pmf_vector(lam, max_k=MAX_GOLES_GRID):
    ks = np.arange(0, max_k + 1)
    factoriales = np.array([math.factorial(k) for k in ks], dtype=float)
    return np.exp(-lam) * lam**ks / factoriales


def _neg_binom_pmf_vector(lam, k, max_k=MAX_GOLES_GRID):
    """PMF con incertidumbre parametrica sobre la tasa lam (mezcla
    Gamma-Poisson => Binomial Negativa) en vez de Poisson puro. k es la
    "confianza" en lam -- alto (muchos partidos reales respaldandolo)
    se acerca a Poisson puro; bajo (poca muestra) da una distribucion
    mas ancha, con probabilidades menos extremas. k=None => Poisson
    puro exacto (comportamiento identico al de siempre).

    Sin esto, el modelo trataba el promedio calculado (a veces con solo
    10 partidos, o menos) como si fuera la tasa EXACTA y verdadera del
    equipo. Medido en un backtest de 1459 partidos reales: el modelo
    daba probabilidades ~8-11 puntos mas extremas de lo que el acierto
    real sostenia en los mercados de mayor confianza (85%+). Ver
    football_model.n_efectivo_estimacion() para como se arma k."""
    if k is None:
        return _poisson_pmf_vector(lam, max_k)
    k = max(float(k), 0.5)
    ks = np.arange(0, max_k + 1)
    log_coef = np.array([math.lgamma(n + k) - math.lgamma(k) - math.lgamma(n + 1) for n in ks])
    p = k / (k + lam)
    log_pmf = log_coef + k * math.log(p) + ks * math.log(1 - p)
    return np.exp(log_pmf)


def _muestrear_conteo(media, k, sims):
    """Muestrea sims conteos de una variable con incertidumbre
    parametrica sobre su tasa (Gamma-Poisson) si se pasa k, o Poisson
    puro si k es None (comportamiento identico al de siempre). Version
    Monte Carlo de _neg_binom_pmf_vector, para corners/tarjetas (que ya
    se simulaban asi antes de este cambio, a diferencia de goles que
    usa la grilla Dixon-Coles cerrada)."""
    if k is None:
        return np.random.poisson(media, sims)
    k = max(float(k), 0.5)
    lam = np.random.gamma(k, media / k, sims)
    return np.random.poisson(lam)


def _tau_dixon_coles(x, y, lam, mu, rho):
    if x == 0 and y == 0:
        return 1 - (lam * mu * rho)
    if x == 0 and y == 1:
        return 1 + (lam * rho)
    if x == 1 and y == 0:
        return 1 + (mu * rho)
    if x == 1 and y == 1:
        return 1 - rho
    return 1.0


def _grid_dixon_coles(media_a, media_b, k_a=None, k_b=None, rho=RHO_DIXON_COLES, max_goles=MAX_GOLES_GRID):
    """Matriz de probabilidad conjunta P(goles_local=x, goles_visitante=y),
    con la correccion tau de Dixon-Coles sobre los 4 marcadores bajos.
    Normalizada para sumar 1 despues de aplicar tau (tau mueve masa de
    probabilidad, no la agrega/quita).

    k_a/k_b: confianza en media_a/media_b para la mezcla Gamma-Poisson
    (ver _neg_binom_pmf_vector) -- None (default) da el Poisson puro de
    siempre. La correccion tau se sigue aplicando sobre media_a/media_b
    tal cual (esta pensada para la correlacion ENTRE ambos equipos en
    marcadores bajos, no para el ancho de cada marginal)."""
    prob_a = _neg_binom_pmf_vector(media_a, k_a, max_goles)
    prob_b = _neg_binom_pmf_vector(media_b, k_b, max_goles)
    grid = np.outer(prob_a, prob_b)
    for x in range(2):
        for y in range(2):
            grid[x, y] *= _tau_dixon_coles(x, y, media_a, media_b, rho)
    return grid / grid.sum()


# Promedio real de tarjetas_total medido en el CSV (15,780 partidos FT)
# segun la diferencia de goles final del partido -- partidos parejos
# tienen mas tarjetas, goleadas tienen menos (r=-0.15 Pearson, r=-0.14
# Spearman, ambos altamente significativos; efecto real pero moderado,
# r^2~2.4%). Verificado que NO existe la misma relacion para corners
# (r=-0.008, no significativo) -- por eso el ajuste de parejez solo
# aplica a tarjetas. Ver conversacion de diseno.
TARJETAS_POR_DIFERENCIA_GOLES = {0: 4.63, 1: 4.80, 2: 4.26, 3: 3.78, 4: 3.38, 5: 3.19}
PESO_PAREJEZ_TARJETAS = 0.15  # ajuste suave: el promedio real del equipo sigue dominando


def _tarjetas_esperadas_por_parejez(grid_goles):
    """Tarjetas totales esperadas segun la diferencia de goles ESPERADA
    de la simulacion (no la mas probable), interpolando la tabla
    empirica TARJETAS_POR_DIFERENCIA_GOLES sobre la grilla Dixon-Coles."""
    n = grid_goles.shape[0]
    xs, ys = np.meshgrid(np.arange(n), np.arange(n), indexing="ij")
    diferencia_esperada = float(np.sum(np.abs(xs - ys) * grid_goles))

    puntos_x = sorted(TARJETAS_POR_DIFERENCIA_GOLES.keys())
    puntos_y = [TARJETAS_POR_DIFERENCIA_GOLES[k] for k in puntos_x]
    return float(np.interp(diferencia_esperada, puntos_x, puntos_y))


def simular_partido_futbol(
    media_goles_a,
    media_goles_b,
    std_goles_a,
    std_goles_b,
    media_corners_a,
    media_corners_b,
    media_tarjetas_total,
    sims=10000,
    k_goles_a=None,
    k_goles_b=None,
    k_corners_a=None,
    k_corners_b=None,
    k_tarjetas=None,
):
    # Aplicar limites realistas a los inputs
    media_goles_a = float(np.clip(media_goles_a, GOLES_MIN, GOLES_MAX))
    media_goles_b = float(np.clip(media_goles_b, GOLES_MIN, GOLES_MAX))
    media_corners_a = float(np.clip(media_corners_a, CORNERS_MIN, CORNERS_MAX))
    media_corners_b = float(np.clip(media_corners_b, CORNERS_MIN, CORNERS_MAX))
    media_tarjetas_total = float(np.clip(media_tarjetas_total, TARJETAS_MIN, TARJETAS_MAX))

    # Goles: matriz de probabilidad conjunta cerrada (no Monte Carlo) con
    # la correccion Dixon-Coles sobre marcadores bajos -- ver
    # _grid_dixon_coles() arriba. Exacta, sin ruido de muestreo. Corners,
    # tarjetas y el desglose por mitades siguen con Poisson independiente
    # + Monte Carlo: Dixon-Coles es especificamente sobre la correlacion
    # de goles entre ambos equipos, no aplica a esas metricas.
    #
    # k_goles_a/b, k_corners_a/b, k_tarjetas: confianza en el promedio
    # respectivo para la mezcla Gamma-Poisson (ver _neg_binom_pmf_vector/
    # _muestrear_conteo) -- None (default) reproduce el Poisson puro de
    # siempre. Se aplican SOLO a goles_ou/corners_ou/tarjetas_ou (lo que
    # alimenta el Top3), no al desglose por mitades ni al 1X2/handicap/
    # ambos marcan, que no fueron parte del backtest de calibracion.
    grid_goles = _grid_dixon_coles(media_goles_a, media_goles_b, k_goles_a, k_goles_b)
    n_grid = grid_goles.shape[0]
    xs_grid, ys_grid = np.meshgrid(np.arange(n_grid), np.arange(n_grid), indexing="ij")
    dif_grid = xs_grid - ys_grid
    total_grid = xs_grid + ys_grid

    # Muestreo Monte Carlo de goles SOLO para el desglose por mitades mas
    # abajo (Dixon-Coles no cubre esa division) -- Poisson independiente,
    # igual que antes de este cambio.
    std_goles_a = normalizar_std(std_goles_a, 0.35)
    std_goles_b = normalizar_std(std_goles_b, 0.35)
    goles_a = np.random.poisson(media_goles_a, sims).astype(float)
    goles_b = np.random.poisson(media_goles_b, sims).astype(float)

    # Corners: sin ajuste de parejez (no hay correlacion real medida
    # entre corners y goles, ver conversacion de diseno).
    corners_a = _muestrear_conteo(media_corners_a, k_corners_a, sims)
    corners_b = _muestrear_conteo(media_corners_b, k_corners_b, sims)

    # Tarjetas: ajuste suave segun que tan pareja resulta la simulacion
    # de goles (grilla Dixon-Coles) -- partidos parejos tienden a tener
    # mas tarjetas que goleadas, medido en el CSV real. Peso bajo a
    # proposito: el promedio real de tarjetas del equipo (media_tarjetas_
    # total, ya calculado antes de llegar aca) sigue siendo el que manda.
    tarjetas_por_parejez = _tarjetas_esperadas_por_parejez(grid_goles)
    media_tarjetas_total = (
        media_tarjetas_total * (1 - PESO_PAREJEZ_TARJETAS)
        + tarjetas_por_parejez * PESO_PAREJEZ_TARJETAS
    )
    media_tarjetas_total = float(np.clip(media_tarjetas_total, TARJETAS_MIN, TARJETAS_MAX))
    tarjetas = _muestrear_conteo(media_tarjetas_total, k_tarjetas, sims)

    total_corners = corners_a + corners_b

    # RESULTADO 1X2 (desde la grilla Dixon-Coles)
    prob_local     = float(grid_goles[xs_grid > ys_grid].sum())
    prob_empate    = float(grid_goles[xs_grid == ys_grid].sum())
    prob_visitante = float(grid_goles[xs_grid < ys_grid].sum())

    # DOBLE OPORTUNIDAD
    prob_1x = prob_local + prob_empate
    prob_x2 = prob_empate + prob_visitante
    prob_12 = prob_local + prob_visitante

    # HANDICAP 3-WAY
    prob_hcp_local_m1    = float(grid_goles[dif_grid > 1].sum())
    prob_hcp_empate_m1   = float(grid_goles[dif_grid == 1].sum())
    prob_hcp_visit_m1    = float(grid_goles[dif_grid < 1].sum())
    prob_hcp_local_p1    = float(grid_goles[dif_grid > -1].sum())
    prob_hcp_empate_p1   = float(grid_goles[dif_grid == -1].sum())
    prob_hcp_visit_p1    = float(grid_goles[dif_grid < -1].sum())

    # AMBOS MARCAN
    prob_ambos = float(grid_goles[(xs_grid >= 1) & (ys_grid >= 1)].sum())

    # OVER/UNDER GOLES 0.5 a 7.5
    goles_ou = {}
    for linea in [0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5, 7.5]:
        goles_ou[linea] = {
            "over":  float(grid_goles[total_grid > linea].sum()),
            "under": float(grid_goles[total_grid < linea].sum())
        }

    # OVER/UNDER CORNERS 3.5 a 19.5
    corners_ou = {}
    for linea in [3.5, 4.5, 5.5, 6.5, 7.5, 8.5, 9.5, 10.5, 11.5, 12.5, 13.5, 14.5, 15.5, 16.5, 17.5, 18.5, 19.5]:
        corners_ou[linea] = {
            "over":  float(np.mean(total_corners > linea)),
            "under": float(np.mean(total_corners < linea))
        }

    # OVER/UNDER TARJETAS 0.5 a 11.5
    tarjetas_ou = {}
    for linea in [0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5, 7.5, 8.5, 9.5, 10.5, 11.5]:
        tarjetas_ou[linea] = {
            "over":  float(np.mean(tarjetas > linea)),
            "under": float(np.mean(tarjetas < linea))
        }

    # MARCADOR EXACTO top 6 (probabilidad exacta de la grilla, no conteo
    # de muestras)
    marcadores_flat = [((x, y), grid_goles[x, y]) for x in range(n_grid) for y in range(n_grid)]
    top_marcadores = sorted(marcadores_flat, key=lambda item: item[1], reverse=True)[:6]
    marcadores_prob = [(f"{x}-{y}", round(p * 100, 1)) for (x, y), p in top_marcadores]

    # RESULTADO POR MITADES
    # Los goles del primer tiempo siguen una distribucion independiente
    # En promedio el 45% de los goles ocurren en el primer tiempo
    ratio_1t = 0.45
    media_a_1t = max(media_goles_a * ratio_1t, 0.1)
    media_b_1t = max(media_goles_b * ratio_1t, 0.1)

    goles_a_1t = np.random.poisson(media_a_1t, sims).astype(float)
    goles_b_1t = np.random.poisson(media_b_1t, sims).astype(float)
    goles_a_2t = np.clip(goles_a - goles_a_1t, 0, None)
    goles_b_2t = np.clip(goles_b - goles_b_1t, 0, None)

    prob_1t_local     = float(np.mean(goles_a_1t > goles_b_1t))
    prob_1t_empate    = float(np.mean(goles_a_1t == goles_b_1t))
    prob_1t_visitante = float(np.mean(goles_b_1t > goles_a_1t))
    prob_2t_local     = float(np.mean(goles_a_2t > goles_b_2t))
    prob_2t_empate    = float(np.mean(goles_a_2t == goles_b_2t))
    prob_2t_visitante = float(np.mean(goles_b_2t > goles_a_2t))

    return {
        # RESULTADO
        "prob_local": prob_local,
        "prob_empate": prob_empate,
        "prob_visitante": prob_visitante,
        # DOBLE OPORTUNIDAD
        "prob_1x": prob_1x,
        "prob_x2": prob_x2,
        "prob_12": prob_12,
        # HANDICAP
        "prob_hcp_local_m1": prob_hcp_local_m1,
        "prob_hcp_empate_m1": prob_hcp_empate_m1,
        "prob_hcp_visit_m1": prob_hcp_visit_m1,
        "prob_hcp_local_p1": prob_hcp_local_p1,
        "prob_hcp_empate_p1": prob_hcp_empate_p1,
        "prob_hcp_visit_p1": prob_hcp_visit_p1,
        # AMBOS MARCAN
        "prob_ambos_marcan": prob_ambos,
        # OVER/UNDER
        "goles_ou": goles_ou,
        "corners_ou": corners_ou,
        "tarjetas_ou": tarjetas_ou,
        # MARCADOR EXACTO
        "marcadores_prob": marcadores_prob,
        # MITADES
        "prob_1t_local": prob_1t_local,
        "prob_1t_empate": prob_1t_empate,
        "prob_1t_visitante": prob_1t_visitante,
        "prob_2t_local": prob_2t_local,
        "prob_2t_empate": prob_2t_empate,
        "prob_2t_visitante": prob_2t_visitante,
        # PROYECCIONES (esperanza de la grilla Dixon-Coles, no de las
        # muestras de mitades)
        "goles_local_proj": float(np.sum(np.arange(n_grid) * grid_goles.sum(axis=1))),
        "goles_visitante_proj": float(np.sum(np.arange(n_grid) * grid_goles.sum(axis=0))),
        "corners_totales_proj": float(total_corners.mean()),
        "tarjetas_totales_proj": float(tarjetas.mean())
    }


def proyectar_tiempos(goles_a, goles_b):
    return {
        "A": [goles_a * 0.45, goles_a * 0.55],
        "B": [goles_b * 0.45, goles_b * 0.55]
    }


def _over_under_poisson(lam, linea, max_k=40, k=None):
    """P(over) y P(under) de una linea arbitraria para una variable
    Poisson(lam) -- calculo cerrado, sin Monte Carlo. Valido para
    corners totales (suma de dos Poisson independientes = Poisson de la
    suma de sus medias) y para tarjetas totales (ya es un unico
    Poisson). max_k=40 alcanza de sobra para cualquier lambda realista
    de corners/tarjetas de un partido (linea tipica hasta ~20).

    k: confianza en lam para la mezcla Gamma-Poisson (ver
    _neg_binom_pmf_vector) -- None (default) da el Poisson puro de
    siempre."""
    pmf = _neg_binom_pmf_vector(lam, k, max_k=max_k)
    piso = int(np.floor(linea))
    prob_under = float(pmf[:piso + 1].sum()) if linea != piso else float(pmf[:piso].sum())
    prob_over = float(1.0 - pmf[:piso + 1].sum())
    return prob_over, prob_under


def probabilidad_linea_personalizada(mercado, linea, lado,
                                      media_goles_a, media_goles_b,
                                      media_corners_total,
                                      media_tarjetas_total,
                                      k_goles_a=None, k_goles_b=None,
                                      k_corners=None, k_tarjetas=None):
    """Probabilidad de una linea arbitraria (no solo las fijas que ya
    mostramos) para value betting manual -- el usuario mete la linea y
    la cuota de su casa de apuestas, esto le da nuestra probabilidad
    para comparar. mercado: 'goles' | 'corners' | 'tarjetas'.
    lado: 'over' | 'under'. Reutiliza la grilla Dixon-Coles (goles) o
    el cierre Poisson/Binomial Negativa (corners/tarjetas) -- mismo
    calculo exacto que ya usa simular_partido_futbol(), sin Monte Carlo
    nuevo.

    media_corners_total y media_tarjetas_total van ya combinados (no
    por separado local/visitante) para poder pasar directo los valores
    finales que ya calcula simular() en futbol_service.py -- esos ya
    incluyen H2H, ajuste de liga y los multiplicadores de presion/
    agresividad/clasico/intensidad ofensiva, mismos numeros que
    alimentan corners_ou/tarjetas_ou en el resto de la app.

    k_goles_a/b, k_corners, k_tarjetas: confianza en el promedio
    respectivo (ver _neg_binom_pmf_vector) -- None (default) da el
    Poisson puro de siempre, para no romper llamadas existentes que
    todavia no la pasan."""
    if mercado == "goles":
        media_goles_a = float(np.clip(media_goles_a, GOLES_MIN, GOLES_MAX))
        media_goles_b = float(np.clip(media_goles_b, GOLES_MIN, GOLES_MAX))
        grid = _grid_dixon_coles(media_goles_a, media_goles_b, k_goles_a, k_goles_b)
        n = grid.shape[0]
        xs, ys = np.meshgrid(np.arange(n), np.arange(n), indexing="ij")
        total = xs + ys
        prob_over = float(grid[total > linea].sum())
        prob_under = float(grid[total < linea].sum())
    elif mercado == "corners":
        lam = max(float(media_corners_total), 0.1)
        prob_over, prob_under = _over_under_poisson(lam, linea, k=k_corners)
    elif mercado == "tarjetas":
        lam = max(float(media_tarjetas_total), 0.1)
        prob_over, prob_under = _over_under_poisson(lam, linea, k=k_tarjetas)
    else:
        raise ValueError(f"Mercado no soportado: {mercado!r} (usar 'goles', 'corners' o 'tarjetas')")

    return prob_over if lado == "over" else prob_under


def tarjetas_esperadas_por_parejez(media_goles_a, media_goles_b):
    """Wrapper publico de _tarjetas_esperadas_por_parejez() para uso
    fuera de este modulo (ej. el texto de reglas fijas del value bet
    manual, que necesita explicar si el ajuste de parejez subio o bajo
    el promedio de tarjetas) -- arma la grilla Dixon-Coles internamente."""
    media_goles_a = float(np.clip(media_goles_a, GOLES_MIN, GOLES_MAX))
    media_goles_b = float(np.clip(media_goles_b, GOLES_MIN, GOLES_MAX))
    grid = _grid_dixon_coles(media_goles_a, media_goles_b)
    return _tarjetas_esperadas_por_parejez(grid)
