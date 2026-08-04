with open("app/services/data_loader.py", "r", encoding="utf-8") as f:
    content = f.read()

old = "def obtener_partidos_mas_recientes(df, n=20):"

new = '''def obtener_partidos_rango_futbol(df, dias=4):
    """Devuelve partidos desde hoy hasta 'dias' dias en el futuro, agrupables por fecha."""
    if df.empty:
        return df
    hoy = pd.Timestamp.now(tz="America/Bogota").normalize()
    hasta = hoy + pd.Timedelta(days=dias - 1)

    if "estado" not in df.columns:
        return df[
            (df["fecha"].dt.normalize() >= hoy) &
            (df["fecha"].dt.normalize() <= hasta)
        ].copy()

    partidos = df[
        (df["fecha"].dt.normalize() >= hoy) &
        (df["fecha"].dt.normalize() <= hasta) &
        (df["estado"].isin(ESTADOS_EN_JUEGO))
    ].copy()
    return partidos


def obtener_partidos_mas_recientes(df, n=20):'''

if old in content:
    content = content.replace(old, new, 1)
    with open("app/services/data_loader.py", "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print("OK: funcion obtener_partidos_rango_futbol agregada")
else:
    print("ERROR: no encontrado")
