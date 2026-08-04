with open("app/services/futbol_service.py", "r", encoding="utf-8") as f:
    content = f.read()

old = "6) Responde en espanol."
new = "7) IMPORTANTE - RIVALES DE COPA: cuando un partido del historico tenga la etiqueta RIVAL DE CATEGORIA MENOR, significa que el rival de ese partido especifico NO juega en Primera Division. Si mencionas ese partido, aclara que fue contra un equipo de categoria menor, y NO uses ese resultado como referencia principal de la forma del equipo. Prioriza los partidos SIN esa etiqueta para evaluar la forma real. 8) Responde en espanol."

if old in content:
    content = content.replace(old, new, 1)
    with open("app/services/futbol_service.py", "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print("OK: regla de categoria de rival agregada")
else:
    print("ERROR: no encontrado")
