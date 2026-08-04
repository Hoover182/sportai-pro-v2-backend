import requests
import json
from datetime import datetime

API_KEY = "7be9c4250da301a68726beedbe2b382a"
headers = {"x-apisports-key": API_KEY}

team_id = 1198
liga_id = 71  # Brasileirao

todos_jugadores = []
pagina = 1
total_paginas = 1
while pagina <= total_paginas and pagina <= 5:
    resp = requests.get(
        "https://v3.football.api-sports.io/players",
        headers=headers,
        params={"team": team_id, "league": liga_id, "season": 2026, "page": pagina}
    )
    data = resp.json()
    todos_jugadores.extend(data.get("response", []))
    paging = data.get("paging", {})
    total_paginas = paging.get("total", 1)
    print(f"Pagina {pagina}/{total_paginas}: {len(data.get('response', []))} jugadores")
    pagina += 1

print(f"\nTotal jugadores descargados: {len(todos_jugadores)}")

with open("app/services/jugadores_data/Remo.json", "w", encoding="utf-8") as f:
    json.dump({
        "equipo": "Remo", "team_id": team_id, "liga": "Brasileirao",
        "fecha_descarga": datetime.now().isoformat(), "completo": True,
        "jugadores": todos_jugadores
    }, f, ensure_ascii=False)

print("OK: Remo.json actualizado correctamente")
