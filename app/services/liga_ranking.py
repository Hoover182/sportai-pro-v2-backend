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


def get_nivel_liga(liga):
    """Score de fuerza (0-100) de una liga domestica de clubes, o None si
    no esta en la tabla."""
    return NIVEL_LIGA_CLUBES.get(liga)


def ajuste_liga_clubes(liga_a, liga_b):
    """Factor de ajuste de goles esperados por diferencia de nivel entre
    las ligas domesticas de dos equipos de club (ej. Premier League vs
    Championship en una copa). Retorna (factor_a, factor_b), ambos 1.0 si
    alguna liga es desconocida o son la misma."""
    if not liga_a or not liga_b or liga_a == liga_b:
        return 1.0, 1.0

    score_a = NIVEL_LIGA_CLUBES.get(liga_a)
    score_b = NIVEL_LIGA_CLUBES.get(liga_b)
    if score_a is None or score_b is None:
        return 1.0, 1.0

    diff = (score_a - score_b) / 60.0
    diff = max(-1.0, min(1.0, diff))

    factor_a = 1.0 + diff * 0.30
    factor_b = 1.0 - diff * 0.30

    return round(factor_a, 3), round(factor_b, 3)
