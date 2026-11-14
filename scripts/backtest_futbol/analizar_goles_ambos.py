"""Eleccion, criterios e informativo de PREREGISTRO_goles_ambos.md.

Uso desde backend/:
  python scripts/backtest_futbol/analizar_goles_ambos.py --eleccion pred_ga_2025h2.csv \
      --evaluacion pred_ga_2026.csv --salida resultados_goles_ambos.json
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

S_CANDIDATOS = (0.9, 0.8, 0.7, 0.6)   # orden = desempate (mas cercano al actual primero)
A_CANDIDATOS = (0.5, 0.0)
UMBRAL, TOL_C4 = 0.70, -0.03


class FrecuenciasLinea:
    """Tasa de over de una linea de goles en la liga, [t-365d, t), como R1."""

    def __init__(self, hist, linea):
        h = hist.sort_values("t")
        self.glob = self._armar(h, linea)
        self.liga = {lg: self._armar(g, linea) for lg, g in h.groupby("liga")}

    @staticmethod
    def _armar(g, linea):
        y = ((g["gl"] + g["gv"]) > linea).astype(float).to_numpy()
        return g["t"].astype("int64").to_numpy(), np.concatenate([[0.0], np.cumsum(y)])

    def tasa(self, liga, corte):
        t1, t0 = corte.value, (corte - pd.Timedelta(days=A.DIAS_R1)).value
        for serie, minimo in ((self.liga.get(liga), A.MIN_LIGA), (self.glob, 1)):
            if serie is None:
                continue
            ts, acum = serie
            i, j = np.searchsorted(ts, t0, "left"), np.searchsorted(ts, t1, "left")
            if j - i >= minimo:
                return (acum[j] - acum[i]) / (j - i)
        return np.nan


def preparar(ruta, crudo, validas, freq, f15, f35, ppg):
    d = pd.read_csv(ruta).merge(crudo, on="fixture_id", how="left")
    d["gl"], d["gv"] = A.goles_90(d)
    n_total = len(d)
    ok = (d["p_local"].notna() & (d["error"].fillna("") == "") & (d["n_prev_local"] >= A.MIN_PREVIOS)
          & (d["n_prev_visitante"] >= A.MIN_PREVIOS) & d["gl"].notna())
    var_cols = [f"{m}_s{s}" for m in ("pl", "pe", "pv", "o15", "o25", "o35", "ambos") for s in S_CANDIDATOS]
    sin_var = ok & d[var_cols].isna().any(axis=1)
    d = d[ok & ~sin_var].copy().reset_index(drop=True)
    d["t"] = d["fecha"].dt.tz_convert("UTC")
    d["corte"] = d["t"] - pd.Timedelta(hours=1)
    iso = d["t"].dt.isocalendar()
    d["semana"] = iso["year"].astype(str) + "-" + iso["week"].astype(str).str.zfill(2)
    R1 = np.array([freq.tasas(lg, c)[0] for lg, c in zip(d["liga"], d["corte"])])
    d["r1_l"], d["r1_e"], d["r1_v"], d["r1_o25"], d["r1_ambos"] = R1.T
    d["r1_o15"] = [f15.tasa(lg, c) for lg, c in zip(d["liga"], d["corte"])]
    d["r1_o35"] = [f35.tasa(lg, c) for lg, c in zip(d["liga"], d["corte"])]
    d["ppg_l"] = [ppg.ppg(e, c) for e, c in zip(d["equipo_local"], d["corte"])]
    d["ppg_v"] = [ppg.ppg(e, c) for e, c in zip(d["equipo_visitante"], d["corte"])]
    # H-A: peso efectivo de la mezcla con los cruces
    c, f, tasa = d["ambos_s1"], d["ambos_final"], d["tasa_h2h"]
    den = tasa - c
    d["w_h2h"] = np.where(den.abs() > 1e-12, (f - c) / den.where(den.abs() > 1e-12, 1), 0.0)
    d["tasa_h2h"] = tasa.fillna(0.0)
    return d, {"filas": n_total, "evaluados": len(d), "sin_variantes_(mu_nan)": int(sin_var.sum())}


def p1x2(d, s):
    P = d[[f"pl_s{s}", f"pe_s{s}", f"pv_s{s}"]].to_numpy(float)
    return P / P.sum(axis=1, keepdims=True)


def ambos(d, s, a):
    c_s = d[f"ambos_s{s}"].to_numpy(float)
    return c_s + a * d["w_h2h"].to_numpy() * (d["tasa_h2h"].to_numpy() - c_s)


def resultados(d):
    Y = np.column_stack([d["gl"] > d["gv"], d["gl"] == d["gv"], d["gl"] < d["gv"]]).astype(float)
    tot = (d["gl"] + d["gv"]).to_numpy()
    return Y, (tot > 1.5).astype(float), (tot > 2.5).astype(float), (tot > 3.5).astype(float), \
        ((d["gl"] > 0) & (d["gv"] > 0)).astype(float).to_numpy()


def mejora(m_ref, m_var, sem):
    media, lo, hi = A.ic_bloques(m_ref - m_var, sem)
    return {"ref": A.r4(m_ref.mean()), "variante": A.r4(m_var.mean()), "mejora": A.r4(media),
            "ic90": [round(lo, 5), round(hi, 5)]}


def c4_parcial(pares, sem):
    ps = np.concatenate([p for p, _ in pares]); ys = np.concatenate([y for _, y in pares])
    bs = np.concatenate([sem for _ in pares])
    m = ps >= UMBRAL
    if not m.any():
        return {"n": 0, "pasa": True}
    media, lo, hi = A.ic_bloques(ys[m] - ps[m], bs[m])
    return {"n": int(m.sum()), "prob_media": A.r4(ps[m].mean()), "tasa_real": A.r4(ys[m].mean()),
            "diferencia": A.r4(media), "ic90": [round(lo, 5), round(hi, 5)], "pasa": bool(hi >= TOL_C4)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--eleccion", required=True)
    ap.add_argument("--evaluacion", required=True)
    ap.add_argument("--salida", required=True)
    a = ap.parse_args()

    crudo, validas, _ = A.cargar_resultados()
    gl, gv = A.goles_90(crudo)
    hist = crudo.assign(gl=gl, gv=gv, t=crudo["fecha"].dt.tz_convert("UTC"))
    hist = hist[hist["estado"].isin(A.TERMINADOS) & hist["gl"].notna()]
    hv = hist[hist["fixture_id"].isin(validas["fixture_id"])]
    freq, f15, f35, ppg = A.Frecuencias(hv), FrecuenciasLinea(hv, 1.5), FrecuenciasLinea(hv, 3.5), A.PuntosPorPartido(hist)

    res = {}
    # ---------------- Eleccion (julio-diciembre 2025)
    e, res["n_eleccion"] = preparar(a.eleccion, crudo, validas, freq, f15, f35, ppg)
    _, _, yo25, _, ya = resultados(e)
    brier_s = {s: round(float(A.brier_bin(e[f"o25_s{s}"].to_numpy(), yo25).mean()), 4) for s in (1,) + S_CANDIDATOS}
    s_elegido = min(S_CANDIDATOS, key=lambda s: (brier_s[s], S_CANDIDATOS.index(s)))
    brier_a = {a_: round(float(A.brier_bin(ambos(e, s_elegido, a_), ya).mean()), 4) for a_ in (1.0,) + A_CANDIDATOS}
    a_elegido = min(A_CANDIDATOS, key=lambda x: (brier_a[x], A_CANDIDATOS.index(x)))
    res["eleccion"] = {"brier_over25_por_s": {str(k): v for k, v in brier_s.items()}, "s_elegido": s_elegido,
                       "brier_ambos_por_a_con_s_elegido": {str(k): v for k, v in brier_a.items()},
                       "a_elegido": a_elegido}

    # ---------------- Evaluacion (retrospectivo 2026)
    d, res["n_evaluacion"] = preparar(a.evaluacion, crudo, validas, freq, f15, f35, ppg)
    Y, yo15, yo25, yo35, ya = resultados(d)
    sem = d["semana"].to_numpy()
    yi = Y.argmax(axis=1)

    # H-B
    hb_o25 = mejora(A.brier_bin(d["o25_s1"].to_numpy(), yo25), A.brier_bin(d[f"o25_s{s_elegido}"].to_numpy(), yo25), sem)
    hb_1x2 = mejora(A.brier_1x2(p1x2(d, 1), Y), A.brier_1x2(p1x2(d, s_elegido), Y), sem)
    P_s = p1x2(d, s_elegido)
    P_r1 = d[["r1_l", "r1_e", "r1_v"]].to_numpy(float)
    P_r1 = P_r1 / P_r1.sum(axis=1, keepdims=True)
    c1_brier = mejora(A.brier_1x2(P_r1, Y), A.brier_1x2(P_s, Y), sem)
    pick_r2 = np.where(np.nan_to_num(d["ppg_v"].to_numpy(), nan=-1) > np.nan_to_num(d["ppg_l"].to_numpy(), nan=-1), 2, 0)
    ac_s, ac_r2 = float((P_s.argmax(axis=1) == yi).mean()), float((pick_r2 == yi).mean())
    c1_pasa = c1_brier["ic90"][0] > 0 and ac_s >= ac_r2
    hb_entra = hb_o25["ic90"][0] > 0 and hb_1x2["ic90"][1] >= 0 and c1_pasa
    res["H_B"] = {"s": s_elegido, "over25": hb_o25, "1x2_no_empeora": hb_1x2,
                  "C1_con_HB": {**c1_brier, "acierto": A.r4(ac_s), "acierto_R2": A.r4(ac_r2), "pasa": bool(c1_pasa)},
                  "entra": bool(hb_entra)}
    sB = s_elegido if hb_entra else 1

    # H-A
    ha = mejora(A.brier_bin(ambos(d, sB, 1.0), ya), A.brier_bin(ambos(d, sB, a_elegido), ya), sem)
    ha_entra = ha["ic90"][0] > 0
    res["H_A"] = {"a": a_elegido, "sobre_s": sB, "ambos": ha, "entra": bool(ha_entra)}
    aA = a_elegido if ha_entra else 1.0
    res["modelo_final"] = {"s": sB, "a": aA}

    # Volver a mostrar
    p_o25 = d[f"o25_s{sB}"].to_numpy(float)
    p_am = ambos(d, sB, aA)
    c2 = mejora(A.brier_bin(d["r1_o25"].to_numpy(), yo25), A.brier_bin(p_o25, yo25), sem)
    c4g = c4_parcial([(p_o25, yo25), (1 - p_o25, 1 - yo25)], sem)
    c3 = mejora(A.brier_bin(d["r1_ambos"].to_numpy(), ya), A.brier_bin(p_am, ya), sem)
    c4a = c4_parcial([(p_am, ya), (1 - p_am, 1 - ya)], sem)
    res["mostrar_goles_ou"] = {"C2": {**c2, "pasa": bool(c2["ic90"][0] > 0)}, "C4_goles": c4g,
                               "vuelve": bool(c2["ic90"][0] > 0 and c4g["pasa"])}
    res["mostrar_ambos_marcan"] = {"C3": {**c3, "pasa": bool(c3["ic90"][0] > 0)}, "C4_ambos": c4a,
                                   "vuelve": bool(c3["ic90"][0] > 0 and c4a["pasa"])}

    # ---------------- Informativo
    inf = {}
    for linea, y, col in (("1.5", yo15, "o15"), ("3.5", yo35, "o35")):
        p = d[f"{col}_s{sB}"].to_numpy(float)
        r1 = d[f"r1_{col}"].to_numpy(float)
        m = ~np.isnan(r1)
        inf[f"over{linea}"] = {**mejora(A.brier_bin(r1[m], y[m]), A.brier_bin(p[m], y[m]), sem[m]),
                               "nota": "ref = R1 de esa linea; variante = modelo final",
                               "brier_modelo_actual": A.r4(A.brier_bin(d[f"{col}_s1"].to_numpy()[m], y[m]).mean()),
                               "calibracion_final": A.calibracion_bandas(p, y)}
    cand = {}
    for s in (1,) + S_CANDIDATOS:
        for a_ in (1.0,) + A_CANDIDATOS:
            pa = ambos(d, s, a_)
            cand[f"s{s}_a{a_}"] = {"brier_over25": A.r4(A.brier_bin(d[f"o25_s{s}"].to_numpy(), yo25).mean()),
                                   "brier_ambos": A.r4(A.brier_bin(pa, ya).mean()),
                                   "brier_1x2": A.r4(A.brier_1x2(p1x2(d, s), Y).mean()),
                                   "acierto_1x2": A.r4((p1x2(d, s).argmax(axis=1) == yi).mean())}
    inf["candidatos_en_evaluacion"] = cand
    tot = d["gl"] + d["gv"]
    for s in (1, sB):
        lam = (d["mu_local"] + s * (d["lam_a"] - d["mu_local"])) + (d["mu_visitante"] + s * (d["lam_b"] - d["mu_visitante"]))
        inf[f"pendiente_goles_reales_sobre_esperados_s{s}"] = round(float(np.polyfit(lam, tot, 1)[0]), 3)
    inf["calibracion_local_final"] = A.calibracion_bandas(p1x2(d, sB)[:, 0], Y[:, 0])
    inf["calibracion_over25_final"] = A.calibracion_bandas(p_o25, yo25)
    inf["calibracion_ambos_final"] = A.calibracion_bandas(p_am, ya)
    res["informativo"] = inf

    with open(a.salida, "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1)

    print("Eleccion:", res["eleccion"])
    print("H-B:", {k: res["H_B"][k] for k in ("s", "entra")}, "over25", hb_o25, "| 1x2", hb_1x2, "| C1", res["H_B"]["C1_con_HB"])
    print("H-A:", {k: res["H_A"][k] for k in ("a", "sobre_s", "entra")}, res["H_A"]["ambos"])
    print("Modelo final:", res["modelo_final"])
    print("Goles O/U vuelve:", res["mostrar_goles_ou"]["vuelve"], res["mostrar_goles_ou"])
    print("Ambos marcan vuelve:", res["mostrar_ambos_marcan"]["vuelve"], res["mostrar_ambos_marcan"])


if __name__ == "__main__":
    main()
