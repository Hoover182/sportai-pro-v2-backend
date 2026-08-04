with open("app/services/futbol_service.py", "r", encoding="utf-8") as f:
    content = f.read()

old = "def cargar_df():"

new = '''LIGAS_NIVEL_1 = [
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
    Se cachea en memoria porque el CSV no cambia dentro del mismo proceso."""
    global _cache_equipos_nivel1
    if _cache_equipos_nivel1 is not None:
        return _cache_equipos_nivel1
    equipos = set()
    for liga in LIGAS_NIVEL_1:
        sub = df[df["liga"] == liga]
        equipos.update(sub["equipo_local"].unique())
        equipos.update(sub["equipo_visitante"].unique())
    _cache_equipos_nivel1 = equipos
    return equipos


def categoria_equipo(nombre, equipos_nivel1):
    """Devuelve 'Primera' si el equipo juega habitualmente en una liga top,
    o 'Categoria menor' si solo aparece en copas (posible Segunda/Tercera/amateur)."""
    return "Primera" if nombre in equipos_nivel1 else "Categoria menor"


def cargar_df():'''

if old in content:
    content = content.replace(old, new, 1)
    with open("app/services/futbol_service.py", "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print("OK: funciones de categoria agregadas")
else:
    print("ERROR: no encontrado")
