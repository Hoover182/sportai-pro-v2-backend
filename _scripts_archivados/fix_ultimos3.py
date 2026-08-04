with open("app/services/futbol_service.py", "r", encoding="utf-8") as f:
    content = f.read()

old = 'ultimos_local.append({\n                "fecha": str(r["fecha"])[:10],\n                "rival": r["equipo_visitante"] if es_local else r["equipo_local"],\n                "resultado": f"{gl}-{gv}",\n                "ganado": gf > gc,\n                "empate": gf == gc,\n            })'

new = 'ultimos_local.append({\n                "fecha": str(r["fecha"])[:10],\n                "rival": r["equipo_visitante"] if es_local else r["equipo_local"],\n                "resultado": f"{gl}-{gv}",\n                "ganado": gf > gc,\n                "empate": gf == gc,\n                "corners": int(r["corners_local"] if es_local else r["corners_visitante"]) if "corners_local" in r.index and str(r["corners_local"]) != "nan" else 0,\n                "tarjetas": int(r["tarjetas_local"] if es_local else r["tarjetas_visitante"]) if "tarjetas_local" in r.index and str(r["tarjetas_local"]) != "nan" else 0,\n                "tiros_arco": int(r["tiros_arco_local"] if es_local else r["tiros_arco_visitante"]) if "tiros_arco_local" in r.index and str(r["tiros_arco_local"]) != "nan" else 0,\n                "tiros_total": int(r["tiros_total_local"] if es_local else r["tiros_total_visitante"]) if "tiros_total_local" in r.index and str(r["tiros_total_local"]) != "nan" else 0,\n            })'

old2 = 'ultimos_visitante.append({\n                "fecha": str(r["fecha"])[:10],\n                "rival": r["equipo_visitante"] if es_local else r["equipo_local"],\n                "resultado": f"{gl}-{gv}",\n                "ganado": gf > gc,\n                "empate": gf == gc,\n            })'

new2 = 'ultimos_visitante.append({\n                "fecha": str(r["fecha"])[:10],\n                "rival": r["equipo_visitante"] if r["equipo_local"] == visitante else r["equipo_local"],\n                "resultado": f\"{int(r[\'goles_local\'])}-{int(r[\'goles_visitante\'])}\",\n                "ganado": (int(r["goles_local"]) if r["equipo_local"] == visitante else int(r["goles_visitante"])) > (int(r["goles_visitante"]) if r["equipo_local"] == visitante else int(r["goles_local"])),\n                "empate": int(r["goles_local"]) == int(r["goles_visitante"]),\n                "corners": int(r["corners_local"] if r["equipo_local"] == visitante else r["corners_visitante"]) if "corners_local" in r.index and str(r["corners_local"]) != "nan" else 0,\n                "tarjetas": int(r["tarjetas_local"] if r["equipo_local"] == visitante else r["tarjetas_visitante"]) if "tarjetas_local" in r.index and str(r["tarjetas_local"]) != "nan" else 0,\n                "tiros_arco": int(r["tiros_arco_local"] if r["equipo_local"] == visitante else r["tiros_arco_visitante"]) if "tiros_arco_local" in r.index and str(r["tiros_arco_local"]) != "nan" else 0,\n                "tiros_total": int(r["tiros_total_local"] if r["equipo_local"] == visitante else r["tiros_total_visitante"]) if "tiros_total_local" in r.index and str(r["tiros_total_local"]) != "nan" else 0,\n            })'

if old in content:
    content = content.replace(old, new, 1)
    print("OK: ultimos_local")
else:
    print("ERROR: ultimos_local")

if old2 in content:
    content = content.replace(old2, new2, 1)
    print("OK: ultimos_visitante")
else:
    print("ERROR: ultimos_visitante")

with open("app/services/futbol_service.py", "w", encoding="utf-8", newline="\n") as f:
    f.write(content)
