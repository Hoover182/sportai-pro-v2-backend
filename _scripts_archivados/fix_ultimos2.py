with open("app/services/futbol_service.py", "r", encoding="utf-8") as f:
    content = f.read()

old = """            ultimos_local.append({
                  "fecha": str(r["fecha"])[:10],
                  "rival": r["equipo_visitante"] if es_local else r["equipo_local"],
                  "resultado": f"{gl}-{gv}",
                  "ganado": gf > gc,
                  "empate": gf == gc,
              })"""

new = """            ultimos_local.append({
                  "fecha": str(r["fecha"])[:10],
                  "rival": r["equipo_visitante"] if es_local else r["equipo_local"],
                  "resultado": f"{gl}-{gv}",
                  "ganado": gf > gc,
                  "empate": gf == gc,
                  "corners":    int(r["corners_local"]    if es_local else r["corners_visitante"])    if "corners_local"    in r.index and str(r["corners_local"])    != "nan" else 0,
                  "tarjetas":   int(r["tarjetas_local"]   if es_local else r["tarjetas_visitante"])   if "tarjetas_local"   in r.index and str(r["tarjetas_local"])   != "nan" else 0,
                  "tiros_arco": int(r["tiros_arco_local"] if es_local else r["tiros_arco_visitante"]) if "tiros_arco_local" in r.index and str(r["tiros_arco_local"]) != "nan" else 0,
                  "tiros_total":int(r["tiros_total_local"]if es_local else r["tiros_total_visitante"])if "tiros_total_local" in r.index and str(r["tiros_total_local"])!= "nan" else 0,
              })"""

old2 = """            ultimos_visitante.append({
                  "fecha": str(r["fecha"])[:10],
                  "rival": r["equipo_visitante"] if es_local else r["equipo_local"],
                  "resultado": f"{gl}-{gv}",
                  "ganado": gf > gc,
                  "empate": gf == gc,
              })"""

new2 = """            ultimos_visitante.append({
                  "fecha": str(r["fecha"])[:10],
                  "rival": r["equipo_visitante"] if es_local else r["equipo_local"],
                  "resultado": f"{gl}-{gv}",
                  "ganado": gf > gc,
                  "empate": gf == gc,
                  "corners":    int(r["corners_local"]    if r["equipo_local"] == visitante else r["corners_visitante"])    if "corners_local"    in r.index and str(r["corners_local"])    != "nan" else 0,
                  "tarjetas":   int(r["tarjetas_local"]   if r["equipo_local"] == visitante else r["tarjetas_visitante"])   if "tarjetas_local"   in r.index and str(r["tarjetas_local"])   != "nan" else 0,
                  "tiros_arco": int(r["tiros_arco_local"] if r["equipo_local"] == visitante else r["tiros_arco_visitante"]) if "tiros_arco_local" in r.index and str(r["tiros_arco_local"]) != "nan" else 0,
                  "tiros_total":int(r["tiros_total_local"]if r["equipo_local"] == visitante else r["tiros_total_visitante"])if "tiros_total_local" in r.index and str(r["tiros_total_local"])!= "nan" else 0,
              })"""

if old in content:
    content = content.replace(old, new, 1)
    print("OK: ultimos_local")
else:
    print("ERROR: ultimos_local - buscando caracteres exactos...")
    idx = content.find("ultimos_local.append")
    print(repr(content[idx:idx+200]))

if old2 in content:
    content = content.replace(old2, new2, 1)
    print("OK: ultimos_visitante")
else:
    print("ERROR: ultimos_visitante")

with open("app/services/futbol_service.py", "w", encoding="utf-8", newline="\n") as f:
    f.write(content)
