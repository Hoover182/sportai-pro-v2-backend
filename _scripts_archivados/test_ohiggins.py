import sys
sys.path.insert(0, "app/services")
from futbol_service import get_analisis_partido

r, e = get_analisis_partido("Boca Juniors", "O Higgins")
if r:
    for p in r["ultimos_visitante"][:5]:
        estado = "GANO" if p["ganado"] else ("EMPATE" if p["empate"] else "PERDIO")
        print(p["fecha"], "vs", p["rival"], "->", p["resultado"], estado)
else:
    print("ERROR:", e)
