with open("app/services/player_model.py", "r", encoding="utf-8") as f:
    content = f.read()

old = '''def obtener_historial_jugador(nombre_jugador, fixture_ids, n=5):
    """Busca el desglose real de un jugador especifico en una lista de fixture_ids.
    Devuelve lista de dicts: [{fixture_id, tiros_total, tiros_arco, goles, asistencias, tarjetas_amarillas}, ...]"""
    resultado = []
    for fid in fixture_ids[:n]:
        datos_fixture = obtener_stats_jugadores_fixture(fid)
        for equipo in datos_fixture:
            for j in equipo.get("players", []):
                nombre = j.get("player", {}).get("name", "")
                if nombre.lower() != nombre_jugador.lower():
                    continue'''

new = '''def _normalizar_nombre(nombre):
    """Quita acentos y pasa a minusculas para comparar nombres de forma flexible."""
    import unicodedata
    nfkd = unicodedata.normalize("NFKD", nombre)
    sin_acentos = "".join(c for c in nfkd if not unicodedata.combining(c))
    return sin_acentos.lower().strip()


def _nombres_coinciden(nombre_a, nombre_b):
    """Compara nombres de forma flexible: exacto, o coincidencia de apellido
    (util cuando un lado tiene nombre abreviado tipo 'J. Ordonez' y el otro
    tiene el nombre completo 'Jorge Ordonez')."""
    a = _normalizar_nombre(nombre_a)
    b = _normalizar_nombre(nombre_b)
    if a == b:
        return True
    partes_a = a.replace(".", "").split()
    partes_b = b.replace(".", "").split()
    if not partes_a or not partes_b:
        return False
    apellido_a = partes_a[-1]
    apellido_b = partes_b[-1]
    if apellido_a != apellido_b or len(apellido_a) < 3:
        return False
    inicial_a = partes_a[0][0] if partes_a[0] else ""
    inicial_b = partes_b[0][0] if partes_b[0] else ""
    return inicial_a == inicial_b


def obtener_historial_jugador(nombre_jugador, fixture_ids, n=5):
    """Busca el desglose real de un jugador especifico en una lista de fixture_ids.
    Devuelve lista de dicts: [{fixture_id, tiros_total, tiros_arco, goles, asistencias, tarjetas_amarillas}, ...]"""
    resultado = []
    for fid in fixture_ids[:n]:
        datos_fixture = obtener_stats_jugadores_fixture(fid)
        for equipo in datos_fixture:
            for j in equipo.get("players", []):
                nombre = j.get("player", {}).get("name", "")
                if not _nombres_coinciden(nombre, nombre_jugador):
                    continue'''

if old in content:
    content = content.replace(old, new, 1)
    with open("app/services/player_model.py", "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print("OK: comparacion de nombres flexible aplicada")
else:
    print("ERROR: no encontrado")
