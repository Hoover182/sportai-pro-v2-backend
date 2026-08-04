import sys
sys.path.insert(0, "app/services")
import requests
from player_model import API_KEY, BASE_URL

headers = {"x-apisports-key": API_KEY}
resp_team = requests.get(f"{BASE_URL}/teams", headers=headers, params={"search": "Remo"})
data_team = resp_team.json()
print("Primer resultado (el que usa el codigo):", data_team["response"][0]["team"]["id"], data_team["response"][0]["team"]["name"], data_team["response"][0]["team"]["country"])
