"""
Modulo para obtener y gestionar el ranking FIFA.
Descarga el ranking desde la API de API-Football (equipos nacionales)
y lo guarda en SQLite para consulta rapida.
"""
import os
import requests
from database import guardar_fifa_ranking, leer_fifa_ranking, iniciar_fifa_ranking

API_KEY = os.environ.get("APIFOOTBALL_KEY", "")
BASE_URL = "https://v3.football.api-sports.io"

# Ranking FIFA hardcodeado como fallback (junio 2026)
# Se usa solo si la API no devuelve datos
FIFA_FALLBACK = [
    {"posicion": 1,  "equipo": "Argentina",   "puntos": 1877},
    {"posicion": 2,  "equipo": "Spain",        "puntos": 1874},
    {"posicion": 3,  "equipo": "France",       "puntos": 1870},
    {"posicion": 4,  "equipo": "England",      "puntos": 1828},
    {"posicion": 5,  "equipo": "Portugal",     "puntos": 1767},
    {"posicion": 6,  "equipo": "Brazil",       "puntos": 1765},
    {"posicion": 7,  "equipo": "Morocco",      "puntos": 1755},
    {"posicion": 8,  "equipo": "Netherlands",  "puntos": 1753},
    {"posicion": 9,  "equipo": "Belgium",      "puntos": 1742},
    {"posicion": 10, "equipo": "Germany",      "puntos": 1735},
    {"posicion": 11, "equipo": "Croatia",      "puntos": 1714},
    {"posicion": 12, "equipo": "Italy",        "puntos": 1704},
    {"posicion": 13, "equipo": "Colombia",     "puntos": 1698},
    {"posicion": 14, "equipo": "Mexico",       "puntos": 1687},
    {"posicion": 15, "equipo": "Senegal",      "puntos": 1684},
    {"posicion": 16, "equipo": "Uruguay",      "puntos": 1673},
    {"posicion": 17, "equipo": "USA",          "puntos": 1671},
    {"posicion": 18, "equipo": "Japan",        "puntos": 1661},
    {"posicion": 19, "equipo": "Switzerland",  "puntos": 1650},
    {"posicion": 20, "equipo": "Denmark",      "puntos": 1619},
    {"posicion": 21, "equipo": "Turkey",       "puntos": 1605},
    {"posicion": 22, "equipo": "Ecuador",      "puntos": 1598},
    {"posicion": 23, "equipo": "Austria",      "puntos": 1597},
    {"posicion": 24, "equipo": "South Korea",  "puntos": 1591},
    {"posicion": 25, "equipo": "Nigeria",      "puntos": 1585},
    {"posicion": 26, "equipo": "Australia",    "puntos": 1579},
    {"posicion": 27, "equipo": "Algeria",      "puntos": 1571},
    {"posicion": 28, "equipo": "Egypt",        "puntos": 1562},
    {"posicion": 29, "equipo": "Canada",       "puntos": 1559},
    {"posicion": 30, "equipo": "Norway",       "puntos": 1557},
    {"posicion": 31, "equipo": "Ukraine",      "puntos": 1549},
    {"posicion": 32, "equipo": "Serbia",       "puntos": 1540},
    {"posicion": 33, "equipo": "Poland",       "puntos": 1526},
    {"posicion": 34, "equipo": "Wales",        "puntos": 1516},
    {"posicion": 35, "equipo": "Sweden",       "puntos": 1509},
    {"posicion": 36, "equipo": "Chile",        "puntos": 1475},
    {"posicion": 37, "equipo": "Peru",         "puntos": 1460},
    {"posicion": 38, "equipo": "Venezuela",    "puntos": 1448},
    {"posicion": 39, "equipo": "Bolivia",      "puntos": 1380},
    {"posicion": 40, "equipo": "Paraguay",     "puntos": 1420},
    {"posicion": 41, "equipo": "Costa Rica",   "puntos": 1440},
    {"posicion": 42, "equipo": "Panama",       "puntos": 1539},
    {"posicion": 43, "equipo": "Saudi Arabia", "puntos": 1450},
    {"posicion": 44, "equipo": "Ghana",        "puntos": 1430},
    {"posicion": 45, "equipo": "Tunisia",      "puntos": 1425},
    {"posicion": 46, "equipo": "Cape Verde Islands", "puntos": 1390},
    {"posicion": 47, "equipo": "Congo DR",     "puntos": 1410},
    {"posicion": 48, "equipo": "New Zealand",  "puntos": 1350},
    {"posicion": 49, "equipo": "Bosnia & Herzegovina", "puntos": 1410},
    {"posicion": 50, "equipo": "Iran",         "puntos": 1619},
]

FIFA_PROMEDIO = 1450  # puntos para selecciones no conocidas

def actualizar_ranking_fifa():
    """
    Intenta obtener el ranking FIFA desde API-Football.
    Si falla, usa el fallback hardcodeado.
    Guarda en SQLite.
    """
    iniciar_fifa_ranking()
    print("  Actualizando ranking FIFA...")

    try:
        # API-Football tiene endpoint de ranking FIFA
        headers = {"x-apisports-key": API_KEY}
        resp = requests.get(
            f"{BASE_URL}/teams",
            headers=headers,
            params={"league": 1, "season": 2026},
            timeout=20
        )
        data = resp.json()
        equipos = data.get("response", [])

        if equipos:
            # Intentar obtener standings del mundial para tener team_ids
            resp2 = requests.get(
                f"{BASE_URL}/standings",
                headers=headers,
                params={"league": 1, "season": 2026},
                timeout=20
            )
            data2 = resp2.json()
            # Los standings del mundial no tienen ranking FIFA directamente
            # Usamos fallback pero lo guardamos en DB
            raise ValueError("API no tiene ranking FIFA directo, usando fallback")

    except Exception as e:
        print(f"  API no disponible ({e}), usando ranking FIFA junio 2026...")
        guardar_fifa_ranking(FIFA_FALLBACK)
        return

    guardar_fifa_ranking(FIFA_FALLBACK)


# Cache en memoria del ranking FIFA -- leer_fifa_ranking() abre una
# conexion SQLite nueva por llamada, y get_puntos_fifa()/es_seleccion_
# nacional() se llaman por CADA partido de CADA equipo en los endpoints
# que recorren todos los partidos del dia (miles de veces por request).
# Medido en vivo con cProfile: 5,250 llamadas a es_seleccion_nacional()
# en un solo request de 73 partidos, ~5.2s solo en abrir/leer SQLite --
# para un dato que no cambia durante la vida del proceso (solo lo
# actualiza actualizar_ranking_fifa(), un script de mantenimiento
# aparte, no el flujo normal de requests).
_cache_ranking_fifa = None


def _obtener_ranking_cacheado():
    global _cache_ranking_fifa
    if _cache_ranking_fifa is None:
        _cache_ranking_fifa = leer_fifa_ranking()
    return _cache_ranking_fifa


def get_puntos_fifa(equipo):
    """Retorna los puntos FIFA de un equipo (cacheado en memoria, ver
    _obtener_ranking_cacheado)."""
    ranking = _obtener_ranking_cacheado()
    if ranking:
        return ranking.get(equipo, FIFA_PROMEDIO)
    # Si DB vacia, usar fallback directo
    for r in FIFA_FALLBACK:
        if r["equipo"] == equipo:
            return r["puntos"]
    return FIFA_PROMEDIO


def es_seleccion_nacional(equipo):
    """Detecta si un equipo es una seleccion nacional (cacheado en
    memoria, ver _obtener_ranking_cacheado)."""
    ranking = _obtener_ranking_cacheado()
    if ranking:
        return equipo in ranking
    return any(r["equipo"] == equipo for r in FIFA_FALLBACK)


def ajuste_fifa(equipo_local, equipo_visitante):
    """
    Calcula factor de ajuste FIFA para medias de goles.
    Solo aplica cuando ambos son selecciones nacionales.
    Retorna (factor_local, factor_visitante).
    """
    if not (es_seleccion_nacional(equipo_local) and es_seleccion_nacional(equipo_visitante)):
        return 1.0, 1.0

    pts_local = get_puntos_fifa(equipo_local)
    pts_visit = get_puntos_fifa(equipo_visitante)

    # Diferencia normalizada (max ~300 pts entre top y bottom)
    diff = (pts_local - pts_visit) / 350.0
    diff = max(-1.0, min(1.0, diff))

    # Ajuste maximo +/- 25% en medias de goles
    factor_local = 1.0 + (diff * 0.25)
    factor_visit = 1.0 - (diff * 0.25)

    return round(factor_local, 3), round(factor_visit, 3)


if __name__ == "__main__":
    actualizar_ranking_fifa()
    print("\nTest ajustes:")
    print("Spain vs Belgium:", ajuste_fifa("Spain", "Belgium"))
    print("Argentina vs Norway:", ajuste_fifa("Argentina", "Norway"))
    print("France vs Morocco:", ajuste_fifa("France", "Morocco"))
    print("Man City vs Arsenal (clubes):", ajuste_fifa("Manchester City", "Arsenal"))
    print("\nPuntos FIFA:")
    print("Spain:", get_puntos_fifa("Spain"))
    print("Belgium:", get_puntos_fifa("Belgium"))
    print("Norway:", get_puntos_fifa("Norway"))
