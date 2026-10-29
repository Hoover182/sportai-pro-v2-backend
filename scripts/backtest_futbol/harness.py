"""Corre futbol_service.simular() point-in-time sobre partidos terminados.
Criterios y reglas en PREREGISTRO.md (congelado antes de escribir esto).

Uso desde backend/:
  python scripts/backtest_futbol/harness.py --desde 2026-01-01 --hasta 2026-10-28 \
      --elo ruta/elo_historico.csv --salida predicciones_retro.csv [--procesos 6] [--limite N]

Para cada partido, "ahora" = inicio - 1 hora:
- datos: solo filas con fecha < ahora, mas el partido como NS sin goles/stats;
- hora congelada en ahora (pd.Timestamp.now, datetime.now, date.today);
- Elo: ultimo rating de cada equipo con fecha < ahora (elo_historico.csv);
- caches del modelo vaciados antes de cada partido.
No modifica el codigo del modelo: reemplaza nombres dentro de sus modulos.
"""
import argparse
import bisect
import datetime as _dt
import os
import sys
import time
from multiprocessing import Pool

import numpy as np
import pandas as pd

AQUI = os.path.dirname(os.path.abspath(__file__))
SERVICES = os.path.abspath(os.path.join(AQUI, "..", "..", "app", "services"))
TERMINADOS = ("FT", "AET", "PEN")
COLS_RESULTADO = None  # columnas que se vacian en la fila NS (todo lo que no es identidad)
IDENTIDAD = {"fixture_id", "fecha", "estado", "liga", "equipo_local", "equipo_visitante"}

# ---------------------------------------------------------------- reloj
_AHORA = None  # pd.Timestamp tz-aware (UTC)
_RealTS = pd.Timestamp


def _ahora_en(tz):
    if tz is None:
        return _AHORA.tz_convert("UTC").tz_localize(None)  # Render corre en UTC
    return _AHORA.tz_convert(tz)


class _TSMeta(type):
    def __instancecheck__(cls, obj):
        return isinstance(obj, _RealTS)

    def __call__(cls, *a, **k):
        return _RealTS(*a, **k)

    def __getattr__(cls, name):
        return getattr(_RealTS, name)


class _TS(metaclass=_TSMeta):
    @staticmethod
    def now(tz=None):
        return _ahora_en(tz)

    @staticmethod
    def today(tz=None):
        return _ahora_en(tz)


class _PdProxy:
    """pandas con Timestamp.now congelado; todo lo demas es pandas tal cual."""
    Timestamp = _TS

    def __getattr__(self, name):
        return getattr(pd, name)


class _DT(_dt.datetime):
    @classmethod
    def now(cls, tz=None):
        t = _ahora_en(tz).to_pydatetime()
        return t

    @classmethod
    def today(cls):
        return _ahora_en(None).to_pydatetime()


class _Date(_dt.date):
    @classmethod
    def today(cls):
        return _ahora_en(None).date()


# ---------------------------------------------------------------- Elo
class EloPuntual:
    """Mismo uso que el dict de cargar_elo_ratings(): .get(equipo, {})."""

    def __init__(self, idx):
        self.idx = idx

    def get(self, equipo, defecto=None):
        serie = self.idx.get(equipo)
        if serie is None:
            return defecto
        fechas, ratings, ns = serie
        i = bisect.bisect_left(fechas, _AHORA.value) - 1  # ultimo con fecha < ahora
        if i < 0:
            return defecto
        return {"rating": ratings[i], "n_partidos": ns[i]}


def indexar_elo(ruta):
    e = pd.read_csv(ruta, encoding="utf-8-sig")
    e["t"] = pd.to_datetime(e["fecha"], utc=True, errors="coerce")
    e = e.dropna(subset=["t"]).sort_values(["equipo", "t"], kind="stable")
    idx = {}
    for eq, g in e.groupby("equipo", sort=False):
        idx[eq] = (g["t"].astype("int64").tolist(), g["rating"].astype(float).tolist(),
                   g["n_partidos"].astype(int).tolist())
    return idx


# ---------------------------------------------------------------- worker
_G = {}


def _iniciar(elo_ruta):
    sys.path.insert(0, SERVICES)
    cwd = os.getcwd()
    os.chdir(SERVICES)
    import data_loader as DL
    import football_model as FM
    import futbol_service as FS
    import modelo_presion as MP
    crudo = DL.cargar_partidos_csv()
    os.chdir(cwd)
    validas = DL.filtrar_ligas_validas(crudo)
    proxy = _PdProxy()
    for mod in (FS, FM, MP, DL):
        if hasattr(mod, "pd"):
            mod.pd = proxy
    FS.datetime = _DT
    MP.date = _Date
    FS.cargar_elo_ratings = lambda: EloPuntual(_G["elo"])
    FS.print = lambda *a, **k: None  # avisos de nombres: no hacen falta
    _G.update(FS=FS, FM=FM, MP=MP, crudo=crudo, validas=validas, elo=indexar_elo(elo_ruta))


def _limpiar_caches():
    FS, FM, MP = _G["FS"], _G["FM"], _G["MP"]
    MP._cache_tablas.clear()
    FM._cache_eficiencia_arqueros.clear()
    FS._cache_resultados.clear()


def _fila_ns(fila):
    ns = fila.copy()
    for c in ns.index:
        if c not in IDENTIDAD:
            ns[c] = np.nan
    ns["estado"] = "NS"
    return ns


def correr_partido(fixture_id):
    global _AHORA
    crudo, validas, FS = _G["crudo"], _G["validas"], _G["FS"]
    fila = validas.loc[validas["fixture_id"] == fixture_id].iloc[0]
    inicio = fila["fecha"]
    corte = inicio - pd.Timedelta(hours=1)
    _AHORA = corte.tz_convert("UTC")
    ns = _fila_ns(fila).to_frame().T.astype(validas.dtypes.to_dict(), errors="ignore")
    crudo_cut = pd.concat([ns, crudo[crudo["fecha"] < corte]], ignore_index=True)
    df_cut = pd.concat([ns, validas[validas["fecha"] < corte]], ignore_index=True)
    FS._registrar_fuente_h2h(df_cut, crudo_cut)
    _limpiar_caches()
    loc, vis = fila["equipo_local"], fila["equipo_visitante"]
    term = crudo_cut[crudo_cut["estado"].isin(TERMINADOS)]
    n_prev_loc = int(((term["equipo_local"] == loc) | (term["equipo_visitante"] == loc)).sum())
    n_prev_vis = int(((term["equipo_local"] == vis) | (term["equipo_visitante"] == vis)).sum())
    out = {"fixture_id": fixture_id, "n_prev_local": n_prev_loc, "n_prev_visitante": n_prev_vis,
           "error": ""}
    try:
        sim, _, _ = FS.simular(df_cut, loc, vis)
    except Exception as e:  # se reporta, no se esconde
        out["error"] = f"{type(e).__name__}: {e}"[:200]
        return out
    if sim is None:
        out["error"] = "simular devolvio None"
        return out
    out.update(
        p_local=sim["prob_local"], p_empate=sim["prob_empate"], p_visitante=sim["prob_visitante"],
        p_over25=sim["goles_ou"][2.5]["over"], p_under25=sim["goles_ou"][2.5]["under"],
        p_ambos=sim["prob_ambos_marcan"],
        p_corners_over95=sim["corners_ou"].get(9.5, {}).get("over"),
        p_tarjetas_over45=sim["tarjetas_ou"].get(4.5, {}).get("over"),
    )
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--desde", required=True)
    ap.add_argument("--hasta", required=True)
    ap.add_argument("--elo", required=True)
    ap.add_argument("--salida", required=True)
    ap.add_argument("--procesos", type=int, default=max(os.cpu_count() - 2, 1))
    ap.add_argument("--limite", type=int, default=0)
    a = ap.parse_args()

    _iniciar(a.elo)
    v = _G["validas"]
    t = v["fecha"].dt.tz_convert("UTC")
    desde = pd.Timestamp(a.desde, tz="UTC")
    hasta = pd.Timestamp(a.hasta, tz="UTC") + pd.Timedelta(days=1)
    sel = v[v["estado"].isin(TERMINADOS) & (t >= desde) & (t < hasta)].sort_values("fecha")
    ids = sel["fixture_id"].tolist()
    if a.limite:
        ids = ids[:a.limite]
    print(f"{len(ids)} partidos entre {a.desde} y {a.hasta}; {a.procesos} procesos", flush=True)

    t0 = time.time()
    filas = []
    with Pool(a.procesos, initializer=_iniciar, initargs=(a.elo,)) as pool:
        for i, r in enumerate(pool.imap_unordered(correr_partido, ids, chunksize=8), 1):
            filas.append(r)
            if i % 250 == 0 or i == len(ids):
                print(f"  {i}/{len(ids)}  {time.time() - t0:.0f}s", flush=True)
                pd.DataFrame(filas).to_csv(a.salida, index=False)
    pd.DataFrame(filas).to_csv(a.salida, index=False)
    print("listo:", a.salida)


if __name__ == "__main__":
    main()
