"""
Tabla de fuerza relativa por liga domestica de clubes, para ajustar el
enfrentamiento entre equipos de ligas de distinto nivel (ej. un equipo de
Premier League contra uno de Championship en una copa). Mismo patron que
fifa_ranking.py para selecciones, pero sin capa de API/DB -- la fuerza de
una liga no cambia dia a dia como si lo hace un ranking FIFA.

Escala 0-100, criterio editorial (igual de subjetivo que FIFA_FALLBACK),
ajustable a mano si algun caso puntual lo amerita. Copas domesticas,
continentales, supercopas y Mundial 2026 quedan fuera de esta tabla --
no representan la liga de origen de un equipo.
"""

NIVEL_LIGA_CLUBES = {
    # Top flight
    "Premier League": 100,
    "La Liga": 95,
    "Bundesliga": 90,
    "Serie A": 88,
    "Ligue 1": 82,
    "Brasileirao": 75,
    "Primeira Liga": 72,
    "Liga Profesional Argentina": 68,
    "Eredivisie": 68,
    "Super Lig Turquia": 65,
    "Liga MX": 62,
    "Pro League Belgica": 62,
    "Pro League Arabia": 60,
    "MLS": 58,
    "Liga Colombia": 50,
    "Primera Division Chile": 50,
    "Primera Division Uruguay": 48,
    "Primera Division Peru": 45,
    "Liga Pro Ecuador": 45,
    "Division Profesional Paraguay": 42,
    "Premier League Egipto": 40,
    "Primera Division Bolivia": 38,
    "Primera Division Venezuela": 35,

    # Segundas divisiones (solo historial de equipos rivales puntuales)
    "Championship": 55,
    "Serie B Brasil": 55,
    "2. Bundesliga": 52,
    "Serie B Italia": 50,
    "Segunda Division Espana": 50,
    "Ligue 2": 48,
    "Eerste Divisie": 42,
    "3. Liga": 35,
    "Primera B Colombia": 30,
    "Primera B Metropolitana": 25,
    "Second League Egipto": 20,
}


# ---------------------------------------------------------------------------
# Ligas fuera de la tabla editorial (plan A+B del 16/10/2026). Separadas de
# NIVEL_LIGA_CLUBES a proposito: los factores entre las ligas que ya
# estaban no cambian (ver tests/test_ajuste_liga.py).
# ---------------------------------------------------------------------------

# A) Ligas europeas: nivel sacado del coeficiente UEFA por pais (publico, no
# sale de nuestros resultados, asi que no sobreajusta a los partidos con los
# que se valida). Ranking 2025 = fin de la temporada 2024/25: no incluye
# ningun resultado de los partidos del backtest (desde 07/2025).
# Curva ajustada sobre las 9 ligas UEFA de la tabla editorial (sus niveles
# no se tocan): nivel = -103.435 + 42.620 * ln(coeficiente UEFA por pais,
# 5 temporadas, ranking 2025), acotado a 0-100 y redondeado.
NIVEL_LIGA_UEFA = {
    "Czech Liga Czech-Republic": 58,  # Czechia, coef 44.100
    "Eliteserien Norway": 53,  # Norway, coef 39.687
    "Super League 1 Greece": 53,  # Greece, coef 39.312
    "Bundesliga Austria": 50,  # Austria, coef 36.450
    "Premiership Scotland": 49,  # Scotland, coef 35.550
    "Ekstraklasa Poland": 48,  # Poland, coef 35.000
    "Superliga Denmark": 47,  # Denmark, coef 33.981
    "Super League Switzerland": 46,  # Switzerland, coef 33.625
    "Ligat Ha'al Israel": 44,  # Israel, coef 31.625
    "1. Division Cyprus": 38,  # Cyprus, coef 27.537
    "Allsvenskan Sweden": 37,  # Sweden, coef 27.125
    "HNL Croatia": 37,  # Croatia, coef 27.025
    "Super Liga Serbia": 35,  # Serbia, coef 25.500
    "Premier League Ukraine": 33,  # Ukraine, coef 24.400
    "NB I Hungary": 32,  # Hungary, coef 24.000
    "Liga I Romania": 31,  # Romania, coef 23.250
    "Super Liga Slovakia": 27,  # Slovakia, coef 21.250
    "1. SNL Slovenia": 25,  # Slovenia, coef 20.343
    "First League Bulgaria": 24,  # Bulgaria, coef 19.875
    "Premyer Liqa Azerbaijan": 23,  # Azerbaijan, coef 19.625
    "Úrvalsdeild Iceland": 8,  # Iceland, coef 13.520
    "Premijer Liga Bosnia": 6,  # Bosnia-Herzegovina, coef 13.031
    "Virsliga Latvia": 3,  # Latvia, coef 12.250
    "Premier League Armenia": 3,  # Armenia, coef 12.250
    "Veikkausliiga Finland": 2,  # Finland, coef 11.750
    "Premier League Kazakhstan": 0,  # Kazakhstan, coef 11.125
    "A Lyga Lithuania": 0,  # Lithuania, coef 8.250
    "Superliga Albania": 0,  # Albania, coef 7.875
    "Erovnuli Liga Georgia": 0,  # Georgia, coef 6.625
    "1a Divisió Andorra": 0,  # Andorra, coef 5.498
    "Premier Division Gibraltar": 0,  # Gibraltar, coef 5.457
}

# Nivel por pais (nombres de pais de api-football), para equipos sin liga
# domestica cargada en copas UEFA. Las 9 asociaciones ancla usan el nivel
# de su liga en la tabla editorial; el resto, la misma curva.
NIVEL_PAIS_UEFA = {
    "England": 100,  # coef 115.196
    "Italy": 88,  # coef 97.231
    "Spain": 95,  # coef 94.453
    "Germany": 90,  # coef 86.331
    "France": 82,  # coef 73.093
    "Netherlands": 68,  # coef 67.150
    "Portugal": 72,  # coef 62.266
    "Belgium": 62,  # coef 56.850
    "Czech-Republic": 58,  # coef 44.100
    "Turkey": 65,  # coef 43.900
    "Norway": 53,  # coef 39.687
    "Greece": 53,  # coef 39.312
    "Austria": 50,  # coef 36.450
    "Scotland": 49,  # coef 35.550
    "Poland": 48,  # coef 35.000
    "Denmark": 47,  # coef 33.981
    "Switzerland": 46,  # coef 33.625
    "Israel": 44,  # coef 31.625
    "Cyprus": 38,  # coef 27.537
    "Sweden": 37,  # coef 27.125
    "Croatia": 37,  # coef 27.025
    "Serbia": 35,  # coef 25.500
    "Ukraine": 33,  # coef 24.400
    "Hungary": 32,  # coef 24.000
    "Romania": 31,  # coef 23.250
    "Russia": 30,  # coef 22.632
    "Slovakia": 27,  # coef 21.250
    "Slovenia": 25,  # coef 20.343
    "Bulgaria": 24,  # coef 19.875
    "Azerbaijan": 23,  # coef 19.625
    "Ireland": 12,  # coef 14.968
    "Moldova": 11,  # coef 14.500
    "Iceland": 8,  # coef 13.520
    "Bosnia": 6,  # coef 13.031
    "Armenia": 3,  # coef 12.250
    "Latvia": 3,  # coef 12.250
    "Kosovo": 3,  # coef 12.041
    "Finland": 2,  # coef 11.750
    "Kazakhstan": 0,  # coef 11.125
    "Faroe-Islands": 0,  # coef 10.750
    "Malta": 0,  # coef 8.500
    "Northern-Ireland": 0,  # coef 8.333
    "Lithuania": 0,  # coef 8.250
    "Liechtenstein": 0,  # coef 8.000
    "Estonia": 0,  # coef 7.957
    "Albania": 0,  # coef 7.875
    "Montenegro": 0,  # coef 7.208
    "Luxembourg": 0,  # coef 6.875
    "Wales": 0,  # coef 6.791
    "Georgia": 0,  # coef 6.625
    "Macedonia": 0,  # coef 6.166
    "Belarus": 0,  # coef 6.000
    "Andorra": 0,  # coef 5.498
    "Gibraltar": 0,  # coef 5.457
    "San-Marino": 0,  # coef 2.498
}

# A) Ligas validas sin coeficiente UEFA: criterio editorial, SIN VALIDAR
# (mismo criterio subjetivo que el resto de la tabla).
NIVEL_LIGA_SIN_VALIDAR = {
    "Primera Nacional Argentina": 35,
    "Liga de Expansion MX": 35,
    "2. Lig Turquia": 25,
    "Primera C Argentina": 10,
}

# B) Nivel por pais de las asociaciones CONMEBOL/CONCACAF: el de su primera
# division en la tabla editorial.
NIVEL_PAIS_AMERICA = {
    "Brazil": 75, "Argentina": 68, "Colombia": 50, "Chile": 50,
    "Uruguay": 48, "Peru": 45, "Ecuador": 45, "Paraguay": 42,
    "Bolivia": 38, "Venezuela": 35, "Mexico": 62, "USA": 58,
}

COPAS_INTERNACIONALES = {
    "Champions League": "UEFA", "Europa League": "UEFA",
    "Conference League": "UEFA", "Super Cup UEFA": "UEFA",
    "Copa Libertadores": "CONMEBOL", "Copa Sudamericana": "CONMEBOL",
    "Recopa Sudamericana": "CONMEBOL",
    "CONCACAF Champions League": "CONCACAF", "Leagues Cup": "CONCACAF",
}

# B) Equipo sin pais conocido en copa internacional: percentil 25 de los
# niveles de las asociaciones de la confederacion (los equipos no seguidos
# que llegan a una copa son casi siempre de asociaciones chicas: de los 72
# equipos UEFA sin liga cargada al 16/10, 71 tienen pais y salen de
# asociaciones fuera del top 10 de coeficiente).
NIVEL_DEFAULT_CONFEDERACION = {
    "UEFA": 0,        # P25 de NIVEL_PAIS_UEFA (55 asociaciones)
    "CONMEBOL": 43,   # P25 de las 10 de NIVEL_PAIS_AMERICA
    "CONCACAF": 59,   # P25 de Mexico/USA
}

# Interruptores para el backtest (variantes "55 + A", "55 + B", etc.).
USAR_NIVELES_A = True
USAR_RED_B = True


def get_nivel_liga(liga):
    """Score de fuerza (0-100) de una liga domestica de clubes, o None si
    no esta en ninguna tabla."""
    nivel = NIVEL_LIGA_CLUBES.get(liga)
    if nivel is None and USAR_NIVELES_A:
        nivel = NIVEL_LIGA_UEFA.get(liga, NIVEL_LIGA_SIN_VALIDAR.get(liga))
    return nivel


def ligas_con_nivel_extra():
    """Ligas de la parte A, para sumarlas a las ligas de referencia."""
    if not USAR_NIVELES_A:
        return []
    return list(NIVEL_LIGA_UEFA) + list(NIVEL_LIGA_SIN_VALIDAR)


_pais_equipos = None


def _pais_equipo(equipo):
    global _pais_equipos
    if _pais_equipos is None:
        import json, os
        ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pais_equipos.json")
        try:
            with open(ruta, encoding="utf-8") as f:
                _pais_equipos = json.load(f)
        except (OSError, ValueError):
            _pais_equipos = {}
    return _pais_equipos.get(equipo)


def niveles_referencia(liga_ref_a, liga_ref_b, equipo_a, equipo_b, liga_partido):
    """Nivel (0-100) de cada equipo para ajuste_por_nivel(). Con liga de
    referencia, el de esa liga. Red de seguridad (B) para el que no tiene,
    solo si el rival si tiene (ambos sin referencia: neutro, como antes):
      - copa internacional: nivel de su pais, o el default de la
        confederacion si no se conoce el pais;
      - cualquier otro partido: la liga del propio partido, si tiene nivel
        (si juega la Primera Nacional, es de la Primera Nacional)."""
    nivel_a = get_nivel_liga(liga_ref_a) if liga_ref_a else None
    nivel_b = get_nivel_liga(liga_ref_b) if liga_ref_b else None
    if not USAR_RED_B or (liga_ref_a is None and liga_ref_b is None):
        return nivel_a, nivel_b

    def _red(equipo):
        confederacion = COPAS_INTERNACIONALES.get(liga_partido)
        if confederacion:
            pais = _pais_equipo(equipo)
            nivel = NIVEL_PAIS_UEFA.get(pais, NIVEL_PAIS_AMERICA.get(pais))
            return nivel if nivel is not None else NIVEL_DEFAULT_CONFEDERACION[confederacion]
        return get_nivel_liga(liga_partido) if liga_partido else None

    if liga_ref_a is None:
        nivel_a = _red(equipo_a)
    if liga_ref_b is None:
        nivel_b = _red(equipo_b)
    return nivel_a, nivel_b


def ajuste_por_nivel(score_a, score_b):
    """Mismo factor que ajuste_liga_clubes(), a partir de los niveles."""
    if score_a is None or score_b is None or score_a == score_b:
        return 1.0, 1.0

    diff = (score_a - score_b) / 60.0
    diff = max(-1.0, min(1.0, diff))

    factor_a = 1.0 + diff * 0.30
    factor_b = 1.0 - diff * 0.30

    return round(factor_a, 3), round(factor_b, 3)


def ajuste_liga_clubes(liga_a, liga_b):
    """Factor de ajuste de goles esperados por diferencia de nivel entre
    las ligas domesticas de dos equipos de club (ej. Premier League vs
    Championship en una copa). Retorna (factor_a, factor_b), ambos 1.0 si
    alguna liga es desconocida o son la misma."""
    if not liga_a or not liga_b or liga_a == liga_b:
        return 1.0, 1.0

    return ajuste_por_nivel(get_nivel_liga(liga_a), get_nivel_liga(liga_b))
