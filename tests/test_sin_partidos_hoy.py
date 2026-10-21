"""Sin partidos hoy: /top10-mis-competiciones, /partidos-hoy y /top-picks
devuelven vacio en vez de mostrar como de hoy partidos de otro dia (antes:
proxima fecha con partidos, o los 20 terminados mas recientes en /top-picks).
Correr desde backend/: python -m unittest discover -s tests -v"""
import io
import os
import sys
import unittest
from contextlib import redirect_stdout
from unittest import mock

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app", "services"))
import data_loader as DL
import futbol_service as F

HOY = pd.Timestamp.now(tz="America/Bogota").normalize()


def df_con(*partidos):
    """partidos: (dias desde hoy, estado). 20:00 hora Colombia."""
    return pd.DataFrame([
        {"fecha": HOY + pd.Timedelta(days=d, hours=20), "estado": e, "liga": "Liga Colombia",
         "equipo_local": f"L{i}", "equipo_visitante": f"V{i}", "fixture_id": i}
        for i, (d, e) in enumerate(partidos)
    ])


def sin_salida(fn, *args):
    with redirect_stdout(io.StringIO()) as out:
        res = fn(*args)
    return res, out.getvalue()


class ObtenerPartidosHoy(unittest.TestCase):
    def setUp(self):
        DL._avisos_sin_partidos_hoy.clear()

    def test_devuelve_solo_los_de_hoy(self):
        res, _ = sin_salida(DL.obtener_partidos_hoy_futbol, df_con((0, "NS"), (1, "NS"), (-1, "FT")))
        self.assertEqual(res["fixture_id"].tolist(), [0])

    def test_sin_partidos_hoy_no_cae_a_la_proxima_fecha(self):
        res, _ = sin_salida(DL.obtener_partidos_hoy_futbol, df_con((1, "NS"), (2, "NS"), (-1, "FT")))
        self.assertTrue(res.empty)

    def test_terminados_de_hoy_no_cuentan(self):
        res, _ = sin_salida(DL.obtener_partidos_hoy_futbol, df_con((0, "FT"), (1, "NS")))
        self.assertTrue(res.empty)

    def test_avisa_una_vez_y_sospecha_sync_trabado(self):
        df = df_con((1, "NS"), (-5, "FT"))
        _, log1 = sin_salida(DL.obtener_partidos_hoy_futbol, df)
        _, log2 = sin_salida(DL.obtener_partidos_hoy_futbol, df)
        self.assertIn("AVISO sin partidos hoy", log1)
        self.assertIn("POSIBLE SYNC TRABADO", log1)
        self.assertEqual(log2, "")

    def test_con_datos_al_dia_no_sospecha(self):
        _, log = sin_salida(DL.obtener_partidos_hoy_futbol, df_con((1, "NS"), (-1, "FT")))
        self.assertIn("AVISO sin partidos hoy", log)
        self.assertNotIn("SYNC TRABADO", log)


class Endpoints(unittest.TestCase):
    def setUp(self):
        DL._avisos_sin_partidos_hoy.clear()
        # Solo un partido manana y uno terminado ayer: ninguno es de hoy.
        self.df = df_con((1, "NS"), (-1, "FT"))

    def _llamar(self, fn, *args):
        # Ningun partido es de hoy: no tiene que simular ninguno (antes
        # simulaba el de manana, o los terminados de ayer en /top-picks).
        simular = mock.MagicMock(return_value=(None, None, None))
        with mock.patch.object(F, "cargar_df", return_value=self.df), mock.patch.object(F, "simular", simular):
            res, _ = sin_salida(fn, *args)
        simular.assert_not_called()
        return res

    def test_top10_mis_competiciones_vacio(self):
        self.assertEqual(self._llamar(F._calcular_top10_mis_competiciones, ("Liga Colombia",)), [])

    def test_partidos_hoy_vacio(self):
        self.assertEqual(self._llamar(F._calcular_partidos_hoy), [])

    def test_top_picks_vacio_sin_caer_a_terminados(self):
        self.assertEqual(self._llamar(F._calcular_top_picks), [])


if __name__ == "__main__":
    unittest.main()
