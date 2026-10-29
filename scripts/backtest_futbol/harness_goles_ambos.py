"""Variantes H-A / H-B de PREREGISTRO_goles_ambos.md sobre el harness point-in-time.

Uso desde backend/:
  python scripts/backtest_futbol/harness_goles_ambos.py --desde 2025-07-01 --hasta 2025-12-31 \
      --salida pred_ga_2025h2.csv [--procesos 6] [--limite N]

Por partido corre simular() igual que harness.py (el resultado de produccion
no cambia) y ademas, dentro de la misma llamada, repite simular_partido_futbol()
con los goles esperados acercados al promedio de la liga (H-B, s en S_VALORES).
Para H-A guarda la probabilidad de ambos marcan sin mezcla (c) y con mezcla (f):
con un factor a, la probabilidad es c + a*(f - c), y con H-B es
c_s + a*w*(tasa_h2h - c_s), con w = (f - c)/(tasa_h2h - c).
"""
import argparse
import os
import sys
import time
from multiprocessing import Pool

import numpy as np
import pandas as pd

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import harness as H  # noqa: E402

S_VALORES = (0.9, 0.8, 0.7, 0.6)
DIAS_MU, MIN_LIGA = 365, 50
_CAP = {}
_CTX = {}


class MediasLiga:
    """Promedio de goles a 90' del local y del visitante en [t-365d, t), por
    liga; con menos de 50 partidos, el global de las ligas validas."""

    def __init__(self, validas):
        tiene90 = validas["goles_90_local"].notna() & validas["goles_90_visitante"].notna()
        ft = (validas["estado"] == "FT") & validas["goles_local"].notna() & validas["goles_visitante"].notna()
        gl = np.where(tiene90, validas["goles_90_local"], np.where(ft, validas["goles_local"], np.nan))
        gv = np.where(tiene90, validas["goles_90_visitante"], np.where(ft, validas["goles_visitante"], np.nan))
        h = validas.assign(gl=gl, gv=gv, t=validas["fecha"].dt.tz_convert("UTC"))
        h = h[h["estado"].isin(H.TERMINADOS) & h["gl"].notna()].sort_values("t")
        self.glob = self._armar(h)
        self.liga = {lg: self._armar(g) for lg, g in h.groupby("liga")}

    @staticmethod
    def _armar(g):
        y = np.column_stack([g["gl"], g["gv"]]).astype(float)
        return g["t"].astype("int64").to_numpy(), np.vstack([np.zeros(2), np.cumsum(y, axis=0)])

    @staticmethod
    def _ventana(serie, t0, t1):
        ts, acum = serie
        i, j = np.searchsorted(ts, t0, "left"), np.searchsorted(ts, t1, "left")
        return j - i, acum[j] - acum[i]

    def medias(self, liga, corte):
        t1, t0 = corte.value, (corte - pd.Timedelta(days=DIAS_MU)).value
        if liga in self.liga:
            n, s = self._ventana(self.liga[liga], t0, t1)
            if n >= MIN_LIGA:
                return s / n, "liga"
        n, s = self._ventana(self.glob, t0, t1)
        return (s / n if n else np.array([np.nan, np.nan])), "global"


def _resumen(r):
    return {"pl": r["prob_local"], "pe": r["prob_empate"], "pv": r["prob_visitante"],
            "o15": r["goles_ou"][1.5]["over"], "o25": r["goles_ou"][2.5]["over"],
            "o35": r["goles_ou"][3.5]["over"], "ambos": r["prob_ambos_marcan"]}


def _iniciar():
    H._iniciar()
    FS = H._G["FS"]
    _CTX["medias"] = MediasLiga(H._G["validas"])
    orig_sim, orig_h2h = FS.simular_partido_futbol, FS._h2h

    def sim_variantes(*a, **k):
        base = orig_sim(*a, **k)
        lam_a, lam_b = a[0], a[1]
        _CAP.update(lam_a=lam_a, lam_b=lam_b)
        for clave, v in _resumen(base).items():
            _CAP[f"{clave}_s1"] = v
        mu, fuente = _CTX["medias"].medias(_CTX["liga"], H._AHORA)
        _CAP.update(mu_local=mu[0], mu_visitante=mu[1], mu_fuente=fuente)
        if not np.isnan(mu[0]):
            for s in S_VALORES:
                a2 = (mu[0] + s * (lam_a - mu[0]), mu[1] + s * (lam_b - mu[1])) + tuple(a[2:])
                r = orig_sim(*a2, **k)
                for clave, v in _resumen(r).items():
                    _CAP[f"{clave}_s{s}"] = v
        return base

    def h2h_cap(*a, **k):
        r = orig_h2h(*a, **k)
        g = r[r["goles_local"].notna() & r["goles_visitante"].notna()] if len(r) else r
        _CAP["n_h2h"] = len(r)
        _CAP["tasa_h2h"] = float(((g["goles_local"] > 0) & (g["goles_visitante"] > 0)).mean()) if len(g) else np.nan
        return r

    FS.simular_partido_futbol, FS._h2h = sim_variantes, h2h_cap


def correr(fid):
    _CAP.clear()
    v = H._G["validas"]
    _CTX["liga"] = v.loc[v["fixture_id"] == fid, "liga"].iloc[0]
    out = H.correr_partido(fid)   # fija H._AHORA antes de simular
    out.update(_CAP)
    # f = ambos marcan final (con mezcla) de produccion
    out["ambos_final"] = out.get("p_ambos")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--desde", required=True)
    ap.add_argument("--hasta", required=True)
    ap.add_argument("--salida", required=True)
    ap.add_argument("--procesos", type=int, default=max(os.cpu_count() - 2, 1))
    ap.add_argument("--limite", type=int, default=0)
    a = ap.parse_args()
    _iniciar()
    v = H._G["validas"]
    t = v["fecha"].dt.tz_convert("UTC")
    sel = v[v["estado"].isin(H.TERMINADOS) & (t >= pd.Timestamp(a.desde, tz="UTC"))
            & (t < pd.Timestamp(a.hasta, tz="UTC") + pd.Timedelta(days=1))].sort_values("fecha")
    ids = sel["fixture_id"].tolist()[: a.limite or None]
    print(f"{len(ids)} partidos entre {a.desde} y {a.hasta}; {a.procesos} procesos", flush=True)
    t0, filas = time.time(), []
    with Pool(a.procesos, initializer=_iniciar) as pool:
        for i, r in enumerate(pool.imap_unordered(correr, ids, chunksize=8), 1):
            filas.append(r)
            if i % 500 == 0 or i == len(ids):
                print(f"  {i}/{len(ids)}  {time.time() - t0:.0f}s", flush=True)
    pd.DataFrame(filas).to_csv(a.salida, index=False)
    print("listo:", a.salida)


if __name__ == "__main__":
    main()
