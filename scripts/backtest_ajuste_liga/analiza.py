"""Analisis pre-registrado del backtest del ajuste de liga. Uso: analiza.py SP [tabla]"""
import sys, glob, numpy as np, pandas as pd
from scipy.stats import poisson
SP = sys.argv[1]; TABLA = sys.argv[2] if len(sys.argv) > 2 else "2025"
VARS = ["prod", "55", "55A", "55B", "55AB"]
TOP5 = {"Premier League", "La Liga", "Bundesliga", "Serie A", "Ligue 1"}
B, SEMILLA = 2000, 20261016

def carga(conj, var, tabla):
    fs = glob.glob(f"{SP}/res/{conj}_{var}_{tabla}_*.csv")
    return pd.concat([pd.read_csv(f) for f in fs]).drop_duplicates("fid").set_index("fid") if fs else None

def metricas(d):
    g_l = d.g90l.fillna(d.gl).astype(float); g_v = d.g90v.fillna(d.gv).astype(float)
    res = np.select([g_l > g_v, g_l == g_v], [0, 1], 2)
    P = np.clip(d[["pl", "pe", "pv"]].to_numpy(float), 1e-6, 1)
    O = np.eye(3)[res]
    m = pd.DataFrame(index=d.index)
    m["logloss"] = -np.log((P * O).sum(1))
    m["brier"] = ((P - O) ** 2).sum(1)
    m["nll_goles"] = -(poisson.logpmf(g_l, d.xl) + poisson.logpmf(g_v, d.xv))
    okc = (d.cl.fillna(0) + d.cv.fillna(0) > 0) & d.xcl.notna()
    m["nll_corners"] = np.where(okc, -(poisson.logpmf(d.cl.fillna(0).round(), d.xcl.clip(lower=1e-6)) + poisson.logpmf(d.cv.fillna(0).round(), d.xcv.clip(lower=1e-6))), np.nan)
    m["dif_real"] = g_l - g_v; m["dif_esp"] = d.xl - d.xv
    m["mes"] = d.fecha.str[:7]
    return m

def boot(fn, meses_df, rng):
    meses = meses_df.mes.unique(); grupos = {k: v for k, v in meses_df.groupby("mes")}
    out = []
    for _ in range(B):
        s = rng.choice(meses, len(meses), replace=True)
        out.append(fn(pd.concat([grupos[k] for k in s])))
    return np.nanpercentile(out, [2.5, 97.5])

for conj in ("europa", "control"):
    D = {v: carga(conj, v, TABLA if v != "prod" and v != "55" else "2025") for v in VARS}
    if any(x is None for x in D.values()): print(conj, "faltan resultados"); continue
    comunes = sorted(set.intersection(*[set(x.index) for x in D.values()]))
    M = {v: metricas(D[v].loc[comunes]) for v in VARS}
    print(f"\n===== {conj} (tabla {TABLA}): {len(comunes)} partidos simulados en las 5 variantes " + str({v: len(D[v]) for v in VARS}))
    rng = np.random.default_rng(SEMILLA)
    print(f"{'variante':8s} " + " ".join(f"{k:>30s}" for k in ["logloss", "brier", "nll_goles", "nll_corners"]))
    for v in VARS:
        fila = []
        for k in ["logloss", "brier", "nll_goles", "nll_corners"]:
            if v == "prod": fila.append(f"{M[v][k].mean():30.4f}"); continue
            dd = (M[v][k] - M["prod"][k]).to_frame("d"); dd["mes"] = M[v].mes
            ci = boot(lambda x: x.d.mean(), dd, rng)
            fila.append(f"{dd.d.mean():+9.4f} [{ci[0]:+8.4f},{ci[1]:+8.4f}]")
        print(f"{v:8s} " + " ".join(fila))
    if conj == "europa":
        p = D["prod"].loc[comunes]
        top_l = p.ref_l.isin(TOP5) & p.ref_v.isna(); top_v = p.ref_v.isin(TOP5) & p.ref_l.isna()
        grupo = p.index[top_l | top_v]; signo = pd.Series(np.where(top_l, 1, -1), index=p.index)
        print(f"\nDesvio top-5 vs rival sin referencia (refs de produccion), n={len(grupo)}")
        gaps = {}
        for v in VARS:
            g = M[v].loc[grupo].copy(); s = signo.loc[grupo]
            g["gap"] = (g.dif_real - g.dif_esp) * s
            ci = boot(lambda x: x.gap.mean(), g, rng)
            gaps[v] = (g.gap.mean(), ci)
            print(f"  {v:6s} gap {g.gap.mean():+.3f} IC95 [{ci[0]:+.3f},{ci[1]:+.3f}]   dif esperada {(g.dif_esp*s).mean():+.3f} real {(g.dif_real*s).mean():+.3f}")
        dd = (M["55AB"].logloss - M["prod"].logloss).to_frame("d"); dd["mes"] = M["prod"].mes
        ci = boot(lambda x: x.d.mean(), dd, np.random.default_rng(SEMILLA))
        c1 = ci[0] <= 0
        c2 = gaps["55AB"][0] < gaps["prod"][0] and gaps["55AB"][1][1] < gaps["prod"][0]
        print(f"\nCRITERIO 1 (A+B no peor que prod en log-loss, IC no del lado malo): delta {dd.d.mean():+.4f} IC [{ci[0]:+.4f},{ci[1]:+.4f}] -> {'CUMPLE' if c1 else 'NO CUMPLE'}")
        print(f"CRITERIO 2 (desvio se achica, IC de A+B excluye el valor de prod {gaps['prod'][0]:+.3f}): A+B {gaps['55AB'][0]:+.3f} IC [{gaps['55AB'][1][0]:+.3f},{gaps['55AB'][1][1]:+.3f}] -> {'CUMPLE' if c2 else 'NO CUMPLE'}  (tambien vs +1.57: {'excluye' if gaps['55AB'][1][1] < 1.57 else 'no excluye'})")
    else:
        dd = (M["55AB"].logloss - M["prod"].logloss).to_frame("d"); dd["mes"] = M["prod"].mes
        ci = boot(lambda x: x.d.mean(), dd, np.random.default_rng(SEMILLA))
        print(f"\nNO-DANO control (A+B vs prod log-loss): {dd.d.mean():+.4f} IC [{ci[0]:+.4f},{ci[1]:+.4f}] -> {'OK' if ci[0] <= 0 else 'PEOR'}")
        cambian = (D["55AB"].loc[comunes].pl - D["prod"].loc[comunes].pl).abs() > 0.005
        print("partidos que cambian >0.5pt por liga:"); print(D["prod"].loc[comunes][cambian].liga.value_counts().head(15).to_string())
