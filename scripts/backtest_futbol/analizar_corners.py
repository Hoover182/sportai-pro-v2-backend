"""Analisis de PREREGISTRO_multiplicador_corners.md (escrito antes de ver resultados).

Uso desde backend/:
  python scripts/backtest_futbol/analizar_corners.py --eleccion pred_co_2025h2.csv \
      --evaluacion pred_co_2026.csv --salida scripts/backtest_futbol/resultados_corners.json
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
LINEAS_TOTAL = (7.5, 8.5, 9.5, 10.5, 11.5)
LINEAS_EQUIPO = (2.5, 3.5, 4.5, 5.5, 6.5)
LINEA = 9.5
UMBRAL, TOL_C4, BANDA_SACAR = 0.70, -0.03, 0.0010


def suf(f):
    return "f1" if f == 1.0 else f"f{f}"


class TasaLiga:
    """R1 de corners: tasa de Over 9.5 de la liga en [t-365d, t), partidos con
    stats verificadas; con menos de 50, el global de las ligas validas."""

    def __init__(self, hist):
        h = hist.sort_values("t")
        self.glob = self._armar(h)
        self.liga = {lg: self._armar(g) for lg, g in h.groupby("liga")}

    @staticmethod
    def _armar(g):
        y = (g["co"] > LINEA).astype(float).to_numpy()
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


def preparar(ruta, crudo, tasa):
    d = pd.read_csv(ruta).merge(crudo, on="fixture_id", how="left")
    n = len(d)
    d["cl"], d["cv"] = d["corners_local"].fillna(0), d["corners_visitante"].fillna(0)
    d["co"] = d["cl"] + d["cv"]
    ok = ((d["error"].fillna("") == "") & d[f"o{LINEA}_f1"].notna()
          & (d["n_prev_local"] >= A.MIN_PREVIOS) & (d["n_prev_visitante"] >= A.MIN_PREVIOS)
          & d["estado"].isin(A.TERMINADOS) & (d["co"] > 0))
    d = d[ok].copy().reset_index(drop=True)
    # Sin la llamada al multiplicador (excepcion en modelo_presion) el
    # multiplicador ya es 1: las variantes son iguales al actual.
    sin_var = d["o9.5_f0.0"].isna() if "o9.5_f0.0" in d else pd.Series(True, index=d.index)
    for f in F_CANDIDATOS[1:]:
        for c in [c for c in d.columns if c.endswith("_f1")]:
            v = c[:-3] + "_" + suf(f)
            if v not in d:
                d[v] = np.nan
            d.loc[sin_var, v] = d.loc[sin_var, c]
    d["t"] = d["fecha"].dt.tz_convert("UTC")
    iso = d["t"].dt.isocalendar()
    d["semana"] = iso["year"].astype(str) + "-" + iso["week"].astype(str).str.zfill(2)
    corte = d["t"] - pd.Timedelta(hours=1)
    d["r1"] = [tasa.tasa(lg, c) for lg, c in zip(d["liga"], corte)]
    return d, {"filas": n, "evaluados": len(d), "sin_variantes_(multiplicador_1)": int(sin_var.sum())}


def brier(d, col, y):
    return A.brier_bin(d[col].to_numpy(float), y)


def y_over(d, ln, col="co"):
    return (d[col] > ln).astype(float).to_numpy()


def mejora(m_ref, m_var, sem):
    media, lo, hi = A.ic_bloques(m_ref - m_var, sem)
    return {"ref": A.r4(m_ref.mean()), "variante": A.r4(m_var.mean()), "mejora": A.r4(media),
            "ic90": [round(lo, 5), round(hi, 5)]}


def c4(d, s):
    p = d[f"o{LINEA}_{s}"].to_numpy(float)
    y = y_over(d, LINEA)
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
    neutros = (~d["con_tiros_local"].fillna(False).astype(bool)) & (~d["con_tiros_visitante"].fillna(False).astype(bool)) \
        if "con_tiros_local" in d else pd.Series(False, index=d.index)
    for s in sufijos:
        r = {"proyeccion_media": A.r4(d[f"proj_{s}"].mean()), "sesgo_medio": A.r4((d[f"proj_{s}"] - d["co"]).mean())}
        for ln in LINEAS_TOTAL:
            r[f"brier_o{ln}"] = A.r4(brier(d, f"o{ln}_{s}", y_over(d, ln)).mean())
        for lado, col in (("l", "cl"), ("v", "cv")):
            for ln in LINEAS_EQUIPO:
                c = f"{lado}{ln}_{s}"
                mm = d[c].notna().to_numpy()
                r[f"brier_{lado}{ln}"] = A.r4(A.brier_bin(d[c].to_numpy(float)[mm], y_over(d, ln, col)[mm]).mean())
        r["calibracion_o9.5"] = A.calibracion_bandas(d[f"o{LINEA}_{s}"].to_numpy(float), y_over(d, LINEA))
        if neutros.any():
            dn = d[neutros]
            r["neutros_n"] = int(neutros.sum())
            r["neutros_brier_o9.5"] = A.r4(brier(dn, f"o{LINEA}_{s}", y_over(dn, LINEA)).mean())
            r["neutros_sesgo_medio"] = A.r4((dn[f"proj_{s}"] - dn["co"]).mean())
        out[s] = r
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--eleccion", required=True)
    ap.add_argument("--evaluacion", required=True)
    ap.add_argument("--salida", required=True)
    a = ap.parse_args()

    crudo, validas, _ = A.cargar_resultados()
    h = crudo[crudo["fixture_id"].isin(validas["fixture_id"]) & crudo["estado"].isin(A.TERMINADOS)]
    h = h.assign(t=h["fecha"].dt.tz_convert("UTC"),
                 co=h["corners_local"].fillna(0) + h["corners_visitante"].fillna(0))
    h = h[h["co"] > 0]
    tasa = TasaLiga(h)
    res = {}

    # Eleccion
    e, res["n_eleccion"] = preparar(a.eleccion, crudo, tasa)
    ye = y_over(e, LINEA)
    b = {f: round(float(brier(e, f"o{LINEA}_{suf(f)}", ye).mean()), 4) for f in F_CANDIDATOS}
    mejor = min(b.values())
    f_el = next(f for f in F_CANDIDATOS if b[f] == mejor)
    res["eleccion"] = {"brier_o9.5_por_f": {str(k): v for k, v in b.items()}, "f_elegido": f_el}

    # Evaluacion
    d, res["n_evaluacion"] = preparar(a.evaluacion, crudo, tasa)
    sem = d["semana"].to_numpy()
    s_el = suf(f_el)
    hc = {"f": f_el}
    if f_el == 1.0:
        hc["entra"] = False
        hc["nota"] = "la eleccion dejo el multiplicador actual"
    else:
        for ln in (9.5, 8.5, 10.5):
            yy = y_over(d, ln)
            hc[f"o{ln}"] = mejora(brier(d, f"o{ln}_f1", yy), brier(d, f"o{ln}_{s_el}", yy), sem)
        hc["entra"] = bool(hc["o9.5"]["ic90"][0] > 0 and hc["o8.5"]["ic90"][1] >= 0 and hc["o10.5"]["ic90"][1] >= 0)
    res["H_C"] = hc

    # Si no entra: regla de sacarlo (f = 0 contra el actual dentro de +-0,0010)
    y95 = y_over(d, LINEA)
    if hc["entra"]:
        f_fin = f_el
        res["sacar_multiplicador"] = {"aplica": False}
    else:
        f0 = mejora(brier(d, f"o{LINEA}_f1", y95), brier(d, f"o{LINEA}_f0.0", y95), sem)
        dentro = bool(f0["ic90"][0] >= -BANDA_SACAR and f0["ic90"][1] <= BANDA_SACAR)
        res["sacar_multiplicador"] = {"aplica": True, "f0_contra_actual": f0, "dentro_de_banda": dentro, "se_saca": dentro}
        f_fin = 0.0 if dentro else 1.0
    s_fin = suf(f_fin)
    res["modelo_final"] = {"f": f_fin}

    # Mercado de corners contra la tasa de la liga
    c5 = mejora(A.brier_bin(d["r1"].to_numpy(float), y95), brier(d, f"o{LINEA}_{s_fin}", y95), sem)
    c5["pasa"] = bool(c5["ic90"][0] > 0)
    c4r = c4(d, s_fin)
    visible = bool(c5["pasa"] and c4r["pasa"])
    res["mercado_corners"] = {"C5": c5, "C4_corners": c4r, "sigue_visible": visible,
                              "si_no": "se oculta el pronostico de corners y se muestra el promedio de la liga (O/U 9.5)"}

    # Informativo
    res["informativo"] = {
        "evaluacion": informativo(d, ["f1", "f0.5", "f0.0"]),
        "eleccion": informativo(e, ["f1", "f0.5", "f0.0"]),
        "multiplicador_medio_evaluacion": A.r4(d["m"].clip(0.8, 1.3).mean()),
        "corners_reales_medios_evaluacion": A.r4(d["co"].mean()),
        "dispersion_real_var_sobre_media": A.r4(d["co"].var() / d["co"].mean()),
        "brier_r1_o9.5": A.r4(A.brier_bin(d["r1"].to_numpy(float), y95).mean()),
        "c4_con_cada_f": {s: c4(d, s) for s in ("f1", "f0.5", "f0.0")},
    }
    with open(a.salida, "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1)
    print(json.dumps({k: res[k] for k in ("eleccion", "H_C", "sacar_multiplicador", "modelo_final", "mercado_corners")},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
