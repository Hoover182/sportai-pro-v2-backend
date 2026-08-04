with open("app/services/futbol_service.py", "r", encoding="utf-8") as f:
    content = f.read()

old = """              ultimos_local.append({
                  "fecha": str(r["fecha"])[:10],
                  "rival": r["equipo_visitante"] if es_local else r["equipo_local"],
                  "resultado": f"{gl}-{gv}",
                  "ganado": gf > gc,
                  "empate": gf == gc,
              })"""

new = """              ultimos_local.append({
                  "fecha": str(r["fecha"])[:10],
                  "rival": r["equipo_visitante"] if es_local else r["equipo_local"],
                  "resultado": f"{gl}-{gv}",
                  "ganado": gf > gc,
                  "empate": gf == gc,
                  "corners": int(r["corners_local"] if es_local else r["corners_visitante"]) if "corners_local" in r and r["corners_local"] == r["corners_local"] else 0,
                  "tarjetas": int(r["tarjetas_local"] if es_local else r["tarjetas_visitante"]) if "tarjetas_local" in r and r["tarjetas_local"] == r["tarjetas_local"] else 0,
                  "tiros_arco": int(r["tiros_arco_local"] if es_local else r["tiros_arco_visitante"]) if "tiros_arco_local" in r and r["tiros_arco_local"] == r["tiros_arco_local"] else 0,
                  "tiros_total": int(r["tiros_total_local"] if es_local else r["tiros_total_visitante"]) if "tiros_total_local" in r and r["tiros_total_local"] == r["tiros_total_local"] else 0,
              })"""

if old in content:
    content = content.replace(old, new, 1)
    print("OK: ultimos_local actualizado")
else:
    print("ERROR: patron ultimos_local no encontrado")

old2 = """              ultimos_visitante.append({
                  "fecha": str(r["fecha"])[:10],
                  "rival": r["equipo_visitante"] if es_local else r["equipo_local"],
                  "resultado": f"{gl}-{gv}",
                  "ganado": gf > gc,
                  "empate": gf == gc,
              })"""

new2 = """              ultimos_visitante.append({
                  "fecha": str(r["fecha"])[:10],
                  "rival": r["equipo_visitante"] if r["equipo_local"] == visitante else r["equipo_local"],
                  "resultado": f"{int(r['goles_local'])}-{int(r['goles_visitante'])}",
                  "ganado": (int(r["goles_local"]) if r["equipo_local"] == visitante else int(r["goles_visitante"])) > (int(r["goles_visitante"]) if r["equipo_local"] == visitante else int(r["goles_local"])),
                  "empate": int(r["goles_local"]) == int(r["goles_visitante"]),
                  "corners": int(r["corners_local"] if r["equipo_local"] == visitante else r["corners_visitante"]) if "corners_local" in r and r["corners_local"] == r["corners_local"] else 0,
                  "tarjetas": int(r["tarjetas_local"] if r["equipo_local"] == visitante else r["tarjetas_visitante"]) if "tarjetas_local" in r and r["tarjetas_local"] == r["tarjetas_local"] else 0,
                  "tiros_arco": int(r["tiros_arco_local"] if r["equipo_local"] == visitante else r["tiros_arco_visitante"]) if "tiros_arco_local" in r and r["tiros_arco_local"] == r["tiros_arco_local"] else 0,
                  "tiros_total": int(r["tiros_total_local"] if r["equipo_local"] == visitante else r["tiros_total_visitante"]) if "tiros_total_local" in r and r["tiros_total_local"] == r["tiros_total_local"] else 0,
              })"""

if old2 in content:
    content = content.replace(old2, new2, 1)
    print("OK: ultimos_visitante actualizado")
else:
    print("ERROR: patron ultimos_visitante no encontrado")

with open("app/services/futbol_service.py", "w", encoding="utf-8", newline="\n") as f:
    f.write(content)
