with open("app/services/futbol_service.py", "r", encoding="utf-8") as f:
    content = f.read()

old = "IMPORTANTE DE FORMATO: separa cada seccion o idea con un salto de linea doble (una linea en blanco entre parrafos), para que el texto se lea comodo en pantallas pequenas de celular. NUNCA escribas todo en un solo bloque de texto corrido. Cada dato o mercado nuevo debe ir en su propia linea o parrafo corto, no mas de 2-3 oraciones seguidas sin salto de linea."

new = "IMPORTANTE DE FORMATO: usa saltos de linea doble SOLO entre secciones grandes distintas (por ejemplo entre el bloque de 1X2 y el bloque de goles, o entre goles y corners). Dentro de una misma seccion, agrupa los datos relacionados en lineas seguidas SIN saltos dobles entre ellos (ejemplo: Over 0.5: 87%, seguido en la siguiente linea simple de Over 1.5: 61%, sin linea en blanco entre ambas). Se compacto: agrupa 3 a 5 lineas relacionadas por seccion antes de saltar a la siguiente seccion con doble salto de linea."

if old in content:
    content = content.replace(old, new, 1)
    with open("app/services/futbol_service.py", "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print("OK: prompt mas compacto aplicado")
else:
    print("ERROR: no encontrado")
