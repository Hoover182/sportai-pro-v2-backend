"""Analisis de PREREGISTRO_arbitro_tarjetas.md (escrito antes de ver resultados).

Uso desde backend/:
  python scripts/backtest_futbol/analizar_arbitro.py --csv datos_arbitro_6e660fe.csv \
      --eleccion pred_ar_2025h2.csv --evaluacion pred_ar_2026.csv \
      --salida scripts/backtest_futbol/resultados_arbitro.json
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
import analizar_tarjetas as AT  # noqa: E402

CANDIDATOS = ("base", "L50", "L25", "L10")   # orden = desempate (mas cercano al actual primero)
TRAMOS = ((0, 0), (1, 9), (10, 24), (25, 10 ** 9))
FIN_EVAL = pd.Timestamp("2026-10-29", tz="UTC")   # 1-28 de octubre inclusive


def preparar(rutas, crudo, tasa):
    d = pd.concat([pd.read_csv(r) for r in rutas], ignore_index=True)
    d = d.drop_duplicates("fixture_id").merge(crudo, on="fixture_id", how="left")
    n = len(d)
    cor = d["corners_local"].fillna(0) + d["corners_visitante"].fillna(0)
    ok = ((d["error"].fillna("") == "") & d["o4.5_base"].notna()
          & (d["n_prev_local"] >= A.MIN_PREVIOS) & (d["n_prev_visitante"] >= A.MIN_PREVIOS)
          & d["estado"].isin(A.TERMINADOS) & (cor > 0))
    d = d[ok].copy().reset_index(drop=True)
    d["t"] = d["fecha"].dt.tz_convert("UTC")
    d = d[~d["t"].dt.strftime("%Y-%m").isin(AT.MESES_EXCLUIDOS) & (d["t"] < FIN_EVAL)].reset_index(drop=True)
    d["tl"], d["tv"] = d["tarjetas_local"].fillna(0), d["tarjetas_visitante"].fillna(0)
    d["tj"] = d["tl"] + d["tv"]
    iso = d["t"].dt.isocalendar()
    d["semana"] = iso["year"].astype(str) + "-" + iso["week"].astype(str).str.zfill(2)
    corte = d["t"] - pd.Timedelta(hours=1)
    d["r1"] = [tasa.tasa(lg, c) for lg, c in zip(d["liga"], corte)]
    return d, {"filas": n, "evaluados": len(d)}


def y_linea(d, ln):
    return (d["tj"] > ln).astype(float).to_numpy()


def brier(d, s, ln):
    return A.brier_bin(d[f"o{ln}_{s}"].to_numpy(float), y_linea(d, ln))


def c4_s(d, s):
    """C4 de tarjetas (analizar_tarjetas.c4) con un sufijo cualquiera."""
    return AT.c4(d, s)


def c5(d, s):
    c = AT.mejora(A.brier_bin(d["r1"].to_numpy(float), y_linea(d, 4.5)), brier(d, s, 4.5), d["semana"].to_numpy())
    c["pasa"] = bool(c["ic90"][0] > 0)
    c["n"] = len(d)
    return c


def dist_marb(d, col):
    m = d[col].astype(float)
    return {"media": A.r4(m.mean()), "p5": A.r4(m.quantile(.05)), "p50": A.r4(m.median()),
            "p95": A.r4(m.quantile(.95)), "min": A.r4(m.min()), "max": A.r4(m.max()),
            "fraccion_igual_1": A.r4((m == 1.0).mean())}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--eleccion", required=True, nargs="+")
    ap.add_argument("--evaluacion", required=True, nargs="+")
    ap.add_argument("--salida", required=True)
    a = ap.parse_args()

    sys.path.insert(0, A.SERVICES)
    import data_loader as DL
    DL.CSV_FUTBOL = os.path.abspath(a.csv)
    crudo, validas, _ = A.cargar_resultados()
    h = crudo[crudo["fixture_id"].isin(validas["fixture_id"]) & crudo["estado"].isin(A.TERMINADOS)]
    h = h[(h["corners_local"].fillna(0) + h["corners_visitante"].fillna(0)) > 0]
    h = h.assign(t=h["fecha"].dt.tz_convert("UTC"),
                 tj=h["tarjetas_local"].fillna(0) + h["tarjetas_visitante"].fillna(0))
    tasa = AT.TasaLiga(h)
    res = {}

    # Eleccion
    e, res["n_eleccion"] = preparar(a.eleccion, crudo, tasa)
    b = {s: round(float(brier(e, s, 4.5).mean()), 4) for s in CANDIDATOS}
    mejor = min(b.values())
    s_el = next(s for s in CANDIDATOS if b[s] == mejor)
    res["eleccion"] = {"brier_o4.5": b, "elegido": s_el}

    # Evaluacion
    d, res["n_evaluacion"] = preparar(a.evaluacion, crudo, tasa)
    sem = d["semana"].to_numpy()
    hr = {"elegido": s_el}
    if s_el == "base":
        hr["entra"] = False
        hr["nota"] = "la eleccion dejo el modelo sin arbitro"
    else:
        for ln in (4.5, 3.5, 5.5):
            hr[f"o{ln}"] = AT.mejora(brier(d, "base", ln), brier(d, s_el, ln), sem)
        hr["entra"] = bool(hr["o4.5"]["ic90"][0] > 0 and hr["o3.5"]["ic90"][1] >= 0
                           and hr["o5.5"]["ic90"][1] >= 0)
    res["H_R"] = hr

    if hr["entra"]:
        mostrar = d[d["n_hist_L"] >= 1].reset_index(drop=True)
        c5r, c4r = c5(mostrar, s_el), c4_s(mostrar, s_el)
        res["mercado_tarjetas"] = {
            "subconjunto": "arbitro con al menos 1 partido previo en la liga",
            "C5": c5r, "C4_tarjetas": c4r,
            "se_muestra_con_arbitro": bool(c5r["pasa"] and c4r["pasa"])}
    else:
        res["mercado_tarjetas"] = {"nota": "H-R no entra: tarjetas sigue oculto", "se_muestra_con_arbitro": False}

    # Informativo
    s_inf = s_el if s_el != "base" else "L25"
    k_inf = s_inf[1:]
    suf = ["base", "L10", "L25", "L50", "T10", "T25", "T50"]
    inf = {
        "evaluacion": AT.informativo(d, suf),
        "eleccion": AT.informativo(e, suf),
        "marb_evaluacion": {s: dist_marb(d, f"marb_{s}") for s in suf[1:]},
        "historial_liga_evaluacion": {
            "sin_arbitro": A.r4(d["clave_arbitro"].isna().mean()),
            "cero_previos": A.r4((d["n_hist_L"] == 0).mean()),
            "mediana_previos": float(d["n_hist_L"].median())},
        "mejora_o4.5_por_tramo_de_historial": {},
        "C5_todos_los_partidos": {s: c5(d, s) for s in ("base", s_inf)},
        "C4_todos_los_partidos": {s: c4_s(d, s) for s in ("base", s_inf)},
        "todas_las_competiciones": {
            f"T{k_inf}_vs_base_o4.5": AT.mejora(brier(d, "base", 4.5), brier(d, f"T{k_inf}", 4.5), sem),
            f"T{k_inf}_vs_{s_inf}_o4.5": AT.mejora(brier(d, s_inf, 4.5), brier(d, f"T{k_inf}", 4.5), sem)},
        "correlacion_marb_vs_proyeccion_base": A.r4(np.corrcoef(d[f"marb_{s_inf}"], d["proj_base"])[0, 1]),
        "nota": f"tramos, C5/C4 de todos y comparaciones con {s_inf}"
                + (" (k elegido)" if s_inf == s_el else " (la eleccion dejo la base; L25 solo como referencia)"),
    }
    for lo, hi in TRAMOS:
        m = ((d["n_hist_L"] >= lo) & (d["n_hist_L"] <= hi)).to_numpy()
        clave = f"{lo}" if lo == hi else (f"{lo}+" if hi > 10 ** 6 else f"{lo}-{hi}")
        if m.sum() == 0:
            inf["mejora_o4.5_por_tramo_de_historial"][clave] = {"n": 0}
            continue
        r = AT.mejora(brier(d, "base", 4.5)[m], brier(d, s_inf, 4.5)[m], sem[m])
        r["n"] = int(m.sum())
        inf["mejora_o4.5_por_tramo_de_historial"][clave] = r
    res["informativo"] = inf

    with open(a.salida, "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1)
    print(json.dumps({k: res[k] for k in ("n_eleccion", "eleccion", "n_evaluacion", "H_R", "mercado_tarjetas")},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
