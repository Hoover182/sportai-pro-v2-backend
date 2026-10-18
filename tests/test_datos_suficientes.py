"""Mercados de stats (corners, tarjetas, tiros, tiros al arco, atajadas)
solo con datos suficientes: al menos 3 partidos con stats en los ultimos 12
meses en cada equipo. Mismo criterio en el detalle, Top3, combinadas y la
calculadora de cuota (tiene_datos_suficientes).
Correr desde backend/: python -m unittest discover -s tests -v"""
import os
import sys
import unittest
from unittest import mock

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app", "services"))
import football_model as FM
import futbol_service as F
from test_nota_top_picks import sim_base

CON = {"n_partidos_stats": 10, "n_partidos_stats_12m": 10}
VIEJOS = {"n_partidos_stats": 10, "n_partidos_stats_12m": 2}   # ej. Uruguay: stats solo de hace mas de un ano
SIN = {"n_partidos_stats": 0, "n_partidos_stats_12m": 0}


def partidos_hace(*dias):
    ahora = pd.Timestamp.now(tz="America/Bogota")
    return pd.DataFrame({"fecha": [ahora - pd.Timedelta(days=d) for d in dias]})


class TieneDatosSuficientes(unittest.TestCase):
    def test_umbral_de_3(self):
        self.assertTrue(FM.tiene_datos_suficientes({"n_partidos_stats_12m": 3}))
        self.assertFalse(FM.tiene_datos_suficientes({"n_partidos_stats_12m": 2}))

    def test_sin_stats_o_sin_campo(self):
        self.assertFalse(FM.tiene_datos_suficientes(None))
        self.assertFalse(FM.tiene_datos_suficientes({}))
        self.assertFalse(FM.tiene_datos_suficientes({"n_partidos_stats": 10}))

    def test_cuenta_solo_los_ultimos_12_meses(self):
        self.assertEqual(FM._n_recientes(partidos_hace(10, 200, 364, 366, 900), 365), 3)
        self.assertEqual(FM._n_recientes(partidos_hace(), 365), 0)


class Top3YCombinadas(unittest.TestCase):
    def _mercados(self, fn, stats_a, stats_b):
        return [p["mercado"] for p in fn(sim_base(), None, stats_a, stats_b)]

    def test_con_datos_entran_los_picks_de_stats(self):
        self.assertIn("Over 7.5 corners", self._mercados(F.calcular_top3, CON, CON))

    def test_un_equipo_con_stats_viejas_saca_los_picks_de_stats(self):
        for stats_a, stats_b in ((CON, VIEJOS), (VIEJOS, CON), (CON, SIN)):
            mercados = self._mercados(F.calcular_top3, stats_a, stats_b)
            self.assertFalse([m for m in mercados if "corners" in m or "tarjetas" in m], mercados)

    def test_combinadas_mismo_criterio(self):
        # Combinadas solo devuelve picks con cuota: se simula una cuota de 1.90
        # para todo mercado, asi el filtro que se prueba es solo el de datos.
        with (
            mock.patch.object(F, "_cargar_cuotas_cache", return_value={"1": {"x": 1}}),
            mock.patch.object(F, "_resolver_cuota_mercado", return_value=(1.90, None)),
        ):
            con = [p["mercado"] for p in F.calcular_picks_combinados(sim_base(), 1, CON, CON)]
            sin = [p["mercado"] for p in F.calcular_picks_combinados(sim_base(), 1, CON, VIEJOS)]
        self.assertTrue([m for m in con if "corners" in m or "tarjetas" in m], con)
        self.assertFalse([m for m in sin if "corners" in m or "tarjetas" in m], sin)


class ClavesAnuladas(unittest.TestCase):
    def test_cubre_los_5_mercados_en_total_y_por_equipo(self):
        for mercado in ("corners", "tarjetas", "tiros_arco", "tiros_total", "atajadas"):
            for sufijo in ("proj", "local_proj", "visitante_proj", "ou", "ou_local", "ou_visitante"):
                self.assertIn(f"{mercado}_{sufijo}", F.CLAVES_MERCADOS_STATS)

    def test_no_toca_goles_ni_1x2(self):
        self.assertFalse([c for c in F.CLAVES_MERCADOS_STATS if c.startswith(("goles", "prob_"))])


if __name__ == "__main__":
    unittest.main()
