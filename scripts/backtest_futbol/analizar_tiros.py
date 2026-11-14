"""Analisis de PREREGISTRO_tiros_atajadas.md (congelado 2c1c326; escrito antes de ver resultados).

Uso desde backend/ (este worktree):
  python scripts/backtest_futbol/analizar_tiros.py --servicios RUTA_MAIN/app/services \
      --csv datos_tiros_eea826c.csv --eleccion pred_ti_2025h2.csv \
      --evaluacion pred_ti_2026a.csv pred_ti_2026b.csv \
      --salida scripts/backtest_futbol/resultados_tiros.json

Nueve series (T/L/V x arco/tiros/ataj), cada una decide sola:
  linea central = tasa real de Over en la eleccion (jul-dic 2025) mas cerca de
                  50% (3 decimales, empate -> la mas baja), sin el modelo;
  C5 = Brier de Over en la linea central mejora contra R1 (IC90 inferior > 0);
  C4 = probabilidades >= 70% no se pasan en mas de 3 pt (IC90 superior de
       real - prometido >= -3 pt); en los totales entran la central y las
       dos lineas de Top Picks, Over y Under; por equipo, solo la central.
       Sin ningun >= 70%: C4 se da por cumplido y se anota.
"""
import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import analizar as A  # noqa: E402

UMBRAL, TOL_C4 = 0.70, -0.03
# mercado: (columna local, columna visitante, lineas de Top Picks del total)
MERCADOS = {
    "arco": ("tiros_arco_local", "tiros_arco_visitante", (6.5, 7.5)),
    "tiros": ("tiros_total_local", "tiros_total_visitante", (23.5, 24.5)),
    "ataj": ("atajadas_local", "atajadas_visitante", (4.5, 5.5)),
}
SERIES = [f"{lado}-{m}" for m in MERCADOS for lado in ("T", "L", "V")]
CORTE_COBERTURA = pd.Timestamp("2026-04-01", tz="UTC")   # stats completas desde abr-2026


def real(df, serie):
    lado, m = serie.split("-")
    cl, cv, _ = MERCADOS[m]
    return {"T": df[cl] + df[cv], "L": df[cl], "V": df[cv]}[lado]


def lineas_de(df, serie):
    pre = f"o_{serie}_"
    return sorted(float(c[len(pre):]) for c in df.columns if c.startswith(pre))


class TasaLiga:
    """R1 por serie y linea: tasa de Over en la liga en [corte-365d, corte),
    partidos terminados con stats verificadas y con los dos datos del
    mercado; con menos de 50, la tasa global de esa ventana."""

    def __init__(self, hist, serie, lineas):
        h = hist.sort_values("t")
        x = real(h, serie)
        h = h[x.notna()]
        x = x[x.notna()]
        self.lineas = lineas
        self.glob = self._armar(h, x)
        self.liga = {lg: self._armar(g, x.loc[g.index]) for lg, g in h.groupby("liga")}

    def _armar(self, g, x):
        ts = g["t"].astype("int64").to_numpy()
        acum = {ln: np.concatenate([[0.0], np.cumsum((x.to_numpy() > ln).astype(float))]) for ln in self.lineas}
        return ts, acum

    def tasa(self, liga, corte, ln):
        t1, t0 = corte.value, (corte - pd.Timedelta(days=A.DIAS_R1)).value
        for serie, minimo in ((self.liga.get(liga), A.MIN_LIGA), (self.glob, 1)):
            if serie is None:
                continue
            ts, acum = serie
            i, j = np.searchsorted(ts, t0, "left"), np.searchsorted(ts, t1, "left")
            if j - i >= minimo:
                return (acum[ln][j] - acum[ln][i]) / (j - i)
        return np.nan


def preparar(rutas, crudo):
    d = pd.concat([pd.read_csv(r) for r in rutas], ignore_index=True)
    n = len(d)
    d = d.merge(crudo, on="fixture_id", how="left")
    co = d["corners_local"].fillna(0) + d["corners_visitante"].fillna(0)
    ok = ((d["error"].fillna("") == "") & (d["n_prev_local"] >= A.MIN_PREVIOS)
          & (d["n_prev_visitante"] >= A.MIN_PREVIOS) & d["estado"].isin(A.TERMINADOS) & (co > 0)
          & d["datos_ok_local"].fillna(False).astype(bool) & d["datos_ok_visitante"].fillna(False).astype(bool))
    d = d[ok].copy().reset_index(drop=True)
    d["t"] = d["fecha"].dt.tz_convert("UTC")
    iso = d["t"].dt.isocalendar()
    d["semana"] = iso["year"].astype(str) + "-" + iso["week"].astype(str).str.zfill(2)
    d["corte"] = d["t"] - pd.Timedelta(hours=1)
    return d, {"filas": n, "con_filtros_comunes": len(d)}


def de_serie(d, serie):
    """Filas de la serie: el modelo la devuelve y estan los dos datos del mercado."""
    _, m = serie.split("-")
    cl, cv, _ = MERCADOS[m]
    ok = d[f"proj_{serie}"].notna() & d[cl].notna() & d[cv].notna()
    return d[ok].reset_index(drop=True)


def linea_central(e, serie):
    x = real(e, serie).to_numpy(float)
    tasas = {ln: round(float((x > ln).mean()), 3) for ln in lineas_de(e, serie)}
    dist = {ln: round(abs(t - 0.5), 3) for ln, t in tasas.items()}
    mejor = min(dist.values())
    return min(ln for ln, v in dist.items() if v == mejor), tasas


def mejora(m_ref, m_var, sem):
    media, lo, hi = A.ic_bloques(m_ref - m_var, sem)
    return {"ref": A.r4(m_ref.mean()), "modelo": A.r4(m_var.mean()), "mejora": A.r4(media),
            "ic90": [round(lo, 5), round(hi, 5)]}


def c5(d, serie, ln, r1):
    y = (real(d, serie) > ln).astype(float).to_numpy()
    p = d[f"o_{serie}_{ln}"].to_numpy(float)
    rr = r1.to_numpy(float)
    m = ~np.isnan(rr)
    r = mejora(A.brier_bin(rr[m], y[m]), A.brier_bin(p[m], y[m]), d["semana"].to_numpy()[m])
    r["n"] = int(m.sum())
    r["pasa"] = bool(r["ic90"][0] > 0)
    return r


def c4(d, serie, lineas):
    x = real(d, serie).to_numpy(float)
    ps, ys, bs = [], [], []
    for ln in lineas:
        p = d[f"o_{serie}_{ln}"].to_numpy(float)
        y = (x > ln).astype(float)
        ps += [p, 1 - p]; ys += [y, 1 - y]; bs += [d["semana"].to_numpy()] * 2
    ps, ys, bs = np.concatenate(ps), np.concatenate(ys), np.concatenate(bs)
    m = ps >= UMBRAL
    if not m.any():
        return {"lineas": list(lineas), "n": 0, "pasa": True, "nota": "sin pronosticos >= 70%: se da por cumplido"}
    media, lo, hi = A.ic_bloques(ys[m] - ps[m], bs[m])
    return {"lineas": list(lineas), "n": int(m.sum()), "prob_media": A.r4(ps[m].mean()),
            "tasa_real": A.r4(ys[m].mean()), "diferencia": A.r4(media),
            "ic90": [round(lo, 5), round(hi, 5)], "pasa": bool(hi >= TOL_C4)}


def top20_volumen(crudo_stats):
    """20 equipos con mas tiros totales propios por partido en ene-jun 2025
    (minimo 10 partidos con dato), antes de la eleccion."""
    h = crudo_stats[(crudo_stats["t"] >= pd.Timestamp("2025-01-01", tz="UTC"))
                    & (crudo_stats["t"] < pd.Timestamp("2025-07-01", tz="UTC"))]
    filas = pd.concat([
        h[["equipo_local", "tiros_total_local"]].set_axis(["eq", "x"], axis=1),
        h[["equipo_visitante", "tiros_total_visitante"]].set_axis(["eq", "x"], axis=1)]).dropna()
    g = filas.groupby("eq")["x"].agg(["mean", "size"])
    return set(g[g["size"] >= 10].sort_values("mean", ascending=False).head(20).index)


def informativo(d, serie, central, r1s, top20):
    x = real(d, serie)
    out = {"n": len(d), "proyeccion_media": A.r4(d[f"proj_{serie}"].mean()), "real_medio": A.r4(x.mean()),
           "sesgo_medio_proj_menos_real": A.r4((d[f"proj_{serie}"] - x).mean()),
           "real_var_sobre_media": A.r4(x.var() / x.mean()),
           "calibracion_central": A.calibracion_bandas(d[f"o_{serie}_{central}"].to_numpy(float),
                                                      (x > central).astype(float).to_numpy())}
    lineas = {}
    for ln, r1 in r1s.items():
        y = (x > ln).astype(float).to_numpy()
        rr = r1.to_numpy(float)
        m = ~np.isnan(rr)
        lineas[str(ln)] = {"tasa_real": A.r4(y.mean()),
                           "brier_modelo": A.r4(A.brier_bin(d[f"o_{serie}_{ln}"].to_numpy(float)[m], y[m]).mean()),
                           "brier_r1": A.r4(A.brier_bin(rr[m], y[m]).mean())}
    out["lineas"] = lineas
    lado, m = serie.split("-")
    if m == "tiros" and lado in ("L", "V"):
        eq = d["equipo_local"] if lado == "L" else d["equipo_visitante"]
        es = eq.isin(top20)
        out["top20_volumen"] = {
            "n": int(es.sum()),
            "sesgo_real_menos_proj_top20": A.r4((x[es] - d.loc[es, f"proj_{serie}"]).mean()),
            "sesgo_real_menos_proj_resto": A.r4((x[~es] - d.loc[~es, f"proj_{serie}"]).mean())}
    if lado in ("L", "V"):
        tope = {"arco": 9.0, "tiros": 22.0, "ataj": 11.0}[m]
        out["proj_cerca_del_tope_(>=97%)"] = int((d[f"proj_{serie}"] >= 0.97 * tope).sum())
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--servicios", required=True)
    ap.add_argument("--csv", required=True)
    ap.add_argument("--eleccion", nargs="+", required=True)
    ap.add_argument("--evaluacion", nargs="+", required=True)
    ap.add_argument("--salida", required=True)
    a = ap.parse_args()
    A.SERVICES = os.path.abspath(a.servicios)
    sys.path.insert(0, A.SERVICES)
    import data_loader as DL
    DL.CSV_FUTBOL = os.path.abspath(a.csv)

    crudo, validas, _ = A.cargar_resultados()
    h = crudo[crudo["fixture_id"].isin(validas["fixture_id"]) & crudo["estado"].isin(A.TERMINADOS)]
    h = h.assign(t=h["fecha"].dt.tz_convert("UTC"))
    h = h[(h["corners_local"].fillna(0) + h["corners_visitante"].fillna(0)) > 0]
    top20 = top20_volumen(h)

    e_all, n_e = preparar(a.eleccion, crudo)
    d_all, n_d = preparar(a.evaluacion, crudo)
    res = {"n_eleccion": n_e, "n_evaluacion": n_d, "series": {}, "informativo": {}}

    for serie in SERIES:
        e, d = de_serie(e_all, serie), de_serie(d_all, serie)
        central, tasas_e = linea_central(e, serie)
        lado, m = serie.split("-")
        lineas_c4 = sorted({central, *MERCADOS[m][2]}) if lado == "T" else [central]
        lineas_r1 = sorted({central, *MERCADOS[m][2]}) if lado == "T" else [central]
        tasa = TasaLiga(h, serie, lineas_r1)
        r1s = {ln: pd.Series([tasa.tasa(lg, c, ln) for lg, c in zip(d["liga"], d["corte"])]) for ln in lineas_r1}
        rc5 = c5(d, serie, central, r1s[central])
        rc4 = c4(d, serie, lineas_c4)
        pasa = bool(rc5["pasa"] and rc4["pasa"])
        res["series"][serie] = {
            "n_eleccion": len(e), "n_evaluacion": len(d), "linea_central": central,
            "tasa_real_central_eleccion": tasas_e[central], "C5": rc5, "C4": rc4, "pasa": pasa,
            "si_falla": ("se oculta el O/U y la proyeccion del total; bloque gris con el promedio de la liga "
                         f"O/U {central}; fuera de Top Picks, value bets y analisis IA") if lado == "T"
                        else "se oculta la serie sin reemplazo"}
        res["informativo"][serie] = informativo(d, serie, central, r1s, top20)
        # C5 por tramo de cobertura de stats (informativo)
        tramos = {}
        for nombre, msk in (("hasta_mar26", d["t"] < CORTE_COBERTURA), ("desde_abr26", d["t"] >= CORTE_COBERTURA)):
            dd = d[msk.to_numpy()].reset_index(drop=True)
            if len(dd) > 50:
                tramos[nombre] = c5(dd, serie, central, r1s[central][msk.to_numpy()].reset_index(drop=True))
        res["informativo"][serie]["C5_por_tramo_cobertura"] = tramos
        res["informativo"][serie]["tasas_reales_eleccion"] = {str(k): v for k, v in tasas_e.items()}

    res["resumen"] = {s: ("PASA" if v["pasa"] else "NO PASA") + f" (C5 {'si' if v['C5']['pasa'] else 'no'}, "
                      f"C4 {'si' if v['C4']['pasa'] else 'no'})" for s, v in res["series"].items()}
    res["fallan_todas"] = not any(v["pasa"] for v in res["series"].values())
    with open(a.salida, "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1)
    print(json.dumps(res["resumen"], ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
