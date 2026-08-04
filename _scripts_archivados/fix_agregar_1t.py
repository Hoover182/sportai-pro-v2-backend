with open("app/services/futbol_service.py", "r", encoding="utf-8") as f:
    content = f.read()

# Insertar el calculo de 1T en el JSON de respuesta (despues de tarjetas_ou)
old = '''        "tarjetas_ou": {
            str(k): {"over": round(v["over"]*100,1), "under": round(v["under"]*100,1)}
            for k, v in sim["tarjetas_ou"].items()
        },
        "top3": top3,'''

new = '''        "tarjetas_ou": {
            str(k): {"over": round(v["over"]*100,1), "under": round(v["under"]*100,1)}
            for k, v in sim["tarjetas_ou"].items()
        },
        "goles_1t": _calcular_goles_1t(df, local, visitante),
        "top3": top3,'''

if old in content:
    content = content.replace(old, new, 1)
    print("OK: goles_1t agregado al JSON")
else:
    print("ERROR: return no encontrado")

# Agregar la funcion helper _calcular_goles_1t antes de get_analisis_partido
old2 = "def stats_goles_1t(df, equipo, n=10):"

new2 = '''def _calcular_goles_1t(df, local, visitante):
    """Calcula proyecciones y Over/Under del primer tiempo para el partido."""
    try:
        s_local = stats_goles_1t(df, local)
        s_visit = stats_goles_1t(df, visitante)
        if s_local is None or s_visit is None:
            return None
        # Media de goles 1T: ataque propio + defensa rival
        media_local = (s_local["goles_favor_1t"] + s_visit["goles_contra_1t"]) / 2
        media_visit = (s_visit["goles_favor_1t"] + s_local["goles_contra_1t"]) / 2
        sim_1t = simular_goles_1t(media_local, media_visit)
        return {
            "proj": f"{sim_1t['goles_local_proj_1t']:.2f} - {sim_1t['goles_visitante_proj_1t']:.2f}",
            "ou": sim_1t["ou"],
            "ambos_marcan_1t": sim_1t["ambos_marcan_1t"],
            "media_local_gf_1t": round(s_local["goles_favor_1t"], 2),
            "media_local_gc_1t": round(s_local["goles_contra_1t"], 2),
            "media_visit_gf_1t": round(s_visit["goles_favor_1t"], 2),
            "media_visit_gc_1t": round(s_visit["goles_contra_1t"], 2),
        }
    except Exception:
        return None


def stats_goles_1t(df, equipo, n=10):'''

if old2 in content:
    content = content.replace(old2, new2, 1)
    print("OK: helper _calcular_goles_1t agregado")
else:
    print("ERROR: stats_goles_1t no encontrado")

with open("app/services/futbol_service.py", "w", encoding="utf-8", newline="\n") as f:
    f.write(content)
