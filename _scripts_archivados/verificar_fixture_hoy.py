import requests

API_KEY = "[APIFOOTBALL_KEY_REMOVIDA]"
headers = {"x-apisports-key": API_KEY}

resp = requests.get(
    "https://v3.football.api-sports.io/fixtures",
    headers=headers,
    params={"team": 1154, "season": 2026, "last": 5}
)
data = resp.json()
for f in data.get("response", []):
    fid = f["fixture"]["id"]
    fecha = f["fixture"]["date"]
    estado = f["fixture"]["status"]["short"]
    home = f["teams"]["home"]["name"]
    away = f["teams"]["away"]["name"]
    print(f"{fid} | {fecha[:10]} | {estado} | {home} vs {away}")
