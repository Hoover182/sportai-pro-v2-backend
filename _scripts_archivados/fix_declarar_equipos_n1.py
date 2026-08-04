with open("app/services/futbol_service.py", "r", encoding="utf-8") as f:
    content = f.read()

old = '''def get_analisis_partido(local_input, visitante_input):
    df = cargar_df()
    if df.empty:
        return None, "No hay datos disponibles"'''

new = '''def get_analisis_partido(local_input, visitante_input):
    df = cargar_df()
    if df.empty:
        return None, "No hay datos disponibles"
    equipos_n1 = obtener_equipos_nivel1(df)'''

if old in content:
    content = content.replace(old, new, 1)
    with open("app/services/futbol_service.py", "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print("OK: equipos_n1 declarada")
else:
    print("ERROR: no encontrado")
