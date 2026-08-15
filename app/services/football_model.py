import numpy as np
import pandas as pd
from fifa_ranking import ajuste_fifa
from value_bet import normalizar_std

# Minimos y maximos realistas por equipo
# Constantes para ligas de clubes
GOLES_MIN = 0.7
GOLES_MAX = 3.5
CORNERS_MIN = 3.0
CORNERS_MAX = 9.0     # subido de 8 a 9 - equipos top promedian 6-7
TARJETAS_MIN = 0.5    # por equipo
TARJETAS_MAX = 4.0    # por equipo

# Constantes especificas para torneos de selecciones (Mundial, Copas)
# Basadas en datos reales del Mundial 2026: 2.97 goles, 8.96 corners, 2.53 tarjetas por partido
TORNEOS_SELECCIONES = ["Mundial 2026", "Copa America", "Eurocopa", "Nations League"]
GOLES_MIN_SELECC    = 0.8
GOLES_MAX_SELECC    = 3.2   # partidos eliminatorios son mas cerrados
CORNERS_MIN_SELECC  = 3.5
CORNERS_MAX_SELECC  = 10.0  # mundial 2026 promedia 8.96
TARJETAS_MIN_SELECC = 0.8   # mundial 2026 promedia 2.53 totales = 1.27 por equipo
TARJETAS_MAX_SELECC = 3.5   # por equipo


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

    # Goles con todos los partidos - ponderados por fuerza del rival (ranking FIFA)
    try:
        from fifa_ranking import get_puntos_fifa, es_seleccion_nacional
        usar_peso_fifa = True
    except Exception:
        usar_peso_fifa = False

    pesos_partidos = []
    for _, row in partidos.iterrows():
        if row["equipo_local"] == equipo:
            gf = float(row["goles_local"] or 0)
            gc = float(row["goles_visitante"] or 0)
            rival = str(row["equipo_visitante"])
        else:
            gf = float(row["goles_visitante"] or 0)
            gc = float(row["goles_local"] or 0)
            rival = str(row["equipo_local"])

        # Calcular peso segun fuerza del rival
        peso = 1.0
        if usar_peso_fifa and es_seleccion_nacional(equipo) and es_seleccion_nacional(rival):
            pts_equipo = get_puntos_fifa(equipo)
            pts_rival  = get_puntos_fifa(rival)
            # Rival fuerte (mas puntos) -> peso mayor (partido mas valioso)
            # Rival debil (menos puntos) -> peso menor (partido menos valioso)
            ratio = pts_rival / max(pts_equipo, 1)
            peso = max(0.3, min(2.0, ratio))

        pesos_partidos.append(peso)
        goles_favor.append(gf * peso)
        goles_contra.append(gc * peso)

        if gf > gc: victorias += 1
        elif gf == gc: empates += 1
        else: derrotas += 1

    # Corners, tarjetas y tiros solo con partidos con stats reales
    # Ponderados por fuerza del rival (ranking FIFA) igual que goles
    for _, row in partidos_stats.iterrows():
        if row["equipo_local"] == equipo:
            cf = float(row["corners_local"] or 0)
            cc = float(row["corners_visitante"] or 0)
            tf = float(row["tarjetas_local"] or 0)
            ta_f = float(row["tiros_arco_local"] or 0)
            ta_c = float(row["tiros_arco_visitante"] or 0)
            tt_f = float(row["tiros_total_local"] if "tiros_total_local" in row.index and row["tiros_total_local"] else 0)
            tt_c = float(row["tiros_total_visitante"] if "tiros_total_visitante" in row.index and row["tiros_total_visitante"] else 0)
            rival_stats = str(row["equipo_visitante"])
        else:
            cf = float(row["corners_visitante"] or 0)
            cc = float(row["corners_local"] or 0)
            tf = float(row["tarjetas_visitante"] or 0)
            ta_f = float(row["tiros_arco_visitante"] or 0)
            ta_c = float(row["tiros_arco_local"] or 0)
            tt_f = float(row["tiros_total_visitante"] if "tiros_total_visitante" in row.index and row["tiros_total_visitante"] else 0)
            tt_c = float(row["tiros_total_local"] if "tiros_total_local" in row.index and row["tiros_total_local"] else 0)
            rival_stats = str(row["equipo_local"])

        # Peso por rival FIFA (mismo sistema que goles)
        peso_stats = 1.0
        if usar_peso_fifa and es_seleccion_nacional(equipo) and es_seleccion_nacional(rival_stats):
            pts_equipo = get_puntos_fifa(equipo)
            pts_rival  = get_puntos_fifa(rival_stats)
            ratio = pts_rival / max(pts_equipo, 1)
            peso_stats = max(0.3, min(2.0, ratio))

        corners_favor.append(cf * peso_stats)
        corners_contra.append(cc * peso_stats)
        tarjetas_favor.append(tf * peso_stats)
        tiros_arco_favor.append(ta_f * peso_stats)
        tiros_arco_contra.append(ta_c * peso_stats)
        tiros_total_favor.append(tt_f * peso_stats)
        tiros_total_contra.append(tt_c * peso_stats)

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

        # Medias ponderadas: suma(valor*peso) / suma(pesos) para normalizar
        suma_pesos = sum(pesos_partidos) if pesos_partidos else len(goles_favor)
        n_goles = len(goles_favor)
        media_gf  = (sum(goles_favor)  / suma_pesos if suma_pesos > 0 else np.mean(goles_favor))  * peso_real + prom_liga["goles"]      * peso_liga
        media_gc  = (sum(goles_contra) / suma_pesos if suma_pesos > 0 else np.mean(goles_contra)) * peso_real + prom_liga["goles"]      * peso_liga
        media_cf  = np.mean(corners_favor)  * peso_real + prom_liga["corners"]    * peso_liga
        media_cc  = np.mean(corners_contra) * peso_real + prom_liga["corners"]    * peso_liga
        media_tf  = np.mean(tarjetas_favor) * peso_real + prom_liga["tarjetas"]   * peso_liga
        media_ta_f = np.mean(tiros_arco_favor)  * peso_real + prom_liga["tiros_arco"] * peso_liga
        media_ta_c = np.mean(tiros_arco_contra) * peso_real + prom_liga["tiros_arco"] * peso_liga
        media_tt_f = np.mean(tiros_total_favor)  * peso_real + prom_liga["tiros_total"] * peso_liga
        media_tt_c = np.mean(tiros_total_contra) * peso_real + prom_liga["tiros_total"] * peso_liga
    else:
        suma_pesos = sum(pesos_partidos) if pesos_partidos else len(goles_favor)
        media_gf   = sum(goles_favor)  / suma_pesos if suma_pesos > 0 else np.mean(goles_favor)
        media_gc   = sum(goles_contra) / suma_pesos if suma_pesos > 0 else np.mean(goles_contra)
        media_cf   = np.mean(corners_favor)  if corners_favor  else 0.0
        media_cc   = np.mean(corners_contra) if corners_contra else 0.0
        media_tf   = np.mean(tarjetas_favor) if tarjetas_favor else 0.0
        media_ta_f = np.mean(tiros_arco_favor)   if tiros_arco_favor   else 0.0
        media_ta_c = np.mean(tiros_arco_contra)  if tiros_arco_contra  else 0.0
        media_tt_f = np.mean(tiros_total_favor)  if tiros_total_favor  else 0.0
        media_tt_c = np.mean(tiros_total_contra) if tiros_total_contra else 0.0

    # Detectar si es torneo de selecciones para usar constantes correctas
    try:
        liga_equipo = partidos["liga"].iloc[0] if not partidos.empty else ""
        es_torneo_selecc = liga_equipo in TORNEOS_SELECCIONES
    except Exception:
        es_torneo_selecc = False

    # Aplicar limites realistas segun tipo de competicion
    if es_torneo_selecc:
        media_gf  = float(np.clip(media_gf,  GOLES_MIN_SELECC,    GOLES_MAX_SELECC))
        media_gc  = float(np.clip(media_gc,  GOLES_MIN_SELECC,    GOLES_MAX_SELECC))
        media_cf  = float(np.clip(media_cf,  CORNERS_MIN_SELECC,  CORNERS_MAX_SELECC))
        media_cc  = float(np.clip(media_cc,  CORNERS_MIN_SELECC,  CORNERS_MAX_SELECC))
        media_tf  = float(np.clip(media_tf,  TARJETAS_MIN_SELECC, TARJETAS_MAX_SELECC))
    else:
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


def ajustar_medias_con_rival(stats_a, stats_b, h2h, equipo_local=None, equipo_visitante=None):
    # Base: promedio entre ataque propio y defensa rival
    goles_a   = (stats_a["goles_favor"]   + stats_b["goles_contra"])   / 2
    goles_b   = (stats_b["goles_favor"]   + stats_a["goles_contra"])   / 2
    corners_a = (stats_a["corners_favor"] + stats_b["corners_contra"]) / 2
    corners_b = (stats_b["corners_favor"] + stats_a["corners_contra"]) / 2
    tarjetas_total = stats_a["tarjetas_favor"] + stats_b["tarjetas_favor"]

    # Ajuste H2H - mas peso cuando hay mas partidos directos
    if not h2h.empty:
        n_h2h = len(h2h)
        # 1 partido=15%, 2=20%, 3=25%, 4+=30%
        peso_h2h = min(0.15 + (n_h2h - 1) * 0.05, 0.30)

        # Ajuste por antiguedad del H2H - el conjunto completo pesa menos
        # si el enfrentamiento mas reciente ya es viejo, aunque haya
        # varios partidos. Interpolacion entre 4 puntos de referencia:
        # 0 anos=100%, 1 ano=90%, 2 anos=70%, 3+ anos=50% (piso).
        try:
            fecha_mas_reciente = pd.to_datetime(h2h["fecha"]).max()
            if fecha_mas_reciente.tzinfo is not None:
                ahora_h2h = pd.Timestamp.now(tz=fecha_mas_reciente.tzinfo)
            else:
                ahora_h2h = pd.Timestamp.now()
            anios_desde_ultimo = (ahora_h2h - fecha_mas_reciente).days / 365.25
            multiplicador_antiguedad = np.interp(anios_desde_ultimo, [0, 1, 2, 3], [1.0, 0.9, 0.7, 0.5])
            peso_h2h = peso_h2h * multiplicador_antiguedad
        except Exception:
            pass

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

        # Ajuste H2H para tarjetas si hay datos
        h2h_con_tarjetas = h2h[
            h2h["tarjetas_local"].notna() & h2h["tarjetas_visitante"].notna()
        ]
        if not h2h_con_tarjetas.empty:
            tarjetas_h2h_total = (h2h_con_tarjetas["tarjetas_local"] + h2h_con_tarjetas["tarjetas_visitante"]).mean()
            if not np.isnan(tarjetas_h2h_total):
                tarjetas_total = tarjetas_total * peso_base + tarjetas_h2h_total * peso_h2h

    # Aplicar limites finales
    goles_a        = float(np.clip(goles_a,        GOLES_MIN,    GOLES_MAX))
    goles_b        = float(np.clip(goles_b,        GOLES_MIN,    GOLES_MAX))
    corners_a      = float(np.clip(corners_a,      CORNERS_MIN,  CORNERS_MAX))
    corners_b      = float(np.clip(corners_b,      CORNERS_MIN,  CORNERS_MAX))
    tarjetas_total = float(np.clip(tarjetas_total, 1.5,          8.0))

    # Ajuste FIFA - solo aplica para selecciones nacionales
    try:
        if equipo_local and equipo_visitante:
            from fifa_ranking import ajuste_fifa, es_seleccion_nacional, get_puntos_fifa
            if es_seleccion_nacional(equipo_local) and es_seleccion_nacional(equipo_visitante):
                pts_local = get_puntos_fifa(equipo_local)
                pts_visit = get_puntos_fifa(equipo_visitante)
                # Cap de goles segun rival: si gano 5-1 a un equipo debil, limitar impacto
                # Usar directamente los puntos FIFA como proxy de fuerza relativa
                # Media ponderada: 60% ranking FIFA, 40% datos reales cuando hay pocos partidos
                n_partidos_a = stats_a.get("n_partidos", 10)
                n_partidos_b = stats_b.get("n_partidos", 10)
                n_min = min(n_partidos_a, n_partidos_b)
                # Con 5 partidos -> 65% FIFA, con 10+ -> 30% FIFA
                peso_fifa = max(0.30, min(0.65, 0.65 - (n_min - 5) * 0.07))
                # Goles esperados segun ranking FIFA puro (Elo-like)
                diff_pts = (pts_local - pts_visit) / 400.0
                diff_pts = max(-1.0, min(1.0, diff_pts))
                media_total = (goles_a + goles_b) / 2
                goles_a_fifa = media_total * (1.0 + diff_pts * 0.5)
                goles_b_fifa = media_total * (1.0 - diff_pts * 0.5)
                # Blend: datos reales + FIFA
                goles_a = goles_a * (1 - peso_fifa) + goles_a_fifa * peso_fifa
                goles_b = goles_b * (1 - peso_fifa) + goles_b_fifa * peso_fifa
                # Corners proporcional a goles
                f_local = goles_a / max((goles_a + goles_b) / 2, 0.1)
                f_visit = goles_b / max((goles_a + goles_b) / 2, 0.1)
                corners_a = corners_a * f_local
                corners_b = corners_b * f_visit
    except Exception:
        pass
    return goles_a, goles_b, corners_a, corners_b, tarjetas_total
