import json
import requests

API_KEY = "7be9c4250da301a68726beedbe2b382a"
headers = {"x-apisports-key": API_KEY}

archivos_test = ["Platense.json", "Junior.json", "Santa Fe.json"]

for archivo in archivos_test:
    with open(f"app/services/jugadores_data/{archivo}", "r", encoding="utf-8") as f:
        data = json.load(f)
    team_id = data["team_id"]
    liga = data["liga"]
    print(f"\n{archivo}: team_id={team_id}, liga={liga}")

    # Buscar el liga_id que se uso
    resp = requests.get(
        "https://v3.football.api-sports.io/players",
        headers=headers,
        params={"team": team_id, "season": 2026}
    )
    r = resp.json()
    if r.get("response"):
        for st in r["response"][0].get("statistics", []):
            print("  Liga disponible:", st.get("league", {}).get("name"), "| ID:", st.get("league", {}).get("id"))
