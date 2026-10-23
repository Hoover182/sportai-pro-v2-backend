"""Fase 0 de NBA, segunda prueba: ¿alcanza cdn.nba.com para el historial?

Desde Actions stats.nba.com no responde pero el CDN si. Esto pide al CDN
el calendario de la temporada y boxscores de partidos ya jugados de varias
temporadas, y revisa que traigan puntos por cuarto y PTS/REB/AST/MIN por
jugador. Los GAME_ID salen de leaguegamefinder corrido desde la PC.

Uso: python scripts/nba_probe_cdn.py
Sale con codigo 1 si algun boxscore de la temporada actual no sirve.
"""
import time

import requests
from nba_api.live.nba.library.http import STATS_HEADERS

TIMEOUT = 30
PAUSA = 0.6
CDN = "https://cdn.nba.com/static/json"

# (game_id, descripcion, marcador segun stats.nba.com desde la PC)
PARTIDOS = [
    ("0022600001", "2026-27 RS, 20/10 DET vs BOS", "DET 121"),
    ("0022600007", "2026-27 RS, 22/10 DEN @ OKC", None),
    ("0022500001", "2025-26 RS, 21/10/25 OKC vs HOU", "OKC 125"),
    ("0022501189", "2025-26 RS, ultimo partido 12/04/26", None),
    ("0042500405", "2025-26 Finales, juego 5", None),
    ("0022300061", "2023-24 RS, DEN vs LAL", "DEN 119 / LAL 107"),
    ("0021900001", "2019-20 RS, NOP @ TOR", "TOR 122?"),
]
ACTUAL = "00226"


def _get(path):
    r = requests.get(f"{CDN}/{path}", headers=STATS_HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def calendario():
    t0 = time.time()
    try:
        data = _get("staticData/scheduleLeagueV2.json")["leagueSchedule"]
    except Exception as e:
        print(f"[FALLA] calendario ({time.time() - t0:.1f}s) -> {type(e).__name__}: {e}"[:300])
        return
    juegos = [g for d in data["gameDates"] for g in d["games"]]
    jugados = [g for g in juegos if g.get("gameStatus") == 3]
    print(f"[OK] calendario {data['seasonYear']} ({time.time() - t0:.1f}s) -> "
          f"{len(juegos)} partidos, {len(jugados)} terminados")


def _equipo(t):
    jug = [p for p in t["players"] if p.get("played") == "1"]
    s0 = jug[0]["statistics"] if jug else {}
    campos = [c for c in ("points", "reboundsTotal", "assists", "minutes") if c in s0]
    suma = sum(p["statistics"]["points"] for p in jug)
    cuartos = [p["score"] for p in t["periods"]]
    return (f"{t['teamTricode']} {t['score']} cuartos={cuartos} "
            f"jugadores={len(jug)} campos={campos} suma_pts={suma}"), (
        len(cuartos) >= 4 and len(campos) == 4 and suma == t["score"])


def boxscore(game_id, desc, ref):
    t0 = time.time()
    try:
        g = _get(f"liveData/boxscore/boxscore_{game_id}.json")["game"]
    except Exception as e:
        print(f"[FALLA] {game_id} {desc} ({time.time() - t0:.1f}s) -> "
              f"{type(e).__name__}: {e}"[:300])
        return False
    loc, ok_l = _equipo(g["homeTeam"])
    vis, ok_v = _equipo(g["awayTeam"])
    ok = ok_l and ok_v
    print(f"[{'OK' if ok else 'INCOMPLETO'}] {game_id} {desc} ({time.time() - t0:.1f}s)"
          f"\n    local: {loc}\n    visita: {vis}\n    referencia PC: {ref}")
    if game_id == PARTIDOS[0][0]:
        print(f"    stats de equipo disponibles: {sorted(g['homeTeam']['statistics'])}")
    return ok


def main():
    calendario()
    actuales_ok = True
    for game_id, desc, ref in PARTIDOS:
        time.sleep(PAUSA)
        ok = boxscore(game_id, desc, ref)
        if game_id.startswith(ACTUAL):
            actuales_ok &= ok
    raise SystemExit(0 if actuales_ok else 1)


if __name__ == "__main__":
    main()
