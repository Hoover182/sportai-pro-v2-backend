"""Sync de NBA (scripts/sync_nba.py): parseo de boxscores reales del CDN,
recorrido de ids de una temporada, modo diario e idempotencia, con el CDN
simulado. No toca la red.
Correr desde backend/: python -m unittest discover -s tests -v"""
import copy
import json
import os
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import sync_nba as S

DATOS = os.path.join(os.path.dirname(__file__), "datos", "nba")


def _box(game_id):
    with open(os.path.join(DATOS, f"boxscore_{game_id}.json"), encoding="utf-8") as f:
        return json.load(f)["game"]


def _box_con_id(base, game_id, fecha="2025-10-21"):
    g = copy.deepcopy(base)
    g["gameId"] = game_id
    g["gameEt"] = f"{fecha}T19:30:00-04:00"
    return g


class Parseo(unittest.TestCase):
    def test_doble_prorroga_real(self):
        # OKC 125 - HOU 124 en 2OT, 21/10/2025 (verificado contra stats.nba.com)
        fila, jug = S.parsear_boxscore(_box("0022500001"))
        self.assertEqual(fila["fecha"], "2025-10-21")
        self.assertEqual(fila["temporada"], "2025-26")
        self.assertEqual(fila["tipo"], "regular")
        self.assertEqual((fila["sigla_local"], fila["sigla_visitante"]), ("OKC", "HOU"))
        self.assertEqual(fila["equipo_local"], "Oklahoma City Thunder")
        self.assertEqual((fila["puntos_local"], fila["puntos_visitante"]), (125, 124))
        self.assertEqual([fila[f"q{i}_local"] for i in range(1, 5)], [27, 24, 24, 29])
        self.assertEqual((fila["prorroga_local"], fila["prorroga_visitante"]), (21, 20))
        self.assertEqual(fila["n_prorrogas"], 2)
        self.assertEqual(set(fila), set(S.COLS_PARTIDOS))
        self.assertEqual(sum(j["pts"] for j in jug if j["local"] == 1), 125)
        self.assertEqual(sum(j["pts"] for j in jug if j["local"] == 0), 124)
        self.assertTrue(all(set(j) == set(S.COLS_JUGADORES) for j in jug))

    def test_final_playoffs(self):
        fila, _ = S.parsear_boxscore(_box("0042500405"))
        self.assertEqual(fila["tipo"], "playoffs")
        self.assertEqual(fila["n_prorrogas"], 0)
        self.assertEqual((fila["puntos_local"], fila["puntos_visitante"]), (90, 94))

    def test_cuartos_que_no_cierran_frenan(self):
        g = _box("0042500405")
        g["homeTeam"]["score"] += 1
        with self.assertRaises(ValueError):
            S.parsear_boxscore(g)

    def test_partido_sin_terminar_frena(self):
        g = _box("0042500405")
        g["gameStatus"] = 2
        with self.assertRaises(ValueError):
            S.parsear_boxscore(g)

    def test_minutos(self):
        self.assertEqual(S.minutos("PT45M15.10S"), 45.25)
        self.assertEqual(S.minutos("PT00M00.00S"), 0.0)
        self.assertEqual(S.minutos(""), 0.0)

    def test_temporada(self):
        self.assertEqual(S.temporada_de("0022500001"), "2025-26")
        self.assertEqual(S.temporada_de("0021900001"), "2019-20")


class Calendario(unittest.TestCase):
    def test_filtra_pretemporada_y_no_terminados(self):
        cal = {"leagueSchedule": {"gameDates": [{"games": [
            {"gameId": "0012600001", "gameStatus": 3},   # pretemporada
            {"gameId": "0022600002", "gameStatus": 3},
            {"gameId": "0022600001", "gameStatus": 3},
            {"gameId": "0022600003", "gameStatus": 1},   # sin jugar
            {"gameId": "0032600001", "gameStatus": 3},   # All-Star
            {"gameId": "0062600001", "gameStatus": 3},   # final Copa
        ]}]}}
        self.assertEqual(S.ids_terminados_calendario(cal),
                         ["0022600001", "0022600002", "0062600001"])


class Recorrido(unittest.TestCase):
    def _cdn(self, existentes):
        pedidos = []

        def pedir(ruta):
            gid = ruta.rsplit("_", 1)[1].split(".")[0]
            pedidos.append(gid)
            return {"game": {"gameId": gid}} if gid in existentes else None
        return pedir, pedidos

    def test_temporada_completa(self):
        existentes = {f"00225{n:05d}" for n in range(1, 1231)}
        existentes |= {"0052500101", "0052500102", "0052500201"}
        existentes |= {f"00425001{s}{j}" for s in range(8) for j in range(1, 5)}  # 8 barridas
        existentes |= {"0042500201", "0062500001"}
        pedir, pedidos = self._cdn(existentes)
        nuevos = S.recorrer_temporada(25, set(), pedir=pedir, log=lambda *_: None)
        ids = {g["gameId"] for g in nuevos}
        self.assertEqual(ids, existentes)
        # se corto 20 ids despues del 1230
        self.assertNotIn("0022501251", pedidos)
        self.assertIn("0022501250", pedidos)

    def test_no_repide_lo_que_ya_esta(self):
        existentes = {f"00225{n:05d}" for n in range(1, 1231)}
        pedir, pedidos = self._cdn(existentes)
        S.recorrer_temporada(25, {"0022500500"}, pedir=pedir, log=lambda *_: None)
        self.assertNotIn("0022500500", pedidos)

    def test_bloqueo_no_se_confunde_con_fin_de_temporada(self):
        pedir, _ = self._cdn(set())
        with self.assertRaises(S.Bloqueado):
            S.recorrer_temporada(25, set(), pedir=pedir, log=lambda *_: None)


class Diario(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)
        for nombre, valor in (("CSV_PARTIDOS", "nba_partidos.csv"),
                              ("DIR_JUGADORES", "nba_jugadores"),
                              ("META", "nba_datos_meta.json")):
            p = mock.patch.object(S, nombre, os.path.join(self.dir, valor))
            p.start()
            self.addCleanup(p.stop)
        base = _box("0042500405")
        self.boxes = {
            "0022600001": _box_con_id(base, "0022600001", "2026-10-20"),
            "0022600002": _box_con_id(base, "0022600002", "2026-10-21"),
        }
        self.cal = {"leagueSchedule": {"seasonYear": "2026-27", "gameDates": [{"games": [
            {"gameId": gid, "gameStatus": 3} for gid in self.boxes]}]}}

    def _pedir(self, bloqueado=False):
        def pedir(ruta):
            if ruta.startswith("staticData"):
                return self.cal
            gid = ruta.rsplit("_", 1)[1].split(".")[0]
            return None if bloqueado else {"game": self.boxes.get(gid)} if gid in self.boxes else None
        return pedir

    def test_baja_y_es_idempotente(self):
        log = lambda *_: None
        self.assertEqual(S.diario(pedir=self._pedir(), log=log), 2)
        partidos = S.leer_csv(S.CSV_PARTIDOS)
        self.assertEqual([p["game_id"] for p in partidos], ["0022600001", "0022600002"])
        jug = S.leer_csv(S.ruta_jugadores("2026-27"))
        self.assertEqual(len(jug), 2 * len(S.parsear_boxscore(self.boxes["0022600001"])[1]))
        with open(S.META, encoding="utf-8") as f:
            self.assertIn("datos_actualizados_en", json.load(f))
        # Segunda corrida: nada nuevo, nada reescrito.
        self.assertEqual(S.diario(pedir=self._pedir(), log=log), 0)
        self.assertEqual(len(S.leer_csv(S.CSV_PARTIDOS)), 2)

    def test_partido_nuevo_no_borra_los_viejos(self):
        log = lambda *_: None
        S.diario(pedir=self._pedir(), log=log)
        self.boxes["0022600003"] = _box_con_id(self.boxes["0022600001"], "0022600003", "2026-10-22")
        self.cal["leagueSchedule"]["gameDates"][0]["games"].append(
            {"gameId": "0022600003", "gameStatus": 3})
        self.assertEqual(S.diario(pedir=self._pedir(), log=log), 1)
        self.assertEqual(len(S.leer_csv(S.CSV_PARTIDOS)), 3)

    def test_bloqueo_en_boxscores_es_error(self):
        with self.assertRaises(S.Bloqueado):
            S.diario(pedir=self._pedir(bloqueado=True), log=lambda *_: None)


if __name__ == "__main__":
    unittest.main()
