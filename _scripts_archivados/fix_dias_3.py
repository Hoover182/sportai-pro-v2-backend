with open("app/routes/futbol.py", "r", encoding="utf-8") as f:
    content = f.read()

old = "async def partidos_rango(dias: int = 4):"
new = "async def partidos_rango(dias: int = 3):"

if old in content:
    content = content.replace(old, new, 1)
    with open("app/routes/futbol.py", "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print("OK: default cambiado a 3 dias")
else:
    print("ERROR: no encontrado")
