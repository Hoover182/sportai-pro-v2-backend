def _safe(v):
    try:
        f = float(v)
        return 0.0 if f != f else round(f, 2)
    except:
        return 0.0

import os
JUGADORES_DATA_DIR = os.path.join(os.path.dirname(__file__), "jugadores_data")
import sys
import json
import time
import pandas as pd
from datetime import datetime

# Cache en memoria con TTL para los endpoints que recorren TODOS los
# partidos del dia llamando a simular() uno por uno (Monte Carlo +
# Dixon-Coles + xG + ajuste de liga por cada partido) -- sin esto, cada
# request recalculaba de cero para los ~70+ partidos del dia, bloqueando
# el unico worker de Uvicorn (uvicorn corre sin --workers) el tiempo
# suficiente como para que Render matara la instancia pensando que no
# respondia. 5 minutos de TTL: nuevos partidos/resultados tardan como
# maximo eso en reflejarse, imperceptible para el usuario.
_CACHE_TTL_SEGUNDOS = 300
_cache_resultados = {}


def _obtener_o_calcular_cacheado(clave, fn_calculo):
    ahora = time.time()
    cacheado = _cache_resultados.get(clave)
    if cacheado is not None and (ahora - cacheado["timestamp"]) < _CACHE_TTL_SEGUNDOS:
        return cacheado["data"]
    resultado = fn_calculo()
    _cache_resultados[clave] = {"data": resultado, "timestamp": ahora}
    return resultado

# Apuntar al CSV correcto
CSV_PATH = os.path.join(os.path.dirname(__file__), "futbol_partidos.csv")

# Agregar services al path para imports
sys.path.insert(0, os.path.dirname(__file__))

from data_loader import (
    cargar_partidos_csv as _cargar_csv,
    obtener_equipo_por_nombre,
    filtrar_ligas_validas,
    obtener_partidos_hoy_futbol,
    obtener_partidos_mas_recientes,
    obtener_partidos_rango_futbol,
    _cargar_ligas_auto_detectadas,
)
from football_model import (
    estadisticas_equipo_ultimos10,
    ultimos_enfrentamientos_directos,
    ajustar_medias_con_rival,
    obtener_partidos_equipo,
    obtener_liga_partido,
    n_efectivo_estimacion,
)
from simulator import simular_partido_futbol, probabilidad_linea_personalizada, tarjetas_esperadas_por_parejez, _muestrear_conteo
from value_bet import edge_ratio
from elo_ranking import cargar_elo_ratings, peso_elo_confianza
import numpy as np

LIGAS_IDS = {
    "Champions League": (2, None),
    "Europa League": (3, None),
    "Conference League": (848, None),
    "Premier League": (39, None),
    "La Liga": (140, None),
    "Serie A": (135, None),
    "Bundesliga": (78, None),
    "Ligue 1": (61, None),
    "Primeira Liga": (94, None),
    "Eredivisie": (88, None),
    "MLS": (253, 2026),
    "Liga MX": (262, None),
    "Copa Libertadores": (13, 2026),
    "Copa Sudamericana": (11, 2026),
    "Liga Profesional Argentina": (128, 2026),
    "Brasileirao": (71, 2026),
    "Liga Colombia": (239, 2026),
    "Liga Pro Ecuador": (242, 2026),
    "Primera Division Chile": (265, 2026),
    "Primera Division Uruguay": (268, 2026),
    "Primera Division Peru": (281, 2026),
    "Primera Division Venezuela": (337, 2026),
    "Primera Division Bolivia": (344, 2026),
    "Division Profesional Paraguay": (250, 2026),
    "Liga MX": (262, None),
    "MLS": (253, 2026),
    "Copa Argentina": (130, 2026),
    "Copa Chile": (267, 2026),
    "Copa Colombia": (241, 2026),
    "Copa Uruguay": (270, 2026),
    "Copa do Brasil": (73, 2026),
    "Recopa Sudamericana": (12, 2026),
    "Mundial 2026": (1, 2026),
}

ORDEN_COMPETENCIAS = [
    "Champions League", "Europa League", "Conference League",
    "Premier League", "La Liga", "Serie A", "Bundesliga", "Ligue 1",
    "Primeira Liga", "Eredivisie", "MLS", "Liga MX",
    "Copa Libertadores", "Copa Sudamericana",
    "Liga Profesional Argentina", "Brasileirao",
    "Liga Colombia", "Liga Pro Ecuador",
]

OPUESTOS = {
    "Over 1.5 goles": "Under 1.5 goles", "Under 1.5 goles": "Over 1.5 goles",
    "Over 2.5 goles": "Under 2.5 goles", "Under 2.5 goles": "Over 2.5 goles",
    "Over 3.5 goles": "Under 3.5 goles", "Under 3.5 goles": "Over 3.5 goles",
    "Over 7.5 corners": "Under 7.5 corners", "Under 7.5 corners": "Over 7.5 corners",
    "Over 8.5 corners": "Under 8.5 corners", "Under 8.5 corners": "Over 8.5 corners",
    "Over 9.5 corners": "Under 9.5 corners", "Under 9.5 corners": "Over 9.5 corners",
    "Over 2.5 tarjetas": "Under 2.5 tarjetas", "Under 2.5 tarjetas": "Over 2.5 tarjetas",
    "Over 3.5 tarjetas": "Under 3.5 tarjetas", "Under 3.5 tarjetas": "Over 3.5 tarjetas",
    "Gana local": "Gana visitante", "Gana visitante": "Gana local",
}


LIGAS_NIVEL_1 = [
    "Premier League", "La Liga", "Serie A", "Bundesliga", "Ligue 1", "Primeira Liga",
    "Eredivisie", "Pro League Belgica", "Premier League Egipto", "Pro League Arabia",
    "Super Lig Turquia", "Liga Profesional Argentina", "Brasileirao", "Liga Colombia",
    "Primera Division Chile", "Primera Division Uruguay", "Primera Division Peru",
    "Liga Pro Ecuador", "Primera Division Venezuela", "Primera Division Bolivia",
    "Division Profesional Paraguay", "Liga MX", "MLS",
]

_cache_equipos_nivel1 = None

def obtener_equipos_nivel1(df):
    """Devuelve el set de equipos que juegan en ligas de Primera division.
    Incluye tanto LIGAS_NIVEL_1 (lista fija) como las ligas auto-detectadas
    por el backfill de equipos desconocidos en copas internacionales (ver
    ligas_auto_detectadas.json) -- mismo criterio de union que ya usa
    filtrar_ligas_validas() en data_loader.py, sin duplicar logica. Se
    cachea en memoria porque el CSV no cambia dentro del mismo proceso."""
    global _cache_equipos_nivel1
    if _cache_equipos_nivel1 is not None:
        return _cache_equipos_nivel1
    ligas_n1 = set(LIGAS_NIVEL_1) | set(_cargar_ligas_auto_detectadas().values())
    equipos = set()
    for liga in ligas_n1:
        sub = df[df["liga"] == liga]
        equipos.update(sub["equipo_local"].unique())
        equipos.update(sub["equipo_visitante"].unique())
    _cache_equipos_nivel1 = equipos
    return equipos


import unicodedata

_cache_equipos_todos = None


def _normalizar_nombre(nombre):
    """Quita tildes y pasa a minusculas para comparacion tolerante."""
    sin_tildes = unicodedata.normalize('NFKD', nombre).encode('ascii', 'ignore').decode('ascii')
    return sin_tildes.lower().strip()


def resolver_nombre_equipo(df, nombre_input):
    """Resuelve un nombre de equipo (posiblemente sin tilde o con mayusculas
    distintas) al nombre exacto tal como esta guardado en el CSV.
    Devuelve (nombre_resuelto, hubo_correccion_aproximada).
    Si no encuentra nada ni por aproximacion, devuelve (nombre_input, False)."""
    global _cache_equipos_todos
    if _cache_equipos_todos is None:
        equipos = set(df["equipo_local"].dropna().unique()) | set(df["equipo_visitante"].dropna().unique())
        _cache_equipos_todos = {_normalizar_nombre(eq): eq for eq in equipos}

    nombre_normalizado = _normalizar_nombre(nombre_input)
    exacto = _cache_equipos_todos.get(nombre_normalizado)

    # El match "exacto" es TOTALMENTE confiable cuando el input ya
    # coincide letra por letra (salvo mayusculas) con el nombre real --
    # ahi no hay nada que revisar. El caso riesgoso es cuando ese match
    # solo existe porque sacar tildes/diacriticos igualo dos nombres que
    # en realidad tienen letras distintas -- ej. "Velez" (arg.) normaliza
    # igual que "Velež" (con ž, club bosnio NK Velez Mostar), porque
    # _normalizar_nombre() borra la "ž" igual que borraria un acento
    # comun, aunque el input nunca tuvo esa letra.
    exacto_sin_normalizar = exacto is not None and exacto.lower() == nombre_input.lower()

    if exacto is not None and not exacto_sin_normalizar:
        # Coincidencia por PREFIJO de palabra completa (ej. "Velez" ->
        # "Velez Sarsfield") tiene prioridad sobre esa clase de match
        # "exacto" fragil -- es la forma coloquial habitual de acortar
        # un nombre oficial (se suele decir "Velez" en vez de "Velez
        # Sarsfield", igual que "Racing" por "Racing Club"), mas
        # confiable que una coincidencia cruzada entre paises que solo
        # aparece por normalizar. Solo se aplica si el candidato por
        # prefijo es UNICO -- si hay mas de uno (ej. "Racing" matchea a
        # "Racing Club", "Racing Montevideo" Y "Racing Santander" a la
        # vez) la ambiguedad real no se resuelve aca, cae al match
        # exacto de siempre.
        candidatos_prefijo = sorted({
            nombre for clave, nombre in _cache_equipos_todos.items()
            if clave.startswith(nombre_normalizado + " ")
        })
        if len(candidatos_prefijo) == 1:
            return candidatos_prefijo[0], True

    if exacto is not None:
        return exacto, False

    from difflib import get_close_matches
    candidatos = get_close_matches(nombre_normalizado, _cache_equipos_todos.keys(), n=1, cutoff=0.80)
    if candidatos:
        nombre_resuelto = _cache_equipos_todos[candidatos[0]]
        return nombre_resuelto, True

    return nombre_input, False


def categoria_equipo(nombre, equipos_nivel1):
    """Devuelve 'Primera' si el equipo juega habitualmente en una liga top,
    o 'Categoria menor' si solo aparece en copas (posible Segunda/Tercera/amateur)."""
    return "Primera" if nombre in equipos_nivel1 else "Categoria menor"


def cargar_df():
    import os
    original = os.getcwd()
    os.chdir(os.path.dirname(__file__))
    df = _cargar_csv()
    os.chdir(original)
    if not df.empty:
        df = filtrar_ligas_validas(df)
    return df


def get_temporada(liga_nombre):
    hoy = datetime.now()
    temporada_europea = hoy.year if hoy.month >= 8 else hoy.year - 1
    if liga_nombre in LIGAS_IDS:
        liga_id, temporada_fija = LIGAS_IDS[liga_nombre]
        temporada = temporada_fija if temporada_fija else temporada_europea
        return liga_id, temporada
    return None, temporada_europea


def simular(df, local, visitante):
    local_resuelto, corr_local = resolver_nombre_equipo(df, local)
    visitante_resuelto, corr_visitante = resolver_nombre_equipo(df, visitante)
    if corr_local:
        print(f"AVISO: '{local}' no coincide exacto, usando '{local_resuelto}' (correccion aproximada)")
    if corr_visitante:
        print(f"AVISO: '{visitante}' no coincide exacto, usando '{visitante_resuelto}' (correccion aproximada)")
    local, visitante = local_resuelto, visitante_resuelto

    # Semilla fija por partido+fecha, para que la simulacion de Poisson
    # de el mismo resultado sin importar cuantas veces se llame a simular()
    # el mismo dia (evita que la lista de partidos y el detalle del
    # partido muestren porcentajes ligeramente distintos entre si).
    # Usa hashlib en vez de hash() nativo porque hash() de strings no es
    # determinista entre reinicios del proceso (Render duerme por inactividad).
    try:
        import numpy as np
        import hashlib
        partido_pendiente = df[
            (df["equipo_local"] == local) & (df["equipo_visitante"] == visitante) &
            (df["estado"] == "NS")
        ]
        if not partido_pendiente.empty:
            fecha_partido = str(partido_pendiente.iloc[0]["fecha"])[:10]
        else:
            fecha_partido = "sin-fecha"
        texto_semilla = local + "|" + visitante + "|" + fecha_partido
        hash_bytes = hashlib.md5(texto_semilla.encode("utf-8")).digest()
        semilla = int.from_bytes(hash_bytes[:4], byteorder="big") % (2**31)
        np.random.seed(semilla)
    except Exception:
        pass

    # Liga del partido que se esta analizando (partido programado > liga
    # domestica mas frecuente del equipo > ultimo jugado como ultimo
    # recurso -- ver obtener_liga_partido). Se calcula una sola vez y se
    # comparte con las stats de ambos equipos (incluida la ventana por
    # condicion local/visitante, que la usa para no mezclar copas u
    # otra division) y con los filtros de presion/agresividad, en vez
    # de adivinar la liga por separado con la primera fila que aparezca
    # para el equipo local (podia no ser su liga domestica actual).
    liga_partido = obtener_liga_partido(df, local, visitante)

    stats_a = estadisticas_equipo_ultimos10(df, local, liga=liga_partido, condicion="local")
    stats_b = estadisticas_equipo_ultimos10(df, visitante, liga=liga_partido, condicion="visitante")
    if stats_a is None or stats_b is None:
        return None, None, None
    h2h = ultimos_enfrentamientos_directos(df, local, visitante, n=5)

    # ---- Filtros adicionales de tarjetas (arbitro, presion, agresividad, clasico) ----
    try:
        from modelo_presion import calcular_tabla, calcular_presion, calcular_indice_agresividad, es_clasico
        tabla_liga = calcular_tabla(df, liga_partido)

        presion_local = calcular_presion(tabla_liga, local)
        presion_visitante = calcular_presion(tabla_liga, visitante)
        presion_promedio = (presion_local + presion_visitante) / 2

        agresividad_local, _ = calcular_indice_agresividad(df, local, liga_partido)
        agresividad_visitante, _ = calcular_indice_agresividad(df, visitante, liga_partido)
        agresividad_promedio = (agresividad_local + agresividad_visitante) / 2

        clasico = es_clasico(local, visitante)

        # Multiplicador combinado: base 1.0, cada factor puede sumar hasta +25%
        multiplicador_tarjetas = 1.0
        multiplicador_tarjetas += presion_promedio * 0.15
        multiplicador_tarjetas += agresividad_promedio * 0.10
        # NOTA: peso de clasico calibrado para futbol sudamericano (mas fisico).
        # Si se agregan ligas europeas, este peso deberia ser mas bajo alli,
        # ya que los derbis europeos tienden a menos tarjetas que los sudamericanos.
        if clasico:
            multiplicador_tarjetas += 0.35
        multiplicador_tarjetas = min(multiplicador_tarjetas, 1.5)

        # ---- Multiplicador de corners basado en intensidad ofensiva reciente ----
        from modelo_presion import calcular_indice_intensidad_ofensiva
        intensidad_local, _ = calcular_indice_intensidad_ofensiva(df, local, liga_partido)
        intensidad_visitante, _ = calcular_indice_intensidad_ofensiva(df, visitante, liga_partido)
        intensidad_promedio = (intensidad_local + intensidad_visitante) / 2
        # Base 1.0, hasta +/-20% segun que tan ofensivos vienen ambos equipos
        multiplicador_corners = 0.9 + (intensidad_promedio * 0.3)
        multiplicador_corners = max(0.8, min(multiplicador_corners, 1.3))

        # ---- Multiplicador de goles basado en intensidad ofensiva individual ----
        # A diferencia de corners/tarjetas (ajuste combinado), goles se ajusta
        # por equipo por separado, porque afecta goles_a y goles_b antes de
        # simular_partido_futbol(), propagandose de forma coherente a 1X2,
        # handicap y ambos marcan. Rango mas angosto que corners (+/-10-15%
        # vs +/-20%) porque un mismo % mueve mas la linea con una media base
        # mas baja (~2.5 goles totales vs ~9-10 corners totales).
        multiplicador_goles_local = 0.95 + (intensidad_local * 0.10)
        multiplicador_goles_local = max(0.9, min(multiplicador_goles_local, 1.15))
        multiplicador_goles_visitante = 0.95 + (intensidad_visitante * 0.10)
        multiplicador_goles_visitante = max(0.9, min(multiplicador_goles_visitante, 1.15))
    except Exception:
        multiplicador_tarjetas = 1.0
        multiplicador_corners = 1.0
        multiplicador_goles_local = 1.0
        multiplicador_goles_visitante = 1.0
    goles_a, goles_b, corners_a, corners_b, tarjetas = ajustar_medias_con_rival(
        stats_a, stats_b, h2h, equipo_local=local, equipo_visitante=visitante
    )
    goles_a = goles_a * multiplicador_goles_local
    goles_b = goles_b * multiplicador_goles_visitante

    # Confianza (k) en cada promedio para la mezcla Gamma-Poisson -- ver
    # n_efectivo_estimacion() y la conversacion de calibracion. Goles usa
    # n_partidos/n_partidos_condicion (siempre disponibles); corners/
    # tarjetas usan n_partidos_stats/n_partidos_condicion (solo partidos
    # con esos datos reales). Tarjetas es un unico total combinado, asi
    # que usa la muestra mas chica de los dos equipos (el eslabon mas
    # debil determina cuanto ensanchar).
    k_goles_a = n_efectivo_estimacion(stats_a["n_partidos"], stats_a["n_partidos_condicion"])
    k_goles_b = n_efectivo_estimacion(stats_b["n_partidos"], stats_b["n_partidos_condicion"])
    k_corners_a = n_efectivo_estimacion(stats_a["n_partidos_stats"], stats_a["n_partidos_condicion"])
    k_corners_b = n_efectivo_estimacion(stats_b["n_partidos_stats"], stats_b["n_partidos_condicion"])
    k_tarjetas = min(k_corners_a, k_corners_b)

    # Elo casero -- SOLO influye en prob_local/prob_empate/prob_visitante
    # (ver elo_ranking.py y simular_partido_futbol). Si el equipo no tiene
    # rating todavia (archivo no generado, o equipo nunca visto), queda
    # en None y simular_partido_futbol() simplemente no aplica el ajuste.
    elo_ratings = cargar_elo_ratings()
    elo_local = elo_ratings.get(local, {}).get("rating")
    elo_visitante = elo_ratings.get(visitante, {}).get("rating")
    peso_elo = peso_elo_confianza(
        elo_ratings.get(local, {}).get("n_partidos"),
        elo_ratings.get(visitante, {}).get("n_partidos"),
    )

    sim = simular_partido_futbol(
        goles_a, goles_b,
        stats_a["std_goles_favor"], stats_b["std_goles_favor"],
        corners_a, corners_b, tarjetas,
        k_goles_a=k_goles_a, k_goles_b=k_goles_b,
        k_corners_a=k_corners_a, k_corners_b=k_corners_b,
        k_tarjetas=k_tarjetas,
        elo_local=elo_local, elo_visitante=elo_visitante, peso_elo=peso_elo,
    )

    # Ajuste H2H directo para Ambos Marcan - el modelo derivado de Poisson
    # puede diferir bastante del patron real de este cruce especifico
    # (ej. equipos que historicamente no se hacen goles entre si aunque
    # sean ofensivos contra otros rivales). Mismo peso_h2h con antiguedad
    # que ya se usa para goles/corners/tarjetas.
    try:
        import numpy as np
        if not h2h.empty:
            n_h2h_am = len(h2h)
            peso_h2h_am = min(0.15 + (n_h2h_am - 1) * 0.05, 0.30)
            fecha_mas_reciente_am = pd.to_datetime(h2h["fecha"]).max()
            if fecha_mas_reciente_am.tzinfo is not None:
                ahora_am = pd.Timestamp.now(tz=fecha_mas_reciente_am.tzinfo)
            else:
                ahora_am = pd.Timestamp.now()
            anios_am = (ahora_am - fecha_mas_reciente_am).days / 365.25
            mult_antiguedad_am = np.interp(anios_am, [0, 1, 2, 3], [1.0, 0.9, 0.7, 0.5])
            peso_h2h_am = peso_h2h_am * mult_antiguedad_am

            h2h_goles = h2h[h2h["goles_local"].notna() & h2h["goles_visitante"].notna()]
            if not h2h_goles.empty:
                ambos_marcan_h2h = ((h2h_goles["goles_local"] > 0) & (h2h_goles["goles_visitante"] > 0)).mean()
                peso_base_am = 1 - peso_h2h_am
                sim["prob_ambos_marcan"] = sim["prob_ambos_marcan"] * peso_base_am + ambos_marcan_h2h * peso_h2h_am
    except Exception:
        pass

    # Aplicar el multiplicador de arbitro/presion/agresividad/clasico a las tarjetas
    if multiplicador_tarjetas != 1.0 and "tarjetas_totales_proj" in sim:
        sim["tarjetas_totales_proj"] = sim["tarjetas_totales_proj"] * multiplicador_tarjetas
        if "tarjetas_ou" in sim:
            media_ajustada = max(sim["tarjetas_totales_proj"], 0.1)
            # Mismo k_tarjetas que ya uso simular_partido_futbol() para
            # tarjetas_ou -- sin esto, este resampleo pisaba la mezcla
            # Gamma-Poisson con un Poisson puro, anulando la correccion
            # de calibracion en la enorme mayoria de partidos (el
            # multiplicador casi nunca da exactamente 1.0).
            valores_sim = _muestrear_conteo(media_ajustada, k_tarjetas, 10000)
            for linea_ou in list(sim["tarjetas_ou"].keys()):
                sim["tarjetas_ou"][linea_ou] = {
                    "over": float(np.mean(valores_sim > linea_ou)),
                    "under": float(np.mean(valores_sim < linea_ou)),
                }

    # Aplicar el multiplicador de intensidad ofensiva a los corners
    if multiplicador_corners != 1.0 and "corners_totales_proj" in sim:
        sim["corners_totales_proj"] = sim["corners_totales_proj"] * multiplicador_corners
        if "corners_ou" in sim:
            media_ajustada_c = max(sim["corners_totales_proj"], 0.1)
            # Mismo criterio que arriba -- k combinado (el mas chico de
            # los dos equipos) ya que este resampleo trabaja sobre el
            # total combinado, no por separado local/visitante.
            valores_sim_c = _muestrear_conteo(media_ajustada_c, min(k_corners_a, k_corners_b), 10000)
            for linea_ou in list(sim["corners_ou"].keys()):
                sim["corners_ou"][linea_ou] = {
                    "over": float(np.mean(valores_sim_c > linea_ou)),
                    "under": float(np.mean(valores_sim_c < linea_ou)),
                }

    return sim, stats_a, stats_b


CUOTAS_CACHE_PATH = os.path.join(os.path.dirname(__file__), "cuotas_cache.json")
_cache_cuotas = None


def _cargar_cuotas_cache():
    """Cuotas reales de Betano/1xBet por fixture_id, armadas por
    actualizar_cuotas_cache() en el cron (api_to_csv.py) -- nunca se
    llama a la API de cuotas en vivo desde un request de usuario. Cache
    en memoria sin TTL, mismo criterio que _cache_ranking_fifa/
    _cache_elo_ratings: el archivo solo cambia una vez al dia. Se usa
    SOLO como filtro de disponibilidad real en calcular_top3() (Regla 3),
    no para ordenar -- el criterio de orden sigue siendo probabilidad."""
    global _cache_cuotas
    if _cache_cuotas is not None:
        return _cache_cuotas
    if not os.path.exists(CUOTAS_CACHE_PATH):
        _cache_cuotas = {}
        return _cache_cuotas
    try:
        with open(CUOTAS_CACHE_PATH, "r", encoding="utf-8") as f:
            _cache_cuotas = json.load(f)
    except Exception:
        _cache_cuotas = {}
    return _cache_cuotas


def _obtener_fixture_id_pendiente(df, local, visitante):
    """Fixture_id del proximo partido NS entre estos dos equipos (o el mas
    reciente si no hay ninguno pendiente) -- mismo criterio de preferencia
    que _obtener_ajuste_ia(), para buscar la cuota real del partido que se
    va a jugar, no de un cruce historico viejo."""
    try:
        fila = df[(df["equipo_local"] == local) & (df["equipo_visitante"] == visitante)]
        if fila.empty:
            return None
        pendientes = fila[fila["estado"] == "NS"]
        fila_ordenada = (pendientes if not pendientes.empty else fila).sort_values("fecha", ascending=False)
        fid = fila_ordenada.iloc[0].get("fixture_id")
        return int(fid) if pd.notna(fid) else None
    except Exception:
        return None


def _familia_mercado(nombre):
    """Familia del mercado para evitar mostrar la misma apuesta de fondo
    dos veces en el Top3 con distinta linea (ej. 'Over 1.5 tarjetas' y
    'Over 2.5 tarjetas' son la misma apuesta con distinto numero, no dos
    picks distintos). Los mercados Over/Under comparten familia por la
    palabra final del nombre (goles/corners/tarjetas); el resto de los
    mercados (resultado, doble oportunidad, ambos marcan) no se agrupan
    entre si -- cada uno ya es una apuesta genuinamente distinta, no una
    linea distinta de la misma apuesta."""
    partes = nombre.split()
    if partes and partes[0] in ("Over", "Under"):
        return partes[-1]
    return nombre


CUOTA_MINIMA_DISPONIBILIDAD = 1.15  # por debajo de esto, "practicamente
                                     # sin pago" -- se descarta igual que
                                     # si no hubiera cuota


def calcular_top3(sim, fixture_id, stats_a=None, stats_b=None):
    """Top3 por PROBABILIDAD del modelo (el criterio de siempre, no edge/
    valor -- se probo el sistema por edge y no convencio, ver
    conversacion). Tres reglas sobre la lista ordenada por probabilidad:

    1. Orden por probabilidad descendente (igual que siempre).
    2. Sin mercados repetidos: ademas del opuesto exacto en la misma
       linea (OPUESTOS, ej. no 'Over 2.5 goles' si ya esta 'Under 2.5
       goles'), tampoco se repite la FAMILIA de mercado con otra linea
       (ver _familia_mercado()) -- 'Over 1.5 tarjetas' y 'Over 2.5
       tarjetas' son la misma apuesta de fondo, no pueden entrar juntas.
    3. Verificacion de disponibilidad real: un candidato solo entra si
       Betano o 1xBet tienen esa linea especifica con cuota >=
       CUOTA_MINIMA_DISPONIBILIDAD (via cuotas_cache.json, armado por el
       cron -- nunca se llama a la API en vivo aca). Si no hay cuota o es
       menor al piso, se SALTA ese candidato y se sigue bajando por
       probabilidad -- IMPORTANTE: un candidato saltado por esta regla
       NO marca su familia como usada, porque nunca llego a entrar al
       resultado (si "Over 2.5 tarjetas" se salta por falta de cuota,
       "Over 3.5 tarjetas" todavia puede entrar despues si tiene cuota
       real). Si ningun candidato de un partido pasa las 3 reglas, mismo
       fallback de siempre: menos de 3 picks, o ninguno."""
    stats_ok = (
        stats_a and stats_b and
        stats_a.get("n_partidos_stats", 0) >= 3 and
        stats_b.get("n_partidos_stats", 0) >= 3
    )
    candidatos = [
        ("Gana local", sim["prob_local"]),
        ("Empate", sim["prob_empate"]),
        ("Gana visitante", sim["prob_visitante"]),
        ("1X (Local o Empate)", sim["prob_1x"]),
        ("X2 (Empate o Visitante)", sim["prob_x2"]),
        ("Ambos marcan", sim["prob_ambos_marcan"]),
        ("Over 1.5 goles", sim["goles_ou"][1.5]["over"]),
        ("Under 1.5 goles", sim["goles_ou"][1.5]["under"]),
        ("Over 2.5 goles", sim["goles_ou"][2.5]["over"]),
        ("Under 2.5 goles", sim["goles_ou"][2.5]["under"]),
        ("Over 3.5 goles", sim["goles_ou"][3.5]["over"]),
        ("Under 3.5 goles", sim["goles_ou"][3.5]["under"]),
    ]
    if stats_ok:
        candidatos += [
            ("Over 7.5 corners", sim["corners_ou"][7.5]["over"]),
            ("Under 7.5 corners", sim["corners_ou"][7.5]["under"]),
            ("Over 8.5 corners", sim["corners_ou"][8.5]["over"]),
            ("Under 8.5 corners", sim["corners_ou"][8.5]["under"]),
            ("Over 2.5 tarjetas", sim["tarjetas_ou"][2.5]["over"]),
            ("Under 2.5 tarjetas", sim["tarjetas_ou"][2.5]["under"]),
            ("Over 3.5 tarjetas", sim["tarjetas_ou"][3.5]["over"]),
            ("Under 3.5 tarjetas", sim["tarjetas_ou"][3.5]["under"]),
        ]

    candidatos = sorted(candidatos, key=lambda x: x[1], reverse=True)

    # fixture_id puede llegar como numpy.float64 (columnas del CSV con NaN
    # en otro lado se vuelven float64 aunque este valor puntual sea un id
    # entero) -- str() directo da "1549744.0" y nunca matchea la clave
    # "1549744" del JSON. Normalizar a int primero.
    try:
        fixture_id_str = str(int(fixture_id)) if fixture_id is not None and pd.notna(fixture_id) else None
    except (TypeError, ValueError):
        fixture_id_str = None
    cuotas_partido = _cargar_cuotas_cache().get(fixture_id_str, {}) if fixture_id_str else {}

    resultado = []
    usados = set()
    familias_usadas = set()
    for nombre, prob in candidatos:
        if prob < 0.60:
            break
        familia = _familia_mercado(nombre)
        if nombre in usados or OPUESTOS.get(nombre) in usados or familia in familias_usadas:
            continue
        cuota = cuotas_partido.get(nombre)
        if not cuota or cuota < CUOTA_MINIMA_DISPONIBILIDAD:
            continue  # sin disponibilidad real -- se salta, la familia sigue libre
        resultado.append({"mercado": nombre, "prob": round(prob * 100, 1), "cuota": cuota})
        usados.add(nombre)
        familias_usadas.add(familia)
        if len(resultado) == 3:
            break
    return resultado


def get_partidos_hoy():
    return _obtener_o_calcular_cacheado("partidos_hoy", _calcular_partidos_hoy)


def _calcular_partidos_hoy():
    df = cargar_df()
    if df.empty:
        return []
    partidos = obtener_partidos_hoy_futbol(df)
    if partidos.empty:
        return []
    resultado = []
    ligas_en_datos = partidos["liga"].unique().tolist()
    ligas_ordenadas = [l for l in ORDEN_COMPETENCIAS if l in ligas_en_datos]
    ligas_ordenadas += [l for l in ligas_en_datos if l not in ORDEN_COMPETENCIAS]
    for liga in ligas_ordenadas:
        partidos_liga = partidos[partidos["liga"] == liga]
        for _, row in partidos_liga.iterrows():
            fecha = str(row["fecha"].date()) if hasattr(row["fecha"], "date") else str(row["fecha"])[:10]
            hora = str(row["fecha"].time())[:5] if hasattr(row["fecha"], "time") else ""
            local = row["equipo_local"]
            visitante = row["equipo_visitante"]
            prob_local = prob_empate = prob_visitante = None
            ajuste_ia = None
            try:
                sim, stats_a, stats_b = simular(df, local, visitante)
                if sim is not None:
                    prob_local = round(sim["prob_local"] * 100, 1)
                    prob_empate = round(sim["prob_empate"] * 100, 1)
                    prob_visitante = round(sim["prob_visitante"] * 100, 1)
                    ajuste_info = _obtener_ajuste_ia(df, local, visitante)
                    if ajuste_info:
                        aj_l = ajuste_info.get("ajuste_local", 0)
                        aj_v = ajuste_info.get("ajuste_visitante", 0)
                        pl = prob_local + aj_l
                        pv = prob_visitante + aj_v
                        pe = prob_empate
                        total = pl + pe + pv
                        if total > 0:
                            factor = 100 / total
                            pl, pe, pv = pl * factor, pe * factor, pv * factor
                        prob_local = round(max(1, min(98, pl)), 1)
                        prob_visitante = round(max(1, min(98, pv)), 1)
                        prob_empate = round(max(1, 100 - prob_local - prob_visitante), 1)
                        ajuste_ia = ajuste_info
            except Exception:
                pass

            resultado.append({
                "liga": liga,
                "local": local,
                "visitante": visitante,
                "fecha": fecha,
                "hora": hora,
                "prob_local": prob_local,
                "prob_empate": prob_empate,
                "prob_visitante": prob_visitante,
                "ajuste_ia": ajuste_ia,
            })
    return resultado


def get_partidos_rango(dias=4):
    return _obtener_o_calcular_cacheado(f"partidos_rango_{dias}", lambda: _calcular_partidos_rango(dias))


def _calcular_partidos_rango(dias=4):
    import pytz
    df = cargar_df()
    if df.empty:
        return []
    partidos = obtener_partidos_rango_futbol(df, dias=dias)
    if partidos.empty:
        return []

    hoy = pd.Timestamp.now(tz="America/Bogota").normalize()
    resultado = []
    ligas_en_datos = partidos["liga"].unique().tolist()
    ligas_ordenadas = [l for l in ORDEN_COMPETENCIAS if l in ligas_en_datos]
    ligas_ordenadas += [l for l in ligas_en_datos if l not in ORDEN_COMPETENCIAS]

    for liga in ligas_ordenadas:
        partidos_liga = partidos[partidos["liga"] == liga]
        for _, row in partidos_liga.iterrows():
            fecha_normalizada = row["fecha"].normalize() if hasattr(row["fecha"], "normalize") else None
            dia_offset = (fecha_normalizada - hoy).days if fecha_normalizada is not None else 0

            fecha = str(row["fecha"].date()) if hasattr(row["fecha"], "date") else str(row["fecha"])[:10]
            hora = str(row["fecha"].time())[:5] if hasattr(row["fecha"], "time") else ""
            local = row["equipo_local"]
            visitante = row["equipo_visitante"]
            prob_local = prob_empate = prob_visitante = None
            ajuste_ia = None
            try:
                sim, stats_a, stats_b = simular(df, local, visitante)
                if sim is not None:
                    prob_local = round(sim["prob_local"] * 100, 1)
                    prob_empate = round(sim["prob_empate"] * 100, 1)
                    prob_visitante = round(sim["prob_visitante"] * 100, 1)
                    ajuste_info = _obtener_ajuste_ia(df, local, visitante)
                    if ajuste_info:
                        aj_l = ajuste_info.get("ajuste_local", 0)
                        aj_v = ajuste_info.get("ajuste_visitante", 0)
                        pl = prob_local + aj_l
                        pv = prob_visitante + aj_v
                        pe = prob_empate
                        total = pl + pe + pv
                        if total > 0:
                            factor = 100 / total
                            pl, pe, pv = pl * factor, pe * factor, pv * factor
                        prob_local = round(max(1, min(98, pl)), 1)
                        prob_visitante = round(max(1, min(98, pv)), 1)
                        prob_empate = round(max(1, 100 - prob_local - prob_visitante), 1)
                        ajuste_ia = ajuste_info
            except Exception:
                pass

            resultado.append({
                "liga": liga,
                "local": local,
                "visitante": visitante,
                "fecha": fecha,
                "hora": hora,
                "dia_offset": dia_offset,
                "prob_local": prob_local,
                "prob_empate": prob_empate,
                "prob_visitante": prob_visitante,
                "ajuste_ia": ajuste_ia,
            })
    return resultado


def get_top_picks():
    return _obtener_o_calcular_cacheado("top_picks", _calcular_top_picks)


def _calcular_top_picks():
    df = cargar_df()
    if df.empty:
        return []
    partidos = obtener_partidos_hoy_futbol(df)
    if partidos.empty:
        partidos = obtener_partidos_mas_recientes(df, n=20)
    if partidos.empty:
        return []
    resultados = []
    for _, row in partidos.iterrows():
        local = row["equipo_local"]
        visitante = row["equipo_visitante"]
        liga = row["liga"]
        fixture_id = row.get("fixture_id")
        sim, stats_a, stats_b = simular(df, local, visitante)
        if sim is None:
            continue
        top3 = calcular_top3(sim, fixture_id, stats_a, stats_b)
        if not top3:
            continue
        for pick in top3:
            resultados.append({
                "liga": liga,
                "partido": f"{local} vs {visitante}",
                "mercado": pick["mercado"],
                "prob": pick["prob"],
            })
    resultados.sort(key=lambda x: x["prob"], reverse=True)
    return resultados


def _obtener_ajuste_ia(df, local, visitante):
    """Busca el ajuste cualitativo de IA para este partido si existe.
    Prioriza el partido mas reciente (o el pendiente NS) para evitar
    traer el ajuste de un enfrentamiento historico viejo entre los mismos equipos."""
    try:
        fila = df[(df["equipo_local"] == local) & (df["equipo_visitante"] == visitante)]
        if fila.empty:
            return None
        # Preferir partidos pendientes (NS), si no hay, tomar el mas reciente por fecha
        pendientes = fila[fila["estado"] == "NS"]
        if not pendientes.empty:
            fila_ordenada = pendientes.sort_values("fecha", ascending=False)
        else:
            fila_ordenada = fila.sort_values("fecha", ascending=False)
        r = fila_ordenada.iloc[0]
        if "ajuste_ia_local" not in r.index or pd.isna(r.get("ajuste_ia_local")):
            return None
        return {
            "ajuste_local": float(r["ajuste_ia_local"]),
            "ajuste_visitante": float(r["ajuste_ia_visitante"]),
            "explicacion": str(r["ajuste_ia_explicacion"]) if not pd.isna(r.get("ajuste_ia_explicacion")) else "",
        }
    except Exception:
        return None


def _calcular_goles_1t(df, local, visitante):
    """Calcula proyecciones y Over/Under del primer tiempo para el partido."""
    try:
        s_local = stats_goles_1t(df, local)
        s_visit = stats_goles_1t(df, visitante)
        if s_local is None or s_visit is None:
            return None
        # Media de goles 1T: ataque propio + defensa rival
        media_local = (s_local["goles_favor_1t"] + s_visit["goles_contra_1t"]) / 2
        media_visit = (s_visit["goles_favor_1t"] + s_local["goles_contra_1t"]) / 2
        sim_1t = simular_goles_1t(media_local, media_visit)
        return {
            "proj": f"{sim_1t['goles_local_proj_1t']:.2f} - {sim_1t['goles_visitante_proj_1t']:.2f}",
            "ou": sim_1t["ou"],
            "ambos_marcan_1t": sim_1t["ambos_marcan_1t"],
            "media_local_gf_1t": round(s_local["goles_favor_1t"], 2),
            "media_local_gc_1t": round(s_local["goles_contra_1t"], 2),
            "media_visit_gf_1t": round(s_visit["goles_favor_1t"], 2),
            "media_visit_gc_1t": round(s_visit["goles_contra_1t"], 2),
        }
    except Exception:
        return None


def stats_goles_1t(df, equipo, n=10):
    """Calcula el promedio de goles a favor y en contra en el primer tiempo."""
    import numpy as np
    from football_model import obtener_partidos_equipo
    partidos = obtener_partidos_equipo(df, equipo, n=n)
    gf_1t = []
    gc_1t = []
    for _, r in partidos.iterrows():
        if "goles_local_1t" not in r.index:
            continue
        if str(r["goles_local_1t"]) in ["nan", "None"]:
            continue
        es_local = r["equipo_local"] == equipo
        if es_local:
            gf = r["goles_local_1t"]
            gc = r["goles_visitante_1t"]
        else:
            gf = r["goles_visitante_1t"]
            gc = r["goles_local_1t"]
        try:
            gf_1t.append(float(gf))
            gc_1t.append(float(gc))
        except Exception:
            continue
    if len(gf_1t) < 2:
        return None
    return {
        "goles_favor_1t": float(np.mean(gf_1t)),
        "goles_contra_1t": float(np.mean(gc_1t)),
        "n_partidos": len(gf_1t),
    }


def simular_goles_1t(media_local, media_visitante, iteraciones=10000):
    """Simula goles del primer tiempo con Poisson y devuelve probabilidades Over/Under."""
    import numpy as np
    media_local = max(float(media_local), 0.05)
    media_visitante = max(float(media_visitante), 0.05)
    goles_local = np.random.poisson(media_local, iteraciones)
    goles_visitante = np.random.poisson(media_visitante, iteraciones)
    total = goles_local + goles_visitante
    resultado = {}
    for linea in [0.5, 1.5, 2.5]:
        resultado[str(linea)] = {
            "over": round(float(np.mean(total > linea)) * 100, 1),
            "under": round(float(np.mean(total < linea)) * 100, 1),
        }
    # Ambos marcan en 1T
    ambos_1t = round(float(np.mean((goles_local > 0) & (goles_visitante > 0))) * 100, 1)
    return {
        "ou": resultado,
        "ambos_marcan_1t": ambos_1t,
        "goles_local_proj_1t": round(float(np.mean(goles_local)), 2),
        "goles_visitante_proj_1t": round(float(np.mean(goles_visitante)), 2),
    }


def _obtener_estado_real_partido(df, local, visitante):
    """Si el kickoff programado ya paso, consulta el estado EN VIVO via
    api-football en vez de confiar en el "estado" del CSV (que solo se
    refresca una vez al dia via el cron y puede quedar mostrando "NS"
    mientras el partido ya esta en juego o termino). Gateado por hora de
    kickoff para no gastar cuota en partidos que todavia no empezaron.
    Devuelve (estado_real, goles_local_real, goles_visitante_real), con
    None en los 3 si no aplica o no se pudo verificar."""
    try:
        partido_row = df[
            ((df["equipo_local"] == local) & (df["equipo_visitante"] == visitante)) |
            ((df["equipo_local"] == visitante) & (df["equipo_visitante"] == local))
        ].sort_values("fecha", ascending=False)
        if partido_row.empty:
            return None, None, None
        fila = partido_row.iloc[0]
        fixture_id = fila.get("fixture_id")
        if fixture_id is None or pd.isna(fixture_id):
            return None, None, None
        fixture_id = int(fixture_id)

        kickoff = fila["fecha"]
        if pd.isna(kickoff):
            return None, None, None
        from datetime import timezone
        if kickoff > datetime.now(timezone.utc):
            return None, None, None  # todavia no empieza, no gastar cuota

        import requests as _requests
        from player_model import API_KEY as _PM_API_KEY, BASE_URL as _PM_BASE_URL
        headers = {"x-apisports-key": _PM_API_KEY}
        resp = _requests.get(f"{_PM_BASE_URL}/fixtures", headers=headers, params={"id": fixture_id}, timeout=10)
        resp_list = resp.json().get("response", [])
        if not resp_list:
            return None, None, None
        f = resp_list[0]
        estado_real = f["fixture"]["status"]["short"]
        gl = f["goals"]["home"]
        gv = f["goals"]["away"]
        return estado_real, gl, gv
    except Exception:
        return None, None, None


def get_analisis_partido(local_input, visitante_input):
    df = cargar_df()
    if df.empty:
        return None, "No hay datos disponibles"
    equipos_n1 = obtener_equipos_nivel1(df)
    local = obtener_equipo_por_nombre(df, local_input)
    visitante = obtener_equipo_por_nombre(df, visitante_input)
    if local is None:
        return None, f"Equipo no encontrado: {local_input}"
    if visitante is None:
        return None, f"Equipo no encontrado: {visitante_input}"
    sim, stats_a, stats_b = simular(df, local, visitante)
    if sim is None:
        return None, "No hay datos suficientes para simular"
    try:
        liga_series = df[
            (df["equipo_local"] == local) | (df["equipo_visitante"] == local)
        ]["liga"]
        liga = liga_series.iloc[0] if not liga_series.empty else "Desconocida"
    except Exception:
        liga = "Desconocida"
    fixture_id_pendiente = _obtener_fixture_id_pendiente(df, local, visitante)
    top3 = calcular_top3(sim, fixture_id_pendiente, stats_a, stats_b)
    estado_real, goles_local_real, goles_visitante_real = _obtener_estado_real_partido(df, local, visitante)
    ultimos_local = []
    ultimos_visitante = []
    try:
        pl = obtener_partidos_equipo(df, local, n=20)
        for _, r in pl.iterrows():
            gl = int(r["goles_local"])
            gv = int(r["goles_visitante"])
            es_local = r["equipo_local"] == local
            gf = gl if es_local else gv
            gc = gv if es_local else gl
            # Calcular el valor real primero y chequear NaN sobre ESE valor
            # (antes siempre chequeaba la columna "_local" aunque es_local
            # fuera False, dando el resultado equivocado), y usar None en
            # vez de 0 cuando el dato genuinamente falta (mismo patron que
            # construir_fila()/api_to_csv.py y _stats_n_equipo()).
            _corners_val = r["corners_local"] if es_local else r["corners_visitante"]
            _tarjetas_val = r["tarjetas_local"] if es_local else r["tarjetas_visitante"]
            _tiros_arco_val = r["tiros_arco_local"] if es_local else r["tiros_arco_visitante"]
            _tiros_total_val = r["tiros_total_local"] if es_local else r["tiros_total_visitante"]
            ultimos_local.append({
                "fecha": str(r["fecha"])[:10],
                "rival": r["equipo_visitante"] if es_local else r["equipo_local"],
                "resultado": f"{gl}-{gv}",
                "ganado": gf > gc,
                "empate": gf == gc,
                "corners": int(_corners_val) if pd.notna(_corners_val) else None,
                "tarjetas": int(_tarjetas_val) if pd.notna(_tarjetas_val) else None,
                "tiros_arco": int(_tiros_arco_val) if pd.notna(_tiros_arco_val) else None,
                "tiros_total": int(_tiros_total_val) if pd.notna(_tiros_total_val) else None,
                  "goles_favor_1t": int(r["goles_local_1t"] if es_local else r["goles_visitante_1t"]) if "goles_local_1t" in r.index and str(r["goles_local_1t"]) not in ["nan","None"] else None,
                  "goles_contra_1t": int(r["goles_visitante_1t"] if es_local else r["goles_local_1t"]) if "goles_visitante_1t" in r.index and str(r["goles_visitante_1t"]) not in ["nan","None"] else None,
                  "goles_favor_2t": int(r["goles_local_2t"] if es_local else r["goles_visitante_2t"]) if "goles_local_2t" in r.index and str(r["goles_local_2t"]) not in ["nan","None"] else None,
                  "goles_contra_2t": int(r["goles_visitante_2t"] if es_local else r["goles_local_2t"]) if "goles_visitante_2t" in r.index and str(r["goles_visitante_2t"]) not in ["nan","None"] else None,
                  "tarjetas_favor_1t": int(r["tarjetas_local_1t"] if es_local else r["tarjetas_visitante_1t"]) if "tarjetas_local_1t" in r.index and str(r["tarjetas_local_1t"]) not in ["nan","None"] else None,
                  "tarjetas_favor_2t": int(r["tarjetas_local_2t"] if es_local else r["tarjetas_visitante_2t"]) if "tarjetas_local_2t" in r.index and str(r["tarjetas_local_2t"]) not in ["nan","None"] else None,
                  "liga_partido": str(r["liga"]) if "liga" in r.index else "",
                "categoria_rival": categoria_equipo(r["equipo_visitante"] if r["equipo_local"] == local else r["equipo_local"], equipos_n1),
            })
    except Exception:
        pass
    try:
        pv = obtener_partidos_equipo(df, visitante, n=20)
        for _, r in pv.iterrows():
            gl = int(r["goles_local"])
            gv = int(r["goles_visitante"])
            es_local = r["equipo_local"] == visitante
            gf = gl if es_local else gv
            gc = gv if es_local else gl
            _corners_val = r["corners_local"] if es_local else r["corners_visitante"]
            _tarjetas_val = r["tarjetas_local"] if es_local else r["tarjetas_visitante"]
            _tiros_arco_val = r["tiros_arco_local"] if es_local else r["tiros_arco_visitante"]
            _tiros_total_val = r["tiros_total_local"] if es_local else r["tiros_total_visitante"]
            ultimos_visitante.append({
                "fecha": str(r["fecha"])[:10],
                "rival": r["equipo_visitante"] if es_local else r["equipo_local"],
                "resultado": f"{gf}-{gc}",
                "ganado": gf > gc,
                "empate": gf == gc,
                "corners": int(_corners_val) if pd.notna(_corners_val) else None,
                "tarjetas": int(_tarjetas_val) if pd.notna(_tarjetas_val) else None,
                "tiros_arco": int(_tiros_arco_val) if pd.notna(_tiros_arco_val) else None,
                "tiros_total": int(_tiros_total_val) if pd.notna(_tiros_total_val) else None,
                "goles_favor_1t": int(r["goles_local_1t"] if es_local else r["goles_visitante_1t"]) if "goles_local_1t" in r.index and str(r["goles_local_1t"]) not in ["nan","None"] else None,
                "goles_contra_1t": int(r["goles_visitante_1t"] if es_local else r["goles_local_1t"]) if "goles_visitante_1t" in r.index and str(r["goles_visitante_1t"]) not in ["nan","None"] else None,
                "goles_favor_2t": int(r["goles_local_2t"] if es_local else r["goles_visitante_2t"]) if "goles_local_2t" in r.index and str(r["goles_local_2t"]) not in ["nan","None"] else None,
                "goles_contra_2t": int(r["goles_visitante_2t"] if es_local else r["goles_local_2t"]) if "goles_visitante_2t" in r.index and str(r["goles_visitante_2t"]) not in ["nan","None"] else None,
                "tarjetas_favor_1t": int(r["tarjetas_local_1t"] if es_local else r["tarjetas_visitante_1t"]) if "tarjetas_local_1t" in r.index and str(r["tarjetas_local_1t"]) not in ["nan","None"] else None,
                "tarjetas_favor_2t": int(r["tarjetas_local_2t"] if es_local else r["tarjetas_visitante_2t"]) if "tarjetas_local_2t" in r.index and str(r["tarjetas_local_2t"]) not in ["nan","None"] else None,
                "liga_partido": str(r["liga"]) if "liga" in r.index else "",
                "categoria_rival": categoria_equipo(r["equipo_visitante"] if r["equipo_local"] == visitante else r["equipo_local"], equipos_n1),
            })
    except Exception:
        pass

    # Aplicar ajuste cualitativo de IA si existe (lesiones, forma, contexto)
    ajuste_ia_info = _obtener_ajuste_ia(df, local, visitante)
    prob_local_final = sim["prob_local"] * 100
    prob_empate_final = sim["prob_empate"] * 100
    prob_visitante_final = sim["prob_visitante"] * 100

    if ajuste_ia_info:
        aj_local = ajuste_ia_info.get("ajuste_local", 0)
        aj_visit = ajuste_ia_info.get("ajuste_visitante", 0)
        prob_local_final = prob_local_final + aj_local
        prob_visitante_final = prob_visitante_final + aj_visit
        # Mantener el empate igual y renormalizar para que sume 100
        total = prob_local_final + prob_empate_final + prob_visitante_final
        if total > 0:
            factor = 100 / total
            prob_local_final = prob_local_final * factor
            prob_empate_final = prob_empate_final * factor
            prob_visitante_final = prob_visitante_final * factor
        # Evitar valores fuera de rango
        prob_local_final = max(1, min(98, prob_local_final))
        prob_visitante_final = max(1, min(98, prob_visitante_final))
        prob_empate_final = max(1, 100 - prob_local_final - prob_visitante_final)

    return {
        "local": local,
        "visitante": visitante,
        "liga": liga,
        "estado_real": estado_real,
        "goles_local_real": goles_local_real,
        "goles_visitante_real": goles_visitante_real,
        "prob_local": round(prob_local_final, 1),
        "prob_empate": round(prob_empate_final, 1),
        "prob_visitante": round(prob_visitante_final, 1),
        "prob_local_original": round(sim["prob_local"] * 100, 1),
        "prob_empate_original": round(sim["prob_empate"] * 100, 1),
        "prob_visitante_original": round(sim["prob_visitante"] * 100, 1),
        "prob_1x": round(sim["prob_1x"] * 100, 1),
        "prob_x2": round(sim["prob_x2"] * 100, 1),
        "prob_ambos_marcan": round(sim["prob_ambos_marcan"] * 100, 1),
        "goles_proj": f"{sim['goles_local_proj']:.2f} - {sim['goles_visitante_proj']:.2f}",
        "corners_proj": round(sim["corners_totales_proj"], 2),
        "tarjetas_proj": round(sim["tarjetas_totales_proj"], 2),
        "goles_ou": {
            str(k): {"over": round(v["over"]*100,1), "under": round(v["under"]*100,1)}
            for k, v in sim["goles_ou"].items()
        },
        "corners_ou": {
            str(k): {"over": round(v["over"]*100,1), "under": round(v["under"]*100,1)}
            for k, v in sim["corners_ou"].items()
        },
        "tarjetas_ou": {
            str(k): {"over": round(v["over"]*100,1), "under": round(v["under"]*100,1)}
            for k, v in sim["tarjetas_ou"].items()
        },
        "goles_1t": _calcular_goles_1t(df, local, visitante),
        "ajuste_ia": _obtener_ajuste_ia(df, local, visitante),
        "top3": top3,
        "ultimos_local": ultimos_local,
        "ultimos_visitante": ultimos_visitante,
        "h2h": [
            {
                "fecha": str(r["fecha"])[:10],
                "equipo_local": r["equipo_local"],
                "equipo_visitante": r["equipo_visitante"],
                "goles_local": int(r["goles_local"]),
                "goles_visitante": int(r["goles_visitante"]),
            }
            for _, r in ultimos_enfrentamientos_directos(df, local, visitante, n=10).sort_values("fecha", ascending=False).iterrows()
        ],
        "stats_local_5": _stats_n_equipo(df, local, 5),
        "stats_local_10": _stats_n_equipo(df, local, 10),
        "stats_visitante_5": _stats_n_equipo(df, visitante, 5),
        "stats_visitante_10": _stats_n_equipo(df, visitante, 10),
        "cuotas": get_cuotas_partido(local, visitante, liga),
        "stats_local_temporada": _stats_temporada_actual(df, local),
        "stats_visitante_temporada": _stats_temporada_actual(df, visitante),
        "tiros_arco_local": 0,
        "stats_local": {
            "goles_favor": round(stats_a["goles_favor"], 2),
            "goles_contra": round(stats_a["goles_contra"], 2),
            "corners_favor": round(stats_a["corners_favor"], 2),
            "corners_contra": round(stats_a["corners_contra"], 2),
            "tarjetas_favor": round(stats_a["tarjetas_favor"], 2),
            "tiros_arco_favor": _safe(stats_a.get("tiros_arco_favor")),
            "tiros_total_favor": _safe(stats_a.get("tiros_total_favor")),
            "victorias": stats_a["victorias"],
            "empates": stats_a["empates"],
            "derrotas": stats_a["derrotas"],
            "n_partidos": stats_a["n_partidos"],
        },
        "stats_visitante": {
            "goles_favor": round(stats_b["goles_favor"], 2),
            "goles_contra": round(stats_b["goles_contra"], 2),
            "corners_favor": round(stats_b["corners_favor"], 2),
            "corners_contra": round(stats_b["corners_contra"], 2),
            "tarjetas_favor": round(stats_b["tarjetas_favor"], 2),
            "tiros_arco_favor": _safe(stats_b.get("tiros_arco_favor")),
            "tiros_total_favor": _safe(stats_b.get("tiros_total_favor")),
            "victorias": stats_b["victorias"],
            "empates": stats_b["empates"],
            "derrotas": stats_b["derrotas"],
            "n_partidos": stats_b["n_partidos"],
        },
        "tiros_arco_visitante": 0,
        "tiros_total_local": 0,
        "tiros_total_visitante": 0,
    }, None


MERCADOS_VALIDOS = ("goles", "corners", "tarjetas")
LADOS_VALIDOS = ("over", "under")


def _armar_analisis_reglas_fijas(mercado, linea, lado, probabilidad_modelo,
                                  local, visitante, sim, stats_a, stats_b, h2h):
    """Texto automatico (sin IA, sin costo) que explica el calculo del
    value bet con los datos reales que ya usa el modelo -- forma
    reciente, H2H si hay, xG si hay cobertura. Nunca inventa un dato: si
    algo no esta disponible, esa frase se omite en vez de rellenarla."""
    partes = []

    if mercado == "corners":
        proyeccion = sim["corners_totales_proj"]
        partes.append(f"El modelo proyecta {proyeccion:.1f} corners totales para este partido.")
        partes.append(
            f"{local} promedia {stats_a['corners_favor']:.1f} corners a favor en sus "
            f"últimos {stats_a['n_partidos']} partidos, mientras {visitante} concede "
            f"{stats_b['corners_contra']:.1f} en promedio."
        )
        h2h_stats = h2h.dropna(subset=["corners_local", "corners_visitante"]) if not h2h.empty else h2h
        if not h2h_stats.empty:
            total_h2h = (h2h_stats["corners_local"] + h2h_stats["corners_visitante"]).mean()
            partes.append(
                f"En los últimos {len(h2h_stats)} enfrentamientos directos con datos de corners, "
                f"el total promedió {total_h2h:.1f}."
            )

    elif mercado == "goles":
        proyeccion = sim["goles_local_proj"] + sim["goles_visitante_proj"]
        partes.append(
            f"El modelo proyecta {proyeccion:.2f} goles totales "
            f"({local} {sim['goles_local_proj']:.2f}, {visitante} {sim['goles_visitante_proj']:.2f})."
        )
        partes.append(
            f"{local} promedia {stats_a['goles_favor']:.1f} goles a favor y "
            f"{stats_a['goles_contra']:.1f} en contra en sus últimos {stats_a['n_partidos']} partidos; "
            f"{visitante} promedia {stats_b['goles_favor']:.1f} a favor y {stats_b['goles_contra']:.1f} en contra."
        )
        if not h2h.empty:
            total_h2h = (h2h["goles_local"] + h2h["goles_visitante"]).mean()
            partes.append(
                f"En los últimos {len(h2h)} enfrentamientos directos, el total de goles promedió {total_h2h:.1f}."
            )
        if stats_a.get("n_partidos_xg", 0) >= 3 or stats_b.get("n_partidos_xg", 0) >= 3:
            partes.append(
                "Se usaron datos reales de expected goals (xG) de los últimos partidos de "
                "ambos equipos para afinar este número."
            )

    elif mercado == "tarjetas":
        proyeccion = sim["tarjetas_totales_proj"]
        partes.append(f"El modelo proyecta {proyeccion:.2f} tarjetas totales.")
        partes.append(
            f"{local} promedia {stats_a['tarjetas_favor']:.1f} tarjetas por partido y "
            f"{visitante} promedia {stats_b['tarjetas_favor']:.1f}."
        )
        try:
            tarjetas_parejez = tarjetas_esperadas_por_parejez(sim["goles_local_proj"], sim["goles_visitante_proj"])
            base_sin_parejez = (stats_a["tarjetas_favor"] + stats_b["tarjetas_favor"]) / 2
            if tarjetas_parejez - base_sin_parejez > 0.15:
                partes.append("Como este partido se proyecta parejo, el modelo ajusta el promedio de tarjetas levemente hacia arriba.")
            elif base_sin_parejez - tarjetas_parejez > 0.15:
                partes.append("Como este partido se proyecta con un favorito claro, el modelo ajusta el promedio de tarjetas levemente hacia abajo.")
        except Exception:
            pass
        h2h_stats = h2h.dropna(subset=["tarjetas_local", "tarjetas_visitante"]) if not h2h.empty else h2h
        if not h2h_stats.empty:
            total_h2h = (h2h_stats["tarjetas_local"] + h2h_stats["tarjetas_visitante"]).mean()
            partes.append(
                f"En los últimos {len(h2h_stats)} enfrentamientos directos con datos de tarjetas, "
                f"el total promedió {total_h2h:.1f}."
            )

    posicion = "por debajo" if linea < proyeccion else "por encima"
    lado_texto = "Over" if lado == "over" else "Under"
    partes.append(
        f"La línea que pusiste ({linea:g}) está {posicion} de la proyección del modelo, "
        f"por eso te da {round(probabilidad_modelo * 100, 1)}% de probabilidad para {lado_texto}."
    )

    for stats, nombre in ((stats_a, local), (stats_b, visitante)):
        if stats.get("pocos_datos"):
            partes.append(
                f"Ojo: {nombre} tiene poco historial disponible ({stats['n_partidos']} partidos), "
                "así que parte de esta proyección viene del promedio general de su liga."
            )

    return " ".join(partes)


def calcular_value_bet_manual(local_input, visitante_input, mercado, linea, lado, cuota):
    """Value betting manual: el usuario elige un mercado (goles/corners/
    tarjetas), mete una linea PUNTUAL (no tiene que ser una de las fijas
    que ya mostramos, ej. 8.5) y la cuota real de su casa de apuestas, y
    esto le dice si nuestra probabilidad calculada le da "valor" frente
    a esa cuota.

    Reutiliza simular() tal cual (mismo pipeline que get_analisis_partido:
    H2H, ajuste de liga, multiplicadores de presion/agresividad/clasico/
    intensidad ofensiva) y lee goles_local_proj/goles_visitante_proj/
    corners_totales_proj/tarjetas_totales_proj del resultado -- son los
    mismos numeros ya ajustados que alimentan goles_ou/corners_ou/
    tarjetas_ou en el resto de la app, asi que la probabilidad para
    cualquier linea personalizada queda consistente con lo que el
    usuario ya ve ahi."""
    if mercado not in MERCADOS_VALIDOS:
        return None, f"Mercado no valido: {mercado!r} (usar goles, corners o tarjetas)"
    if lado not in LADOS_VALIDOS:
        return None, f"Lado no valido: {lado!r} (usar over o under)"
    try:
        linea = float(linea)
    except (TypeError, ValueError):
        return None, f"Linea invalida: {linea!r}"
    try:
        cuota = float(cuota)
    except (TypeError, ValueError):
        return None, f"Cuota invalida: {cuota!r}"
    if cuota <= 1.0:
        return None, "La cuota tiene que ser mayor a 1.0"

    df = cargar_df()
    if df.empty:
        return None, "No hay datos disponibles"
    local = obtener_equipo_por_nombre(df, local_input)
    visitante = obtener_equipo_por_nombre(df, visitante_input)
    if local is None:
        return None, f"Equipo no encontrado: {local_input}"
    if visitante is None:
        return None, f"Equipo no encontrado: {visitante_input}"

    sim, stats_a, stats_b = simular(df, local, visitante)
    if sim is None:
        return None, "No hay datos suficientes para simular"
    h2h = ultimos_enfrentamientos_directos(df, local, visitante, n=5)

    # Misma confianza (k) que ya usa simular() para goles_ou/corners_ou/
    # tarjetas_ou -- sin esto, una linea personalizada mostraria una
    # probabilidad mas extrema (Poisson puro) que la que el usuario ya
    # ve en las lineas fijas del mismo partido para el mismo mercado.
    k_goles_a = n_efectivo_estimacion(stats_a["n_partidos"], stats_a["n_partidos_condicion"])
    k_goles_b = n_efectivo_estimacion(stats_b["n_partidos"], stats_b["n_partidos_condicion"])
    k_corners_a = n_efectivo_estimacion(stats_a["n_partidos_stats"], stats_a["n_partidos_condicion"])
    k_corners_b = n_efectivo_estimacion(stats_b["n_partidos_stats"], stats_b["n_partidos_condicion"])

    probabilidad_modelo = probabilidad_linea_personalizada(
        mercado, linea, lado,
        media_goles_a=sim["goles_local_proj"],
        media_goles_b=sim["goles_visitante_proj"],
        media_corners_total=sim["corners_totales_proj"],
        media_tarjetas_total=sim["tarjetas_totales_proj"],
        k_goles_a=k_goles_a, k_goles_b=k_goles_b,
        k_corners=min(k_corners_a, k_corners_b),
        k_tarjetas=min(k_corners_a, k_corners_b),
    )

    probabilidad_implicita = 1 / cuota
    edge_porcentual = edge_ratio(probabilidad_modelo, cuota) * 100
    cuota_minima_valor = 1 / probabilidad_modelo if probabilidad_modelo > 0 else None

    analisis_reglas_fijas = _armar_analisis_reglas_fijas(
        mercado, linea, lado, probabilidad_modelo, local, visitante, sim, stats_a, stats_b, h2h
    )

    return {
        "local": local,
        "visitante": visitante,
        "mercado": mercado,
        "linea": linea,
        "lado": lado,
        "cuota": cuota,
        "probabilidad_modelo": round(probabilidad_modelo * 100, 1),
        "probabilidad_implicita": round(probabilidad_implicita * 100, 1),
        "edge_porcentual": round(edge_porcentual, 1),
        "analisis_reglas_fijas": analisis_reglas_fijas,
        "tiene_valor": probabilidad_modelo > probabilidad_implicita,
        "cuota_minima_valor": round(cuota_minima_valor, 2) if cuota_minima_valor else None,
    }, None


def explicar_value_bet_ia(local_input, visitante_input, mercado, linea, lado, cuota):
    """Explicacion opcional con IA (Claude Haiku) de un calculo de value
    bet manual ya hecho -- el usuario la pide explicitamente con un
    boton aparte, no se genera sola. Vuelve a calcular todo server-side
    (no confia en numeros que mande el frontend) para tener datos
    frescos + el texto de reglas fijas, y le pide a la IA que lo
    explique en lenguaje natural sin recalcular ni cambiar ningun
    numero. System prompt propio y corto -- no el del chat general
    (ese trae reglas de jugadores/1T-2T/rivales de categoria menor que
    no aplican aca y solo agregarian ruido)."""
    resultado, error = calcular_value_bet_manual(local_input, visitante_input, mercado, linea, lado, cuota)
    if error:
        return None, error

    df = cargar_df()
    liga_series = df[
        (df["equipo_local"] == resultado["local"]) | (df["equipo_visitante"] == resultado["local"])
    ]["liga"] if not df.empty else None
    liga = liga_series.iloc[0] if liga_series is not None and not liga_series.empty else "Desconocida"

    contexto = f"""PARTIDO: {resultado['local']} vs {resultado['visitante']} ({liga})
MERCADO: {resultado['mercado']} - Linea {resultado['linea']} - Lado: {resultado['lado']}
CUOTA INGRESADA: {resultado['cuota']}
PROBABILIDAD DEL MODELO: {resultado['probabilidad_modelo']}%
PROBABILIDAD IMPLICITA DE LA CUOTA: {resultado['probabilidad_implicita']}%
EDGE: {resultado['edge_porcentual']}%
TIENE VALOR: {"si" if resultado['tiene_valor'] else "no"}
CUOTA MINIMA PARA QUE HAYA VALOR: {resultado['cuota_minima_valor']}

ANALISIS DE DATOS QUE USO EL MODELO:
{resultado['analisis_reglas_fijas']}

Explica este resultado en lenguaje natural."""

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
        system = (
            "Sos un asistente que explica en lenguaje natural y conversacional un calculo de "
            "value betting ya hecho por un modelo estadistico. NO recalcules nada, NO cambies "
            "ningun numero -- todos los datos que necesitas estan en el contexto. Tu trabajo es "
            "explicar con tus palabras, en 2 a 4 oraciones, por que el modelo llego a esa "
            "probabilidad y que significa el edge en terminos simples para alguien que no es "
            "estadistico. No uses jerga tecnica (Poisson, distribucion, Dixon-Coles, etc) ni "
            "markdown ni asteriscos. Nunca digas 'apostar' ni 'no apostar' -- termina siempre "
            "con una frase tipo 'los datos respaldan/no respaldan esta cuota', sin dar una orden "
            "directa. Cerra siempre con: Esto es un analisis estadistico, no una garantia - el "
            "resultado real de un partido puede diferir. Responde en espanol, maximo 120 palabras."
        )
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            system=system,
            messages=[{"role": "user", "content": contexto}],
        )
        return response.content[0].text, None
    except Exception as e:
        return None, str(e)


def get_historial_jugador(equipo_input, jugador_nombre, n=5):
    """Devuelve el desglose real (partido por partido) de un jugador especifico,
    buscando en los ultimos n partidos de su equipo."""
    import requests as _requests
    from player_model import obtener_historial_jugador, API_KEY as _PM_API_KEY, BASE_URL as _PM_BASE_URL

    df = cargar_df()
    if df.empty:
        return None, "No hay datos disponibles"
    equipo = obtener_equipo_por_nombre(df, equipo_input)
    if equipo is None:
        return None, f"Equipo no encontrado: {equipo_input}"

    try:
        liga_series = df[
            (df["equipo_local"] == equipo) | (df["equipo_visitante"] == equipo)
        ]["liga"]
        liga = liga_series.iloc[0] if not liga_series.empty else None
    except Exception:
        liga = None
    if not liga:
        return None, "Liga no encontrada"
    liga_id, temporada = get_temporada(liga)
    if not liga_id:
        return None, f"No se pudo resolver liga_id para {liga}"

    try:
        headers = {"x-apisports-key": _PM_API_KEY}
        resp_team = _requests.get(f"{_PM_BASE_URL}/teams", headers=headers, params={"search": equipo})
        data_team = resp_team.json()
        if not data_team.get("response"):
            return None, "Equipo no encontrado en la API"
        LIGA_PAIS = {
            "Liga Profesional Argentina": "Argentina", "Brasileirao": "Brazil",
            "Brasileirao Serie A": "Brazil", "Liga Colombia": "Colombia",
            "Primera Division Chile": "Chile", "Primera Division Uruguay": "Uruguay",
            "Primera Division Peru": "Peru", "Liga Pro Ecuador": "Ecuador",
            "Primera Division Venezuela": "Venezuela", "Primera Division Bolivia": "Bolivia",
            "Division Profesional Paraguay": "Paraguay", "Liga MX": "Mexico", "MLS": "USA",
            "Copa Argentina": "Argentina", "Copa Chile": "Chile", "Copa Colombia": "Colombia",
            "Copa Uruguay": "Uruguay", "Copa do Brasil": "Brazil",
        }
        pais_esperado = LIGA_PAIS.get(liga)
        candidatos_team = data_team["response"]
        team_id = None
        if pais_esperado:
            for c in candidatos_team:
                if c["team"]["country"] == pais_esperado:
                    team_id = c["team"]["id"]
                    break
        if team_id is None:
            team_id = candidatos_team[0]["team"]["id"]

        # Buscar un rango amplio de fixtures del equipo (no solo n), porque el
        # jugador puede no haber participado en varios partidos recientes
        # (lesion, suspension, no convocado). Se sigue buscando hacia atras
        # hasta encontrar n partidos REALES donde el jugador jugo.
        RANGO_BUSQUEDA = max(n * 4, 20)
        resp_fixtures = _requests.get(
            f"{_PM_BASE_URL}/fixtures", headers=headers,
            params={"team": team_id, "season": temporada, "last": RANGO_BUSQUEDA}
        )
        data_fixtures = resp_fixtures.json()
        fixture_ids = [f["fixture"]["id"] for f in data_fixtures.get("response", [])]
        if not fixture_ids:
            return [], None

        historial = obtener_historial_jugador(jugador_nombre, fixture_ids, n=n, rango_busqueda=RANGO_BUSQUEDA)
        return historial, None
    except Exception as e:
        return None, str(e)


def buscar_jugador_general(query, limite=20):
    """Busca jugadores por nombre en los equipos ya descargados localmente.
    Devuelve lista de coincidencias con nombre, equipo, posicion y stats basicas."""
    import json as _json
    q = query.lower().strip()
    if len(q) < 2:
        return []

    resultados = []
    if not os.path.exists(JUGADORES_DATA_DIR):
        return []

    for archivo in os.listdir(JUGADORES_DATA_DIR):
        if not archivo.endswith(".json") or archivo.startswith("fixture_"):
            continue
        try:
            with open(os.path.join(JUGADORES_DATA_DIR, archivo), "r", encoding="utf-8") as f:
                data = _json.load(f)
        except Exception:
            continue

        equipo_nombre = data.get("equipo", "")
        for jraw in data.get("jugadores", []):
            info = jraw.get("player", {})
            nombre = info.get("name", "")
            if q not in nombre.lower():
                continue
            stats_list = jraw.get("statistics", [])
            stats = stats_list[0] if stats_list else {}
            games = stats.get("games", {}) or {}
            resultados.append({
                "nombre": nombre,
                "equipo": equipo_nombre,
                "posicion": games.get("position", "") or "",
                "partidos": games.get("appearences", 0) or 0,
                "foto": info.get("photo", ""),
            })
            if len(resultados) >= limite:
                return resultados
    return resultados


def get_jugadores_partido(local_input, visitante_input):
    """Devuelve jugadores agrupados por equipo: 5 atacantes y 5 defensivos por equipo."""
    from player_model import obtener_jugadores_partido, obtener_fixture_id

    df = cargar_df()
    if df.empty:
        return None, "No hay datos disponibles"

    local = obtener_equipo_por_nombre(df, local_input)
    visitante = obtener_equipo_por_nombre(df, visitante_input)
    if local is None:
        return None, f"Equipo no encontrado: {local_input}"
    if visitante is None:
        return None, f"Equipo no encontrado: {visitante_input}"

    # Buscar liga del partido
    try:
        liga_series = df[
            ((df["equipo_local"] == local) & (df["equipo_visitante"] == visitante)) |
            ((df["equipo_local"] == visitante) & (df["equipo_visitante"] == local))
        ]["liga"]
        if liga_series.empty:
            liga_series = df[
                (df["equipo_local"] == local) | (df["equipo_visitante"] == local)
            ]["liga"]
        liga = liga_series.iloc[0] if not liga_series.empty else None
    except Exception:
        liga = None

    if not liga:
        return None, "Liga no encontrada para el partido"

    liga_id, temporada = get_temporada(liga)
    if not liga_id:
        return None, f"No se pudo resolver liga_id para {liga}"

    # Buscar fixture_id en el CSV o via API
    fixture_id = None
    try:
        partido_row = df[
            ((df["equipo_local"] == local) & (df["equipo_visitante"] == visitante)) |
            ((df["equipo_local"] == visitante) & (df["equipo_visitante"] == local))
        ].sort_values("fecha", ascending=False)
        if not partido_row.empty and "fixture_id" in partido_row.columns:
            fid = partido_row.iloc[0]["fixture_id"]
            if fid and not pd.isna(fid):
                fixture_id = int(fid)
    except Exception:
        pass

    if not fixture_id:
        try:
            fecha_partido = datetime.now().strftime("%Y-%m-%d")
            fixture_id = obtener_fixture_id(liga_id, temporada, local, visitante, fecha_partido, df)
        except Exception as e:
            return None, f"No se pudo obtener fixture_id: {e}"

    if not fixture_id:
        return None, "Fixture no encontrado en la API"

    try:
        data = obtener_jugadores_partido(fixture_id, liga_id, temporada, nombre_local=local, nombre_visitante=visitante)
    except Exception as e:
        return None, str(e)

    if not data:
        return None, "Sin datos de jugadores para este partido"

    # Devolver dict estructurado: {local: {atacantes, defensivos}, visitante: {atacantes, defensivos}}
    equipos_ordenados = {}
    for nombre_equipo, secciones in data.items():
        equipos_ordenados[nombre_equipo] = secciones

    return {
        "liga": liga,
        "local": local,
        "visitante": visitante,
        "equipos": equipos_ordenados,
    }, None


def _stats_n_equipo(df, equipo, n):
    import numpy as np
    from football_model import obtener_partidos_equipo
    try:
        ps = obtener_partidos_equipo(df, equipo, n=n)
        if ps.empty:
            return None
        gf_list, gc_list, cf_list, tf_list, ta_list = [], [], [], [], []
        v = e = d = 0
        for _, r in ps.iterrows():
            es_local = r["equipo_local"] == equipo
            # NaN es "truthy" en Python, asi que "valor or 0" NO lo reemplaza
            # por 0 -- hay que chequear pd.notna() explicitamente. Los goles
            # casi nunca faltan, pero se protegen igual por consistencia.
            gf_val = r["goles_local"] if es_local else r["goles_visitante"]
            gc_val = r["goles_visitante"] if es_local else r["goles_local"]
            gf = float(gf_val) if pd.notna(gf_val) else 0.0
            gc = float(gc_val) if pd.notna(gc_val) else 0.0
            gf_list.append(gf); gc_list.append(gc)
            if gf > gc: v += 1
            elif gf == gc: e += 1
            else: d += 1

            # Corners/tarjetas/tiros al arco: partidos sin stats detalladas
            # en la API quedan en NaN (ver construir_fila() en api_to_csv.py).
            # Se excluyen del promedio en vez de contarlos como 0 real, y se
            # excluyen por metrica individual (no la fila entera) porque un
            # partido puede tener corners pero no tarjetas, o viceversa.
            cf_val = r["corners_local"] if es_local else r["corners_visitante"]
            tf_val = r["tarjetas_local"] if es_local else r["tarjetas_visitante"]
            ta_val = r["tiros_arco_local"] if es_local else r["tiros_arco_visitante"]
            if pd.notna(cf_val): cf_list.append(float(cf_val))
            if pd.notna(tf_val): tf_list.append(float(tf_val))
            if pd.notna(ta_val): ta_list.append(float(ta_val))
        return {
            "goles_favor": round(float(np.mean(gf_list)), 2) if gf_list else 0,
            "goles_contra": round(float(np.mean(gc_list)), 2) if gc_list else 0,
            "corners_favor": round(float(np.mean(cf_list)), 2) if cf_list else 0,
            "tarjetas_favor": round(float(np.mean(tf_list)), 2) if tf_list else 0,
            "tiros_arco_favor": round(float(np.mean(ta_list)), 2) if ta_list else 0,
            "victorias": v, "empates": e, "derrotas": d, "n_partidos": len(ps)
        }
    except: return None


def _stats_temporada_actual(df, equipo):
    import numpy as np
    from football_model import obtener_partidos_equipo
    from datetime import datetime
    try:
        hoy = datetime.now()
        inicio_temp = f"{hoy.year if hoy.month >= 8 else hoy.year - 1}-07-01"
        ps = obtener_partidos_equipo(df, equipo, n=999)
        ps = ps[ps["fecha"] >= inicio_temp]
        if ps.empty:
            return None
        gf_list, gc_list, cf_list, tf_list, ta_list = [], [], [], [], []
        v = e = d = 0
        for _, r in ps.iterrows():
            es_local = r["equipo_local"] == equipo
            # NaN es "truthy" en Python, asi que "valor or 0" NO lo reemplaza
            # por 0 -- hay que chequear pd.notna() explicitamente. Los goles
            # casi nunca faltan, pero se protegen igual por consistencia.
            gf_val = r["goles_local"] if es_local else r["goles_visitante"]
            gc_val = r["goles_visitante"] if es_local else r["goles_local"]
            gf = float(gf_val) if pd.notna(gf_val) else 0.0
            gc = float(gc_val) if pd.notna(gc_val) else 0.0
            gf_list.append(gf); gc_list.append(gc)
            if gf > gc: v += 1
            elif gf == gc: e += 1
            else: d += 1

            # Corners/tarjetas/tiros al arco: partidos sin stats detalladas
            # en la API quedan en NaN (ver construir_fila() en api_to_csv.py).
            # Se excluyen del promedio en vez de contarlos como 0 real, y se
            # excluyen por metrica individual (no la fila entera) porque un
            # partido puede tener corners pero no tarjetas, o viceversa.
            cf_val = r["corners_local"] if es_local else r["corners_visitante"]
            tf_val = r["tarjetas_local"] if es_local else r["tarjetas_visitante"]
            ta_val = r["tiros_arco_local"] if es_local else r["tiros_arco_visitante"]
            if pd.notna(cf_val): cf_list.append(float(cf_val))
            if pd.notna(tf_val): tf_list.append(float(tf_val))
            if pd.notna(ta_val): ta_list.append(float(ta_val))
        return {
            "goles_favor": round(float(np.mean(gf_list)), 2) if gf_list else 0,
            "goles_contra": round(float(np.mean(gc_list)), 2) if gc_list else 0,
            "corners_favor": round(float(np.mean(cf_list)), 2) if cf_list else 0,
            "tarjetas_favor": round(float(np.mean(tf_list)), 2) if tf_list else 0,
            "tiros_arco_favor": round(float(np.mean(ta_list)), 2) if ta_list else 0,
            "victorias": v, "empates": e, "derrotas": d, "n_partidos": len(ps)
        }
    except: return None


def get_cuotas_partido(local, visitante, liga_nombre):
    import requests
    ODDS_API_KEY = "016ac8cef97435449ec8f235ada4cbad"
    LIGAS_ODDS = {
        "Premier League": "soccer_epl",
        "La Liga": "soccer_spain_la_liga",
        "Serie A": "soccer_italy_serie_a",
        "Bundesliga": "soccer_germany_bundesliga",
        "Ligue 1": "soccer_france_ligue_one",
        "Champions League": "soccer_uefa_champs_league",
        "Europa League": "soccer_uefa_europa_league",
        "Primeira Liga": "soccer_portugal_primeira_liga",
        "Eredivisie": "soccer_netherlands_eredivisie",
        "MLS": "soccer_usa_mls",
        "Liga MX": "soccer_mexico_ligamx",
        "Brasileirao": "soccer_brazil_campeonato",
        "Liga Profesional Argentina": "soccer_argentina_primera_division",
    }
    sport_key = LIGAS_ODDS.get(liga_nombre)
    if not sport_key:
        return []
    try:
        url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/"
        params = {
            "apiKey": ODDS_API_KEY,
            "regions": "eu",
            "markets": "h2h,totals",
            "oddsFormat": "decimal",
        }
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code != 200:
            return []
        data = resp.json()
        local_lower = local.lower()
        visitante_lower = visitante.lower()
        for partido in data:
            home = partido.get("home_team", "").lower()
            away = partido.get("away_team", "").lower()
            if (local_lower[:6] in home or home[:6] in local_lower) and \
               (visitante_lower[:6] in away or away[:6] in visitante_lower):
                home_team_lower = partido["home_team"].lower()
                away_team_lower = partido["away_team"].lower()
                cuotas = []
                for bm in partido.get("bookmakers", [])[:10]:
                    casa_data = {
                        "casa": bm["title"],
                        "local": 0,
                        "empate": 0,
                        "visitante": 0,
                        "totals": {},
                    }
                    for market in bm.get("markets", []):
                        if market["key"] == "h2h":
                            outcomes = {o["name"].lower(): o["price"] for o in market["outcomes"]}
                            casa_data["local"] = outcomes.get(home_team_lower, 0)
                            casa_data["empate"] = outcomes.get("draw", 0)
                            casa_data["visitante"] = outcomes.get(away_team_lower, 0)
                        elif market["key"] == "totals":
                            for o in market["outcomes"]:
                                punto = str(o.get("point", ""))
                                if not punto:
                                    continue
                                if punto not in casa_data["totals"]:
                                    casa_data["totals"][punto] = {"over": 0, "under": 0}
                                nombre = o.get("name", "").lower()
                                if nombre == "over":
                                    casa_data["totals"][punto]["over"] = o["price"]
                                elif nombre == "under":
                                    casa_data["totals"][punto]["under"] = o["price"]
                    if casa_data["local"] > 0 or casa_data["totals"]:
                        cuotas.append(casa_data)
                return cuotas
        return []
    except Exception:
        return []

# Cache global para value bets (TTL 30 min)
_VB_CACHE = {"timestamp": 0, "data": []}
_VB_TTL_SEGUNDOS = 30 * 60


def get_value_bets_hoy():
    """Recorre partidos de los proximos 7 dias con cuotas y devuelve top errores de cuota.
    Cachea el resultado por 30 minutos para evitar recalcular en cada request.
    """
    import time
    from datetime import datetime, timedelta

    # Verificar cache
    ahora = time.time()
    if (ahora - _VB_CACHE["timestamp"]) < _VB_TTL_SEGUNDOS and _VB_CACHE["data"]:
        return _VB_CACHE["data"]

    df = cargar_df()
    if df.empty:
        return []

    # Filtrar partidos entre hoy y +7 dias (sin resultado todavia)
    hoy = datetime.now()
    limite = hoy + timedelta(days=7)
    df_fechas = df.copy()
    df_fechas["fecha_dt"] = pd.to_datetime(df_fechas["fecha"], errors="coerce")
    partidos = df_fechas[
        (df_fechas["fecha_dt"] >= hoy.replace(hour=0, minute=0, second=0, microsecond=0))
        & (df_fechas["fecha_dt"] <= limite)
    ]
    if partidos.empty:
        _VB_CACHE["timestamp"] = ahora
        _VB_CACHE["data"] = []
        return []

    LIGAS_CON_CUOTAS = {
        "Premier League", "La Liga", "Serie A", "Bundesliga", "Ligue 1",
        "Champions League", "Europa League", "Primeira Liga", "Eredivisie",
        "MLS", "Liga MX", "Brasileirao", "Liga Profesional Argentina",
    }

    VALOR_MIN = 5.0
    PROB_MIN = 30.0
    CUOTA_MIN = 1.30
    CUOTA_MAX = 6.0
    MAX_POR_PARTIDO = 3
    MAX_TOTAL = 50

    # Deduplicar partidos por (local, visitante, liga) para no procesar duplicados
    partidos_unicos = partidos.drop_duplicates(subset=["equipo_local", "equipo_visitante", "liga"])

    resultado = []
    for _, row in partidos_unicos.iterrows():
        liga = row["liga"]
        if liga not in LIGAS_CON_CUOTAS:
            continue
        local = row["equipo_local"]
        visitante = row["equipo_visitante"]

        fecha_str = ""
        hora_str = ""
        try:
            fdt = row["fecha_dt"]
            if pd.notna(fdt):
                fecha_str = fdt.strftime("%Y-%m-%d")
                hora_str = fdt.strftime("%H:%M")
        except Exception:
            pass

        sim, stats_a, stats_b = simular(df, local, visitante)
        if sim is None:
            continue

        cuotas = get_cuotas_partido(local, visitante, liga)
        if not cuotas:
            continue

        prob_local = round(sim["prob_local"] * 100, 1)
        prob_empate = round(sim["prob_empate"] * 100, 1)
        prob_visitante = round(sim["prob_visitante"] * 100, 1)
        goles_ou = {
            str(k): {"over": round(v["over"] * 100, 1), "under": round(v["under"] * 100, 1)}
            for k, v in sim["goles_ou"].items()
        }

        candidatos_partido = []
        for casa in cuotas:
            opciones = [
                {"mercado": f"{local} gana", "cuota": casa.get("local", 0), "probIA": prob_local},
                {"mercado": "Empate", "cuota": casa.get("empate", 0), "probIA": prob_empate},
                {"mercado": f"{visitante} gana", "cuota": casa.get("visitante", 0), "probIA": prob_visitante},
            ]
            totals = casa.get("totals") or {}
            for punto, vals in totals.items():
                ou = goles_ou.get(punto)
                if not ou:
                    continue
                if vals.get("over"):
                    opciones.append({
                        "mercado": f"Over {punto} goles",
                        "cuota": vals["over"],
                        "probIA": ou["over"],
                    })
                if vals.get("under"):
                    opciones.append({
                        "mercado": f"Under {punto} goles",
                        "cuota": vals["under"],
                        "probIA": ou["under"],
                    })

            for o in opciones:
                cuota = o["cuota"]
                probIA = o["probIA"]
                if not cuota or cuota < CUOTA_MIN or cuota > CUOTA_MAX:
                    continue
                if probIA < PROB_MIN:
                    continue
                prob_implicita = (1 / cuota) * 100
                valor = probIA - prob_implicita
                if valor < VALOR_MIN:
                    continue
                candidatos_partido.append({
                    "liga": liga,
                    "local": local,
                    "visitante": visitante,
                    "fecha": fecha_str,
                    "hora": hora_str,
                    "casa": casa["casa"],
                    "mercado": o["mercado"],
                    "cuota": round(cuota, 2),
                    "probIA": probIA,
                    "valor": round(valor, 1),
                })

        candidatos_partido.sort(key=lambda x: x["valor"], reverse=True)
        vistos = set()
        seleccionados = []
        for c in candidatos_partido:
            if c["mercado"] in vistos:
                continue
            vistos.add(c["mercado"])
            seleccionados.append(c)
            if len(seleccionados) >= MAX_POR_PARTIDO:
                break
        resultado.extend(seleccionados)

    resultado.sort(key=lambda x: x["valor"], reverse=True)
    resultado = resultado[:MAX_TOTAL]

    # Guardar en cache
    _VB_CACHE["timestamp"] = ahora
    _VB_CACHE["data"] = resultado
    return resultado


def chat_ia(mensajes, contexto=""):
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
        system = "Eres SportAI Pro, asistente estadistico deportivo. El contexto que recibes contiene TODOS los datos reales del partido: promedios, historicos partido por partido, y probabilidades ya calculadas por el modelo. LEE CUIDADOSAMENTE todo el contexto antes de responder, los datos que necesitas casi siempre estan ahi (busca lineas como PROMEDIO CORNERS, DATOS 1T, ULTIMOS PARTIDOS, etc). REGLA CRITICA: usa SIEMPRE los numeros exactos que aparecen en el contexto, nunca los cambies ni los redondees diferente. Solo si un dato especifico verdaderamente no aparece en NINGUNA parte del contexto, di que no esta disponible - pero antes de decir eso, revisa TODO el contexto con cuidado porque casi siempre el dato esta ahi con otro nombre o formato. REGLAS ADICIONALES: 1) NUNCA uses asteriscos, negritas, cursivas ni markdown. Solo texto plano con emojis. 2) USA EMOJIS DE FORMA CONSISTENTE Y VISUAL: cada seccion o subtitulo de tu respuesta DEBE empezar con un emoji relevante (ejemplo: usa un emoji de grafico como cabecera de analisis, un circulo amarillo para tarjetas, una pelota para goles, una bandera para corners, un trofeo para conclusiones, una lupa para desglose de datos). Dentro de cada seccion, resalta los numeros o datos mas importantes con un emoji corto al lado (una flecha hacia arriba o hacia abajo segun si el dato es alto o bajo, un check para lo que respalda tu conclusion). No dejes ningun bloque largo de texto sin al menos un emoji cada 2-3 lineas. El objetivo es que el usuario pueda escanear visualmente la respuesta sin tener que leer cada palabra. IMPORTANTE DE FORMATO: usa saltos de linea doble SOLO entre secciones grandes distintas (por ejemplo entre el bloque de 1X2 y el bloque de goles, o entre goles y corners). Dentro de una misma seccion, agrupa los datos relacionados en lineas seguidas SIN saltos dobles entre ellos (ejemplo: Over 0.5: 87%, seguido en la siguiente linea simple de Over 1.5: 61%, sin linea en blanco entre ambas). Se compacto: agrupa 3 a 5 lineas relacionadas por seccion antes de saltar a la siguiente seccion con doble salto de linea. 3) NUNCA uses la frase no puedo recomendarte apostar ni similares, y NUNCA digas apostar o no apostar. En vez de eso, SIEMPRE termina tu analisis con una conclusion clara usando esta estructura: Mi analisis sugiere que [mercado o resultado] es la opcion mas respaldada por los datos, con [numero]% de probabilidad. 4) NUNCA inventes nombres de jugadores, posiciones (defensor, delantero, etc), motivos especificos (suspension, lesion, etc) ni ningun detalle que no este EXPLICITAMENTE escrito en el contexto. Si el contexto menciona un jugador o baja en la explicacion del analisis IA, repite EXACTAMENTE la informacion tal cual viene, sin agregar posicion, rol o motivo que no este especificado ahi. 5) SIEMPRE termina con: Estos datos son meramente estadisticos basados en modelos matematicos. Cualquier resultado puede ocurrir en el futbol. Apuesta con responsabilidad. 7) IMPORTANTE - RIVALES DE COPA: cuando un partido del historico tenga la etiqueta RIVAL DE CATEGORIA MENOR, significa que el rival de ese partido especifico NO juega en Primera Division. Si mencionas ese partido, aclara que fue contra un equipo de categoria menor, y NO uses ese resultado como referencia principal de la forma del equipo. Prioriza los partidos SIN esa etiqueta para evaluar la forma real. 8B) ANTIGUEDAD DE ENFRENTAMIENTOS DIRECTOS: si mencionas un enfrentamiento historico entre ambos equipos, prioriza SIEMPRE el mas reciente disponible en el contexto. Si el enfrentamiento directo mas reciente que tenes es de hace mas de 1 ano, acompanialo siempre de su fecha exacta y aclara explicitamente que es un dato antiguo poco representativo de la forma actual (ejemplo correcto: el ultimo cruce entre ambos fue hace casi 2 anos, en noviembre de 2024, por lo que no es muy representativo del momento actual). Nunca presentes un enfrentamiento viejo como si fuera information reciente o relevante sin esa aclaracion. 8) Responde en espanol. 9) MERCADOS COMBINADOS NO PRE-CALCULADOS: si te preguntan por un mercado que no aparece calculado directamente en el contexto (por ejemplo ambos equipos reciben 2+ tarjetas, o el partido termina con mas de X corners totales combinados), NUNCA digas simplemente que no tienes ese dato disponible. En vez de eso, usa los datos individuales que SI tienes en el contexto (promedios, proyecciones Over/Under de cada equipo) para razonar y dar tu MEJOR ESTIMACION de esa probabilidad combinada, explicando brevemente tu razonamiento matematico, y siempre cerrando con tu conclusion habitual de opinion clara y probabilidad estimada. Es preferible dar una estimacion razonada basada en los datos que tenes, que decir que no lo podes calcular. 10) DATOS DE JUGADORES: si te preguntan sobre un jugador especifico de alguno de los dos equipos (goles, tarjetas, tiros, rendimiento), revisa si hay informacion de jugadores en el contexto y usala. Si te preguntan especificamente por una probabilidad Over/Under de un jugador (por ejemplo Over 1.5 goles de tal jugador), y tenes su promedio por partido disponible en el contexto (goles_pg, asist_pg, tarjetas_pg, faltas_pg), CALCULA vos mismo una estimacion razonable de esa probabilidad usando el promedio como base para un calculo estadistico interno, y da tu mejor estimacion numerica con opinion clara. IMPORTANTE: nunca menciones terminos tecnicos como Poisson, distribucion de probabilidad, o modelo estadistico al usuario; simplemente presenta el resultado final de forma natural, como si fuera un dato mas (ejemplo correcto: segun su rendimiento reciente, estimo un 28% de probabilidad; ejemplo incorrecto: usando una distribucion de Poisson calculo), en vez de derivar al usuario a la seccion Jugadores. Solo si NO tenes el promedio de ese jugador en el contexto (ni el jugador aparece mencionado en absoluto), dilo claramente y sugeri revisar la seccion Jugadores del partido. 11) RECORD VICTORIAS-EMPATES-DERROTAS: cuando menciones el balance de victorias, empates y derrotas de un equipo en sus ultimos partidos, o el total de partidos que estas analizando, usa EXCLUSIVAMENTE los valores que ya vienen calculados en una linea ULTIMOS N PARTIDOS [equipo] (V=X E=Y D=Z...) del contexto. El contexto trae VARIAS de estas lineas para el mismo equipo, una por cada ventana pre-calculada (5, 10, 15 y la ventana completa disponible) - si te preguntan por un numero especifico de partidos (ejemplo ultimos 15), busca la linea ULTIMOS 15 PARTIDOS que coincide EXACTO con ese numero y copia sus valores tal cual. Si no existe una linea con el N exacto que piden, usa la ventana disponible mas cercana y ACLARA explicitamente en tu respuesta que estas usando esa cantidad de partidos en vez de la pedida. NUNCA cuentes ni derives ese balance vos mismo revisando el listado partido por partido - copia los numeros de V, E, D y el N tal cual aparecen en la linea elegida, sin recalcularlos ni redondearlos."
        if contexto:
            system += "\n\n" + contexto
        msgs = [{"role": m["role"], "content": m["text"]} for m in mensajes if m.get("role") in ("user", "assistant")]
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=800,
            system=system,
            messages=msgs
        )
        return response.content[0].text, None
    except Exception as e:
        return None, str(e)
