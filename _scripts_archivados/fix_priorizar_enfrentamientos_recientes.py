with open("app/services/futbol_service.py", "r", encoding="utf-8") as f:
    content = f.read()

old = "Prioriza los partidos SIN esa etiqueta para evaluar la forma real."

new = "Prioriza los partidos SIN esa etiqueta para evaluar la forma real. 8B) ANTIGUEDAD DE ENFRENTAMIENTOS DIRECTOS: si mencionas un enfrentamiento historico entre ambos equipos, prioriza SIEMPRE el mas reciente disponible en el contexto. Si el enfrentamiento directo mas reciente que tenes es de hace mas de 1 año, acompanialo siempre de su fecha exacta y aclara explicitamente que es un dato antiguo poco representativo de la forma actual (ejemplo correcto: el ultimo cruce entre ambos fue hace casi 2 anos, en noviembre de 2024, por lo que no es muy representativo del momento actual). Nunca presentes un enfrentamiento viejo como si fuera information reciente o relevante sin esa aclaracion."

if old in content:
    content = content.replace(old, new, 1)
    with open("app/services/futbol_service.py", "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print("OK: regla de antiguedad de enfrentamientos agregada")
else:
    print("ERROR: no encontrado")
