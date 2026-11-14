"""Analisis de PREREGISTRO_tiros_localia.md (congelado 74e9dfa; escrito antes de
medir la eleccion y de ver resultados).

Tres pasos, en orden:

  medir    b_serie = media de (real - proyeccion) del LOCAL con el modelo actual
           en la eleccion (jul-dic 2025), para L-arco y L-tiros. 2 decimales.
           IC90 por bloques de semana; si el IC90 incluye 0 o b < 0, esa
           serie no tiene correccion. Visitante: informativo.
  elegir   por serie, c en {0; 0,5; 1} con menor Brier de Over de la linea
           central del local en la eleccion (4.5 arco, 13.5 tiros);
           4 decimales, empate -> el c mas chico.
  evaluar  2026, con las sumas elegidas:
           1) entra si el Brier de la central del local mejora contra el modelo
              actual (IC90 inferior > 0);
           2) L-arco / L-tiros con la correccion: C5 contra R1 y C4 (central,
              Over y Under);
           3) si entro la de su serie, T-arco / T-tiros: C5 en la central
              (8.5 / 24.5) y C4 en la central + lineas de Top Picks.

Uso desde backend/ (este worktree):
  python scripts/backtest_futbol/analizar_localia.py medir --servicios RUTA/app/services \
      --csv datos_tiros_eea826c.csv --eleccion pred_ti_2025h2.csv --salida loc_medir.json
  python ... elegir --servicios ... --csv ... --medir loc_medir.json \
      --c0 pred_ti_2025h2.csv --c05 pred_loc_2025h2_c05.csv --c1 pred_loc_2025h2_c1.csv \
      --salida loc_elegir.json
  python ... evaluar --servicios ... --csv ... --elegir loc_elegir.json \
      --actual pred_ti_2026a.csv pred_ti_2026b.csv --variante pred_loc_2026a.csv pred_loc_2026b.csv \
      --salida scripts/backtest_futbol/resultados_tiros_localia.json
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
import analizar_tiros as AT  # noqa: E402

SERIES_L = {"arco": "L-arco", "tiros": "L-tiros"}
CENTRAL_L = {"L-arco": 4.5, "L-tiros": 13.5}            # resultados_tiros.json
CENTRAL_T = {"T-arco": 8.5, "T-tiros": 24.5}
TOTAL_DE = {"arco": "T-arco", "tiros": "T-tiros"}
CANDIDATOS = (0.0, 0.5, 1.0)


def cargar(a):
    A.SERVICES = os.path.abspath(a.servicios)
    sys.path.insert(0, A.SERVICES)
    import data_loader as DL
    DL.CSV_FUTBOL = os.path.abspath(a.csv)
    crudo, validas, _ = A.cargar_resultados()
    h = crudo[crudo["fixture_id"].isin(validas["fixture_id"]) & crudo["estado"].isin(A.TERMINADOS)]
    h = h.assign(t=h["fecha"].dt.tz_convert("UTC"))
    h = h[(h["corners_local"].fillna(0) + h["corners_visitante"].fillna(0)) > 0]
    return crudo, h


def sesgo(d, serie):
    """media e IC90 de (real - proyeccion)."""
    x = (AT.real(d, serie) - d[f"proj_{serie}"]).to_numpy(float)
    media, lo, hi = A.ic_bloques(x, d["semana"].to_numpy())
    return {"n": len(d), "real_menos_proj": A.r4(media), "ic90": [round(lo, 4), round(hi, 4)]}


def brier_central(d, serie, ln):
    y = (AT.real(d, serie) > ln).astype(float).to_numpy()
    return A.brier_bin(d[f"o_{serie}_{ln}"].to_numpy(float), y)


def pares(base, var, serie):
    """Filas de la serie en las dos corridas, mismo orden (por fixture_id)."""
    b = AT.de_serie(base, serie)
    v = AT.de_serie(var, serie)
    ids = sorted(set(b["fixture_id"]) & set(v["fixture_id"]))
    b = b.set_index("fixture_id").loc[ids].reset_index()
    v = v.set_index("fixture_id").loc[ids].reset_index()
    return b, v


def medir(a):
    crudo, _ = cargar(a)
    e, n = AT.preparar(a.eleccion, crudo)
    res = {"n_eleccion": n, "b": {}, "informativo_visitante": {}}
    for m, serie in SERIES_L.items():
        s = sesgo(AT.de_serie(e, serie), serie)
        b = round(s["real_menos_proj"], 2)
        corrige = bool(b > 0 and s["ic90"][0] > 0)
        res["b"][m] = {**s, "b": b if corrige else None, "corrige": corrige,
                       "sumas_candidatas": {str(c): round(c * b, 4) for c in CANDIDATOS} if corrige else None}
        sv = f"V-{m}"
        res["informativo_visitante"][sv] = sesgo(AT.de_serie(e, sv), sv)
    return res


def elegir(a):
    crudo, _ = cargar(a)
    med = json.load(open(a.medir, encoding="utf-8"))
    corridas = {0.0: AT.preparar([a.c0], crudo)[0]}
    if a.c05:
        corridas[0.5] = AT.preparar([a.c05], crudo)[0]
    if a.c1:
        corridas[1.0] = AT.preparar([a.c1], crudo)[0]
    res = {"elegido": {}, "brier": {}}
    for m, serie in SERIES_L.items():
        info = med["b"][m]
        if not info["corrige"]:
            res["elegido"][m] = {"c": 0.0, "suma": 0.0, "nota": "sin b (IC90 incluye 0 o b < 0)"}
            continue
        ln = CENTRAL_L[serie]
        base = corridas[0.0]
        br = {}
        for c, d in corridas.items():
            b, v = pares(base, d, serie)
            br[c] = round(float(brier_central(v, serie, ln).mean()), 4)
        mejor = min(br.values())
        c = min(k for k, v in br.items() if v == mejor)
        res["brier"][serie] = {str(k): v for k, v in br.items()}
        res["elegido"][m] = {"c": c, "suma": round(c * info["b"], 4)}
    return res


def evaluar(a):
    crudo, h = cargar(a)
    eleg = json.load(open(a.elegir, encoding="utf-8"))["elegido"]
    act, n_act = AT.preparar(a.actual, crudo)
    var, n_var = AT.preparar(a.variante, crudo)
    res = {"n_actual": n_act, "n_variante": n_var, "sumas": eleg, "entra": {}, "series_local": {},
           "totales": {}, "informativo": {}}
    for m, serie in SERIES_L.items():
        c = eleg[m]["c"]
        ln = CENTRAL_L[serie]
        b, v = pares(act, var, serie)
        if c == 0:
            res["entra"][serie] = {"entra": False, "nota": "c = 0 en la eleccion: no cambia"}
        else:
            r = AT.mejora(brier_central(b, serie, ln), brier_central(v, serie, ln), v["semana"].to_numpy())
            r["n"] = len(v)
            r["entra"] = bool(r["ic90"][0] > 0)
            res["entra"][serie] = r
        entra = res["entra"][serie]["entra"]
        # 2) serie del local con el modelo resultante
        d = v if entra else b
        tasa = AT.TasaLiga(h, serie, [ln])
        r1 = pd.Series([tasa.tasa(lg, ct, ln) for lg, ct in zip(d["liga"], d["corte"])])
        rc5, rc4 = AT.c5(d, serie, ln, r1), AT.c4(d, serie, [ln])
        res["series_local"][serie] = {"con_correccion": entra, "linea_central": ln, "C5": rc5, "C4": rc4,
                                      "pasa": bool(rc5["pasa"] and rc4["pasa"])}
        # b y v tienen los mismos partidos en el mismo orden: el mismo R1 sirve
        res["informativo"][serie] = {"actual": AT.informativo(b, serie, ln, {ln: r1}, set()),
                                     "variante": AT.informativo(v, serie, ln, {ln: r1}, set())}
        # 3) total del partido
        st = TOTAL_DE[m]
        lt = CENTRAL_T[st]
        if not entra:
            res["totales"][st] = {"evaluado": False, "nota": "no entro la correccion de su serie: sigue oculto"}
            continue
        bt, vt = pares(act, var, st)
        lineas = sorted({lt, *AT.MERCADOS[m][2]})
        tasa_t = AT.TasaLiga(h, st, lineas)
        r1t = {x: pd.Series([tasa_t.tasa(lg, ct, x) for lg, ct in zip(vt["liga"], vt["corte"])]) for x in lineas}
        rc5, rc4 = AT.c5(vt, st, lt, r1t[lt]), AT.c4(vt, st, lineas)
        res["totales"][st] = {"evaluado": True, "linea_central": lt, "C5": rc5, "C4": rc4,
                              "pasa": bool(rc5["pasa"] and rc4["pasa"]),
                              "informativo_actual_C5": AT.c5(bt, st, lt, pd.Series(
                                  [tasa_t.tasa(lg, ct, lt) for lg, ct in zip(bt["liga"], bt["corte"])]))}
        res["informativo"][st] = AT.informativo(vt, st, lt, r1t, set())
    # visitante: no deberia cambiar (control)
    for m in SERIES_L:
        sv = f"V-{m}"
        b, v = pares(act, var, sv)
        cols = [c for c in b.columns if c.startswith(f"o_{sv}_") or c == f"proj_{sv}"]
        res["informativo"][f"{sv}_identico_a_actual"] = bool(np.allclose(b[cols].to_numpy(float), v[cols].to_numpy(float),
                                                                          equal_nan=True, rtol=0, atol=0))
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paso", choices=["medir", "elegir", "evaluar"])
    ap.add_argument("--servicios", required=True)
    ap.add_argument("--csv", required=True)
    ap.add_argument("--eleccion", nargs="+")
    ap.add_argument("--medir")
    ap.add_argument("--c0")
    ap.add_argument("--c05")
    ap.add_argument("--c1")
    ap.add_argument("--elegir")
    ap.add_argument("--actual", nargs="+")
    ap.add_argument("--variante", nargs="+")
    ap.add_argument("--salida", required=True)
    a = ap.parse_args()
    res = {"medir": medir, "elegir": elegir, "evaluar": evaluar}[a.paso](a)
    with open(a.salida, "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1, default=str)
    print(json.dumps(res, ensure_ascii=False, indent=1, default=str)[:4000])


if __name__ == "__main__":
    main()
