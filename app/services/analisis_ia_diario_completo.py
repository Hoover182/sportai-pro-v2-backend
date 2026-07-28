import requests
import pandas as pd
import json
import re
import time
from datetime import datetime, timedelta

import os
API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
import os
CSV = os.path.join(os.path.dirname(__file__), "futbol_partidos.csv")

def analizar_partido_ia(local, visitante, liga, fecha):
    headers = {
        "x-api-key": API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }

    prompt = f"""Eres un analista experto de futbol. Este partido AUN NO SE HA JUGADO: {local} vs {visitante} ({liga}), fecha: {fecha}.

Tu tarea:
1. Si necesitas informacion actual (lesiones, cambios de tecnico, motivacion especial, suspensiones, racha reciente, posicion en tabla) para dar un veredicto mas preciso sobre este partido FUTURO, usa la herramienta de busqueda web (maximo 2 busquedas).
2. Da un AJUSTE cualitativo con una explicacion CLARA Y JUSTIFICADA que un usuario no experto pueda entender. Explica el POR QUE del ajuste mencionando cosas concretas como: racha de victorias/derrotas reciente, forma del equipo, lesiones importantes, motivacion especial, posicion en la tabla, o estilo de juego (ofensivo/defensivo). MUY IMPORTANTE: Se breve en tu analisis (maximo 100 palabras de texto antes del JSON). Al FINAL de tu respuesta, SIEMPRE debes escribir el JSON en una sola linea, sin saltos de linea dentro del JSON, con esta estructura exacta y nada mas despues:

{{"ajuste_local": <numero entre -15 y 15>, "ajuste_visitante": <numero entre -15 y 15>, "explicacion": "<explicacion clara de 30 a 50 palabras que justifique el ajuste con datos concretos, ejemplo: Racing Montevideo llega invicto con 5 victorias consecutivas y buen momento ofensivo, mientras Cerro atraviesa un tramo irregular con 3 derrotas en sus ultimos 5 partidos y juega de forma muy defensiva>"}}"""

    payload = {
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 1000,
        "messages": [{"role": "user", "content": prompt}],
        "tools": [{"type": "web_search_20250305", "name": "web_search", "max_uses": 2}]
    }

    try:
        resp = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload, timeout=45)
        data = resp.json()
        texto_final = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                texto_final += block.get("text", "")

        # Extraer el JSON del texto de forma mas robusta
        # 1. Intentar encontrar bloque completo con regex tolerante a saltos de linea
        matches = re.findall(r'\{[\s\S]*?"ajuste_local"[\s\S]*?"explicacion"[\s\S]*?\}', texto_final)
        resultado = None
        for m in reversed(matches):
            try:
                resultado = json.loads(m)
                break
            except Exception:
                continue

        # 2. Si fallo, buscar el ultimo { hasta el ultimo } del texto completo
        if resultado is None:
            try:
                start = texto_final.rindex("{")
                end = texto_final.rindex("}") + 1
                resultado = json.loads(texto_final[start:end])
            except Exception:
                pass

        if resultado and "ajuste_local" in resultado:
            return resultado, None
        else:
            return None, "No se encontro JSON valido en la respuesta"
    except Exception as e:
        return None, str(e)


def main():
    df = pd.read_csv(CSV)
    df["fecha_dt"] = pd.to_datetime(df["fecha"], errors="coerce")

    # Asegurar columnas nuevas
    for col in ["ajuste_ia_local", "ajuste_ia_visitante", "ajuste_ia_explicacion", "ajuste_ia_fecha_calculo"]:
        if col not in df.columns:
            df[col] = None

    # Ventana ampliada: cubre desfase de zona horaria entre Colombia (UTC-5)
    # y las fechas del CSV. Toma desde 8 horas antes de ahora hasta el
    # final del dia siguiente, para capturar partidos que ya son "hoy"
    # en la zona horaria del partido aunque en Colombia figuren distinto.
    ahora = datetime.now()
    desde = ahora - timedelta(hours=8)
    hasta = (ahora + timedelta(days=1)).replace(hour=23, minute=59, second=59)

    partidos_hoy = df[
        (df["estado"] == "NS") &
        (df["fecha_dt"] >= desde) &
        (df["fecha_dt"] <= hasta)
    ]

    print(f"Partidos de hoy a procesar: {len(partidos_hoy)}")
    print()

    procesados = 0
    errores = 0
    for idx, row in partidos_hoy.iterrows():
        local = row["equipo_local"]
        visitante = row["equipo_visitante"]
        liga = row["liga"]
        fecha = row["fecha"]

        print(f"[{procesados+errores+1}/{len(partidos_hoy)}] {local} vs {visitante} ({liga})...")

        resultado, error = analizar_partido_ia(local, visitante, liga, fecha)

        if resultado:
            df.at[idx, "ajuste_ia_local"] = resultado.get("ajuste_local", 0)
            df.at[idx, "ajuste_ia_visitante"] = resultado.get("ajuste_visitante", 0)
            df.at[idx, "ajuste_ia_explicacion"] = resultado.get("explicacion", "")
            df.at[idx, "ajuste_ia_fecha_calculo"] = datetime.now().isoformat()
            print(f"  OK: ajuste_local={resultado.get('ajuste_local')} ajuste_visitante={resultado.get('ajuste_visitante')}")
            print(f"  Explicacion: {resultado.get('explicacion')}")
            procesados += 1
        else:
            print(f"  ERROR: {error}")
            errores += 1

        time.sleep(1)  # Evitar rate limits

    df = df.drop(columns=["fecha_dt"])
    df.to_csv(CSV, index=False, encoding="utf-8-sig")
    print(f"\nOK: {procesados} procesados, {errores} errores")


if __name__ == "__main__":
    main()
