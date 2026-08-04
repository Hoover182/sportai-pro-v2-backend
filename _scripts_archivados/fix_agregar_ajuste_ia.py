with open("app/services/futbol_service.py", "r", encoding="utf-8") as f:
    content = f.read()

old = '"goles_1t": _calcular_goles_1t(df, local, visitante),'

new = '''"goles_1t": _calcular_goles_1t(df, local, visitante),
        "ajuste_ia": _obtener_ajuste_ia(df, local, visitante),'''

if old in content:
    content = content.replace(old, new, 1)
    print("OK: ajuste_ia agregado al JSON")
else:
    print("ERROR: patron no encontrado")

# Agregar la funcion helper
old2 = "def _calcular_goles_1t(df, local, visitante):"

new2 = '''def _obtener_ajuste_ia(df, local, visitante):
    """Busca el ajuste cualitativo de IA para este partido si existe."""
    try:
        fila = df[(df["equipo_local"] == local) & (df["equipo_visitante"] == visitante)]
        if fila.empty:
            return None
        r = fila.iloc[0]
        if "ajuste_ia_local" not in r.index or pd.isna(r.get("ajuste_ia_local")):
            return None
        return {
            "ajuste_local": float(r["ajuste_ia_local"]),
            "ajuste_visitante": float(r["ajuste_ia_visitante"]),
            "explicacion": str(r["ajuste_ia_explicacion"]) if not pd.isna(r.get("ajuste_ia_explicacion")) else "",
        }
    except Exception:
        return None


def _calcular_goles_1t(df, local, visitante):'''

if old2 in content:
    content = content.replace(old2, new2, 1)
    print("OK: funcion _obtener_ajuste_ia agregada")
else:
    print("ERROR: _calcular_goles_1t no encontrado")

with open("app/services/futbol_service.py", "w", encoding="utf-8", newline="\n") as f:
    f.write(content)
