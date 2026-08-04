with open("app/services/futbol_service.py", "r", encoding="utf-8") as f:
    content = f.read()

old = """        multiplicador_tarjetas = min(multiplicador_tarjetas, 1.5)
    except Exception:
        multiplicador_tarjetas = 1.0"""

new = """        multiplicador_tarjetas = min(multiplicador_tarjetas, 1.5)

        # ---- Multiplicador de corners basado en intensidad ofensiva reciente ----
        from modelo_presion import calcular_indice_intensidad_ofensiva
        intensidad_local, _ = calcular_indice_intensidad_ofensiva(df, local, liga_partido)
        intensidad_visitante, _ = calcular_indice_intensidad_ofensiva(df, visitante, liga_partido)
        intensidad_promedio = (intensidad_local + intensidad_visitante) / 2
        # Base 1.0, hasta +/-20% segun que tan ofensivos vienen ambos equipos
        multiplicador_corners = 0.9 + (intensidad_promedio * 0.3)
        multiplicador_corners = max(0.8, min(multiplicador_corners, 1.3))
    except Exception:
        multiplicador_tarjetas = 1.0
        multiplicador_corners = 1.0"""

if old in content:
    content = content.replace(old, new, 1)
    with open("app/services/futbol_service.py", "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print("OK: multiplicador de corners calculado")
else:
    print("ERROR: no encontrado")
