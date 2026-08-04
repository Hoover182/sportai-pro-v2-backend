with open("app/services/futbol_service.py", "r", encoding="utf-8") as f:
    content = f.read()

old = 'ipo_local"] == visitante else r["tiros_total_visitante"]) if "tiros_total_local" in r.index and str(r["tiros_total_local"]) != "nan" else 0,\n            })\n    except Exception:\n        pass\n    return {'

new = 'ipo_local"] == visitante else r["tiros_total_visitante"]) if "tiros_total_local" in r.index and str(r["tiros_total_local"]) != "nan" else 0,\n                "goles_favor_1t": int(r["goles_local_1t"] if r["equipo_local"] == visitante else r["goles_visitante_1t"]) if "goles_local_1t" in r.index and str(r["goles_local_1t"]) not in ["nan","None"] else None,\n                "goles_contra_1t": int(r["goles_visitante_1t"] if r["equipo_local"] == visitante else r["goles_local_1t"]) if "goles_visitante_1t" in r.index and str(r["goles_visitante_1t"]) not in ["nan","None"] else None,\n                "goles_favor_2t": int(r["goles_local_2t"] if r["equipo_local"] == visitante else r["goles_visitante_2t"]) if "goles_local_2t" in r.index and str(r["goles_local_2t"]) not in ["nan","None"] else None,\n                "goles_contra_2t": int(r["goles_visitante_2t"] if r["equipo_local"] == visitante else r["goles_local_2t"]) if "goles_visitante_2t" in r.index and str(r["goles_visitante_2t"]) not in ["nan","None"] else None,\n                "tarjetas_favor_1t": int(r["tarjetas_local_1t"] if r["equipo_local"] == visitante else r["tarjetas_visitante_1t"]) if "tarjetas_local_1t" in r.index and str(r["tarjetas_local_1t"]) not in ["nan","None"] else None,\n            })\n    except Exception:\n        pass\n    return {'

if old in content:
    content = content.replace(old, new, 1)
    with open("app/services/futbol_service.py", "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print("OK: datos 1T agregados a ultimos_visitante")
else:
    print("ERROR")
