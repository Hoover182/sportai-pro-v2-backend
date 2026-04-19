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


def simular_partido_futbol(
    media_goles_a,
    media_goles_b,
    std_goles_a,
    std_goles_b,
    media_corners_a,
    media_corners_b,
    media_tarjetas_total,
    sims=10000
):
    # Aplicar limites realistas a los inputs
    media_goles_a = float(np.clip(media_goles_a, GOLES_MIN, GOLES_MAX))
    media_goles_b = float(np.clip(media_goles_b, GOLES_MIN, GOLES_MAX))
    media_corners_a = float(np.clip(media_corners_a, CORNERS_MIN, CORNERS_MAX))
    media_corners_b = float(np.clip(media_corners_b, CORNERS_MIN, CORNERS_MAX))
    media_tarjetas_total = float(np.clip(media_tarjetas_total, TARJETAS_MIN, TARJETAS_MAX))

    # Goles con distribucion de Poisson (mas realista que normal para goles)
    # Mezclamos Poisson con un poco de variabilidad adicional
    std_goles_a = normalizar_std(std_goles_a, 0.35)
    std_goles_b = normalizar_std(std_goles_b, 0.35)

    goles_a = np.random.poisson(media_goles_a, sims).astype(float)
    goles_b = np.random.poisson(media_goles_b, sims).astype(float)

    # Corners y tarjetas con Poisson
    corners_a = np.random.poisson(media_corners_a, sims)
    corners_b = np.random.poisson(media_corners_b, sims)
    tarjetas = np.random.poisson(media_tarjetas_total, sims)

    total_goles = goles_a + goles_b
    total_corners = corners_a + corners_b

    # RESULTADO 1X2
    prob_local     = float(np.mean(goles_a > goles_b))
    prob_empate    = float(np.mean(goles_a == goles_b))
    prob_visitante = float(np.mean(goles_b > goles_a))

    # DOBLE OPORTUNIDAD
    prob_1x = prob_local + prob_empate
    prob_x2 = prob_empate + prob_visitante
    prob_12 = prob_local + prob_visitante

    # HANDICAP 3-WAY
    prob_hcp_local_m1    = float(np.mean((goles_a - goles_b) > 1))
    prob_hcp_empate_m1   = float(np.mean((goles_a - goles_b) == 1))
    prob_hcp_visit_m1    = float(np.mean((goles_a - goles_b) < 1))
    prob_hcp_local_p1    = float(np.mean((goles_a - goles_b) > -1))
    prob_hcp_empate_p1   = float(np.mean((goles_a - goles_b) == -1))
    prob_hcp_visit_p1    = float(np.mean((goles_a - goles_b) < -1))

    # AMBOS MARCAN
    prob_ambos = float(np.mean((goles_a > 0) & (goles_b > 0)))

    # OVER/UNDER GOLES 0.5 a 7.5
    goles_ou = {}
    for linea in [0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5, 7.5]:
        goles_ou[linea] = {
            "over":  float(np.mean(total_goles > linea)),
            "under": float(np.mean(total_goles < linea))
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

    # MARCADOR EXACTO top 6
    marcadores = Counter(zip(goles_a.astype(int), goles_b.astype(int)))
    top_marcadores = sorted(marcadores.items(), key=lambda x: x[1], reverse=True)[:6]
    marcadores_prob = [(f"{a}-{b}", round(c/sims*100, 1)) for (a,b), c in top_marcadores]

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
        # PROYECCIONES
        "goles_local_proj": float(goles_a.mean()),
        "goles_visitante_proj": float(goles_b.mean()),
        "corners_totales_proj": float(total_corners.mean()),
        "tarjetas_totales_proj": float(tarjetas.mean())
    }


def proyectar_tiempos(goles_a, goles_b):
    return {
        "A": [goles_a * 0.45, goles_a * 0.55],
        "B": [goles_b * 0.45, goles_b * 0.55]
    }
