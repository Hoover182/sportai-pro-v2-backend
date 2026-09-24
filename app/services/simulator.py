import math

import numpy as np
from collections import Counter
from value_bet import normalizar_std
from elo_ranking import VENTAJA_LOCAL_ELO, ESCALA_ELO


# Minimos y maximos realistas para cualquier liga profesional
GOLES_MIN = 0.7       # ningun equipo profesional promedia menos de 0.7 goles
GOLES_MAX = 3.5       # ningun equipo promedia mas de 3.5 goles
CORNERS_MIN = 3.0     # minimo realista de corners por equipo
CORNERS_MAX = 8.0     # maximo realista de corners por equipo
TARJETAS_MIN = 1.5    # minimo realista de tarjetas totales
TARJETAS_MAX = 6.0    # maximo realista de tarjetas totales
TIROS_ARCO_MIN = 1.5    # minimo realista de tiros al arco por equipo
TIROS_ARCO_MAX = 9.0    # maximo realista de tiros al arco por equipo
TIROS_TOTAL_MIN = 5.0   # minimo realista de tiros totales por equipo
TIROS_TOTAL_MAX = 22.0  # maximo realista de tiros totales por equipo
ATAJADAS_MIN = 1.0      # minimo realista de atajadas por equipo
ATAJADAS_MAX = 11.0     # maximo realista de atajadas por equipo

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


def _media_valida(media):
    """True si media es un numero finito. None (el caller no la paso) y
    NaN/inf (equipo sin datos de esa metrica que se filtro hasta aca)
    cuentan igual: sin esa metrica, no se simula ni se expone su O/U.
    np.clip(nan) devuelve nan, asi que sin este chequeo el NaN llegaba a
    np.random.poisson y explotaba con "lam value too large"."""
    return media is not None and bool(np.isfinite(media))


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


def _ou_desde_pmf(pmf, lineas):
    """Over/under de una pmf discreta indexada 0..N-1 (ej. marginal de
    grid_goles, P(goles_a=k)) para cada linea -- cerrado, sin Monte
    Carlo, mismo criterio exacto que ya usa goles_ou sobre grid_goles."""
    ks = np.arange(len(pmf))
    return {
        linea: {
            "over": float(pmf[ks > linea].sum()),
            "under": float(pmf[ks < linea].sum()),
        }
        for linea in lineas
    }


def _ou_desde_muestra(muestra, lineas):
    """Over/under de una muestra Monte Carlo (ej. corners_a) para cada
    linea -- generaliza el patron que ya usan corners_ou/tarjetas_ou/
    tiros_arco_ou/tiros_total_ou/atajadas_ou mas abajo (todos con el
    mismo calculo escrito a mano); no reemplaza esos bloques, solo se
    usa para las tablas por equipo nuevas (Bloque 3, ver conversacion
    de diseno), para no tocar codigo ya validado sin necesidad."""
    return {
        linea: {
            "over": float(np.mean(muestra > linea)),
            "under": float(np.mean(muestra < linea)),
        }
        for linea in lineas
    }


# Lineas O/U POR EQUIPO (local/visitante por separado) -- calibradas con
# percentiles reales del CSV (15,780+ partidos FT/AET/PEN), separando la
# columna _local de la _visitante en vez de usar el total combinado:
# ventaja de local real y medible en todo salvo atajadas (ahi se invierte,
# el arquero visitante ataja mas porque el local ataca mas). Piso = p1 +
# 0.5, techo = p99 + 1.5 sobre el RANGO MAS AMPLIO entre local y
# visitante -- mismo set de lineas para ambos lados a proposito (ver
# conversacion de diseno, Bloque 2): evita tener que exponer tablas de
# distinto tamano/rango por lado para el mismo partido, al costo de
# alguna linea con probabilidad extrema del lado mas debil, mismo
# comportamiento que ya conviven en las tablas del total de mas abajo.
LINEAS_GOLES_EQUIPO = [0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5]
LINEAS_CORNERS_EQUIPO = [0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5, 7.5, 8.5, 9.5,
                         10.5, 11.5, 12.5, 13.5, 14.5, 15.5]
LINEAS_TIROS_ARCO_EQUIPO = [0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5, 7.5, 8.5, 9.5,
                            10.5, 11.5, 12.5, 13.5]
LINEAS_TIROS_TOTAL_EQUIPO = [2.5, 3.5, 4.5, 5.5, 6.5, 7.5, 8.5, 9.5, 10.5, 11.5,
                             12.5, 13.5, 14.5, 15.5, 16.5, 17.5, 18.5, 19.5, 20.5,
                             21.5, 22.5, 23.5, 24.5, 25.5, 26.5, 27.5, 28.5, 29.5, 30.5]
LINEAS_ATAJADAS_EQUIPO = [0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5, 7.5, 8.5, 9.5, 10.5]
# Tarjetas por equipo (Bloque 5, no en el Bloque 2 original -- tarjetas
# quedo afuera de esa calibracion a proposito, pendiente de que el reparto
# por equipo pasara su propio backtest). Mismo criterio piso=p1+0.5/
# techo=p99+1.5 sobre el CSV real: local y visitante dan p1=0, p99=6 por
# separado (mismo rango en ambos lados a esta granularidad).
LINEAS_TARJETAS_EQUIPO = [0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5, 7.5]


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


def _reescalar_grid_por_elo(grid_goles, dif_grid, prob_local_pre, prob_visitante_pre, prob_local_post, prob_visitante_post):
    """Generaliza el ajuste de Elo -- que sobre 1X2 solo redistribuye masa
    entre los 3 agregados -- a la grilla Dixon-Coles completa, para que el
    HANDICAP quede en la misma base que el 1X2 que ya ve el usuario:
    reescala proporcionalmente el bloque "gana local" (dif_grid > 0) por
    el mismo factor en que Elo movio prob_local, y el bloque "gana
    visitante" (dif_grid < 0) por el factor de prob_visitante, dejando el
    empate (dif_grid == 0) intacto -- mismo principio que el ajuste
    actual (Elo clasico no tiene concepto de empate).

    Usada SOLO para handicap -- europeo (+/-1, ver grid_handicap en
    simular_partido_futbol) y asiatico (ver probabilidad_handicap_
    asiatico() mas abajo, mismas 13 lineas leyendo de esta misma grilla
    reescalada, sin recalcular nada nuevo) -- backtest de 1456 partidos
    (mismo criterio de muestra/random_state que el backtest de Elo sobre
    1X2) confirmo mejora real y consistente en Brier score y log loss
    de handicap con este reescalado (validado de nuevo especificamente
    para las 13 lineas del asiatico, misma metodologia, misma mejora
    consistente sin excepcion). Medido tambien sobre goles_ou (las 8
    lineas) y ambos_marcan, sin encontrar mejora practica en ninguno de
    los dos (goles_ou: diferencia de Brier <=0.00004 en todas las
    lineas; ambos_marcan: Brier/log loss iguales, accuracy del pick top
    empeoro 0.07 puntos) -- por eso esos mercados y marcador exacto/
    proyecciones siguen leyendo de grid_goles sin reescalar, sin pasar
    por esta funcion. Ver conversacion de diseno."""
    scale_local = (prob_local_post / prob_local_pre) if prob_local_pre > 0 else 1.0
    scale_visit = (prob_visitante_post / prob_visitante_pre) if prob_visitante_pre > 0 else 1.0
    grid_elo = grid_goles.copy()
    grid_elo[dif_grid > 0] *= scale_local
    grid_elo[dif_grid < 0] *= scale_visit
    return grid_elo / grid_elo.sum()


LINEAS_HANDICAP_ASIATICO = [-3.0, -2.5, -2.0, -1.5, -1.0, -0.5, 0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0]


def probabilidad_handicap_asiatico(dif_grid, grid, linea):
    """(cubre, push, no_cubre) para UNA linea de handicap asiatico sobre
    el equipo LOCAL (negativo = local favorito, ej. -1.5 = "Local -1.5").
    "Visitante +1.5" es la misma apuesta vista del otro lado -- no hace
    falta un campo separado, no_cubre YA es la probabilidad de que el
    visitante cubra (descontando push).

    "Local L" cubre si dif + L > 0, o sea dif > -L (dif_grid = goles
    local - goles visitante): Local -1.5 cubre si gana por 2 o mas,
    Local +1.5 si no pierde por 2 o mas. Misma convencion que el
    europeo (prob_hcp_local_m1 = dif > 1 = "Local -1"). Hasta el
    2026-09-23 la formula comparaba contra +linea (dif > linea): cada
    linea mostraba en realidad la probabilidad de la linea opuesta (la
    "-1.0" era "Local +1", igual a 1X). Las probabilidades no cambiaron
    con el arreglo, solo que numero va con cada linea -- y el backtest
    de abajo sigue valiendo: el conjunto de 13 lineas es simetrico, los
    mismos eventos con el signo bien puesto.

    Una sola formula sirve para lineas enteras (con push, ej. -1) y
    medias (sin push, ej. -1.5): dif_grid es siempre entero, asi que
    dif_grid == -linea da exactamente 0 cuando linea es .5 -- no hace
    falta ramificar el codigo por tipo de linea.

    grid tiene que ser grid_handicap (reescalada por Elo si hay Elo
    disponible), no grid_goles sin reescalar -- backtest de 1461
    partidos confirmo mejora real y consistente en las 13 lineas de
    LINEAS_HANDICAP_ASIATICO con el reescalado, sin ninguna excepcion
    (ver conversacion de diseno)."""
    cubre = float(grid[dif_grid > -linea].sum())
    push = float(grid[dif_grid == -linea].sum())
    no_cubre = float(grid[dif_grid < -linea].sum())
    return cubre, push, no_cubre


def simular_partido_futbol(
    media_goles_a,
    media_goles_b,
    std_goles_a,
    std_goles_b,
    media_corners_a,
    media_corners_b,
    media_tarjetas_total,
    media_tiros_arco_a=None,
    media_tiros_arco_b=None,
    media_tiros_total_a=None,
    media_tiros_total_b=None,
    media_tarjetas_a=None,
    media_atajadas_a=None,
    media_atajadas_b=None,
    sims=10000,
    k_goles_a=None,
    k_goles_b=None,
    k_corners_a=None,
    k_corners_b=None,
    k_tarjetas=None,
    k_tiros_arco_a=None,
    k_tiros_arco_b=None,
    k_tiros_total_a=None,
    k_tiros_total_b=None,
    k_atajadas_a=None,
    k_atajadas_b=None,
    elo_local=None,
    elo_visitante=None,
    peso_elo=None,
):
    # Aplicar limites realistas a los inputs
    media_goles_a = float(np.clip(media_goles_a, GOLES_MIN, GOLES_MAX))
    media_goles_b = float(np.clip(media_goles_b, GOLES_MIN, GOLES_MAX))
    media_corners_a = float(np.clip(media_corners_a, CORNERS_MIN, CORNERS_MAX))
    media_corners_b = float(np.clip(media_corners_b, CORNERS_MIN, CORNERS_MAX))
    # Peso proporcional para el reparto local/visitante de tarjetas (ver
    # mas abajo, despues del ajuste de parejez) -- calculado ANTES de
    # cualquier clip de esta funcion, sobre los mismos numeros que ya
    # arma ajustar_medias_con_rival() (Opcion A: el total se ajusta y
    # clipea sin cambios, el reparto es aritmetica aparte que no toca el
    # muestreo). None si el caller no lo paso (compatibilidad con
    # probabilidad_linea_personalizada, que no lo usa).
    peso_tarjetas_local = (
        media_tarjetas_a / media_tarjetas_total
        if media_tarjetas_a is not None and media_tarjetas_total > 0
        else None
    )
    media_tarjetas_total = float(np.clip(media_tarjetas_total, TARJETAS_MIN, TARJETAS_MAX))
    # Tiros son opcionales (default None) para no romper otros callers que
    # todavia no los pasan (ej. probabilidad_linea_personalizada no los usa).
    tiene_tiros = _media_valida(media_tiros_arco_a) and _media_valida(media_tiros_arco_b) \
        and _media_valida(media_tiros_total_a) and _media_valida(media_tiros_total_b)
    if tiene_tiros:
        media_tiros_arco_a = float(np.clip(media_tiros_arco_a, TIROS_ARCO_MIN, TIROS_ARCO_MAX))
        media_tiros_arco_b = float(np.clip(media_tiros_arco_b, TIROS_ARCO_MIN, TIROS_ARCO_MAX))
        media_tiros_total_a = float(np.clip(media_tiros_total_a, TIROS_TOTAL_MIN, TIROS_TOTAL_MAX))
        media_tiros_total_b = float(np.clip(media_tiros_total_b, TIROS_TOTAL_MIN, TIROS_TOTAL_MAX))
    # Atajadas: mismo patron opcional que tiros (default None para no
    # romper otros callers), chequeado y clipeado aparte.
    tiene_atajadas = _media_valida(media_atajadas_a) and _media_valida(media_atajadas_b)
    if tiene_atajadas:
        media_atajadas_a = float(np.clip(media_atajadas_a, ATAJADAS_MIN, ATAJADAS_MAX))
        media_atajadas_b = float(np.clip(media_atajadas_b, ATAJADAS_MIN, ATAJADAS_MAX))

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

    # Tiros: mismo patron que corners (Gamma-Poisson independiente, sin
    # ajuste de parejez). Opcional -- si el caller no los paso, quedan
    # como None y no se calculan tiros_arco_ou/tiros_total_ou mas abajo.
    #
    # Guardar/restaurar el estado del generador global alrededor de este
    # bloque -- sin esto, agregar estas 4 llamadas nuevas corre la
    # posicion del stream para TODO lo que viene despues en la misma
    # corrida seedeada por partido (tarjetas mas abajo, el re-muestreo de
    # corners_ou/tarjetas_ou en futbol_service.simular() cuando hay
    # multiplicador de presion/intensidad, y goles_1t en
    # get_analisis_partido()) -- ninguno de esos cambiaria de VALOR
    # esperado, pero silenciosamente dejarian de dar el mismo numero
    # concreto que antes de agregar tiros, con partidos ya consultados
    # antes por un usuario. Restaurar el estado deja esa parte del
    # pipeline byte-identica, tiros incluido (mismo seed determinista
    # por partido, solo en una sub-porcion propia del stream).
    if tiene_tiros:
        _rng_state_pre_tiros = np.random.get_state()
        tiros_arco_a = _muestrear_conteo(media_tiros_arco_a, k_tiros_arco_a, sims)
        tiros_arco_b = _muestrear_conteo(media_tiros_arco_b, k_tiros_arco_b, sims)
        tiros_total_a = _muestrear_conteo(media_tiros_total_a, k_tiros_total_a, sims)
        tiros_total_b = _muestrear_conteo(media_tiros_total_b, k_tiros_total_b, sims)
        np.random.set_state(_rng_state_pre_tiros)

    # Atajadas: mismo patron Gamma-Poisson independiente que tiros, en su
    # PROPIO bloque de guardado/restauracion de RNG -- separado del de
    # tiros de arriba a proposito, para no tocar esa ventana ya validada
    # byte a byte. Aislado desde el principio (no se espera a que
    # aparezca el problema, ver conversacion de diseno).
    if tiene_atajadas:
        _rng_state_pre_atajadas = np.random.get_state()
        atajadas_a = _muestrear_conteo(media_atajadas_a, k_atajadas_a, sims)
        atajadas_b = _muestrear_conteo(media_atajadas_b, k_atajadas_b, sims)
        np.random.set_state(_rng_state_pre_atajadas)

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

    # Reparto Binomial de tarjetas por equipo (Bloque 5) -- sobre la
    # MISMA muestra del total de arriba, que nunca se toca: por
    # construccion algebraica, tarjetas_a_muestra + tarjetas_b_muestra ==
    # tarjetas siempre, exacto (no aproximado). peso_tarjetas_local ya
    # viene clippeado a 0.15-0.85 desde ajustar_medias_con_rival() en
    # football_model.py. Backtest aprobado (ver conversacion de diseno):
    # mejora consistente en Brier score y log loss del reparto, sin
    # ninguna excepcion en las 5 lineas evaluadas ni en 2 semillas
    # distintas (~1470 partidos held-out cada una). None si el caller no
    # paso media_tarjetas_a (compatibilidad con probabilidad_linea_
    # personalizada), igual que ya pasaba con el reparto proporcional
    # de antes de este bloque.
    #
    # Guardar/restaurar el estado del RNG alrededor de esta llamada nueva
    # -- mismo motivo que tiros/atajadas: sin esto correria el stream
    # para todo lo que viene despues en la misma corrida (mitades, mas
    # abajo).
    tarjetas_a_muestra = None
    tarjetas_b_muestra = None
    if peso_tarjetas_local is not None:
        _rng_state_pre_tarjetas_equipo = np.random.get_state()
        tarjetas_a_muestra = np.random.binomial(tarjetas, peso_tarjetas_local)
        tarjetas_b_muestra = tarjetas - tarjetas_a_muestra
        np.random.set_state(_rng_state_pre_tarjetas_equipo)

    total_corners = corners_a + corners_b

    # RESULTADO 1X2 (desde la grilla Dixon-Coles)
    prob_local     = float(grid_goles[xs_grid > ys_grid].sum())
    prob_empate    = float(grid_goles[xs_grid == ys_grid].sum())
    prob_visitante = float(grid_goles[xs_grid < ys_grid].sum())

    # Ajuste de Elo -- SOLO toca estas 3 variables (y por extension el
    # handicap, ver grid_handicap mas abajo). No modifica grid_goles ni
    # ninguna otra proyeccion (goles_ou, corners, tarjetas, ambos_marcan,
    # marcador exacto, mitades siguen leyendo directo de grid_goles/
    # corners_a/corners_b/media_tarjetas_total, sin pasar por este
    # bloque ni por grid_handicap -- backtest confirmo que ahi el
    # reescalado no aporta, ver _reescalar_grid_por_elo()). El empate no
    # se toca -- se queda con lo que ya daba Dixon-Coles; Elo solo
    # redistribuye el resto (todo lo que no es empate) entre local y
    # visitante segun a quien favorece la diferencia de rating. Ver
    # conversacion de diseno / elo_ranking.py.
    prob_local_pre_elo = prob_local
    prob_visitante_pre_elo = prob_visitante

    if elo_local is not None and elo_visitante is not None and peso_elo:
        dr = (elo_local + VENTAJA_LOCAL_ELO) - elo_visitante
        e_local_elo = 1.0 / (1.0 + 10 ** (-dr / ESCALA_ELO))
        no_empate = 1.0 - prob_empate
        prob_local_elo = e_local_elo * no_empate
        prob_visitante_elo = (1.0 - e_local_elo) * no_empate
        prob_local = prob_local * (1 - peso_elo) + prob_local_elo * peso_elo
        prob_visitante = prob_visitante * (1 - peso_elo) + prob_visitante_elo * peso_elo

    # DOBLE OPORTUNIDAD (se calculan DESPUES del ajuste de Elo -- son una
    # suma directa de los 3 valores de arriba, no un mercado independiente)
    prob_1x = prob_local + prob_empate
    prob_x2 = prob_empate + prob_visitante
    prob_12 = prob_local + prob_visitante

    # GRILLA DE HANDICAP -- unica y exclusivamente para los 6 prob_hcp_*
    # de abajo. Si hay Elo disponible, reescala grid_goles proporcional
    # al mismo movimiento que el Elo ya le aplico a prob_local/
    # prob_visitante (ver _reescalar_grid_por_elo()); si no hay Elo,
    # grid_handicap == grid_goles. Backtest de 1456 partidos (mismo
    # criterio de muestra que el backtest de Elo sobre 1X2) confirmo
    # mejora real en Brier score y log loss de handicap con este
    # reescalado -- medido tambien sobre goles_ou y ambos_marcan sin
    # encontrar mejora practica en ninguno de los dos, por eso esos
    # mercados (y marcador exacto/proyecciones) siguen leyendo de
    # grid_goles sin reescalar, mas abajo.
    grid_handicap = grid_goles
    if elo_local is not None and elo_visitante is not None and peso_elo:
        grid_handicap = _reescalar_grid_por_elo(
            grid_goles, dif_grid, prob_local_pre_elo, prob_visitante_pre_elo, prob_local, prob_visitante
        )

    # HANDICAP 3-WAY
    prob_hcp_local_m1    = float(grid_handicap[dif_grid > 1].sum())
    prob_hcp_empate_m1   = float(grid_handicap[dif_grid == 1].sum())
    prob_hcp_visit_m1    = float(grid_handicap[dif_grid < 1].sum())
    prob_hcp_local_p1    = float(grid_handicap[dif_grid > -1].sum())
    prob_hcp_empate_p1   = float(grid_handicap[dif_grid == -1].sum())
    prob_hcp_visit_p1    = float(grid_handicap[dif_grid < -1].sum())
    # +/-2 y +/-3: misma grid_handicap y misma convencion (m = "Local -k",
    # gana si dif > k; p = "Local +k", gana si dif > -k). Son exactamente
    # los mismos eventos que cubre/push/no_cubre de las lineas enteras
    # del asiatico (+/-2, +/-3), ya cubiertas por su backtest de 1461
    # partidos -- sin backtest nuevo. Medido sobre 200 partidos: +/-3 da
    # un lado >= 95% en ~28-50% de los partidos (informacion real, se
    # muestra igual, decision de producto).
    prob_hcp_local_m2    = float(grid_handicap[dif_grid > 2].sum())
    prob_hcp_empate_m2   = float(grid_handicap[dif_grid == 2].sum())
    prob_hcp_visit_m2    = float(grid_handicap[dif_grid < 2].sum())
    prob_hcp_local_p2    = float(grid_handicap[dif_grid > -2].sum())
    prob_hcp_empate_p2   = float(grid_handicap[dif_grid == -2].sum())
    prob_hcp_visit_p2    = float(grid_handicap[dif_grid < -2].sum())
    prob_hcp_local_m3    = float(grid_handicap[dif_grid > 3].sum())
    prob_hcp_empate_m3   = float(grid_handicap[dif_grid == 3].sum())
    prob_hcp_visit_m3    = float(grid_handicap[dif_grid < 3].sum())
    prob_hcp_local_p3    = float(grid_handicap[dif_grid > -3].sum())
    prob_hcp_empate_p3   = float(grid_handicap[dif_grid == -3].sum())
    prob_hcp_visit_p3    = float(grid_handicap[dif_grid < -3].sum())

    # HANDICAP ASIATICO -- 13 lineas, misma grid_handicap que el europeo
    # (backtest de 1461 partidos confirmo mejora real y consistente con
    # el reescalado en las 13, sin excepcion, ver probabilidad_handicap_
    # asiatico()). Sin cuartos de linea (.25/.75) en esta entrega.
    handicap_asiatico = {}
    for linea in LINEAS_HANDICAP_ASIATICO:
        cubre, push, no_cubre = probabilidad_handicap_asiatico(dif_grid, grid_handicap, linea)
        handicap_asiatico[linea] = {
            "tipo": "entera" if linea == int(linea) else "media",
            "cubre": cubre,
            "push": push,
            "no_cubre": no_cubre,
        }

    # AMBOS MARCAN (grid_goles sin reescalar -- ver nota de grid_handicap arriba)
    prob_ambos = float(grid_goles[(xs_grid >= 1) & (ys_grid >= 1)].sum())

    # OVER/UNDER GOLES 0.5 a 7.5 (grid_goles sin reescalar -- ver nota de grid_handicap arriba)
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

    # OVER/UNDER GOLES/CORNERS POR EQUIPO (Bloque 3) -- goles_ou_local/
    # visitante salen de la marginal de grid_goles (cerrado, sin Monte
    # Carlo, mismo criterio que goles_local_proj/goles_visitante_proj
    # mas abajo); corners_ou_local/visitante reusan corners_a/corners_b
    # ya muestreados arriba, sin ningun muestreo nuevo -- ver
    # conversacion de diseno (Bloque 3) sobre por que esto no necesita
    # guardar/restaurar el estado del RNG como si hizo falta con tiros/
    # atajadas: no hay ninguna llamada nueva a np.random en este bloque.
    marginal_goles_a = grid_goles.sum(axis=1)
    marginal_goles_b = grid_goles.sum(axis=0)
    goles_ou_local = _ou_desde_pmf(marginal_goles_a, LINEAS_GOLES_EQUIPO)
    goles_ou_visitante = _ou_desde_pmf(marginal_goles_b, LINEAS_GOLES_EQUIPO)
    corners_ou_local = _ou_desde_muestra(corners_a, LINEAS_CORNERS_EQUIPO)
    corners_ou_visitante = _ou_desde_muestra(corners_b, LINEAS_CORNERS_EQUIPO)

    # OVER/UNDER TARJETAS 0.5 a 11.5
    tarjetas_ou = {}
    for linea in [0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5, 7.5, 8.5, 9.5, 10.5, 11.5]:
        tarjetas_ou[linea] = {
            "over":  float(np.mean(tarjetas > linea)),
            "under": float(np.mean(tarjetas < linea))
        }

    # OVER/UNDER TARJETAS POR EQUIPO (Bloque 5) -- reusa tarjetas_a_
    # muestra/tarjetas_b_muestra del reparto Binomial de arriba, sin
    # muestreo nuevo en este punto. None si peso_tarjetas_local no vino
    # (mismo criterio que el resto de los mercados opcionales).
    tarjetas_ou_local = None
    tarjetas_ou_visitante = None
    if tarjetas_a_muestra is not None:
        tarjetas_ou_local = _ou_desde_muestra(tarjetas_a_muestra, LINEAS_TARJETAS_EQUIPO)
        tarjetas_ou_visitante = _ou_desde_muestra(tarjetas_b_muestra, LINEAS_TARJETAS_EQUIPO)

    # OVER/UNDER TIROS AL ARCO 3.5 a 18.5, TIROS TOTALES 15.5 a 42.5 --
    # mismo criterio de tope que corners/tarjetas (~p99 real + 1.5), ver
    # conversacion de diseno del Bloque 1. None si el caller no paso
    # medias de tiros (backward-compatible con probabilidad_linea_
    # personalizada, que no las usa).
    tiros_arco_ou = None
    tiros_total_ou = None
    total_tiros_arco = None
    total_tiros_total = None
    if tiene_tiros:
        total_tiros_arco = tiros_arco_a + tiros_arco_b
        total_tiros_total = tiros_total_a + tiros_total_b
        tiros_arco_ou = {}
        for linea in [3.5, 4.5, 5.5, 6.5, 7.5, 8.5, 9.5, 10.5, 11.5, 12.5, 13.5, 14.5, 15.5, 16.5, 17.5, 18.5]:
            tiros_arco_ou[linea] = {
                "over":  float(np.mean(total_tiros_arco > linea)),
                "under": float(np.mean(total_tiros_arco < linea))
            }
        tiros_total_ou = {}
        for linea in [15.5, 16.5, 17.5, 18.5, 19.5, 20.5, 21.5, 22.5, 23.5, 24.5, 25.5, 26.5, 27.5, 28.5,
                       29.5, 30.5, 31.5, 32.5, 33.5, 34.5, 35.5, 36.5, 37.5, 38.5, 39.5, 40.5, 41.5, 42.5]:
            tiros_total_ou[linea] = {
                "over":  float(np.mean(total_tiros_total > linea)),
                "under": float(np.mean(total_tiros_total < linea))
            }

    # OVER/UNDER TIROS POR EQUIPO (Bloque 3) -- reusan tiros_arco_a/b y
    # tiros_total_a/b ya muestreados arriba (tiene_tiros), sin muestreo
    # nuevo. None si tiene_tiros es False, mismo criterio que tiros_arco_ou.
    tiros_arco_ou_local = None
    tiros_arco_ou_visitante = None
    tiros_total_ou_local = None
    tiros_total_ou_visitante = None
    if tiene_tiros:
        tiros_arco_ou_local = _ou_desde_muestra(tiros_arco_a, LINEAS_TIROS_ARCO_EQUIPO)
        tiros_arco_ou_visitante = _ou_desde_muestra(tiros_arco_b, LINEAS_TIROS_ARCO_EQUIPO)
        tiros_total_ou_local = _ou_desde_muestra(tiros_total_a, LINEAS_TIROS_TOTAL_EQUIPO)
        tiros_total_ou_visitante = _ou_desde_muestra(tiros_total_b, LINEAS_TIROS_TOTAL_EQUIPO)

    # OVER/UNDER ATAJADAS 1.5 a 14.5 -- percentiles reales sobre el
    # dataset ya sincronizado: p1=1, p99=13 (total del partido), mismo
    # margen de +1.5 sobre p99 que ya usan tarjetas_ou/tiros_arco_ou.
    # None si el caller no paso medias de atajadas.
    atajadas_ou = None
    total_atajadas = None
    atajadas_ou_local = None
    atajadas_ou_visitante = None
    if tiene_atajadas:
        total_atajadas = atajadas_a + atajadas_b
        atajadas_ou = {}
        for linea in [1.5, 2.5, 3.5, 4.5, 5.5, 6.5, 7.5, 8.5, 9.5, 10.5, 11.5, 12.5, 13.5, 14.5]:
            atajadas_ou[linea] = {
                "over":  float(np.mean(total_atajadas > linea)),
                "under": float(np.mean(total_atajadas < linea))
            }
        # OVER/UNDER ATAJADAS POR EQUIPO (Bloque 3) -- reusa atajadas_a/b
        # ya muestreados arriba, sin muestreo nuevo.
        atajadas_ou_local = _ou_desde_muestra(atajadas_a, LINEAS_ATAJADAS_EQUIPO)
        atajadas_ou_visitante = _ou_desde_muestra(atajadas_b, LINEAS_ATAJADAS_EQUIPO)

    # MARCADOR EXACTO top 6 (probabilidad exacta de la grilla, no conteo
    # de muestras; grid_goles sin reescalar -- ver nota de grid_handicap arriba)
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
        "prob_hcp_local_m2": prob_hcp_local_m2,
        "prob_hcp_empate_m2": prob_hcp_empate_m2,
        "prob_hcp_visit_m2": prob_hcp_visit_m2,
        "prob_hcp_local_p2": prob_hcp_local_p2,
        "prob_hcp_empate_p2": prob_hcp_empate_p2,
        "prob_hcp_visit_p2": prob_hcp_visit_p2,
        "prob_hcp_local_m3": prob_hcp_local_m3,
        "prob_hcp_empate_m3": prob_hcp_empate_m3,
        "prob_hcp_visit_m3": prob_hcp_visit_m3,
        "prob_hcp_local_p3": prob_hcp_local_p3,
        "prob_hcp_empate_p3": prob_hcp_empate_p3,
        "prob_hcp_visit_p3": prob_hcp_visit_p3,
        # HANDICAP ASIATICO
        "handicap_asiatico": handicap_asiatico,
        # AMBOS MARCAN
        "prob_ambos_marcan": prob_ambos,
        # OVER/UNDER
        "goles_ou": goles_ou,
        "corners_ou": corners_ou,
        "tarjetas_ou": tarjetas_ou,
        "tiros_arco_ou": tiros_arco_ou,
        "tiros_total_ou": tiros_total_ou,
        "atajadas_ou": atajadas_ou,
        # OVER/UNDER POR EQUIPO (Bloque 3, local/visitante por separado --
        # ver conversacion de diseno sobre percentiles y lineas)
        "goles_ou_local": goles_ou_local,
        "goles_ou_visitante": goles_ou_visitante,
        "corners_ou_local": corners_ou_local,
        "corners_ou_visitante": corners_ou_visitante,
        "tiros_arco_ou_local": tiros_arco_ou_local,
        "tiros_arco_ou_visitante": tiros_arco_ou_visitante,
        "tiros_total_ou_local": tiros_total_ou_local,
        "tiros_total_ou_visitante": tiros_total_ou_visitante,
        "atajadas_ou_local": atajadas_ou_local,
        "atajadas_ou_visitante": atajadas_ou_visitante,
        # Tarjetas por equipo (Bloque 5) -- reparto Binomial sobre la
        # muestra del total, no reparto proporcional de la media (ver
        # tarjetas_a_muestra mas arriba y conversacion de diseno)
        "tarjetas_ou_local": tarjetas_ou_local,
        "tarjetas_ou_visitante": tarjetas_ou_visitante,
        # MARCADOR EXACTO
        "marcadores_prob": marcadores_prob,
        # MITADES
        "prob_1t_local": prob_1t_local,
        "prob_1t_empate": prob_1t_empate,
        "prob_1t_visitante": prob_1t_visitante,
        "prob_2t_local": prob_2t_local,
        "prob_2t_empate": prob_2t_empate,
        "prob_2t_visitante": prob_2t_visitante,
        # PROYECCIONES (esperanza de la grilla Dixon-Coles sin reescalar,
        # no de las muestras de mitades -- ver nota de grid_handicap arriba)
        "goles_local_proj": float(np.sum(np.arange(n_grid) * grid_goles.sum(axis=1))),
        "goles_visitante_proj": float(np.sum(np.arange(n_grid) * grid_goles.sum(axis=0))),
        "corners_totales_proj": float(total_corners.mean()),
        "corners_local_proj": float(corners_a.mean()),
        "corners_visitante_proj": float(corners_b.mean()),
        "tarjetas_totales_proj": float(tarjetas.mean()),
        # Bloque 5: media de tarjetas_a_muestra/tarjetas_b_muestra (el
        # reparto Binomial de arriba), ya no el reparto proporcional
        # deterministico de la media (Opcion A, antes de este bloque).
        # Por construccion, tarjetas_local_proj + tarjetas_visitante_proj
        # == tarjetas_totales_proj sigue siendo una identidad algebraica
        # exacta (tarjetas_a_muestra + tarjetas_b_muestra == tarjetas en
        # CADA muestra, no solo en promedio) -- None si el caller no paso
        # media_tarjetas_a (mismo criterio que siempre).
        "tarjetas_local_proj": float(tarjetas_a_muestra.mean()) if tarjetas_a_muestra is not None else None,
        "tarjetas_visitante_proj": float(tarjetas_b_muestra.mean()) if tarjetas_b_muestra is not None else None,
        "tiros_arco_totales_proj": float(total_tiros_arco.mean()) if tiene_tiros else None,
        "tiros_arco_local_proj": float(tiros_arco_a.mean()) if tiene_tiros else None,
        "tiros_arco_visitante_proj": float(tiros_arco_b.mean()) if tiene_tiros else None,
        "tiros_total_totales_proj": float(total_tiros_total.mean()) if tiene_tiros else None,
        "tiros_total_local_proj": float(tiros_total_a.mean()) if tiene_tiros else None,
        "tiros_total_visitante_proj": float(tiros_total_b.mean()) if tiene_tiros else None,
        # Directo (mean() de cada array por separado), sin el truco de
        # reparto proporcional de tarjetas -- mismo criterio que tiros_arco.
        "atajadas_totales_proj": float(total_atajadas.mean()) if tiene_atajadas else None,
        "atajadas_local_proj": float(atajadas_a.mean()) if tiene_atajadas else None,
        "atajadas_visitante_proj": float(atajadas_b.mean()) if tiene_atajadas else None,
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
