import requests
resp = requests.get("https://sportai-pro-v2-backend.onrender.com/futbol/partido/San Jose Earthquakes/Los Angeles Galaxy", timeout=60)
print("Status:", resp.status_code)
print(resp.text[:300])
