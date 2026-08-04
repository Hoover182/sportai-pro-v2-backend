import requests
import urllib.parse

local = urllib.parse.quote("San Jose Earthquakes")
visitante = urllib.parse.quote("Los Angeles Galaxy")
url = f"https://sportai-pro-v2-backend.onrender.com/futbol/partido/{local}/{visitante}"
print("URL:", url)
resp = requests.get(url, timeout=60)
print("Status:", resp.status_code)
print(resp.text[:500])
