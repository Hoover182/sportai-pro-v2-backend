def _safe(v):
    try:
        f = float(v)
        return 0.0 if f != f else round(f, 2)
    except:
        return 0.0

import os
import sys
import pandas as pd
from datetime import datetime

# Apuntar al CSV correcto
CSV_PATH = os.path.join(os.path.dirname(__file__), "futbol_partidos.csv")

# Agregar services al path para imports
sys.path.insert(0, os.path.dirname(__file__))

from data_loader import (
    cargar_partidos_csv as _cargar_csv,
    obtener_equipo_por_nombre,
    filtrar_ligas_validas,
    obtener_partidos_hoy_futbol,
    obtener_partidos_mas_recientes,
)
from football_model import (
    estadisticas_equipo_ultimos10,
    ultimos_enfrentamientos_directos,
    ajustar_medias_con_rival,
    obtener_partidos_equipo,
)
from simulator import simular_partido_futbol

LIGAS_IDS = {
    "Champions League": (2, None),
    "Europa League": (3, None),
    "Conference League": (848, None),
    "Premier League": (39, None),
    "La Liga": (140, None),
    "Serie A": (135, None),
    "Bundesliga": (78, None),
    "Ligue 1": (61, None),
    "Primeira Liga": (94, None),
    "Eredivisie": (88, None),
    "MLS": (253, 2026),
    "Liga MX": (262, None),
    "Copa Libertadores": (13, 2026),
    "Copa Sudamericana": (11, 2026),
    "Liga Profesional Argentina": (128, 2026),
    "Brasileirao": (71, 2026),
    "Liga Colombia": (239, 2026),
    "Liga Pro Ecuador": (242, 2026),
}

ORDEN_COMPETENCIAS = [
    "Champions League", "Europa League", "Conference League",
    "Premier League", "La Liga", "Serie A", "Bundesliga", "Ligue 1",
    "Primeira Liga", "Eredivisie", "MLS", "Liga MX",
    "Copa Libertadores", "Copa Sudamericana",
    "Liga Profesional Argentina", "Brasileirao",
    "Liga Colombia", "Liga Pro Ecuador",
]

OPUESTOS = {
    "Over 1.5 goles": "Under 1.5 goles", "Under 1.5 goles": "Over 1.5 goles",
    "Over 2.5 goles": "Under 2.5 goles", "Under 2.5 goles": "Over 2.5 goles",
    "Over 3.5 goles": "Under 3.5 goles", "Under 3.5 goles": "Over 3.5 goles",
    "Over 7.5 corners": "Under 7.5 corners", "Under 7.5 corners": "Over 7.5 corners",
    "Over 8.5 corners": "Under 8.5 corners", "Under 8.5 corners": "Over 8.5 corners",
    "Over 9.5 corners": "Under 9.5 corners", "Under 9.5 corners": "Over 9.5 corners",
    "Over 2.5 tarjetas": "Under 2.5 tarjetas", "Under 2.5 tarjetas": "Over 2.5 tarjetas",
    "Over 3.5 tarjetas": "Under 3.5 tarjetas", "Under 3.5 tarjetas": "Over 3.5 tarjetas",
    "Gana local": "Gana visitante", "Gana visitante": "Gana local",
}


def cargar_df():
    import os
    original = os.getcwd()
    os.chdir(os.path.dirname(__file__))
    df = _cargar_csv()
    os.chdir(original)
    if not df.empty:
        df = filtrar_ligas_validas(df)
    return df


def get_temporada(liga_nombre):
    hoy = datetime.now()
    temporada_europea = hoy.year if hoy.month >= 8 else hoy.year - 1
    if liga_nombre in LIGAS_IDS:
        liga_id, temporada_fija = LIGAS_IDS[liga_nombre]
        temporada = temporada_fija if temporada_fija else temporada_europea
        return liga_id, temporada
    return None, temporada_europea


def simular(df, local, visitante):
    stats_a = estadisticas_equipo_ultimos10(df, local)
    stats_b = estadisticas_equipo_ultimos10(df, visitante)
    if stats_a is None or stats_b is None:
        return None, None, None
    h2h = ultimos_enfrentamientos_directos(df, local, visitante, n=5)
    goles_a, goles_b, corners_a, corners_b, tarjetas = ajustar_medias_con_rival(
        stats_a, stats_b, h2h
    )
    sim = simular_partido_futbol(
        goles_a, goles_b,
        stats_a["std_goles_favor"], stats_b["std_goles_favor"],
        corners_a, corners_b, tarjetas
    )
    return sim, stats_a, stats_b


def calcular_top3(sim, stats_a=None, stats_b=None):
    stats_ok = (
        stats_a and stats_b and
        stats_a.get("n_partidos_stats", 0) >= 3 and
        stats_b.get("n_partidos_stats", 0) >= 3
    )
    candidatos = [
        ("Gana local", sim["prob_local"]),
        ("Empate", sim["prob_empate"]),
        ("Gana visitante", sim["prob_visitante"]),
        ("1X (Local o Empate)", sim["prob_1x"]),
        ("X2 (Empate o Visitante)", sim["prob_x2"]),
        ("Ambos marcan", sim["prob_ambos_marcan"]),
        ("Over 1.5 goles", sim["goles_ou"][1.5]["over"]),
        ("Under 1.5 goles", sim["goles_ou"][1.5]["under"]),
        ("Over 2.5 goles", sim["goles_ou"][2.5]["over"]),
        ("Under 2.5 goles", sim["goles_ou"][2.5]["under"]),
        ("Over 3.5 goles", sim["goles_ou"][3.5]["over"]),
        ("Under 3.5 goles", sim["goles_ou"][3.5]["under"]),
    ]
    if stats_ok:
        candidatos += [
            ("Over 7.5 corners", sim["corners_ou"][7.5]["over"]),
            ("Under 7.5 corners", sim["corners_ou"][7.5]["under"]),
            ("Over 8.5 corners", sim["corners_ou"][8.5]["over"]),
            ("Under 8.5 corners", sim["corners_ou"][8.5]["under"]),
            ("Over 2.5 tarjetas", sim["tarjetas_ou"][2.5]["over"]),
            ("Under 2.5 tarjetas", sim["tarjetas_ou"][2.5]["under"]),
            ("Over 3.5 tarjetas", sim["tarjetas_ou"][3.5]["over"]),
            ("Under 3.5 tarjetas", sim["tarjetas_ou"][3.5]["under"]),
        ]
    candidatos = sorted(candidatos, key=lambda x: x[1], reverse=True)
    resultado = []
    usados = set()
    for nombre, prob in candidatos:
        if prob < 0.60:
            break
        if nombre in usados or OPUESTOS.get(nombre) in usados:
            continue
        resultado.append({"mercado": nombre, "prob": round(prob * 100, 1)})
        usados.add(nombre)
        if len(resultado) == 3:
            break
    return resultado


def get_partidos_hoy():
    df = cargar_df()
    if df.empty:
        return []
    partidos = obtener_partidos_hoy_futbol(df)
    if partidos.empty:
        return []
    resultado = []
    ligas_en_datos = partidos["liga"].unique().tolist()
    ligas_ordenadas = [l for l in ORDEN_COMPETENCIAS if l in ligas_en_datos]
    ligas_ordenadas += [l for l in ligas_en_datos if l not in ORDEN_COMPETENCIAS]
    for liga in ligas_ordenadas:
        partidos_liga = partidos[partidos["liga"] == liga]
        for _, row in partidos_liga.iterrows():
            fecha = str(row["fecha"].date()) if hasattr(row["fecha"], "date") else str(row["fecha"])[:10]
            hora = str(row["fecha"].time())[:5] if hasattr(row["fecha"], "time") else ""
            resultado.append({
                "liga": liga,
                "local": row["equipo_local"],
                "visitante": row["equipo_visitante"],
                "fecha": fecha,
                "hora": hora,
            })
    return resultado


def get_top_picks():
    df = cargar_df()
    if df.empty:
        return []
    partidos = obtener_partidos_hoy_futbol(df)
    if partidos.empty:
        partidos = obtener_partidos_mas_recientes(df, n=20)
    if partidos.empty:
        return []
    resultados = []
    for _, row in partidos.iterrows():
        local = row["equipo_local"]
        visitante = row["equipo_visitante"]
        liga = row["liga"]
        sim, stats_a, stats_b = simular(df, local, visitante)
        if sim is None:
            continue
        top3 = calcular_top3(sim, stats_a, stats_b)
        if not top3:
            continue
        for pick in top3:
            resultados.append({
                "liga": liga,
                "partido": f"{local} vs {visitante}",
                "mercado": pick["mercado"],
                "prob": pick["prob"],
            })
    resultados.sort(key=lambda x: x["prob"], reverse=True)
    return resultados


def get_analisis_partido(local_input, visitante_input):
    df = cargar_df()
    if df.empty:
        return None, "No hay datos disponibles"
    local = obtener_equipo_por_nombre(df, local_input)
    visitante = obtener_equipo_por_nombre(df, visitante_input)
    if local is None:
        return None, f"Equipo no encontrado: {local_input}"
    if visitante is None:
        return None, f"Equipo no encontrado: {visitante_input}"
    sim, stats_a, stats_b = simular(df, local, visitante)
    if sim is None:
        return None, "No hay datos suficientes para simular"
    try:
        liga_series = df[
            (df["equipo_local"] == local) | (df["equipo_visitante"] == local)
        ]["liga"]
        liga = liga_series.iloc[0] if not liga_series.empty else "Desconocida"
    except Exception:
        liga = "Desconocida"
    top3 = calcular_top3(sim, stats_a, stats_b)
    ultimos_local = []
    ultimos_visitante = []
    try:
        pl = obtener_partidos_equipo(df, local, n=10)
        for _, r in pl.iterrows():
            gl = int(r["goles_local"])
            gv = int(r["goles_visitante"])
            es_local = r["equipo_local"] == local
            gf = gl if es_local else gv
            gc = gv if es_local else gl
            ultimos_local.append({
                "fecha": str(r["fecha"])[:10],
                "rival": r["equipo_visitante"] if es_local else r["equipo_local"],
                "resultado": f"{gl}-{gv}",
                "ganado": gf > gc,
                "empate": gf == gc,
            })
    except Exception:
        pass
    try:
        pv = obtener_partidos_equipo(df, visitante, n=10)
        for _, r in pv.iterrows():
            gl = int(r["goles_local"])
            gv = int(r["goles_visitante"])
            es_local = r["equipo_local"] == visitante
            gf = gl if es_local else gv
            gc = gv if es_local else gl
            ultimos_visitante.append({
                "fecha": str(r["fecha"])[:10],
                "rival": r["equipo_visitante"] if es_local else r["equipo_local"],
                "resultado": f"{gl}-{gv}",
                "ganado": gf > gc,
                "empate": gf == gc,
            })
    except Exception:
        pass
    return {
        "local": local,
        "visitante": visitante,
        "liga": liga,
        "prob_local": round(sim["prob_local"] * 100, 1),
        "prob_empate": round(sim["prob_empate"] * 100, 1),
        "prob_visitante": round(sim["prob_visitante"] * 100, 1),
        "prob_1x": round(sim["prob_1x"] * 100, 1),
        "prob_x2": round(sim["prob_x2"] * 100, 1),
        "prob_ambos_marcan": round(sim["prob_ambos_marcan"] * 100, 1),
        "goles_proj": f"{sim['goles_local_proj']:.2f} - {sim['goles_visitante_proj']:.2f}",
        "corners_proj": round(sim["corners_totales_proj"], 2),
        "tarjetas_proj": round(sim["tarjetas_totales_proj"], 2),
        "goles_ou": {
            str(k): {"over": round(v["over"]*100,1), "under": round(v["under"]*100,1)}
            for k, v in sim["goles_ou"].items()
        },
        "corners_ou": {
            str(k): {"over": round(v["over"]*100,1), "under": round(v["under"]*100,1)}
            for k, v in sim["corners_ou"].items()
        },
        "tarjetas_ou": {
            str(k): {"over": round(v["over"]*100,1), "under": round(v["under"]*100,1)}
            for k, v in sim["tarjetas_ou"].items()
        },
        "top3": top3,
        "ultimos_local": ultimos_local,
        "ultimos_visitante": ultimos_visitante,
        "stats_local_5": _stats_n_equipo(df, local, 5),
        "stats_local_10": _stats_n_equipo(df, local, 10),
        "stats_visitante_5": _stats_n_equipo(df, visitante, 5),
        "stats_visitante_10": _stats_n_equipo(df, visitante, 10),
        "cuotas": get_cuotas_partido(local, visitante, liga),
        "stats_local_temporada": _stats_temporada_actual(df, local),
        "stats_visitante_temporada": _stats_temporada_actual(df, visitante),
        "tiros_arco_local": 0,
        "stats_local": {
            "goles_favor": round(stats_a["goles_favor"], 2),
            "goles_contra": round(stats_a["goles_contra"], 2),
            "corners_favor": round(stats_a["corners_favor"], 2),
            "corners_contra": round(stats_a["corners_contra"], 2),
            "tarjetas_favor": round(stats_a["tarjetas_favor"], 2),
            "tiros_arco_favor": _safe(stats_a.get("tiros_arco_favor")),
            "tiros_total_favor": _safe(stats_a.get("tiros_total_favor")),
            "victorias": stats_a["victorias"],
            "empates": stats_a["empates"],
            "derrotas": stats_a["derrotas"],
            "n_partidos": stats_a["n_partidos"],
        },
        "stats_visitante": {
            "goles_favor": round(stats_b["goles_favor"], 2),
            "goles_contra": round(stats_b["goles_contra"], 2),
            "corners_favor": round(stats_b["corners_favor"], 2),
            "corners_contra": round(stats_b["corners_contra"], 2),
            "tarjetas_favor": round(stats_b["tarjetas_favor"], 2),
            "tiros_arco_favor": _safe(stats_b.get("tiros_arco_favor")),
            "tiros_total_favor": _safe(stats_b.get("tiros_total_favor")),
            "victorias": stats_b["victorias"],
            "empates": stats_b["empates"],
            "derrotas": stats_b["derrotas"],
            "n_partidos": stats_b["n_partidos"],
        },
        "tiros_arco_visitante": 0,
        "tiros_total_local": 0,
        "tiros_total_visitante": 0,
    }, None
def get_jugadores_partido(fixture_id, liga_nombre=None):
    from player_model import analizar_jugadores_partido
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app', 'services'))

    liga_id = None
    temporada = None

    if liga_nombre:
        liga_id, temporada = get_temporada(liga_nombre)

    if not liga_id:
        return [], "Liga no encontrada"

    try:
        jugadores = analizar_jugadores_partido(fixture_id, liga_id, temporada)
    except Exception as e:
        return [], str(e)

    resultado = []
    for j in jugadores:
        resultado.append({
            "nombre": j["nombre"],
            "equipo": j["equipo"],
            "posicion": j["posicion"],
            "posicion_tipo": j["posicion_tipo"],
            "partidos": j["partidos"],
            "goles_pg": j["goles_pg"],
            "asist_pg": j["asist_pg"],
            "tiros_arco": {str(k): {"over": round(v["over"]*100,1), "under": round(v["under"]*100,1)} for k, v in j["tiros_arco"].items()},
            "tiros_total": {str(k): {"over": round(v["over"]*100,1), "under": round(v["under"]*100,1)} for k, v in j["tiros_total"].items()},
            "asistencias": {str(k): {"over": round(v["over"]*100,1), "under": round(v["under"]*100,1)} for k, v in j["asistencias"].items()},
            "tarjetas": {str(k): {"over": round(v["over"]*100,1), "under": round(v["under"]*100,1)} for k, v in j["tarjetas"].items()},
            "faltas": {str(k): {"over": round(v["over"]*100,1), "under": round(v["under"]*100,1)} for k, v in j["faltas"].items()},
        })

    return resultado, None










def _stats_n_equipo(df, equipo, n):
    import numpy as np
    from football_model import obtener_partidos_equipo
    try:
        ps = obtener_partidos_equipo(df, equipo, n=n)
        if ps.empty:
            return None
        gf_list, gc_list, cf_list, tf_list, ta_list = [], [], [], [], []
        v = e = d = 0
        for _, r in ps.iterrows():
            es_local = r["equipo_local"] == equipo
            gf = float(r["goles_local"] if es_local else r["goles_visitante"] or 0)
            gc = float(r["goles_visitante"] if es_local else r["goles_local"] or 0)
            gf_list.append(gf); gc_list.append(gc)
            if gf > gc: v += 1
            elif gf == gc: e += 1
            else: d += 1
            try:
                cf = float(r["corners_local"] if es_local else r["corners_visitante"] or 0)
                tf = float(r["tarjetas_local"] if es_local else r["tarjetas_visitante"] or 0)
                ta = float(r["tiros_arco_local"] if es_local else r["tiros_arco_visitante"] or 0)
                cf_list.append(cf); tf_list.append(tf); ta_list.append(ta)
            except: pass
        return {
            "goles_favor": round(float(np.mean(gf_list)), 2) if gf_list else 0,
            "goles_contra": round(float(np.mean(gc_list)), 2) if gc_list else 0,
            "corners_favor": round(float(np.mean(cf_list)), 2) if cf_list else 0,
            "tarjetas_favor": round(float(np.mean(tf_list)), 2) if tf_list else 0,
            "tiros_arco_favor": round(float(np.mean(ta_list)), 2) if ta_list else 0,
            "victorias": v, "empates": e, "derrotas": d, "n_partidos": len(ps)
        }
    except: return None


def _stats_temporada_actual(df, equipo):
    import numpy as np
    from football_model import obtener_partidos_equipo
    from datetime import datetime
    try:
        hoy = datetime.now()
        inicio_temp = f"{hoy.year if hoy.month >= 8 else hoy.year - 1}-07-01"
        ps = obtener_partidos_equipo(df, equipo, n=999)
        ps = ps[ps["fecha"] >= inicio_temp]
        if ps.empty:
            return None
        gf_list, gc_list, cf_list, tf_list, ta_list = [], [], [], [], []
        v = e = d = 0
        for _, r in ps.iterrows():
            es_local = r["equipo_local"] == equipo
            gf = float(r["goles_local"] if es_local else r["goles_visitante"] or 0)
            gc = float(r["goles_visitante"] if es_local else r["goles_local"] or 0)
            gf_list.append(gf); gc_list.append(gc)
            if gf > gc: v += 1
            elif gf == gc: e += 1
            else: d += 1
            try:
                cf = float(r["corners_local"] if es_local else r["corners_visitante"] or 0)
                tf = float(r["tarjetas_local"] if es_local else r["tarjetas_visitante"] or 0)
                ta = float(r["tiros_arco_local"] if es_local else r["tiros_arco_visitante"] or 0)
                cf_list.append(cf); tf_list.append(tf); ta_list.append(ta)
            except: pass
        return {
            "goles_favor": round(float(np.mean(gf_list)), 2) if gf_list else 0,
            "goles_contra": round(float(np.mean(gc_list)), 2) if gc_list else 0,
            "corners_favor": round(float(np.mean(cf_list)), 2) if cf_list else 0,
            "tarjetas_favor": round(float(np.mean(tf_list)), 2) if tf_list else 0,
            "tiros_arco_favor": round(float(np.mean(ta_list)), 2) if ta_list else 0,
            "victorias": v, "empates": e, "derrotas": d, "n_partidos": len(ps)
        }
    except: return None


def get_cuotas_partido(local, visitante, liga_nombre):
    import requests
    ODDS_API_KEY = "016ac8cef97435449ec8f235ada4cbad"
    LIGAS_ODDS = {
        "Premier League": "soccer_epl",
        "La Liga": "soccer_spain_la_liga",
        "Serie A": "soccer_italy_serie_a",
        "Bundesliga": "soccer_germany_bundesliga",
        "Ligue 1": "soccer_france_ligue_one",
        "Champions League": "soccer_uefa_champs_league",
        "Europa League": "soccer_uefa_europa_league",
        "Primeira Liga": "soccer_portugal_primeira_liga",
        "Eredivisie": "soccer_netherlands_eredivisie",
        "MLS": "soccer_usa_mls",
        "Liga MX": "soccer_mexico_ligamx",
        "Brasileirao": "soccer_brazil_campeonato",
        "Liga Profesional Argentina": "soccer_argentina_primera_division",
    }
    sport_key = LIGAS_ODDS.get(liga_nombre)
    if not sport_key:
        return []
    try:
        url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/"
        params = {
            "apiKey": ODDS_API_KEY,
            "regions": "eu",
            "markets": "h2h,totals",
            "oddsFormat": "decimal",
        }
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code != 200:
            return []
        data = resp.json()
        local_lower = local.lower()
        visitante_lower = visitante.lower()
        for partido in data:
            home = partido.get("home_team", "").lower()
            away = partido.get("away_team", "").lower()
            if (local_lower[:6] in home or home[:6] in local_lower) and \
               (visitante_lower[:6] in away or away[:6] in visitante_lower):
                home_team_lower = partido["home_team"].lower()
                away_team_lower = partido["away_team"].lower()
                cuotas = []
                for bm in partido.get("bookmakers", [])[:10]:
                    casa_data = {
                        "casa": bm["title"],
                        "local": 0,
                        "empate": 0,
                        "visitante": 0,
                        "totals": {},
                    }
                    for market in bm.get("markets", []):
                        if market["key"] == "h2h":
                            outcomes = {o["name"].lower(): o["price"] for o in market["outcomes"]}
                            casa_data["local"] = outcomes.get(home_team_lower, 0)
                            casa_data["empate"] = outcomes.get("draw", 0)
                            casa_data["visitante"] = outcomes.get(away_team_lower, 0)
                        elif market["key"] == "totals":
                            for o in market["outcomes"]:
                                punto = str(o.get("point", ""))
                                if not punto:
                                    continue
                                if punto not in casa_data["totals"]:
                                    casa_data["totals"][punto] = {"over": 0, "under": 0}
                                nombre = o.get("name", "").lower()
                                if nombre == "over":
                                    casa_data["totals"][punto]["over"] = o["price"]
                                elif nombre == "under":
                                    casa_data["totals"][punto]["under"] = o["price"]
                    if casa_data["local"] > 0 or casa_data["totals"]:
                        cuotas.append(casa_data)
                return cuotas
        return []
    except Exception:
        return []