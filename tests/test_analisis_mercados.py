"""Analisis IA por mercado (texto por reglas): umbrales, direccion,
semilla fija por (fixture, mercado), tonos con prioridad, y que cada
numero del texto salga de los datos de entrada.
Correr desde backend/: python -m unittest discover -s tests -v"""
import copy
import os
import random
import re
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.services import analisis_mercados as A

CAMPOS = {"tono", "emoji", "titulo", "resumen", "bullets", "disclaimer"}
MERCADOS = ["1x2", "doble_oportunidad", "ambos_marcan", "goles", "corners", "tarjetas", "tiros_arco", "tiros_total",
            "hcp_europeo", "hcp_asiatico", "atajadas_local", "atajadas_visitante"]
LINEAS_ASIATICO = [-3.0, -2.5, -2.0, -1.5, -1.0, -0.5, 0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0]


def ou(proj, lineas):
    """O/U con over decreciente alrededor de la proyeccion (forma realista)."""
    out = {}
    for linea in lineas:
        over = round(max(1.0, min(99.0, 50 + (proj - linea) * 18)), 1)
        out[str(linea)] = {"over": over, "under": round(100 - over, 1), "over_cuota": None}
    return out


def handicap(pl, pe, pv):
    """prob_hcp_* y handicap_asiatico coherentes con el 1X2, desde una
    distribucion de dif = goles local - visitante (convencion corregida:
    "Local L" cubre si dif > -L)."""
    pesos = [0.5, 0.3, 0.15, 0.05]
    dist = {0: pe / 100}
    for i, w in enumerate(pesos, start=1):
        dist[i] = pl / 100 * w
        dist[-i] = pv / 100 * w
    P = lambda cond: round(100 * sum(p for d, p in dist.items() if cond(d)), 1)
    out = {}
    for k in (1, 2, 3):
        out[f"prob_hcp_local_m{k}"] = P(lambda d: d > k)
        out[f"prob_hcp_empate_m{k}"] = P(lambda d: d == k)
        out[f"prob_hcp_visit_m{k}"] = P(lambda d: d < k)
        out[f"prob_hcp_local_p{k}"] = P(lambda d: d > -k)
        out[f"prob_hcp_empate_p{k}"] = P(lambda d: d == -k)
        out[f"prob_hcp_visit_p{k}"] = P(lambda d: d < -k)
    out["handicap_asiatico"] = {
        str(l): {"tipo": "entera" if l == int(l) else "media", "cubre": P(lambda d: d > -l),
                 "push": P(lambda d: d == -l), "no_cubre": P(lambda d: d < -l)} for l in LINEAS_ASIATICO}
    return out


def respuesta(pl=36.0, pe=26.4, pv=37.6, btts=59.7, gl=1.53, gv=1.50, local="Union La Calera", visitante="U. Catolica",
              ataj_l=3.3, ataj_v=2.4):
    lineas_ataj = [0.5, 1.5, 2.5, 3.5, 4.5]
    return {
        **handicap(pl, pe, pv),
        "atajadas_local_proj": ataj_l, "atajadas_visitante_proj": ataj_v,
        "atajadas_ou_local": ou(ataj_l, lineas_ataj), "atajadas_ou_visitante": ou(ataj_v, lineas_ataj),
        "tiros_arco_local_proj": 4.1, "tiros_arco_visitante_proj": 5.07,
        "local": local, "visitante": visitante,
        "prob_local": pl, "prob_empate": pe, "prob_visitante": pv,
        "prob_1x": round(pl + pe, 1), "prob_x2": round(pe + pv, 1), "prob_12": round(pl + pv, 1),
        "prob_ambos_marcan": btts, "goles_proj": f"{gl:.2f} - {gv:.2f}",
        "goles_ou": ou(gl + gv, [0.5, 1.5, 2.5, 3.5, 4.5]),
        "corners_proj": 9.62, "corners_ou": ou(9.62, [7.5, 8.5, 9.5, 10.5, 11.5]),
        "tarjetas_proj": 5.29, "tarjetas_ou": ou(5.29, [2.5, 3.5, 4.5, 5.5]),
        "tiros_arco_proj": 8.7, "tiros_arco_ou": ou(8.7, [6.5, 7.5, 8.5, 9.5]),
        "tiros_total_proj": 25.9, "tiros_total_ou": ou(25.9, [22.5, 23.5, 24.5, 25.5]),
        "stats_local": {"goles_favor": 1.5, "goles_contra": 1.7, "corners_favor": 4.7, "corners_contra": 5.4,
                        "tarjetas_favor": 2.0, "tiros_arco_favor": 4.1, "tiros_total_favor": 12.3, "n_partidos": 10},
        "stats_visitante": {"goles_favor": 1.6, "goles_contra": 1.7, "corners_favor": 4.6, "corners_contra": 5.5,
                            "tarjetas_favor": 2.3, "tiros_arco_favor": 4.4, "tiros_total_favor": 13.1, "n_partidos": 10},
    }


def equipo(v=2, e=1, d=2, cv=2, cn=5, btts=6, n_total=40, pocos=False, cobertura=10, gan=5, gan2=2,
           n_atajadas=6, atajadas_prom=3.1, ventana=10):
    n5 = v + e + d
    return {"n_total": n_total, "pocos_datos": pocos,
            "forma5": {"v": v, "e": e, "d": d, "n": n5, "ppg": round((3 * v + e) / n5, 2) if n5 else None},
            "condicion": {"v": cv, "n": cn}, "btts": {"x": btts, "n": 10}, "n_ventana": ventana,
            "n_corners": cobertura, "n_tarjetas": cobertura, "n_tiros_arco": cobertura, "n_tiros_total": cobertura,
            "margen": {"gan": gan, "gan2": gan2, "n": ventana},
            "n_atajadas": n_atajadas, "atajadas_prom": atajadas_prom if n_atajadas else None}


def hechos(local=None, visitante=None, h2h_n=3):
    hl, hv = local or equipo(), visitante or equipo()
    return {"local": hl, "visitante": hv, "pocos_datos": hl["pocos_datos"] or hv["pocos_datos"],
            "h2h": {"n": h2h_n, "g": min(2, h2h_n), "e": min(1, max(0, h2h_n - 2)), "p": 0, "btts": min(2, h2h_n),
                    "goles_prom": 2.7 if h2h_n else None, "n_corners": 1 if h2h_n else 0, "corners_prom": 9.0 if h2h_n else None,
                    "n_tarjetas": 1 if h2h_n else 0, "tarjetas_prom": 7.0 if h2h_n else None,
                    "ultima_fecha": "2026-04-03" if h2h_n else None, "ultimo_antiguo": False}}


def numeros_permitidos(r, h):
    """Todas las formas en que un numero de la entrada puede aparecer en el texto."""
    vals = set()

    def recorrer(x):
        if isinstance(x, bool) or x is None:
            return
        if isinstance(x, (int, float)):
            vals.update({str(int(x)) if float(x).is_integer() else None, f"{float(x):.1f}", f"{float(x):.2f}"})
        elif isinstance(x, str):
            vals.update(A.NUMERO.findall(x))
        elif isinstance(x, dict):
            for k, v in x.items():
                recorrer(k) if isinstance(k, str) else None
                recorrer(v)
        elif isinstance(x, (list, tuple)):
            for v in x:
                recorrer(v)
    recorrer(r)
    recorrer(h)
    # diferencias y complementos que el texto calcula a partir de la entrada
    for p1 in [r["prob_local"], r["prob_empate"], r["prob_visitante"], r["prob_1x"], r["prob_x2"], r["prob_12"],
               r["prob_ambos_marcan"]]:
        for p2 in [r["prob_local"], r["prob_empate"], r["prob_visitante"], r["prob_ambos_marcan"],
                   round(100 - r["prob_ambos_marcan"], 1)]:
            vals.add(f"{p1 - p2:.1f}")
    vals.add(f"{100 - r['prob_ambos_marcan']:.1f}")
    no = round(100 - r["prob_ambos_marcan"], 1)
    vals.add(f"{no - r['prob_ambos_marcan']:.1f}")
    for m in ("goles_ou", "corners_ou", "tarjetas_ou", "tiros_arco_ou", "tiros_total_ou"):
        for v in r[m].values():
            vals.add(f"{abs(v['over'] - v['under']):.1f}")
    gl, gv = (float(x) for x in r["goles_proj"].split(" - "))
    vals.add(f"{gl + gv:.2f}")
    vals.update({"1", "2", "12", "50"})   # "(1)", "(2)", "X2"/"1X", "12 (gana cualquiera)", "50-50"
    # handicap: diferencias entre desenlaces de cada trio/par y nombres de linea
    for k in (1, 2, 3):
        for s in ("m", "p"):
            t = [r[f"prob_hcp_{x}_{s}{k}"] for x in ("local", "empate", "visit")]
            vals.update(f"{a - b:.1f}" for a in t for b in t)
    for v in r["handicap_asiatico"].values():
        vals.add(f"{v['cubre'] - v['no_cubre']:.1f}")
        vals.add(f"{v['no_cubre'] - v['cubre']:.1f}")
    for m in ("atajadas_ou_local", "atajadas_ou_visitante"):
        for v in r[m].values():
            vals.add(f"{abs(v['over'] - v['under']):.1f}")
    vals.update({"0", "0.5", "1.5", "3", "4"})   # "-0.5", "-1.5", "linea 0", "3 o mas", "4 o mas"
    vals.discard(None)
    return vals


class Umbrales(unittest.TestCase):
    def test_bordes(self):
        self.assertEqual(A.nivel(70, 30), "favorito_claro")
        self.assertEqual(A.nivel(69.9, 30.1), "moderado")
        self.assertEqual(A.nivel(55, 45), "moderado")
        self.assertEqual(A.nivel(54.9, 45.1), "parejo")
        self.assertEqual(A.nivel(50, 50), "parejo")

    def test_tres_opciones_usa_proporcion_entre_las_dos_primeras(self):
        # 42.6 crudo seria "parejo"; frente a la siguiente opcion (30.2) es 58.5% -> moderado
        a = A.analisis_1x2(respuesta(pl=30.2, pe=27.2, pv=42.6), hechos(), "k")
        self.assertEqual(a["tono"], "moderado")


class Direccion(unittest.TestCase):
    def test_favorito_visitante_listado_segundo(self):
        r = respuesta(pl=20.0, pe=20.0, pv=60.0, local="Iquique", visitante="Antofagasta")
        a = A.analisis_1x2(r, hechos(), "k")
        self.assertIn("Antofagasta (2)", a["resumen"])
        self.assertLess(a["resumen"].find("Antofagasta"), a["resumen"].find("Iquique") if "Iquique" in a["resumen"] else 10 ** 6)
        self.assertEqual(a["tono"], "favorito_claro")

    def test_favorito_local(self):
        r = respuesta(pl=55.0, pe=25.0, pv=20.0, local="Iquique", visitante="Antofagasta")
        a = A.analisis_1x2(r, hechos(), "k")
        self.assertTrue(a["resumen"].find("Iquique (1)") < a["resumen"].find("Antofagasta") or "Antofagasta" not in a["resumen"])

    def test_under_favorito_en_ou(self):
        r = respuesta(gl=0.8, gv=0.7)
        a = A.analisis_goles(r, hechos(), "k")
        self.assertIn("Under 2.5 goles", a["resumen"])

    def test_ambos_marcan_no_favorito(self):
        a = A.analisis_ambos_marcan(respuesta(btts=30.0), hechos(), "k")
        self.assertIn("No", a["resumen"])
        self.assertEqual(a["tono"], "favorito_claro")


class Semilla(unittest.TestCase):
    def test_mismo_partido_mismo_texto(self):
        r, h = respuesta(), hechos()
        self.assertEqual(A.armar_analisis_ia(r, h, 1638385), A.armar_analisis_ia(copy.deepcopy(r), copy.deepcopy(h), 1638385))

    def test_partidos_distintos_rotan_todas_las_variantes(self):
        r, h = respuesta(pl=60.0, pe=20.0, pv=20.0), hechos()
        titulos, resumenes = set(), set()
        for fid in range(1_600_000, 1_600_300):
            a = A.analisis_1x2(r, h, fid)
            titulos.add(a["titulo"])
            resumenes.add(a["resumen"])
        self.assertEqual(titulos, set(A.TITULOS["favorito_claro"]))
        self.assertEqual(len(resumenes), len(A.RESUMENES["resultado"]["favorito_claro"]))

    def test_distintos_mercados_del_mismo_partido_no_comparten_indice(self):
        idx = {m: A._indice(1638385, m, "titulo", 5) for m in MERCADOS}
        self.assertGreater(len(set(idx.values())), 1)

    def test_indice_fijo_regresion(self):
        # sha256 es estable entre procesos, versiones y maquinas: si esto cambia,
        # los textos de TODOS los partidos cambian.
        self.assertEqual([A._indice(1638384, "1x2", "titulo", 5), A._indice(1638384, "1x2", "resumen", 3),
                          A._indice(1549482, "goles", "titulo", 5)], EXPECTED_INDICES)

    def test_estable_entre_procesos_con_distinto_hashseed(self):
        codigo = ("import sys; sys.path.insert(0, '.'); from app.services import analisis_mercados as A; "
                  "print([A._indice(f, m, s, 5) for f in (1, 1638384) for m in ('1x2', 'goles') for s in ('titulo', 'resumen')])")
        raiz = os.path.join(os.path.dirname(__file__), "..")
        salidas = {subprocess.run([sys.executable, "-c", codigo], cwd=raiz, capture_output=True, text=True,
                                  env={**os.environ, "PYTHONHASHSEED": seed}).stdout for seed in ("0", "1", "12345")}
        self.assertEqual(len(salidas), 1, salidas)


class TonosConPrioridad(unittest.TestCase):
    def test_pocos_datos_pisa_y_explica(self):
        h = hechos(local=equipo(n_total=1, pocos=True))
        for m, a in A.armar_analisis_ia(respuesta(pl=60.0, pe=20.0, pv=20.0), h, "k").items():
            self.assertEqual(a["tono"], "pocos_datos", m)
            self.assertTrue(a["bullets"][0].startswith("Ojo: Union La Calera tiene 1 partido "), m)

    def test_pocos_datos_no_cita_promedios_de_goles(self):
        # Caso real Zwaluwen: 1 partido -> "promedia 3.5 goles" seria la mezcla con la liga
        h = hechos(local=equipo(n_total=1, pocos=True))
        salida = A.armar_analisis_ia(respuesta(), h, "k")
        for m in ("goles", "ambos_marcan"):
            texto = " ".join(salida[m]["bullets"])
            self.assertNotIn("Union La Calera promedia", texto, m)
            self.assertNotIn("convierte", texto, m)

    def test_senales_cruzadas_modelo_parejo_forma_distinta(self):
        h = hechos(local=equipo(v=0, e=1, d=4), visitante=equipo(v=4, e=0, d=1))
        a = A.analisis_1x2(respuesta(pl=38.0, pe=26.8, pv=35.2), h, "k")
        self.assertEqual(a["tono"], "senales_cruzadas")
        self.assertTrue(a["bullets"][0].startswith("Forma reciente (V-E-D)"))

    def test_senales_cruzadas_forma_contra_el_favorito(self):
        h = hechos(local=equipo(v=0, e=1, d=4), visitante=equipo(v=4, e=0, d=1))
        a = A.analisis_1x2(respuesta(pl=55.0, pe=25.0, pv=20.0), h, "k")
        self.assertEqual(a["tono"], "senales_cruzadas")

    def test_forma_a_favor_del_favorito_no_cruza(self):
        h = hechos(local=equipo(v=4, e=0, d=1), visitante=equipo(v=0, e=1, d=4))
        self.assertEqual(A.analisis_1x2(respuesta(pl=60.0, pe=20.0, pv=20.0), h, "k")["tono"], "favorito_claro")

    def test_cruzadas_no_aplica_a_mercados_de_goles(self):
        h = hechos(local=equipo(v=0, e=1, d=4), visitante=equipo(v=4, e=0, d=1))
        self.assertNotEqual(A.analisis_goles(respuesta(), h, "k")["tono"], "senales_cruzadas")


class SinInventar(unittest.TestCase):
    def test_cada_numero_del_texto_sale_de_la_entrada(self):
        rnd = random.Random(7)
        for i in range(300):
            pl, pv = rnd.uniform(10, 70), rnd.uniform(10, 70)
            pe = rnd.uniform(10, 35)
            tot = pl + pe + pv
            pl, pe, pv = (round(100 * x / tot, 1) for x in (pl, pe, pv))
            r = respuesta(pl=pl, pe=pe, pv=pv, btts=round(rnd.uniform(20, 80), 1),
                          gl=round(rnd.uniform(0.3, 2.8), 2), gv=round(rnd.uniform(0.3, 2.8), 2))
            h = hechos(local=equipo(v=rnd.randint(0, 5), e=0, d=0, cobertura=rnd.choice([0, 2, 4, 10])),
                       visitante=equipo(v=0, e=rnd.randint(1, 5), d=0, cobertura=rnd.choice([0, 3, 10])),
                       h2h_n=rnd.choice([0, 1, 3]))
            permitidos = numeros_permitidos(r, h)
            for m, a in A.armar_analisis_ia(r, h, i).items():
                for n in A.numeros_en_texto(a):
                    self.assertIn(n, permitidos, f"{m}: {n!r} no sale de la entrada -> {a['resumen']} {a['bullets']}")

    def test_texto_limpio(self):
        for fid in range(200):
            for m, a in A.armar_analisis_ia(respuesta(), hechos(h2h_n=fid % 3), fid).items():
                texto = " ".join([a["titulo"], a["resumen"]] + a["bullets"])
                for malo in ("{", "}", "((", " a el ", " de el ", "  "):
                    self.assertNotIn(malo, texto, f"{m}: {texto}")
                self.assertIsNone(re.search(r"(None|nan|NaN|inf)", texto), f"{m}: {texto}")
                self.assertEqual(set(a), CAMPOS)
                self.assertEqual(a["disclaimer"], A.DISCLAIMER)
                self.assertLessEqual(len(a["bullets"]), 3)
                self.assertEqual(a["emoji"], A.EMOJI[a["tono"]])

    def test_sin_datos_propios_no_cita_promedio_del_equipo(self):
        # Caso real Curico Unido: 0 partidos con tiros -> el modelo usa el promedio de liga
        h = hechos(local=equipo(cobertura=0))
        for m in ("corners", "tarjetas", "tiros_arco", "tiros_total"):
            a = A.armar_analisis_ia(respuesta(), h, "k")[m]
            texto = " ".join(a["bullets"])
            self.assertNotIn("Union La Calera promedia", texto, m)
            self.assertIn("Union La Calera no tiene datos propios", texto, m)
            self.assertIn("U. Catolica promedia", texto, m)

    def test_ninguno_con_datos(self):
        h = hechos(local=equipo(cobertura=0), visitante=equipo(cobertura=1))
        a = A.armar_analisis_ia(respuesta(), h, "k")["corners"]
        self.assertIn("Ni Union La Calera ni U. Catolica tienen datos propios", a["bullets"][0])

    def test_cobertura_baja_se_avisa(self):
        h = hechos(local=equipo(cobertura=4))
        a = A.armar_analisis_ia(respuesta(), h, "k")["corners"]
        self.assertTrue(any(b.startswith("Cobertura baja: solo 4 de los últimos 10 partidos de Union La Calera") for b in a["bullets"]))

    def test_mercado_sin_proyeccion(self):
        r = respuesta()
        r["tiros_arco_proj"], r["tiros_arco_ou"] = None, {}
        a = A.armar_analisis_ia(r, hechos(), "k")["tiros_arco"]
        self.assertEqual((a["tono"], a["bullets"]), ("sin_datos", []))

    def test_un_mercado_roto_no_rompe_los_demas(self):
        r = respuesta()
        del r["stats_local"]["corners_favor"]
        salida = A.armar_analisis_ia(r, hechos(), "k")
        self.assertEqual(salida["corners"]["tono"], "sin_datos")
        self.assertNotEqual(salida["goles"]["tono"], "sin_datos")
        self.assertEqual(list(salida), MERCADOS)

    def test_h2h_singular_y_sin_h2h(self):
        a = A.armar_analisis_ia(respuesta(), hechos(h2h_n=1), "k")["corners"]
        self.assertIn("El único cruce directo con datos sumó 9.0 corners.", a["bullets"])
        a = A.analisis_1x2(respuesta(), hechos(h2h_n=0), "k")
        self.assertIn("No hay cruces directos en la base", " ".join(a["bullets"]))


class SegundaPasada(unittest.TestCase):
    def texto(self, a):
        return " ".join([a["resumen"]] + a["bullets"])

    def test_favorito_del_handicap_es_el_del_1x2_en_ambas_direcciones(self):
        casos = [(50.0, 25.0, 25.0, "Iquique", "Antofagasta"), (20.0, 25.0, 55.0, "Antofagasta", "Iquique"),
                 (38.0, 26.8, 35.2, "Iquique", "Antofagasta"), (35.2, 26.8, 38.0, "Antofagasta", "Iquique")]
        for pl, pe, pv, fav, riv in casos:
            r = respuesta(pl=pl, pe=pe, pv=pv, local="Iquique", visitante="Antofagasta")
            for m, marca_fav, marca_riv in (("hcp_europeo", f"{fav} -1", f"{riv} -1"), ("hcp_asiatico", f"{fav} -0.5", f"{riv} -0.5")):
                with self.subTest(favorito=fav, mercado=m):
                    t = self.texto(A.armar_analisis_ia(r, hechos(), "k")[m])
                    self.assertIn(marca_fav, t)
                    self.assertNotIn(marca_riv, t)

    def test_europeo_visitante_favorito_usa_la_linea_p1(self):
        r = respuesta(pl=20.0, pe=25.0, pv=55.0, local="Iquique", visitante="Antofagasta")
        a = A.analisis_hcp_europeo(r, hechos(), "k")
        # Visitante -1 = Local +1: "Iquique +1" es prob_hcp_local_p1
        self.assertIn(f"{r['prob_hcp_local_p1']:.1f}%", a["resumen"])
        self.assertIn(f"Ganar por 3 o más (Antofagasta -2): {r['prob_hcp_visit_p2']:.1f}%", self.texto(a))

    def test_asiatico_menos_05_es_la_prob_de_ganar_del_1x2(self):
        for pl, pe, pv, fav, riv in ((60.0, 20.0, 20.0, "Iquique", "Antofagasta"), (20.0, 20.0, 60.0, "Antofagasta", "Iquique")):
            r = respuesta(pl=pl, pe=pe, pv=pv, local="Iquique", visitante="Antofagasta")
            a = A.analisis_hcp_asiatico(r, hechos(), "k")
            res = a["resumen"]
            # el favorito -0.5 (gana, 60%) lidera y va primero; el rival +0.5 (no pierde, 40%) segundo
            self.assertLess(res.find(f"{fav} -0.5 (gana el partido)"), res.find(f"{riv} +0.5 (no pierde)"))
            self.assertIn("60.0%", res)
            self.assertIn(f"Con la línea 0 (si empatan se devuelve): {fav} 60.0% contra {riv} 20.0%", " ".join(a["bullets"]))

    def test_titulos_propios_del_europeo(self):
        for fid in range(40):
            a = A.analisis_hcp_europeo(respuesta(pl=60.0, pe=20.0, pv=20.0), hechos(local=equipo(v=4, e=0, d=1)), fid)
            if a["tono"] in A.TITULOS_HCP_EUROPEO:
                self.assertIn(a["titulo"], A.TITULOS_HCP_EUROPEO[a["tono"]])

    def test_senales_cruzadas_en_handicap(self):
        h = hechos(local=equipo(v=0, e=1, d=4), visitante=equipo(v=4, e=0, d=1))
        for m in ("hcp_europeo", "hcp_asiatico"):
            self.assertEqual(A.armar_analisis_ia(respuesta(pl=55.0, pe=25.0, pv=20.0), h, "k")[m]["tono"], "senales_cruzadas")

    def test_atajadas_dos_bullets_sin_forzar_un_tercero(self):
        salida = A.armar_analisis_ia(respuesta(), hechos(), "k")
        for lado in ("local", "visitante"):
            self.assertEqual(len(salida[f"atajadas_{lado}"]["bullets"]), 2, lado)
        self.assertIn("U. Catolica proyecta 5.07 tiros al arco", salida["atajadas_local"]["bullets"][0])

    def test_atajadas_sin_dato_propio(self):
        h = hechos(local=equipo(n_atajadas=1))
        b = A.armar_analisis_ia(respuesta(), h, "k")["atajadas_local"]["bullets"]
        self.assertIn("tiene el dato de atajadas en solo 1 de sus últimos 10 partidos", b[1])
        self.assertNotIn("promedia", " ".join(b))

    def test_atajadas_disperso_no_contradice(self):
        r = respuesta(ataj_l=3.1)
        # distribucion muy dispersa: promedio 3.1 pero Under 2.5 mas probable
        r["atajadas_ou_local"]["2.5"] = {"over": 36.2, "under": 63.8}
        a = A.analisis_atajadas_equipo(r, hechos(), "k", "local")
        self.assertIn("dispers", a["resumen"])
        self.assertIn("Under 2.5 atajadas", a["resumen"])

    def test_atajadas_sin_proyeccion(self):
        r = respuesta()
        r["atajadas_visitante_proj"], r["atajadas_ou_visitante"] = None, None
        a = A.armar_analisis_ia(r, hechos(), "k")["atajadas_visitante"]
        self.assertEqual((a["tono"], a["bullets"]), ("sin_datos", []))

    def test_un_solo_partido_en_singular(self):
        h = hechos(local=equipo(ventana=1, gan=1, gan2=1, n_atajadas=0, n_total=1, pocos=True))
        salida = A.armar_analisis_ia(respuesta(pl=60.0, pe=20.0, pv=20.0), h, "k")
        texto = " ".join(self.texto(salida[m]) for m in ("hcp_europeo", "atajadas_local"))
        self.assertNotIn("de sus últimos 1 ", texto)
        self.assertIn("tiene un solo partido registrado", texto)


class LineaDeReferencia(unittest.TestCase):
    def test_usa_la_linea_de_referencia(self):
        r = respuesta()
        for m, ref in A.LINEAS_REFERENCIA.items():
            self.assertEqual(float(A._elegir_linea(r[f"{m}_ou"], m)[0]), ref)

    def test_si_falta_usa_la_mas_cercana(self):
        self.assertEqual(A._elegir_linea(ou(2.0, [0.5, 1.5, 3.5]), "goles")[0], "1.5")

    def test_genero_tarjetas(self):
        textos = {A.analisis_tarjetas(respuesta(), hechos(), f)["resumen"] for f in range(60)}
        self.assertFalse(any("tarjetas proyectados" in t for t in textos))


# Valores fijados a mano (calculados el 2026-09-23), no recalculados aca.
EXPECTED_INDICES = [4, 0, 4]

if __name__ == "__main__":
    unittest.main()
