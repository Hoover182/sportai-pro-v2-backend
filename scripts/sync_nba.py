#!/usr/bin/env python3
"""
Sync de NBA: baja boxscores de cdn.nba.com y actualiza el historial en
este mismo repo (sin repo intermedio, a diferencia de futbol).

  app/services/nba_partidos.csv            una fila por partido (local/visitante)
  app/services/nba_jugadores/<temporada>.csv  una fila por jugador que jugo
  app/services/nba_cartelera.json          partidos de hoy y los 2 dias siguientes (ET)
  app/services/nba_datos_meta.json         hora real del ultimo sync con cambios

La cartelera tambien sale de aca y no de una llamada en vivo desde Render:
Render esta en la nube como Actions, y no sabemos si el CDN le responde.

Por que el CDN y no stats.nba.com: desde Actions stats.nba.com cuelga la
conexion (bloqueo de IPs de nube, prueba del 23/10/2026, run 39988119348).
El CDN responde desde Actions pero NO desde la PC, y solo a requests con
headers de navegador (curl recibe 403 por la huella TLS de Akamai).

Ojo: un partido que no existe devuelve 403, igual que un bloqueo. Por eso
antes de dar por terminada una temporada se pide un partido testigo que
seguro existe; si el testigo tambien falla, es bloqueo y se aborta.

Modos:
  python scripts/sync_nba.py diario
      calendario de la temporada en curso -> partidos terminados que falten
  python scripts/sync_nba.py backfill --temporada 2025-26
      recorre los ids de una temporada pasada (el calendario solo trae la actual)

Codigos de salida (como check_sync.py): 0 sin cambios, 2 hubo cambios,
cualquier otro = error (el workflow tiene que quedar en rojo).
"""
import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests

BASE = os.path.join(os.path.dirname(__file__), "..", "app", "services")
CSV_PARTIDOS = os.path.join(BASE, "nba_partidos.csv")
DIR_JUGADORES = os.path.join(BASE, "nba_jugadores")
META = os.path.join(BASE, "nba_datos_meta.json")
CARTELERA = os.path.join(BASE, "nba_cartelera.json")
DIAS_CARTELERA = 3
ET = ZoneInfo("America/New_York")

CDN = "https://cdn.nba.com/static/json"
# Headers de nba_api.live, importados y NO copiados: el CDN bloquea
# User-Agents viejos (23/10/2026: el Chrome 87 de nba_api 1.11.4 ya da 403,
# el Firefox 158 de 1.11.6 pasa). El workflow instala nba_api sin fijar
# version, asi que cuando los mantenedores actualicen los headers el sync
# los toma solo. Si el CDN vuelve a bloquear, el testigo da 403 y la
# corrida queda en rojo.
from nba_api.live.nba.library.http import STATS_HEADERS as HEADERS
TIMEOUT = 30
PAUSA = 0.6

# Prefijo del game_id -> tipo. 001 pretemporada y 003 All-Star quedan afuera.
TIPOS = {"002": "regular", "004": "playoffs", "005": "play_in", "006": "copa_final"}

STATS_EQUIPO = [
    ("fgm", "fieldGoalsMade"), ("fga", "fieldGoalsAttempted"),
    ("tres_m", "threePointersMade"), ("tres_a", "threePointersAttempted"),
    ("tl_m", "freeThrowsMade"), ("tl_a", "freeThrowsAttempted"),
    ("reb_of", "reboundsOffensive"), ("reb_def", "reboundsDefensive"),
    ("reb", "reboundsTotal"), ("ast", "assists"), ("robos", "steals"),
    ("tapas", "blocks"), ("perdidas", "turnovers"), ("faltas", "foulsPersonal"),
]
COLS_PARTIDOS = (
    ["game_id", "fecha", "temporada", "tipo",
     "equipo_local", "equipo_visitante", "id_local", "id_visitante",
     "sigla_local", "sigla_visitante", "puntos_local", "puntos_visitante"]
    + [f"q{i}_{lado}" for lado in ("local", "visitante") for i in range(1, 5)]
    + ["prorroga_local", "prorroga_visitante", "n_prorrogas"]
    + [f"{c}_{lado}" for c, _ in STATS_EQUIPO for lado in ("local", "visitante")]
)
STATS_JUGADOR = [
    ("pts", "points"), ("reb", "reboundsTotal"), ("ast", "assists"),
    ("tres_m", "threePointersMade"), ("robos", "steals"), ("tapas", "blocks"),
    ("perdidas", "turnovers"),
]
COLS_JUGADORES = (
    ["game_id", "fecha", "id_equipo", "sigla_equipo", "rival", "local",
     "id_jugador", "jugador", "titular", "minutos"]
    + [c for c, _ in STATS_JUGADOR]
)


class Bloqueado(Exception):
    """El CDN rechaza tambien al partido testigo: no es 'no existe'."""


# -----------------------------
# CDN
# -----------------------------

def pedir(ruta):
    """JSON de una ruta del CDN, o None si da 403/404 (no existe o bloqueo:
    quien llama decide con el testigo)."""
    r = requests.get(f"{CDN}/{ruta}", headers=HEADERS, timeout=TIMEOUT)
    time.sleep(PAUSA)
    if r.status_code in (403, 404):
        return None
    r.raise_for_status()
    return r.json()


def pedir_boxscore(game_id, pedir=pedir):
    data = pedir(f"liveData/boxscore/boxscore_{game_id}.json")
    return data["game"] if data else None


def verificar_testigo(testigo, pedir=pedir):
    if pedir_boxscore(testigo, pedir) is None:
        raise Bloqueado(f"el partido testigo {testigo} tambien da 403: el CDN "
                        "nos esta bloqueando, no es que el partido no exista")


# -----------------------------
# PARSEO
# -----------------------------

def temporada_de(game_id):
    yy = int(game_id[3:5])
    return f"20{yy:02d}-{yy + 1:02d}"


def minutos(iso):
    """'PT45M15.10S' -> 45.25"""
    if not iso or not iso.startswith("PT"):
        return 0.0
    m, _, s = iso[2:].rstrip("S").partition("M")
    return round(float(m or 0) + float(s or 0) / 60, 2)


def _periodos(equipo):
    # El CDN a veces agrega un "quinto cuarto" REGULAR fantasma con 0 puntos
    # (0022200429 SAC-DET 16/12/2022, sin prorroga). Se descarta; si tuviera
    # puntos no se toca y el chequeo de 4 cuartos frena el sync.
    reg = [p["score"] for p in equipo["periods"] if p["periodType"] == "REGULAR"
           and not (p["period"] > 4 and p["score"] == 0)]
    ot = [p["score"] for p in equipo["periods"] if p["periodType"] == "OVERTIME"]
    return reg, ot


def parsear_boxscore(g):
    """(fila de partido, filas de jugadores). Levanta ValueError si el
    boxscore no cierra (cuartos que no suman el marcador, etc.): mejor
    frenar el sync que guardar un dato roto."""
    gid = g["gameId"]
    if g.get("gameStatus") != 3:
        raise ValueError(f"{gid}: no esta terminado (gameStatus={g.get('gameStatus')})")
    loc, vis = g["homeTeam"], g["awayTeam"]
    fila = {
        "game_id": gid, "fecha": g["gameEt"][:10], "temporada": temporada_de(gid),
        "tipo": TIPOS[gid[:3]],
        "equipo_local": f"{loc['teamCity']} {loc['teamName']}",
        "equipo_visitante": f"{vis['teamCity']} {vis['teamName']}",
        "id_local": loc["teamId"], "id_visitante": vis["teamId"],
        "sigla_local": loc["teamTricode"], "sigla_visitante": vis["teamTricode"],
        "puntos_local": loc["score"], "puntos_visitante": vis["score"],
    }
    n_ot = None
    for lado, eq in (("local", loc), ("visitante", vis)):
        reg, ot = _periodos(eq)
        if len(reg) != 4:
            crudo = [(p["period"], p["periodType"], p["score"]) for p in eq["periods"]]
            raise ValueError(f"{gid}: {lado} tiene {len(reg)} cuartos regulares; periodos del CDN: {crudo}")
        if sum(reg) + sum(ot) != eq["score"]:
            raise ValueError(f"{gid}: cuartos de {lado} suman {sum(reg) + sum(ot)}, marcador {eq['score']}")
        for i, pts in enumerate(reg, start=1):
            fila[f"q{i}_{lado}"] = pts
        fila[f"prorroga_{lado}"] = sum(ot)
        n_ot = len(ot)
        for col, clave in STATS_EQUIPO:
            fila[f"{col}_{lado}"] = eq["statistics"][clave]
    fila["n_prorrogas"] = n_ot

    jugadores = []
    for es_local, eq, rival in ((1, loc, vis), (0, vis, loc)):
        for p in eq["players"]:
            if p.get("played") != "1":
                continue
            s = p["statistics"]
            j = {
                "game_id": gid, "fecha": fila["fecha"], "id_equipo": eq["teamId"],
                "sigla_equipo": eq["teamTricode"], "rival": rival["teamTricode"],
                "local": es_local, "id_jugador": p["personId"], "jugador": p["name"],
                "titular": int(p.get("starter") == "1"), "minutos": minutos(s["minutes"]),
            }
            for col, clave in STATS_JUGADOR:
                j[col] = s[clave]
            jugadores.append(j)
    return fila, jugadores


# -----------------------------
# QUE PARTIDOS BAJAR
# -----------------------------

def ids_terminados_calendario(calendario):
    """game_ids terminados (gameStatus 3) de los tipos que guardamos."""
    juegos = (g for d in calendario["leagueSchedule"]["gameDates"] for g in d["games"])
    return sorted(g["gameId"] for g in juegos
                  if g["gameStatus"] == 3 and g["gameId"][:3] in TIPOS)


def recorrer_temporada(yy, ya_tengo, pedir=pedir, log=print):
    """Boxscores de una temporada pasada recorriendo ids (el calendario del
    CDN solo trae la temporada actual). Devuelve la lista de boxscores
    nuevos. Los ids que ya estan en el CSV no se piden."""
    testigo = f"002{yy:02d}00001"
    verificar_testigo(testigo, pedir)
    nuevos = []

    def bajar(gid):
        if gid in ya_tengo:
            return True
        g = pedir_boxscore(gid, pedir)
        if g is None:
            return False
        if g.get("gameStatus") == 3:
            nuevos.append(g)
        else:
            # Existe pero el CDN lo tiene "sin terminar" en una temporada
            # pasada: boxscore roto del CDN (0022301104 ATL-DET 03/04/2024 se
            # jugo segun stats.nba.com). Se saltea con aviso, no frena todo.
            log(f"  AVISO {gid}: boxscore del CDN sin terminar "
                f"(gameStatus={g.get('gameStatus')}), queda afuera")
        return True

    # Fase regular: 1230 partidos; despues del 1230 se sigue hasta 20
    # ausencias seguidas (2019-20 tuvo ids hasta 1316 por la burbuja, con
    # los partidos cancelados como huecos antes del 1230).
    seguidos, n = 0, 0
    while seguidos < 20:
        n += 1
        if bajar(f"002{yy:02d}{n:05d}"):
            seguidos = 0
        elif n > 1230:
            seguidos += 1
        if n % 100 == 0:
            log(f"  regular {n}: {len(nuevos)} nuevos")
    verificar_testigo(testigo, pedir)   # las ausencias son reales, no un bloqueo

    # Play-in (desde 2019-20): 005YY00 + ronda (1-2) + serie + juego, como
    # playoffs (2025-26: 101 111 121 131 / 201 211). Un solo juego por
    # serie, pero se prueban hasta 3 por las dudas (~48 pedidos).
    for ronda in (1, 2):
        for serie in range(8):
            for juego in range(1, 4):
                bajar(f"005{yy:02d}00{ronda}{serie}{juego}")

    # Playoffs: 004YY00 + ronda (1-4) + serie (0-7) + juego (1-7)
    for ronda, series in ((1, 8), (2, 4), (3, 2), (4, 1)):
        for serie in range(series):
            for juego in range(1, 8):
                if not bajar(f"004{yy:02d}00{ronda}{serie}{juego}"):
                    break

    # Final de la Copa NBA (desde 2023-24)
    bajar(f"006{yy:02d}00001")
    verificar_testigo(testigo, pedir)
    return nuevos


def armar_cartelera(calendario, hoy_et, dias=DIAS_CARTELERA):
    """Partidos de hoy_et y los dias siguientes (fecha ET, la que usa la
    NBA), de los tipos que guardamos, ordenados por hora."""
    hasta = (hoy_et + timedelta(days=dias - 1)).isoformat()
    desde = hoy_et.isoformat()
    partidos = []
    for d in calendario["leagueSchedule"]["gameDates"]:
        for g in d["games"]:
            fecha = g["gameDateEst"][:10]
            if not (desde <= fecha <= hasta) or g["gameId"][:3] not in TIPOS:
                continue
            equipo = lambda t: {"id": t["teamId"], "nombre": f"{t['teamCity']} {t['teamName']}",
                                "sigla": t["teamTricode"]}
            partidos.append({
                "game_id": g["gameId"], "fecha": fecha, "hora_utc": g["gameDateTimeUTC"],
                "tipo": TIPOS[g["gameId"][:3]], "estado": g["gameStatus"],
                "neutral": bool(g.get("isNeutral")), "postergado": g.get("postponedStatus") == "Y",
                "local": equipo(g["homeTeam"]), "visitante": equipo(g["awayTeam"]),
            })
    partidos.sort(key=lambda p: (p["hora_utc"], p["game_id"]))
    return {"temporada": calendario["leagueSchedule"]["seasonYear"], "desde": desde,
            "hasta": hasta, "partidos": partidos}


def escribir_cartelera(cartelera):
    """Escribe la cartelera si cambio. Devuelve True si cambio."""
    nuevo = json.dumps(cartelera, indent=2, ensure_ascii=False) + "\n"
    if os.path.exists(CARTELERA):
        with open(CARTELERA, encoding="utf-8") as f:
            if f.read() == nuevo:
                return False
    with open(CARTELERA, "w", encoding="utf-8") as f:
        f.write(nuevo)
    return True


# -----------------------------
# ARCHIVOS
# -----------------------------

def leer_csv(ruta):
    if not os.path.exists(ruta):
        return []
    with open(ruta, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def escribir_csv(ruta, filas, columnas, orden):
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    filas = sorted(filas, key=orden)
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columnas)
        w.writeheader()
        w.writerows(filas)


def ruta_jugadores(temporada):
    return os.path.join(DIR_JUGADORES, f"{temporada}.csv")


def guardar(boxscores, ahora=None, log=print):
    """Agrega los boxscores nuevos a los CSV. Devuelve cuantos partidos
    nuevos entraron. Nunca borra filas: un partido ya guardado no se pisa."""
    partidos = leer_csv(CSV_PARTIDOS)
    antes = len(partidos)
    ya = {p["game_id"] for p in partidos}
    jug_por_temp = {}
    for g in boxscores:
        if g["gameId"] in ya:
            continue
        fila, jugadores = parsear_boxscore(g)
        partidos.append(fila)
        ya.add(fila["game_id"])
        jug_por_temp.setdefault(fila["temporada"], []).extend(jugadores)
    nuevos = len(partidos) - antes
    if not nuevos:
        return 0

    escribir_csv(CSV_PARTIDOS, partidos, COLS_PARTIDOS,
                 lambda p: (p["fecha"], p["game_id"]))
    for temp, nuevos_jug in jug_por_temp.items():
        ruta = ruta_jugadores(temp)
        escribir_csv(ruta, leer_csv(ruta) + nuevos_jug, COLS_JUGADORES,
                     lambda j: (j["fecha"], j["game_id"], -int(j["local"]), str(j["id_jugador"])))
    ahora = ahora or datetime.now(timezone.utc)
    with open(META, "w", encoding="utf-8") as f:
        json.dump({"datos_actualizados_en": ahora.strftime("%Y-%m-%dT%H:%M:%SZ")}, f, indent=2)
        f.write("\n")
    log(f"{nuevos} partidos nuevos (total {len(partidos)})")
    return nuevos


# -----------------------------
# MAIN
# -----------------------------

def diario(pedir=pedir, log=print, ahora=None):
    """Devuelve cuantos cambios hubo (partidos nuevos + 1 si cambio la cartelera)."""
    cal = pedir("staticData/scheduleLeagueV2.json")
    if cal is None:
        raise Bloqueado("el calendario del CDN da 403")
    ahora = ahora or datetime.now(timezone.utc)
    cambio_cartelera = escribir_cartelera(armar_cartelera(cal, ahora.astimezone(ET).date()))
    ya = {p["game_id"] for p in leer_csv(CSV_PARTIDOS)}
    faltan = [gid for gid in ids_terminados_calendario(cal) if gid not in ya]
    log(f"Temporada {cal['leagueSchedule']['seasonYear']}: {len(faltan)} partidos terminados sin bajar")
    boxscores, testigo_ok = [], False
    for gid in faltan:
        g = pedir_boxscore(gid, pedir)
        if g is None:
            # Esta en el calendario como terminado: un 403 aca es bloqueo
            # o un boxscore que todavia no se publico. El testigo los separa;
            # si no es bloqueo, se reintenta en la proxima corrida.
            if not testigo_ok:
                # Testigo = un partido que ya tenemos (seguro existe).
                verificar_testigo(max(ya) if ya else ids_terminados_calendario(cal)[0], pedir)
                testigo_ok = True
            log(f"  {gid}: sin boxscore todavia")
            continue
        boxscores.append(g)
    return guardar(boxscores, ahora=ahora, log=log) + int(cambio_cartelera)


def backfill(temporada, log=print):
    yy = int(temporada[2:4])
    ya = {p["game_id"] for p in leer_csv(CSV_PARTIDOS)}
    log(f"Backfill {temporada}: recorriendo ids")
    return guardar(recorrer_temporada(yy, ya, log=log), log=log)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="modo", required=True)
    sub.add_parser("diario")
    b = sub.add_parser("backfill")
    b.add_argument("--temporada", required=True, help="ej. 2025-26")
    args = ap.parse_args()
    try:
        nuevos = diario() if args.modo == "diario" else backfill(args.temporada)
    except Bloqueado as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    return 2 if nuevos else 0


if __name__ == "__main__":
    sys.exit(main())
