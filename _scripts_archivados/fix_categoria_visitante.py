with open("app/services/futbol_service.py", "r", encoding="utf-8") as f:
    content = f.read()

old = '                "liga_partido": str(r["liga"]) if "liga" in r.index else "",\n            })\n    except Exception:\n        pass'
new = '                "liga_partido": str(r["liga"]) if "liga" in r.index else "",\n                "categoria_rival": categoria_equipo(r["equipo_visitante"] if r["equipo_local"] == visitante else r["equipo_local"], equipos_n1),\n            })\n    except Exception:\n        pass'

if old in content:
    content = content.replace(old, new, 1)
    with open("app/services/futbol_service.py", "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print("OK: categoria_rival agregada al bloque visitante")
else:
    print("ERROR: no encontrado (puede que ya se haya aplicado)")
