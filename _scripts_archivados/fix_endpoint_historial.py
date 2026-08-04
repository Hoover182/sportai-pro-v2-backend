with open("app/routes/futbol.py", "r", encoding="utf-8") as f:
    content = f.read()

old = '''@router.get("/jugadores/{local}/{visitante}")
async def jugadores(local: str, visitante: str):
    try:
        resultado, error = futbol_service.get_jugadores_partido(local, visitante)
        if error:
            return {"error": error}
        return resultado'''

new = '''@router.get("/jugadores/{local}/{visitante}")
async def jugadores(local: str, visitante: str):
    try:
        resultado, error = futbol_service.get_jugadores_partido(local, visitante)
        if error:
            return {"error": error}
        return resultado
    except Exception as e:
        return {"error": str(e)}


@router.get("/jugador-historial/{equipo}/{jugador}")
async def jugador_historial(equipo: str, jugador: str, n: int = 5):
    try:
        resultado, error = futbol_service.get_historial_jugador(equipo, jugador, n=n)
        if error:
            return {"error": error}
        return {"historial": resultado}'''

if old in content:
    content = content.replace(old, new, 1)
    with open("app/routes/futbol.py", "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print("OK: endpoint jugador-historial agregado")
else:
    print("ERROR: no encontrado")
