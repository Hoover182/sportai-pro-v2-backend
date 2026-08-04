import requests
import pandas as pd
import json
import os
import re
import unicodedata
import time
from datetime import datetime

API_KEY = "7be9c4250da301a68726beedbe2b382a"
headers = {"x-apisports-key": API_KEY}

CSV = "C:/Users/hoove/OneDrive/Documentos/analista_futbol/futbol_partidos.csv"
CACHE_DIR = "app/services/jugadores_data"

LIGA_IDS = {
    "Liga Profesional Argentina": (128, "Argentina"), "Brasileirao": (71, "Brazil"),
    "Brasileirao Serie A": (71, "Brazil"),
    "Liga Colombia": (239, "Colombia"), "Primera Division Chile": (265, "Chile"),
    "Primera Division Uruguay": (268, "Uruguay"), "Primera Division Peru": (281, "Peru"),
    "Liga Pro Ecuador": (242, "Ecuador"), "Primera Division Venezuela": (337, "Venezuela"),
    "Primera Division Bolivia": (344, "Bolivia"), "Division Profesional Paraguay": (250, "Paraguay"),
    "Liga MX": (262, "Mexico"), "MLS": (253, "USA"),
    "Copa Libertadores": (13, None), "Copa Sudamericana": (11, None), "Recopa Sudamericana": (12, None),
    "Copa Argentina": (130, "Argentina"), "Copa Chile": (267, "Chile"), "Copa Colombia": (241, "Colombia"),
    "Copa Uruguay": (270, "Uruguay"), "Copa do Brasil": (73, "Brazil"),
}

def limpiar_busqueda(nombre):
    nfkd = unicodedata.normalize("NFKD", nombre)
    sin_acentos = "".join(c for c in nfkd if not unicodedata.combining(c))
    limpio = re.sub(r"[^a-zA-Z0-9 ]", " ", sin_acentos)
    return re.sub(r"\s+", " ", limpio).strip()

df = pd.read_csv(CSV)
principales = df.groupby("equipo_local")["liga"].agg(lambda x: x.value_counts().index[0])

archivos_vacios = []
for archivo in os.listdir(CACHE_DIR):
    if not archivo.endswith(".json") or archivo.startswith("fixture_"):
        continue
    try:
        with open(os.path.join(CACHE_DIR, archivo), "r", encoding="utf-8") as f:
            data = json.load(f)
        if len(data.get("jugadores", [])) == 0:
            equipo = archivo.replace(".json", "")
            archivos_vacios.append(equipo)
    except Exception:
        pass

print(f"Equipos a re-descargar: {len(archivos_vacios)}")

procesados = 0
sin_team = 0
sin_liga_pais = 0
errores = 0

for equipo in archivos_vacios:
    liga = principales.get(equipo)
    if liga is None or liga not in LIGA_IDS:
        errores += 1
        continue
    liga_id, pais_esperado = LIGA_IDS[liga]
    busqueda = limpiar_busqueda(equipo)

    try:
        resp_team = requests.get(
            "https://v3.football.api-sports.io/teams",
            headers=headers, params={"search": busqueda}, timeout=15
        )
        data_team = resp_team.json()
        candidatos = data_team.get("response", [])
        if not candidatos:
            sin_team += 1
            continue

        # Filtrar por pais si lo conocemos
        team_id = None
        if pais_esperado:
            for c in candidatos:
                if c["team"]["country"] == pais_esperado:
                    team_id = c["team"]["id"]
                    break
        if team_id is None:
            team_id = candidatos[0]["team"]["id"]  # fallback al primero

        # Verificar que ese team_id tenga stats en esta liga/temporada
        todos_jugadores = []
        pagina = 1
        total_paginas = 1
        while pagina <= total_paginas and pagina <= 5:
            resp_players = requests.get(
                "https://v3.football.api-sports.io/players",
                headers=headers,
                params={"team": team_id, "league": liga_id, "season": 2026, "page": pagina}
            )
            data_players = resp_players.json()
            todos_jugadores.extend(data_players.get("response", []))
            paging = data_players.get("paging", {})
            total_paginas = paging.get("total", 1)
            pagina += 1

        if not todos_jugadores:
            sin_liga_pais += 1
            continue

        archivo_cache = os.path.join(CACHE_DIR, f"{equipo.replace('/', '_')}.json")
        with open(archivo_cache, "w", encoding="utf-8") as f:
            json.dump({
                "equipo": equipo, "team_id": team_id, "liga": liga,
                "fecha_descarga": datetime.now().isoformat(), "completo": True,
                "jugadores": todos_jugadores
            }, f, ensure_ascii=False)

        procesados += 1
        if procesados % 15 == 0:
            print(f"  [{procesados}] {equipo} - {len(todos_jugadores)} jugadores")

    except Exception as e:
        errores += 1

print(f"\nOK: {procesados} procesados | sin_team: {sin_team} | sin_liga_pais: {sin_liga_pais} | errores: {errores}")
