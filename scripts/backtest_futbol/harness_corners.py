"""Variantes de PREREGISTRO_multiplicador_corners.md sobre el harness point-in-time.

Uso desde backend/:
  python scripts/backtest_futbol/harness_corners.py --desde 2025-07-01 --hasta 2025-12-31 \
      --salida pred_co_2025h2.csv [--procesos 4] [--limite N]

Por partido corre simular() igual que harness.py (f = 1, produccion) y lo
repite con el multiplicador de corners cambiado:  m' = 1 + f*(m - 1),
f en {0,5; 0}.
No toca el codigo del modelo: futbol_service calcula
  multiplicador_corners = max(0.8, min(multiplicador_corners, 1.3))
(el unico min(..., 1.3) del modulo); el harness pone un min propio en el
modulo que devuelve m' en esa llamada y pasa todo lo demas tal cual. Con
f = 0 el multiplicador queda en 1,0 exacto y simular() no re-muestrea los
corners, igual que pasaria sin el multiplicador en el codigo. La semilla de
simular() sale de equipos + fecha, asi que todas las variantes de un partido
usan el mismo azar.
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
LINEAS_TOTAL = (7.5, 8.5, 9.5, 10.5, 11.5)
LINEAS_EQUIPO = (2.5, 3.5, 4.5, 5.5, 6.5)
_CAP = {}
_CTX = {"f": None}   # None = produccion
_REG = {}


def _min_harness(*a, **k):
    r = builtins.min(*a, **k)
    if len(a) == 2 and not k and a[1] == 1.3:
        _REG["m"] = a[0]
        if _CTX["f"] is not None:
            return 1 + _CTX["f"] * (r - 1)
    return r


def _resumen(sim, suf):
    out = {f"proj_{suf}": sim.get("corners_totales_proj"),
           f"projl_{suf}": sim.get("corners_local_proj"),
           f"projv_{suf}": sim.get("corners_visitante_proj")}
    cou = sim.get("corners_ou") or {}
    for ln in LINEAS_TOTAL:
        out[f"o{ln}_{suf}"] = cou.get(ln, {}).get("over")
    for lado, clave in (("l", "corners_ou_local"), ("v", "corners_ou_visitante")):
        t = sim.get(clave) or {}
        for ln in LINEAS_EQUIPO:
            out[f"{lado}{ln}_{suf}"] = t.get(ln, {}).get("over")
    return out


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
        _CAP["m"] = _REG.get("m")
        ii = _REG.get("i", [])
        if len(ii) >= 2:
            _CAP.update(int_local=ii[0][0], int_visitante=ii[1][0],
                        con_tiros_local=ii[0][1], con_tiros_visitante=ii[1][1])
        if "m" in _REG:   # sin la llamada (excepcion en modelo_presion) el multiplicador ya es 1
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
    ap.add_argument("--procesos", type=int, default=4)
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
