"""Variantes de PREREGISTRO_multiplicador_tarjetas.md sobre el harness point-in-time.

Uso desde backend/:
  python scripts/backtest_futbol/harness_tarjetas.py --desde 2025-07-01 --hasta 2025-12-31 \
      --salida pred_tj_2025h2.csv [--procesos 6] [--limite N]

Por partido corre simular() igual que harness.py (f = 1, produccion) y lo
repite con el multiplicador de tarjetas cambiado:
  - H-T (decide): m' = 1 + f*(m - 1), f en {0,5; 0}.
  - Componentes (informativo): m' = min(1 + fp*0,15*presion + fa*0,10*agresividad
    + fc*0,35*clasico, 1,5), con uno de los tres factores en 0 o 0,5 y los
    otros en 1.
No toca el codigo del modelo: futbol_service calcula
  multiplicador_tarjetas = min(multiplicador_tarjetas, 1.5)
(el unico min(..., 1.5) del modulo); el harness pone un min propio en el
modulo que devuelve m' en esa llamada y pasa todo lo demas tal cual. Los
componentes se leen envolviendo calcular_presion / calcular_indice_agresividad
/ es_clasico de modelo_presion (solo los registran). La semilla de simular()
sale de equipos + fecha, asi que todas las variantes de un partido usan el
mismo azar.
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
COMPONENTES = [("p", 0.0), ("p", 0.5), ("a", 0.0), ("a", 0.5), ("c", 0.0), ("c", 0.5)]
LINEAS_TOTAL = (2.5, 3.5, 4.5, 5.5, 6.5, 7.5)
LINEAS_EQUIPO = (0.5, 1.5, 2.5, 3.5)
_CAP = {}
_CTX = {"modo": None}   # None = produccion; ("f", f) o ("comp", letra, factor)
_COMP = {}


def _min_harness(*a, **k):
    r = builtins.min(*a, **k)
    if len(a) == 2 and not k and a[1] == 1.5:
        _COMP["m_crudo"] = a[0]
        modo = _CTX["modo"]
        if modo is None:
            return r
        if modo[0] == "f":
            return 1 + modo[1] * (r - 1)
        _, letra, fac = modo
        fp, fa, fc = (fac if letra == x else 1.0 for x in "pac")
        p = sum(_COMP["p"]) / 2
        ag = sum(_COMP["a"]) / 2
        return builtins.min(1 + fp * 0.15 * p + fa * 0.10 * ag + fc * 0.35 * float(_COMP["c"]), 1.5)
    return r


def _resumen(sim, suf):
    out = {f"proj_{suf}": sim.get("tarjetas_totales_proj")}
    tou = sim.get("tarjetas_ou") or {}
    for ln in LINEAS_TOTAL:
        out[f"o{ln}_{suf}"] = tou.get(ln, {}).get("over")
    for lado, clave in (("l", "tarjetas_ou_local"), ("v", "tarjetas_ou_visitante")):
        t = sim.get(clave) or {}
        for ln in LINEAS_EQUIPO:
            out[f"{lado}{ln}_{suf}"] = t.get(ln, {}).get("over")
    return out


def _iniciar():
    H._iniciar()
    FS, MP = H._G["FS"], H._G["MP"]
    FS.min = _min_harness
    orig_p, orig_a, orig_c = MP.calcular_presion, MP.calcular_indice_agresividad, MP.es_clasico

    def presion(*a, **k):
        v = orig_p(*a, **k)
        _COMP.setdefault("p", []).append(v)
        return v

    def agresividad(*a, **k):
        v = orig_a(*a, **k)
        _COMP.setdefault("a", []).append(v[0])
        return v

    def clasico(*a, **k):
        v = orig_c(*a, **k)
        _COMP["c"] = bool(v)
        return v

    MP.calcular_presion, MP.calcular_indice_agresividad, MP.es_clasico = presion, agresividad, clasico
    orig_sim = FS.simular

    def sim_variantes(*a, **k):
        _CTX["modo"] = None
        _COMP.clear()
        base = orig_sim(*a, **k)
        if base is None or base[0] is None:
            return base
        _CAP.update(_resumen(base[0], "f1"))
        _CAP["m"] = _COMP.get("m_crudo")
        if "p" in _COMP:
            _CAP.update(presion=sum(_COMP["p"]) / 2, agresividad=sum(_COMP["a"]) / 2,
                        clasico=_COMP.get("c"))
        variantes = [(("f", f), f"f{f}") for f in F_VALORES]
        if "p" in _COMP:   # sin componentes (excepcion en modelo_presion) el multiplicador ya es 1
            variantes += [(("comp", le, fa), f"{le}{fa}") for le, fa in COMPONENTES]
        for modo, suf in variantes:
            _CTX["modo"] = modo
            _COMP.clear()
            FS._cache_resultados.clear()
            r = orig_sim(*a, **k)
            _CAP.update(_resumen(r[0], suf))
        _CTX["modo"] = None
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
    pd.DataFrame(filas).to_csv(a.salida, index=False)
    print("listo:", a.salida)


if __name__ == "__main__":
    main()
