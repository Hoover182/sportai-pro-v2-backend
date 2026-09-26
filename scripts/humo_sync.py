#!/usr/bin/env python3
"""
Prueba de humo del sync: corre el codigo real del backend contra los
archivos de datos de un directorio (los de la rama del sync) y falla si
algo que usa produccion se rompe. Existe porque el backend se traga los
errores de carga: cargar_partidos_csv() devuelve un DataFrame vacio ante
cualquier excepcion y _cargar_cuotas_cache()/_cargar_team_ids() devuelven
{} -- un CSV roto no tira 500, deja la app sin partidos en silencio.

Uso: python scripts/humo_sync.py DIR_CON_LOS_DATOS
Exit 0 = paso; 1 = fallo (la ultima linea de la salida dice por que).
"""
import json
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "app", "services"))

# Columnas que lee el codigo del backend: si falta una, falla aca y no
# con un KeyError en produccion.
COLUMNAS_REQUERIDAS = [
    "fixture_id", "fecha", "estado", "liga", "equipo_local", "equipo_visitante",
    "goles_local", "goles_visitante", "corners_local", "corners_visitante",
    "tarjetas_local", "tarjetas_visitante", "tiros_arco_local", "tiros_arco_visitante",
    "atajadas_local", "atajadas_visitante",
]


def fallar(msg):
    print(f"HUMO FALLO: {msg}")
    sys.exit(1)


def main():
    if len(sys.argv) != 2:
        fallar("uso: humo_sync.py DIR_CON_LOS_DATOS")
    d = os.path.abspath(sys.argv[1])
    os.environ.pop("ODDS_API_KEY", None)  # nunca gastar cuota de la API de cuotas en la prueba

    # Los JSON se validan aparte: el backend los reemplaza por {} si no parsean.
    for nombre in ("cuotas_cache.json", "cache_team_ids.json"):
        ruta = os.path.join(d, nombre)
        if os.path.exists(ruta):
            try:
                with open(ruta, encoding="utf-8") as f:
                    if not isinstance(json.load(f), dict):
                        fallar(f"{nombre} no es un objeto JSON")
            except ValueError as e:
                fallar(f"{nombre} no parsea: {e}")

    import data_loader
    import futbol_service as F
    data_loader.CSV_FUTBOL = os.path.join(d, "futbol_partidos.csv")
    F.CUOTAS_CACHE_PATH = os.path.join(d, "cuotas_cache.json")
    F.TEAM_IDS_PATH = os.path.join(d, "cache_team_ids.json")

    try:
        df = F.cargar_df()
        if df.empty:
            fallar("cargar_df() devolvio 0 filas (el CSV no carga o ninguna liga es valida)")
        faltan = [c for c in COLUMNAS_REQUERIDAS if c not in df.columns]
        if faltan:
            fallar(f"faltan columnas que usa el backend: {faltan}")

        hoy = F._calcular_partidos_hoy("1xBet")
        if not isinstance(hoy, list):
            fallar(f"_calcular_partidos_hoy devolvio {type(hoy).__name__}, no una lista")

        ultimo = df[df["estado"].isin(("FT", "AET", "PEN"))].iloc[0]  # df viene ordenado por fecha descendente
        sim, _, _ = F.simular(df, ultimo["equipo_local"], ultimo["equipo_visitante"])
        if sim is None:
            fallar(f"simular() devolvio None para {ultimo['equipo_local']} vs {ultimo['equipo_visitante']}")
    except SystemExit:
        raise
    except Exception as e:
        fallar(f"{type(e).__name__}: {e}")

    print(f"HUMO OK: {len(df)} filas validas, {len(hoy)} partido(s) en /partidos-hoy, "
          f"simulacion de {ultimo['equipo_local']} vs {ultimo['equipo_visitante']} OK")


if __name__ == "__main__":
    main()
