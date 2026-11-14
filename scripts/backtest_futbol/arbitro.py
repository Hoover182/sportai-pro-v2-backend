"""Factor del arbitro para tarjetas (PREREGISTRO_arbitro_tarjetas.md).

    m_arb = (sum y_i + k * mu_bar) / (sum mu_i + k * mu_bar),   mu_bar = sum mu_i / n

- y_i: amarillas totales de cada partido previo del arbitro (las dos columnas
  presentes).
- mu_i: media de amarillas totales de la liga en [t_i - 365d, t_i), partidos
  con stats (corners total > 0); con menos de 50, la media global de esa
  ventana. Mismo conjunto que la R1 de tarjetas.
- Historial: misma clave de arbitro, misma liga (o todas las competiciones,
  informativo), fecha < corte.
Sin arbitro o sin historial: m_arb = 1.
"""
import re
import unicodedata

import numpy as np
import pandas as pd

DIAS, MIN_LIGA = 365, 50


def clave(nombre):
    """Inicial del primer pedazo + ultimo pedazo, sin pais, sin acentos, minusculas."""
    if not isinstance(nombre, str) or not nombre.strip():
        return None
    n = nombre.split(",")[0].strip()
    n = "".join(c for c in unicodedata.normalize("NFKD", n) if not unicodedata.combining(c)).lower()
    t = [w for w in re.split(r"[\s\.]+", n) if w]
    if not t:
        return None
    return t[0][0] + " " + t[-1]


def _ventana(ts, acum_y, t):
    """(suma, n) en [t - 365d, t) para arrays ordenados por tiempo."""
    i = np.searchsorted(ts, t - pd.Timedelta(days=DIAS).value, "left")
    j = np.searchsorted(ts, t, "left")
    return acum_y[j] - acum_y[i], j - i


class FactorArbitro:
    def __init__(self, hist):
        """hist: partidos terminados de ligas validas con columnas fecha (tz),
        liga, arbitro, corners_*, tarjetas_*."""
        h = hist[(hist["corners_local"].fillna(0) + hist["corners_visitante"].fillna(0)) > 0].copy()
        h["t"] = h["fecha"].dt.tz_convert("UTC").astype("int64")
        h["tj"] = h["tarjetas_local"].fillna(0) + h["tarjetas_visitante"].fillna(0)
        h = h.sort_values("t").reset_index(drop=True)
        # mu_i point-in-time (ventana anterior a cada partido)
        g_ts = h["t"].to_numpy()
        g_acum = np.concatenate([[0.0], np.cumsum(h["tj"].to_numpy(float))])
        ligas = {lg: (g["t"].to_numpy(), np.concatenate([[0.0], np.cumsum(g["tj"].to_numpy(float))]))
                 for lg, g in h.groupby("liga")}
        mu = np.empty(len(h))
        for idx, (lg, t) in enumerate(zip(h["liga"].to_numpy(), g_ts)):
            s, n = _ventana(*ligas[lg], t)
            if n < MIN_LIGA:
                s, n = _ventana(g_ts, g_acum, t)
            mu[idx] = s / n if n else np.nan
        h["mu"] = mu
        h["clave"] = h["arbitro"].map(clave)
        ok = (h["clave"].notna() & h["mu"].notna()
              & h["tarjetas_local"].notna() & h["tarjetas_visitante"].notna())
        h = h[ok]
        self.por_liga = self._indexar(h.groupby(["clave", "liga"]))
        self.por_clave = self._indexar(h.groupby("clave"))

    @staticmethod
    def _indexar(grupos):
        out = {}
        for key, g in grupos:
            out[key] = (g["t"].to_numpy(),
                        np.concatenate([[0.0], np.cumsum(g["tj"].to_numpy(float))]),
                        np.concatenate([[0.0], np.cumsum(g["mu"].to_numpy(float))]))
        return out

    def historial(self, arbitro, liga, corte, todas=False):
        """(n, sum_y, sum_mu) con fecha < corte."""
        c = clave(arbitro)
        if c is None:
            return 0, 0.0, 0.0
        serie = (self.por_clave.get(c) if todas else self.por_liga.get((c, liga)))
        if serie is None:
            return 0, 0.0, 0.0
        ts, ay, am = serie
        j = np.searchsorted(ts, pd.Timestamp(corte).tz_convert("UTC").value, "left")
        return int(j), float(ay[j]), float(am[j])

    @staticmethod
    def factor(n, sy, smu, k):
        if n == 0:
            return 1.0
        mu_bar = smu / n
        return (sy + k * mu_bar) / (smu + k * mu_bar)
