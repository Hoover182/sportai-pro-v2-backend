import requests

API_KEY = "7be9c4250da301a68726beedbe2b382a"
headers = {"x-apisports-key": API_KEY}

fixture_ids = [1519427, 1519420, 1519410, 1519402, 1519392]

for fid in fixture_ids:
    resp = requests.get(
        "https://v3.football.api-sports.io/fixtures/players",
        headers=headers,
        params={"fixture": fid}
    )
    data = resp.json()
    for equipo in data.get("response", []):
        if equipo.get("team", {}).get("name") == "Deportivo Cuenca":
            for j in equipo.get("players", []):
                nombre = j.get("player", {}).get("name", "")
                if "ordo" in nombre.lower():
                    print(f"Fixture {fid}: {repr(nombre)}")
