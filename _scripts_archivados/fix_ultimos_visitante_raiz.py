with open("app/services/futbol_service.py", "r", encoding="utf-8") as f:
    content = f.read()

old = """    try:
        pv = obtener_partidos_equipo(df, visitante, n=20)
        for _, r in pv.iterrows():
            gl = int(r["goles_local"])
            gv = int(r["goles_visitante"])
            es_local = r["equipo_local"] == visitante
            gf = gl if es_local else gv
            gc = gv if es_local else gl
            ultimos_visitante.append({
                "fecha": str(r["fecha"])[:10],
                "rival": r["equipo_visitante"] if r["equipo_local"] == visitante else r["equipo_local"],
                "resultado": f"{int(r['goles_local'])}-{int(r['goles_visitante'])}",
                "ganado": (int(r["goles_local"]) if r["equipo_local"] == visitante else int(r["goles_visitante"])) > (int(r["goles_visitante"]) if r["equipo_local"] == visitante else int(r["goles_local"])),
                "empate": int(r["goles_local"]) == int(r["goles_visitante"]),
                "corners": int(r["corners_local"] if r["equipo_local"] == visitante else r["corners_visitante"]) if "corners_local" in r.index and str(r["corners_local"]) != "nan" else 0,
                "tarjetas": int(r["tarjetas_local"] if r["equipo_local"] == visitante else r["tarjetas_visitante"]) if "tarjetas_local" in r.index and str(r["tarjetas_local"]) != "nan" else 0,
                "tiros_arco": int(r["tiros_arco_local"] if r["equipo_local"] == visitante else r["tiros_arco_visitante"]) if "tiros_arco_local" in r.index and str(r["tiros_arco_local"]) != "nan" else 0,
                "tiros_total": int(r["tiros_total_local"] if r["equipo_local"] == visitante else r["tiros_total_visitante"]) if "tiros_total_local" in r.index and str(r["tiros_total_local"]) != "nan" else 0,
                "goles_favor_1t": int(r["goles_local_1t"] if r["equipo_local"] == visitante else r["goles_visitante_1t"]) if "goles_local_1t" in r.index and str(r["goles_local_1t"]) not in ["nan","None"] else None,
                "goles_contra_1t": int(r["goles_visitante_1t"] if r["equipo_local"] == visitante else r["goles_local_1t"]) if "goles_visitante_1t" in r.index and str(r["goles_visitante_1t"]) not in ["nan","None"] else None,
                "goles_favor_2t": int(r["goles_local_2t"] if r["equipo_local"] == visitante else r["goles_visitante_2t"]) if "goles_local_2t" in r.index and str(r["goles_local_2t"]) not in ["nan","None"] else None,
                "goles_contra_2t": int(r["goles_visitante_2t"] if r["equipo_local"] == visitante else r["goles_local_2t"]) if "goles_visitante_2t" in r.index and str(r["goles_visitante_2t"]) not in ["nan","None"] else None,
                "tarjetas_favor_1t": int(r["tarjetas_local_1t"] if r["equipo_local"] == visitante else r["tarjetas_visitante_1t"]) if "tarjetas_local_1t" in r.index and str(r["tarjetas_local_1t"]) not in ["nan","None"] else None,
                "tarjetas_favor_2t": int(r["tarjetas_local_2t"] if r["equipo_local"] == visitante else r["tarjetas_visitante_2t"]) if "tarjetas_local_2t" in r.index and str(r["tarjetas_local_2t"]) not in ["nan","None"] else None,
                "liga_partido": str(r["liga"]) if "liga" in r.index else "",
            })
    except Exception:
        pass"""

new = """    try:
        pv = obtener_partidos_equipo(df, visitante, n=20)
        for _, r in pv.iterrows():
            gl = int(r["goles_local"])
            gv = int(r["goles_visitante"])
            es_local = r["equipo_local"] == visitante
            gf = gl if es_local else gv
            gc = gv if es_local else gl
            ultimos_visitante.append({
                "fecha": str(r["fecha"])[:10],
                "rival": r["equipo_visitante"] if es_local else r["equipo_local"],
                "resultado": f"{gf}-{gc}",
                "ganado": gf > gc,
                "empate": gf == gc,
                "corners": int(r["corners_local"] if es_local else r["corners_visitante"]) if "corners_local" in r.index and str(r["corners_local"]) != "nan" else 0,
                "tarjetas": int(r["tarjetas_local"] if es_local else r["tarjetas_visitante"]) if "tarjetas_local" in r.index and str(r["tarjetas_local"]) != "nan" else 0,
                "tiros_arco": int(r["tiros_arco_local"] if es_local else r["tiros_arco_visitante"]) if "tiros_arco_local" in r.index and str(r["tiros_arco_local"]) != "nan" else 0,
                "tiros_total": int(r["tiros_total_local"] if es_local else r["tiros_total_visitante"]) if "tiros_total_local" in r.index and str(r["tiros_total_local"]) != "nan" else 0,
                "goles_favor_1t": int(r["goles_local_1t"] if es_local else r["goles_visitante_1t"]) if "goles_local_1t" in r.index and str(r["goles_local_1t"]) not in ["nan","None"] else None,
                "goles_contra_1t": int(r["goles_visitante_1t"] if es_local else r["goles_local_1t"]) if "goles_visitante_1t" in r.index and str(r["goles_visitante_1t"]) not in ["nan","None"] else None,
                "goles_favor_2t": int(r["goles_local_2t"] if es_local else r["goles_visitante_2t"]) if "goles_local_2t" in r.index and str(r["goles_local_2t"]) not in ["nan","None"] else None,
                "goles_contra_2t": int(r["goles_visitante_2t"] if es_local else r["goles_local_2t"]) if "goles_visitante_2t" in r.index and str(r["goles_visitante_2t"]) not in ["nan","None"] else None,
                "tarjetas_favor_1t": int(r["tarjetas_local_1t"] if es_local else r["tarjetas_visitante_1t"]) if "tarjetas_local_1t" in r.index and str(r["tarjetas_local_1t"]) not in ["nan","None"] else None,
                "tarjetas_favor_2t": int(r["tarjetas_local_2t"] if es_local else r["tarjetas_visitante_2t"]) if "tarjetas_local_2t" in r.index and str(r["tarjetas_local_2t"]) not in ["nan","None"] else None,
                "liga_partido": str(r["liga"]) if "liga" in r.index else "",
            })
    except Exception:
        pass"""

if old in content:
    content = content.replace(old, new, 1)
    with open("app/services/futbol_service.py", "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print("OK: bug de resultado invertido corregido en ultimos_visitante")
else:
    print("ERROR: patron no encontrado, verificar diferencias de espacios")
