"""promedio_liga (O/U 2.5 y ambos marcan de la liga, ultimos 365 dias, goles a
90') y la linea del chat para los mercados sin pronostico.
Correr desde backend/: python -m unittest discover -s tests -v"""
import os
import sys
import unittest

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app", "services"))
import futbol_service as F

AHORA = pd.Timestamp("2026-11-07 12:00", tz="UTC")


def partidos(n, liga="Liga Prueba", gl=2, gv=1, estado="FT", dias_atras=10, g90=None, corners=(6, 5)):
    fechas = [AHORA - pd.Timedelta(days=dias_atras, hours=i) for i in range(n)]
    d = pd.DataFrame({"fixture_id": range(n), "fecha": fechas, "liga": liga, "estado": estado,
                      "equipo_local": "A", "equipo_visitante": "B",
                      "goles_local": float(gl), "goles_visitante": float(gv),
                      "goles_90_local": float("nan"), "goles_90_visitante": float("nan"),
                      "corners_local": float(corners[0]), "corners_visitante": float(corners[1])})
    if g90 is not None:
        d["goles_90_local"], d["goles_90_visitante"] = float(g90[0]), float(g90[1])
    return d


class PromedioLiga(unittest.TestCase):
    def test_tasas_y_redondeo(self):
        df = pd.concat([partidos(30, gl=2, gv=1), partidos(30, gl=1, gv=0)], ignore_index=True)
        p = F.promedio_liga_goles(df, "Liga Prueba", ahora=AHORA)
        self.assertEqual((p["over25"], p["under25"], p["ambos_si"], p["ambos_no"]), (50.0, 50.0, 50.0, 50.0))
        self.assertEqual((p["n_partidos"], p["dias"], p["liga"]), (60, 365, "Liga Prueba"))

    def test_menos_de_50_partidos_es_null(self):
        self.assertIsNone(F.promedio_liga_goles(partidos(49), "Liga Prueba", ahora=AHORA))
        self.assertIsNotNone(F.promedio_liga_goles(partidos(50), "Liga Prueba", ahora=AHORA))

    def test_fuera_de_la_ventana_y_futuro_no_cuentan(self):
        df = pd.concat([partidos(50), partidos(40, dias_atras=400), partidos(40, dias_atras=-3)], ignore_index=True)
        self.assertEqual(F.promedio_liga_goles(df, "Liga Prueba", ahora=AHORA)["n_partidos"], 50)

    def test_copas_internacionales_y_amistosos_son_null(self):
        for liga in ("Copa del Rey", "FA Cup", "DFB Pokal", "Champions League", "Club Friendlies", "Supercopa"):
            with self.subTest(liga=liga):
                self.assertIsNone(F.promedio_liga_goles(partidos(200, liga=liga), liga, ahora=AHORA))
        self.assertIsNone(F.promedio_liga_goles(partidos(200), None, ahora=AHORA))

    def test_goles_a_90(self):
        # AET sin goles a 90': no cuenta (los goles finales traen la prorroga)
        df = pd.concat([partidos(50, gl=0, gv=0), partidos(10, gl=3, gv=2, estado="AET")], ignore_index=True)
        p = F.promedio_liga_goles(df, "Liga Prueba", ahora=AHORA)
        self.assertEqual((p["n_partidos"], p["over25"]), (50, 0.0))
        # con goles_90_*: se usan esos (3-2 final, 1-1 a 90')
        df = partidos(50, gl=3, gv=2, estado="AET", g90=(1, 1))
        p = F.promedio_liga_goles(df, "Liga Prueba", ahora=AHORA)
        self.assertEqual((p["over25"], p["ambos_si"]), (0.0, 100.0))

    def test_liga_del_partido_solo_si_hay_ns(self):
        df = partidos(3)
        df.loc[0, "estado"] = "NS"
        self.assertEqual(F._liga_del_partido(df, 0), "Liga Prueba")
        self.assertIsNone(F._liga_del_partido(df, 1))
        self.assertIsNone(F._liga_del_partido(df, None))


class PromedioLigaCorners(unittest.TestCase):
    def test_over_under_95_con_stats(self):
        df = pd.concat([partidos(30, corners=(6, 5)), partidos(30, corners=(4, 4))], ignore_index=True)
        c = F.promedio_liga_goles(df, "Liga Prueba", ahora=AHORA)["corners"]
        self.assertEqual((c["over95"], c["under95"], c["n_partidos"]), (50.0, 50.0, 60))

    def test_sin_stats_no_cuentan_y_menos_de_50_es_null(self):
        # corners 0-0 o vacios = sin stats (misma regla que el backtest)
        df = pd.concat([partidos(49, corners=(6, 5)), partidos(30, corners=(0, 0))], ignore_index=True)
        p = F.promedio_liga_goles(df, "Liga Prueba", ahora=AHORA)
        self.assertEqual(p["n_partidos"], 79)
        self.assertIsNone(p["corners"])
        df = pd.concat([partidos(50, corners=(6, 5)), partidos(30, corners=(float("nan"), float("nan")))], ignore_index=True)
        self.assertEqual(F.promedio_liga_goles(df, "Liga Prueba", ahora=AHORA)["corners"]["n_partidos"], 50)

    def test_corners_ocultos_en_la_app(self):
        self.assertIn("corners_ou", F.MERCADOS_OCULTOS)
        self.assertIn("corners", F.SECCIONES_OCULTAS)
        self.assertIn("corners", F.ANALISIS_OCULTOS)
        for clave in ("corners_proj", "corners_ou", "corners_ou_local", "corners_ou_visitante",
                      "corners_local_proj", "corners_visitante_proj"):
            self.assertIn(clave, F.CLAVES_OCULTAS_PARTIDO)
        self.assertIn("Over/Under de corners", F._chat_linea_sin_pronostico())


class ChatSinPronostico(unittest.TestCase):
    def test_linea_fija_con_los_mercados_ocultos(self):
        system = F._chat_system("CTX", hoy="2026-11-07")
        self.assertIn("MERCADOS SIN PRONOSTICO PARA ESTE PARTIDO: ", system)
        for seccion in F.SECCIONES_OCULTAS:
            self.assertIn(F._CHAT_NOMBRES_OCULTOS[seccion], system)
        self.assertIn("Esta regla 9 NO se aplica a los mercados de la linea MERCADOS SIN PRONOSTICO", system)
        self.assertIn("o si te preguntan por un mercado de la linea MERCADOS SIN PRONOSTICO", system)
        # va en la parte fija (antes del contexto), para no romper la cache de xAI
        self.assertLess(system.index("MERCADOS SIN PRONOSTICO PARA"), system.index("FECHA DE HOY"))

    def test_sin_ocultos_no_hay_linea(self):
        original = F.SECCIONES_OCULTAS
        try:
            F.SECCIONES_OCULTAS = ()
            self.assertEqual(F._chat_linea_sin_pronostico(), "")
        finally:
            F.SECCIONES_OCULTAS = original

    def test_promedio_liga_no_entra_al_chat(self):
        self.assertNotIn("promedio", F._chat_linea_sin_pronostico().lower())


if __name__ == "__main__":
    unittest.main()
