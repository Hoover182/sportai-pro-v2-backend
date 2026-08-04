import requests
resp = requests.get("https://sportai-pro-v2-backend.onrender.com/futbol/partidos-rango?dias=4", timeout=30)
print("Status:", resp.status_code)
data = resp.json()
print("Total partidos:", len(data.get("partidos", [])))
if data.get("partidos"):
    print(data["partidos"][0])
