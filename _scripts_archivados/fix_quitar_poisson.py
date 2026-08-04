with open("app/services/futbol_service.py", "r", encoding="utf-8") as f:
    content = f.read()

old = "CALCULA vos mismo una estimacion razonable de esa probabilidad usando el promedio como base de una distribucion de Poisson simple, y da tu mejor estimacion numerica con opinion clara"

new = "CALCULA vos mismo una estimacion razonable de esa probabilidad usando el promedio como base para un calculo estadistico interno, y da tu mejor estimacion numerica con opinion clara. IMPORTANTE: nunca menciones terminos tecnicos como Poisson, distribucion de probabilidad, o modelo estadistico al usuario; simplemente presenta el resultado final de forma natural, como si fuera un dato mas (ejemplo correcto: segun su rendimiento reciente, estimo un 28% de probabilidad; ejemplo incorrecto: usando una distribucion de Poisson calculo)"

if old in content:
    content = content.replace(old, new, 1)
    with open("app/services/futbol_service.py", "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print("OK: instruccion de evitar jerga tecnica agregada")
else:
    print("ERROR: no encontrado")
