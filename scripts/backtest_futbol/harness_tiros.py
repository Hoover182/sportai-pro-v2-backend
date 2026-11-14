"""Harness point-in-time de PREREGISTRO_tiros_atajadas.md (congelado 2c1c326).

Corre el codigo de produccion TAL CUAL (main eea826c, en un worktree aparte)
con la maquinaria de harness.py (reloj congelado en inicio - 1 hora, datos
anteriores al corte, Elo puntual, caches vaciados) y guarda, por partido,
las proyecciones y el Over de todas las lineas de las 9 series:

  T/L/V x arco (tiros al arco) / tiros (tiros totales) / ataj (atajadas)

No hay variantes: se evalua el modelo actual.

Uso desde backend/ (este worktree):
  python scripts/backtest_futbol/harness_tiros.py --servicios RUTA_MAIN/app/services \
      --csv datos_tiros_eea826c.csv --desde 2025-07-01 --hasta 2025-12-31 \
      --salida pred_ti_2025h2.csv [--procesos 4] [--limite N] [--ids 1,2,3]

--servicios: app/services de un checkout de main en eea826c.
--csv: el CSV congelado del pre-registro (SHA-256 4b6b315f0facfa6e...).
Solo corre partidos terminados de ligas validas con stats (corners total > 0).

Modo verificacion (--verificar N): toma N partidos NS de los proximos dias y
compara el harness (reloj congelado en un instante T, datos < T) con el
codigo de main SIN parches sobre el CSV completo. Tiene que dar exactamente
lo mismo antes de correr nada (pre-registro, "Modelo de referencia").
"""
import argparse
import os
import sys
import time
from multiprocessing import Pool

import pandas as pd

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import harness as H  # noqa: E402

SERIES = {
    # serie: (clave O/U en sim, clave proyeccion en sim)
    "T-arco": ("tiros_arco_ou", "tiros_arco_totales_proj"),
    "L-arco": ("tiros_arco_ou_local", "tiros_arco_local_proj"),
    "V-arco": ("tiros_arco_ou_visitante", "tiros_arco_visitante_proj"),
    "T-tiros": ("tiros_total_ou", "tiros_total_totales_proj"),
    "L-tiros": ("tiros_total_ou_local", "tiros_total_local_proj"),
    "V-tiros": ("tiros_total_ou_visitante", "tiros_total_visitante_proj"),
    "T-ataj": ("atajadas_ou", "atajadas_totales_proj"),
    "L-ataj": ("atajadas_ou_local", "atajadas_local_proj"),
    "V-ataj": ("atajadas_ou_visitante", "atajadas_visitante_proj"),
}


def resumen(sim, stats_a, stats_b):
    """Columnas planas: proj_<serie>, o_<serie>_<linea> (Over), y el filtro
    de produccion (tiene_datos_suficientes de cada equipo)."""
    FM = H._G["FM"]
    out = {
        "datos_ok_local": bool(FM.tiene_datos_suficientes(stats_a)),
        "datos_ok_visitante": bool(FM.tiene_datos_suficientes(stats_b)),
        "n_stats12_local": (stats_a or {}).get("n_partidos_stats_12m"),
        "n_stats12_visitante": (stats_b or {}).get("n_partidos_stats_12m"),
    }
    for serie, (k_ou, k_proj) in SERIES.items():
        out[f"proj_{serie}"] = sim.get(k_proj)
        ou = sim.get(k_ou) or {}
        for linea, d in ou.items():
            out[f"o_{serie}_{float(linea)}"] = d.get("over")
    return out


_CAP = {}


def _iniciar():
    sys.path.insert(0, H.SERVICES)
    import data_loader as DL
    DL.CSV_FUTBOL = os.environ["CSV_TIROS"]
    H._iniciar()
    FS = H._G["FS"]
    orig = FS.simular

    def sim_captura(*a, **kw):
        r = orig(*a, **kw)
        if r is not None and r[0] is not None:
            _CAP.update(resumen(*r))
        return r

    FS.simular = sim_captura


def correr(fid):
    _CAP.clear()
    out = H.correr_partido(fid)
    out.update(_CAP)
    return out


def _configurar(servicios, csv):
    H.SERVICES = os.path.abspath(servicios)
    os.environ["CSV_TIROS"] = os.path.abspath(csv)
    os.environ["SERVICIOS_TIROS"] = H.SERVICES


def _iniciar_pool():
    H.SERVICES = os.environ["SERVICIOS_TIROS"]
    _iniciar()


# ------------------------------------------------------------ verificacion
def verificar(n):
    """Harness con reloj congelado en T contra main sin parches, mismos
    partidos NS, mismo CSV. Devuelve (iguales, distintos, detalle)."""
    import importlib
    _iniciar()
    v = H._G["validas"]
    t = v["fecha"].dt.tz_convert("UTC")
    ahora = pd.Timestamp.now(tz="UTC").floor("s")
    ns = v[(v["estado"] == "NS") & (t > ahora) & (t < ahora + pd.Timedelta(days=21))].sort_values("fecha")
    ns = ns.head(n * 8)  # de mas: muchos no tienen datos de tiros

    # 1) harness: corte = ahora (no inicio - 1h), filas NS tal cual
    harness_res = {}
    crudo, validas, FS = H._G["crudo"], H._G["validas"], H._G["FS"]
    H._AHORA = ahora
    df_cut = validas[(validas["fecha"] < ahora) | (validas["estado"] == "NS")]
    crudo_cut = crudo[(crudo["fecha"] < ahora) | (crudo["estado"] == "NS")]
    FS._registrar_fuente_h2h(df_cut, crudo_cut)
    for _, f in ns.iterrows():
        _CAP.clear()
        H._limpiar_caches()
        FS.simular(df_cut, f["equipo_local"], f["equipo_visitante"])
        if _CAP.get("proj_T-arco") is not None:
            harness_res[f["fixture_id"]] = dict(_CAP)

    # 2) main sin parches: modulos recien importados, reloj real
    for m in ("futbol_service", "football_model", "modelo_presion", "data_loader", "elo_ranking", "simulator"):
        sys.modules.pop(m, None)
    cwd = os.getcwd()
    os.chdir(H.SERVICES)
    import data_loader as DL2
    DL2.CSV_FUTBOL = os.environ["CSV_TIROS"]
    import futbol_service as FS2
    import football_model as FM2
    os.chdir(cwd)
    df2 = FS2.cargar_df() if hasattr(FS2, "cargar_df") else None
    iguales, distintos, detalle = 0, 0, []
    H._G["FM"] = FM2
    for fid, hres in list(harness_res.items())[:n]:
        f = ns[ns["fixture_id"] == fid].iloc[0]
        sim, sa, sb = FS2.simular(df2, f["equipo_local"], f["equipo_visitante"])
        mres = resumen(sim, sa, sb)
        claves = set(hres) | set(mres)
        dif = [c for c in claves if hres.get(c) != mres.get(c)]
        if dif:
            distintos += 1
            detalle.append((fid, f["equipo_local"], f["equipo_visitante"],
                            [(c, hres.get(c), mres.get(c)) for c in sorted(dif)[:5]]))
        else:
            iguales += 1
    return iguales, distintos, detalle, len(harness_res)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--servicios", required=True)
    ap.add_argument("--csv", required=True)
    ap.add_argument("--desde")
    ap.add_argument("--hasta")
    ap.add_argument("--salida")
    ap.add_argument("--procesos", type=int, default=max(os.cpu_count() - 2, 1))
    ap.add_argument("--limite", type=int, default=0)
    ap.add_argument("--ids", default="")
    ap.add_argument("--verificar", type=int, default=0)
    a = ap.parse_args()
    _configurar(a.servicios, a.csv)

    if a.verificar:
        ig, di, det, n_h = verificar(a.verificar)
        print(f"verificacion: {ig} iguales, {di} distintos (harness con tiros: {n_h})")
        for d in det:
            print("  DISTINTO", d)
        return 0 if di == 0 and ig >= a.verificar else 1

    _iniciar()
    v = H._G["validas"]
    t = v["fecha"].dt.tz_convert("UTC")
    cor = v["corners_local"].fillna(0) + v["corners_visitante"].fillna(0)
    sel = v[v["estado"].isin(H.TERMINADOS) & (cor > 0) & (t >= pd.Timestamp(a.desde, tz="UTC"))
            & (t < pd.Timestamp(a.hasta, tz="UTC") + pd.Timedelta(days=1))].sort_values("fecha")
    ids = sel["fixture_id"].tolist()
    if a.ids:
        quiero = {float(x) for x in a.ids.split(",")}
        ids = [i for i in ids if float(i) in quiero]
    ids = ids[: a.limite or None]
    print(f"{len(ids)} partidos entre {a.desde} y {a.hasta}; {a.procesos} procesos", flush=True)
    t0, filas = time.time(), []
    with Pool(a.procesos, initializer=_iniciar_pool) as pool:
        for i, r in enumerate(pool.imap_unordered(correr, ids, chunksize=8), 1):
            filas.append(r)
            if i % 500 == 0 or i == len(ids):
                print(f"  {i}/{len(ids)}  {time.time() - t0:.0f}s", flush=True)
                pd.DataFrame(filas).to_csv(a.salida, index=False)
    pd.DataFrame(filas).to_csv(a.salida, index=False)
    print("listo:", a.salida)


if __name__ == "__main__":
    sys.exit(main())
