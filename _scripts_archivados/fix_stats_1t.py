with open("app/services/futbol_service.py", "r", encoding="utf-8") as f:
    content = f.read()

# Agregar funcion para calcular stats de 1T antes de get_analisis_partido
old = "def get_analisis_partido(local_input, visitante_input):"

new = '''def stats_goles_1t(df, equipo, n=10):
    """Calcula el promedio de goles a favor y en contra en el primer tiempo."""
    import numpy as np
    from football_model import obtener_partidos_equipo
    partidos = obtener_partidos_equipo(df, equipo, n=n)
    gf_1t = []
    gc_1t = []
    for _, r in partidos.iterrows():
        if "goles_local_1t" not in r.index:
            continue
        if str(r["goles_local_1t"]) in ["nan", "None"]:
            continue
        es_local = r["equipo_local"] == equipo
        if es_local:
            gf = r["goles_local_1t"]
            gc = r["goles_visitante_1t"]
        else:
            gf = r["goles_visitante_1t"]
            gc = r["goles_local_1t"]
        try:
            gf_1t.append(float(gf))
            gc_1t.append(float(gc))
        except Exception:
            continue
    if len(gf_1t) < 2:
        return None
    return {
        "goles_favor_1t": float(np.mean(gf_1t)),
        "goles_contra_1t": float(np.mean(gc_1t)),
        "n_partidos": len(gf_1t),
    }


def simular_goles_1t(media_local, media_visitante, iteraciones=10000):
    """Simula goles del primer tiempo con Poisson y devuelve probabilidades Over/Under."""
    import numpy as np
    media_local = max(float(media_local), 0.05)
    media_visitante = max(float(media_visitante), 0.05)
    goles_local = np.random.poisson(media_local, iteraciones)
    goles_visitante = np.random.poisson(media_visitante, iteraciones)
    total = goles_local + goles_visitante
    resultado = {}
    for linea in [0.5, 1.5, 2.5]:
        resultado[str(linea)] = {
            "over": round(float(np.mean(total > linea)) * 100, 1),
            "under": round(float(np.mean(total < linea)) * 100, 1),
        }
    # Ambos marcan en 1T
    ambos_1t = round(float(np.mean((goles_local > 0) & (goles_visitante > 0))) * 100, 1)
    return {
        "ou": resultado,
        "ambos_marcan_1t": ambos_1t,
        "goles_local_proj_1t": round(float(np.mean(goles_local)), 2),
        "goles_visitante_proj_1t": round(float(np.mean(goles_visitante)), 2),
    }


def get_analisis_partido(local_input, visitante_input):'''

if old in content:
    content = content.replace(old, new, 1)
    with open("app/services/futbol_service.py", "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print("OK: funciones stats_goles_1t y simular_goles_1t agregadas")
else:
    print("ERROR: no encontrado")
