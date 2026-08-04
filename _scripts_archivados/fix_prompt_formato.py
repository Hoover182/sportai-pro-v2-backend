with open("app/services/futbol_service.py", "r", encoding="utf-8") as f:
    content = f.read()

old = '2) Usa emojis naturales para hacer visual.'
new = '2) Usa emojis naturales para hacer visual. IMPORTANTE DE FORMATO: separa cada seccion o idea con un salto de linea doble (una linea en blanco entre parrafos), para que el texto se lea comodo en pantallas pequenas de celular. NUNCA escribas todo en un solo bloque de texto corrido. Cada dato o mercado nuevo debe ir en su propia linea o parrafo corto, no mas de 2-3 oraciones seguidas sin salto de linea.'

if old in content:
    content = content.replace(old, new, 1)
    with open("app/services/futbol_service.py", "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print("OK: regla de formato agregada")
else:
    print("ERROR: no encontrado")
