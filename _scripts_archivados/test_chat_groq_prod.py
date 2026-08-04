import requests
resp = requests.post(
    "https://sportai-pro-v2-backend.onrender.com/futbol/chat",
    json={"mensajes": [{"role": "user", "text": "hola, responde en una linea"}], "contexto": "prueba"},
    timeout=30
)
print("Status:", resp.status_code)
print("Respuesta:", resp.text[:400])
