with open("app/services/futbol_service.py", "r", encoding="utf-8") as f:
    content = f.read()

old = "10) DATOS DE JUGADORES: si te preguntan sobre un jugador especifico de alguno de los dos equipos (goles, tarjetas, tiros, rendimiento), revisa si hay informacion de jugadores en el contexto y usala. Si no encontras datos de ese jugador en el contexto actual, dilo claramente y sugiere al usuario revisar la seccion Jugadores del partido para ver sus estadisticas detalladas."

new = "10) DATOS DE JUGADORES: si te preguntan sobre un jugador especifico de alguno de los dos equipos (goles, tarjetas, tiros, rendimiento), revisa si hay informacion de jugadores en el contexto y usala. Si te preguntan especificamente por una probabilidad Over/Under de un jugador (por ejemplo Over 1.5 goles de tal jugador), y tenes su promedio por partido disponible en el contexto (goles_pg, asist_pg, tarjetas_pg, faltas_pg), CALCULA vos mismo una estimacion razonable de esa probabilidad usando el promedio como base de una distribucion de Poisson simple, y da tu mejor estimacion numerica con opinion clara, en vez de derivar al usuario a la seccion Jugadores. Solo si NO tenes el promedio de ese jugador en el contexto (ni el jugador aparece mencionado en absoluto), dilo claramente y sugeri revisar la seccion Jugadores del partido."

if old in content:
    content = content.replace(old, new, 1)
    with open("app/services/futbol_service.py", "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print("OK: instruccion reforzada para calcular OU de jugadores")
else:
    print("ERROR: no encontrado")
