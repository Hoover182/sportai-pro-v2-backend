#!/usr/bin/env python3
"""
Compara futbol_partidos.csv de analista-futbol (main) contra el CSV
actual de este repo, y arma un reporte de que cambiaria si se
sincronizara. NUNCA aplica el cambio solo -- eso lo decide un humano
mergeando el Pull Request que arma el workflow de GitHub Actions.

Uso:
    python check_sync.py                                   # solo imprime el reporte
    python check_sync.py --write-csv SALIDA.csv             # ademas escribe el CSV combinado
    python check_sync.py --summary-out resumen.md           # ademas escribe el reporte a archivo

Exit code 0: sin cambios. Exit code 2: hay cambios (para que el
workflow de GitHub Actions sepa si abrir el Pull Request o no).
"""
import sys
import argparse
import io

import requests
import pandas as pd

ANALISTA_FUTBOL_CSV_URL = "https://raw.githubusercontent.com/Hoover182/analista-futbol/main/futbol_partidos.csv"
BACKEND_CSV_PATH = "app/services/futbol_partidos.csv"

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
                   dup_fixture_id, dup_partido, fechas_raras, encoding_roto):
    lineas = []
    alertas = []

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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-csv", metavar="RUTA", help="Escribir el CSV combinado en esta ruta")
    parser.add_argument("--summary-out", metavar="RUTA", help="Escribir el resumen en este archivo")
    args = parser.parse_args()

    print("Descargando futbol_partidos.csv de analista-futbol...", file=sys.stderr)
    df_nuevo = descargar_csv_analista_futbol()
    df_actual = cargar_csv_backend()

    nuevas, actualizadas = detectar_filas_nuevas_y_actualizadas(df_nuevo, df_actual)

    if nuevas.empty and not actualizadas:
        print("Sin cambios. futbol_partidos.csv del backend ya esta al dia.")
        sys.exit(0)

    ligas_desconocidas = chequear_ligas_desconocidas(df_nuevo)
    ligas_ambiguas = chequear_posible_ambiguedad(ligas_desconocidas)
    dup_fixture_id, dup_partido = chequear_duplicados(df_nuevo)
    fechas_raras = chequear_fechas_fuera_de_rango(df_nuevo)
    encoding_roto = chequear_encoding_roto(df_nuevo)

    reporte = armar_reporte(
        nuevas, actualizadas, ligas_desconocidas, ligas_ambiguas,
        dup_fixture_id, dup_partido, fechas_raras, encoding_roto,
    )
    print(reporte)

    if args.summary_out:
        with open(args.summary_out, "w", encoding="utf-8") as f:
            f.write(reporte)

    if args.write_csv:
        combinado = combinar(df_actual, df_nuevo)
        combinado.to_csv(args.write_csv, index=False, encoding="utf-8-sig")

    sys.exit(2)


if __name__ == "__main__":
    main()
