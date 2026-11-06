"""Variantes de PREREGISTRO_multiplicador_goles.md sobre el harness point-in-time.

Uso desde backend/:
  python scripts/backtest_futbol/harness_goles_mult.py --desde 2025-07-01 --hasta 2025-12-31 \
      --salida pred_gm_2025h2.csv [--procesos 5] [--limite N]

Por partido corre simular() igual que harness.py (f = 1, produccion) y lo
repite con m' = 1 + f*(m - 1) en el multiplicador de goles de cada equipo,
f en {0,5; 0}. No toca el codigo del modelo: futbol_service calcula
  multiplicador_goles_X = max(0.9, min(multiplicador_goles_X, 1.15))
(los unicos min(..., 1.15) del modulo, uno por equipo); el harness pone un min
propio en el modulo que devuelve m' en esas llamadas y pasa todo lo demas tal
cual. La intensidad de cada equipo se lee envolviendo
calcular_indice_intensidad_ofensiva (solo la registra). La semilla de
simular() sale de equipos + fecha: todas las variantes usan el mismo azar.
"""
import argparse
import builtins
import os
import sys
import time
from multiprocessing import Pool

import pandas as pd

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import harness as H  # noqa: E402

F_VALORES = (0.5, 0.0)
_CAP = {}
_CTX = {"f": None}   # None = produccion
_REG = {}


def _min_harness(*a, **k):
    r = builtins.min(*a, **k)
    if len(a) == 2 and not k and a[1] == 1.15:
        _REG.setdefault("m", []).append(a[0])
        if _CTX["f"] is not None:
            return 1 + _CTX["f"] * (r - 1)
    return r


def _resumen(s, suf):
    return {f"pl_{suf}": s["prob_local"], f"pe_{suf}": s["prob_empate"], f"pv_{suf}": s["prob_visitante"],
            f"hl1_{suf}": s.get("prob_hcp_local_m1"), f"he1_{suf}": s.get("prob_hcp_empate_m1"),
            f"hv1_{suf}": s.get("prob_hcp_visit_m1"),
            f"o25_{suf}": s["goles_ou"][2.5]["over"], f"ambos_{suf}": s["prob_ambos_marcan"]}


def _iniciar():
    H._iniciar()
    FS, MP = H._G["FS"], H._G["MP"]
    FS.min = _min_harness
    orig_int = MP.calcular_indice_intensidad_ofensiva

    def intensidad(*a, **k):
        v = orig_int(*a, **k)
        _REG.setdefault("i", []).append((v[0], bool(v[1])))
        return v

    MP.calcular_indice_intensidad_ofensiva = intensidad
    orig_sim = FS.simular

    def sim_variantes(*a, **k):
        _CTX["f"] = None
        _REG.clear()
        base = orig_sim(*a, **k)
        if base is None or base[0] is None:
            return base
        _CAP.update(_resumen(base[0], "f1"))
        ms, ii = _REG.get("m", []), _REG.get("i", [])
        if len(ms) == 2:
            _CAP.update(m_local=ms[0], m_visitante=ms[1])
        if len(ii) >= 2:
            # las dos primeras llamadas son local y visitante (corners y goles usan las mismas)
            _CAP.update(int_local=ii[0][0], int_visitante=ii[1][0],
                        con_tiros_local=ii[0][1], con_tiros_visitante=ii[1][1])
        if len(ms) == 2:   # sin las 2 llamadas (excepcion en modelo_presion) el multiplicador ya es 1
            for f in F_VALORES:
                _CTX["f"] = f
                _REG.clear()
                FS._cache_resultados.clear()
                r = orig_sim(*a, **k)
                _CAP.update(_resumen(r[0], f"f{f}"))
        _CTX["f"] = None
        return base

    FS.simular = sim_variantes


def correr(fid):
    _CAP.clear()
    out = H.correr_partido(fid)
    out.update(_CAP)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--desde", required=True)
    ap.add_argument("--hasta", required=True)
    ap.add_argument("--salida", required=True)
    ap.add_argument("--procesos", type=int, default=5)
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
    pd.DataFrame(filas).to_csv(a.salida, index=False)
    print("listo:", a.salida)


if __name__ == "__main__":
    main()
