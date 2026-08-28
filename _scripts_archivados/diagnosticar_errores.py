import requests
import pandas as pd
import re
import unicodedata
import json
import os

API_KEY = "[APIFOOTBALL_KEY_REMOVIDA]"
headers = {"x-apisports-key": API_KEY}
CSV = "C:/Users/hoove/OneDrive/Documentos/analista_futbol/futbol_partidos.csv"
CACHE_DIR = "app/services/jugadores_data"

LIGA_IDS = {
    "Liga Profesional Argentina": (128, "Argentina"), "Brasileirao": (71, "Brazil"),
    "Brasileirao Serie A": (71, "Brazil"), "Liga Colombia": (239, "Colombia"),
    "Primera Division Chile": (265, "Chile"), "Primera Division Uruguay": (268, "Uruguay"),
    "Primera Division Peru": (281, "Peru"), "Liga Pro Ecuador": (242, "Ecuador"),
    "Primera Division Venezuela": (337, "Venezuela"), "Primera Division Bolivia": (344, "Bolivia"),
    "Division Profesional Paraguay": (250, "Paraguay"), "Liga MX": (262, "Mexico"), "MLS": (253, "USA"),
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

equipo_test = "Platense"
liga = principales.get(equipo_test)
print("Liga de", equipo_test, ":", liga)
if liga not in LIGA_IDS:
    print("PROBLEMA: liga no esta en LIGA_IDS")
else:
    liga_id, pais = LIGA_IDS[liga]
    busqueda = limpiar_busqueda(equipo_test)
    try:
        resp_team = requests.get("https://v3.football.api-sports.io/teams", headers=headers, params={"search": busqueda}, timeout=15)
        data_team = resp_team.json()
        print("Candidatos:", len(data_team.get("response", [])))
        for c in data_team.get("response", []):
            print(" ", c["team"]["id"], c["team"]["name"], c["team"]["country"])
    except Exception as e:
        print("EXCEPCION:", repr(e))
