import pandas as pd

CSV_FUTBOL = "futbol_partidos.csv"

LIGAS_VALIDAS = [
    "Premier League", "La Liga", "Serie A", "Bundesliga", "Ligue 1",
    "Primeira Liga", "Eredivisie", "Pro League Belgica", "Super Lig Turquia",
    "Serie B Italia", "Serie B Brasil",
    "Championship", "Segunda Division Espana", "Ligue 2", "Eerste Divisie",
    "2. Bundesliga", "3. Liga", "Second League Egipto", "Primera B Colombia",
    "Primera B Metropolitana",
    "Segunda Liga Portugal", "Challenger Pro League", "1. Lig Turquia",
    "Segunda Division Uruguay", "Segunda Division Peru", "Liga Pro Serie B",
    "Nacional B Bolivia",
    "Champions League", "Europa League", "Conference League",
    "FA Cup", "Copa del Rey", "Coppa Italia", "DFB Pokal", "Coupe de France",
    "Taça de Portugal", "KNVB Beker", "Copa Belgica", "Turkiye Kupasi",
    "Community Shield", "Trophée des Champions",
    "Super Cup Italia", "Super Cup Espana", "Super Cup Alemania",
    "Premier League Egipto", "Copa Egipto", "Pro League Arabia",
    "MLS", "Liga MX", "Liga Profesional Argentina", "Brasileirao",
    "Liga Colombia", "Primera Division Chile", "Primera Division Uruguay",
    "Primera Division Peru", "Liga Pro Ecuador", "Primera Division Venezuela",
    "Mundial 2026",
    "Primera Division Bolivia", "Division Profesional Paraguay",
    "Copa Libertadores", "Copa Sudamericana", "Recopa Sudamericana",
    "Copa Argentina", "Copa do Brasil", "Copa Chile", "Copa Colombia",
    "Copa Uruguay",
]

ESTADOS_EN_JUEGO   = ("NS", "1H", "HT", "2H", "ET", "BT", "LIVE")
ESTADOS_TERMINADOS = ("FT", "AET", "PEN")

LIGAS_PRINCIPALES = [
    "Premier League", "La Liga", "Serie A", "Bundesliga", "Ligue 1",
    "Champions League", "Europa League", "Conference League",
    "Liga MX", "Liga Profesional Argentina", "Brasileirao",
    "Mundial 2026", "Liga Colombia", "Primeira Liga", "Eredivisie", "Pro League Belgica",
    "Super Lig Turquia", "Primera Division Uruguay", "Primera Division Chile",
    "Copa Libertadores", "Copa Sudamericana", "MLS",
]


def cargar_partidos_csv():
    try:
        df = pd.read_csv(CSV_FUTBOL)
        df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce", utc=True)
        df["fecha"] = df["fecha"].dt.tz_convert("America/Bogota")
        df = df.dropna(subset=["fecha"])
        df = df.sort_values("fecha", ascending=False).reset_index(drop=True)
        return df
    except FileNotFoundError:
        print(f"No se encontro el archivo {CSV_FUTBOL}")
        return pd.DataFrame()
    except Exception as e:
        print("Error cargando CSV:", e)
        return pd.DataFrame()


def filtrar_ligas_validas(df):
    if df.empty:
        return df
    return df[df["liga"].isin(LIGAS_VALIDAS)].copy()


def listar_equipos(df):
    if df.empty:
        return []
    local     = df["equipo_local"].dropna().unique().tolist()
    visitante = df["equipo_visitante"].dropna().unique().tolist()
    return sorted(list(set(local + visitante)))


def obtener_equipo_por_nombre(df, nombre):
    nombre_lower = nombre.lower().strip()

    # 1. Busqueda exacta en ligas principales
    for liga in LIGAS_PRINCIPALES:
        df_liga = df[df["liga"] == liga]
        if df_liga.empty:
            continue
        equipos = pd.concat([df_liga["equipo_local"], df_liga["equipo_visitante"]]).unique()
        for equipo in equipos:
            if nombre_lower == str(equipo).lower():
                return equipo

    # 2. Busqueda exacta en todas las ligas
    for equipo in listar_equipos(df):
        if nombre_lower == str(equipo).lower():
            return equipo

    # 3. Busqueda parcial en ligas principales
    PREFIJOS = ("afc ", "fc ", "cd ", "cf ", "sd ", "ud ")
    for liga in LIGAS_PRINCIPALES:
        df_liga = df[df["liga"] == liga]
        if df_liga.empty:
            continue
        equipos = pd.concat([df_liga["equipo_local"], df_liga["equipo_visitante"]]).unique()
        for equipo in equipos:
            equipo_lower = str(equipo).lower()
            tiene_prefijo = any(equipo_lower.startswith(p) for p in PREFIJOS)
            if nombre_lower in equipo_lower and not tiene_prefijo:
                return equipo
        for equipo in equipos:
            if nombre_lower in str(equipo).lower():
                return equipo

    # 4. Busqueda parcial en todas las ligas
    for equipo in listar_equipos(df):
        if nombre_lower in str(equipo).lower():
            return equipo

    return None


def obtener_partidos_hoy_futbol(df):
    if df.empty:
        return df

    hoy = pd.Timestamp.now(tz="America/Bogota").normalize()

    if "estado" not in df.columns:
        return df[df["fecha"].dt.normalize() == hoy].copy()

    partidos_hoy = df[
        (df["fecha"].dt.normalize() == hoy) &
        (df["estado"].isin(ESTADOS_EN_JUEGO))
    ].copy()

    if not partidos_hoy.empty:
        return partidos_hoy

    proximos = df[
        (df["fecha"].dt.normalize() >= hoy) &
        (df["estado"].isin(ESTADOS_EN_JUEGO))
    ].copy()

    if not proximos.empty:
        proxima_fecha = proximos["fecha"].dt.normalize().min()
        if proxima_fecha > hoy:
            print(f"\nNo hay partidos pendientes hoy. Proxima fecha: {proxima_fecha.date()}\n")
        return proximos[proximos["fecha"].dt.normalize() == proxima_fecha].copy()

    print("\nNo hay partidos proximos disponibles.\n")
    return pd.DataFrame()


def obtener_partidos_rango_futbol(df, dias=4):
    """Devuelve partidos desde hoy hasta 'dias' dias en el futuro, agrupables por fecha."""
    if df.empty:
        return df
    hoy = pd.Timestamp.now(tz="America/Bogota").normalize()
    hasta = hoy + pd.Timedelta(days=dias - 1)

    if "estado" not in df.columns:
        return df[
            (df["fecha"].dt.normalize() >= hoy) &
            (df["fecha"].dt.normalize() <= hasta)
        ].copy()

    partidos = df[
        (df["fecha"].dt.normalize() >= hoy) &
        (df["fecha"].dt.normalize() <= hasta) &
        (df["estado"].isin(ESTADOS_EN_JUEGO))
    ].copy()
    return partidos


def obtener_partidos_mas_recientes(df, n=20):
    if df.empty:
        return df
    partidos = df[df["estado"].isin(ESTADOS_TERMINADOS)].copy() if "estado" in df.columns else df.copy()
    partidos = partidos.sort_values("fecha", ascending=False)
    partidos = partidos.drop_duplicates(subset=["fecha", "liga", "equipo_local", "equipo_visitante"])
    return partidos.head(n)
