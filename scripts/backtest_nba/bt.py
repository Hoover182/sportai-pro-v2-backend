"""Backtest del modelo de partido NBA. Criterios en PREREGISTRO.md (congelados
antes de correrlo).

Uso desde backend/: python scripts/backtest_nba/bt.py
Escribe scripts/backtest_nba/resultados.json y muestra el resumen.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

AQUI = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(AQUI, "..", ".."))
from app.services import nba_model as M

CSV = os.path.join(AQUI, "..", "..", "app", "services", "nba_partidos.csv")
AJUSTE, EVALUACION = "2024-25", "2025-26"
GRILLA_H = [i / 2 for i in range(11)]                   # 0 .. 5
GRILLA_F = [round(0.85 + i / 100, 2) for i in range(16)]  # 0.85 .. 1.00
N_BOOT, SEMILLA_BOOT = 2000, 2026


def correr(partidos, largo, temporada, params):
    """Una fila por partido evaluado: prob_local, total, margen, y lo real."""
    filas = []
    for p in partidos[partidos["temporada"] == temporada].itertuples():
        r = M.analizar_partido(largo, int(p.id_local), int(p.id_visitante), p.fecha,
                               p.temporada, params)
        if r is None:
            continue
        filas.append({
            "game_id": p.game_id, "prob_local": r["prob_local"],
            "total": r["total"], "margen": r["margen_local"],
            "gana_local": int(p.puntos_local > p.puntos_visitante),
            "total_real": p.puntos_local + p.puntos_visitante,
            "margen_real": p.puntos_local - p.puntos_visitante,
        })
    return pd.DataFrame(filas)


def errores(df):
    """Error por partido de cada metrica."""
    return {
        "brier": (df["prob_local"] - df["gana_local"]) ** 2,
        "acierto": ((df["prob_local"] >= 0.5).astype(int) == df["gana_local"]).astype(float),
        "err_total": (df["total"] - df["total_real"]).abs(),
        "err_margen": (df["margen"] - df["margen_real"]).abs(),
    }


def metricas(df):
    return {k: round(float(v.mean()), 4) for k, v in errores(df).items()} | {"n": len(df)}


def ic_mejora(err_ref, err_var):
    """IC 90% bootstrap pareado de la mejora media (ref - var); > 0 = la variante mejora."""
    d = (err_ref.to_numpy() - err_var.to_numpy())
    rng = np.random.default_rng(SEMILLA_BOOT)
    idx = rng.integers(0, len(d), size=(N_BOOT, len(d)))
    medias = d[idx].mean(axis=1)
    return round(float(d.mean()), 5), round(float(np.percentile(medias, 5)), 5), round(float(np.percentile(medias, 95)), 5)


def bases(partidos, temporada):
    previas = partidos[partidos["temporada"] < temporada]
    tasa_local = float((previas["puntos_local"] > previas["puntos_visitante"]).mean())
    ev = partidos[partidos["temporada"] == temporada].sort_values(["fecha", "game_id"])
    y = (ev["puntos_local"] > ev["puntos_visitante"]).astype(int)
    brier_fijo = float(((tasa_local - y) ** 2).mean())

    # Mejor record hasta el dia anterior: los partidos del mismo dia no se ven entre si.
    record, aciertos = {}, []
    for fecha, dia in ev.groupby("fecha", sort=True):
        for p in dia.itertuples():
            gl, pl = record.get(p.id_local, (0, 0))
            gv, pv = record.get(p.id_visitante, (0, 0))
            pct_l = gl / (gl + pl) if gl + pl else 0.0
            pct_v = gv / (gv + pv) if gv + pv else 0.0
            elige_local = pct_l >= pct_v
            aciertos.append(elige_local == (p.puntos_local > p.puntos_visitante))
        for p in dia.itertuples():
            gana = p.puntos_local > p.puntos_visitante
            gl, pl = record.get(p.id_local, (0, 0))
            gv, pv = record.get(p.id_visitante, (0, 0))
            record[p.id_local] = (gl + gana, pl + (not gana))
            record[p.id_visitante] = (gv + (not gana), pv + gana)
    return {"tasa_local_previa": round(tasa_local, 4), "brier_prob_fija": round(brier_fijo, 4),
            "acierto_mejor_record": round(float(np.mean(aciertos)), 4)}


def main():
    partidos = pd.read_csv(CSV, dtype={"game_id": str})
    temporadas = sorted(partidos["temporada"].unique())
    print("Temporadas en el CSV:", temporadas,
          partidos.groupby("temporada").size().to_dict())
    for t in ("2023-24", AJUSTE, EVALUACION):
        assert t in temporadas, f"falta {t} en el CSV"
    largo = M.partidos_por_equipo(partidos)
    total_ev = int((partidos["temporada"] == EVALUACION).sum())
    res = {}

    # ---- Criterio 1: base
    base_ev = correr(partidos, largo, EVALUACION, M.Params())
    res["base_2025_26"] = metricas(base_ev)
    res["salteados_2025_26"] = total_ev - len(base_ev)
    res["bases_2025_26"] = bases(partidos, EVALUACION)
    b = res["bases_2025_26"]
    c1 = (res["base_2025_26"]["brier"] < b["brier_prob_fija"]
          and res["base_2025_26"]["acierto"] >= b["acierto_mejor_record"])
    res["criterio_1"] = c1
    print("\n[1] Base 2025-26:", res["base_2025_26"], "| salteados:", res["salteados_2025_26"])
    print("    Bases:", b, "->", "PASA" if c1 else "NO PASA")

    # ---- Criterio 2: localia
    ajuste_h = {}
    for h in GRILLA_H:
        ajuste_h[h] = metricas(correr(partidos, largo, AJUSTE, M.Params(ventaja_local=h)))["brier"]
    h_elegido = min(GRILLA_H, key=lambda h: (ajuste_h[h], h))
    res["localia_brier_2024_25"] = ajuste_h
    res["localia_h_elegido"] = h_elegido
    var_h = correr(partidos, largo, EVALUACION, M.Params(ventaja_local=h_elegido))
    eb, ev_ = errores(base_ev), errores(var_h)
    ic = ic_mejora(eb["brier"], ev_["brier"])
    c2 = ic[1] > 0 and ev_["err_margen"].mean() <= eb["err_margen"].mean()
    res["localia_2025_26"] = metricas(var_h) | {"mejora_brier_ic90": ic}
    res["criterio_2"] = c2
    print(f"\n[2] Localia: h elegido en 2024-25 = {h_elegido}  (Brier por h: {ajuste_h})")
    print("    2025-26:", res["localia_2025_26"], "->", "ENTRA" if c2 else "NO ENTRA")

    # ---- Criterio 3: fatiga, encima de lo que quedo del 2
    h_ref = h_elegido if c2 else 0.0
    ref_ev = var_h if c2 else base_ev
    ajuste_f = {}
    for f in GRILLA_F:
        ajuste_f[f] = metricas(correr(partidos, largo, AJUSTE,
                                      M.Params(ventaja_local=h_ref, factor_fatiga=f)))["err_total"]
    f_elegido = min(GRILLA_F, key=lambda f: (ajuste_f[f], abs(1 - f)))
    res["fatiga_err_total_2024_25"] = ajuste_f
    res["fatiga_f_elegido"] = f_elegido
    var_f = correr(partidos, largo, EVALUACION, M.Params(ventaja_local=h_ref, factor_fatiga=f_elegido))
    er, evf = errores(ref_ev), errores(var_f)
    ic_f = ic_mejora(er["err_total"], evf["err_total"])
    c3 = ic_f[1] > 0 and evf["brier"].mean() <= er["brier"].mean()
    res["fatiga_2025_26"] = metricas(var_f) | {"mejora_err_total_ic90": ic_f}
    res["criterio_3"] = c3
    f085 = correr(partidos, largo, EVALUACION, M.Params(ventaja_local=h_ref, factor_fatiga=0.85))
    res["fatiga_085_2025_26"] = metricas(f085) | {
        "mejora_err_total_ic90": ic_mejora(er["err_total"], errores(f085)["err_total"])}
    print(f"\n[3] Fatiga (sobre h={h_ref}): f elegido en 2024-25 = {f_elegido}")
    print("    err_total por f:", ajuste_f)
    print("    2025-26:", res["fatiga_2025_26"], "->", "ENTRA" if c3 else "NO ENTRA")
    print("    con f=0.85 (original):", res["fatiga_085_2025_26"])
    print("    referencia (sin fatiga):", metricas(ref_ev))

    with open(os.path.join(AQUI, "resultados.json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2, ensure_ascii=False, default=str)


if __name__ == "__main__":
    main()
