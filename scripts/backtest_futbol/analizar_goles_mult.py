"""Analisis de PREREGISTRO_multiplicador_goles.md (escrito antes de ver resultados).

Uso desde backend/:
  python scripts/backtest_futbol/analizar_goles_mult.py --eleccion pred_gm_2025h2.csv \
      --evaluacion pred_gm_2026.csv --salida scripts/backtest_futbol/resultados_goles_mult.json \
      [--anterior pred_ga_2026.csv]
--anterior (informativo): corrida previa con el harness sin arreglar, para
contar cuantos partidos cambian por el cache de nombres (enmienda 1).
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

F_CANDIDATOS = (1.0, 0.5, 0.0)   # orden = desempate (mas cercano al actual primero)
UMBRAL, TOL_C4 = 0.70, -0.03
BANDA_SACAR = 0.0010


def suf(f):
    return "f1" if f == 1.0 else f"f{f}"


def preparar(ruta, crudo, freq, ppg):
    d = pd.read_csv(ruta).merge(crudo, on="fixture_id", how="left")
    n = len(d)
    d["gl"], d["gv"] = A.goles_90(d)
    # Sin variantes = el multiplicador no se calculo (excepcion en
    # modelo_presion -> 1,0): todas las variantes son iguales a f = 1.
    sin_var_m = d["pl_f1"].notna() & d["pl_f0.0"].isna()
    sin_var = int(sin_var_m.sum())
    for col in [c for c in d.columns if c.endswith("_f1")]:
        base = col[:-3]
        for f in ("0.5", "0.0"):
            d.loc[sin_var_m, f"{base}_f{f}"] = d.loc[sin_var_m, col]
    for c in ("m_local", "m_visitante"):
        d[c] = d[c].fillna(1.0) if c in d else 1.0
    for c in ("con_tiros_local", "con_tiros_visitante"):
        d[c] = d[c].fillna(False) if c in d else False
    ok = ((d["error"].fillna("") == "") & d["pl_f1"].notna()
          & (d["n_prev_local"] >= A.MIN_PREVIOS) & (d["n_prev_visitante"] >= A.MIN_PREVIOS) & d["gl"].notna())
    d = d[ok].copy().reset_index(drop=True)
    d["t"] = d["fecha"].dt.tz_convert("UTC")
    d["corte"] = d["t"] - pd.Timedelta(hours=1)
    iso = d["t"].dt.isocalendar()
    d["semana"] = iso["year"].astype(str) + "-" + iso["week"].astype(str).str.zfill(2)
    R1 = np.array([freq.tasas(lg, c)[0] for lg, c in zip(d["liga"], d["corte"])])
    d["r1_l"], d["r1_e"], d["r1_v"], d["r1_o25"], d["r1_ambos"] = R1.T
    d["ppg_l"] = [ppg.ppg(e, c) for e, c in zip(d["equipo_local"], d["corte"])]
    d["ppg_v"] = [ppg.ppg(e, c) for e, c in zip(d["equipo_visitante"], d["corte"])]
    return d, {"filas": n, "evaluados": len(d), "sin_variantes_(multiplicador_1)": sin_var}


def P(d, s):
    x = d[[f"pl_{s}", f"pe_{s}", f"pv_{s}"]].to_numpy(float)
    return x / x.sum(axis=1, keepdims=True)


def Y(d):
    return np.column_stack([d["gl"] > d["gv"], d["gl"] == d["gv"], d["gl"] < d["gv"]]).astype(float)


def mejora(m_ref, m_var, sem):
    media, lo, hi = A.ic_bloques(m_ref - m_var, sem)
    return {"ref": A.r4(m_ref.mean()), "variante": A.r4(m_var.mean()), "mejora": A.r4(media),
            "ic90": [round(lo, 5), round(hi, 5)]}


def c1(d, s):
    p, y, sem = P(d, s), Y(d), d["semana"].to_numpy()
    pr1 = d[["r1_l", "r1_e", "r1_v"]].to_numpy(float)
    pr1 = pr1 / pr1.sum(axis=1, keepdims=True)
    b = mejora(A.brier_1x2(pr1, y), A.brier_1x2(p, y), sem)
    ac = (p.argmax(axis=1) == y.argmax(axis=1)).mean()
    pick_r2 = np.where(np.nan_to_num(d["ppg_v"].to_numpy(float), nan=-1) > np.nan_to_num(d["ppg_l"].to_numpy(float), nan=-1), 2, 0)
    ac_r2 = (pick_r2 == y.argmax(axis=1)).mean()
    b.update(acierto=A.r4(ac), acierto_R2=A.r4(ac_r2), cumple_brier=bool(b["ic90"][0] > 0),
             cumple_acierto=bool(ac >= ac_r2))
    b["pasa"] = b["cumple_brier"] and b["cumple_acierto"]
    return b


def c4(d, s):
    p, y = P(d, s), Y(d)
    ps, ys = p.T.reshape(-1), y.T.reshape(-1)
    bs = np.concatenate([d["semana"].to_numpy()] * 3)
    m = ps >= UMBRAL
    if not m.any():
        return {"n": 0, "pasa": True}
    media, lo, hi = A.ic_bloques(ys[m] - ps[m], bs[m])
    return {"n": int(m.sum()), "prob_media": A.r4(ps[m].mean()), "tasa_real": A.r4(ys[m].mean()),
            "diferencia": A.r4(media), "ic90": [round(lo, 5), round(hi, 5)], "pasa": bool(hi >= TOL_C4)}


def informativo(d, sem):
    y = Y(d)
    dif = d["gl"] - d["gv"]
    yh = np.column_stack([dif > 1, dif == 1, dif < 1]).astype(float)
    y_o25 = ((d["gl"] + d["gv"]) > 2.5).astype(float).to_numpy()
    y_amb = ((d["gl"] > 0) & (d["gv"] > 0)).astype(float).to_numpy()
    out = {}
    for f in F_CANDIDATOS:
        s = suf(f)
        p = P(d, s)
        h = d[[f"hl1_{s}", f"he1_{s}", f"hv1_{s}"]].to_numpy(float)
        out[s] = {
            "brier_1x2": A.r4(A.brier_1x2(p, y).mean()), "logloss_1x2": A.r4(A.logloss_1x2(p, y).mean()),
            "acierto_1x2": A.r4((p.argmax(axis=1) == y.argmax(axis=1)).mean()),
            "brier_doble_1x": A.r4(A.brier_bin(p[:, 0] + p[:, 1], y[:, 0] + y[:, 1]).mean()),
            "brier_doble_x2": A.r4(A.brier_bin(p[:, 1] + p[:, 2], y[:, 1] + y[:, 2]).mean()),
            "brier_hcp_m1": A.r4(A.brier_1x2(h / h.sum(axis=1, keepdims=True), yh).mean()),
            "brier_over25_oculto": A.r4(A.brier_bin(d[f"o25_{s}"].to_numpy(float), y_o25).mean()),
            "brier_ambos_oculto": A.r4(A.brier_bin(d[f"ambos_{s}"].to_numpy(float), y_amb).mean()),
            "calibracion_local": A.calibracion_bandas(p[:, 0], y[:, 0]),
        }
    con = (d["con_tiros_local"].astype(bool) & d["con_tiros_visitante"].astype(bool)).to_numpy()
    sub = {}
    for nombre, m in (("con_tiros_ambos", con), ("sin_tiros_alguno", ~con)):
        if m.sum():
            sub[nombre] = {"n": int(m.sum()), **{suf(f): A.r4(A.brier_1x2(P(d, suf(f))[m], y[m]).mean()) for f in F_CANDIDATOS}}
    out["por_datos_de_tiros"] = sub
    out["multiplicador"] = {"medio_local": A.r4(d["m_local"].mean()), "medio_visitante": A.r4(d["m_visitante"].mean()),
                            "rango_local": [A.r4(d["m_local"].min()), A.r4(d["m_local"].max())],
                            "neutro_ambos": int(((d["m_local"] == 1) & (d["m_visitante"] == 1)).sum())}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--eleccion", required=True)
    ap.add_argument("--evaluacion", required=True)
    ap.add_argument("--salida", required=True)
    ap.add_argument("--anterior")
    a = ap.parse_args()

    crudo, validas, _ = A.cargar_resultados()
    gl, gv = A.goles_90(crudo)
    hist = crudo.assign(gl=gl, gv=gv, t=crudo["fecha"].dt.tz_convert("UTC"))
    hist = hist[hist["estado"].isin(A.TERMINADOS) & hist["gl"].notna()]
    freq = A.Frecuencias(hist[hist["fixture_id"].isin(validas["fixture_id"])])
    ppg = A.PuntosPorPartido(hist)
    res = {}

    e, res["n_eleccion"] = preparar(a.eleccion, crudo, freq, ppg)
    ye = Y(e)
    b = {f: round(float(A.brier_1x2(P(e, suf(f)), ye).mean()), 4) for f in F_CANDIDATOS}
    f_el = next(f for f in F_CANDIDATOS if b[f] == min(b.values()))
    res["eleccion"] = {"brier_1x2_por_f": {str(k): v for k, v in b.items()}, "f_elegido": f_el}

    d, res["n_evaluacion"] = preparar(a.evaluacion, crudo, freq, ppg)
    y, sem = Y(d), d["semana"].to_numpy()
    c1_actual, c4_actual = c1(d, "f1"), c4(d, "f1")
    res["actual_f1"] = {"C1": c1_actual, "C4_1x2": c4_actual}

    hg = {"f": f_el}
    if f_el == 1.0:
        hg["entra"] = False
        hg["nota"] = "la eleccion dejo el multiplicador actual"
    else:
        s = suf(f_el)
        hg["brier_1x2"] = mejora(A.brier_1x2(P(d, "f1"), y), A.brier_1x2(P(d, s), y), sem)
        hg["C1"] = c1(d, s)
        hg["C4_1x2"] = c4(d, s)
        c4_ok = hg["C4_1x2"]["pasa"] or not c4_actual["pasa"]
        hg["entra"] = bool(hg["brier_1x2"]["ic90"][0] > 0 and hg["C1"]["pasa"] and c4_ok)
    res["H_G"] = hg

    sacar = {"aplica": not hg["entra"]}
    if sacar["aplica"]:
        sacar["f0_contra_actual"] = mejora(A.brier_1x2(P(d, "f1"), y), A.brier_1x2(P(d, "f0.0"), y), sem)
        sacar["C1_con_f0"] = c1(d, "f0.0")
        lo, hi = sacar["f0_contra_actual"]["ic90"]
        sacar["dentro_de_banda"] = bool(lo >= -BANDA_SACAR and hi <= BANDA_SACAR)
        sacar["se_saca"] = bool(sacar["dentro_de_banda"] and sacar["C1_con_f0"]["pasa"])
    res["sacar_multiplicador"] = sacar
    res["decision"] = (f"aplicar f={f_el}" if hg["entra"] else
                       "sacar el multiplicador de goles" if sacar.get("se_saca") else "dejar como esta")

    res["informativo"] = {"evaluacion": informativo(d, sem), "eleccion": informativo(e, e["semana"].to_numpy())}
    if a.anterior:
        ant = pd.read_csv(a.anterior)[["fixture_id", "p_local", "p_empate", "p_visitante"]]
        m = d[["fixture_id", "pl_f1", "pe_f1", "pv_f1"]].merge(ant, on="fixture_id")
        dif = (m[["pl_f1", "pe_f1", "pv_f1"]].to_numpy() - m[["p_local", "p_empate", "p_visitante"]].to_numpy())
        cambia = np.abs(dif).max(axis=1) > 1e-9
        res["informativo"]["enmienda1_cache_nombres"] = {
            "partidos_comparados": int(len(m)), "cambian": int(cambia.sum()),
            "cambio_max_pt": A.r4(np.abs(dif).max() * 100) if len(m) else None}
    with open(a.salida, "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1)
    print(json.dumps({k: res[k] for k in ("eleccion", "H_G", "sacar_multiplicador", "decision")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
