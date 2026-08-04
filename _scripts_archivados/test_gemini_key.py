import requests
url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=AIzaSyDmfsijMZw2mF9P9tub6fuSHgNLHBcR9TM"
payload = {
    "contents": [{"role": "user", "parts": [{"text": "hola, responde en una linea"}]}],
    "generationConfig": {"maxOutputTokens": 50}
}
resp = requests.post(url, json=payload, timeout=10)
print("Status:", resp.status_code)
print("Respuesta:", str(resp.json())[:300])
