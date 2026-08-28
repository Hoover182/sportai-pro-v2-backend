import requests

API_KEY = "[APIFOOTBALL_KEY_REMOVIDA]"
headers = {"x-apisports-key": API_KEY}

resp = requests.get(
    "https://v3.football.api-sports.io/players",
    headers=headers,
    params={"search": "Pikachu"}
)
data = resp.json()
for p in data.get("response", []):
    info = p.get("player", {})
    print("Nombre:", info.get("name"), "| Nombre completo:", info.get("firstname"), info.get("lastname"))
