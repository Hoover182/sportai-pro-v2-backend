#!/usr/bin/env python3
"""
Veredicto de auto-merge del PR de sincronizacion: compara los datos de
main (antes) contra los de la rama del sync (despues) y decide si el PR
se podria mergear solo o si tiene que quedar para revision manual.

MODO OBSERVACION: este script NUNCA mergea. Solo escribe el veredicto
(JSON + comentario markdown); el workflow lo publica en el PR. Activar el
merge real es un cambio aparte, que se decide despues del periodo de
observacion.

Criterios (todos tienen que pasar para "auto_merge": true):
  A. Integridad: 0 celdas vaciadas, 0 filas perdidas, mismas columnas,
     estados solo hacia adelante, historia (>7 dias) sin cambios en
     goles/estado, prueba de humo con el codigo real sobre los datos nuevos.
  B. Volumen: filas nuevas/actualizadas dentro de un tope que escala con
     los dias transcurridos desde la ultima sync.
  C. Alertas que EMPEORAN respecto de main (las que ya estaban no cuentan).
  D. Caches: ningun team_id existente cambia; cuotas no quedan vacias.
  F. El diff del PR toca SOLO los archivos de datos del sync (lista exacta,
     no "cualquier .csv/.json"): nunca se auto-mergea codigo ni config.
  (E, verificacion en produccion despues del merge, vive en
   verificar_produccion.py: solo tiene sentido con merge real.)

Si el propio script falla, no hay veredicto -- y un veredicto ausente se
trata como "revision manual", nunca como aprobacion.

Uso:
    python scripts/veredicto_sync.py \\
        --antes-dir DIR_CON_ARCHIVOS_DE_MAIN --despues-dir DIR_CON_ARCHIVOS_DEL_SYNC \\
        --out veredicto.json --comentario veredicto.md

Exit code 0: veredicto "auto_merge" (se habria mergeado).
Exit code 3: veredicto "revision manual".
Cualquier otro: el script fallo (sin veredicto).
"""
import argparse
import json
import math
import os
import subprocess
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from check_sync import PATRONES_MOJIBAKE, chequear_ligas_desconocidas, chequear_posible_ambiguedad  # noqa: E402

CSV = "futbol_partidos.csv"
TEAMIDS = "cache_team_ids.json"
CUOTAS = "cuotas_cache.json"
META = "datos_meta.json"

ESTADOS_FINALES = {"FT", "AET", "PEN", "AWD"}
COLUMNAS_HISTORIA = ["estado", "goles_local", "goles_visitante"]
DIAS_HISTORIA = 7

# Topes de volumen, sacados de los 27 PRs de sync del 2026-08-30 al
# 2026-09-26: un dia normal trae 0-400 filas nuevas y 100-650 actualizadas;
# los PRs que acumulan varios dias escalan mas o menos lineal.
TOPE_NUEVAS_BASE, TOPE_NUEVAS_POR_DIA = 600, 200
TOPE_ACTUALIZADAS_BASE, TOPE_ACTUALIZADAS_POR_DIA = 1500, 400

# Filas nuevas con fecha fuera de esta ventana = backfill o fecha rota ->
# revision manual.
DIAS_NUEVAS_PASADO, DIAS_NUEVAS_FUTURO = 60, 400

# Unicos archivos que un PR de sync puede tocar para auto-mergearse.
ARCHIVOS_PERMITIDOS = {
    "app/services/futbol_partidos.csv",
    "app/services/cache_team_ids.json",
    "app/services/cuotas_cache.json",
    "app/services/datos_meta.json",
}

# Historial: el pipeline completa los H2H de los partidos cercanos
# (actualizar_h2h_desactualizado) y eso trae partidos viejos como filas
# nuevas en casi todas las corridas (PR #42: 4 Penarol-Torque 2024-2026;
# PR #28: 81 filas 2016-2023). Una fila nueva vieja se acepta solo si esta
# finalizada y su liga y sus DOS equipos ya existen en main: un equipo o una
# liga desconocidos en datos viejos es justo la forma de la contaminacion.

EXIT_AUTO, EXIT_MANUAL = 0, 3


def _iguales(a, b):
    """Igualdad por columna tolerante a NaN y a 2 vs 2.0 (un CSV con NaN en
    la columna lee enteros como float)."""
    na, nb = pd.to_numeric(a, errors="coerce"), pd.to_numeric(b, errors="coerce")
    ambos_num = na.notna() & nb.notna()
    ambos_na = a.isna() & b.isna()
    return ambos_na | (ambos_num & (na == nb)) | (~ambos_num & a.notna() & b.notna() & (a.astype(str) == b.astype(str)))


def _alinear(antes, despues):
    """Filas del mismo fixture_id en los dos CSV, en el mismo orden."""
    a = antes.drop_duplicates("fixture_id").set_index("fixture_id")
    d = despues.drop_duplicates("fixture_id").set_index("fixture_id")
    comunes = a.index.intersection(d.index)
    return a.loc[comunes], d.loc[comunes]


def _dias_desde_ultima_sync(meta_antes, ahora):
    try:
        ultima = pd.Timestamp(meta_antes["datos_actualizados_en"])
    except (KeyError, TypeError, ValueError):
        return 1, "sin datos_meta.json en main: se asume 1 dia"
    dias = max(1, math.ceil((ahora - ultima) / pd.Timedelta(days=1)))
    return dias, None


def _es_historial_conocido(nuevas, antes):
    """Mascara sobre `nuevas`: partido finalizado de una liga y dos equipos
    que main ya tiene."""
    equipos = set(antes["equipo_local"].dropna()) | set(antes["equipo_visitante"].dropna())
    return (nuevas["estado"].isin(ESTADOS_FINALES) & nuevas["liga"].isin(set(antes["liga"].dropna()))
            & nuevas["equipo_local"].isin(equipos) & nuevas["equipo_visitante"].isin(equipos))


def evaluar(antes, despues, ids_antes, ids_despues, cuotas_antes, cuotas_despues,
            meta_antes, ahora, humo=None, archivos_cambiados=None):
    """Devuelve {"auto_merge": bool, "fallos": [...], "metricas": {...}}.
    humo: (ok, detalle) de la prueba de humo, o None si no se corrio (cuenta
    como fallo: sin prueba de humo no hay auto-merge).
    archivos_cambiados: rutas del diff del PR, o None si no se sabe (cuenta
    como fallo, mismo criterio)."""
    fallos, m = [], {}

    # --- F. Solo archivos de datos ---
    if archivos_cambiados is None:
        fallos.append("No se pudo obtener la lista de archivos cambiados del PR")
    else:
        otros = sorted(set(archivos_cambiados) - ARCHIVOS_PERMITIDOS)
        m["archivos_cambiados"] = sorted(archivos_cambiados)
        if otros:
            fallos.append(f"El PR toca archivos que no son datos del sync (nunca se auto-mergea codigo/config): {otros}")

    # --- A. Integridad ---
    cols_antes, cols_despues = set(antes.columns), set(despues.columns)
    agregadas, quitadas = sorted(cols_despues - cols_antes), sorted(cols_antes - cols_despues)
    m["columnas_agregadas"], m["columnas_quitadas"] = agregadas, quitadas
    if agregadas or quitadas:
        fallos.append(f"Cambio de estructura: columnas agregadas {agregadas or '-'}, quitadas {quitadas or '-'}")

    perdidas = sorted(set(antes["fixture_id"].dropna()) - set(despues["fixture_id"].dropna()))
    m["filas_perdidas"] = len(perdidas)
    if perdidas:
        fallos.append(f"{len(perdidas)} fila(s) de main desaparecen (ej. fixture_id {perdidas[:5]})")

    a, d = _alinear(antes, despues)
    comunes_cols = [c for c in a.columns if c in d.columns]
    vaciadas = {c: int((a[c].notna() & d[c].isna()).sum()) for c in comunes_cols}
    vaciadas = {c: n for c, n in vaciadas.items() if n}
    m["celdas_vaciadas"] = sum(vaciadas.values())
    if vaciadas:
        fallos.append(f"{m['celdas_vaciadas']} celda(s) con dato en main quedan vacias: {vaciadas}")

    retroceden = a["estado"].isin(ESTADOS_FINALES) & ~d["estado"].isin(ESTADOS_FINALES)
    m["estados_hacia_atras"] = int(retroceden.sum())
    if retroceden.any():
        ej = [f"{fid}: {a.at[fid, 'estado']}->{d.at[fid, 'estado']}" for fid in a.index[retroceden][:5]]
        fallos.append(f"{m['estados_hacia_atras']} partido(s) finalizado(s) vuelven a un estado no final: {ej}")

    fechas = pd.to_datetime(a["fecha"], errors="coerce", utc=True)
    viejos = a["estado"].isin(ESTADOS_FINALES) & (fechas < ahora - pd.Timedelta(days=DIAS_HISTORIA))
    cambio_hist = pd.Series(False, index=a.index)
    for c in COLUMNAS_HISTORIA:
        if c in comunes_cols:
            cambio_hist |= ~_iguales(a[c], d[c])
    cambio_hist &= viejos
    m["historia_modificada"] = int(cambio_hist.sum())
    if cambio_hist.any():
        ej = [f"{fid} ({a.at[fid, 'equipo_local']} vs {a.at[fid, 'equipo_visitante']}, "
              f"{a.at[fid, 'goles_local']}-{a.at[fid, 'goles_visitante']} -> "
              f"{d.at[fid, 'goles_local']}-{d.at[fid, 'goles_visitante']}, {a.at[fid, 'estado']}->{d.at[fid, 'estado']})"
              for fid in a.index[cambio_hist][:5]]
        fallos.append(f"{m['historia_modificada']} partido(s) finalizado(s) hace mas de {DIAS_HISTORIA} dias "
                      f"cambian goles o estado: {ej}")

    if humo is None:
        fallos.append("No se corrio la prueba de humo")
    elif not humo[0]:
        fallos.append(f"Prueba de humo fallo: {humo[1]}")
    m["humo"] = None if humo is None else humo[1]

    # --- B. Volumen ---
    dias, aviso_dias = _dias_desde_ultima_sync(meta_antes, ahora)
    m["dias_desde_ultima_sync"] = dias
    if aviso_dias:
        m["aviso_dias"] = aviso_dias
    ids_antes_csv = set(antes["fixture_id"].dropna())
    nuevas = despues[despues["fixture_id"].notna() & ~despues["fixture_id"].isin(ids_antes_csv)]
    sin_id_antes, sin_id_despues = int(antes["fixture_id"].isna().sum()), int(despues["fixture_id"].isna().sum())
    if sin_id_despues > sin_id_antes:
        fallos.append(f"Aumentan las filas sin fixture_id: {sin_id_antes} -> {sin_id_despues}")
    distinta = pd.Series(False, index=a.index)
    for c in comunes_cols:
        distinta |= ~_iguales(a[c], d[c])
    m["filas_nuevas"], m["filas_actualizadas"] = len(nuevas), int(distinta.sum())
    tope_n = max(TOPE_NUEVAS_BASE, TOPE_NUEVAS_POR_DIA * dias)
    tope_a = max(TOPE_ACTUALIZADAS_BASE, TOPE_ACTUALIZADAS_POR_DIA * dias)
    m["tope_nuevas"], m["tope_actualizadas"] = tope_n, tope_a
    if len(nuevas) > tope_n:
        fallos.append(f"Volumen anomalo: {len(nuevas)} filas nuevas (tope {tope_n} para {dias} dia(s))")
    if m["filas_actualizadas"] > tope_a:
        fallos.append(f"Volumen anomalo: {m['filas_actualizadas']} filas actualizadas (tope {tope_a} para {dias} dia(s))")

    # --- C. Alertas que empeoran respecto de main ---
    amb_antes = set(chequear_posible_ambiguedad(chequear_ligas_desconocidas(antes)))
    amb_nuevas = sorted(set(chequear_posible_ambiguedad(chequear_ligas_desconocidas(despues))) - amb_antes)
    m["ligas_ambiguas_nuevas"] = amb_nuevas
    if amb_nuevas:
        fallos.append(f"Liga(s) de nombre ambiguo que main no tenia (posible contaminacion): {amb_nuevas}")

    def n_dup_id(df):
        return int(df["fixture_id"].duplicated(keep=False).sum())

    def n_dup_partido(df):
        return int(df.duplicated(subset=["fecha", "liga", "equipo_local", "equipo_visitante"], keep=False).sum())

    for nombre, fn in (("fixture_id duplicados", n_dup_id), ("partidos duplicados con fixture_id distinto", n_dup_partido)):
        na, nd = fn(antes), fn(despues)
        if nd > na:
            fallos.append(f"Aumentan las filas con {nombre}: {na} -> {nd}")

    def mojibake(df):
        vals = set()
        for col in ("liga", "equipo_local", "equipo_visitante"):
            vals |= {v for v in df[col].dropna().astype(str).unique() if any(p in v for p in PATRONES_MOJIBAKE)}
        return vals

    moji = sorted(mojibake(despues) - mojibake(antes))
    if moji:
        fallos.append(f"Encoding roto nuevo: {moji[:5]}")

    f_nuevas = pd.to_datetime(nuevas["fecha"], errors="coerce", utc=True)
    vieja = f_nuevas < ahora - pd.Timedelta(days=DIAS_NUEVAS_PASADO)
    historial = vieja & _es_historial_conocido(nuevas, antes)
    m["filas_nuevas_historial_aceptadas"] = int(historial.sum())
    raras = nuevas[f_nuevas.isna() | (vieja & ~historial) | (f_nuevas > ahora + pd.Timedelta(days=DIAS_NUEVAS_FUTURO))]
    m["filas_nuevas_fecha_rara"] = len(raras)
    if len(raras):
        ej = [f"{r.fecha} {r.liga}: {r.equipo_local} vs {r.equipo_visitante}" for r in raras.head(3).itertuples()]
        fallos.append(f"{len(raras)} fila(s) nueva(s) con fecha vacia, a mas de {DIAS_NUEVAS_FUTURO} dias, o de hace mas "
                      f"de {DIAS_NUEVAS_PASADO} dias con liga o equipo que main no tiene: {ej}")

    # --- D. Caches ---
    ids_cambiados = {k: (ids_antes[k], v) for k, v in ids_despues.items() if k in ids_antes and ids_antes[k] != v}
    m["team_ids_cambiados"] = len(ids_cambiados)
    if ids_cambiados:
        fallos.append(f"{len(ids_cambiados)} equipo(s) con team_id cambiado: {dict(list(ids_cambiados.items())[:5])}")
    if cuotas_antes and not cuotas_despues:
        fallos.append(f"cuotas_cache.json queda vacio (main tenia {len(cuotas_antes)} fixtures con cuota)")

    return {"auto_merge": not fallos, "fallos": fallos, "metricas": m}


def correr_humo(dir_datos, repo_raiz):
    """Prueba de humo en un proceso aparte (el codigo del backend cachea en
    memoria y cambia de directorio al cargar)."""
    try:
        r = subprocess.run([sys.executable, os.path.join(repo_raiz, "scripts", "humo_sync.py"), dir_datos],
                           capture_output=True, text=True, timeout=600)
    except subprocess.TimeoutExpired:
        return False, "timeout de 10 minutos"
    salida = (r.stdout + r.stderr).strip().splitlines()
    detalle = salida[-1] if salida else "(sin salida)"
    return r.returncode == 0, detalle


def armar_comentario(v):
    m = v["metricas"]
    lineas = ["## Veredicto de auto-merge (MODO OBSERVACION: no se mergea nada solo)", ""]
    if v["auto_merge"]:
        lineas.append("✅ **Se habria mergeado solo.** Todos los criterios pasaron.")
    else:
        lineas.append(f"⛔ **NO se habria mergeado solo** -- queda para revision manual. {len(v['fallos'])} criterio(s) fallaron:")
        lineas += [f"- {f}" for f in v["fallos"]]
    lineas += [
        "",
        "<details><summary>Metricas</summary>",
        "",
        f"- Dias desde la ultima sync: {m.get('dias_desde_ultima_sync')}" + (f" ({m['aviso_dias']})" if m.get("aviso_dias") else ""),
        f"- Filas nuevas: {m.get('filas_nuevas')} (tope {m.get('tope_nuevas')})",
        f"- Filas actualizadas: {m.get('filas_actualizadas')} (tope {m.get('tope_actualizadas')})",
        f"- Filas perdidas: {m.get('filas_perdidas')} | celdas vaciadas: {m.get('celdas_vaciadas')}",
        f"- Estados hacia atras: {m.get('estados_hacia_atras')} | historia modificada: {m.get('historia_modificada')}",
        f"- Columnas agregadas: {m.get('columnas_agregadas')} | quitadas: {m.get('columnas_quitadas')}",
        f"- Ligas ambiguas nuevas: {m.get('ligas_ambiguas_nuevas')} | team_ids cambiados: {m.get('team_ids_cambiados')}",
        f"- Filas nuevas con fecha rara: {m.get('filas_nuevas_fecha_rara')} | historial de equipos conocidos aceptado: {m.get('filas_nuevas_historial_aceptadas')}",
        f"- Archivos cambiados: {m.get('archivos_cambiados')}",
        f"- Prueba de humo: {m.get('humo')}",
        "",
        "</details>",
    ]
    return "\n".join(lineas)


def _leer_json(ruta, defecto):
    if not os.path.exists(ruta):
        return defecto
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def _leer_archivos_cambiados(ruta):
    if not os.path.exists(ruta):
        return None
    with open(ruta, encoding="utf-8") as f:
        return [l.strip() for l in f if l.strip()]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--antes-dir", required=True, help="Directorio con los archivos de datos de main")
    p.add_argument("--despues-dir", required=True, help="Directorio con los archivos de datos de la rama del sync")
    p.add_argument("--out", required=True, help="Ruta del veredicto JSON")
    p.add_argument("--comentario", required=True, help="Ruta del comentario markdown para el PR")
    p.add_argument("--archivos-cambiados", required=True,
                   help="Archivo de texto con las rutas del diff del PR, una por linea (git diff --name-only)")
    p.add_argument("--ahora", help="Momento de la evaluacion (ISO, UTC); por defecto ahora. Solo para simular PRs viejos")
    args = p.parse_args()

    ahora = pd.Timestamp(args.ahora) if args.ahora else pd.Timestamp.now(tz="UTC")
    if ahora.tzinfo is None:
        ahora = ahora.tz_localize("UTC")
    antes = pd.read_csv(os.path.join(args.antes_dir, CSV))
    despues = pd.read_csv(os.path.join(args.despues_dir, CSV))
    repo_raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    v = evaluar(
        antes, despues,
        _leer_json(os.path.join(args.antes_dir, TEAMIDS), {}), _leer_json(os.path.join(args.despues_dir, TEAMIDS), {}),
        _leer_json(os.path.join(args.antes_dir, CUOTAS), {}), _leer_json(os.path.join(args.despues_dir, CUOTAS), {}),
        _leer_json(os.path.join(args.antes_dir, META), {}), ahora,
        humo=correr_humo(os.path.abspath(args.despues_dir), repo_raiz),
        archivos_cambiados=_leer_archivos_cambiados(args.archivos_cambiados),
    )
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(v, f, ensure_ascii=False, indent=2, default=str)
    comentario = armar_comentario(v)
    with open(args.comentario, "w", encoding="utf-8") as f:
        f.write(comentario)
    print(comentario)
    sys.exit(EXIT_AUTO if v["auto_merge"] else EXIT_MANUAL)


if __name__ == "__main__":
    main()
