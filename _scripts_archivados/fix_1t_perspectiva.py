with open("app/services/futbol_service.py", "r", encoding="utf-8") as f:
    content = f.read()

old = '                  "goles_local_1t": int(r["goles_local_1t"]) if "goles_local_1t" in r.index and str(r["goles_local_1t"]) not in ["nan","None"] else None,\n                  "goles_visitante_1t": int(r["goles_visitante_1t"]) if "goles_visitante_1t" in r.index and str(r["goles_visitante_1t"]) not in ["nan","None"] else None,\n                  "goles_local_2t": int(r["goles_local_2t"]) if "goles_local_2t" in r.index and str(r["goles_local_2t"]) not in ["nan","None"] else None,\n                  "goles_visitante_2t": int(r["goles_visitante_2t"]) if "goles_visitante_2t" in r.index and str(r["goles_visitante_2t"]) not in ["nan","None"] else None,\n                  "tarjetas_local_1t": int(r["tarjetas_local_1t"]) if "tarjetas_local_1t" in r.index and str(r["tarjetas_local_1t"]) not in ["nan","None"] else None,\n                  "tarjetas_visitante_1t": int(r["tarjetas_visitante_1t"]) if "tarjetas_visitante_1t" in r.index and str(r["tarjetas_visitante_1t"]) not in ["nan","None"] else None,'

new = '                  "goles_favor_1t": int(r["goles_local_1t"] if es_local else r["goles_visitante_1t"]) if "goles_local_1t" in r.index and str(r["goles_local_1t"]) not in ["nan","None"] else None,\n                  "goles_contra_1t": int(r["goles_visitante_1t"] if es_local else r["goles_local_1t"]) if "goles_visitante_1t" in r.index and str(r["goles_visitante_1t"]) not in ["nan","None"] else None,\n                  "goles_favor_2t": int(r["goles_local_2t"] if es_local else r["goles_visitante_2t"]) if "goles_local_2t" in r.index and str(r["goles_local_2t"]) not in ["nan","None"] else None,\n                  "goles_contra_2t": int(r["goles_visitante_2t"] if es_local else r["goles_local_2t"]) if "goles_visitante_2t" in r.index and str(r["goles_visitante_2t"]) not in ["nan","None"] else None,\n                  "tarjetas_favor_1t": int(r["tarjetas_local_1t"] if es_local else r["tarjetas_visitante_1t"]) if "tarjetas_local_1t" in r.index and str(r["tarjetas_local_1t"]) not in ["nan","None"] else None,'

if old in content:
    content = content.replace(old, new, 1)
    with open("app/services/futbol_service.py", "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print("OK: datos 1T desde perspectiva del equipo")
else:
    print("ERROR: no encontrado")
    idx = content.find("goles_local_1t")
    print(repr(content[idx:idx+300]))
