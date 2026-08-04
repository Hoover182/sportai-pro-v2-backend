with open("app/services/futbol_service.py", "r", encoding="utf-8") as f:
    content = f.read()

old = '''    except Exception:
        pass
    return {
        "local": local,
        "visitante": visitante,
        "liga": liga,
        "prob_local": round(sim["prob_local"] * 100, 1),
        "prob_empate": round(sim["prob_empate"] * 100, 1),
        "prob_visitante": round(sim["prob_visitante"] * 100, 1),
        "prob_1x": round(sim["prob_1x"] * 100, 1),
        "prob_x2": round(sim["prob_x2"] * 100, 1),'''

new = '''    except Exception:
        pass

    # Aplicar ajuste cualitativo de IA si existe (lesiones, forma, contexto)
    ajuste_ia_info = _obtener_ajuste_ia(df, local, visitante)
    prob_local_final = sim["prob_local"] * 100
    prob_empate_final = sim["prob_empate"] * 100
    prob_visitante_final = sim["prob_visitante"] * 100

    if ajuste_ia_info:
        aj_local = ajuste_ia_info.get("ajuste_local", 0)
        aj_visit = ajuste_ia_info.get("ajuste_visitante", 0)
        prob_local_final = prob_local_final + aj_local
        prob_visitante_final = prob_visitante_final + aj_visit
        # Mantener el empate igual y renormalizar para que sume 100
        total = prob_local_final + prob_empate_final + prob_visitante_final
        if total > 0:
            factor = 100 / total
            prob_local_final = prob_local_final * factor
            prob_empate_final = prob_empate_final * factor
            prob_visitante_final = prob_visitante_final * factor
        # Evitar valores fuera de rango
        prob_local_final = max(1, min(98, prob_local_final))
        prob_visitante_final = max(1, min(98, prob_visitante_final))
        prob_empate_final = max(1, 100 - prob_local_final - prob_visitante_final)

    return {
        "local": local,
        "visitante": visitante,
        "liga": liga,
        "prob_local": round(prob_local_final, 1),
        "prob_empate": round(prob_empate_final, 1),
        "prob_visitante": round(prob_visitante_final, 1),
        "prob_local_original": round(sim["prob_local"] * 100, 1),
        "prob_empate_original": round(sim["prob_empate"] * 100, 1),
        "prob_visitante_original": round(sim["prob_visitante"] * 100, 1),
        "prob_1x": round(sim["prob_1x"] * 100, 1),
        "prob_x2": round(sim["prob_x2"] * 100, 1),'''

if old in content:
    content = content.replace(old, new, 1)
    print("OK: ajuste IA aplicado a probabilidades principales")
else:
    print("ERROR: patron no encontrado")

with open("app/services/futbol_service.py", "w", encoding="utf-8", newline="\n") as f:
    f.write(content)
