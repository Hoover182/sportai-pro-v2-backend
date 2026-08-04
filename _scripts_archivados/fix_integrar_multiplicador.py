with open("app/services/futbol_service.py", "r", encoding="utf-8") as f:
    content = f.read()

old = '''    h2h = ultimos_enfrentamientos_directos(df, local, visitante, n=5)'''

new = '''    h2h = ultimos_enfrentamientos_directos(df, local, visitante, n=5)

    # ---- Filtros adicionales de tarjetas (arbitro, presion, agresividad, clasico) ----
    try:
        from modelo_presion import calcular_tabla, calcular_presion, calcular_indice_agresividad, es_clasico
        liga_partido = df[(df["equipo_local"] == local) | (df["equipo_visitante"] == local)]["liga"].iloc[0]
        tabla_liga = calcular_tabla(df, liga_partido)

        presion_local = calcular_presion(tabla_liga, local)
        presion_visitante = calcular_presion(tabla_liga, visitante)
        presion_promedio = (presion_local + presion_visitante) / 2

        agresividad_local, _ = calcular_indice_agresividad(df, local, liga_partido)
        agresividad_visitante, _ = calcular_indice_agresividad(df, visitante, liga_partido)
        agresividad_promedio = (agresividad_local + agresividad_visitante) / 2

        clasico = es_clasico(local, visitante)

        # Multiplicador combinado: base 1.0, cada factor puede sumar hasta +25%
        multiplicador_tarjetas = 1.0
        multiplicador_tarjetas += presion_promedio * 0.15
        multiplicador_tarjetas += agresividad_promedio * 0.10
        if clasico:
            multiplicador_tarjetas += 0.20
        multiplicador_tarjetas = min(multiplicador_tarjetas, 1.5)
    except Exception:
        multiplicador_tarjetas = 1.0'''

if old in content:
    content = content.replace(old, new, 1)
    with open("app/services/futbol_service.py", "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print("OK: calculo de multiplicador integrado")
else:
    print("ERROR: no encontrado")
