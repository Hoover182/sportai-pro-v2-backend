#!/usr/bin/env python3
"""
Aviso por Telegram para cosas urgentes de produccion (datos viejos, sync
trabado en revision manual). Usa sendMessage de la API de bots con los
secretos TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID.

Nunca imprime el token: la URL lo lleva adentro, asi que los errores se
informan solo por tipo y codigo HTTP.

Uso:
  python scripts/avisar_telegram.py "texto"
  python scripts/avisar_telegram.py --archivo /tmp/mensaje.txt
Sale con 1 si no se pudo enviar (falta un secreto, error de red o la API
responde ok=false), para que se vea en el log; los workflows lo llaman de
forma que un fallo de Telegram no tape el resultado real de la corrida.
"""
import argparse
import os
import sys

import requests

API = "https://api.telegram.org/bot{token}/sendMessage"
LIMITE = 4000   # Telegram corta en 4096 caracteres


def enviar(texto, token=None, chat_id=None):
    """(ok, detalle). No lanza excepciones."""
    token = token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        return False, "faltan TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID"
    if len(texto) > LIMITE:
        texto = texto[: LIMITE - 20] + "\n[...recortado]"
    try:
        r = requests.post(API.format(token=token),
                          json={"chat_id": chat_id, "text": texto, "disable_web_page_preview": True},
                          timeout=30)
    except requests.RequestException as e:
        return False, f"error de red ({type(e).__name__})"
    try:
        js = r.json()
    except ValueError:
        return False, f"respuesta no JSON (HTTP {r.status_code})"
    if not js.get("ok"):
        return False, f"Telegram respondio ok=false (HTTP {r.status_code}): {js.get('description', '')}"
    res = js.get("result", {})
    return True, f"enviado: message_id={res.get('message_id')} date={res.get('date')}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("texto", nargs="?")
    ap.add_argument("--archivo")
    a = ap.parse_args()
    if a.archivo:
        with open(a.archivo, encoding="utf-8") as fh:
            texto = fh.read()
    else:
        texto = a.texto or ""
    if not texto.strip():
        print("Telegram: mensaje vacio, no se envia")
        return 1
    ok, detalle = enviar(texto)
    print(f"Telegram: {detalle}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
