"""Chat IA (chat_ia) con grok-4.3: pedido a xAI, id de cache derivado del
contexto, fecha de hoy, instrucciones corregidas, mensaje amable ante
cualquier falla y linea CHAT en el log. xAI esta simulado: estas pruebas no
gastan creditos.
Correr desde backend/: python -m unittest discover -s tests -v"""
import io
import os
import sys
import unittest
from contextlib import redirect_stdout
from unittest import mock

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app", "services"))
import futbol_service as F

MENSAJES = [{"role": "assistant", "text": "Hola! Soy SportAI Pro"},
            {"role": "user", "text": "¿Ambos marcan?"},
            {"role": "otro", "text": "se descarta"}]


def respuesta(status=200, texto="⚽ Ambos marcan SI 52.7% ✅", usage=None, cuerpo=None):
    r = mock.Mock(status_code=status, text="error de xAI")
    r.json.return_value = cuerpo if cuerpo is not None else {
        "choices": [{"message": {"content": texto}, "finish_reason": "stop"}],
        "usage": usage if usage is not None else {
            "prompt_tokens": 7450, "prompt_tokens_details": {"cached_tokens": 7424},
            "completion_tokens": 180, "completion_tokens_details": {"reasoning_tokens": 700},
            "cost_in_usd_ticks": 40000000}}
    return r


def chatear(resp=None, excepcion=None, clave="xai-prueba", contexto="=== PARTIDO: A vs B ===\nDATOS"):
    out = io.StringIO()
    with mock.patch.dict(os.environ, {"XAI_API_KEY": clave}), \
            mock.patch("requests.post", side_effect=excepcion, return_value=resp) as post, redirect_stdout(out):
        res = F.chat_ia(MENSAJES, contexto)
    return res, post, out.getvalue()


class PedidoAXai(unittest.TestCase):
    def test_modelo_razonamiento_tokens_y_mensajes(self):
        (texto, err), post, log = chatear(respuesta())
        self.assertEqual((texto, err), ("⚽ Ambos marcan SI 52.7% ✅", None))
        args, kw = post.call_args
        self.assertEqual(args[0], "https://api.x.ai/v1/chat/completions")
        body = kw["json"]
        self.assertEqual((body["model"], body["reasoning_effort"], body["max_tokens"]), ("grok-4.3", "low", 2000))
        self.assertEqual(kw["timeout"], 30)
        self.assertEqual([m["role"] for m in body["messages"]], ["system", "assistant", "user"])
        self.assertEqual(body["messages"][2]["content"], "¿Ambos marcan?")
        self.assertEqual(kw["headers"]["Authorization"], "Bearer xai-prueba")

    def test_clave_con_espacios_saltos_o_comillas(self):
        for clave in (" xai-prueba", "xai-prueba\n", "xai-prueba\r\n", '"xai-prueba"', "'xai-prueba' ", ' " xai-prueba " '):
            with self.subTest(clave=repr(clave)):
                (texto, err), post, _ = chatear(respuesta(), clave=clave)
                self.assertIsNone(err)
                self.assertEqual(post.call_args.kwargs["headers"]["Authorization"], "Bearer xai-prueba")

    def test_clave_solo_espacios_es_clave_faltante(self):
        (texto, err), post, log = chatear(respuesta(), clave="  \n ")
        post.assert_not_called()
        self.assertIn("motivo=falta XAI_API_KEY", log)

    def test_instrucciones_corregidas_y_fecha_de_hoy(self):
        _, post, _ = chatear(respuesta())
        system = post.call_args.kwargs["json"]["messages"][0]["content"]
        self.assertIn("FORMATO OBLIGATORIO", system)
        self.assertIn("EXCEPCION, CON PRIORIDAD SOBRE LA REGLA 9", system)
        self.assertNotIn("hace casi 2 anos, en noviembre de 2024", system)
        self.assertRegex(system, r"\n\nFECHA DE HOY: \d{4}-\d{2}-\d{2}\n=== PARTIDO: A vs B ===")

    def test_sin_contexto_no_agrega_fecha(self):
        self.assertNotIn("FECHA DE HOY", F._chat_system("", hoy="2026-10-01"))

    def test_id_de_cache_estable_por_contexto(self):
        ids = []
        for ctx in ("PARTIDO A", "PARTIDO A", "PARTIDO B"):
            _, post, _ = chatear(respuesta(), contexto=ctx)
            ids.append(post.call_args.kwargs["headers"]["x-grok-conv-id"])
        self.assertEqual(ids[0], ids[1])
        self.assertNotEqual(ids[0], ids[2])
        self.assertRegex(ids[0], r"^chat-[0-9a-f]{32}$")


class Log(unittest.TestCase):
    def test_linea_con_tokens_y_costo_real(self):
        _, _, log = chatear(respuesta())
        self.assertIn("CHAT proveedor=xai modelo=grok-4.3 entrada=7450 cache=7424 salida=180 razonamiento=700 "
                      "costo_usd=0.00400", log)

    def test_costo_calculado_si_no_viene_el_de_xai(self):
        _, _, log = chatear(respuesta(usage={"prompt_tokens": 1000000, "completion_tokens": 0}))
        self.assertIn("costo_usd=1.25000", log)


class FallaAmable(unittest.TestCase):
    def comprobar(self, log_esperado, **kw):
        (texto, err), post, log = chatear(**kw)
        self.assertIsNone(texto)
        self.assertEqual(err, F.CHAT_ERROR_AMABLE)
        self.assertIn(log_esperado, log)
        return post

    def test_sin_clave_no_llama(self):
        self.comprobar("motivo=falta XAI_API_KEY", clave="").assert_not_called()

    def test_errores_http(self):
        for status in (401, 402, 403, 429, 500, 503):
            with self.subTest(status=status):
                self.comprobar(f"motivo=HTTP {status}", resp=respuesta(status=status))

    def test_timeout_y_red(self):
        self.comprobar("motivo=sin respuesta (Timeout)", excepcion=requests.exceptions.Timeout("lento"))
        self.comprobar("motivo=sin respuesta (ConnectionError)", excepcion=requests.exceptions.ConnectionError("caido"))

    def test_respuesta_vacia_o_rara(self):
        self.comprobar("motivo=respuesta vacia", resp=respuesta(texto="   "))
        self.comprobar("motivo=respuesta inesperada", resp=respuesta(cuerpo={"choices": []}))

    def test_no_expone_el_error_tecnico(self):
        (texto, err), _, _ = chatear(resp=respuesta(status=402))
        self.assertNotIn("xAI", err)
        self.assertNotIn("402", err)


if __name__ == "__main__":
    unittest.main()
