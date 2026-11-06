"""Avisos por Telegram (scripts/avisar_telegram.py, aviso_sync_telegram.py y
su uso en alerta_datos_viejos.py), con la API simulada. No toca la red.
Correr desde backend/: python -m unittest discover -s tests -v"""
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from unittest import mock

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import alerta_datos_viejos as A  # noqa: E402
import avisar_telegram as T  # noqa: E402
import aviso_sync_telegram as S  # noqa: E402

TOKEN = "123456:SECRETO-NO-IMPRIMIR"
ENV = {"TELEGRAM_BOT_TOKEN": TOKEN, "TELEGRAM_CHAT_ID": "42"}

# Comentario real del veredicto del sync #107 (05/11/2026), recortado.
VEREDICTO_107 = """## Veredicto de auto-merge

⛔ **NO se mergea solo** -- queda para revision manual. 2 criterio(s) fallaron:
- Volumen anomalo: 659 filas nuevas (tope 600 para 3 dia(s))
- 58 fila(s) nueva(s) con fecha vacia, a mas de 400 dias, o de hace mas de 60 dias con liga o equipo que main no tiene: ['2014-08-16T14:00:00 League Two: York vs Northampton']

<details><summary>Metricas</summary>

- Dias desde la ultima sync: 3
- Filas nuevas: 659 (tope 600)

</details>
"""


def respuesta(js, status=200):
    r = mock.MagicMock()
    r.status_code = status
    r.json.return_value = js
    return r


class Enviar(unittest.TestCase):
    def test_envio_ok_usa_chat_y_texto(self):
        with mock.patch.dict(os.environ, ENV), \
             mock.patch.object(T.requests, "post", return_value=respuesta({"ok": True, "result": {"message_id": 7, "date": 1}})) as post:
            ok, detalle = T.enviar("hola")
        self.assertTrue(ok)
        self.assertIn("message_id=7", detalle)
        url = post.call_args.args[0]
        self.assertEqual(url, f"https://api.telegram.org/bot{TOKEN}/sendMessage")
        self.assertEqual(post.call_args.kwargs["json"]["chat_id"], "42")
        self.assertEqual(post.call_args.kwargs["json"]["text"], "hola")

    def test_sin_secretos_no_llama_a_la_api(self):
        with mock.patch.dict(os.environ, {}, clear=True), mock.patch.object(T.requests, "post") as post:
            ok, detalle = T.enviar("hola")
        self.assertFalse(ok)
        post.assert_not_called()
        self.assertIn("faltan", detalle)

    def test_error_de_red_no_muestra_el_token(self):
        err = requests.ConnectionError(f"Max retries exceeded with url: /bot{TOKEN}/sendMessage")
        with mock.patch.dict(os.environ, ENV), mock.patch.object(T.requests, "post", side_effect=err):
            ok, detalle = T.enviar("hola")
        self.assertFalse(ok)
        self.assertNotIn(TOKEN, detalle)
        self.assertNotIn("SECRETO", detalle)

    def test_ok_false_es_fallo(self):
        with mock.patch.dict(os.environ, ENV), \
             mock.patch.object(T.requests, "post", return_value=respuesta({"ok": False, "description": "Bad Request: chat not found"}, 400)):
            ok, detalle = T.enviar("hola")
        self.assertFalse(ok)
        self.assertIn("chat not found", detalle)
        self.assertNotIn(TOKEN, detalle)

    def test_texto_largo_se_recorta(self):
        with mock.patch.dict(os.environ, ENV), \
             mock.patch.object(T.requests, "post", return_value=respuesta({"ok": True, "result": {}})) as post:
            T.enviar("x" * 10000)
        self.assertLessEqual(len(post.call_args.kwargs["json"]["text"]), T.LIMITE)


class AvisoSync(unittest.TestCase):
    def _veredicto(self, texto):
        f = tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8")
        f.write(texto)
        f.close()
        self.addCleanup(os.remove, f.name)
        return f.name

    def test_motivos_reales_del_107_sin_metricas(self):
        m = S.motivos(self._veredicto(VEREDICTO_107))
        self.assertEqual(len(m), 2)
        self.assertIn("659 filas nuevas", m[0])
        self.assertTrue(all("Dias desde" not in x for x in m))

    def test_mensaje_con_pr_y_corrida(self):
        txt = S.armar("https://run/1", "https://pr/107", self._veredicto(VEREDICTO_107))
        self.assertIn("revision manual", txt)
        self.assertIn("https://pr/107", txt)
        self.assertIn("https://run/1", txt)
        self.assertNotIn("PRUEBA", txt)

    def test_sin_veredicto_avisa_igual(self):
        txt = S.armar("https://run/1", None, "/no/existe.md")
        self.assertIn("fallo un paso", txt)
        self.assertNotIn("PR:", txt)

    def test_prueba_se_marca_como_prueba(self):
        self.assertIn("PRUEBA", S.armar("https://run/1", prueba=True))


class AlertaConTelegram(unittest.TestCase):
    def _correr(self, meta, abierto, argv=()):
        gh = mock.MagicMock()
        gh.issue_abierto.return_value = abierto
        gh.abrir.return_value = {"number": 99, "html_url": "https://github.com/o/r/issues/99"}
        with mock.patch.object(A, "leer_meta", return_value=meta), \
             mock.patch.object(A, "GitHub", return_value=gh), \
             mock.patch.object(A, "enviar_telegram", return_value=(True, "enviado")) as tg, \
             mock.patch.dict(os.environ, {"GITHUB_TOKEN": "x", "GITHUB_REPOSITORY": "o/r"}), \
             mock.patch.object(sys, "argv", ["alerta_datos_viejos.py", *argv]), \
             mock.patch("builtins.print"):
            codigo = A.main()
        return codigo, gh, tg

    def test_abre_issue_y_avisa_con_link(self):
        codigo, gh, tg = self._correr("2020-01-01T00:00:00Z", None)
        self.assertEqual(codigo, 1)
        tg.assert_called_once()
        self.assertIn("datos viejos", tg.call_args.args[0])
        self.assertIn("issues/99", tg.call_args.args[0])

    def test_issue_ya_abierto_no_repite_el_aviso(self):
        _, gh, tg = self._correr("2020-01-01T00:00:00Z", {"number": 7})
        gh.comentar.assert_called_once()
        tg.assert_not_called()

    def test_al_cerrar_avisa_que_se_resolvio(self):
        _, gh, tg = self._correr(datetime.now(timezone.utc).isoformat(), {"number": 7})
        gh.cerrar.assert_called_once()
        tg.assert_called_once()
        self.assertIn("al dia", tg.call_args.args[0])

    def test_al_dia_sin_issue_no_avisa(self):
        _, _, tg = self._correr(datetime.now(timezone.utc).isoformat(), None)
        tg.assert_not_called()

    def test_prueba_telegram_no_toca_issues(self):
        codigo, gh, tg = self._correr("2020-01-01T00:00:00Z", None, ["--prueba-telegram"])
        self.assertEqual(codigo, 0)
        tg.assert_called_once()
        self.assertIn("Prueba", tg.call_args.args[0])
        gh.issue_abierto.assert_not_called()
        gh.abrir.assert_not_called()

    def test_telegram_caido_no_cambia_el_resultado(self):
        gh = mock.MagicMock()
        gh.issue_abierto.return_value = None
        gh.abrir.return_value = {"number": 99}
        with mock.patch.object(A, "leer_meta", return_value="2020-01-01T00:00:00Z"), \
             mock.patch.object(A, "GitHub", return_value=gh), \
             mock.patch.object(A, "enviar_telegram", return_value=(False, "error de red (ConnectionError)")), \
             mock.patch.dict(os.environ, {"GITHUB_TOKEN": "x", "GITHUB_REPOSITORY": "o/r"}), \
             mock.patch.object(sys, "argv", ["alerta_datos_viejos.py"]), \
             mock.patch("builtins.print"):
            self.assertEqual(A.main(), 1)
        gh.abrir.assert_called_once()


if __name__ == "__main__":
    unittest.main()
