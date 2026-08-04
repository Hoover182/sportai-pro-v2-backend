with open("app/services/futbol_service.py", "r", encoding="utf-8") as f:
    content = f.read()

old = "2) Usa emojis naturales para hacer visual."

new = "2) USA EMOJIS DE FORMA CONSISTENTE Y VISUAL: cada seccion o subtitulo de tu respuesta DEBE empezar con un emoji relevante (ejemplo: usa un emoji de grafico como cabecera de analisis, un circulo amarillo para tarjetas, una pelota para goles, una bandera para corners, un trofeo para conclusiones, una lupa para desglose de datos). Dentro de cada seccion, resalta los numeros o datos mas importantes con un emoji corto al lado (una flecha hacia arriba o hacia abajo segun si el dato es alto o bajo, un check para lo que respalda tu conclusion). No dejes ningun bloque largo de texto sin al menos un emoji cada 2-3 lineas. El objetivo es que el usuario pueda escanear visualmente la respuesta sin tener que leer cada palabra."

if old in content:
    content = content.replace(old, new, 1)
    with open("app/services/futbol_service.py", "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print("OK: instruccion de emojis reforzada")
else:
    print("ERROR: no encontrado")
