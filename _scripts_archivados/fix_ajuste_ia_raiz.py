with open("app/services/futbol_service.py", "r", encoding="utf-8") as f:
    content = f.read()

old = '''def _obtener_ajuste_ia(df, local, visitante):
    """Busca el ajuste cualitativo de IA para este partido si existe."""
    try:
        fila = df[(df["equipo_local"] == local) & (df["equipo_visitante"] == visitante)]
        if fila.empty:
            return None
        r = fila.iloc[0]'''

new = '''def _obtener_ajuste_ia(df, local, visitante):
    """Busca el ajuste cualitativo de IA para este partido si existe.
    Prioriza el partido mas reciente (o el pendiente NS) para evitar
    traer el ajuste de un enfrentamiento historico viejo entre los mismos equipos."""
    try:
        fila = df[(df["equipo_local"] == local) & (df["equipo_visitante"] == visitante)]
        if fila.empty:
            return None
        # Preferir partidos pendientes (NS), si no hay, tomar el mas reciente por fecha
        pendientes = fila[fila["estado"] == "NS"]
        if not pendientes.empty:
            fila_ordenada = pendientes.sort_values("fecha", ascending=False)
        else:
            fila_ordenada = fila.sort_values("fecha", ascending=False)
        r = fila_ordenada.iloc[0]'''

if old in content:
    content = content.replace(old, new, 1)
    with open("app/services/futbol_service.py", "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print("OK: fix de raiz aplicado a _obtener_ajuste_ia")
else:
    print("ERROR: no encontrado")
