with open("app/services/futbol_service.py", "r", encoding="utf-8") as f:
    content = f.read()

old = "8) Responde en espanol.\""

new = "8) Responde en espanol. 9) MERCADOS COMBINADOS NO PRE-CALCULADOS: si te preguntan por un mercado que no aparece calculado directamente en el contexto (por ejemplo ambos equipos reciben 2+ tarjetas, o el partido termina con mas de X corners totales combinados), NUNCA digas simplemente que no tienes ese dato disponible. En vez de eso, usa los datos individuales que SI tienes en el contexto (promedios, proyecciones Over/Under de cada equipo) para razonar y dar tu MEJOR ESTIMACION de esa probabilidad combinada, explicando brevemente tu razonamiento matematico, y siempre cerrando con tu conclusion habitual de opinion clara y probabilidad estimada. Es preferible dar una estimacion razonada basada en los datos que tenes, que decir que no lo podes calcular. 10) DATOS DE JUGADORES: si te preguntan sobre un jugador especifico de alguno de los dos equipos (goles, tarjetas, tiros, rendimiento), revisa si hay informacion de jugadores en el contexto y usala. Si no encontras datos de ese jugador en el contexto actual, dilo claramente y sugiere al usuario revisar la seccion Jugadores del partido para ver sus estadisticas detalladas.\""

if old in content:
    content = content.replace(old, new, 1)
    with open("app/services/futbol_service.py", "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print("OK: reglas de mercados combinados y jugadores agregadas al prompt del chat")
else:
    print("ERROR: no encontrado")
