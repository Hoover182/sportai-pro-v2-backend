import requests

API_KEY = "[APIFOOTBALL_KEY_REMOVIDA]"
headers = {"x-apisports-key": API_KEY}

resp = requests.get(
    "https://v3.football.api-sports.io/teams",
    headers=headers,
    params={"search": "Deportivo Cuenca"}
)
data = resp.json()
team_id = data["response"][0]["team"]["id"]
print("Team ID:", team_id)

resp2 = requests.get(
    "https://v3.football.api-sports.io/fixtures",
    headers=headers,
    params={"team": team_id, "season": 2026, "last": 5}
)
data2 = resp2.json()
fixture_ids = [f["fixture"]["id"] for f in data2.get("response", [])]
print("Fixtures:", fixture_ids)

if fixture_ids:
    resp3 = requests.get(
        "https://v3.football.api-sports.io/fixtures/players",
        headers=headers,
        params={"fixture": fixture_ids[0]}
    )
    data3 = resp3.json()
    for equipo in data3.get("response", []):
        if equipo.get("team", {}).get("name") == "Deportivo Cuenca":
            for j in equipo.get("players", []):
                nombre = j.get("player", {}).get("name", "")
                if "rdo" in nombre.lower() or "ordo" in nombre.lower():
                    print("Nombre encontrado:", repr(nombre))
