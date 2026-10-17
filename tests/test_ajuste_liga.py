"""Ajuste de fuerza de liga (plan A+B del 16/10/2026): los factores entre
las ligas que ya estaban en la tabla no cambian, y la red de seguridad (B)
solo actua sobre el equipo sin liga de referencia."""
import itertools
import os
import sys

import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app", "services"))

import liga_ranking as LR  # noqa: E402

# Copia literal de NIVEL_LIGA_CLUBES y de ajuste_liga_clubes() antes del
# cambio, para comparar par por par.
NIVEL_ANTES = {
    "Premier League": 100, "La Liga": 95, "Bundesliga": 90, "Serie A": 88,
    "Ligue 1": 82, "Brasileirao": 75, "Primeira Liga": 72,
    "Liga Profesional Argentina": 68, "Eredivisie": 68, "Super Lig Turquia": 65,
    "Liga MX": 62, "Pro League Belgica": 62, "Pro League Arabia": 60, "MLS": 58,
    "Liga Colombia": 50, "Primera Division Chile": 50,
    "Primera Division Uruguay": 48, "Primera Division Peru": 45,
    "Liga Pro Ecuador": 45, "Division Profesional Paraguay": 42,
    "Premier League Egipto": 40, "Primera Division Bolivia": 38,
    "Primera Division Venezuela": 35,
    "Championship": 55, "Serie B Brasil": 55, "2. Bundesliga": 52,
    "Serie B Italia": 50, "Segunda Division Espana": 50, "Ligue 2": 48,
    "Eerste Divisie": 42, "3. Liga": 35, "Primera B Colombia": 30,
    "Primera B Metropolitana": 25, "Second League Egipto": 20,
}


def _ajuste_antes(liga_a, liga_b):
    if not liga_a or not liga_b or liga_a == liga_b:
        return 1.0, 1.0
    score_a = NIVEL_ANTES.get(liga_a)
    score_b = NIVEL_ANTES.get(liga_b)
    if score_a is None or score_b is None:
        return 1.0, 1.0
    diff = max(-1.0, min(1.0, (score_a - score_b) / 60.0))
    return round(1.0 + diff * 0.30, 3), round(1.0 - diff * 0.30, 3)


class AjusteLigaTest(unittest.TestCase):
    def test_tabla_editorial_intacta(self):
        self.assertEqual(LR.NIVEL_LIGA_CLUBES, NIVEL_ANTES)


    def test_mismos_factores_entre_ligas_existentes(self):
        pares = list(itertools.product(sorted(NIVEL_ANTES), repeat=2))
        self.assertEqual(len(pares), 34 * 34)
        for liga_a, liga_b in pares:
            with self.subTest(liga_a=liga_a, liga_b=liga_b):
                self.assertEqual(LR.ajuste_liga_clubes(liga_a, liga_b), _ajuste_antes(liga_a, liga_b))


    def test_ligas_nuevas_no_pisan_la_tabla(self):
        self.assertFalse(set(LR.NIVEL_LIGA_UEFA) & set(NIVEL_ANTES))
        self.assertFalse(set(LR.NIVEL_LIGA_SIN_VALIDAR) & set(NIVEL_ANTES))
        self.assertEqual(len(LR.NIVEL_LIGA_UEFA), 31)


    def test_niveles_ancla_iguales_a_la_tabla(self):
        for pais, liga in (("England", "Premier League"), ("Spain", "La Liga"), ("Germany", "Bundesliga"),
                           ("Italy", "Serie A"), ("France", "Ligue 1"), ("Portugal", "Primeira Liga"),
                           ("Netherlands", "Eredivisie"), ("Turkey", "Super Lig Turquia"),
                           ("Belgium", "Pro League Belgica")):
            self.assertEqual(LR.NIVEL_PAIS_UEFA[pais], NIVEL_ANTES[liga])


    def test_curva_monotona_en_el_coeficiente(self):
        # El dict esta ordenado por coeficiente descendente; fuera de las 9
        # anclas, el nivel no puede subir al bajar el coeficiente.
        anclas = {"England", "Spain", "Germany", "Italy", "France", "Portugal", "Netherlands", "Turkey", "Belgium"}
        resto = [n for p, n in LR.NIVEL_PAIS_UEFA.items() if p not in anclas]
        self.assertEqual(resto, sorted(resto, reverse=True))


    def test_ekstraklasa_ahora_tiene_ajuste(self):
        fa, fb = LR.ajuste_liga_clubes("Ekstraklasa Poland", "Bundesliga")
        self.assertTrue(fa < 1.0 < fb)


    def test_con_referencia_no_cambia_nada(self):
        self.assertEqual(LR.niveles_referencia("Premier League", "Championship", "A", "B", "FA Cup"), (100, 55))


    def test_ambos_sin_referencia_neutro(self):
        self.assertEqual(LR.niveles_referencia(None, None, "Qarabag", "Shamrock Rovers", "Champions League"), (None, None))


    def test_copa_internacional_usa_el_pais(self):
        self.enterContext(mock.patch.object(LR, "_pais_equipos", {"Shamrock Rovers": "Ireland"}))
        na, nb = LR.niveles_referencia("Premier League", None, "Chelsea", "Shamrock Rovers", "Conference League")
        self.assertEqual((na, nb), (100, LR.NIVEL_PAIS_UEFA["Ireland"]))


    def test_copa_internacional_sin_pais_usa_default(self):
        self.enterContext(mock.patch.object(LR, "_pais_equipos", {}))
        _, nb = LR.niveles_referencia("Premier League", None, "Chelsea", "Saburtalo", "Champions League")
        self.assertEqual(nb, LR.NIVEL_DEFAULT_CONFEDERACION["UEFA"])
        _, nb = LR.niveles_referencia("Brasileirao", None, "Flamengo", "X", "Copa Libertadores")
        self.assertEqual(nb, LR.NIVEL_DEFAULT_CONFEDERACION["CONMEBOL"])


    def test_partido_domestico_usa_la_liga_del_partido(self):
        # San Telmo sin referencia, en la Primera Nacional contra Defensores de
        # Belgrano (referencia Primera B Metro): queda arriba del de tercera.
        na, nb = LR.niveles_referencia(None, "Primera B Metropolitana", "San Telmo", "Defensores de Belgrano",
                                       "Primera Nacional Argentina")
        self.assertEqual((na, nb), (35, 25))


    def test_copa_domestica_sin_nivel_queda_neutra(self):
        self.assertEqual(LR.niveles_referencia("Primeira Liga", None, "Benfica", "Amarante", "Taça de Portugal"), (72, None))
        self.assertEqual(LR.ajuste_por_nivel(72, None), (1.0, 1.0))


    def test_interruptores_apagados_igual_que_antes(self):
        self.enterContext(mock.patch.object(LR, "USAR_NIVELES_A", False))
        self.enterContext(mock.patch.object(LR, "USAR_RED_B", False))
        self.assertEqual(LR.ajuste_liga_clubes("Ekstraklasa Poland", "Bundesliga"), (1.0, 1.0))
        self.assertEqual(LR.niveles_referencia("Bundesliga", None, "A", "B", "Champions League"), (90, None))
        self.assertEqual(LR.ligas_con_nivel_extra(), [])


if __name__ == "__main__":
    unittest.main()
