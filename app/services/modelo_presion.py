import time

import pandas as pd

# Cache en memoria con TTL para la tabla de posiciones por liga -- se
# llama una vez por PARTIDO (simular() la pide para calcular presion/
# agresividad), pero la tabla es la misma para todos los partidos de
# la misma liga el mismo dia. Medido en vivo con cProfile: 66 llamadas
# en un request de 73 partidos, 4.71s acumulados recalculando la misma
# tabla una y otra vez. Mismo TTL (5 min) que el cache de partidos_hoy/
# top_picks en futbol_service.py -- el CSV que alimenta esto solo se
# actualiza una vez al dia via el cron, asi que no se pierde frescura
# real.
_CACHE_TABLA_TTL_SEGUNDOS = 300
_cache_tablas = {}


def calcular_tabla(df, liga_nombre, temporada_desde=None):
    clave = (liga_nombre, temporada_desde)
    ahora = time.time()
    cacheada = _cache_tablas.get(clave)
    if cacheada is not None and (ahora - cacheada["timestamp"]) < _CACHE_TABLA_TTL_SEGUNDOS:
        return cacheada["tabla"]
    tabla = _calcular_tabla_real(df, liga_nombre, temporada_desde)
    _cache_tablas[clave] = {"tabla": tabla, "timestamp": ahora}
    return tabla


def _calcular_tabla_real(df, liga_nombre, temporada_desde=None):
    """Calcula la tabla de posiciones de una liga sumando resultados FT del CSV."""
    sub = df[(df["liga"] == liga_nombre) & (df["estado"].isin(["FT", "AET", "PEN"]))].copy()
    if temporada_desde:
        sub = sub[sub["fecha"] >= temporada_desde]

    equipos = {}
    for _, row in sub.iterrows():
        local, visitante = row["equipo_local"], row["equipo_visitante"]
        gl, gv = row["goles_local"], row["goles_visitante"]

        for eq in (local, visitante):
            if eq not in equipos:
                equipos[eq] = {"PJ": 0, "PG": 0, "PE": 0, "PP": 0, "GF": 0, "GC": 0, "PTS": 0}

        equipos[local]["PJ"] += 1
        equipos[visitante]["PJ"] += 1
        equipos[local]["GF"] += gl
        equipos[local]["GC"] += gv
        equipos[visitante]["GF"] += gv
        equipos[visitante]["GC"] += gl

        if gl > gv:
            equipos[local]["PG"] += 1; equipos[local]["PTS"] += 3
            equipos[visitante]["PP"] += 1
        elif gl < gv:
            equipos[visitante]["PG"] += 1; equipos[visitante]["PTS"] += 3
            equipos[local]["PP"] += 1
        else:
            equipos[local]["PE"] += 1; equipos[local]["PTS"] += 1
            equipos[visitante]["PE"] += 1; equipos[visitante]["PTS"] += 1

    tabla = pd.DataFrame.from_dict(equipos, orient="index")
    tabla["DIF"] = tabla["GF"] - tabla["GC"]
    tabla = tabla.sort_values(["PTS", "DIF", "GF"], ascending=False)
    tabla["POS"] = range(1, len(tabla) + 1)
    return tabla


def calcular_presion(tabla, equipo, zona_descenso=4, zona_clasificacion=6):
    """Devuelve un nivel de presion 0-1 segun que tan cerca esta el equipo
    de la zona de descenso o de clasificacion internacional/titulo.
    Zonas configurables porque varian por liga y numero de equipos."""
    if equipo not in tabla.index:
        return 0.0

    pos = tabla.loc[equipo, "POS"]
    total_equipos = len(tabla)

    dist_descenso = abs(pos - (total_equipos - zona_descenso))
    dist_clasificacion = abs(pos - zona_clasificacion)

    dist_minima = min(dist_descenso, dist_clasificacion)

    if dist_minima <= 2:
        return 1.0
    elif dist_minima <= 4:
        return 0.6
    elif dist_minima <= 6:
        return 0.3
    else:
        return 0.0


def calcular_indice_agresividad(df, equipo, liga_nombre, ultimos_n=10):
    """Calcula un indice de agresividad 0-1 basado en tarjetas amarillas
    de los ultimos N partidos jugados del equipo (unico dato con cobertura completa;
    faltas y tarjetas rojas quedan pendientes de mejor cobertura de datos)."""
    mask = ((df["equipo_local"] == equipo) | (df["equipo_visitante"] == equipo)) & \
           (df["liga"] == liga_nombre) & (df["estado"].isin(["FT", "AET", "PEN"]))
    partidos = df[mask].sort_values("fecha", ascending=False).head(ultimos_n)

    if partidos.empty:
        return 0.0, {}

    tarjetas_totales = []
    for _, row in partidos.iterrows():
        es_local = row["equipo_local"] == equipo
        tarjetas = row["tarjetas_local"] if es_local else row["tarjetas_visitante"]
        if pd.notna(tarjetas):
            tarjetas_totales.append(tarjetas)

    prom_tarjetas = sum(tarjetas_totales) / len(tarjetas_totales) if tarjetas_totales else 0
    indice = min(prom_tarjetas / 3, 1.0)

    detalle = {
        "partidos_analizados": len(partidos),
        "prom_tarjetas": round(prom_tarjetas, 1),
    }
    return round(indice, 2), detalle


# Lista de clasicos/derbis mas conocidos de Sudamerica y Mexico.
# Cada tupla es (equipo1, equipo2) sin importar el orden local/visitante.
CLASICOS = [
    # Argentina (5)
    ("Boca Juniors", "River Plate"),
    ("Independiente", "Racing Club"),
    ("San Lorenzo", "Huracan"),
    ("Estudiantes L.P.", "Gimnasia L.P."),
    ("Newells Old Boys", "Rosario Central"),

    # Colombia (5)
    ("Millonarios", "Independiente Santa Fe"),
    ("America de Cali", "Deportivo Cali"),
    ("Atletico Nacional", "Independiente Medellin"),
    ("Junior", "Atletico Bucaramanga"),
    ("Once Caldas", "Deportes Tolima"),

    # Brasil (5)
    ("Flamengo", "Fluminense"),
    ("Flamengo", "Corinthians"),
    ("Corinthians", "Palmeiras"),
    ("Sao Paulo", "Corinthians"),
    ("Gremio", "Internacional"),

    # Uruguay (2)
    ("Club Nacional", "Penarol"),
    ("Progreso", "Fenix"),

    # Peru (4)
    ("Alianza Lima", "Universitario"),
    ("Sporting Cristal", "Universitario"),
    ("Sporting Cristal", "Alianza Lima"),
    ("Cienciano", "FBC Melgar"),

    # Ecuador (4)
    ("Barcelona SC", "Emelec"),
    ("Liga de Quito", "Universidad Catolica"),
    ("Barcelona SC", "Liga de Quito"),
    ("El Nacional", "Deportivo Quito"),

    # Chile (4)
    ("Colo Colo", "Universidad de Chile"),
    ("Universidad de Chile", "Universidad Catolica"),
    ("Colo Colo", "Universidad Catolica"),
    ("Santiago Wanderers", "Everton de Vina"),

    # Bolivia (3)
    ("The Strongest", "Bolivar"),
    ("Wilstermann", "Aurora"),
    ("Oriente Petrolero", "Blooming"),

    # Paraguay (3)
    ("Cerro Porteno", "Olimpia"),
    ("Guarani", "Libertad"),
    ("Nacional", "Sportivo Luqueno"),

    # Venezuela (3)
    ("Caracas", "Deportivo Tachira"),
    ("Estudiantes de Merida", "Deportivo Tachira"),
    ("Zamora", "Portuguesa"),

    # Mexico (5)
    ("America", "Chivas"),
    ("America", "Cruz Azul"),
    ("Pumas", "America"),
    ("Cruz Azul", "Chivas"),
    ("Monterrey", "Tigres UANL"),
]


def es_clasico(equipo1, equipo2):
    """Devuelve True si el partido entre estos dos equipos es un clasico/derbi conocido."""
    par = frozenset([equipo1, equipo2])
    return any(frozenset([a, b]) == par for a, b in CLASICOS)


def calcular_indice_intensidad_ofensiva(df, equipo, liga_nombre, ultimos_n=10):
    """Calcula un indice 0-1 de intensidad ofensiva basado en tiros totales
    de los ultimos N partidos jugados del equipo. Un equipo con mas tiros
    totales tiende a generar mas corners (rebotes, despejes, presion)."""
    mask = ((df["equipo_local"] == equipo) | (df["equipo_visitante"] == equipo)) & \
           (df["liga"] == liga_nombre) & (df["estado"].isin(["FT", "AET", "PEN"]))
    partidos = df[mask].sort_values("fecha", ascending=False).head(ultimos_n)

    if partidos.empty:
        return 0.5, {}  # neutral si no hay datos

    tiros_totales_lista = []
    for _, row in partidos.iterrows():
        es_local = row["equipo_local"] == equipo
        tiros = row["tiros_total_local"] if es_local else row["tiros_total_visitante"]
        if pd.notna(tiros):
            tiros_totales_lista.append(tiros)

    if not tiros_totales_lista:
        return 0.5, {}

    prom_tiros = sum(tiros_totales_lista) / len(tiros_totales_lista)

    # Normalizar: 8 tiros/partido = bajo (0.2), 20+ tiros/partido = muy alto (1.0)
    indice = max(0.0, min(1.0, (prom_tiros - 8) / 12))

    detalle = {
        "partidos_analizados": len(partidos),
        "prom_tiros_totales": round(prom_tiros, 1),
    }
    return round(indice, 2), detalle
