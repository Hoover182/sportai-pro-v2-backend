with open("app/services/futbol_service.py", "r", encoding="utf-8") as f:
    content = f.read()

old = "    return sim, stats_a, stats_b"

new = '''    # Aplicar el multiplicador de arbitro/presion/agresividad/clasico a las tarjetas
    if multiplicador_tarjetas != 1.0 and "tarjetas_totales_proj" in sim:
        sim["tarjetas_totales_proj"] = sim["tarjetas_totales_proj"] * multiplicador_tarjetas
        if "tarjetas_ou" in sim:
            import numpy as np
            media_ajustada = max(sim["tarjetas_totales_proj"], 0.1)
            valores_sim = np.random.poisson(media_ajustada, 10000)
            for linea_ou in list(sim["tarjetas_ou"].keys()):
                sim["tarjetas_ou"][linea_ou] = {
                    "over": float(np.mean(valores_sim > linea_ou)),
                    "under": float(np.mean(valores_sim < linea_ou)),
                }

    return sim, stats_a, stats_b'''

if old in content:
    content = content.replace(old, new, 1)
    with open("app/services/futbol_service.py", "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print("OK: multiplicador aplicado al resultado final")
else:
    print("ERROR: no encontrado")
