with open("app/services/futbol_service.py", "r", encoding="utf-8") as f:
    content = f.read()

old = "from data_loader import (\n    cargar_partidos_csv as _cargar_csv,\n    obtener_equipo_por_nombre,\n    filtrar_ligas_validas,\n    obtener_partidos_hoy_futbol,\n    obtener_partidos_mas_recientes,\n)"

new = "from data_loader import (\n    cargar_partidos_csv as _cargar_csv,\n    obtener_equipo_por_nombre,\n    filtrar_ligas_validas,\n    obtener_partidos_hoy_futbol,\n    obtener_partidos_mas_recientes,\n    obtener_partidos_rango_futbol,\n)"

if old in content:
    content = content.replace(old, new, 1)
    print("OK: import agregado")
else:
    print("ERROR import")

old2 = "def get_top_picks():"

new2 = '''def get_partidos_rango(dias=4):
    import pytz
    df = cargar_df()
    if df.empty:
        return []
    partidos = obtener_partidos_rango_futbol(df, dias=dias)
    if partidos.empty:
        return []

    hoy = pd.Timestamp.now(tz="America/Bogota").normalize()
    resultado = []
    ligas_en_datos = partidos["liga"].unique().tolist()
    ligas_ordenadas = [l for l in ORDEN_COMPETENCIAS if l in ligas_en_datos]
    ligas_ordenadas += [l for l in ligas_en_datos if l not in ORDEN_COMPETENCIAS]

    for liga in ligas_ordenadas:
        partidos_liga = partidos[partidos["liga"] == liga]
        for _, row in partidos_liga.iterrows():
            fecha_normalizada = row["fecha"].normalize() if hasattr(row["fecha"], "normalize") else None
            dia_offset = (fecha_normalizada - hoy).days if fecha_normalizada is not None else 0

            fecha = str(row["fecha"].date()) if hasattr(row["fecha"], "date") else str(row["fecha"])[:10]
            hora = str(row["fecha"].time())[:5] if hasattr(row["fecha"], "time") else ""
            local = row["equipo_local"]
            visitante = row["equipo_visitante"]
            prob_local = prob_empate = prob_visitante = None
            ajuste_ia = None
            try:
                sim, stats_a, stats_b = simular(df, local, visitante)
                if sim is not None:
                    prob_local = round(sim["prob_local"] * 100, 1)
                    prob_empate = round(sim["prob_empate"] * 100, 1)
                    prob_visitante = round(sim["prob_visitante"] * 100, 1)
                    ajuste_info = _obtener_ajuste_ia(df, local, visitante)
                    if ajuste_info:
                        aj_l = ajuste_info.get("ajuste_local", 0)
                        aj_v = ajuste_info.get("ajuste_visitante", 0)
                        pl = prob_local + aj_l
                        pv = prob_visitante + aj_v
                        pe = prob_empate
                        total = pl + pe + pv
                        if total > 0:
                            factor = 100 / total
                            pl, pe, pv = pl * factor, pe * factor, pv * factor
                        prob_local = round(max(1, min(98, pl)), 1)
                        prob_visitante = round(max(1, min(98, pv)), 1)
                        prob_empate = round(max(1, 100 - prob_local - prob_visitante), 1)
                        ajuste_ia = ajuste_info
            except Exception:
                pass

            resultado.append({
                "liga": liga,
                "local": local,
                "visitante": visitante,
                "fecha": fecha,
                "hora": hora,
                "dia_offset": dia_offset,
                "prob_local": prob_local,
                "prob_empate": prob_empate,
                "prob_visitante": prob_visitante,
                "ajuste_ia": ajuste_ia,
            })
    return resultado


def get_top_picks():'''

if old2 in content:
    content = content.replace(old2, new2, 1)
    print("OK: get_partidos_rango agregada")
else:
    print("ERROR get_top_picks")

with open("app/services/futbol_service.py", "w", encoding="utf-8", newline="\n") as f:
    f.write(content)
