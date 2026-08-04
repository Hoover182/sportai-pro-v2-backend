with open("app/services/futbol_service.py", "r", encoding="utf-8") as f:
    content = f.read()

old = '                  "tiros_total": int(r["tiros_total_local"] if es_local else r["tiros_total_visitante"]) if "tiros_total_local" in r.index and str(r["tiros_total_local"]) != "nan" else 0,\n            })\n    except Exception:\n        pass\n    try:\n        pv = obtener_partidos_equipo(df, visitante, n=10)'

new = '                  "tiros_total": int(r["tiros_total_local"] if es_local else r["tiros_total_visitante"]) if "tiros_total_local" in r.index and str(r["tiros_total_local"]) != "nan" else 0,\n                  "goles_local_1t": int(r["goles_local_1t"]) if "goles_local_1t" in r.index and str(r["goles_local_1t"]) not in ["nan","None"] else None,\n                  "goles_visitante_1t": int(r["goles_visitante_1t"]) if "goles_visitante_1t" in r.index and str(r["goles_visitante_1t"]) not in ["nan","None"] else None,\n                  "goles_local_2t": int(r["goles_local_2t"]) if "goles_local_2t" in r.index and str(r["goles_local_2t"]) not in ["nan","None"] else None,\n                  "goles_visitante_2t": int(r["goles_visitante_2t"]) if "goles_visitante_2t" in r.index and str(r["goles_visitante_2t"]) not in ["nan","None"] else None,\n                  "tarjetas_local_1t": int(r["tarjetas_local_1t"]) if "tarjetas_local_1t" in r.index and str(r["tarjetas_local_1t"]) not in ["nan","None"] else None,\n                  "tarjetas_visitante_1t": int(r["tarjetas_visitante_1t"]) if "tarjetas_visitante_1t" in r.index and str(r["tarjetas_visitante_1t"]) not in ["nan","None"] else None,\n            })\n    except Exception:\n        pass\n    try:\n        pv = obtener_partidos_equipo(df, visitante, n=10)'

if old in content:
    content = content.replace(old, new, 1)
    with open("app/services/futbol_service.py", "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print("OK")
else:
    print("ERROR: no encontrado")
    idx = content.find('"tiros_total_local"] if es_local')
    print(repr(content[idx:idx+200]))
