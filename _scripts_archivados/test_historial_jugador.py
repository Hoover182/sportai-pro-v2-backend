import sys, requests
sys.path.insert(0, "app/services")
from player_model import obtener_historial_jugador

API_KEY = "7be9c4250da301a68726beedbe2b382a"
headers = {"x-apisports-key": API_KEY}

resp = requests.get(
    "https://v3.football.api-sports.io/fixtures",
    headers=headers,
    params={"team": 2315, "season": 2026, "last": 5}
)
data = resp.json()
fixture_ids = [f["fixture"]["id"] for f in data.get("response", [])]
print("Fixtures encontrados:", fixture_ids)

historial = obtener_historial_jugador("Arturo Vidal", fixture_ids, n=5)
print()
print("Historial de Arturo Vidal:")
for h in historial:
    print(" ", h)
