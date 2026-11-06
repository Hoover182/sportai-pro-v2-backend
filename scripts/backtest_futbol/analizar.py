"""Metricas, referencias y criterios del backtest de futbol (PREREGISTRO.md).

Uso desde backend/:
  python scripts/backtest_futbol/analizar.py --pred predicciones.csv --salida resultados.json
Lee app/services/futbol_partidos.csv para resultados y referencias.
"""
import argparse
import bisect
import json
import os
import sys
from collections import defaultdict

import numpy as np
import pandas as pd

AQUI = os.path.dirname(os.path.abspath(__file__))
SERVICES = os.path.abspath(os.path.join(AQUI, "..", "..", "app", "services"))
TERMINADOS = ("FT", "AET", "PEN")
N_BOOT, SEMILLA = 2000, 2026
MIN_PREVIOS, MIN_LIGA, DIAS_R1 = 5, 50, 365
UMBRAL_FUERTE, TOLERANCIA_C4 = 0.70, -0.03
EPS = 1e-6

INTERNACIONALES = {"Champions League", "Europa League", "Conference League", "Copa Libertadores",
                   "Copa Sudamericana", "Recopa Sudamericana", "Mundial 2026"}
PALABRAS_COPA = ("copa", "cup", "pokal", "taça", "taca", "beker", "kupasi", "coppa", "coupe",
                 "shield", "trophée", "trophee", "supercopa", "super cup", "superliga colombia")


# ------------------------------------------------------------ datos
def cargar_resultados():
    sys.path.insert(0, SERVICES)
    cwd = os.getcwd()
    os.chdir(SERVICES)
    import data_loader as DL
    from futbol_service import es_amistoso
    crudo = DL.cargar_partidos_csv()
    os.chdir(cwd)
    validas = DL.filtrar_ligas_validas(crudo)
    return crudo, validas, es_amistoso


def goles_90(df):
    """(gl, gv) a 90': goles_90_* si existen; si no, goles_* solo en FT."""
    tiene90 = df["goles_90_local"].notna() & df["goles_90_visitante"].notna()
    ft = (df["estado"] == "FT") & df["goles_local"].notna() & df["goles_visitante"].notna()
    gl = np.where(tiene90, df["goles_90_local"], np.where(ft, df["goles_local"], np.nan))
    gv = np.where(tiene90, df["goles_90_visitante"], np.where(ft, df["goles_visitante"], np.nan))
    return gl, gv


def tipo_competicion(liga, es_amistoso):
    if es_amistoso(liga):
        return "amistosos"
    if liga in INTERNACIONALES:
        return "copas_internacionales"
    if any(p in liga.lower() for p in PALABRAS_COPA):
        return "copas_nacionales"
    return "ligas"


# ------------------------------------------------------------ referencias
class Frecuencias:
    """Tasas (local, empate, visitante, over25, ambos) en [t-365d, t) por liga y global."""

    def __init__(self, hist):
        h = hist.sort_values("t")
        self.glob = self._armar(h)
        self.liga = {lg: self._armar(g) for lg, g in h.groupby("liga")}

    @staticmethod
    def _armar(g):
        y = np.column_stack([g["gl"] > g["gv"], g["gl"] == g["gv"], g["gl"] < g["gv"],
                             (g["gl"] + g["gv"]) > 2.5, (g["gl"] > 0) & (g["gv"] > 0)]).astype(float)
        return g["t"].astype("int64").to_numpy(), np.vstack([np.zeros(5), np.cumsum(y, axis=0)])

    @staticmethod
    def _ventana(serie, t0, t1):
        ts, acum = serie
        i, j = np.searchsorted(ts, t0, "left"), np.searchsorted(ts, t1, "left")
        return j - i, acum[j] - acum[i]

    def tasas(self, liga, corte):
        t1 = corte.value
        t0 = (corte - pd.Timedelta(days=DIAS_R1)).value
        if liga in self.liga:
            n, s = self._ventana(self.liga[liga], t0, t1)
            if n >= MIN_LIGA:
                return s / n, "liga"
        n, s = self._ventana(self.glob, t0, t1)
        return s / n, "global"


class PuntosPorPartido:
    """Puntos por partido (3/1/0 a 90') en los ultimos 10 terminados, cualquier competicion."""

    def __init__(self, hist):
        self.eq = defaultdict(lambda: ([], []))
        for r in hist.sort_values("t").itertuples(index=False):
            pl = 3 if r.gl > r.gv else (1 if r.gl == r.gv else 0)
            pv = 3 if r.gv > r.gl else (1 if r.gl == r.gv else 0)
            for e, p in ((r.equipo_local, pl), (r.equipo_visitante, pv)):
                self.eq[e][0].append(r.t.value)
                self.eq[e][1].append(p)

    def ppg(self, equipo, corte):
        ts, pts = self.eq.get(equipo, ([], []))
        j = bisect.bisect_left(ts, corte.value)
        ult = pts[max(j - 10, 0):j]
        return np.mean(ult) if ult else np.nan


# ------------------------------------------------------------ metricas
def brier_1x2(P, Y):
    return ((P - Y) ** 2).sum(axis=1)


def logloss_1x2(P, Y):
    return -np.log(np.clip((P * Y).sum(axis=1), EPS, 1))


def brier_bin(p, y):
    return (p - y) ** 2


def logloss_bin(p, y):
    p = np.clip(p, EPS, 1 - EPS)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def ic_bloques(valores, bloques, rng_semilla=SEMILLA, n=N_BOOT):
    """Media de `valores` y percentiles 5/95 por bootstrap de bloques (semana)."""
    valores = np.asarray(valores, float)
    codigos, inv = np.unique(bloques, return_inverse=True)
    suma = np.bincount(inv, weights=valores, minlength=len(codigos))
    cuenta = np.bincount(inv, minlength=len(codigos)).astype(float)
    rng = np.random.default_rng(rng_semilla)
    idx = rng.integers(0, len(codigos), size=(n, len(codigos)))
    medias = suma[idx].sum(axis=1) / cuenta[idx].sum(axis=1)
    return float(valores.mean()), float(np.percentile(medias, 5)), float(np.percentile(medias, 95))


def calibracion_bandas(p, y):
    out = []
    for lo in np.arange(0, 1, 0.1):
        m = (p >= lo) & (p < lo + 0.1 if lo < 0.9 else p <= 1.0)
        if m.sum():
            out.append({"banda": f"{int(lo*100)}-{int(lo*100)+10}", "n": int(m.sum()),
                        "prob_media": round(float(p[m].mean()), 4), "tasa_real": round(float(y[m].mean()), 4)})
    return out


def r4(x):
    return None if x is None else round(float(x), 4)


# ------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pred", required=True)
    ap.add_argument("--salida", required=True)
    a = ap.parse_args()

    crudo, validas, es_amistoso = cargar_resultados()
    pred = pd.read_csv(a.pred)
    res = {"n_predicciones": len(pred)}

    # Historial con resultado a 90' (para referencias)
    gl, gv = goles_90(crudo)
    hist = crudo.assign(gl=gl, gv=gv, t=crudo["fecha"].dt.tz_convert("UTC"))
    hist = hist[hist["estado"].isin(TERMINADOS) & hist["gl"].notna()]
    hist_validas = hist[hist["fixture_id"].isin(validas["fixture_id"])]
    freq = Frecuencias(hist_validas)
    ppg = PuntosPorPartido(hist)

    # Partidos evaluados
    d = pred.merge(crudo, on="fixture_id", how="left")
    d["gl"], d["gv"] = goles_90(d)
    exclusiones = {
        "error_o_none": int((d["error"].fillna("") != "").sum() + d["p_local"].isna().sum()
                            - ((d["error"].fillna("") != "") & d["p_local"].isna()).sum()),
        "menos_de_5_previos": int(((d["n_prev_local"] < MIN_PREVIOS) | (d["n_prev_visitante"] < MIN_PREVIOS)).sum()),
        "sin_resultado_90": int(d["gl"].isna().sum()),
    }
    ok = (d["p_local"].notna() & (d["error"].fillna("") == "")
          & (d["n_prev_local"] >= MIN_PREVIOS) & (d["n_prev_visitante"] >= MIN_PREVIOS) & d["gl"].notna())
    d = d[ok].copy().reset_index(drop=True)
    res["exclusiones"] = exclusiones
    res["n_evaluados"] = len(d)

    d["t"] = d["fecha"].dt.tz_convert("UTC")
    d["corte"] = d["t"] - pd.Timedelta(hours=1)
    iso = d["t"].dt.isocalendar()
    d["semana"] = iso["year"].astype(str) + "-" + iso["week"].astype(str).str.zfill(2)
    d["tipo"] = d["liga"].map(lambda x: tipo_competicion(x, es_amistoso))

    # Referencias
    R1 = np.array([freq.tasas(lg, c)[0] for lg, c in zip(d["liga"], d["corte"])])
    res["r1_fuente"] = pd.Series([freq.tasas(lg, c)[1] for lg, c in zip(d["liga"], d["corte"])]).value_counts().to_dict()
    ppg_l = np.array([ppg.ppg(e, c) for e, c in zip(d["equipo_local"], d["corte"])])
    ppg_v = np.array([ppg.ppg(e, c) for e, c in zip(d["equipo_visitante"], d["corte"])])

    # Resultados
    Y = np.column_stack([d["gl"] > d["gv"], d["gl"] == d["gv"], d["gl"] < d["gv"]]).astype(float)
    y_over = ((d["gl"] + d["gv"]) > 2.5).astype(float).to_numpy()
    y_ambos = ((d["gl"] > 0) & (d["gv"] > 0)).astype(float).to_numpy()

    P = d[["p_local", "p_empate", "p_visitante"]].to_numpy(float)
    P = P / P.sum(axis=1, keepdims=True)
    P_r1 = R1[:, :3] / R1[:, :3].sum(axis=1, keepdims=True)
    p_over = d["p_over25"].to_numpy(float)
    p_ambos = d["p_ambos"].to_numpy(float)
    sem = d["semana"].to_numpy()

    def bloque(nombre, metrica_m, metrica_r):
        mejora = metrica_r - metrica_m
        media, lo, hi = ic_bloques(mejora, sem)
        return {"modelo": r4(metrica_m.mean()), "R1": r4(metrica_r.mean()),
                "mejora": r4(media), "ic90": [round(lo, 5), round(hi, 5)], "cumple": bool(lo > 0)}

    # C1: 1X2
    acierto_m = (P.argmax(axis=1) == Y.argmax(axis=1))
    pick_r2 = np.where(np.nan_to_num(ppg_v, nan=-1) > np.nan_to_num(ppg_l, nan=-1), 2, 0)
    acierto_r2 = (pick_r2 == Y.argmax(axis=1))
    c1 = bloque("1x2", brier_1x2(P, Y), brier_1x2(P_r1, Y))
    c1.update(acierto_modelo=r4(acierto_m.mean()), acierto_R2=r4(acierto_r2.mean()),
              acierto_R1=r4((P_r1.argmax(axis=1) == Y.argmax(axis=1)).mean()),
              logloss_modelo=r4(logloss_1x2(P, Y).mean()), logloss_R1=r4(logloss_1x2(P_r1, Y).mean()))
    c1["cumple_brier"] = c1.pop("cumple")
    c1["cumple_acierto"] = bool(acierto_m.mean() >= acierto_r2.mean())
    c1["pasa"] = c1["cumple_brier"] and c1["cumple_acierto"]
    res["C1_1x2"] = c1

    # C2 / C3
    for clave, p, y, col in (("C2_over25", p_over, y_over, 3), ("C3_ambos", p_ambos, y_ambos, 4)):
        c = bloque(clave, brier_bin(p, y), brier_bin(R1[:, col], y))
        c.update(acierto_modelo=r4(((p >= 0.5) == y).mean()), acierto_R1=r4(((R1[:, col] >= 0.5) == y).mean()),
                 logloss_modelo=r4(logloss_bin(p, y).mean()), logloss_R1=r4(logloss_bin(R1[:, col], y).mean()),
                 tasa_real=r4(y.mean()))
        c["pasa"] = c.pop("cumple")
        res[clave] = c

    # C4: probabilidades fuertes
    ps, ys, bs = [], [], []
    for k in range(3):
        ps.append(P[:, k]); ys.append(Y[:, k]); bs.append(sem)
    for p, y in ((p_over, y_over), (1 - p_over, 1 - y_over), (p_ambos, y_ambos), (1 - p_ambos, 1 - y_ambos)):
        ps.append(p); ys.append(y); bs.append(sem)
    ps, ys, bs = np.concatenate(ps), np.concatenate(ys), np.concatenate(bs)
    m = ps >= UMBRAL_FUERTE
    media, lo, hi = ic_bloques(ys[m] - ps[m], bs[m])
    res["C4_fuertes"] = {"n": int(m.sum()), "prob_media": r4(ps[m].mean()), "tasa_real": r4(ys[m].mean()),
                         "diferencia": r4(media), "ic90": [round(lo, 5), round(hi, 5)],
                         "pasa": bool(hi >= TOLERANCIA_C4)}

    # ---------------- Informativo
    inf = {}
    inf["calibracion"] = {
        "local": calibracion_bandas(P[:, 0], Y[:, 0]), "empate": calibracion_bandas(P[:, 1], Y[:, 1]),
        "visitante": calibracion_bandas(P[:, 2], Y[:, 2]),
        "over25": calibracion_bandas(p_over, y_over), "ambos": calibracion_bandas(p_ambos, y_ambos),
        "X2": calibracion_bandas(P[:, 1] + P[:, 2], Y[:, 1] + Y[:, 2]),
        "1X": calibracion_bandas(P[:, 0] + P[:, 1], Y[:, 0] + Y[:, 1]),
    }
    por_tipo = {}
    for t, g in d.groupby("tipo"):
        i = g.index.to_numpy()
        por_tipo[t] = {
            "n": len(i),
            "brier_1x2": [r4(brier_1x2(P[i], Y[i]).mean()), r4(brier_1x2(P_r1[i], Y[i]).mean())],
            "acierto_1x2": [r4(acierto_m[i].mean()), r4(acierto_r2[i].mean())],
            "brier_over25": [r4(brier_bin(p_over[i], y_over[i]).mean()), r4(brier_bin(R1[i, 3], y_over[i]).mean())],
            "brier_ambos": [r4(brier_bin(p_ambos[i], y_ambos[i]).mean()), r4(brier_bin(R1[i, 4], y_ambos[i]).mean())],
        }
    inf["por_tipo_[modelo,referencia]"] = por_tipo

    # corners / tarjetas: solo partidos con stats verificadas (corners total > 0)
    cor = d["corners_local"].fillna(0) + d["corners_visitante"].fillna(0)
    ver = (cor > 0).to_numpy()
    tarj = (d["tarjetas_local"].fillna(0) + d["tarjetas_visitante"].fillna(0)).to_numpy()
    for clave, pcol, y in (("corners_over95", "p_corners_over95", (cor > 9.5).astype(float).to_numpy()),
                           ("tarjetas_over45", "p_tarjetas_over45", (tarj > 4.5).astype(float))):
        p = d[pcol].to_numpy(float)
        mm = ver & ~np.isnan(p)
        tasa_fija = y[mm].mean()
        inf[clave] = {"n": int(mm.sum()), "prob_media": r4(p[mm].mean()), "tasa_real": r4(tasa_fija),
                      "brier_modelo": r4(brier_bin(p[mm], y[mm]).mean()),
                      "brier_tasa_del_periodo(ojo: mira el futuro)": r4(brier_bin(np.full(mm.sum(), tasa_fija), y[mm]).mean()),
                      "calibracion": calibracion_bandas(p[mm], y[mm])}
    res["informativo"] = inf

    with open(a.salida, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)

    # Resumen
    print(f"Evaluados {len(d)} de {len(pred)}; exclusiones {exclusiones}; R1 fuente {res['r1_fuente']}")
    c = res["C1_1x2"]
    print(f"C1 1X2: Brier {c['modelo']} vs R1 {c['R1']} mejora {c['mejora']} IC90 {c['ic90']} | "
          f"acierto {c['acierto_modelo']} vs R2 {c['acierto_R2']} -> {'PASA' if c['pasa'] else 'NO PASA'}")
    for k in ("C2_over25", "C3_ambos"):
        c = res[k]
        print(f"{k}: Brier {c['modelo']} vs R1 {c['R1']} mejora {c['mejora']} IC90 {c['ic90']} -> {'PASA' if c['pasa'] else 'NO PASA'}")
    c = res["C4_fuertes"]
    print(f"C4 fuertes: n {c['n']} prob {c['prob_media']} real {c['tasa_real']} dif {c['diferencia']} IC90 {c['ic90']} -> {'PASA' if c['pasa'] else 'NO PASA'}")


if __name__ == "__main__":
    main()
