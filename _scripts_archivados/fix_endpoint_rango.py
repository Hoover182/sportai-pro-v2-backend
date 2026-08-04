with open("app/routes/futbol.py", "r", encoding="utf-8") as f:
    content = f.read()

old = '''@router.get("/partidos-hoy")
async def partidos_hoy():
    partidos = futbol_service.get_partidos_hoy()
    return {"partidos": partidos}'''

new = '''@router.get("/partidos-hoy")
async def partidos_hoy():
    partidos = futbol_service.get_partidos_hoy()
    return {"partidos": partidos}


@router.get("/partidos-rango")
async def partidos_rango(dias: int = 4):
    partidos = futbol_service.get_partidos_rango(dias=dias)
    return {"partidos": partidos}'''

if old in content:
    content = content.replace(old, new, 1)
    with open("app/routes/futbol.py", "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print("OK: endpoint partidos-rango agregado")
else:
    print("ERROR: no encontrado")
