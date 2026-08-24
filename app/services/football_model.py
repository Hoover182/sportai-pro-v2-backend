import numpy as np
import pandas as pd
from fifa_ranking import ajuste_fifa
from liga_ranking import ajuste_liga_clubes
from value_bet import normalizar_std

# Minimos y maximos realistas por equipo
# Constantes para ligas de clubes
GOLES_MIN = 0.7
GOLES_MAX = 3.5
CORNERS_MIN = 3.0
CORNERS_MAX = 9.0     # subido de 8 a 9 - equipos top promedian 6-7
TARJETAS_MIN = 0.5    # por equipo
TARJETAS_MAX = 4.0    # por equipo

# Constantes especificas para torneos de selecciones (Mundial, Copas)
# Basadas en datos reales del Mundial 2026: 2.97 goles, 8.96 corners, 2.53 tarjetas por partido
TORNEOS_SELECCIONES = ["Mundial 2026", "Copa America", "Eurocopa", "Nations League"]
GOLES_MIN_SELECC    = 0.8
GOLES_MAX_SELECC    = 3.2   # partidos eliminatorios son mas cerrados
CORNERS_MIN_SELECC  = 3.5
CORNERS_MAX_SELECC  = 10.0  # mundial 2026 promedia 8.96
TARJETAS_MIN_SELECC = 0.8   # mundial 2026 promedia 2.53 totales = 1.27 por equipo
TARJETAS_MAX_SELECC = 3.5   # por equipo


def obtener_partidos_equipo(df, equipo, n=10):
    partidos = df[
        (df["equipo_local"] == equipo) |
        (df["equipo_visitante"] == equipo)
    ].copy()
    if "estado" in partidos.columns:
        partidos = partidos[partidos["estado"].isin(["FT", "AET", "PEN"])]
    return partidos.sort_values("fecha", ascending=False).head(n)


def _historial_equipo(df, equipo):
    """TODO el historial FT/AET/PEN de un equipo (local o visitante),
    ordenado por fecha descendente, SIN truncar a n -- un unico
    filtrado sobre el DataFrame completo (~20k filas), reutilizado
    despues para derivar la ventana mezclada, la ventana por condicion,
    y las versiones "con stats reales" de cada una, sin volver a barrer
    el DataFrame entero por cada una (antes: 4 pasadas completas por
    equipo por partido -- con ~70 partidos/dia x 2 equipos, eran ~560
    pasadas por request. Medido: bajo el tiempo de estadisticas_equipo_
    ultimos10() con condicion de val a val (ver commit))."""
    partidos = df[
        (df["equipo_local"] == equipo) |
        (df["equipo_visitante"] == equipo)
    ].copy()
    if "estado" in partidos.columns:
        partidos = partidos[partidos["estado"].isin(["FT", "AET", "PEN"])]
    return partidos.sort_values("fecha", ascending=False)


def _con_stats(partidos, n=10):
    """Subconjunto con stats reales (corners o tarjetas > 0) de un
    historial YA filtrado por equipo -- mismo criterio que
    obtener_partidos_con_stats(), pero operando sobre un subset chico
    en vez de barrer el DataFrame completo de nuevo."""
    con_stats = partidos[
        (partidos["corners_local"] + partidos["corners_visitante"] > 0) |
        (partidos["tarjetas_local"] + partidos["tarjetas_visitante"] > 0)
    ]
    return con_stats.head(n)


# Las 23 ligas domesticas top de nivel 1 (mismo criterio que LIGAS_NIVEL_1 en
# api_to_csv.py). Se usan para calcular la liga "principal" de un equipo por
# moda, en vez de por el ultimo partido jugado (que puede ser de copa,
# amistoso o continental y no representa su competencia habitual).
LIGAS_DOMESTICAS_NIVEL1 = [
    "Premier League", "La Liga", "Serie A", "Bundesliga", "Ligue 1", "Primeira Liga",
    "Eredivisie", "Pro League Belgica", "Premier League Egipto", "Pro League Arabia",
    "Super Lig Turquia", "Liga Profesional Argentina", "Brasileirao", "Liga Colombia",
    "Primera Division Chile", "Primera Division Uruguay", "Primera Division Peru",
    "Liga Pro Ecuador", "Primera Division Venezuela", "Primera Division Bolivia",
    "Division Profesional Paraguay", "Liga MX", "MLS",
]


def _liga_principal_equipo(df, equipo):
    """Liga domestica de nivel 1 mas frecuente del equipo (moda entre sus
    partidos en esas 23 ligas), o None si no tiene ninguno."""
    partidos_dom = df[
        ((df["equipo_local"] == equipo) | (df["equipo_visitante"] == equipo)) &
        (df["liga"].isin(LIGAS_DOMESTICAS_NIVEL1))
    ]
    if partidos_dom.empty:
        return None
    return partidos_dom["liga"].value_counts().idxmax()


# Segundas divisiones -- solo existen en el CSV como historial de equipos
# puntuales que aparecen de rival de un equipo trackeado (ver LIGAS_VALIDAS
# en data_loader.py). Se suman a LIGAS_DOMESTICAS_NIVEL1 para poder
# resolver la "liga de referencia" tambien de esos equipos (ej. Coventry
# -> Championship), no solo de los de primera.
LIGAS_SEGUNDA_DIVISION = [
    "Championship", "Segunda Division Espana", "Ligue 2", "Eerste Divisie",
    "2. Bundesliga", "3. Liga", "Second League Egipto", "Primera B Colombia",
    "Primera B Metropolitana", "Serie B Italia", "Serie B Brasil",
]

LIGAS_DOMESTICAS_TODAS = LIGAS_DOMESTICAS_NIVEL1 + LIGAS_SEGUNDA_DIVISION


def _liga_referencia_equipo(df, equipo):
    """Liga domestica (de cualquier nivel, no solo primera) mas frecuente
    del equipo -- usada para el ajuste de fuerza de liga entre clubes
    (ver liga_ranking.ajuste_liga_clubes). A diferencia de
    _liga_principal_equipo(), tambien resuelve equipos de segunda
    division como Coventry (Championship)."""
    partidos_dom = df[
        ((df["equipo_local"] == equipo) | (df["equipo_visitante"] == equipo)) &
        (df["liga"].isin(LIGAS_DOMESTICAS_TODAS))
    ]
    if partidos_dom.empty:
        return None
    return partidos_dom["liga"].value_counts().idxmax()


def n_efectivo_estimacion(n_base, n_condicion, min_partidos_condicion=10):
    """Cantidad "equivalente" de partidos reales que respaldan un
    promedio ya blendeado entre la ventana mezclada (n_base partidos) y
    la ventana por condicion local/visitante (n_condicion partidos) --
    mismo peso que usa el blend de los promedios en si (ver
    estadisticas_equipo_ultimos10), aplicado ahora al TAMANO de muestra
    en vez de al valor. Se usa como "k" (confianza) en la mezcla
    Gamma-Poisson de simulator.py, para no tratar un promedio de pocos
    partidos como si fuera la tasa exacta y verdadera del equipo.

    Medido en un backtest de 1459 partidos reales (FT, con datos
    completos, simulados con SOLO los datos disponibles antes de cada
    partido): sin este ajuste el modelo daba probabilidades
    sistematicamente ~8-11 puntos mas extremas que el acierto real en
    los mercados de mayor confianza del Top3 (85%+). Probando k=n_base,
    k=n_base/2 y k=8 fijo contra ese mismo backtest, k=n_efectivo (esta
    funcion) fue el que mas cerca dejo la probabilidad dicha del
    acierto real (gap de +8.0 a -1.3 puntos), sin sobrecorregir para el
    otro lado como n_base/2."""
    peso_cond = min(n_condicion / min_partidos_condicion, 1.0)
    return n_base * (1 - peso_cond) + n_condicion * peso_cond


def obtener_liga_partido(df, local, visitante):
    """Determina la liga del partido que se esta analizando (Boca vs River
    en Liga Profesional Argentina, por ejemplo), en 3 niveles de confianza:

    1) Si hay un partido programado (NS) para este cruce exacto, esa fila
       ES el partido que se va a simular - su liga es la fuente mas
       confiable. Si hay mas de uno (ej. revancha de copa el mismo dia que
       liga), se usa el mas proximo en fecha al momento actual.
    2) Si no hay NS para este cruce, se usa la liga domestica nivel1 mas
       frecuente del equipo local (moda), mas estable que "el ultimo
       partido jugado" porque no cambia semana a semana por congestion de
       fixturas entre liga/copa/continental.
    3) Ultimo recurso: el ultimo partido jugado del equipo local en
       cualquier competencia (comportamiento previo a este fix)."""
    cruce = df[
        ((df["equipo_local"] == local) & (df["equipo_visitante"] == visitante)) |
        ((df["equipo_local"] == visitante) & (df["equipo_visitante"] == local))
    ]
    pendientes = cruce[cruce["estado"] == "NS"] if "estado" in cruce.columns else cruce.iloc[0:0]
    if not pendientes.empty:
        fechas = pd.to_datetime(pendientes["fecha"], errors="coerce", utc=True)
        if fechas.notna().any():
            ahora = pd.Timestamp.now(tz="UTC")
            idx_mas_cercano = (fechas - ahora).abs().idxmin()
            return pendientes.loc[idx_mas_cercano, "liga"]
        return pendientes.iloc[0]["liga"]

    liga_dom = _liga_principal_equipo(df, local)
    if liga_dom:
        return liga_dom

    partidos = obtener_partidos_equipo(df, local, n=1)
    return partidos.iloc[0]["liga"] if not partidos.empty else None


def obtener_partidos_con_stats(df, equipo, n=10):
    """Retorna SOLO partidos con stats reales (corners o tarjetas > 0)."""
    partidos = df[
        (df["equipo_local"] == equipo) |
        (df["equipo_visitante"] == equipo)
    ].copy()
    if "estado" in partidos.columns:
        partidos = partidos[partidos["estado"].isin(["FT", "AET", "PEN"])]
    partidos_con_stats = partidos[
        (partidos["corners_local"] + partidos["corners_visitante"] > 0) |
        (partidos["tarjetas_local"] + partidos["tarjetas_visitante"] > 0)
    ]
    return partidos_con_stats.sort_values("fecha", ascending=False).head(n)


def _promedio_liga_con_stats(df, liga):
    """Calcula promedios de liga usando SOLO partidos con stats reales."""
    df_liga = df[df["liga"] == liga].copy()
    if "estado" in df_liga.columns:
        df_liga = df_liga[df_liga["estado"].isin(["FT", "AET", "PEN"])]

    df_liga_stats = df_liga[
        (df_liga["corners_local"] + df_liga["corners_visitante"] > 0) |
        (df_liga["tarjetas_local"] + df_liga["tarjetas_visitante"] > 0)
    ]

    resultado = {
        "goles": 1.3,
        "corners": 5.0,
        "tarjetas": 1.5,
        "tiros_arco": 4.0,
        "tiros_total": 12.0
    }

    if not df_liga.empty:
        g = (df_liga["goles_local"].mean() + df_liga["goles_visitante"].mean()) / 2
        if not np.isnan(g):
            resultado["goles"] = float(np.clip(g, GOLES_MIN, GOLES_MAX))

    if not df_liga_stats.empty:
        c = (df_liga_stats["corners_local"].mean() + df_liga_stats["corners_visitante"].mean()) / 2
        t = (df_liga_stats["tarjetas_local"].mean() + df_liga_stats["tarjetas_visitante"].mean()) / 2
        ta = (df_liga_stats["tiros_arco_local"].mean() + df_liga_stats["tiros_arco_visitante"].mean()) / 2

        if not np.isnan(c): resultado["corners"] = float(np.clip(c, CORNERS_MIN, CORNERS_MAX))
        if not np.isnan(t): resultado["tarjetas"] = float(np.clip(t, TARJETAS_MIN, TARJETAS_MAX))
        if not np.isnan(ta): resultado["tiros_arco"] = float(ta)

        if "tiros_total_local" in df_liga_stats.columns:
            tt = (df_liga_stats["tiros_total_local"].mean() + df_liga_stats["tiros_total_visitante"].mean()) / 2
            if not np.isnan(tt): resultado["tiros_total"] = float(tt)

    return resultado


def _promedios_ponderados_condicion(historial, equipo, condicion, n=10, liga=None):
    """Promedios ponderados por fuerza FIFA del rival para los ultimos n
    partidos de un equipo EN UNA CONDICION especifica (local o
    visitante) -- mismo criterio de ponderacion y de exclusion null por
    metrica que la ventana general de estadisticas_equipo_ultimos10(),
    pero sin fallback a promedio de liga (ese ya lo aporta el blend con
    la ventana mezclada en el caller). Devuelve None por metrica si no
    hay ningun partido con ese dato, nunca un 0 falso.

    historial: TODO el historial del equipo ya filtrado por
    _historial_equipo() (no el DataFrame completo) -- evita volver a
    barrer las ~20k filas del CSV para sacar la version por condicion,
    ya que la ventana mezclada de mas arriba ya tuvo que filtrar lo
    mismo.

    liga: si se pasa, restringe la ventana de condicion a partidos de
    ESA MISMA liga/competencia (la del partido que se esta simulando).
    A diferencia de la ventana mezclada (que junta los ultimos 10
    partidos de CUALQUIER competencia y por eso se mantiene reciente),
    la ventana por condicion necesita ir mas atras en el tiempo para
    juntar 10 partidos de una sola condicion, lo que la hace mas
    propensa a cruzar a copas (alineaciones rotadas, resultados
    atipicos) o a otra division (equipo recien ascendido/descendido).
    Sin este filtro esos partidos entraban con el mismo peso que
    cualquier otro. Medido en vivo (Elche vs Barcelona, 2026-08-23):
    el gol_contra de visitante de Barcelona bajaba de 1.50 a 1.25 al
    excluir una goleada 0-4 de Copa del Rey ante Atletico Madrid."""
    if condicion == "local":
        historial_condicion = historial[historial["equipo_local"] == equipo]
    else:
        historial_condicion = historial[historial["equipo_visitante"] == equipo]
    if liga:
        historial_condicion = historial_condicion[historial_condicion["liga"] == liga]
    partidos = historial_condicion.head(n)
    partidos_stats = _con_stats(historial_condicion, n=n)

    try:
        from fifa_ranking import get_puntos_fifa, es_seleccion_nacional
        usar_peso_fifa = True
    except Exception:
        usar_peso_fifa = False

    goles_favor, goles_contra, pesos_partidos = [], [], []
    for _, row in partidos.iterrows():
        if row["equipo_local"] == equipo:
            gf_val, gc_val, rival = row["goles_local"], row["goles_visitante"], str(row["equipo_visitante"])
        else:
            gf_val, gc_val, rival = row["goles_visitante"], row["goles_local"], str(row["equipo_local"])
        if pd.isna(gf_val) or pd.isna(gc_val):
            continue
        peso = 1.0
        if usar_peso_fifa and es_seleccion_nacional(equipo) and es_seleccion_nacional(rival):
            pts_equipo = get_puntos_fifa(equipo)
            pts_rival = get_puntos_fifa(rival)
            peso = max(0.3, min(2.0, pts_rival / max(pts_equipo, 1)))
        pesos_partidos.append(peso)
        goles_favor.append(float(gf_val) * peso)
        goles_contra.append(float(gc_val) * peso)

    corners_favor, corners_contra = [], []
    tarjetas_favor = []
    tiros_arco_favor, tiros_arco_contra = [], []
    tiros_total_favor, tiros_total_contra = [], []
    for _, row in partidos_stats.iterrows():
        if row["equipo_local"] == equipo:
            cf_val, cc_val = row["corners_local"], row["corners_visitante"]
            tf_val = row["tarjetas_local"]
            ta_f_val, ta_c_val = row["tiros_arco_local"], row["tiros_arco_visitante"]
            tt_f_val = row["tiros_total_local"] if "tiros_total_local" in row.index else None
            tt_c_val = row["tiros_total_visitante"] if "tiros_total_visitante" in row.index else None
            rival_stats = str(row["equipo_visitante"])
        else:
            cf_val, cc_val = row["corners_visitante"], row["corners_local"]
            tf_val = row["tarjetas_visitante"]
            ta_f_val, ta_c_val = row["tiros_arco_visitante"], row["tiros_arco_local"]
            tt_f_val = row["tiros_total_visitante"] if "tiros_total_visitante" in row.index else None
            tt_c_val = row["tiros_total_local"] if "tiros_total_local" in row.index else None
            rival_stats = str(row["equipo_local"])

        peso_stats = 1.0
        if usar_peso_fifa and es_seleccion_nacional(equipo) and es_seleccion_nacional(rival_stats):
            pts_equipo = get_puntos_fifa(equipo)
            pts_rival = get_puntos_fifa(rival_stats)
            peso_stats = max(0.3, min(2.0, pts_rival / max(pts_equipo, 1)))

        if pd.notna(cf_val):   corners_favor.append(float(cf_val) * peso_stats)
        if pd.notna(cc_val):   corners_contra.append(float(cc_val) * peso_stats)
        if pd.notna(tf_val):   tarjetas_favor.append(float(tf_val) * peso_stats)
        if pd.notna(ta_f_val): tiros_arco_favor.append(float(ta_f_val) * peso_stats)
        if pd.notna(ta_c_val): tiros_arco_contra.append(float(ta_c_val) * peso_stats)
        if pd.notna(tt_f_val): tiros_total_favor.append(float(tt_f_val) * peso_stats)
        if pd.notna(tt_c_val): tiros_total_contra.append(float(tt_c_val) * peso_stats)

    def _media(valores, pesos=None):
        if not valores:
            return None
        if pesos:
            suma_pesos = sum(pesos)
            return sum(valores) / suma_pesos if suma_pesos > 0 else float(np.mean(valores))
        return float(np.mean(valores))

    return {
        "n_partidos": len(partidos),
        "goles_favor": _media(goles_favor, pesos_partidos),
        "goles_contra": _media(goles_contra, pesos_partidos),
        "corners_favor": _media(corners_favor),
        "corners_contra": _media(corners_contra),
        "tarjetas_favor": _media(tarjetas_favor),
        "tiros_arco_favor": _media(tiros_arco_favor),
        "tiros_arco_contra": _media(tiros_arco_contra),
        "tiros_total_favor": _media(tiros_total_favor),
        "tiros_total_contra": _media(tiros_total_contra),
    }


def estadisticas_equipo_ultimos10(df, equipo, liga=None, min_partidos=3, condicion=None):
    """liga: liga del partido que se esta analizando (ver obtener_liga_partido).
    Si no se pasa (compatibilidad con llamadas existentes que no la conocen),
    se infiere con _liga_principal_equipo() en vez de usar el ultimo partido
    jugado del equipo, que puede ser de una competencia distinta.

    condicion: "local" o "visitante" -- la condicion que el equipo va a
    tener en el partido que se esta simulando. Si se pasa, blendea el
    promedio general (mezclado, como siempre) con el promedio SOLO de
    esa condicion, peso proporcional a cuanta muestra real hay en esa
    condicion (sin tope en 1.0, a diferencia del blend de xG: no es un
    dato complementario, es la categoria correcta de dato). Medido en
    vivo: 32.9% de los equipos trackeados tienen una diferencia >0.5
    goles a favor entre jugar de local y de visitante. Si no se pasa
    (compatibilidad), comportamiento identico al de antes de este fix."""
    historial = _historial_equipo(df, equipo)
    partidos = historial.head(10)
    partidos_stats = _con_stats(historial, n=10)

    if partidos.empty:
        return None

    goles_favor = []
    goles_contra = []
    corners_favor = []
    corners_contra = []
    tarjetas_favor = []
    tiros_arco_favor = []
    tiros_arco_contra = []
    tiros_total_favor = []
    tiros_total_contra = []
    xg_favor = []
    xg_contra = []

    victorias = empates = derrotas = 0

    # Goles con todos los partidos - ponderados por fuerza del rival (ranking FIFA)
    try:
        from fifa_ranking import get_puntos_fifa, es_seleccion_nacional
        usar_peso_fifa = True
    except Exception:
        usar_peso_fifa = False

    pesos_partidos = []
    for _, row in partidos.iterrows():
        if row["equipo_local"] == equipo:
            gf_val = row["goles_local"]
            gc_val = row["goles_visitante"]
            rival = str(row["equipo_visitante"])
        else:
            gf_val = row["goles_visitante"]
            gc_val = row["goles_local"]
            rival = str(row["equipo_local"])

        # NaN es "truthy" en Python, asi que "valor or 0" NO lo reemplaza
        # por 0 -- hay que chequear pd.notna() explicitamente. Los goles
        # casi nunca faltan (0 casos en el CSV actual), pero se protege
        # igual por consistencia con el resto del pipeline. Si falta
        # cualquiera de los dos, el partido se excluye de este calculo (no
        # se puede saber si gano/empato/perdio sin ambos goles).
        if pd.isna(gf_val) or pd.isna(gc_val):
            continue
        gf = float(gf_val)
        gc = float(gc_val)

        # Calcular peso segun fuerza del rival
        peso = 1.0
        if usar_peso_fifa and es_seleccion_nacional(equipo) and es_seleccion_nacional(rival):
            pts_equipo = get_puntos_fifa(equipo)
            pts_rival  = get_puntos_fifa(rival)
            # Rival fuerte (mas puntos) -> peso mayor (partido mas valioso)
            # Rival debil (menos puntos) -> peso menor (partido menos valioso)
            ratio = pts_rival / max(pts_equipo, 1)
            peso = max(0.3, min(2.0, ratio))

        pesos_partidos.append(peso)
        goles_favor.append(gf * peso)
        goles_contra.append(gc * peso)

        if gf > gc: victorias += 1
        elif gf == gc: empates += 1
        else: derrotas += 1

    # Corners, tarjetas y tiros solo con partidos con stats reales. Cada
    # metrica se excluye INDIVIDUALMENTE si vino null (un partido puede
    # tener corners pero no tarjetas, o viceversa) en vez de contarla como
    # 0 real -- mismo criterio que _stats_n_equipo() en futbol_service.py.
    # Ponderados por fuerza del rival (ranking FIFA) igual que goles.
    for _, row in partidos_stats.iterrows():
        if row["equipo_local"] == equipo:
            cf_val, cc_val = row["corners_local"], row["corners_visitante"]
            tf_val = row["tarjetas_local"]
            ta_f_val, ta_c_val = row["tiros_arco_local"], row["tiros_arco_visitante"]
            tt_f_val = row["tiros_total_local"] if "tiros_total_local" in row.index else None
            tt_c_val = row["tiros_total_visitante"] if "tiros_total_visitante" in row.index else None
            xg_f_val = row["xg_local"] if "xg_local" in row.index else None
            xg_c_val = row["xg_visitante"] if "xg_visitante" in row.index else None
            rival_stats = str(row["equipo_visitante"])
        else:
            cf_val, cc_val = row["corners_visitante"], row["corners_local"]
            tf_val = row["tarjetas_visitante"]
            ta_f_val, ta_c_val = row["tiros_arco_visitante"], row["tiros_arco_local"]
            tt_f_val = row["tiros_total_visitante"] if "tiros_total_visitante" in row.index else None
            tt_c_val = row["tiros_total_local"] if "tiros_total_local" in row.index else None
            xg_f_val = row["xg_visitante"] if "xg_visitante" in row.index else None
            xg_c_val = row["xg_local"] if "xg_local" in row.index else None
            rival_stats = str(row["equipo_local"])

        # Peso por rival FIFA (mismo sistema que goles)
        peso_stats = 1.0
        if usar_peso_fifa and es_seleccion_nacional(equipo) and es_seleccion_nacional(rival_stats):
            pts_equipo = get_puntos_fifa(equipo)
            pts_rival  = get_puntos_fifa(rival_stats)
            ratio = pts_rival / max(pts_equipo, 1)
            peso_stats = max(0.3, min(2.0, ratio))

        if pd.notna(cf_val):   corners_favor.append(float(cf_val) * peso_stats)
        if pd.notna(cc_val):   corners_contra.append(float(cc_val) * peso_stats)
        if pd.notna(tf_val):   tarjetas_favor.append(float(tf_val) * peso_stats)
        if pd.notna(ta_f_val): tiros_arco_favor.append(float(ta_f_val) * peso_stats)
        if pd.notna(ta_c_val): tiros_arco_contra.append(float(ta_c_val) * peso_stats)
        if pd.notna(tt_f_val): tiros_total_favor.append(float(tt_f_val) * peso_stats)
        if pd.notna(tt_c_val): tiros_total_contra.append(float(tt_c_val) * peso_stats)
        if pd.notna(xg_f_val): xg_favor.append(float(xg_f_val) * peso_stats)
        if pd.notna(xg_c_val): xg_contra.append(float(xg_c_val) * peso_stats)

    n_partidos = len(partidos)
    # n_partidos_stats = partidos con stats reales verificados
    n_partidos_stats = len(partidos_stats)
    pocos_datos = n_partidos < min_partidos

    liga = liga or _liga_principal_equipo(df, equipo) or (partidos["liga"].iloc[0] if not partidos.empty else "")
    prom_liga = _promedio_liga_con_stats(df, liga)

    # Sin stats reales usar promedio de liga
    if not corners_favor:
        corners_favor = [prom_liga["corners"]]
        corners_contra = [prom_liga["corners"]]
        tarjetas_favor = [prom_liga["tarjetas"]]
        tiros_arco_favor = [prom_liga["tiros_arco"]]
        tiros_arco_contra = [prom_liga["tiros_arco"]]
        tiros_total_favor = [prom_liga["tiros_total"]]
        tiros_total_contra = [prom_liga["tiros_total"]]

    if pocos_datos:
        peso_real = n_partidos / min_partidos
        peso_liga = 1 - peso_real

        # Medias ponderadas: suma(valor*peso) / suma(pesos) para normalizar
        suma_pesos = sum(pesos_partidos) if pesos_partidos else len(goles_favor)
        n_goles = len(goles_favor)
        media_gf  = (sum(goles_favor)  / suma_pesos if suma_pesos > 0 else np.mean(goles_favor))  * peso_real + prom_liga["goles"]      * peso_liga
        media_gc  = (sum(goles_contra) / suma_pesos if suma_pesos > 0 else np.mean(goles_contra)) * peso_real + prom_liga["goles"]      * peso_liga
        media_cf  = np.mean(corners_favor)  * peso_real + prom_liga["corners"]    * peso_liga
        media_cc  = np.mean(corners_contra) * peso_real + prom_liga["corners"]    * peso_liga
        media_tf  = np.mean(tarjetas_favor) * peso_real + prom_liga["tarjetas"]   * peso_liga
        media_ta_f = np.mean(tiros_arco_favor)  * peso_real + prom_liga["tiros_arco"] * peso_liga
        media_ta_c = np.mean(tiros_arco_contra) * peso_real + prom_liga["tiros_arco"] * peso_liga
        media_tt_f = np.mean(tiros_total_favor)  * peso_real + prom_liga["tiros_total"] * peso_liga
        media_tt_c = np.mean(tiros_total_contra) * peso_real + prom_liga["tiros_total"] * peso_liga
    else:
        suma_pesos = sum(pesos_partidos) if pesos_partidos else len(goles_favor)
        media_gf   = sum(goles_favor)  / suma_pesos if suma_pesos > 0 else np.mean(goles_favor)
        media_gc   = sum(goles_contra) / suma_pesos if suma_pesos > 0 else np.mean(goles_contra)
        media_cf   = np.mean(corners_favor)  if corners_favor  else 0.0
        media_cc   = np.mean(corners_contra) if corners_contra else 0.0
        media_tf   = np.mean(tarjetas_favor) if tarjetas_favor else 0.0
        media_ta_f = np.mean(tiros_arco_favor)   if tiros_arco_favor   else 0.0
        media_ta_c = np.mean(tiros_arco_contra)  if tiros_arco_contra  else 0.0
        media_tt_f = np.mean(tiros_total_favor)  if tiros_total_favor  else 0.0
        media_tt_c = np.mean(tiros_total_contra) if tiros_total_contra else 0.0

    # Blend con xG (expected goals) cuando hay cobertura real -- fallback
    # total a goles reales si no. Cobertura muy despareja segun competencia
    # (100% en Premier League/La Liga/Serie A, 0% en Champions League y en
    # casi todas las copas, verificado en vivo), asi que el peso es
    # proporcional a cuantos de los ultimos partidos realmente tienen el
    # dato -- nunca un peso fijo. Tope de 50%: el resultado real siempre
    # sigue siendo el ancla, xG solo lo suaviza (no sabe de roja temprana,
    # atajadon puntual, etc).
    MIN_PARTIDOS_XG = 3
    PESO_XG_MAX = 0.5
    n_partidos_xg = len(xg_favor)
    if n_partidos_xg >= MIN_PARTIDOS_XG and n_partidos > 0:
        peso_xg = min(n_partidos_xg / n_partidos, PESO_XG_MAX)
        media_gf = media_gf * (1 - peso_xg) + np.mean(xg_favor)  * peso_xg
        media_gc = media_gc * (1 - peso_xg) + np.mean(xg_contra) * peso_xg

    # Blend por condicion (local/visitante) -- peso proporcional a cuanta
    # muestra real hay en esa condicion especifica, SIN tope en 1.0 (a
    # diferencia de xG): con muestra completa (10 partidos en esa
    # condicion) el promedio general mezclado queda completamente
    # reemplazado, no es un dato complementario sino la categoria
    # correcta. Aplica a las 4 metricas principales (goles, corners,
    # tarjetas, tiros) con la misma logica.
    MIN_PARTIDOS_CONDICION = 10
    n_partidos_condicion = 0
    if condicion in ("local", "visitante"):
        prom_condicion = _promedios_ponderados_condicion(historial, equipo, condicion, n=10, liga=liga)
        n_partidos_condicion = prom_condicion["n_partidos"]
        if n_partidos_condicion > 0:
            peso_cond = min(n_partidos_condicion / MIN_PARTIDOS_CONDICION, 1.0)
            if prom_condicion["goles_favor"] is not None:
                media_gf = media_gf * (1 - peso_cond) + prom_condicion["goles_favor"] * peso_cond
            if prom_condicion["goles_contra"] is not None:
                media_gc = media_gc * (1 - peso_cond) + prom_condicion["goles_contra"] * peso_cond
            if prom_condicion["corners_favor"] is not None:
                media_cf = media_cf * (1 - peso_cond) + prom_condicion["corners_favor"] * peso_cond
            if prom_condicion["corners_contra"] is not None:
                media_cc = media_cc * (1 - peso_cond) + prom_condicion["corners_contra"] * peso_cond
            if prom_condicion["tarjetas_favor"] is not None:
                media_tf = media_tf * (1 - peso_cond) + prom_condicion["tarjetas_favor"] * peso_cond
            if prom_condicion["tiros_arco_favor"] is not None:
                media_ta_f = media_ta_f * (1 - peso_cond) + prom_condicion["tiros_arco_favor"] * peso_cond
            if prom_condicion["tiros_arco_contra"] is not None:
                media_ta_c = media_ta_c * (1 - peso_cond) + prom_condicion["tiros_arco_contra"] * peso_cond
            if prom_condicion["tiros_total_favor"] is not None:
                media_tt_f = media_tt_f * (1 - peso_cond) + prom_condicion["tiros_total_favor"] * peso_cond
            if prom_condicion["tiros_total_contra"] is not None:
                media_tt_c = media_tt_c * (1 - peso_cond) + prom_condicion["tiros_total_contra"] * peso_cond

    # Detectar si es torneo de selecciones para usar constantes correctas
    es_torneo_selecc = liga in TORNEOS_SELECCIONES

    # Aplicar limites realistas segun tipo de competicion
    if es_torneo_selecc:
        media_gf  = float(np.clip(media_gf,  GOLES_MIN_SELECC,    GOLES_MAX_SELECC))
        media_gc  = float(np.clip(media_gc,  GOLES_MIN_SELECC,    GOLES_MAX_SELECC))
        media_cf  = float(np.clip(media_cf,  CORNERS_MIN_SELECC,  CORNERS_MAX_SELECC))
        media_cc  = float(np.clip(media_cc,  CORNERS_MIN_SELECC,  CORNERS_MAX_SELECC))
        media_tf  = float(np.clip(media_tf,  TARJETAS_MIN_SELECC, TARJETAS_MAX_SELECC))
    else:
        media_gf  = float(np.clip(media_gf,  GOLES_MIN,    GOLES_MAX))
        media_gc  = float(np.clip(media_gc,  GOLES_MIN,    GOLES_MAX))
        media_cf  = float(np.clip(media_cf,  CORNERS_MIN,  CORNERS_MAX))
        media_cc  = float(np.clip(media_cc,  CORNERS_MIN,  CORNERS_MAX))
        media_tf  = float(np.clip(media_tf,  TARJETAS_MIN, TARJETAS_MAX))

    return {
        "log": partidos,
        "pocos_datos": pocos_datos,
        "n_partidos": n_partidos,
        "n_partidos_stats": n_partidos_stats,
        "n_partidos_xg": n_partidos_xg,
        "condicion": condicion,
        "n_partidos_condicion": n_partidos_condicion,
        "goles_favor": media_gf,
        "goles_contra": media_gc,
        "std_goles_favor":   normalizar_std(np.std(goles_favor),    0.35),
        "std_goles_contra":  normalizar_std(np.std(goles_contra),   0.35),
        "corners_favor": media_cf,
        "corners_contra": media_cc,
        "std_corners_favor": normalizar_std(np.std(corners_favor),  1.0),
        "tarjetas_favor": media_tf,
        "std_tarjetas_favor": normalizar_std(np.std(tarjetas_favor), 0.8),
        "tiros_arco_favor": media_ta_f,
        "tiros_arco_contra": media_ta_c,
        "tiros_total_favor": media_tt_f,
        "tiros_total_contra": media_tt_c,
        "victorias": victorias,
        "empates": empates,
        "derrotas": derrotas,
        "puntos": victorias * 3 + empates,
        "liga_referencia": _liga_referencia_equipo(df, equipo)
    }


def ultimos_enfrentamientos_directos(df, equipo_a, equipo_b, n=5):
    h2h = df[
        ((df["equipo_local"] == equipo_a) & (df["equipo_visitante"] == equipo_b)) |
        ((df["equipo_local"] == equipo_b) & (df["equipo_visitante"] == equipo_a))
    ].copy()
    if "estado" in h2h.columns:
        h2h = h2h[h2h["estado"].isin(["FT", "AET", "PEN"])]
    return h2h.sort_values("fecha", ascending=False).head(n)


def _peso_antiguedad_partido(fecha_partido, ahora=None):
    """Peso individual de UN partido segun su antiguedad -- mismo
    decaimiento (0 anios=100%, 1 anio=90%, 2 anios=70%, 3+ anios=50%
    piso) que ya se usaba para descontar el BLOQUE entero de H2H segun
    el cruce mas reciente, aplicado ahora partido por partido antes de
    promediar. Sin esto, un resultado de hace 2-3 anios pesaba
    exactamente igual que uno de hace 6 meses dentro del promedio (el
    descuento por antiguedad del bloque solo miraba la fecha del cruce
    MAS NUEVO, no la de cada partido individual) -- ver conversacion
    sobre el caso River Plate vs Velez Sarsfield, donde 2 goleadas de
    2024 (5-0 y 4-1) pesaban lo mismo que los 2 cruces mas parejos y
    recientes de 2025-2026."""
    fecha_partido = pd.to_datetime(fecha_partido)
    if ahora is None:
        ahora = pd.Timestamp.now(tz=fecha_partido.tzinfo) if fecha_partido.tzinfo is not None else pd.Timestamp.now()
    anios = (ahora - fecha_partido).days / 365.25
    return float(np.interp(anios, [0, 1, 2, 3], [1.0, 0.9, 0.7, 0.5]))


def _promedio_ponderado_pares(pares):
    """Promedio ponderado de una lista de (valor, peso) -- devuelve None
    si la lista esta vacia (mismo comportamiento que antes: el caller
    chequea "if valores_h2h" para decidir si hay datos)."""
    if not pares:
        return None
    suma_pesos = sum(p for _, p in pares)
    if suma_pesos <= 0:
        return sum(v for v, _ in pares) / len(pares)
    return sum(v * p for v, p in pares) / suma_pesos


def _promedios_h2h_por_equipo(h2h, columna, equipo_a):
    """Extrae los valores de una columna (goles o corners) del H2H
    separados por EQUIPO real, no por columna local/visitante -- los
    cruces historicos alternan de estadio temporada a temporada (ej. en
    5 partidos Espanyol-Real Madrid, Real Madrid jugo de local en 3 de
    los 5), asi que promediar ciegamente la columna "local" mezclaba los
    goles de ambos equipos segun quien jugaba en casa en CADA partido
    pasado, no segun el equipo local de HOY -- ver conversacion sobre el
    caso Espanyol vs Real Madrid.
    Retorna (pares_a, pares_b): pares (valor, peso_antiguedad) de
    equipo_a y de su rival, uno por partido donde el dato no sea nulo.
    peso_antiguedad viene de _peso_antiguedad_partido() -- el caller
    arma el promedio ponderado con _promedio_ponderado_pares()."""
    ahora = pd.Timestamp.now(tz="UTC")
    pares_a, pares_b = [], []
    for _, row in h2h.iterrows():
        val_local = row.get(f"{columna}_local")
        val_visit = row.get(f"{columna}_visitante")
        if row["equipo_local"] == equipo_a:
            v_a, v_b = val_local, val_visit
        elif row["equipo_visitante"] == equipo_a:
            v_a, v_b = val_visit, val_local
        else:
            continue
        peso = _peso_antiguedad_partido(row["fecha"], ahora)
        if pd.notna(v_a):
            pares_a.append((float(v_a), peso))
        if pd.notna(v_b):
            pares_b.append((float(v_b), peso))
    return pares_a, pares_b


def ajustar_medias_con_rival(stats_a, stats_b, h2h, equipo_local=None, equipo_visitante=None):
    # Base: promedio entre ataque propio y defensa rival
    goles_a   = (stats_a["goles_favor"]   + stats_b["goles_contra"])   / 2
    goles_b   = (stats_b["goles_favor"]   + stats_a["goles_contra"])   / 2
    corners_a = (stats_a["corners_favor"] + stats_b["corners_contra"]) / 2
    corners_b = (stats_b["corners_favor"] + stats_a["corners_contra"]) / 2
    tarjetas_total = stats_a["tarjetas_favor"] + stats_b["tarjetas_favor"]

    # Ajuste H2H - mas peso cuando hay mas partidos directos
    if not h2h.empty:
        n_h2h = len(h2h)
        # 1 partido=15%, 2=20%, 3=25%, 4+=30%
        peso_h2h = min(0.15 + (n_h2h - 1) * 0.05, 0.30)

        # Ajuste por antiguedad del H2H - el conjunto completo pesa menos
        # si el enfrentamiento mas reciente ya es viejo, aunque haya
        # varios partidos. Interpolacion entre 4 puntos de referencia:
        # 0 anos=100%, 1 ano=90%, 2 anos=70%, 3+ anos=50% (piso).
        try:
            fecha_mas_reciente = pd.to_datetime(h2h["fecha"]).max()
            if fecha_mas_reciente.tzinfo is not None:
                ahora_h2h = pd.Timestamp.now(tz=fecha_mas_reciente.tzinfo)
            else:
                ahora_h2h = pd.Timestamp.now()
            anios_desde_ultimo = (ahora_h2h - fecha_mas_reciente).days / 365.25
            multiplicador_antiguedad = np.interp(anios_desde_ultimo, [0, 1, 2, 3], [1.0, 0.9, 0.7, 0.5])
            peso_h2h = peso_h2h * multiplicador_antiguedad
        except Exception:
            pass

        peso_base = 1 - peso_h2h

        # Ajuste H2H para goles y corners -- separado por equipo real
        # (ver _promedios_h2h_por_equipo), no por columna local/
        # visitante. Sin equipo_local/equipo_visitante no hay forma de
        # saber que lado corresponde a cada equipo en cada cruce
        # historico, asi que se omite el ajuste antes que arriesgar la
        # mezcla (comportamiento previo a este fix).
        if equipo_local and equipo_visitante:
            # Cada partido del H2H pesa distinto DENTRO del promedio
            # segun su propia antiguedad (_peso_antiguedad_partido),
            # ademas del descuento de peso_h2h de arriba que ya aplica
            # al bloque completo -- sin esto, un resultado de hace 2-3
            # anios pesaba exactamente igual que uno de hace 6 meses en
            # el promedio (ver _promedios_h2h_por_equipo).
            goles_a_h2h, goles_b_h2h = _promedios_h2h_por_equipo(h2h, "goles", equipo_local)
            prom_goles_a_h2h = _promedio_ponderado_pares(goles_a_h2h)
            prom_goles_b_h2h = _promedio_ponderado_pares(goles_b_h2h)
            if prom_goles_a_h2h is not None:
                goles_a = goles_a * peso_base + prom_goles_a_h2h * peso_h2h
            if prom_goles_b_h2h is not None:
                goles_b = goles_b * peso_base + prom_goles_b_h2h * peso_h2h

            # Solo partidos con datos de corners reales (evita que un
            # partido sin stats registradas cuente como 0 corners real)
            h2h_con_stats = h2h[
                (h2h["corners_local"] + h2h["corners_visitante"] > 0)
            ]
            corners_a_h2h, corners_b_h2h = _promedios_h2h_por_equipo(h2h_con_stats, "corners", equipo_local)
            prom_corners_a_h2h = _promedio_ponderado_pares(corners_a_h2h)
            prom_corners_b_h2h = _promedio_ponderado_pares(corners_b_h2h)
            if prom_corners_a_h2h is not None:
                corners_a = corners_a * peso_base + prom_corners_a_h2h * peso_h2h
            if prom_corners_b_h2h is not None:
                corners_b = corners_b * peso_base + prom_corners_b_h2h * peso_h2h

        # Ajuste H2H para tarjetas si hay datos
        h2h_con_tarjetas = h2h[
            h2h["tarjetas_local"].notna() & h2h["tarjetas_visitante"].notna()
        ]
        if not h2h_con_tarjetas.empty:
            tarjetas_h2h_total = (h2h_con_tarjetas["tarjetas_local"] + h2h_con_tarjetas["tarjetas_visitante"]).mean()
            if not np.isnan(tarjetas_h2h_total):
                tarjetas_total = tarjetas_total * peso_base + tarjetas_h2h_total * peso_h2h

    # Aplicar limites finales
    goles_a        = float(np.clip(goles_a,        GOLES_MIN,    GOLES_MAX))
    goles_b        = float(np.clip(goles_b,        GOLES_MIN,    GOLES_MAX))
    corners_a      = float(np.clip(corners_a,      CORNERS_MIN,  CORNERS_MAX))
    corners_b      = float(np.clip(corners_b,      CORNERS_MIN,  CORNERS_MAX))
    tarjetas_total = float(np.clip(tarjetas_total, 1.5,          8.0))

    # Ajuste de fuerza de liga - solo aplica entre clubes (no selecciones)
    # cuando se conoce la liga domestica de referencia de ambos equipos y
    # son distintas (ej. Premier League vs Championship en una copa). Sin
    # esto, un equipo de segunda division en racha ofensiva se comparaba
    # a nivel de goles crudos contra un equipo de primera de otro pais,
    # sin ningun contexto de que juega en una liga mas debil.
    liga_ref_a = stats_a.get("liga_referencia")
    liga_ref_b = stats_b.get("liga_referencia")
    factor_liga_a, factor_liga_b = ajuste_liga_clubes(liga_ref_a, liga_ref_b)
    if factor_liga_a != 1.0 or factor_liga_b != 1.0:
        goles_a   = goles_a   * factor_liga_a
        goles_b   = goles_b   * factor_liga_b
        corners_a = corners_a * factor_liga_a
        corners_b = corners_b * factor_liga_b

    # Ajuste FIFA - solo aplica para selecciones nacionales
    try:
        if equipo_local and equipo_visitante:
            from fifa_ranking import ajuste_fifa, es_seleccion_nacional, get_puntos_fifa
            if es_seleccion_nacional(equipo_local) and es_seleccion_nacional(equipo_visitante):
                pts_local = get_puntos_fifa(equipo_local)
                pts_visit = get_puntos_fifa(equipo_visitante)
                # Cap de goles segun rival: si gano 5-1 a un equipo debil, limitar impacto
                # Usar directamente los puntos FIFA como proxy de fuerza relativa
                # Media ponderada: 60% ranking FIFA, 40% datos reales cuando hay pocos partidos
                n_partidos_a = stats_a.get("n_partidos", 10)
                n_partidos_b = stats_b.get("n_partidos", 10)
                n_min = min(n_partidos_a, n_partidos_b)
                # Con 5 partidos -> 65% FIFA, con 10+ -> 30% FIFA
                peso_fifa = max(0.30, min(0.65, 0.65 - (n_min - 5) * 0.07))
                # Goles esperados segun ranking FIFA puro (Elo-like)
                diff_pts = (pts_local - pts_visit) / 400.0
                diff_pts = max(-1.0, min(1.0, diff_pts))
                media_total = (goles_a + goles_b) / 2
                goles_a_fifa = media_total * (1.0 + diff_pts * 0.5)
                goles_b_fifa = media_total * (1.0 - diff_pts * 0.5)
                # Blend: datos reales + FIFA
                goles_a = goles_a * (1 - peso_fifa) + goles_a_fifa * peso_fifa
                goles_b = goles_b * (1 - peso_fifa) + goles_b_fifa * peso_fifa
                # Corners proporcional a goles
                f_local = goles_a / max((goles_a + goles_b) / 2, 0.1)
                f_visit = goles_b / max((goles_a + goles_b) / 2, 0.1)
                corners_a = corners_a * f_local
                corners_b = corners_b * f_visit
    except Exception:
        pass
    return goles_a, goles_b, corners_a, corners_b, tarjetas_total
