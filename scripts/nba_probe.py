"""Fase 0 de NBA: prueba si stats.nba.com y cdn.nba.com responden desde
donde corre este script (PC o runner de GitHub Actions).

stats.nba.com no publica limites y hay reportes de que bloquea IPs de
nube colgando la conexion en vez de devolver error, por eso cada pedido
lleva timeout explicito y se mide el tiempo.

Uso: python scripts/nba_probe.py [--temporada 2026-27]
Sale con codigo 1 si falla algun pedido a stats.nba.com (el CDN es solo informativo).
"""
import argparse
import time

TIMEOUT = 30
PAUSA = 0.6  # entre pedidos a stats.nba.com


def _probar(nombre, fn):
    t0 = time.time()
    try:
        detalle = fn()
        ok = True
    except Exception as e:
        detalle = f"{type(e).__name__}: {e}"[:300]
        ok = False
    print(f"[{'OK' if ok else 'FALLA'}] {nombre} ({time.time() - t0:.1f}s) -> {detalle}")
    return ok


def cdn_scoreboard():
    # Cliente live de nba_api: manda los headers de navegador que el CDN
    # exige (un requests.get pelado recibe 403).
    from nba_api.live.nba.endpoints import scoreboard
    sb = scoreboard.ScoreBoard(timeout=TIMEOUT).get_dict()["scoreboard"]
    return f"fecha {sb['gameDate']}, {len(sb['games'])} partidos"


def stats_cartelera():
    # V3 y no V2: nba_api avisa que V2 trae mal los line scores 2025-26.
    from datetime import date
    from nba_api.stats.endpoints import scoreboardv3
    sb = scoreboardv3.ScoreboardV3(
        game_date=date.today().isoformat(), timeout=TIMEOUT,
    ).get_dict()["scoreboard"]
    return f"fecha {sb['gameDate']}, {len(sb['games'])} partidos"


def stats_partidos(temporada):
    from nba_api.stats.endpoints import leaguegamefinder
    df = leaguegamefinder.LeagueGameFinder(
        season_nullable=temporada, league_id_nullable="00", timeout=TIMEOUT,
    ).get_data_frames()[0]
    return f"{len(df)} filas equipo-partido, ultima fecha {df['GAME_DATE'].max()}"


def stats_jugadores(temporada):
    from nba_api.stats.endpoints import leaguegamelog
    df = leaguegamelog.LeagueGameLog(
        season=temporada, player_or_team_abbreviation="P", timeout=TIMEOUT,
    ).get_data_frames()[0]
    return f"{len(df)} filas jugador-partido, {df['PLAYER_ID'].nunique()} jugadores"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--temporada", default="2026-27")
    args = ap.parse_args()

    print(f"Temporada {args.temporada}, timeout {TIMEOUT}s por pedido")
    # Informativo: desde la PC tambien da 403 (Akamai), no decide nada.
    _probar("cdn.nba.com scoreboard", cdn_scoreboard)
    ok0 = _probar("stats.nba.com scoreboardv3 (cartelera)", stats_cartelera)
    time.sleep(PAUSA)
    ok1 = _probar("stats.nba.com leaguegamefinder", lambda: stats_partidos(args.temporada))
    time.sleep(PAUSA)
    ok2 = _probar("stats.nba.com leaguegamelog (jugadores)", lambda: stats_jugadores(args.temporada))
    raise SystemExit(0 if ok0 and ok1 and ok2 else 1)


if __name__ == "__main__":
    main()
