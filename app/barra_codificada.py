"""Nombres de equipo con "/" en las rutas /{local}/{visitante}.

Hay equipos cuyo nombre lleva una barra ("Bodo/Glimt", "Tirol/CEFAT",
"CFRJ / Marica"). El frontend ya los manda codificados (encodeURIComponent
-> "Bodo%2FGlimt"), pero Starlette decodifica el %2F ANTES de rutear: la
ruta queda con un segmento de mas ("/partido/Bodo/Glimt/Borussia Dortmund")
y responde 404.

Arreglo en dos partes, sin tocar los endpoints uno por uno:
- BarraCodificadaMiddleware: antes de rutear, toma la ruta cruda
  (raw_path, sin decodificar) y cambia cada %2F por SENTINELA, asi la barra
  queda dentro de su segmento.
- RutaConBarra: route_class del router que devuelve SENTINELA a "/" en los
  path params, asi cada endpoint recibe el nombre real del equipo.
Una barra SIN codificar sigue partiendo el segmento (no hay forma de saber
donde termina cada nombre).
"""
from urllib.parse import unquote

from fastapi.routing import APIRoute

# Barra de division (U+2215): no aparece en ningun nombre del CSV.
SENTINELA = "∕"


class BarraCodificadaMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            raw = scope.get("raw_path") or b""
            if b"%2f" in raw.lower():
                ruta = raw.split(b"?", 1)[0].decode("latin-1")
                segmentos = [
                    unquote(s.replace("%2F", SENTINELA).replace("%2f", SENTINELA))
                    for s in ruta.split("/")
                ]
                scope = dict(scope, path="/".join(segmentos))
        await self.app(scope, receive, send)


class RutaConBarra(APIRoute):
    def matches(self, scope):
        match, child_scope = super().matches(scope)
        params = child_scope.get("path_params")
        if params:
            child_scope["path_params"] = {
                k: v.replace(SENTINELA, "/") if isinstance(v, str) else v
                for k, v in params.items()
            }
        return match, child_scope
