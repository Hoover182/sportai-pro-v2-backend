import requests

API_KEY = "7be9c4250da301a68726beedbe2b382a"
headers = {"x-apisports-key": API_KEY}

resp = requests.get(
    "https://v3.football.api-sports.io/fixtures/players",
    headers=headers,
    params={"fixture": 1519427}
)
data = resp.json()
for equipo in data.get("response", []):
    if equipo.get("team", {}).get("name") == "Deportivo Cuenca":
        print("Total jugadores listados:", len(equipo.get("players", [])))
        for j in equipo.get("players", []):
            print(" ", repr(j.get("player", {}).get("name", "")))
