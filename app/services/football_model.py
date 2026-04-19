import numpy as np
from value_bet import normalizar_std

# Minimos y maximos realistas por equipo
GOLES_MIN = 0.7
GOLES_MAX = 3.5
CORNERS_MIN = 3.0
CORNERS_MAX = 9.0     # subido de 8 a 9 — equipos top promedian 6-7
TARJETAS_MIN = 0.5    # por equipo
TARJETAS_MAX = 4.0    # por equipo


def obtener_partidos_equipo(df, equipo, n=10):
    partidos = df[
        (df["equipo_local"] == equipo) |
        (df["equipo_visitante"] == equipo)
    ].copy()
    if "estado" in partidos.columns:
        partidos = partidos[partidos["estado"].isin(["FT", "AET", "PEN"])]
    return partidos.sort_values("fecha", ascending=False).head(n)


def obtener_partidos_con_stats(df, equipo, n=10):
    """Retorna SOLO partidos con stats reales (corners o tarjetas > 0)."""
    partidos = df[
        (df["equipo_local"] == equipo) |
        (df["equipo_visitante"] == equipo)
    ].copy()
    if "estado" in partidos.columns:
        partidos = partidos[partidos["estado"].isin(["FT", "AET", "PEN"])]
    partidos_con_stats = partidos[
        (partidos["corners_local"] + partidos["corners_visitante"] > 0) |
        (partidos["tarjetas_local"] + partidos["tarjetas_visitante"] > 0)
    ]
    return partidos_con_stats.sort_values("fecha", ascending=False).head(n)


def _promedio_liga_con_stats(df, liga):
    """Calcula promedios de liga usando SOLO partidos con stats reales."""
    df_liga = df[df["liga"] == liga].copy()
    if "estado" in df_liga.columns:
        df_liga = df_liga[df_liga["estado"].isin(["FT", "AET", "PEN"])]

    df_liga_stats = df_liga[
        (df_liga["corners_local"] + df_liga["corners_visitante"] > 0) |
        (df_liga["tarjetas_local"] + df_liga["tarjetas_visitante"] > 0)
    ]

    resultado = {
        "goles": 1.3,
        "corners": 5.0,
        "tarjetas": 1.5,
        "tiros_arco": 4.0,
        "tiros_total": 12.0
    }

    if not df_liga.empty:
        g = (df_liga["goles_local"].mean() + df_liga["goles_visitante"].mean()) / 2
        if not np.isnan(g):
            resultado["goles"] = float(np.clip(g, GOLES_MIN, GOLES_MAX))

    if not df_liga_stats.empty:
        c = (df_liga_stats["corners_local"].mean() + df_liga_stats["corners_visitante"].mean()) / 2
        t = (df_liga_stats["tarjetas_local"].mean() + df_liga_stats["tarjetas_visitante"].mean()) / 2
        ta = (df_liga_stats["tiros_arco_local"].mean() + df_liga_stats["tiros_arco_visitante"].mean()) / 2

        if not np.isnan(c): resultado["corners"] = float(np.clip(c, CORNERS_MIN, CORNERS_MAX))
        if not np.isnan(t): resultado["tarjetas"] = float(np.clip(t, TARJETAS_MIN, TARJETAS_MAX))
        if not np.isnan(ta): resultado["tiros_arco"] = float(ta)

        if "tiros_total_local" in df_liga_stats.columns:
            tt = (df_liga_stats["tiros_total_local"].mean() + df_liga_stats["tiros_total_visitante"].mean()) / 2
            if not np.isnan(tt): resultado["tiros_total"] = float(tt)

    return resultado


def estadisticas_equipo_ultimos10(df, equipo, min_partidos=3):
    partidos = obtener_partidos_equipo(df, equipo, n=10)
    partidos_stats = obtener_partidos_con_stats(df, equipo, n=10)

    if partidos.empty:
        return None

    goles_favor = []
    goles_contra = []
    corners_favor = []
    corners_contra = []
    tarjetas_favor = []
    tiros_arco_favor = []
    tiros_arco_contra = []
    tiros_total_favor = []
    tiros_total_contra = []

    victorias = empates = derrotas = 0

    # Goles con todos los partidos
    for _, row in partidos.iterrows():
        if row["equipo_local"] == equipo:
            gf = float(row["goles_local"] or 0)
            gc = float(row["goles_visitante"] or 0)
        else:
            gf = float(row["goles_visitante"] or 0)
            gc = float(row["goles_local"] or 0)

        goles_favor.append(gf)
        goles_contra.append(gc)

        if gf > gc: victorias += 1
        elif gf == gc: empates += 1
        else: derrotas += 1

    # Corners, tarjetas y tiros solo con partidos con stats reales
    for _, row in partidos_stats.iterrows():
        if row["equipo_local"] == equipo:
            cf = float(row["corners_local"] or 0)
            cc = float(row["corners_visitante"] or 0)
            tf = float(row["tarjetas_local"] or 0)
            ta_f = float(row["tiros_arco_local"] or 0)
            ta_c = float(row["tiros_arco_visitante"] or 0)
            tt_f = float(row["tiros_total_local"] if "tiros_total_local" in row.index and row["tiros_total_local"] else 0)
            tt_c = float(row["tiros_total_visitante"] if "tiros_total_visitante" in row.index and row["tiros_total_visitante"] else 0)
        else:
            cf = float(row["corners_visitante"] or 0)
            cc = float(row["corners_local"] or 0)
            tf = float(row["tarjetas_visitante"] or 0)
            ta_f = float(row["tiros_arco_visitante"] or 0)
            ta_c = float(row["tiros_arco_local"] or 0)
            tt_f = float(row["tiros_total_visitante"] if "tiros_total_visitante" in row.index and row["tiros_total_visitante"] else 0)
            tt_c = float(row["tiros_total_local"] if "tiros_total_local" in row.index and row["tiros_total_local"] else 0)

        corners_favor.append(cf)
        corners_contra.append(cc)
        tarjetas_favor.append(tf)
        tiros_arco_favor.append(ta_f)
        tiros_arco_contra.append(ta_c)
        tiros_total_favor.append(tt_f)
        tiros_total_contra.append(tt_c)

    n_partidos = len(partidos)
    # n_partidos_stats = partidos con stats reales verificados
    n_partidos_stats = len(partidos_stats)
    pocos_datos = n_partidos < min_partidos

    liga = partidos["liga"].iloc[0] if not partidos.empty else ""
    prom_liga = _promedio_liga_con_stats(df, liga)

    # Sin stats reales usar promedio de liga
    if not corners_favor:
        corners_favor = [prom_liga["corners"]]
        corners_contra = [prom_liga["corners"]]
        tarjetas_favor = [prom_liga["tarjetas"]]
        tiros_arco_favor = [prom_liga["tiros_arco"]]
        tiros_arco_contra = [prom_liga["tiros_arco"]]
        tiros_total_favor = [prom_liga["tiros_total"]]
        tiros_total_contra = [prom_liga["tiros_total"]]

    if pocos_datos:
        peso_real = n_partidos / min_partidos
        peso_liga = 1 - peso_real

        media_gf  = np.mean(goles_favor)    * peso_real + prom_liga["goles"]      * peso_liga
        media_gc  = np.mean(goles_contra)   * peso_real + prom_liga["goles"]      * peso_liga
        media_cf  = np.mean(corners_favor)  * peso_real + prom_liga["corners"]    * peso_liga
        media_cc  = np.mean(corners_contra) * peso_real + prom_liga["corners"]    * peso_liga
        media_tf  = np.mean(tarjetas_favor) * peso_real + prom_liga["tarjetas"]   * peso_liga
        media_ta_f = np.mean(tiros_arco_favor)  * peso_real + prom_liga["tiros_arco"] * peso_liga
        media_ta_c = np.mean(tiros_arco_contra) * peso_real + prom_liga["tiros_arco"] * peso_liga
        media_tt_f = np.mean(tiros_total_favor)  * peso_real + prom_liga["tiros_total"] * peso_liga
        media_tt_c = np.mean(tiros_total_contra) * peso_real + prom_liga["tiros_total"] * peso_liga
    else:
        media_gf   = np.mean(goles_favor)
        media_gc   = np.mean(goles_contra)
        media_cf   = np.mean(corners_favor)
        media_cc   = np.mean(corners_contra)
        media_tf   = np.mean(tarjetas_favor)
        media_ta_f = np.mean(tiros_arco_favor)
        media_ta_c = np.mean(tiros_arco_contra)
        media_tt_f = np.mean(tiros_total_favor)
        media_tt_c = np.mean(tiros_total_contra)

    # Aplicar limites realistas
    media_gf  = float(np.clip(media_gf,  GOLES_MIN,    GOLES_MAX))
    media_gc  = float(np.clip(media_gc,  GOLES_MIN,    GOLES_MAX))
    media_cf  = float(np.clip(media_cf,  CORNERS_MIN,  CORNERS_MAX))
    media_cc  = float(np.clip(media_cc,  CORNERS_MIN,  CORNERS_MAX))
    media_tf  = float(np.clip(media_tf,  TARJETAS_MIN, TARJETAS_MAX))

    return {
        "log": partidos,
        "pocos_datos": pocos_datos,
        "n_partidos": n_partidos,
        "n_partidos_stats": n_partidos_stats,
        "goles_favor": media_gf,
        "goles_contra": media_gc,
        "std_goles_favor":   normalizar_std(np.std(goles_favor),    0.35),
        "std_goles_contra":  normalizar_std(np.std(goles_contra),   0.35),
        "corners_favor": media_cf,
        "corners_contra": media_cc,
        "std_corners_favor": normalizar_std(np.std(corners_favor),  1.0),
        "tarjetas_favor": media_tf,
        "std_tarjetas_favor": normalizar_std(np.std(tarjetas_favor), 0.8),
        "tiros_arco_favor": media_ta_f,
        "tiros_arco_contra": media_ta_c,
        "tiros_total_favor": media_tt_f,
        "tiros_total_contra": media_tt_c,
        "victorias": victorias,
        "empates": empates,
        "derrotas": derrotas,
        "puntos": victorias * 3 + empates
    }


def ultimos_enfrentamientos_directos(df, equipo_a, equipo_b, n=5):
    h2h = df[
        ((df["equipo_local"] == equipo_a) & (df["equipo_visitante"] == equipo_b)) |
        ((df["equipo_local"] == equipo_b) & (df["equipo_visitante"] == equipo_a))
    ].copy()
    if "estado" in h2h.columns:
        h2h = h2h[h2h["estado"].isin(["FT", "AET", "PEN"])]
    return h2h.sort_values("fecha", ascending=False).head(n)


def ajustar_medias_con_rival(stats_a, stats_b, h2h):
    # Base: promedio entre ataque propio y defensa rival
    goles_a   = (stats_a["goles_favor"]   + stats_b["goles_contra"])   / 2
    goles_b   = (stats_b["goles_favor"]   + stats_a["goles_contra"])   / 2
    corners_a = (stats_a["corners_favor"] + stats_b["corners_contra"]) / 2
    corners_b = (stats_b["corners_favor"] + stats_a["corners_contra"]) / 2
    tarjetas_total = stats_a["tarjetas_favor"] + stats_b["tarjetas_favor"]

    # Ajuste H2H — mas peso cuando hay mas partidos directos
    if not h2h.empty:
        n_h2h = len(h2h)
        # 1 partido=15%, 2=20%, 3=25%, 4+=30%
        peso_h2h = min(0.15 + (n_h2h - 1) * 0.05, 0.30)
        peso_base = 1 - peso_h2h

        goles_local_h2h = h2h["goles_local"].mean()
        goles_visit_h2h = h2h["goles_visitante"].mean()

        if not np.isnan(goles_local_h2h):
            goles_a = goles_a * peso_base + goles_local_h2h * peso_h2h
        if not np.isnan(goles_visit_h2h):
            goles_b = goles_b * peso_base + goles_visit_h2h * peso_h2h

        # Ajuste H2H para corners si hay datos
        h2h_con_stats = h2h[
            (h2h["corners_local"] + h2h["corners_visitante"] > 0)
        ]
        if not h2h_con_stats.empty:
            corners_h2h_a = h2h_con_stats["corners_local"].mean()
            corners_h2h_b = h2h_con_stats["corners_visitante"].mean()
            if not np.isnan(corners_h2h_a):
                corners_a = corners_a * peso_base + corners_h2h_a * peso_h2h
            if not np.isnan(corners_h2h_b):
                corners_b = corners_b * peso_base + corners_h2h_b * peso_h2h

    # Aplicar limites finales
    goles_a        = float(np.clip(goles_a,        GOLES_MIN,    GOLES_MAX))
    goles_b        = float(np.clip(goles_b,        GOLES_MIN,    GOLES_MAX))
    corners_a      = float(np.clip(corners_a,      CORNERS_MIN,  CORNERS_MAX))
    corners_b      = float(np.clip(corners_b,      CORNERS_MIN,  CORNERS_MAX))
    tarjetas_total = float(np.clip(tarjetas_total, 1.5,          8.0))

    return goles_a, goles_b, corners_a, corners_b, tarjetas_total
