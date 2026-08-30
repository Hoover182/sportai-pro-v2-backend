#!/usr/bin/env python3
"""
Compara futbol_partidos.csv de analista-futbol (main) contra el CSV
actual de este repo, y arma un reporte de que cambiaria si se
sincronizara. NUNCA aplica el cambio solo -- eso lo decide un humano
mergeando el Pull Request que arma el workflow de GitHub Actions.

Tambien compara cache_team_ids.json (nombre de equipo -> id de
api-football, usado para armar la URL del escudo real sin gastar cuota
en vivo) y cuotas_cache.json (cuotas reales de Betano/1xBet por
fixture_id, usado por el Top picks combinado) -- los dos se generaban
solo en analista-futbol, nunca se sincronizaban al backend a proposito,
hasta que la pantalla de Inicio nueva los necesito.

cuotas_cache.json se REEMPLAZA entero (no se mergea como el de ids):
analista-futbol lo regenera de cero en cada corrida del cron, asi que
arrastrar entradas viejas del lado del backend solo acumularia cuotas
de partidos que ya pasaron.

Uso:
    python check_sync.py                                   # solo imprime el reporte
    python check_sync.py --write-csv SALIDA.csv             # ademas escribe el CSV combinado
    python check_sync.py --write-teamids SALIDA.json        # ademas escribe el cache de ids combinado
    python check_sync.py --write-cuotas SALIDA.json         # ademas escribe el cache de cuotas
    python check_sync.py --summary-out resumen.md           # ademas escribe el reporte a archivo

Exit code 0: sin cambios. Exit code 2: hay cambios (para que el
workflow de GitHub Actions sepa si abrir el Pull Request o no).
"""
import sys
import os
import json
import argparse
import io

import requests
import pandas as pd

ANALISTA_FUTBOL_CSV_URL = "https://raw.githubusercontent.com/Hoover182/analista-futbol/main/futbol_partidos.csv"
BACKEND_CSV_PATH = "app/services/futbol_partidos.csv"

ANALISTA_FUTBOL_TEAMIDS_URL = "https://raw.githubusercontent.com/Hoover182/analista-futbol/main/cache_team_ids.json"
BACKEND_TEAMIDS_PATH = "app/services/cache_team_ids.json"

ANALISTA_FUTBOL_CUOTAS_URL = "https://raw.githubusercontent.com/Hoover182/analista-futbol/main/cuotas_cache.json"
BACKEND_CUOTAS_PATH = "app/services/cuotas_cache.json"

# Mismo listado de nombres que LIGAS en api_to_csv.py -- cualquier liga
# en los datos nuevos que no este aca se marca para revisar (o es una
# liga agregada a proposito, o es contaminacion).
LIGAS_CONOCIDAS = {
    "Premier League", "La Liga", "Serie A", "Bundesliga", "Ligue 1", "Primeira Liga",
    "Eredivisie", "Pro League Belgica", "Super Lig Turquia", "Champions League",
    "Europa League", "Conference League", "FA Cup", "Copa del Rey", "Coppa Italia",
    "DFB Pokal", "Coupe de France", "Taça de Portugal", "KNVB Beker", "Copa Belgica",
    "Turkiye Kupasi", "Premier League Egipto", "Copa Egipto", "Pro League Arabia",
    "MLS", "Liga MX", "Liga Profesional Argentina", "Brasileirao", "Liga Colombia",
    "Primera Division Chile", "Primera Division Uruguay", "Primera Division Peru",
    "Liga Pro Ecuador", "Primera Division Venezuela", "Primera Division Bolivia",
    "Division Profesional Paraguay", "Copa Libertadores", "Copa Sudamericana",
    "Recopa Sudamericana", "Copa Argentina", "Copa do Brasil", "Copa Chile",
    "Copa Colombia", "Copa Uruguay", "Mundial 2026",
}

# Fragmentos de nombre que ya sabemos que son ambiguos entre paises --
# si una liga desconocida los contiene, se marca como posible
# contaminacion (caso real de esta sesion: Serie A Italia vs
# Brasileirao, Primera Division x 6 paises distintos).
PATRONES_AMBIGUOS = ["serie a", "serie b", "primera division", "liga profesional", "copa"]

PATRONES_MOJIBAKE = ["Ã", "â€", "Â"]


def descargar_csv_analista_futbol():
    resp = requests.get(ANALISTA_FUTBOL_CSV_URL, timeout=30)
    resp.raise_for_status()
    return pd.read_csv(io.BytesIO(resp.content))


def cargar_csv_backend():
    return pd.read_csv(BACKEND_CSV_PATH)


def descargar_cache_team_ids():
    resp = requests.get(ANALISTA_FUTBOL_TEAMIDS_URL, timeout=30)
    resp.raise_for_status()
    return resp.json()


def cargar_cache_team_ids_backend():
    if not os.path.exists(BACKEND_TEAMIDS_PATH):
        return {}
    with open(BACKEND_TEAMIDS_PATH, encoding="utf-8") as f:
        return json.load(f)


def comparar_team_ids(nuevo, actual):
    """id_nuevos: nombres de equipo que el backend todavia no tiene.
    id_cambiados: mismo nombre pero id distinto -- un id de api-football
    no deberia cambiar nunca para el mismo equipo, asi que esto es una
    señal de alerta real (nombre ambiguo resuelto a un equipo distinto
    en cada corrida), no un caso esperado."""
    id_nuevos = {k: v for k, v in nuevo.items() if k not in actual}
    id_cambiados = {k: (actual[k], v) for k, v in nuevo.items() if k in actual and actual[k] != v}
    return id_nuevos, id_cambiados


def descargar_cuotas_cache():
    resp = requests.get(ANALISTA_FUTBOL_CUOTAS_URL, timeout=30)
    resp.raise_for_status()
    return resp.json()


def cargar_cuotas_cache_backend():
    if not os.path.exists(BACKEND_CUOTAS_PATH):
        return {}
    with open(BACKEND_CUOTAS_PATH, encoding="utf-8") as f:
        return json.load(f)


def detectar_filas_nuevas_y_actualizadas(df_nuevo, df_actual):
    actual_por_id = df_actual.set_index("fixture_id")
    ids_actuales = set(actual_por_id.index)

    nuevas = df_nuevo[~df_nuevo["fixture_id"].isin(ids_actuales)]

    candidatas = df_nuevo[df_nuevo["fixture_id"].isin(ids_actuales)]
    actualizadas = []
    for _, fila in candidatas.iterrows():
        fid = fila["fixture_id"]
        fila_actual = actual_por_id.loc[fid]
        distintos = [c for c in fila.index if c != "fixture_id" and str(fila[c]) != str(fila_actual[c])]
        if distintos:
            actualizadas.append((fid, distintos))

    return nuevas, actualizadas


def chequear_ligas_desconocidas(df_nuevo):
    ligas_en_datos = set(df_nuevo["liga"].dropna().unique())
    return sorted(ligas_en_datos - LIGAS_CONOCIDAS)


def chequear_posible_ambiguedad(ligas_desconocidas):
    sospechosas = []
    for liga in ligas_desconocidas:
        liga_lower = liga.lower()
        if any(patron in liga_lower for patron in PATRONES_AMBIGUOS):
            sospechosas.append(liga)
    return sospechosas


def chequear_duplicados(df_nuevo):
    dup_fixture_id = df_nuevo[df_nuevo.duplicated(subset=["fixture_id"], keep=False)]
    dup_partido = df_nuevo[df_nuevo.duplicated(
        subset=["fecha", "liga", "equipo_local", "equipo_visitante"], keep=False
    )]
    return dup_fixture_id, dup_partido


def chequear_fechas_fuera_de_rango(df_nuevo):
    fechas = pd.to_datetime(df_nuevo["fecha"], errors="coerce")
    hoy = pd.Timestamp.now()
    return df_nuevo[(fechas < hoy - pd.Timedelta(days=400)) | (fechas > hoy + pd.Timedelta(days=400))]


def chequear_encoding_roto(df_nuevo):
    sospechosos = []
    for col in ("liga", "equipo_local", "equipo_visitante"):
        for valor in df_nuevo[col].dropna().unique():
            if any(p in valor for p in PATRONES_MOJIBAKE):
                sospechosos.append((col, valor))
    return sospechosos


def armar_reporte(nuevas, actualizadas, ligas_desconocidas, ligas_ambiguas,
                   dup_fixture_id, dup_partido, fechas_raras, encoding_roto,
                   id_nuevos, id_cambiados, cuotas_actual, cuotas_nuevo):
    lineas = []
    alertas = []

    if cuotas_actual and not cuotas_nuevo:
        alertas.append(
            f"⚠️ **cuotas_cache.json nuevo viene vacio** (el backend tenia {len(cuotas_actual)} "
            "fixtures con cuota real) -- revisar si el paso de cuotas del cron fallo antes de mergear"
        )
    if id_cambiados:
        alertas.append(
            f"⚠️ **{len(id_cambiados)} equipo(s) con id de api-football cambiado** "
            "(un id no deberia cambiar para el mismo nombre -- revisar antes de mergear)"
        )
    if ligas_ambiguas:
        alertas.append(
            f"⚠️ **{len(ligas_ambiguas)} liga(s) con nombre ambiguo/posible contaminacion**: "
            + ", ".join(ligas_ambiguas)
        )
    if not dup_fixture_id.empty:
        alertas.append(f"⚠️ **{dup_fixture_id['fixture_id'].nunique()} fixture_id duplicado(s)** en los datos nuevos")
    if not dup_partido.empty:
        alertas.append(f"⚠️ **{len(dup_partido)} fila(s)** con el mismo partido pero `fixture_id` distinto")
    if not fechas_raras.empty:
        alertas.append(f"⚠️ **{len(fechas_raras)} fila(s)** con fecha fuera de rango razonable (±400 dias)")
    if encoding_roto:
        alertas.append(f"⚠️ **{len(encoding_roto)} valor(es)** con posible encoding roto")
    ligas_solo_nuevas = [l for l in ligas_desconocidas if l not in ligas_ambiguas]
    if ligas_solo_nuevas:
        alertas.append(
            f"ℹ️ **{len(ligas_solo_nuevas)} liga(s) no reconocida(s)** (puede ser intencional, revisar): "
            + ", ".join(ligas_solo_nuevas)
        )

    lineas.append("## Resumen")
    lineas.append(f"- Filas nuevas: **{len(nuevas)}**")
    lineas.append(f"- Filas actualizadas (mismo partido, datos distintos): **{len(actualizadas)}**")
    lineas.append("")

    lineas.append("## Alertas a revisar")
    if alertas:
        for a in alertas:
            lineas.append(f"- {a}")
    else:
        lineas.append("- Ninguna. Todos los chequeos automaticos pasaron limpio.")
    lineas.append("")

    if len(nuevas):
        lineas.append("## Filas nuevas por liga")
        for liga, n in nuevas["liga"].value_counts().items():
            lineas.append(f"- {liga}: {n}")
        lineas.append("")

    if actualizadas:
        lineas.append("## Ejemplos de filas actualizadas (hasta 10)")
        for fid, cols in actualizadas[:10]:
            lineas.append(f"- `fixture_id {fid}`: cambiaron {', '.join(cols)}")
        if len(actualizadas) > 10:
            lineas.append(f"- ... y {len(actualizadas) - 10} mas")
        lineas.append("")

    if id_nuevos or id_cambiados:
        lineas.append("## Cache de equipos (escudos)")
        lineas.append(f"- Equipos nuevos: **{len(id_nuevos)}**")
        lineas.append(f"- Equipos con id cambiado: **{len(id_cambiados)}**")
        if id_cambiados:
            for nombre, (id_viejo, id_nuevo) in list(id_cambiados.items())[:10]:
                lineas.append(f"  - `{nombre}`: {id_viejo} -> {id_nuevo}")
            if len(id_cambiados) > 10:
                lineas.append(f"  - ... y {len(id_cambiados) - 10} mas")
        lineas.append("")

    if cuotas_actual != cuotas_nuevo:
        lineas.append("## Cuotas reales (Betano/1xBet)")
        lineas.append(f"- Fixtures con cuota antes: **{len(cuotas_actual)}**")
        lineas.append(f"- Fixtures con cuota ahora: **{len(cuotas_nuevo)}**")
        lineas.append("")

    lineas.append("---")
    lineas.append(
        "_Chequeos automaticos: pertenencia a la lista de ~45 ligas conocidas, similitud con "
        "nombres de liga ambiguos ya vistos (Serie A/Primera Division), duplicados, fechas fuera "
        "de rango, encoding roto. Esto NO reemplaza tu revision -- son señales de patrones ya "
        "conocidos, no una garantia contra casos nuevos. Revisa el diff de este PR antes de "
        "mergear._"
    )

    return "\n".join(lineas)


def combinar(df_actual, df_nuevo):
    actual_idx = df_actual.set_index("fixture_id")
    nuevo_idx = df_nuevo.set_index("fixture_id")
    actual_idx.update(nuevo_idx)
    faltantes = nuevo_idx.loc[~nuevo_idx.index.isin(actual_idx.index)]
    combinado = pd.concat([actual_idx, faltantes]).reset_index()
    return combinado.sort_values(["fecha", "liga"])


def combinar_team_ids(actual, nuevo):
    combinado = dict(actual)
    combinado.update(nuevo)
    return combinado


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-csv", metavar="RUTA", help="Escribir el CSV combinado en esta ruta")
    parser.add_argument("--write-teamids", metavar="RUTA", help="Escribir el cache de ids combinado en esta ruta")
    parser.add_argument("--write-cuotas", metavar="RUTA", help="Escribir el cache de cuotas nuevo en esta ruta")
    parser.add_argument("--summary-out", metavar="RUTA", help="Escribir el resumen en este archivo")
    args = parser.parse_args()

    print("Descargando futbol_partidos.csv de analista-futbol...", file=sys.stderr)
    df_nuevo = descargar_csv_analista_futbol()
    df_actual = cargar_csv_backend()
    nuevas, actualizadas = detectar_filas_nuevas_y_actualizadas(df_nuevo, df_actual)

    print("Descargando cache_team_ids.json de analista-futbol...", file=sys.stderr)
    teamids_nuevo = descargar_cache_team_ids()
    teamids_actual = cargar_cache_team_ids_backend()
    id_nuevos, id_cambiados = comparar_team_ids(teamids_nuevo, teamids_actual)

    print("Descargando cuotas_cache.json de analista-futbol...", file=sys.stderr)
    cuotas_nuevo = descargar_cuotas_cache()
    cuotas_actual = cargar_cuotas_cache_backend()

    hay_cambios_csv = not nuevas.empty or bool(actualizadas)
    hay_cambios_teamids = bool(id_nuevos) or bool(id_cambiados)
    hay_cambios_cuotas = cuotas_nuevo != cuotas_actual

    if not hay_cambios_csv and not hay_cambios_teamids and not hay_cambios_cuotas:
        print("Sin cambios. futbol_partidos.csv, cache_team_ids.json y cuotas_cache.json del backend ya estan al dia.")
        sys.exit(0)

    ligas_desconocidas = chequear_ligas_desconocidas(df_nuevo)
    ligas_ambiguas = chequear_posible_ambiguedad(ligas_desconocidas)
    dup_fixture_id, dup_partido = chequear_duplicados(df_nuevo)
    fechas_raras = chequear_fechas_fuera_de_rango(df_nuevo)
    encoding_roto = chequear_encoding_roto(df_nuevo)

    reporte = armar_reporte(
        nuevas, actualizadas, ligas_desconocidas, ligas_ambiguas,
        dup_fixture_id, dup_partido, fechas_raras, encoding_roto,
        id_nuevos, id_cambiados, cuotas_actual, cuotas_nuevo,
    )
    print(reporte)

    if args.summary_out:
        with open(args.summary_out, "w", encoding="utf-8") as f:
            f.write(reporte)

    if args.write_csv and hay_cambios_csv:
        combinado = combinar(df_actual, df_nuevo)
        combinado.to_csv(args.write_csv, index=False, encoding="utf-8-sig")

    if args.write_teamids and hay_cambios_teamids:
        combinado_ids = combinar_team_ids(teamids_actual, teamids_nuevo)
        with open(args.write_teamids, "w", encoding="utf-8") as f:
            json.dump(combinado_ids, f, ensure_ascii=False, indent=2)

    if args.write_cuotas and hay_cambios_cuotas:
        with open(args.write_cuotas, "w", encoding="utf-8") as f:
            json.dump(cuotas_nuevo, f, ensure_ascii=False, indent=2)

    sys.exit(2)


if __name__ == "__main__":
    main()
