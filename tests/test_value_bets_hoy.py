"""/value-bets-hoy (get_value_bets_hoy): filtro de fechas con zona horaria.
cargar_df() devuelve la columna fecha en America/Bogota; antes del fix se
comparaba contra datetime.now() sin zona horaria -> TypeError -> 500 en
cada llamada. CSV, simulacion y cuotas simulados: no llama a ninguna API.
Correr desde backend/: python -m unittest discover -s tests -v"""
import os
import sys
import unittest
from unittest import mock

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app", "services"))
import futbol_service as F

TZ = "America/Bogota"


def partido(local, visitante, fecha, liga="Liga MX", estado="NS"):
    return {"equipo_local": local, "equipo_visitante": visitante, "liga": liga, "estado": estado, "fecha": fecha}


def sim_fijo(*a, **k):
    sim = {"prob_local": 0.60, "prob_empate": 0.25, "prob_visitante": 0.15,
           "goles_ou": {2.5: {"over": 0.60, "under": 0.40}}}
    return sim, {}, {}


class ValueBetsHoy(unittest.TestCase):
    def setUp(self):
        F._VB_CACHE.update(timestamp=0, data=[])
        ahora = pd.Timestamp.now(tz=TZ)
        self.hoy0 = ahora.normalize()
        self.filas = [
            partido("Ayer", "X", self.hoy0 - pd.Timedelta(hours=2)),              # antes de hoy -> fuera
            partido("HoyTemprano", "X", self.hoy0 + pd.Timedelta(minutes=1)),     # hoy 00:01 -> dentro (normalize)
            partido("En3Dias", "X", ahora + pd.Timedelta(days=3)),                # dentro
            partido("Casi7Dias", "X", ahora + pd.Timedelta(days=6, hours=23)),    # dentro
            partido("En8Dias", "X", ahora + pd.Timedelta(days=8)),                # fuera
            partido("LigaSinCuotas", "X", ahora + pd.Timedelta(days=1), liga="Copa Chile"),  # fuera por liga
        ]
        self.consultados = []

    def correr(self, cuotas):
        df = pd.DataFrame(self.filas)
        df["fecha"] = pd.to_datetime(df["fecha"]).dt.tz_convert(TZ)   # mismo tipo que cargar_df()
        def espia(local, visitante, liga):
            self.consultados.append(local)
            return cuotas
        with mock.patch.object(F, "cargar_df", lambda: df), mock.patch.object(F, "simular", sim_fijo), \
             mock.patch.object(F, "get_cuotas_partido", espia):
            return F.get_value_bets_hoy()

    def test_fechas_con_zona_horaria_no_rompen(self):
        # El caso que daba 500: la columna fecha viene con zona horaria.
        self.assertIsInstance(self.correr([]), list)

    def test_ventana_hoy_a_7_dias(self):
        self.correr([])
        self.assertEqual(sorted(self.consultados), ["Casi7Dias", "En3Dias", "HoyTemprano"])

    def test_sin_cuotas_devuelve_lista_vacia(self):
        self.assertEqual(self.correr([]), [])

    def test_detecta_value_bet(self):
        # local 60% del modelo vs cuota 2.20 (45.5% implicito) -> valor 14.5 >= 5
        cuotas = [{"casa": "Casa", "local": 2.20, "empate": 3.1, "visitante": 5.5, "totals": {}}]
        r = self.correr(cuotas)
        self.assertTrue(r)
        self.assertEqual({x["local"] for x in r}, {"HoyTemprano", "En3Dias", "Casi7Dias"})
        for x in r:
            self.assertEqual((x["mercado"], x["casa"]), (f"{x['local']} gana", "Casa"))


if __name__ == "__main__":
    unittest.main()
