with open("app/services/futbol_service.py", "r", encoding="utf-8") as f:
    content = f.read()

old = """    return sim, stats_a, stats_b"""

new = """    # Aplicar el multiplicador de intensidad ofensiva a los corners
    if multiplicador_corners != 1.0 and "corners_totales_proj" in sim:
        sim["corners_totales_proj"] = sim["corners_totales_proj"] * multiplicador_corners
        if "corners_ou" in sim:
            import numpy as np
            media_ajustada_c = max(sim["corners_totales_proj"], 0.1)
            valores_sim_c = np.random.poisson(media_ajustada_c, 10000)
            for linea_ou in list(sim["corners_ou"].keys()):
                sim["corners_ou"][linea_ou] = {
                    "over": float(np.mean(valores_sim_c > linea_ou)),
                    "under": float(np.mean(valores_sim_c < linea_ou)),
                }

    return sim, stats_a, stats_b"""

if old in content:
    content = content.replace(old, new, 1)
    with open("app/services/futbol_service.py", "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print("OK: multiplicador de corners aplicado al resultado final")
else:
    print("ERROR: no encontrado")
