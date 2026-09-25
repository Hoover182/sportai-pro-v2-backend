"""Arqueros sin historial de atajadas (< 3 partidos con el dato en sus
ultimos 10): atajadas = eficiencia general x tiros al arco del rival.
Usa el CSV real del repo para las estadisticas de equipos reales.
Correr desde backend/: python -m unittest discover -s tests -v"""
import copy
import os
import sys
import unittest

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app", "services"))
import football_model as FM
import futbol_service as F


def df_chico(filas):
    cols = ["estado", "atajadas_local", "atajadas_visitante", "tiros_arco_local", "tiros_arco_visitante"]
    return pd.DataFrame(filas, columns=cols)


class EficienciaGeneral(unittest.TestCase):
    def setUp(self):
        FM._cache_eficiencia_arqueros.clear()

    def test_atajadas_sobre_tiros_recibidos(self):
        d = df_chico([("FT", 3, 4, 6, 4), ("FT", 2, 2, 3, 3), ("NS", 9, 9, 1, 1)])
        # atajadas 3+4+2+2 = 11 ; tiros al arco recibidos 4+6+3+3 = 16 (NS excluido)
        self.assertAlmostEqual(FM.eficiencia_general_arqueros(d), 11 / 16)

    def test_excluye_relleno_y_faltantes(self):
        d = df_chico([("FT", 3, 4, 6, 4), ("FT", 0, 0, 5, 5), ("FT", np.nan, 2, 3, 3), ("FT", 2, 2, np.nan, 3)])
        self.assertAlmostEqual(FM.eficiencia_general_arqueros(d), 7 / 10)

    def test_respaldo_sin_datos_o_valor_absurdo(self):
        self.assertEqual(FM.eficiencia_general_arqueros(df_chico([("FT", np.nan, np.nan, 3, 3)])), FM.EFICIENCIA_ARQUEROS_RESPALDO)
        self.assertEqual(FM.eficiencia_general_arqueros(df_chico([("FT", 20, 20, 2, 2)])), FM.EFICIENCIA_ARQUEROS_RESPALDO)

    def test_csv_real_en_rango(self):
        self.assertTrue(0.6 <= FM.eficiencia_general_arqueros(F.cargar_df()) <= 0.8)


class Reemplazo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df = F.cargar_df()

    def stats(self, local, visitante):
        liga = FM.obtener_liga_partido(self.df, local, visitante)
        return (FM.estadisticas_equipo_ultimos10(self.df, local, liga=liga, condicion="local"),
                FM.estadisticas_equipo_ultimos10(self.df, visitante, liga=liga, condicion="visitante"))

    def ajustar(self, sa, sb, l, v):
        h2h = FM.ultimos_enfrentamientos_directos(self.df, l, v, n=5)
        return FM.ajustar_medias_con_rival(copy.deepcopy(sa), copy.deepcopy(sb), h2h, l, v)

    def test_n_atajadas_en_stats(self):
        sa, sb = self.stats("ADT", "Cienciano")
        self.assertEqual((sa["n_atajadas"], sb["n_atajadas"]), (9, 9))
        sa, sb = self.stats("Deportes Iquique", "Antofagasta")
        self.assertEqual((sa["n_atajadas"], sb["n_atajadas"]), (1, 0))

    def test_sin_historial_usa_eficiencia_por_tiros_del_rival(self):
        l, v = "Deportes Iquique", "Antofagasta"
        sa, sb = self.stats(l, v)
        r = self.ajustar(sa, sb, l, v)
        tiros_a, tiros_b, at_a, at_b = r[6], r[7], r[10], r[11]
        eff = sa["eficiencia_general_arqueros"]
        self.assertAlmostEqual(at_a, float(np.clip(eff * tiros_b, FM.ATAJADAS_MIN, FM.ATAJADAS_MAX)))
        self.assertAlmostEqual(at_b, float(np.clip(eff * tiros_a, FM.ATAJADAS_MIN, FM.ATAJADAS_MAX)))

    def test_con_historial_no_cambia(self):
        l, v = "ADT", "Cienciano"
        sa, sb = self.stats(l, v)
        con = self.ajustar(sa, sb, l, v)
        sa2, sb2 = copy.deepcopy(sa), copy.deepcopy(sb)
        sa2.pop("n_atajadas"); sb2.pop("n_atajadas")      # sin el conteo = comportamiento anterior
        sin_conteo = self.ajustar(sa2, sb2, l, v)
        self.assertEqual(con, sin_conteo)

    def test_borde_2_y_3_partidos(self):
        l, v = "ADT", "Cienciano"
        sa, sb = self.stats(l, v)
        base = self.ajustar(sa, sb, l, v)
        sa["n_atajadas"] = 3
        self.assertEqual(self.ajustar(sa, sb, l, v)[10], base[10])          # 3 -> tiene historial
        sa["n_atajadas"] = 2
        esperado = float(np.clip(sa["eficiencia_general_arqueros"] * base[7], FM.ATAJADAS_MIN, FM.ATAJADAS_MAX))
        self.assertAlmostEqual(self.ajustar(sa, sb, l, v)[10], esperado)   # 2 -> sin historial

    def test_sin_tiros_del_rival_no_reemplaza(self):
        l, v = "ADT", "Cienciano"
        sa, sb = self.stats(l, v)
        base = self.ajustar(sa, sb, l, v)
        sa["n_atajadas"] = 0
        sb["tiros_arco_favor"] = sb["tiros_arco_contra"] = sa["tiros_arco_favor"] = sa["tiros_arco_contra"] = np.nan
        r = self.ajustar(sa, sb, l, v)
        self.assertTrue(np.isnan(r[7]))                 # sin tiros del rival...
        self.assertEqual(r[10], base[10])               # ...se mantiene el calculo anterior


if __name__ == "__main__":
    unittest.main()
