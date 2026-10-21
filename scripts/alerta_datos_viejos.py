#!/usr/bin/env python3
"""
Alerta de datos viejos en produccion: lee /futbol/meta y, si
datos_actualizados_en tiene mas de UMBRAL_HORAS (o produccion no responde),
abre un issue en el repo, con un mail de GitHub al dueno. Si ya hay uno
abierto, le agrega un comentario con la medicion del dia. Cuando los datos
vuelven a estar al dia, cierra el issue.

Motivo: entre el 16 y el 21/10/2026 los syncs quedaron trabados en
revision manual (#81, #83, #84, #85) y produccion sirvio datos del 16/10
durante 5 dias, sin que nadie se enterara hasta una captura de pantalla
("Top picks del dia" con un partido de otro dia).

Uso (lo corre .github/workflows/alerta-datos-viejos.yml):
  python scripts/alerta_datos_viejos.py [--dry-run]
Necesita GITHUB_TOKEN y GITHUB_REPOSITORY (los pone Actions) salvo en --dry-run.
"""
import argparse
import json
import os
import sys
import time

import requests

BACKEND_URL = "https://sportai-pro-v2-backend.onrender.com"
UMBRAL_HORAS = 36
ETIQUETA = "alerta-datos-viejos"
TITULO = "Produccion con datos viejos"
INTENTOS = 3          # Render puede estar dormido: el primer pedido tarda
TIMEOUT_S = 90


def leer_meta(intentos=INTENTOS, espera_s=20):
    """datos_actualizados_en de produccion (str ISO), o None si no responde."""
    for i in range(intentos):
        try:
            r = requests.get(f"{BACKEND_URL}/futbol/meta", timeout=TIMEOUT_S)
            if r.status_code == 200:
                return r.json().get("datos_actualizados_en")
        except (requests.RequestException, ValueError):
            pass
        if i < intentos - 1:
            time.sleep(espera_s)
    return None


def evaluar(datos_actualizados_en, ahora, umbral_horas=UMBRAL_HORAS):
    """(alerta, horas, mensaje). alerta=True si los datos tienen mas de
    umbral_horas o no se pudo leer la fecha."""
    from datetime import datetime
    if not datos_actualizados_en:
        return True, None, "Produccion no respondio /futbol/meta (o vino sin datos_actualizados_en)."
    try:
        actualizado = datetime.fromisoformat(datos_actualizados_en.replace("Z", "+00:00"))
    except ValueError:
        return True, None, f"datos_actualizados_en con formato invalido: {datos_actualizados_en!r}"
    horas = (ahora - actualizado).total_seconds() / 3600
    if horas > umbral_horas:
        return True, horas, (f"Los datos de produccion son del {datos_actualizados_en} "
                             f"(hace {horas:.0f} h, umbral {umbral_horas} h).")
    return False, horas, f"Datos al dia: {datos_actualizados_en} (hace {horas:.0f} h)."


def cuerpo_issue(mensaje):
    return (f"{mensaje}\n\n"
            "Lo mas probable es que los syncs de analista-futbol esten trabados en revision manual "
            "(PRs \"Sync datos desde analista-futbol\" abiertos) o que el cron de analista no haya corrido.\n\n"
            "Que revisar:\n"
            "1. PRs de sync abiertos y el comentario del veredicto (motivo del MANUAL).\n"
            "2. Ultimo commit del cron en analista-futbol.\n"
            "3. `/futbol/meta` en produccion.\n\n"
            "Este issue se cierra solo cuando los datos vuelven a estar al dia "
            "(workflow alerta-datos-viejos).")


class GitHub:
    def __init__(self, token, repo):
        self.base = f"https://api.github.com/repos/{repo}"
        self.h = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}

    def _req(self, metodo, ruta, **kw):
        r = requests.request(metodo, self.base + ruta, headers=self.h, timeout=30, **kw)
        r.raise_for_status()
        return r.json() if r.content else None

    def issue_abierto(self):
        abiertos = self._req("GET", "/issues", params={"state": "open", "labels": ETIQUETA, "per_page": 10})
        abiertos = [i for i in abiertos if "pull_request" not in i]
        return abiertos[0] if abiertos else None

    def abrir(self, cuerpo):
        try:
            self._req("POST", "/labels", json={"name": ETIQUETA, "color": "d73a4a"})
        except requests.HTTPError:
            pass  # ya existe
        return self._req("POST", "/issues", json={"title": TITULO, "body": cuerpo, "labels": [ETIQUETA]})

    def comentar(self, numero, texto):
        self._req("POST", f"/issues/{numero}/comments", json={"body": texto})

    def cerrar(self, numero, texto):
        self.comentar(numero, texto)
        self._req("PATCH", f"/issues/{numero}", json={"state": "closed", "state_reason": "completed"})


def main():
    from datetime import datetime, timezone
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="solo medir e imprimir, sin tocar issues")
    args = ap.parse_args()

    meta = leer_meta()
    alerta, horas, mensaje = evaluar(meta, datetime.now(timezone.utc))
    print(("ALERTA: " if alerta else "OK: ") + mensaje)
    if args.dry_run:
        return 1 if alerta else 0

    gh = GitHub(os.environ["GITHUB_TOKEN"], os.environ["GITHUB_REPOSITORY"])
    abierto = gh.issue_abierto()
    if alerta and abierto is None:
        nuevo = gh.abrir(cuerpo_issue(mensaje))
        print(f"Issue abierto: #{nuevo['number']}")
    elif alerta:
        gh.comentar(abierto["number"], f"Sigue igual: {mensaje}")
        print(f"Comentario en #{abierto['number']}")
    elif abierto is not None:
        gh.cerrar(abierto["number"], f"Resuelto: {mensaje}")
        print(f"Issue #{abierto['number']} cerrado")
    # Exit 1 en alerta: el run queda en rojo en Actions, ademas del issue.
    return 1 if alerta else 0


if __name__ == "__main__":
    sys.exit(main())
