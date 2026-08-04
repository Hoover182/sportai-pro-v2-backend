import re

ARCHIVO = "app/services/futbol_service.py"

with open(ARCHIVO, "r", encoding="utf-8") as f:
    contenido = f.read()

NUEVA_FUNCION = '''
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
'''

# Buscar y reemplazar la funcion existente
patron = re.compile(
    r'\ndef get_value_bets_hoy\(.*?(?=\n(?:def |@router|\Z))',
    re.DOTALL
)

if patron.search(contenido):
    contenido_nuevo = patron.sub(NUEVA_FUNCION, contenido)
    print("Funcion encontrada y sera reemplazada.")
else:
    # No existe, agregar al final
    contenido_nuevo = contenido + "\n" + NUEVA_FUNCION
    print("Funcion no encontrada. Agregando al final.")

with open(ARCHIVO, "w", encoding="utf-8") as f:
    f.write(contenido_nuevo)

print("Listo.")
