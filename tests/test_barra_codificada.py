"""Nombres de equipo con "/" (Bodo/Glimt) en /futbol/{...}/{local}/{visitante}.
Antes del fix, "Bodo%2FGlimt" llegaba decodificado al ruteo y daba 404.
Llama a main.app por ASGI (sin httpx) con el servicio simulado: no carga el
CSV ni llama a ninguna API.
Correr desde backend/: python -m unittest discover -s tests -v"""
import asyncio
import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app  # noqa: E402
from app.services import futbol_service  # noqa: E402


def _get(raw_path, headers=None):
    """GET por ASGI con la ruta cruda tal como la manda el navegador.
    Devuelve (status, headers, cuerpo_json)."""
    ruta, _, query = raw_path.partition("?")
    from urllib.parse import unquote
    scope = {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
        "method": "GET", "scheme": "http", "root_path": "",
        "path": unquote(ruta), "raw_path": ruta.encode("latin-1"),
        "query_string": query.encode("latin-1"),
        "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
        "client": ("127.0.0.1", 1), "server": ("testserver", 80),
    }
    salida = {"status": None, "headers": {}, "cuerpo": b""}

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(msg):
        if msg["type"] == "http.response.start":
            salida["status"] = msg["status"]
            salida["headers"] = {k.decode().lower(): v.decode() for k, v in msg["headers"]}
        elif msg["type"] == "http.response.body":
            salida["cuerpo"] += msg.get("body", b"")

    asyncio.run(app(scope, receive, send))
    return salida["status"], salida["headers"], json.loads(salida["cuerpo"] or b"null")


def _eco(local, visitante, casa=None):
    return {"local": local, "visitante": visitante, "casa": casa}, None


class TestNombresConBarra(unittest.TestCase):
    def setUp(self):
        p = mock.patch.object(futbol_service, "get_analisis_partido", side_effect=_eco)
        self.servicio = p.start()
        self.addCleanup(p.stop)

    def test_barra_en_el_local(self):
        status, _, cuerpo = _get("/futbol/partido/Bodo%2FGlimt/Borussia%20Dortmund")
        self.assertEqual(status, 200)
        self.assertEqual((cuerpo["local"], cuerpo["visitante"]), ("Bodo/Glimt", "Borussia Dortmund"))

    def test_barra_en_el_visitante_y_minuscula(self):
        status, _, cuerpo = _get("/futbol/partido/Borussia%20Dortmund/Bodo%2fGlimt")
        self.assertEqual(status, 200)
        self.assertEqual((cuerpo["local"], cuerpo["visitante"]), ("Borussia Dortmund", "Bodo/Glimt"))

    def test_barra_con_espacios_y_tilde_en_ambos(self):
        status, _, cuerpo = _get("/futbol/partido/CFRJ%20%2F%20Maric%C3%A1/Tirol%2FCEFAT")
        self.assertEqual(status, 200)
        self.assertEqual((cuerpo["local"], cuerpo["visitante"]), ("CFRJ / Maricá", "Tirol/CEFAT"))

    def test_query_string_se_conserva(self):
        status, _, cuerpo = _get("/futbol/partido/Bodo%2FGlimt/Borussia%20Dortmund?casa=betano")
        self.assertEqual(status, 200)
        self.assertEqual(cuerpo["casa"], "betano")

    def test_nombre_normal_sin_cambios(self):
        status, _, cuerpo = _get("/futbol/partido/Boca%20Juniors/River%20Plate")
        self.assertEqual(status, 200)
        self.assertEqual((cuerpo["local"], cuerpo["visitante"]), ("Boca Juniors", "River Plate"))
        self.servicio.assert_called_once_with("Boca Juniors", "River Plate", casa="1xbet")

    def test_barra_sin_codificar_sigue_siendo_404(self):
        status, _, _ = _get("/futbol/partido/Bodo/Glimt/Borussia%20Dortmund")
        self.assertEqual(status, 404)
        self.servicio.assert_not_called()

    def test_cors_sigue_respondiendo(self):
        status, headers, _ = _get("/futbol/partido/Bodo%2FGlimt/Borussia%20Dortmund",
                                  headers={"Origin": "https://dist-phi-steel-41.vercel.app"})
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("access-control-allow-origin"), "*")

    def test_ruta_sin_parametros(self):
        status, _, cuerpo = _get("/")
        self.assertEqual(status, 200)
        self.assertEqual(cuerpo, {"status": "SportAI Pro API running"})


if __name__ == "__main__":
    unittest.main()
