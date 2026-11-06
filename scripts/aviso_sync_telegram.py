#!/usr/bin/env python3
"""
Aviso por Telegram cuando la corrida del sync (sync-check.yml) termina en
rojo: veredicto de revision manual, falla de un script o produccion que no
se actualizo despues del merge. Lo llama el ultimo paso del workflow con
`if: failure()`.

Por que: los syncs quedaron trabados en revision manual del 16 al 21/10, del
22 al 29/10 y del 03 al 06/11/2026 sin que nadie lo viera a tiempo.

Uso:
  python scripts/aviso_sync_telegram.py --run-url URL [--pr-url URL] [--veredicto /tmp/veredicto.md]
"""
import argparse
import os
import sys

from avisar_telegram import enviar


def motivos(ruta):
    """Lineas '- ...' del comentario del veredicto, antes de las metricas."""
    if not ruta or not os.path.exists(ruta):
        return []
    out = []
    with open(ruta, encoding="utf-8") as fh:
        for linea in fh:
            if linea.startswith("<details>"):
                break
            linea = linea.strip()
            if linea.startswith("- "):
                out.append(linea.replace("**", "")[:300])
    return out


def armar(run_url, pr_url=None, ruta_veredicto=None, prueba=False):
    m = motivos(ruta_veredicto)
    partes = ["🧪 PRUEBA del aviso del sync (no paso nada real)." if prueba else
              "⛔ SportAI: el sync de analista-futbol termino en rojo y los datos de produccion NO se actualizaron solos."]
    if m:
        partes.append("Motivos (revision manual):\n" + "\n".join(m[:5]))
    else:
        partes.append("Sin veredicto: fallo un paso de la corrida (ver el log).")
    if pr_url:
        partes.append(f"PR: {pr_url}")
    partes.append(f"Corrida: {run_url}")
    return "\n\n".join(partes)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-url", required=True)
    ap.add_argument("--pr-url")
    ap.add_argument("--veredicto")
    ap.add_argument("--prueba", action="store_true")
    a = ap.parse_args()
    ok, detalle = enviar(armar(a.run_url, a.pr_url, a.veredicto, a.prueba))
    print(f"Telegram: {detalle}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
