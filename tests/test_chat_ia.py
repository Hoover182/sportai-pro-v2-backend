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

    def test_reglas_de_calidad_del_02_10(self):
        system = F._chat_system("CTX", hoy="2026-10-02")
        for fragmento in ("ni V=4 E=1 D=0, ni GF=1.8 GC=0.4",                       # sin notacion cruda
                          "elegi la linea mas cercana a la proyeccion del modelo",     # conclusion O/U coherente
                          "nunca una doble oportunidad como X2 o 1X",                  # 1X2 responde quien gana
                          "Usa esta excepcion SOLO si no hay NINGUN dato relacionado",  # no-dato acotado
                          "E) RESPALDO"):                                              # al menos 2 datos
            self.assertIn(fragmento, system)

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


DATOS = os.path.join(os.path.dirname(__file__), "datos")
# Contextos reales del 02/10 (mismo armado que el frontend publicado; no traen
# las lineas JUGADORES, que el frontend agrega cuando hay datos de jugadores).
CTX_INTER = open(os.path.join(DATOS, "chat_contexto_internacional_once_caldas.txt"), encoding="utf-8").read()
CTX_CALI = open(os.path.join(DATOS, "chat_contexto_cali_valledupar.txt"), encoding="utf-8").read()
CIERRE = "\nEstos datos son meramente estadisticos basados en modelos matematicos."


def sin_dato(respuesta, preguntas, contexto):
    mensajes = []
    for p in preguntas:
        mensajes += [{"role": "user", "text": p}, {"role": "assistant", "text": "..."}]
    return F._chat_sin_dato(respuesta, mensajes[:-1], contexto)


class VigilanciaSinDato(unittest.TestCase):
    """Respuestas reales de grok-4.3 en las pruebas del 01-02/10."""

    def test_falso_sin_dato_original_es_sospechoso(self):
        # Internacional, 01/10: el pick de tarjetas tenia datos y dijo que no.
        d = sin_dato("🔍 No tengo datos de por qué Over 1.5 tarjetas (Internacional de Bogota) está en los Top Picks "
                     "para este partido." + CIERRE,
                     ["¿Por qué Over 1.5 tarjetas (Internacional de Bogota) está en los Top Picks?"], CTX_INTER)
        self.assertEqual((d["veredicto"], d["tema"], d["evidencia"]), ("sospechoso", "tarjetas", "over/under tarjetas"))
        self.assertEqual(d["partido"], "Internacional de Bogota vs Once Caldas (Liga Colombia)")

    def test_atajadas_con_top_pick_de_atajadas_es_sospechoso(self):
        # El contexto trae "Over 1.5 atajadas (Internacional de Bogota) 83.2%" en TOP PICKS IA.
        d = sin_dato("No tengo datos de atajadas del arquero de Internacional de Bogota para este partido." + CIERRE,
                     ["¿Cuántas atajadas va a hacer el arquero de Internacional de Bogota?"], CTX_INTER)
        self.assertEqual((d["veredicto"], d["tema"], d["evidencia"]), ("sospechoso", "atajadas", "top picks ia"))

    def test_atajadas_sin_ningun_dato_es_legitimo(self):
        d = sin_dato("No tengo datos de atajadas del arquero de Deportivo Cali para este partido." + CIERRE,
                     ["¿Cuántas atajadas va a hacer el arquero de Deportivo Cali?"], CTX_CALI)
        self.assertEqual((d["veredicto"], d["tema"], d["evidencia"]), ("legitimo", "atajadas", "-"))

    def test_jugadores_con_la_linea_de_produccion(self):
        ctx = CTX_CALI + "\nJUGADORES Deportivo Cali: A. Perez [Attacker] G/p=0.3 A/p=0.1 T/p=0.2 F/p=0.9"
        pregunta = ["¿Cuántos goles hace el goleador de Deportivo Cali?"]
        respuesta = "No tengo datos de ese jugador para este partido."
        self.assertEqual(sin_dato(respuesta, pregunta, ctx)["veredicto"], "sospechoso")
        self.assertEqual(sin_dato(respuesta, pregunta, CTX_CALI)["veredicto"], "legitimo")

    def test_respuesta_normal_no_es_sin_dato(self):
        self.assertIsNone(sin_dato("⚽ Ambos marcan SI 25.2%." + CIERRE, ["¿Ambos marcan?"], CTX_CALI))

    def test_variantes_de_la_frase(self):
        for respuesta, tema in (("No hay información sobre el árbitro del partido.", "arbitro"),
                                ("No aparece información sobre atajadas en el contexto.", "atajadas"),
                                ("No cuento con estadísticas de lesionados para este partido.", "bajas"),
                                ("No tengo datos para este partido.", "corners")):   # sin [X]: va a la pregunta
            with self.subTest(respuesta=respuesta):
                d = sin_dato(respuesta, ["¿Cuántos corners hay?"], CTX_CALI)
                self.assertEqual(d["tema"], tema)

    def test_repregunta_usa_la_pregunta_anterior(self):
        d = sin_dato("No tengo datos de eso para este partido.",
                     ["¿Cuántos corners esperás?", "¿Y el visitante?"], CTX_CALI)
        self.assertEqual((d["veredicto"], d["tema"]), ("sospechoso", "corners"))
        self.assertEqual(d["pregunta"], "¿Y el visitante?")

    def test_tema_desconocido_queda_sin_clasificar(self):
        d = sin_dato("No tengo datos del clima para este partido.", ["¿Va a llover?"], CTX_CALI)
        self.assertEqual((d["veredicto"], d["tema"]), ("sin_clasificar", "-"))

    def test_secciones_del_contexto(self):
        self.assertEqual(sin_dato("No tengo datos de nada.", ["?"], CTX_INTER)["secciones"], "10/10")
        self.assertEqual(sin_dato("No tengo datos de nada.", ["?"], CTX_CALI)["secciones"], "10/10")
        self.assertEqual(sin_dato("No tengo datos de nada.", ["?"], "=== PARTIDO: A vs B ===")["secciones"], "0/10")

    def test_cada_tema_encuentra_su_etiqueta_en_contextos_reales(self):
        # Si el frontend cambia una etiqueta, el contexto nuevo se vuelve a guardar en tests/datos y esto avisa.
        preguntas = {"tarjetas": "¿Cuántas tarjetas amarillas habrá?", "corners": "¿Cuántos córners esperás?",
                     "tiros": "¿Cuántos tiros al arco?", "ambos_marcan": "¿Ambos equipos marcan?",
                     "primer_tiempo": "¿Hay gol en el primer tiempo?", "cruces": "¿Cómo fueron los enfrentamientos?",
                     "forma": "¿Cómo viene la racha?", "ganador": "¿Quién gana?", "goles": "¿Over 2.5 goles?"}
        for tema, pregunta in preguntas.items():
            for ctx in (CTX_INTER, CTX_CALI):
                with self.subTest(tema=tema):
                    d = sin_dato("No tengo datos para este partido.", [pregunta], ctx)
                    self.assertEqual((d["tema"], d["veredicto"]), (tema, "sospechoso"))


class LogSinDato(unittest.TestCase):
    def test_linea_en_el_log_con_el_mismo_conv_que_la_cache(self):
        texto = "🔍 No tengo datos de atajadas del arquero de Deportivo Cali para este partido." + CIERRE
        (res, err), post, log = chatear(respuesta(texto=texto), contexto=CTX_CALI)
        self.assertEqual(res, texto)
        conv = post.call_args.kwargs["headers"]["x-grok-conv-id"]
        self.assertIn(f'CHAT SIN_DATO veredicto=legitimo tema=atajadas evidencia="-" '
                      f'partido="Deportivo Cali vs Alianza Valledupar (Liga Colombia)" secciones=10/10 conv={conv} '
                      f'frase="atajadas del arquero de deportivo cali para este partido" pregunta="¿Ambos marcan?"', log)
        self.assertLess(log.index("CHAT proveedor="), log.index("CHAT SIN_DATO"))

    def test_respuesta_normal_sin_linea(self):
        _, _, log = chatear(respuesta(), contexto=CTX_CALI)
        self.assertNotIn("SIN_DATO", log)

    def test_pregunta_en_una_linea_sin_comillas_y_recortada(self):
        out = io.StringIO()
        pregunta = 'Hola\n"che"  ' + "x" * 300
        with redirect_stdout(out):
            F._chat_log_sin_dato("No tengo datos.", [{"role": "user", "text": pregunta}], CTX_CALI, "chat-x")
        linea = out.getvalue()
        self.assertEqual(linea.count("\n"), 1)
        self.assertIn("pregunta=\"Hola 'che' xxx", linea)
        self.assertEqual(len(linea.split('pregunta="')[1].rstrip('"\n')), 150)

    def test_detector_roto_no_rompe_la_respuesta(self):
        with mock.patch.object(F, "_chat_sin_dato", side_effect=RuntimeError("bug")):
            (res, err), _, log = chatear(respuesta(texto="No tengo datos."))
        self.assertEqual((res, err), ("No tengo datos.", None))
        self.assertIn("CHAT SIN_DATO ERROR detector=RuntimeError", log)


if __name__ == "__main__":
    unittest.main()
