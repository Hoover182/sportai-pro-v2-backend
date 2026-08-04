with open("app/services/futbol_service.py", "r", encoding="utf-8") as f:
    content = f.read()

old = """            resultado.append({
                "liga": liga,
                "local": row["equipo_local"],
                "visitante": row["equipo_visitante"],
                "fecha": fecha,
                "hora": hora,
            })
    return resultado"""

new = """            local = row["equipo_local"]
            visitante = row["equipo_visitante"]
            prob_local = prob_empate = prob_visitante = None
            ajuste_ia = None
            try:
                sim, stats_a, stats_b = simular(df, local, visitante)
                if sim is not None:
                    prob_local = round(sim["prob_local"] * 100, 1)
                    prob_empate = round(sim["prob_empate"] * 100, 1)
                    prob_visitante = round(sim["prob_visitante"] * 100, 1)
                    ajuste_info = _obtener_ajuste_ia(df, local, visitante)
                    if ajuste_info:
                        aj_l = ajuste_info.get("ajuste_local", 0)
                        aj_v = ajuste_info.get("ajuste_visitante", 0)
                        pl = prob_local + aj_l
                        pv = prob_visitante + aj_v
                        pe = prob_empate
                        total = pl + pe + pv
                        if total > 0:
                            factor = 100 / total
                            pl, pe, pv = pl * factor, pe * factor, pv * factor
                        prob_local = round(max(1, min(98, pl)), 1)
                        prob_visitante = round(max(1, min(98, pv)), 1)
                        prob_empate = round(max(1, 100 - prob_local - prob_visitante), 1)
                        ajuste_ia = ajuste_info
            except Exception:
                pass

            resultado.append({
                "liga": liga,
                "local": local,
                "visitante": visitante,
                "fecha": fecha,
                "hora": hora,
                "prob_local": prob_local,
                "prob_empate": prob_empate,
                "prob_visitante": prob_visitante,
                "ajuste_ia": ajuste_ia,
            })
    return resultado"""

if old in content:
    content = content.replace(old, new, 1)
    with open("app/services/futbol_service.py", "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print("OK: partidos-hoy ahora incluye probabilidades y ajuste IA")
else:
    print("ERROR: patron no encontrado")
