"""Prueba REAL contra el repo de tracking en GitHub. Se saltea sin
TRACKING_REPO_TOKEN. Verifica invariantes sobre TODO el registro real y
algunos casos conocidos (valores inmutables: el registro es append-only
y un resultado escrito no se sobrescribe).
Correr desde backend/: python -m unittest tests.test_tracking_picks_github -v"""
import os
import sys
import unittest
from datetime import datetime, timezone
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.services import tracking_picks as T


@unittest.skipUnless(os.environ.get("TRACKING_REPO_TOKEN"), "sin TRACKING_REPO_TOKEN")
class GitHubReal(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        T._cache.update(indice=None, sha=None, etag=None, leido_en_utc=None, proximo_chequeo=0.0,
                        desactualizado=False)
        cls.indice, cls.meta = T.obtener_indice()
        cls.ahora = datetime.now(timezone.utc)

    def test_lee_del_repo(self):
        self.assertIsNotNone(self.indice, "no se pudo leer el repo (ver AVISO arriba)")
        self.assertFalse(self.meta["datos_desactualizados"])
        self.assertEqual(len(self.meta["commit_tracking"]), 7)

    def test_casos_conocidos(self):
        r = T.armar_picks_fixture(self.indice, 1490481, self.ahora)   # NYCFC - NY Red Bulls
        self.assertEqual(r["estado_tracking"], "registrado")
        p = {x["posicion"]: x for x in r["picks"]}
        self.assertEqual((p[1]["nombre_pick"], p[1]["prob_pct"], p[1]["cuota"], p[1]["resultado"], p[1]["valor_real"]),
                         ("Over 1.5 goles", 79.2, 1.16, "FALLO", "1"))
        self.assertEqual((p[2]["resultado"], p[2]["valor_real"], p[2]["cuota"]), ("ACIERTO", "2", None))

        r = T.armar_picks_fixture(self.indice, 1639781, self.ahora)   # Cerro - Penarol, pos 3 contaminada
        self.assertEqual(r["picks_excluidos"], 1)
        self.assertNotIn(3, [x["posicion"] for x in r["picks"]])

        r = T.armar_picks_fixture(self.indice, 1619905, self.ahora)   # Imortal - Tondela, omitido
        self.assertEqual((r["estado_tracking"], r["motivo_omision"]), ("omitido", "sin_simulacion"))

        self.assertEqual(T.armar_picks_fixture(self.indice, 1, self.ahora)["estado_tracking"], "sin_registro")

    def test_invariantes_sobre_todo_el_registro(self):
        total_reg = sum(len(f) for f in self.indice["registro"].values())
        vistos = excluidos = marcados = 0
        for fid in self.indice["registro"]:
            r = T.armar_picks_fixture(self.indice, fid, self.ahora)
            vistos += len(r["picks"])
            excluidos += r["picks_excluidos"]
            self.assertEqual(sum(r["resumen"].values()), len(r["picks"]))
            for p in r["picks"]:
                self.assertIsNotNone(p["prob_pct"])
                if p["resultado"] == "PENDIENTE":
                    self.assertIsNotNone(p["pendiente_motivo"])
                else:
                    marcados += 1
                    self.assertIsNotNone(p["mercado_id"])
                    self.assertIsNone(p["pendiente_motivo"])
        self.assertEqual(vistos + excluidos, total_reg)
        self.assertEqual(excluidos, len(self.indice["contaminados"]))
        marcados_contaminados = len(self.indice["contaminados"] & set(self.indice["resultados"]))
        self.assertEqual(marcados + marcados_contaminados, len(self.indice["resultados"]))

    def test_rechequeo_sin_commit_nuevo_es_un_304(self):
        llamadas = []
        real = T.requests.get

        def espia(url, **kw):
            resp = real(url, **kw)
            llamadas.append((url.rsplit("/", 2)[-2:], resp.status_code))
            return resp

        T._cache["proximo_chequeo"] = 0.0
        with mock.patch.object(T.requests, "get", espia):
            indice, meta = T.obtener_indice()
        self.assertIs(indice, self.indice)
        self.assertEqual(llamadas, [(["commits", "main"], 304)])


if __name__ == "__main__":
    unittest.main()
