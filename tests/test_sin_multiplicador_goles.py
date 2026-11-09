"""Los goles esperados no dependen de la intensidad ofensiva (multiplicador de
goles sacado, PREREGISTRO_multiplicador_goles.md); los corners si.
Correr desde backend/: python -m unittest discover -s tests -v"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app", "services"))
import futbol_service as F
import modelo_presion as MP


def medias(df, local, visitante, intensidad):
    capturado = {}
    real = F.simular_partido_futbol

    def espia(goles_a, goles_b, std_a, std_b, corners_a, corners_b, *a, **k):
        capturado.update(goles=(goles_a, goles_b), corners=(corners_a, corners_b))
        return real(goles_a, goles_b, std_a, std_b, corners_a, corners_b, *a, **k)

    F._cache_resultados.clear()
    with mock.patch.object(MP, "calcular_indice_intensidad_ofensiva", return_value=(intensidad, True)), \
            mock.patch.object(F, "simular_partido_futbol", side_effect=espia):
        sim, _, _ = F.simular(df, local, visitante)
    capturado["corners_proj"] = sim["corners_totales_proj"]
    return capturado


class SinMultiplicadorGoles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df = F.cargar_df()
        if cls.df.empty:
            raise unittest.SkipTest("sin CSV de partidos")
        jugados = cls.df[cls.df["estado"] == "FT"].sort_values("fecha")
        fila = jugados.iloc[-1]
        cls.local, cls.visitante = fila["equipo_local"], fila["equipo_visitante"]

    def test_goles_iguales_con_intensidad_baja_y_alta(self):
        baja = medias(self.df, self.local, self.visitante, 0.0)
        alta = medias(self.df, self.local, self.visitante, 1.0)
        self.assertEqual(baja["goles"], alta["goles"])
        # control: la intensidad mockeada si llega al modelo (corners la sigue usando)
        self.assertNotEqual(baja["corners_proj"], alta["corners_proj"])


if __name__ == "__main__":
    unittest.main()
