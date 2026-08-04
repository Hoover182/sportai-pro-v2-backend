with open("app/services/futbol_service.py", "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace(
    "pl = obtener_partidos_equipo(df, local, n=10)",
    "pl = obtener_partidos_equipo(df, local, n=20)"
)
content = content.replace(
    "pv = obtener_partidos_equipo(df, visitante, n=10)",
    "pv = obtener_partidos_equipo(df, visitante, n=20)"
)

with open("app/services/futbol_service.py", "w", encoding="utf-8", newline="\n") as f:
    f.write(content)
print("OK: n subido a 20")
