"""Variantes de PREREGISTRO_arbitro_tarjetas.md sobre el harness point-in-time.

Uso desde backend/:
  python scripts/backtest_futbol/harness_arbitro.py --csv RUTA/futbol_partidos.csv \
      --desde 2025-07-01 --hasta 2025-12-31 --salida pred_ar_2025h2.csv \
      [--procesos 4] [--limite N] [--ids 1,2,3]

--csv: el CSV congelado del pre-registro (main 6e660fe, SHA-256 d8862ad9...).
Solo corre partidos terminados de ligas validas con stats (corners total > 0):
son los unicos que se evaluan.

Por partido:
  - base: modelo de produccion para tarjetas = codigo a821c8f con el
    multiplicador en f = 0,5 (m' = 1 + 0,5*(m - 1), como FACTOR_MULTIPLICADOR_
    TARJETAS de main) y el multiplicador de goles sacado (#117: el min(..., 1,15)
    devuelve 1), sin arbitro. Verificado igual a main 6e660fe en 34/34 partidos
    (enmienda 1 del pre-registro);
  - L{k}: base * m_arb con historial del arbitro en la misma liga, k en {10,25,50};
  - T{k}: lo mismo con historial en todas las competiciones (informativo).
Si m_arb da 1 (sin arbitro o sin historial) la variante es identica a la
base y se copia sin volver a simular. El multiplicador se intercepta en el
unico min(..., 1.5) del modulo, como harness_tarjetas.py. La semilla de
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
from arbitro import FactorArbitro, clave  # noqa: E402
from harness_tarjetas import _resumen  # noqa: E402

KS = (10, 25, 50)
F_BASE = 0.5
_CTX = {"m_arb": 1.0, "llamado": False}
_CAP = {}


def _min_harness(*a, **k):
    r = builtins.min(*a, **k)
    if len(a) == 2 and not k and a[1] == 1.5:
        _CTX["llamado"] = True
        return (1 + F_BASE * (r - 1)) * _CTX["m_arb"]
    if len(a) == 2 and not k and a[1] == 1.15:
        return 1.0   # multiplicador de goles sacado en main (#117): max(0,9, 1,0) = 1,0
    return r


def _iniciar():
    sys.path.insert(0, H.SERVICES)
    import data_loader as DL
    DL.CSV_FUTBOL = os.environ["CSV_ARBITRO"]
    H._iniciar()
    FS = H._G["FS"]
    FS.min = _min_harness
    crudo, validas = H._G["crudo"], H._G["validas"]
    hist = crudo[crudo["fixture_id"].isin(validas["fixture_id"]) & crudo["estado"].isin(H.TERMINADOS)]
    H._G["FA"] = FactorArbitro(hist)
    orig_sim = FS.simular

    def sim_variantes(*a, **kw):
        _CTX.update(m_arb=1.0, llamado=False)
        base = orig_sim(*a, **kw)
        if base is None or base[0] is None:
            return base
        _CAP.update(_resumen(base[0], "base"))
        _CAP["mult_llamado"] = _CTX["llamado"]
        for suf, m in _CAP.pop("_variantes"):
            if m == 1.0:
                _CAP.update({c.replace("_base", f"_{suf}"): v for c, v in _resumen(base[0], "base").items()})
                continue
            _CTX["m_arb"] = m
            FS._cache_resultados.clear()
            r = orig_sim(*a, **kw)
            _CAP.update(_resumen(r[0], suf))
        _CTX["m_arb"] = 1.0
        return base

    FS.simular = sim_variantes


def correr(fid):
    _CAP.clear()
    v, FA = H._G["validas"], H._G["FA"]
    fila = v.loc[v["fixture_id"] == fid].iloc[0]
    corte = fila["fecha"] - pd.Timedelta(hours=1)
    arb, liga = fila.get("arbitro"), fila["liga"]
    variantes = []
    for todas, letra in ((False, "L"), (True, "T")):
        n, sy, smu = FA.historial(arb, liga, corte, todas=todas)
        _CAP[f"n_hist_{letra}"] = n
        _CAP[f"ratio_{letra}"] = sy / smu if smu else None
        for k in KS:
            m = FA.factor(n, sy, smu, k)
            _CAP[f"marb_{letra}{k}"] = m
            variantes.append((f"{letra}{k}", m))
    _CAP["clave_arbitro"] = clave(arb)
    _CAP["_variantes"] = variantes
    out = H.correr_partido(fid)
    _CAP.pop("_variantes", None)
    out.update(_CAP)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--desde", required=True)
    ap.add_argument("--hasta", required=True)
    ap.add_argument("--salida", required=True)
    ap.add_argument("--procesos", type=int, default=max(os.cpu_count() - 2, 1))
    ap.add_argument("--limite", type=int, default=0)
    ap.add_argument("--ids", default="")
    a = ap.parse_args()
    os.environ["CSV_ARBITRO"] = os.path.abspath(a.csv)
    _iniciar()
    v = H._G["validas"]
    t = v["fecha"].dt.tz_convert("UTC")
    cor = v["corners_local"].fillna(0) + v["corners_visitante"].fillna(0)
    sel = v[v["estado"].isin(H.TERMINADOS) & (cor > 0) & (t >= pd.Timestamp(a.desde, tz="UTC"))
            & (t < pd.Timestamp(a.hasta, tz="UTC") + pd.Timedelta(days=1))].sort_values("fecha")
    ids = sel["fixture_id"].tolist()
    if a.ids:
        quiero = {float(x) for x in a.ids.split(",")}
        ids = [i for i in ids if float(i) in quiero]
    ids = ids[: a.limite or None]
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
