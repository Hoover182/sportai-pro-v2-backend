"""Guion para TikTok: los partidos mas atractivos de una jornada, con tres
datos curiosos, estadisticas y la prediccion del modelo.

Todo sale de nuestro CSV y del modelo de produccion (futbol_service.simular);
no se inventa nada. Los datos curiosos son HECHOS del historial anterior al
partido. La prediccion usa solo mercados que pasaron su backtest y se
muestran en la app: 1X2 (y doble oportunidad, que sale del 1X2), tiros por
equipo y total de tiros del partido (O/U 24.5). Goles, ambos marcan,
corners, tarjetas, atajadas y tiros al arco del partido NO se predicen aca
(estan ocultos en la app porque no le ganan a la tasa de la liga).

Uso desde backend/:
  python scripts/guion_tiktok.py --desde 2026-11-26 --hasta 2026-11-26 \
      --ligas "Europa League" --n 4 --salida guion_europa.md
  (sin --ligas: Champions, Europa, Conference y las 5 grandes ligas)

--corte AAAA-MM-DD (opcional, para probar con una jornada pasada): usa solo
los datos anteriores a esa fecha y trata los partidos de la jornada como
proximos, igual que si se corriera la vispera.
"""
import argparse
import os
import re
import sys
from collections import Counter

import pandas as pd

AQUI = os.path.dirname(os.path.abspath(__file__))
SERVICES = os.path.join(AQUI, "..", "app", "services")
sys.path.insert(0, SERVICES)

LIGAS_DEFECTO = ["Champions League", "Europa League", "Conference League", "La Liga",
                 "Premier League", "Serie A", "Bundesliga", "Ligue 1"]
PESO_LIGA = {"Champions League": 1.0, "Europa League": 0.8, "Conference League": 0.6,
             "La Liga": 0.9, "Premier League": 0.9, "Serie A": 0.8, "Bundesliga": 0.8, "Ligue 1": 0.7}
TERMINADOS = ("FT", "AET", "PEN")
HORA_COLOMBIA = pd.Timedelta(hours=-5)
AVISO = ("Probabilidades del modelo de SportAI Pro, no garantias. Contenido para mayores de 18. "
         "Apuesta con responsabilidad.")


def cargar(csv, corte):
    import data_loader as DL
    if corte is None:
        DL.CSV_FUTBOL = os.path.abspath(csv)
        crudo = pd.read_csv(csv, low_memory=False)
        return crudo, None
    crudo = pd.read_csv(csv, low_memory=False)
    f = pd.to_datetime(crudo["fecha"], errors="coerce", utc=True)
    c = pd.Timestamp(corte, tz="UTC")
    previo = crudo[f < c].copy()
    jornada = crudo[f >= c].copy()
    for col in jornada.columns:   # la jornada como si no se hubiera jugado
        if col not in ("fecha", "fixture_id", "liga", "equipo_local", "equipo_visitante", "arbitro"):
            jornada[col] = None
    jornada["estado"] = "NS"
    tmp = os.path.join(os.path.dirname(os.path.abspath(csv)), f"_guion_corte_{corte}.csv")
    pd.concat([previo, jornada]).to_csv(tmp, index=False)
    DL.CSV_FUTBOL = tmp
    return pd.read_csv(tmp, low_memory=False), tmp


def ultimos(hist, equipo, n=10):
    h = hist[((hist["equipo_local"] == equipo) | (hist["equipo_visitante"] == equipo))
             & hist["estado"].isin(TERMINADOS) & hist["goles_local"].notna()]
    return h.sort_values("f").tail(n)


def resultado(r, equipo):
    es_l = r["equipo_local"] == equipo
    gf, gc = (r["goles_local"], r["goles_visitante"]) if es_l else (r["goles_visitante"], r["goles_local"])
    return ("G" if gf > gc else "E" if gf == gc else "P"), gf, gc, es_l


def racha(hist, equipo):
    """(tipo, largo) de la racha actual: invicto, sin ganar, ganando."""
    res = [resultado(r, equipo)[0] for _, r in ultimos(hist, equipo, 20).iloc[::-1].iterrows()]
    if not res:
        return None
    def largo(cond):
        n = 0
        for x in res:
            if not cond(x):
                break
            n += 1
        return n
    g, inv, sg = largo(lambda x: x == "G"), largo(lambda x: x != "P"), largo(lambda x: x != "G")
    if g >= 3:
        return ("victorias seguidas", g)
    if inv >= 5:
        return ("partidos sin perder", inv)
    if sg >= 4:
        return ("partidos sin ganar", sg)
    return None


def promedio(serie):
    s = pd.to_numeric(serie, errors="coerce").dropna()
    return float(s.mean()) if len(s) else None


def stats_equipo(hist, equipo):
    u = ultimos(hist, equipo, 10)
    if u.empty:
        return {}
    filas = [resultado(r, equipo) for _, r in u.iterrows()]
    def propio(col):
        return [r[f"{col}_local"] if r["equipo_local"] == equipo else r[f"{col}_visitante"] for _, r in u.iterrows()]
    tiros = pd.to_numeric(pd.Series(propio("tiros_total")), errors="coerce")
    tiros = tiros[tiros > 0]
    pos = pd.to_numeric(pd.Series(propio("posesion")), errors="coerce")
    pos = pos[pos > 0]
    forma = "".join(x[0] for x in filas[-5:])
    return {"n": len(filas), "forma5": forma,
            "gf": sum(x[1] for x in filas) / len(filas), "gc": sum(x[2] for x in filas) / len(filas),
            "vallas": sum(1 for x in filas if x[2] == 0),
            "mas25": sum(1 for x in filas if x[1] + x[2] > 2.5),
            "tiros": float(tiros.mean()) if len(tiros) >= 3 else None,
            "posesion": float(pos.mean()) if len(pos) >= 3 else None}


def h2h(hist, a, b):
    h = hist[(((hist["equipo_local"] == a) & (hist["equipo_visitante"] == b))
              | ((hist["equipo_local"] == b) & (hist["equipo_visitante"] == a)))
             & hist["estado"].isin(TERMINADOS) & hist["goles_local"].notna()].sort_values("f")
    if h.empty:
        return None
    c = Counter(resultado(r, a)[0] for _, r in h.iterrows())
    ult = h.iloc[-1]
    return {"n": len(h), "ga": c["G"], "e": c["E"], "gb": c["P"],
            "goles": float((h["goles_local"] + h["goles_visitante"]).mean()),
            "ultimo": (ult["f"].strftime("%d/%m/%Y"), ult["equipo_local"], int(ult["goles_local"]),
                       int(ult["goles_visitante"]), ult["equipo_visitante"], ult["liga"])}


def datos_curiosos(hist, local, visit, sl, sv, hh):
    """Candidatos (puntaje, texto) ordenados de mas a menos llamativo."""
    out = []
    if hh:
        if hh["n"] >= 3 and max(hh["ga"], hh["gb"]) >= 0.6 * hh["n"]:
            dom, w = (local, hh["ga"]) if hh["ga"] >= hh["gb"] else (visit, hh["gb"])
            out.append((3.0, f"{dom} ganó {w} de los últimos {hh['n']} cruces entre estos dos equipos."))
        else:
            out.append((1.5, f"Historial: {hh['n']} cruce(s) en nuestros datos — {local} {hh['ga']}, "
                             f"empates {hh['e']}, {visit} {hh['gb']}."))
        f_, l_, gl, gv, v_, lg = hh["ultimo"]
        out.append((1.2, f"El último cruce fue el {f_} ({lg}): {l_} {gl}-{gv} {v_}."))
        if hh["n"] >= 3 and hh["goles"] >= 3.2:
            out.append((2.0, f"Sus cruces son de muchos goles: promedio de {hh['goles']:.1f} por partido."))
    else:
        out.append((1.0, f"En nuestros datos no hay ningún cruce previo entre {local} y {visit}: primer duelo registrado."))
    for eq in (local, visit):
        r = racha(hist, eq)
        if r:
            out.append((2.2 + 0.1 * r[1], f"{eq} llega con {r[1]} {r[0]}."))
    for eq, s in ((local, sl), (visit, sv)):
        if not s:
            continue
        if s["vallas"] >= 5:
            out.append((2.0, f"{eq} dejó el arco en cero en {s['vallas']} de sus últimos {s['n']} partidos."))
        if s["gf"] >= 2.2:
            out.append((2.0, f"{eq} promedia {s['gf']:.1f} goles a favor en sus últimos {s['n']} partidos."))
        if s["mas25"] >= 8:
            out.append((1.8, f"{s['mas25']} de los últimos {s['n']} partidos de {eq} tuvieron más de 2,5 goles."))
        if s["tiros"] and s["tiros"] >= 16:
            out.append((1.6, f"{eq} remata mucho: {s['tiros']:.1f} tiros por partido en los últimos 10."))
        if s["posesion"] and s["posesion"] >= 60:
            out.append((1.4, f"{eq} es de tener la pelota: {s['posesion']:.0f}% de posesión promedio."))
    return sorted(out, key=lambda x: -x[0])


def prediccion(sim):
    pl, pe, pv = sim.get("prob_local"), sim.get("prob_empate"), sim.get("prob_visitante")
    return {"pl": pl, "pe": pe, "pv": pv,
            "1x": (pl or 0) + (pe or 0), "x2": (pv or 0) + (pe or 0),
            "tiros_l": sim.get("tiros_total_local_proj"), "tiros_v": sim.get("tiros_total_visitante_proj"),
            "tiros_t_o245": ((sim.get("tiros_total_ou") or {}).get(24.5) or {}).get("over")}


def pct(x):
    if x is None:
        return "—"
    return f"{x * 100:.0f}%" if x <= 1 else f"{x:.0f}%"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=os.path.join(SERVICES, "futbol_partidos.csv"))
    ap.add_argument("--desde", required=True)
    ap.add_argument("--hasta", required=True)
    ap.add_argument("--ligas", default=",".join(LIGAS_DEFECTO))
    ap.add_argument("--n", type=int, default=5)
    ap.add_argument("--corte")
    ap.add_argument("--salida", required=True)
    a = ap.parse_args()
    ligas = [x.strip() for x in a.ligas.split(",") if x.strip()]

    crudo, tmp = cargar(a.csv, a.corte)
    os.chdir(SERVICES)
    import futbol_service as FS
    import elo_ranking as ER
    df = FS.cargar_df()
    elo = ER.cargar_elo_ratings()

    crudo["f"] = pd.to_datetime(crudo["fecha"], errors="coerce", utc=True)
    d0 = pd.Timestamp(a.desde, tz="UTC")
    d1 = pd.Timestamp(a.hasta, tz="UTC") + pd.Timedelta(days=1)
    jornada = crudo[(crudo["estado"] == "NS") & (crudo["f"] >= d0) & (crudo["f"] < d1)
                    & crudo["liga"].isin(ligas)].drop_duplicates("fixture_id")
    hist = crudo[crudo["estado"].isin(TERMINADOS)]

    candidatos = []
    for _, p in jornada.iterrows():
        try:
            sim, sa, sb = FS.simular(df, p["equipo_local"], p["equipo_visitante"])
        except Exception as e:  # equipo sin datos: se saltea
            print("salteado", p["equipo_local"], "-", p["equipo_visitante"], e)
            continue
        if sim is None or sim.get("prob_local") is None:
            continue
        ea = (elo.get(p["equipo_local"]) or {}).get("rating", 1500)
        eb = (elo.get(p["equipo_visitante"]) or {}).get("rating", 1500)
        pr = prediccion(sim)
        parejo = 1 - abs((pr["pl"] or 0) - (pr["pv"] or 0)) / 100
        interes = (ea + eb) / 2 / 100 + 3 * parejo + 4 * PESO_LIGA.get(p["liga"], 0.5)
        candidatos.append((interes, p, sim, sa, sb, ea, eb))
    candidatos.sort(key=lambda x: -x[0])

    lineas = [f"# Guion TikTok — {a.desde}" + (f" al {a.hasta}" if a.hasta != a.desde else ""),
              "", f"Partidos elegidos: {min(a.n, len(candidatos))} de {len(candidatos)} con datos "
              f"({', '.join(ligas)}). Elegidos por nivel de los equipos (Elo), lo parejo del partido y la competencia.",
              "", "Los datos curiosos y las estadísticas salen de los partidos registrados en SportAI Pro "
              "(todas las competencias que seguimos), anteriores al partido.",
              "", f"> {AVISO}", ""]
    for i, (interes, p, sim, sa, sb, ea, eb) in enumerate(candidatos[: a.n], 1):
        loc, vis = p["equipo_local"], p["equipo_visitante"]
        h = hist[hist["f"] < p["f"]]
        sl, sv, hh = stats_equipo(h, loc), stats_equipo(h, vis), h2h(h, loc, vis)
        cur = [t for _, t in datos_curiosos(h, loc, vis, sl, sv, hh)][:3]
        pr = prediccion(sim)
        fav = max((pr["pl"] or 0, loc), (pr["pv"] or 0, vis))
        hora = (p["f"] + HORA_COLOMBIA).strftime("%d/%m %H:%M")
        lineas += [f"## {i}. {loc} vs {vis}", f"*{p['liga']} — {hora} (hora Colombia)*", "",
                   "**3 datos curiosos**"] + [f"{k}. {t}" for k, t in enumerate(cur, 1)] + [
            "", "**Estadísticas (últimos 10 partidos)**", "",
            f"| | {loc} | {vis} |", "|---|---|---|",
            f"| Forma, últimos 5 (G/E/P, el último a la derecha) | {sl.get('forma5', '—')} | {sv.get('forma5', '—')} |",
            f"| Goles a favor / en contra | {sl.get('gf', 0):.1f} / {sl.get('gc', 0):.1f} | {sv.get('gf', 0):.1f} / {sv.get('gc', 0):.1f} |",
            f"| Tiros por partido | {sl['tiros']:.1f} | {sv['tiros']:.1f} |" if sl.get("tiros") and sv.get("tiros") else "| Tiros por partido | — | — |",
            f"| Ranking Elo | {ea:.0f} | {eb:.0f} |",
            "", "**Predicción del modelo**",
            f"- 1X2: {loc} {pct(pr['pl'])} · Empate {pct(pr['pe'])} · {vis} {pct(pr['pv'])}",
            f"- Doble oportunidad: {loc} o empate {pct(pr['1x'])} · {vis} o empate {pct(pr['x2'])}",
        ]
        if pr["tiros_l"] is not None and pr["tiros_v"] is not None:
            lineas.append(f"- Tiros proyectados: {loc} {pr['tiros_l']:.1f} · {vis} {pr['tiros_v']:.1f}"
                          + (f" · Más de 24,5 tiros en el partido: {pct(pr['tiros_t_o245'])}" if pr["tiros_t_o245"] is not None else ""))
        lineas += [f"- Para el video: el modelo ve como favorito a **{fav[1]}** ({pct(fav[0])}).", ""]
    lineas += ["---", f"_{AVISO}_"]
    texto = "\n".join(lineas) + "\n"
    texto = re.sub(r"(?<=\d)\.(?=\d)", ",", texto)   # decimales con coma
    with open(a.salida, "w", encoding="utf-8") as fh:
        fh.write(texto)
    if tmp:
        os.remove(tmp)
    print("listo:", a.salida, "-", min(a.n, len(candidatos)), "partidos")


if __name__ == "__main__":
    main()
