"""H2H con cualquier competicion oficial (cargar_df / _h2h): un cruce cuenta
aunque su liga no este en LIGAS_VALIDAS; solo se excluyen amistosos y
exhibiciones. El resto del modelo sigue usando el df filtrado. Las filas de
Malaga-Espanyol son las reales del CSV (2026-10-09).
Correr desde backend/: python -m unittest discover -s tests -v"""
import gc
import os
import sys
import unittest
from unittest import mock

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app", "services"))
import futbol_service as F


def fila(fid, fecha, liga, local, visitante, gl, gv, estado="FT"):
    return {"fixture_id": fid, "fecha": fecha, "liga": liga, "estado": estado,
            "equipo_local": local, "equipo_visitante": visitante, "goles_local": gl, "goles_visitante": gv}


def csv_crudo():
    filas = [
        fila(9519, "2018-05-13T14:15:00", "La Liga", "Espanyol", "Malaga", 4, 1),
        fila(604286, "2020-09-02T16:45:00", "Friendlies Clubs", "Espanyol", "Malaga", 3, 0),
        fila(606795, "2020-11-02T20:00:00", "Segunda División", "Malaga", "Espanyol", 0, 3),
        fila(607089, "2021-05-02T14:00:00", "Segunda División", "Espanyol", "Malaga", 3, 0),
        fila(1, "2019-07-20T18:00:00", "Premier League - Summer Series", "Malaga", "Espanyol", 1, 1),
        fila(2, "2019-08-01T18:00:00", "Copa del Rey", "Malaga", "Espanyol", None, None),   # terminado sin goles
        fila(1570408, "2026-10-09T19:00:00", "La Liga", "Malaga", "Espanyol", None, None, estado="NS"),
    ]
    df = pd.DataFrame(filas)
    df["fecha"] = pd.to_datetime(df["fecha"], utc=True).dt.tz_convert("America/Bogota")
    return df


def cargar():
    with mock.patch.object(F, "_cargar_csv", side_effect=lambda: csv_crudo()):
        return F.cargar_df()


def fechas(h2h):
    return [str(f)[:10] for f in h2h["fecha"]]


class H2HConCompetenciasOficiales(unittest.TestCase):
    def test_caso_malaga_espanyol_cuenta_segunda_division(self):
        df = cargar()
        self.assertNotIn("Segunda División", set(df["liga"]))   # el filtro general no cambia
        self.assertEqual(fechas(F._h2h(df, "Malaga", "Espanyol", n=10)), ["2021-05-02", "2020-11-02", "2018-05-13"])

    def test_amistosos_exhibiciones_y_sin_goles_no_cuentan(self):
        ligas = set(F._h2h(cargar(), "Malaga", "Espanyol", n=10)["liga"])
        self.assertNotIn("Friendlies Clubs", ligas)
        self.assertNotIn("Premier League - Summer Series", ligas)
        self.assertNotIn("Copa del Rey", ligas)

    def test_tope_n_se_respeta(self):
        self.assertEqual(fechas(F._h2h(cargar(), "Malaga", "Espanyol", n=2)), ["2021-05-02", "2020-11-02"])

    def test_otro_df_usa_sus_propias_filas_como_antes(self):
        df = cargar()
        copia = df.copy()   # no es el df que devolvio cargar_df
        esperado = F.ultimos_enfrentamientos_directos(copia, "Malaga", "Espanyol", n=10)
        self.assertEqual(fechas(F._h2h(copia, "Malaga", "Espanyol", n=10)), fechas(esperado))
        self.assertNotIn("Segunda División", set(esperado["liga"]))

    def test_registro_no_crece_sin_fin(self):
        for _ in range(5):
            cargar()          # cada df se descarta enseguida
        gc.collect()
        df = cargar()         # la carga nueva limpia las entradas muertas
        self.assertIn(id(df), F._FUENTE_H2H)
        self.assertTrue(all(ref() is not None for ref, _ in F._FUENTE_H2H.values()))


class TodasLasLlamadasPasanPorH2H(unittest.TestCase):
    def test_ninguna_llamada_directa_fuera_de_h2h(self):
        # simular (modelo), hechos para analisis/nota (n=10 y n=20), lista de
        # cruces del endpoint y value bets: todas tienen que usar _h2h()
        import inspect
        import re
        fuente = inspect.getsource(F)
        cuerpo_h2h = inspect.getsource(F._h2h)
        llamadas = re.findall(r"ultimos_enfrentamientos_directos\(\w", fuente.replace(cuerpo_h2h, ""))
        self.assertEqual(llamadas, [])
        self.assertEqual(len(re.findall(r"\b_h2h\(df, local, visitante, n=", fuente)), 5)


class EsAmistoso(unittest.TestCase):
    def test_amistosos_y_exhibiciones(self):
        for liga in ("Friendlies Clubs", "Club Friendlies 3", "Torneo Amistoso de Verano",
                     "Premier League - Summer Series", "International Champions Cup", "The Atlantic Cup"):
            self.assertTrue(F.es_amistoso(liga), liga)

    def test_competiciones_oficiales(self):
        for liga in ("Segunda División", "Copa del Rey", "Leagues Cup", "CONCACAF Champions Cup",
                     "US Open Cup", "Copa De La Liga", "Paulista - A1", "UEFA Champions League"):
            self.assertFalse(F.es_amistoso(liga), liga)


if __name__ == "__main__":
    unittest.main()
