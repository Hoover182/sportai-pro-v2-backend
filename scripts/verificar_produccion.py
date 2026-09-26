#!/usr/bin/env python3
"""
Criterio E del auto-merge: despues de un merge del sync, confirmar que
produccion (Render) sirve los datos nuevos. Sondea /futbol/meta hasta que
datos_actualizados_en coincida con el del datos_meta.json mergeado, y
despues exige que /futbol/partidos-hoy responda 200 con una lista.

En modo observacion NO lo llama el workflow (no hay merge automatico que
verificar); existe para activarse junto con el merge real. Se puede correr
a mano despues de un merge manual.

Uso: python scripts/verificar_produccion.py [--esperado ISO] [--timeout-min 20]
Exit 0 = produccion al dia; 1 = no se actualizo a tiempo o respondio mal.
"""
import argparse
import json
import os
import sys
import time

import requests

BACKEND_URL = "https://sportai-pro-v2-backend.onrender.com"
META_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "services", "datos_meta.json")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--esperado", help="datos_actualizados_en esperado; por defecto el de app/services/datos_meta.json")
    p.add_argument("--timeout-min", type=float, default=20)
    p.add_argument("--intervalo-seg", type=float, default=30)
    args = p.parse_args()

    esperado = args.esperado
    if not esperado:
        with open(META_PATH, encoding="utf-8") as f:
            esperado = json.load(f)["datos_actualizados_en"]

    limite = time.time() + args.timeout_min * 60
    visto = None
    while True:
        try:
            r = requests.get(f"{BACKEND_URL}/futbol/meta", timeout=60)
            visto = r.json().get("datos_actualizados_en") if r.status_code == 200 else f"HTTP {r.status_code}"
        except (requests.RequestException, ValueError) as e:
            visto = f"{type(e).__name__}"
        if visto == esperado:
            break
        if time.time() >= limite:
            print(f"PRODUCCION NO SE ACTUALIZO en {args.timeout_min:g} min: /futbol/meta dice {visto!r}, se esperaba {esperado!r}")
            sys.exit(1)
        time.sleep(args.intervalo_seg)

    try:
        r = requests.get(f"{BACKEND_URL}/futbol/partidos-hoy", timeout=120)
        partidos = r.json().get("partidos") if r.status_code == 200 else None
    except (requests.RequestException, ValueError) as e:
        print(f"/futbol/partidos-hoy fallo: {type(e).__name__}: {e}")
        sys.exit(1)
    if not isinstance(partidos, list):
        print(f"/futbol/partidos-hoy respondio HTTP {r.status_code} sin lista de partidos")
        sys.exit(1)
    print(f"PRODUCCION AL DIA: /futbol/meta = {esperado}, /futbol/partidos-hoy = {len(partidos)} partido(s)")


if __name__ == "__main__":
    main()
