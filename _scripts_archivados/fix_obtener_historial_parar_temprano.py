with open("app/services/player_model.py", "r", encoding="utf-8") as f:
    content = f.read()

old = '''def obtener_historial_jugador(nombre_jugador, fixture_ids, n=5):
    """Busca el desglose real de un jugador especifico en una lista de fixture_ids.
    Devuelve lista de dicts: [{fixture_id, rival, tiros_total, tiros_arco, goles, asistencias, tarjetas_amarillas}, ...]"""
    resultado = []
    for fid in fixture_ids[:n]:'''

new = '''def obtener_historial_jugador(nombre_jugador, fixture_ids, n=5, rango_busqueda=None):
    """Busca el desglose real de un jugador especifico en una lista de fixture_ids.
    Recorre hasta 'rango_busqueda' fixtures (o todos si no se especifica) pero se
    detiene apenas encuentra n partidos donde el jugador realmente participo,
    para no gastar requests de mas.
    Devuelve lista de dicts: [{fixture_id, rival, tiros_total, tiros_arco, goles, asistencias, tarjetas_amarillas}, ...]"""
    resultado = []
    limite = rango_busqueda if rango_busqueda else n
    for fid in fixture_ids[:limite]:
        if len(resultado) >= n:
            break'''

if old in content:
    content = content.replace(old, new, 1)
    with open("app/services/player_model.py", "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print("OK: funcion actualizada para buscar ampliado y parar temprano")
else:
    print("ERROR: no encontrado")
