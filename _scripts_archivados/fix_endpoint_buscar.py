with open("app/routes/futbol.py", "r", encoding="utf-8") as f:
    content = f.read()

old = '@router.get("/jugadores/{local}/{visitante}")'
new = '''@router.get("/buscar-jugador")
async def buscar_jugador(q: str, limite: int = 20):
    try:
        resultados = futbol_service.buscar_jugador_general(q, limite=limite)
        return {"jugadores": resultados}
    except Exception as e:
        return {"error": str(e)}


@router.get("/jugadores/{local}/{visitante}")'''

if old in content:
    content = content.replace(old, new, 1)
    with open("app/routes/futbol.py", "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print("OK: endpoint buscar-jugador agregado")
else:
    print("ERROR: no encontrado")
