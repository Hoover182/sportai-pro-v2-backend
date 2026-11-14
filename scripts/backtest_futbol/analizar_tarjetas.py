"""Analisis de PREREGISTRO_multiplicador_tarjetas.md (escrito antes de ver resultados).

Uso desde backend/:
  python scripts/backtest_futbol/analizar_tarjetas.py --eleccion pred_tj_2025h2.csv \
      --evaluacion pred_tj_2026_ene_feb.csv pred_tj_2026_jun_ago.csv pred_tj_2026_oct.csv \
      --salida scripts/backtest_futbol/resultados_tarjetas.json
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
COMPONENTES = ("p0.0", "p0.5", "a0.0", "a0.5", "c0.0", "c0.5")
LINEAS_TOTAL = (2.5, 3.5, 4.5, 5.5, 6.5, 7.5)
LINEAS_EQUIPO = (0.5, 1.5, 2.5, 3.5)
UMBRAL, TOL_C4 = 0.70, -0.03
MESES_EXCLUIDOS = {"2026-03", "2026-04", "2026-05", "2026-09"}


def suf(f):
    return "f1" if f == 1.0 else f"f{f}"


class TasaLiga:
    """R1 de tarjetas: tasa de Over 4.5 de la liga en [t-365d, t), partidos
    con stats verificadas; con menos de 50, el global de las ligas validas."""

    def __init__(self, hist):
        h = hist.sort_values("t")
        self.glob = self._armar(h)
        self.liga = {lg: self._armar(g) for lg, g in h.groupby("liga")}

    @staticmethod
    def _armar(g):
        y = (g["tj"] > 4.5).astype(float).to_numpy()
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


def preparar(rutas, crudo, tasa):
    d = pd.concat([pd.read_csv(r) for r in rutas], ignore_index=True).merge(crudo, on="fixture_id", how="left")
    n = len(d)
    cor = d["corners_local"].fillna(0) + d["corners_visitante"].fillna(0)
    ok = ((d["error"].fillna("") == "") & d["o4.5_f1"].notna()
          & (d["n_prev_local"] >= A.MIN_PREVIOS) & (d["n_prev_visitante"] >= A.MIN_PREVIOS)
          & d["estado"].isin(A.TERMINADOS) & (cor > 0))
    d = d[ok].copy().reset_index(drop=True)
    d["t"] = d["fecha"].dt.tz_convert("UTC")
    d = d[~d["t"].dt.strftime("%Y-%m").isin(MESES_EXCLUIDOS)].reset_index(drop=True)
    d["tl"], d["tv"] = d["tarjetas_local"].fillna(0), d["tarjetas_visitante"].fillna(0)
    d["tj"] = d["tl"] + d["tv"]
    iso = d["t"].dt.isocalendar()
    d["semana"] = iso["year"].astype(str) + "-" + iso["week"].astype(str).str.zfill(2)
    corte = d["t"] - pd.Timedelta(hours=1)
    d["r1"] = [tasa.tasa(lg, c) for lg, c in zip(d["liga"], corte)]
    return d, {"filas": n, "evaluados": len(d)}


def brier(d, col, y):
    return A.brier_bin(d[col].to_numpy(float), y)


def mejora(m_ref, m_var, sem):
    media, lo, hi = A.ic_bloques(m_ref - m_var, sem)
    return {"ref": A.r4(m_ref.mean()), "variante": A.r4(m_var.mean()), "mejora": A.r4(media),
            "ic90": [round(lo, 5), round(hi, 5)]}


def c4(d, s):
    p = d[f"o4.5_{s}"].to_numpy(float)
    y = (d["tj"] > 4.5).astype(float).to_numpy()
    ps = np.concatenate([p, 1 - p]); ys = np.concatenate([y, 1 - y])
    bs = np.concatenate([d["semana"].to_numpy()] * 2)
    m = ps >= UMBRAL
    if not m.any():
        return {"n": 0, "pasa": True}
    media, lo, hi = A.ic_bloques(ys[m] - ps[m], bs[m])
    return {"n": int(m.sum()), "prob_media": A.r4(ps[m].mean()), "tasa_real": A.r4(ys[m].mean()),
            "diferencia": A.r4(media), "ic90": [round(lo, 5), round(hi, 5)], "pasa": bool(hi >= TOL_C4)}


def informativo(d, sufijos):
    out = {}
    for s in sufijos:
        r = {"proyeccion_media": A.r4(d[f"proj_{s}"].mean()), "sesgo_medio": A.r4((d[f"proj_{s}"] - d["tj"]).mean())}
        for ln in LINEAS_TOTAL:
            y = (d["tj"] > ln).astype(float).to_numpy()
            r[f"brier_o{ln}"] = A.r4(brier(d, f"o{ln}_{s}", y).mean())
        for lado, col in (("l", "tl"), ("v", "tv")):
            for ln in LINEAS_EQUIPO:
                c = f"{lado}{ln}_{s}"
                mm = d[c].notna().to_numpy()
                y = (d[col] > ln).astype(float).to_numpy()
                r[f"brier_{lado}{ln}"] = A.r4(A.brier_bin(d[c].to_numpy(float)[mm], y[mm]).mean())
        p = d[f"o4.5_{s}"].to_numpy(float)
        r["calibracion_o4.5"] = A.calibracion_bandas(p, (d["tj"] > 4.5).astype(float).to_numpy())
        out[s] = r
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--eleccion", required=True)
    ap.add_argument("--evaluacion", required=True, nargs="+")
    ap.add_argument("--salida", required=True)
    a = ap.parse_args()

    crudo, validas, _ = A.cargar_resultados()
    h = crudo[crudo["fixture_id"].isin(validas["fixture_id"]) & crudo["estado"].isin(A.TERMINADOS)]
    h = h[(h["corners_local"].fillna(0) + h["corners_visitante"].fillna(0)) > 0]
    h = h.assign(t=h["fecha"].dt.tz_convert("UTC"),
                 tj=h["tarjetas_local"].fillna(0) + h["tarjetas_visitante"].fillna(0))
    tasa = TasaLiga(h)
    res = {}

    # Eleccion
    e, res["n_eleccion"] = preparar([a.eleccion], crudo, tasa)
    y = (e["tj"] > 4.5).astype(float).to_numpy()
    b = {f: round(float(brier(e, f"o4.5_{suf(f)}", y).mean()), 4) for f in F_CANDIDATOS}
    mejor = min(b.values())
    f_el = next(f for f in F_CANDIDATOS if b[f] == mejor)
    res["eleccion"] = {"brier_o4.5_por_f": {str(k): v for k, v in b.items()}, "f_elegido": f_el}

    # Evaluacion
    d, res["n_evaluacion"] = preparar(a.evaluacion, crudo, tasa)
    sem = d["semana"].to_numpy()
    s_el = suf(f_el)
    ht = {"f": f_el}
    if f_el == 1.0:
        ht["entra"] = False
        ht["nota"] = "la eleccion dejo el multiplicador actual"
    else:
        for ln in (4.5, 3.5, 5.5):
            yy = (d["tj"] > ln).astype(float).to_numpy()
            ht[f"o{ln}"] = mejora(brier(d, f"o{ln}_f1", yy), brier(d, f"o{ln}_{s_el}", yy), sem)
        ht["entra"] = bool(ht["o4.5"]["ic90"][0] > 0 and ht["o3.5"]["ic90"][1] >= 0 and ht["o5.5"]["ic90"][1] >= 0)
    res["H_T"] = ht
    s_fin = s_el if ht["entra"] else "f1"
    res["modelo_final"] = {"f": f_el if ht["entra"] else 1.0}

    y45 = (d["tj"] > 4.5).astype(float).to_numpy()
    c5 = mejora(A.brier_bin(d["r1"].to_numpy(float), y45), brier(d, f"o4.5_{s_fin}", y45), sem)
    c5["pasa"] = bool(c5["ic90"][0] > 0)
    c4r = c4(d, s_fin)
    res["mercado_tarjetas"] = {"C5": c5, "C4_tarjetas": c4r, "sigue_visible": bool(c5["pasa"] and c4r["pasa"])}

    # Informativo
    sufijos = ["f1", "f0.5", "f0.0"] + [c for c in COMPONENTES if f"proj_{c}" in d]
    res["informativo"] = {
        "evaluacion": informativo(d, sufijos),
        "eleccion": informativo(e, ["f1", "f0.5", "f0.0"]),
        "multiplicador_medio_evaluacion": A.r4(d["m"].clip(upper=1.5).mean()),
        "tarjetas_reales_medias_evaluacion": A.r4(d["tj"].mean()),
        "dispersion_real_var_sobre_media": A.r4(d["tj"].var() / d["tj"].mean()),
        "c4_con_f0.0": c4(d, "f0.0"),
    }
    with open(a.salida, "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1)
    print(json.dumps({k: res[k] for k in ("eleccion", "H_T", "modelo_final", "mercado_tarjetas")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
