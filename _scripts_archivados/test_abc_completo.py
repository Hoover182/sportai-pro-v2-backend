import requests
import pandas as pd
import re
import unicodedata

API_KEY = "[APIFOOTBALL_KEY_REMOVIDA]"
headers = {"x-apisports-key": API_KEY}
CSV = "C:/Users/hoove/OneDrive/Documentos/analista_futbol/futbol_partidos.csv"

LIGA_IDS = {
    "Copa do Brasil": (73, "Brazil"),
}

def limpiar_busqueda(nombre):
    nfkd = unicodedata.normalize("NFKD", nombre)
    sin_acentos = "".join(c for c in nfkd if not unicodedata.combining(c))
    limpio = re.sub(r"[^a-zA-Z0-9 ]", " ", sin_acentos)
    return re.sub(r"\s+", " ", limpio).strip()

df = pd.read_csv(CSV)
principales = df.groupby("equipo_local")["liga"].agg(lambda x: x.value_counts().index[0])

equipo = "ABC"
liga = principales.get(equipo)
print("Liga real detectada:", repr(liga))

if liga not in LIGA_IDS:
    print("Liga no mapeada en este test, usando Copa do Brasil de todos modos")
liga_id, pais_esperado = 73, "Brazil"

busqueda = limpiar_busqueda(equipo)
print("Busqueda limpia:", repr(busqueda))
resp_team = requests.get("https://v3.football.api-sports.io/teams", headers=headers, params={"search": busqueda}, timeout=15)
data_team = resp_team.json()
print("Status:", resp_team.status_code)
print("Errors:", data_team.get("errors"))
candidatos = data_team.get("response", [])
print("Candidatos:", len(candidatos))
for c in candidatos[:10]:
    print("  ", c["team"]["id"], c["team"]["name"], c["team"]["country"])
