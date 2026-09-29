"""Nota de Top Picks: campo "siguiente" de calcular_top3() (mejor candidato
que quedo afuera y margen) y nota por pick (proyeccion + bullet del
analisis + margen, omitido bajo MARGEN_MINIMO_NOTA).
Correr desde backend/: python -m unittest discover -s tests -v"""
import copy
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app", "services"))
import analisis_mercados as A
import futbol_service as F
from test_analisis_mercados import equipo, hechos, numeros_permitidos, respuesta


def ou2(over):
    return {"over": over, "under": round(1 - over, 4)}


def sim_base(**cambios):
    """sim minimo para calcular_top3() con stats (corners/tarjetas), sin
    tiros/atajadas ni candidatos por equipo. Ver cada test para el orden."""
    sim = {
        "prob_local": 0.45, "prob_empate": 0.34, "prob_visitante": 0.21,
        "prob_1x": 0.79, "prob_x2": 0.55, "prob_ambos_marcan": 0.68,
        "goles_ou": {1.5: ou2(0.88), 2.5: ou2(0.60), 3.5: ou2(0.35)},
        "corners_ou": {7.5: ou2(0.84), 8.5: ou2(0.70)},
        "tarjetas_ou": {2.5: ou2(0.74), 3.5: ou2(0.50)},
    }
    sim.update(cambios)
    return sim


STATS = {"n_partidos_stats": 5}


class Siguiente(unittest.TestCase):
    def test_margen_sobre_el_mejor_que_quedo_afuera(self):
        # #1 Over 1.5 goles 88, #2 Over 7.5 corners 84, #3 Over 2.5 tarjetas 74 (franja).
        # Afuera: 1X 79 (mejor para #1/#2); en la franja 65-78, Ambos marcan 68
        # (Over 8.5 corners 70 y Under 3.5 goles 65 repiten la apuesta de un pick).
        top = F.calcular_top3(sim_base(), None, STATS, STATS)
        self.assertEqual([p["mercado"] for p in top], ["Over 1.5 goles", "Over 7.5 corners", "Over 2.5 tarjetas"])
        s1, s2, s3 = (p["siguiente"] for p in top)
        self.assertEqual((s1["mercado"], s1["prob"], s1["margen"], s1["franja"]), ("1X (Local o Empate)", 79.0, 9.0, None))
        self.assertEqual((s2["mercado"], s2["margen"]), ("1X (Local o Empate)", 5.0))
        self.assertEqual((s3["mercado"], s3["prob"], s3["margen"], s3["franja"]), ("Ambos marcan", 68.0, 6.0, [65.0, 78.0]))

    def test_sin_candidato_afuera(self):
        # Sin stats: solo goles/1X2. Todo lo que queda >= 60% repite la apuesta de un pick.
        sim = sim_base(prob_x2=0.45, prob_ambos_marcan=0.50)
        top = F.calcular_top3(sim, None)
        self.assertEqual([p["mercado"] for p in top], ["Over 1.5 goles", "1X (Local o Empate)"])
        self.assertEqual([p["siguiente"] for p in top], [None, None])

    def test_pick3_por_fallback_compite_como_1_y_2(self):
        # Nada en 65-78 -> el #3 es el 3er mas probable (Over 2.5 tarjetas 81)
        sim = sim_base(tarjetas_ou={2.5: ou2(0.81), 3.5: ou2(0.50)}, prob_ambos_marcan=0.62,
                       corners_ou={7.5: ou2(0.84), 8.5: ou2(0.80)}, goles_ou={1.5: ou2(0.88), 2.5: ou2(0.60), 3.5: ou2(0.35)})
        top = F.calcular_top3(sim, None, STATS, STATS)
        self.assertEqual(top[2]["mercado"], "Over 2.5 tarjetas")
        s3 = top[2]["siguiente"]
        self.assertIsNone(s3["franja"])
        self.assertEqual((s3["mercado"], s3["margen"]), ("1X (Local o Empate)", 2.0))

    def test_margen_sobre_valores_redondeados(self):
        # 84.44 se muestra 84.4 y 78.56 se muestra 78.6: el margen es el de lo que
        # se ve (5.8), no el de los valores crudos (5.88 -> 5.9)
        sim = sim_base(corners_ou={7.5: ou2(0.8444), 8.5: ou2(0.70)}, prob_1x=0.7856)
        top = F.calcular_top3(sim, None, STATS, STATS)
        self.assertEqual((top[1]["prob"], top[1]["siguiente"]["prob"], top[1]["siguiente"]["margen"]), (84.4, 78.6, 5.8))

    def test_no_cambia_los_picks(self):
        sim = sim_base()
        top = F.calcular_top3(sim, None, STATS, STATS)
        self.assertEqual([set(p) for p in top], [{"mercado", "prob", "cuota", "fuente_real", "siguiente"}] * 3)


def partido(top3, pocos=False, **cambios_r):
    r = respuesta(**cambios_r)
    r.update({"corners_local_proj": 5.31, "corners_visitante_proj": 4.31, "tarjetas_local_proj": 2.46,
              "tarjetas_visitante_proj": 0.0, "atajadas_proj": 5.7})
    h = hechos(local=equipo(n_total=1, pocos=True)) if pocos else hechos()
    r["analisis_ia"] = A.armar_analisis_ia(r, h, "k")
    r["top3"] = copy.deepcopy(top3)
    A.armar_notas_top3(r, h)
    return r, h


def sig(mercado, prob, margen, franja=None):
    return {"mercado": mercado, "prob": prob, "margen": margen, "franja": franja}


class Nota(unittest.TestCase):
    def test_margen_grande(self):
        r, _ = partido([{"mercado": "Over 2.5 tarjetas", "prob": 91.3, "siguiente": sig("Under 5.5 corners (Union La Calera)", 76.7, 14.6)}])
        nota = r["top3"][0]["nota"]
        self.assertTrue(nota.startswith("El modelo proyecta 5.29 tarjetas, por encima de la línea de 2.5. "), nota)
        self.assertIn(r["analisis_ia"]["tarjetas"]["bullets"][0], nota)
        self.assertTrue(nota.endswith("Le sacó 14.6 puntos al mejor candidato que quedó afuera "
                                      "(Under 5.5 corners (Union La Calera), 76.7%)."), nota)

    def test_margen_chico_se_omite_y_el_borde_se_muestra(self):
        r, _ = partido([{"mercado": "Over 1.5 goles", "prob": 82.9, "siguiente": sig("Ambos marcan", 81.0, 1.9)},
                        {"mercado": "Over 7.5 corners", "prob": 80.0, "siguiente": sig("Ambos marcan", 78.0, 2.0)}])
        self.assertNotIn("sacó", r["top3"][0]["nota"])
        self.assertIn("Le sacó 2.0 puntos", r["top3"][1]["nota"])

    def test_pick3_en_franja(self):
        top = [{"mercado": "Over 1.5 goles", "prob": 88.0, "siguiente": sig("1X (Local o Empate)", 79.0, 9.0)},
               {"mercado": "Over 7.5 corners", "prob": 84.0, "siguiente": sig("1X (Local o Empate)", 79.0, 5.0)},
               {"mercado": "Over 6.5 tiros al arco", "prob": 77.4, "siguiente": sig("Over 0.5 goles (U. Catolica)", 75.1, 2.3, [65.0, 78.0])}]
        nota = partido(top)[0]["top3"][2]["nota"]
        self.assertTrue(nota.endswith("Es el pick de riesgo moderado: dentro de la franja 65–78% le sacó 2.3 puntos "
                                      "al siguiente (Over 0.5 goles (U. Catolica), 75.1%)."), nota)
        # con margen chico, el #3 se queda sin la frase
        top[2]["siguiente"]["margen"] = 1.2
        self.assertNotIn("riesgo moderado", partido(top)[0]["top3"][2]["nota"])

    def test_sin_candidato_afuera(self):
        r, _ = partido([{"mercado": "Under 3.5 goles", "prob": 83.8, "siguiente": None}], gl=0.91, gv=1.14)
        nota = r["top3"][0]["nota"]
        self.assertTrue(nota.startswith("El modelo proyecta 2.05 goles, por debajo de la línea de 3.5."), nota)
        self.assertNotIn("sacó", nota)

    def test_sin_analisis_usa_la_proyeccion_del_equipo(self):
        top = [{"mercado": "Over 4.5 corners (Union La Calera)", "prob": 80.0, "siguiente": None},
               {"mercado": "Under 1.5 goles (U. Catolica)", "prob": 75.8, "siguiente": sig("Ambos marcan", 75.0, 0.8)},
               {"mercado": "Over 4.5 atajadas", "prob": 88.9, "siguiente": None}]
        r, _ = partido(top)
        self.assertEqual([p["nota"] for p in r["top3"]], [
            "El modelo proyecta 5.31 corners de Union La Calera, por encima de la línea de 4.5.",
            "El modelo proyecta 1.50 goles de U. Catolica, justo en la línea de 1.5.",
            "El modelo proyecta 5.70 atajadas, por encima de la línea de 4.5.",
        ])

    def test_sin_nada_que_decir_es_none(self):
        # tarjetas del visitante sin dato (0.0 de _safe) y margen chico
        r, _ = partido([{"mercado": "Over 1.5 tarjetas (U. Catolica)", "prob": 70.0, "siguiente": sig("Ambos marcan", 69.0, 1.0)}])
        self.assertIsNone(r["top3"][0]["nota"])

    def test_atajadas_de_un_equipo_usa_el_analisis_del_arquero(self):
        r, _ = partido([{"mercado": "Over 1.5 atajadas (Union La Calera)", "prob": 77.9, "siguiente": None}])
        self.assertEqual(r["top3"][0]["nota"], "El modelo proyecta 3.30 atajadas de Union La Calera, por encima de la "
                         "línea de 1.5. " + r["analisis_ia"]["atajadas_local"]["bullets"][0])

    def test_goles_no_repite_la_proyeccion_por_equipo(self):
        r, _ = partido([{"mercado": "Over 1.5 goles", "prob": 82.9, "siguiente": None}])
        self.assertNotIn(A.B_PROYECCION_POR_EQUIPO, r["top3"][0]["nota"])
        self.assertIn("Union La Calera promedia 1.5 goles a favor", r["top3"][0]["nota"])

    def test_pocos_datos_avisa(self):
        r, _ = partido([{"mercado": "Over 1.5 goles", "prob": 82.9, "siguiente": None}], pocos=True)
        self.assertIn("Ojo: Union La Calera tiene 1 partido", r["top3"][0]["nota"])


class Coherencia(unittest.TestCase):
    def test_ou_nunca_usa_el_resumen_de_otra_linea(self):
        # el analisis de tarjetas habla de la linea 4.5; el pick es 2.5
        r, _ = partido([{"mercado": "Over 2.5 tarjetas", "prob": 91.3, "siguiente": None}])
        self.assertNotIn(r["analisis_ia"]["tarjetas"]["resumen"], r["top3"][0]["nota"])
        self.assertNotIn("4.5", r["top3"][0]["nota"])

    def test_doble_oportunidad_coherente_usa_el_resumen(self):
        r, _ = partido([{"mercado": "1X (Local o Empate)", "prob": 80.0, "siguiente": None}], pl=55.0, pe=25.0, pv=20.0)
        a = r["analisis_ia"]["doble_oportunidad"]
        self.assertEqual(r["top3"][0]["nota"], f"{a['resumen']} {a['bullets'][0]}")

    def test_doble_oportunidad_de_la_otra_opcion_no_la_usa(self):
        # el analisis habla de 1X (80%); el pick es X2 (45%): el dato es la forma del LOCAL
        r, _ = partido([{"mercado": "X2 (Empate o Visitante)", "prob": 45.0, "siguiente": None}], pl=55.0, pe=25.0, pv=20.0)
        self.assertEqual(r["top3"][0]["nota"], "Union La Calera ganó 2 de sus últimos 5 partidos.")

    def test_1x2_con_ajuste_ia_no_usa_el_resumen(self):
        # r trae 60.0 (con ajuste IA) y el pick 64.2 (modelo puro): el resumen citaria otro numero
        r, _ = partido([{"mercado": "Gana local", "prob": 64.2, "siguiente": None}], pl=60.0, pe=22.0, pv=18.0)
        self.assertNotIn(r["analisis_ia"]["1x2"]["resumen"], r["top3"][0]["nota"])
        r, _ = partido([{"mercado": "Gana local", "prob": 60.0, "siguiente": None}], pl=60.0, pe=22.0, pv=18.0)
        self.assertTrue(r["top3"][0]["nota"].startswith(r["analisis_ia"]["1x2"]["resumen"]))

    def test_ambos_marcan(self):
        r, _ = partido([{"mercado": "Ambos marcan", "prob": 62.0, "siguiente": None}], btts=62.0)
        self.assertTrue(r["top3"][0]["nota"].startswith(r["analisis_ia"]["ambos_marcan"]["resumen"]))


class SinInventar(unittest.TestCase):
    def test_cada_numero_de_la_nota_sale_de_los_datos(self):
        rnd = random.Random(11)
        nombres = (["Over 1.5 goles", "Under 3.5 goles", "Over 7.5 corners", "Over 2.5 tarjetas", "Under 4.5 tarjetas",
                    "Over 6.5 tiros al arco", "Under 23.5 tiros totales", "Over 4.5 atajadas", "Ambos marcan",
                    "1X (Local o Empate)", "X2 (Empate o Visitante)", "Gana local", "Gana visitante"]
                   + [f"{s} {l} {m} ({eq})" for s in ("Over", "Under") for l in ("0.5", "1.5", "4.5")
                      for m in ("goles", "corners", "tarjetas", "atajadas") for eq in ("Union La Calera", "U. Catolica")])
        for i in range(300):
            pl, pv = rnd.uniform(10, 70), rnd.uniform(10, 70)
            pe = rnd.uniform(10, 35)
            tot = pl + pe + pv
            pl, pe, pv = (round(100 * x / tot, 1) for x in (pl, pe, pv))
            top = []
            for n in range(3):
                prob = round(rnd.uniform(60, 92), 1)
                s = None if rnd.random() < 0.3 else sig(rnd.choice(nombres), round(prob - rnd.uniform(0, 12), 1), 0.0,
                                                          [65.0, 78.0] if n == 2 and rnd.random() < 0.5 else None)
                if s:
                    s["margen"] = round(prob - s["prob"], 1)
                top.append({"mercado": rnd.choice(nombres), "prob": prob, "siguiente": s})
            r, h = partido(top, pl=pl, pe=pe, pv=pv, btts=round(rnd.uniform(20, 80), 1),
                           gl=round(rnd.uniform(0.3, 2.8), 2), gv=round(rnd.uniform(0.3, 2.8), 2))
            base = numeros_permitidos(r, h)
            for p in r["top3"]:
                if p["nota"] is None:
                    continue
                permitidos = base | set(A.NUMERO.findall(p["mercado"]))
                s = p["siguiente"]
                if s:
                    permitidos |= {A._f(s["margen"]), A._f(s["prob"]), "65", "78"} | set(A.NUMERO.findall(s["mercado"]))
                for num in A.NUMERO.findall(p["nota"]):
                    self.assertIn(num, permitidos, f"{num!r} no sale de los datos -> {p}")
                for malo in ("{", "}", "None", "nan", "  ", "..", " de el ", " a el "):
                    self.assertNotIn(malo, p["nota"])

    def test_un_pick_roto_no_rompe_los_demas(self):
        top = [{"mercado": "Over 1.5 goles", "prob": 82.9, "siguiente": {"margen": 5.0}},  # siguiente mal formado
               {"mercado": "Over 7.5 corners", "prob": 80.0, "siguiente": None}]
        r, _ = partido(top)
        self.assertIsNone(r["top3"][0]["nota"])
        self.assertTrue(r["top3"][1]["nota"].startswith("El modelo proyecta 9.62 corners"))


if __name__ == "__main__":
    unittest.main()
