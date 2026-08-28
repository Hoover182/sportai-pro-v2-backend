import requests
import pandas as pd
import re
import unicodedata
import json
from datetime import datetime

API_KEY = "[APIFOOTBALL_KEY_REMOVIDA]"
headers = {"x-apisports-key": API_KEY}
CSV = "C:/Users/hoove/OneDrive/Documentos/analista_futbol/futbol_partidos.csv"

LIGA_IDS = {
    "Liga Profesional Argentina": (128, "Argentina"),
}

def limpiar_busqueda(nombre):
    nfkd = unicodedata.normalize("NFKD", nombre)
    sin_acentos = "".join(c for c in nfkd if not unicodedata.combining(c))
    limpio = re.sub(r"[^a-zA-Z0-9 ]", " ", sin_acentos)
    return re.sub(r"\s+", " ", limpio).strip()

df = pd.read_csv(CSV)
principales = df.groupby("equipo_local")["liga"].agg(lambda x: x.value_counts().index[0])

equipo = "Platense"
liga = principales.get(equipo)
print("Liga real detectada:", repr(liga))
liga_id, pais_esperado = LIGA_IDS[liga]
print("Pais esperado:", repr(pais_esperado))

busqueda = limpiar_busqueda(equipo)
resp_team = requests.get("https://v3.football.api-sports.io/teams", headers=headers, params={"search": busqueda}, timeout=15)
data_team = resp_team.json()
candidatos = data_team.get("response", [])
print("Candidatos encontrados:", len(candidatos))

team_id = None
for c in candidatos:
    print("  Comparando:", repr(c["team"]["country"]), "vs", repr(pais_esperado))
    if c["team"]["country"] == pais_esperado:
        team_id = c["team"]["id"]
        print("  MATCH! team_id =", team_id)
        break

if team_id is None:
    print("NO SE ENCONTRO MATCH, usando fallback:", candidatos[0]["team"]["id"])
    team_id = candidatos[0]["team"]["id"]

print("\nTeam ID final usado:", team_id)

resp_players = requests.get(
    "https://v3.football.api-sports.io/players",
    headers=headers, params={"team": team_id, "league": liga_id, "season": 2026}
)
data_players = resp_players.json()
print("Jugadores encontrados:", len(data_players.get("response", [])))
print("Errors:", data_players.get("errors"))
