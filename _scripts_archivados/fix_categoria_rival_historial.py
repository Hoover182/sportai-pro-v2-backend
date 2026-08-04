with open("app/services/futbol_service.py", "r", encoding="utf-8") as f:
    content = f.read()

# LOCAL: el rival es p.rival ya calculado antes en el mismo dict
old_l = '"liga_partido": str(r["liga"]) if "liga" in r.index else "",\n            })\n    except Exception:\n        pass'
new_l = '"liga_partido": str(r["liga"]) if "liga" in r.index else "",\n                "categoria_rival": categoria_equipo(r["equipo_visitante"] if r["equipo_local"] == local else r["equipo_local"], equipos_n1),\n            })\n    except Exception:\n        pass'

cambios = 0
if old_l in content:
    content = content.replace(old_l, new_l, 1)
    cambios += 1
    print("OK: categoria_rival agregada al bloque 1")
else:
    print("ERROR bloque 1")

# VISITANTE: mismo patron pero puede repetirse, buscamos la segunda ocurrencia
old_v = '"liga_partido": str(r["liga"]) if "liga" in r.index else "",\n                "categoria_rival": categoria_equipo(r["equipo_visitante"] if r["equipo_local"] == local else r["equipo_local"], equipos_n1),\n            })\n    except Exception:\n        pass\n    try:\n        pv = obtener_partidos_equipo(df, visitante, n=20)'

new_v = '"liga_partido": str(r["liga"]) if "liga" in r.index else "",\n                "categoria_rival": categoria_equipo(r["equipo_visitante"] if r["equipo_local"] == local else r["equipo_local"], equipos_n1),\n            })\n    except Exception:\n        pass\n    try:\n        pv = obtener_partidos_equipo(df, visitante, n=20)'

with open("app/services/futbol_service.py", "w", encoding="utf-8", newline="\n") as f:
    f.write(content)
print("Total cambios aplicados:", cambios)
