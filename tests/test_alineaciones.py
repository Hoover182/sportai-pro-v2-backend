"""Alineaciones: formato/cobertura sobre respuestas REALES de api-football
(tests/datos/alineaciones_muestra.json, 4 partidos recortados de
/fixtures?ids=) y cache con la red simulada.
Correr desde backend/: python -m unittest discover -s tests -v"""
import copy
import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.services import alineaciones as A

with open(os.path.join(os.path.dirname(__file__), "datos", "alineaciones_muestra.json"), encoding="utf-8") as fh:
    MUESTRA = json.load(fh)


def fx(nombre):
    return copy.deepcopy(MUESTRA[nombre])


class Formato(unittest.TestCase):
    def test_completa_premier(self):
        estado, estado_partido, equipos = A.formatear_alineaciones(fx("completa_premier"))
        self.assertEqual((estado, estado_partido), ("disponible", "FT"))
        self.assertEqual([(e["lado"], e["equipo"]) for e in equipos], [("local", "Brentford"), ("visitante", "Chelsea")])
        for e in equipos:
            self.assertEqual(e["cobertura"], {"completa": True, "faltantes": []})
            self.assertEqual(len(e["titulares"]), 11)
            self.assertTrue(e["tecnico"])
            self.assertRegex(e["formacion"], r"^\d(-\d)+$")
        arquero = equipos[0]["titulares"][0]
        self.assertEqual((arquero["posicion"], arquero["posicion_original"], arquero["grid"], arquero["fila"], arquero["columna"]),
                         ("arquero", "G", "1:1", 1, 1))
        self.assertNotIn("grid", equipos[0]["suplentes"][0])

    def test_conserva_datos_originales(self):
        crudo = fx("completa_premier")
        _, _, equipos = A.formatear_alineaciones(crudo)
        for e_crudo in crudo["lineups"]:
            e = next(x for x in equipos if x["equipo_id"] == e_crudo["team"]["id"])
            self.assertEqual(e["tecnico"], e_crudo["coach"]["name"])
            self.assertEqual(e["formacion"], e_crudo["formation"])
            for j, jc in zip(e["titulares"], e_crudo["startXI"]):
                p = jc["player"]
                self.assertEqual((j["id"], j["nombre"], j["dorsal"], j["posicion_original"], j["grid"]),
                                 (p["id"], p["name"], p["number"], p["pos"], p["grid"]))
                self.assertEqual(j["posicion"], A.POSICIONES[p["pos"]])
            self.assertEqual([j["id"] for j in e["suplentes"]], [s["player"]["id"] for s in e_crudo["substitutes"]])

    def test_parcial_mls_un_equipo_sin_formacion_grid_tecnico(self):
        estado, _, equipos = A.formatear_alineaciones(fx("parcial_mls"))
        self.assertEqual(estado, "disponible")
        local, visitante = equipos
        self.assertEqual((local["equipo"], local["cobertura"]["completa"]), ("New York City FC", True))
        self.assertEqual(visitante["equipo"], "New York Red Bulls")
        self.assertEqual(visitante["cobertura"], {"completa": False, "faltantes": ["formacion", "grid", "tecnico"]})
        self.assertIsNone(visitante["formacion"])
        self.assertTrue(all(j["fila"] is None and j["posicion"] for j in visitante["titulares"]))

    def test_parcial_primera_nacional_sin_posiciones(self):
        _, _, equipos = A.formatear_alineaciones(fx("parcial_primera_nacional"))
        for e in equipos:
            self.assertFalse(e["cobertura"]["completa"])
            self.assertIn("posiciones", e["cobertura"]["faltantes"])
            self.assertTrue(all(j["posicion"] is None and j["posicion_original"] is None for j in e["titulares"]))
            self.assertTrue(all(j["nombre"] and j["dorsal"] is not None for j in e["titulares"]))

    def test_sin_alineacion(self):
        self.assertEqual(A.formatear_alineaciones(fx("sin_alineacion_us_open_cup")), ("sin_alineacion", "FT", []))

    def test_no_terminado_no_expone_alineaciones(self):
        f = fx("completa_premier")
        f["fixture"]["status"]["short"] = "NS"
        self.assertEqual(A.formatear_alineaciones(f), ("partido_no_terminado", "NS", []))

    def test_local_primero_aunque_la_api_lo_mande_segundo(self):
        f = fx("completa_premier")
        f["lineups"].reverse()
        _, _, equipos = A.formatear_alineaciones(f)
        self.assertEqual([e["lado"] for e in equipos], ["local", "visitante"])

    def test_aet_y_pen_son_terminados(self):
        for estado in ("AET", "PEN"):
            f = fx("completa_premier")
            f["fixture"]["status"]["short"] = estado
            self.assertEqual(A.formatear_alineaciones(f)[0], "disponible")

    def test_titulares_incompletos(self):
        f = fx("completa_premier")
        f["lineups"][0]["startXI"] = f["lineups"][0]["startXI"][:10]
        _, _, equipos = A.formatear_alineaciones(f)
        self.assertIn("titulares", equipos[0]["cobertura"]["faltantes"])


class Resp:
    def __init__(self, data, status=200):
        self._data, self.status_code = data, status

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class Cache(unittest.TestCase):
    def setUp(self):
        A._cache.clear()
        self.llamadas = []
        self.respuestas = {}
        self.reloj = [1000.0]
        self.parches = [
            mock.patch.object(A.requests, "get", self._get),
            mock.patch.object(A.time, "monotonic", lambda: self.reloj[0]),
            mock.patch.dict(os.environ, {"APIFOOTBALL_KEY": "falsa"}),
        ]
        for p in self.parches:
            p.start()

    def tearDown(self):
        for p in self.parches:
            p.stop()

    def _get(self, url, headers=None, params=None, timeout=None):
        self.llamadas.append(params["id"])
        r = self.respuestas[params["id"]]
        return r if isinstance(r, Resp) else Resp({"errors": [], "response": r})

    def test_completa_se_cachea_para_siempre(self):
        self.respuestas[1] = [fx("completa_premier")]
        r1 = A.get_alineaciones(1)
        self.reloj[0] += 10 * 365 * 86400
        r2 = A.get_alineaciones(1)
        self.assertEqual(self.llamadas, [1])
        self.assertEqual((r1["fuente"]["cacheado"], r2["fuente"]["cacheado"]), (False, True))
        self.assertEqual({k: v for k, v in r1.items() if k != "fuente"}, {k: v for k, v in r2.items() if k != "fuente"})
        self.assertTrue(r1["cobertura_completa"])

    def test_parcial_y_vacia_se_reintentan_tras_ttl(self):
        for fid, nombre in ((2, "parcial_mls"), (3, "sin_alineacion_us_open_cup")):
            self.respuestas[fid] = [fx(nombre)]
            A.get_alineaciones(fid)
            self.reloj[0] += A.TTL_INCOMPLETA - 1
            A.get_alineaciones(fid)
            self.assertEqual(self.llamadas.count(fid), 1)
            self.reloj[0] += 1
            A.get_alineaciones(fid)
            self.assertEqual(self.llamadas.count(fid), 2)

    def test_no_terminado_ttl_corto(self):
        f = fx("completa_premier")
        f["fixture"]["status"]["short"] = "NS"
        self.respuestas[4] = [f]
        r = A.get_alineaciones(4)
        self.assertEqual((r["estado"], r["equipos"]), ("partido_no_terminado", []))
        A.get_alineaciones(4)
        self.reloj[0] += A.TTL_NO_TERMINADO
        A.get_alineaciones(4)
        self.assertEqual(self.llamadas, [4, 4])

    def test_error_de_la_api_no_se_cachea(self):
        self.respuestas[5] = Resp({"errors": {"requests": "You have reached the request limit"}, "response": []})
        r = A.get_alineaciones(5)
        self.assertEqual((r["estado"], r["equipos"]), ("fuente_no_disponible", []))
        self.respuestas[5] = [fx("completa_premier")]
        self.assertEqual(A.get_alineaciones(5)["estado"], "disponible")
        self.assertEqual(self.llamadas, [5, 5])

    def test_http_error_y_sin_key(self):
        self.respuestas[6] = Resp({}, status=500)
        self.assertEqual(A.get_alineaciones(6)["estado"], "fuente_no_disponible")
        with mock.patch.dict(os.environ, {"APIFOOTBALL_KEY": ""}):
            self.assertEqual(A.get_alineaciones(7)["estado"], "fuente_no_disponible")
        self.assertEqual(self.llamadas, [6])

    def test_fixture_inexistente(self):
        self.respuestas[8] = []
        self.assertEqual(A.get_alineaciones(8)["estado"], "partido_no_encontrado")

    def test_misma_forma_en_todos_los_estados(self):
        self.respuestas.update({1: [fx("completa_premier")], 3: [fx("sin_alineacion_us_open_cup")], 8: [],
                                5: Resp({"errors": {"token": "x"}, "response": []})})
        formas = {fid: set(A.get_alineaciones(fid)) for fid in (1, 3, 8, 5)}
        self.assertEqual(len({frozenset(f) for f in formas.values()}), 1, formas)


if __name__ == "__main__":
    unittest.main()
