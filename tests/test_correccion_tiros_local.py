"""Correccion de tiros del local (PREREGISTRO_tiros_localia.md, 17/11/2026)."""
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app", "services"))
import futbol_service as F  # noqa: E402
import simulator as S  # noqa: E402


class CorreccionTirosLocal(unittest.TestCase):
    def test_valores_del_preregistro(self):
        self.assertEqual(F.CORRECCION_LOCAL_TIROS_ARCO, 0.19)
        self.assertEqual(F.CORRECCION_LOCAL_TIROS_TOTAL, 0.58)

    def _sim(self, arco_a, total_a, azar_arco=None, azar_total=None):
        np.random.seed(123)
        return S.simular_partido_futbol(
            1.4, 1.1, 1.0, 1.0, 5.0, 4.0, 4.0, arco_a, 4.0, total_a, 11.5,
            k_corners_a=10, k_corners_b=10, k_tarjetas=10,
            k_tiros_arco_a=10, k_tiros_arco_b=10, k_tiros_total_a=10, k_tiros_total_b=10,
            media_tiros_arco_a_azar=azar_arco, media_tiros_total_a_azar=azar_total)

    def test_visitante_igual_con_y_sin_correccion(self):
        base = self._sim(4.5, 13.0)
        corr = self._sim(4.69, 13.58, azar_arco=4.5, azar_total=13.0)
        for k in ("tiros_arco_visitante_proj", "tiros_total_visitante_proj",
                  "tiros_arco_ou_visitante", "tiros_total_ou_visitante", "corners_ou", "goles_ou"):
            self.assertEqual(base.get(k), corr.get(k), k)
        self.assertGreater(corr["tiros_total_local_proj"], base["tiros_total_local_proj"])
        self.assertGreater(corr["tiros_arco_local_proj"], base["tiros_arco_local_proj"])

    def test_sin_azar_aparte_es_lo_de_siempre(self):
        self.assertEqual(self._sim(4.5, 13.0), self._sim(4.5, 13.0, azar_arco=4.5, azar_total=13.0))


if __name__ == "__main__":
    unittest.main()
