"""Nota de Top Picks: campo "siguiente" de calcular_top3() (mejor candidato
que quedo afuera y margen) y nota por pick (que se espera + que paso entre
ellos en ese mercado; atajadas sin cruces, con el peligro del rival).
Correr desde backend/: python -m unittest discover -s tests -v"""
import os
import random
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app", "services"))
import analisis_mercados as A
import futbol_service as F
from test_analisis_mercados import equipo, hechos, respuesta


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


L, V = "Union La Calera", "U. Catolica"   # los de respuesta()


def cruce(dias, local=L, visitante=V, goles=(1, 1), **mercados):
    """Un cruce como los arma _hechos_para_analisis()["h2h_cruces"]."""
    c = {"fecha": "2026-01-01", "dias": dias, "local": local, "visitante": visitante, "goles": list(goles),
         "corners": None, "tarjetas": None, "tiros_arco": None, "tiros_total": None}
    c.update({k: list(v) for k, v in mercados.items()})
    return c


def partido(top3, cruces=(), pocos=False, **cambios_r):
    r = respuesta(**cambios_r)
    r.update({"corners_local_proj": 5.31, "corners_visitante_proj": 4.31, "tarjetas_local_proj": 2.46,
              "tarjetas_visitante_proj": 0.0, "atajadas_proj": 5.7})
    h = hechos(local=equipo(n_total=1, pocos=True)) if pocos else hechos()
    h["h2h_cruces"] = list(cruces)
    r["top3"] = [{"mercado": m, "prob": p, "siguiente": None} for m, p in top3]
    A.armar_notas_top3(r, h)
    return [p["nota"] for p in r["top3"]]


class CasosDeCruces(unittest.TestCase):
    def test_reciente(self):
        cr = [cruce(100 + i, tarjetas=(t - 3, 3)) for i, t in enumerate([7, 4, 8, 7, 10, 2])]
        self.assertEqual(partido([("Over 2.5 tarjetas", 91.3)], cr), [
            "Se esperan 5.3 tarjetas; la línea es 2.5.\n"
            "Entre ellos: más de 2.5 tarjetas en 5 de los últimos 5 cruces (7.2 de promedio)."])

    def test_viejo_dice_la_antiguedad(self):
        cr = [cruce(1200, goles=(2, 2)), cruce(1500, goles=(0, 1))]
        self.assertEqual(partido([("Under 3.5 goles", 78.8)], cr)[0].split("\n")[1],
                         "Entre ellos: menos de 3.5 goles en 1 de los últimos 2 cruces (2.5 de promedio). "
                         "El último fue hace 3 años.")

    def test_borde_de_2_anios(self):
        nota = lambda d: partido([("Under 3.5 goles", 78.8)], [cruce(d), cruce(d + 10)])[0]
        self.assertNotIn("hace", nota(730))
        self.assertIn("El último fue hace 2 años.", nota(731))

    def test_sin_cruces(self):
        self.assertEqual(partido([("Over 2.5 tarjetas", 84.2)], [])[0].split("\n")[1],
                         "No hay cruces oficiales entre ellos en nuestra base.")

    def test_cruces_sin_dato_del_mercado(self):
        cinco = [cruce(100 + i, tarjetas=(2, 2)) for i in range(5)]   # hay tarjetas, no tiros
        self.assertEqual(partido([("Under 7.5 tiros al arco", 91.4)], cinco)[0].split("\n")[1],
                         "Se enfrentaron 5 veces, pero no hay registro de tiros al arco de esos partidos.")
        self.assertEqual(partido([("Under 7.5 tiros al arco", 91.4)], cinco[:1])[0].split("\n")[1],
                         "Se enfrentaron una vez, pero no hay registro de tiros al arco de ese partido.")

    def test_cruce_reciente_sin_dato_aclara_con_registro(self):
        cr = [cruce(50)] + [cruce(100 + i, tarjetas=(3, 3)) for i in range(5)]
        self.assertIn("en 5 de los últimos 5 cruces con registro de tarjetas (6.0 de promedio)",
                      partido([("Over 2.5 tarjetas", 91.3)], cr)[0])

    def test_un_solo_cruce(self):
        self.assertEqual(partido([("Under 3.5 goles", 83.8)], [cruce(40, goles=(2, 1))])[0].split("\n")[1],
                         "Entre ellos: en su único cruce hubo 3 goles.")
        cr = [cruce(40), cruce(80, tarjetas=(4, 3))]
        self.assertEqual(partido([("Over 2.5 tarjetas", 90.0)], cr)[0].split("\n")[1],
                         "Entre ellos: en el único cruce con registro de tarjetas hubo 7.")
        self.assertIn("Fue hace 4 años.", partido([("Under 3.5 goles", 83.8)], [cruce(1500)])[0])

    def test_mercado_de_un_equipo_cuenta_solo_ese_equipo(self):
        # U. Catolica de visitante (3) y de local (0) en los cruces
        cr = [cruce(10, goles=(1, 3)), cruce(20, local=V, visitante=L, goles=(0, 2))]
        self.assertEqual(partido([(f"Over 0.5 goles ({V})", 80.0)], cr)[0], (
            f"Se esperan 1.5 goles de {V}; la línea es 0.5.\n"
            f"Entre ellos: {V} marcó más de 0.5 goles en 1 de los últimos 2 cruces (1.5 de promedio)."))


class Atajadas(unittest.TestCase):
    def test_arquero_sin_cruces_con_peligro_del_rival(self):
        cr = [cruce(10, tiros_arco=(5, 5))]
        self.assertEqual(partido([(f"Over 1.5 atajadas ({L})", 77.8)], cr), [
            f"Se esperan 3.3 atajadas del arquero de {L}; la línea es 1.5.\n"
            f"{V} proyecta 5.1 tiros al arco: ese es el trabajo que le espera."])

    def test_total_de_los_dos_arqueros(self):
        self.assertEqual(partido([("Over 4.5 atajadas", 88.9)], [cruce(10)]), [
            "Se esperan 5.7 atajadas entre los dos arqueros; la línea es 4.5.\n"
            "Entre los dos equipos se proyectan 8.7 tiros al arco."])


class MercadosDeResultado(unittest.TestCase):
    cr = [cruce(10, goles=(2, 0)), cruce(20, local=V, visitante=L, goles=(1, 1)),
          cruce(30, goles=(0, 1)), cruce(40, local=V, visitante=L, goles=(0, 3))]

    def test_doble_oportunidad_desde_el_equipo(self):
        # L gano 2-0, empato 1-1, perdio 0-1, gano 3-0 de visitante -> no perdio en 3 de 4
        self.assertEqual(partido([("1X (Local o Empate)", 80.0)], self.cr), [
            f"El modelo le da 80.0% a que {L} no pierda.\nEntre ellos: {L} no perdió en 3 de los últimos 4 cruces."])

    def test_gana_visitante_y_ambos_marcan(self):
        gana, ambos = partido([("Gana visitante", 61.0), ("Ambos marcan", 62.0)], self.cr)
        self.assertEqual(gana.split("\n")[1], f"Entre ellos: {V} ganó 1 de los últimos 4 cruces.")
        self.assertEqual(ambos, "El modelo le da 62.0% a que marquen los dos.\n"
                                "Entre ellos: marcaron los dos en 1 de los últimos 4 cruces.")

    def test_un_solo_cruce_muestra_el_resultado(self):
        self.assertEqual(partido([("X2 (Empate o Visitante)", 72.3)], [cruce(90, local=V, visitante=L, goles=(2, 1))])[0],
                         f"El modelo le da 72.3% a que {V} no pierda.\nEntre ellos: un solo cruce, {V} 2-1 {L}.")


class Formato(unittest.TestCase):
    def test_proyeccion_igual_a_la_linea_usa_2_decimales(self):
        # 2.46 con 1 decimal seria "2.5", igual a la linea: no diria de que lado cae
        self.assertTrue(partido([(f"Under 2.5 tarjetas ({L})", 60.0)], [])[0].startswith(
            f"Se esperan 2.46 tarjetas de {L}; la línea es 2.5."))
        self.assertTrue(partido([(f"Over 1.5 tarjetas ({L})", 70.0)], [])[0].startswith(
            f"Se esperan 2.5 tarjetas de {L}; la línea es 1.5."))

    def test_sin_proyeccion_queda_solo_lo_que_hay(self):
        # tarjetas del visitante sin dato (0.0 de _safe) y sin cruces
        self.assertEqual(partido([(f"Over 1.5 tarjetas ({V})", 70.0)], []),
                         ["No hay cruces oficiales entre ellos en nuestra base."])

    def test_pocos_datos_agrega_un_aviso(self):
        nota = partido([("Over 1.5 goles", 82.9)], [], pocos=True)[0]
        self.assertEqual(nota.split("\n")[2], f"Ojo: poca historia de {L} en nuestra base.")

    def test_sin_frase_de_margen(self):
        r = respuesta(); h = hechos(); h["h2h_cruces"] = []
        r["top3"] = [{"mercado": "Over 1.5 goles", "prob": 88.0,
                      "siguiente": {"mercado": "1X (Local o Empate)", "prob": 70.0, "margen": 18.0, "franja": None}}]
        A.armar_notas_top3(r, h)
        self.assertNotIn("sacó", r["top3"][0]["nota"])

    def test_un_pick_roto_no_rompe_los_demas(self):
        r = respuesta(); h = hechos(); h["h2h_cruces"] = [{"roto": True}]
        r["top3"] = [{"mercado": "Over 1.5 goles", "prob": 82.9}, {"mercado": f"Over 1.5 atajadas ({L})", "prob": 80.0}]
        A.armar_notas_top3(r, h)
        self.assertIsNone(r["top3"][0]["nota"])
        self.assertTrue(r["top3"][1]["nota"].startswith("Se esperan 3.3 atajadas"))


class SinInventar(unittest.TestCase):
    def test_conteos_y_promedios_recalculados_aparte(self):
        """300 casos al azar: el "X de los ultimos K" y el promedio de la nota
        coinciden con una cuenta independiente sobre los mismos cruces."""
        rnd = random.Random(13)
        mercados = [("goles", "goles"), ("corners", "corners"), ("tarjetas", "tarjetas"),
                    ("tiros_arco", "tiros al arco"), ("tiros_total", "tiros totales")]
        patron = re.compile(r"en (\d+) de los últimos (\d+) cruces[^(]*\((\d+\.\d) de promedio\)")
        for _ in range(300):
            clave, unidad = rnd.choice(mercados)
            sentido, linea = rnd.choice(["Over", "Under"]), rnd.choice([0.5, 1.5, 2.5, 3.5, 7.5, 9.5, 24.5])
            equipo = rnd.choice([None, L, V])
            cr = []
            for i in range(rnd.randint(0, 9)):
                loc, vis = (L, V) if rnd.random() < 0.5 else (V, L)
                dato = None if rnd.random() < 0.3 else (rnd.randint(0, 15), rnd.randint(0, 15))
                c = cruce(rnd.randint(10, 1500), loc, vis, goles=(rnd.randint(0, 4), rnd.randint(0, 4)))
                if clave == "goles":
                    dato = tuple(c["goles"])
                c[clave] = list(dato) if dato else None
                cr.append(c)
            cr.sort(key=lambda c: c["dias"])
            nombre = f"{sentido} {linea} {unidad}" + (f" ({equipo})" if equipo else "")
            nota = partido([(nombre, 75.0)], cr)[0]
            con = [c for c in cr if c[clave] is not None][:A.VENTANA_CRUCES_NOTA]
            vals = [sum(c[clave]) if equipo is None else c[clave][0 if c["local"] == equipo else 1] for c in con]
            if len(vals) >= 2:
                m = patron.search(nota)
                self.assertIsNotNone(m, nota)
                cumple = sum((v > linea) if sentido == "Over" else (v < linea) for v in vals)
                self.assertEqual((int(m.group(1)), int(m.group(2)), m.group(3)),
                                 (cumple, len(vals), f"{sum(vals) / len(vals):.1f}"), nota)
            for malo in ("{", "}", "None", "nan", "  ", "..", " ,"):
                self.assertNotIn(malo, nota)
            for linea_txt in nota.split("\n"):
                self.assertTrue(linea_txt.endswith("."), nota)


if __name__ == "__main__":
    unittest.main()
