import requests
import json
from datetime import datetime

API_KEY = "[APIFOOTBALL_KEY_REMOVIDA]"
headers = {"x-apisports-key": API_KEY}

team_id = 1198  # Remo, confirmado ayer

for liga_id, liga_nombre in [(71, "Brasileirao"), (73, "Copa do Brasil")]:
    resp = requests.get(
        "https://v3.football.api-sports.io/players",
        headers=headers,
        params={"team": team_id, "league": liga_id, "season": 2026}
    )
    data = resp.json()
    print(f"Liga {liga_nombre} (id {liga_id}): {len(data.get('response', []))} jugadores, results={data.get('results')}")
    if data.get("errors"):
        print("  Errores:", data["errors"])
