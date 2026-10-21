"""Alerta de datos viejos (scripts/alerta_datos_viejos.py): umbral, casos sin
respuesta y manejo del issue (abrir, comentar, cerrar), con GitHub simulado.
No toca la red.
Correr desde backend/: python -m unittest discover -s tests -v"""
import os
import sys
import unittest
from datetime import datetime, timezone
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import alerta_datos_viejos as A

AHORA = datetime(2026, 10, 21, 15, 0, tzinfo=timezone.utc)


class Evaluar(unittest.TestCase):
    def test_al_dia(self):
        alerta, horas, _ = A.evaluar("2026-10-20T16:10:51Z", AHORA)
        self.assertFalse(alerta)
        self.assertAlmostEqual(horas, 22.8, places=1)

    def test_caso_real_trabado_5_dias(self):
        alerta, horas, msg = A.evaluar("2026-10-16T16:10:51Z", AHORA)
        self.assertTrue(alerta)
        self.assertGreater(horas, 110)
        self.assertIn("2026-10-16", msg)

    def test_justo_en_el_umbral_no_alerta(self):
        self.assertFalse(A.evaluar("2026-10-20T03:00:00Z", AHORA)[0])   # 36 h exactas
        self.assertTrue(A.evaluar("2026-10-20T02:59:00Z", AHORA)[0])

    def test_sin_respuesta_o_formato_raro_alerta(self):
        self.assertTrue(A.evaluar(None, AHORA)[0])
        self.assertTrue(A.evaluar("ayer", AHORA)[0])


class ManejoDelIssue(unittest.TestCase):
    def _correr(self, meta, abierto):
        gh = mock.MagicMock()
        gh.issue_abierto.return_value = abierto
        gh.abrir.return_value = {"number": 99}
        with mock.patch.object(A, "leer_meta", return_value=meta), \
             mock.patch.object(A, "GitHub", return_value=gh), \
             mock.patch.dict(os.environ, {"GITHUB_TOKEN": "x", "GITHUB_REPOSITORY": "o/r"}), \
             mock.patch.object(sys, "argv", ["alerta_datos_viejos.py"]):
            with mock.patch("builtins.print"):
                codigo = A.main()
        return codigo, gh

    def test_datos_viejos_sin_issue_abre_uno(self):
        codigo, gh = self._correr("2020-01-01T00:00:00Z", None)
        self.assertEqual(codigo, 1)
        gh.abrir.assert_called_once()
        gh.comentar.assert_not_called()

    def test_datos_viejos_con_issue_comenta(self):
        codigo, gh = self._correr("2020-01-01T00:00:00Z", {"number": 7})
        self.assertEqual(codigo, 1)
        gh.abrir.assert_not_called()
        gh.comentar.assert_called_once()

    def test_datos_al_dia_cierra_el_issue(self):
        ahora_iso = datetime.now(timezone.utc).isoformat()
        codigo, gh = self._correr(ahora_iso, {"number": 7})
        self.assertEqual(codigo, 0)
        gh.cerrar.assert_called_once()

    def test_datos_al_dia_sin_issue_no_hace_nada(self):
        codigo, gh = self._correr(datetime.now(timezone.utc).isoformat(), None)
        self.assertEqual(codigo, 0)
        gh.abrir.assert_not_called()
        gh.cerrar.assert_not_called()


if __name__ == "__main__":
    unittest.main()
