"""Backtest point-in-time del ajuste de liga. Uso: bt.py SP variante parte n_partes conjunto [tabla]"""
import sys, os, io, json, contextlib, time, pandas as pd
SP, VAR, PARTE, NP, CONJ = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
TABLA = sys.argv[6] if len(sys.argv) > 6 else "2025"
D = r"C:\Users\hoove\sportai-pro-v2\backend\app\services"; sys.path.insert(0, D); os.chdir(D)
import data_loader as dl, futbol_service as fs, football_model as fm, liga_ranking as lr
if TABLA == "2026":
    ns = {}; exec(open(f"{SP}/codigo2026.py", encoding="utf-8").read(), ns)
    lr.NIVEL_LIGA_UEFA = ns["NIVEL_LIGA_UEFA"]; lr.NIVEL_PAIS_UEFA = ns["NIVEL_PAIS_UEFA"]
TODAS_VIEJA = fm.LIGAS_DOMESTICAS_NIVEL1 + fm.LIGAS_SEGUNDA_DIVISION
cfg = {"prod": ("19", False, False), "55": ("55", False, False), "55A": ("55", True, False), "55B": ("55", False, True), "55AB": ("55", True, True)}[VAR]
auto = json.load(open(f"{SP}/auto_backend19.json" if cfg[0] == "19" else f"{SP}/auto_an.json", encoding="utf-8"))
lr.USAR_NIVELES_A, lr.USAR_RED_B = cfg[1], cfg[2]
fm.LIGAS_DOMESTICAS_TODAS = TODAS_VIEJA + lr.ligas_con_nivel_extra()
dl._cache_ligas_auto_detectadas = dict(auto); dl.CSV_FUTBOL = f"{SP}/an16.csv"
df = dl.filtrar_ligas_validas(dl.cargar_partidos_csv())
lista = pd.read_csv(f"{SP}/partidos_{CONJ}.csv")
lista = lista.iloc[PARTE::NP]
df_by_fid = df.set_index("fixture_id", drop=False)
out = []; t = time.time()
for fid in lista.fid:
    if fid not in df_by_fid.index: continue
    p = df_by_fid.loc[fid]
    if isinstance(p, pd.DataFrame): p = p.iloc[0]
    prev = df[df.fecha < p.fecha]; fila = p.to_frame().T.copy(); fila["estado"] = "NS"
    pit = pd.concat([fila, prev], ignore_index=True); pit["fecha"] = pd.to_datetime(pit["fecha"], utc=True).dt.tz_convert("America/Bogota")
    for n in ("_cache_equipos_nivel1", "_cache_equipos_todos", "_cache_equipos_exactos"): setattr(fs, n, None)
    try:
        with contextlib.redirect_stdout(io.StringIO()): sim, a, b = fs.simular(pit, p.equipo_local, p.equipo_visitante)
    except Exception as e:
        sim = None
    if sim is None: continue
    out.append(dict(fid=int(fid), fecha=str(p.fecha)[:10], liga=p.liga, local=p.equipo_local, visit=p.equipo_visitante,
        gl=p.goles_local, gv=p.goles_visitante, g90l=p.get("goles_90_local"), g90v=p.get("goles_90_visitante"), estado=p.estado,
        cl=p.corners_local, cv=p.corners_visitante,
        pl=sim["prob_local"], pe=sim["prob_empate"], pv=sim["prob_visitante"], xl=sim["goles_local_proj"], xv=sim["goles_visitante_proj"],
        xcl=sim.get("corners_local_proj"), xcv=sim.get("corners_visitante_proj"),
        ref_l=a.get("liga_referencia"), ref_v=b.get("liga_referencia"), niv_l=a.get("nivel_referencia"), niv_v=b.get("nivel_referencia")))
pd.DataFrame(out).to_csv(f"{SP}/res/{CONJ}_{VAR}_{TABLA}_{PARTE}.csv", index=False)
print(VAR, CONJ, PARTE, "pedidos", len(lista), "simulados", len(out), f"{time.time()-t:.0f}s")
