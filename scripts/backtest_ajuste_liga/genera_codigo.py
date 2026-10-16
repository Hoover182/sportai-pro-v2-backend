import sys, json, numpy as np
SP, Y = sys.argv[1], sys.argv[2]
ANCLA_LIGA = {"England":"Premier League","Spain":"La Liga","Germany":"Bundesliga","Italy":"Serie A","France":"Ligue 1","Portugal":"Primeira Liga","Netherlands":"Eredivisie","Türkiye":"Super Lig Turquia","Belgium":"Pro League Belgica"}
NIV = {"Premier League":100,"La Liga":95,"Bundesliga":90,"Serie A":88,"Ligue 1":82,"Primeira Liga":72,"Eredivisie":68,"Super Lig Turquia":65,"Pro League Belgica":62}
A_API = {"Czechia":"Czech-Republic","Bosnia-Herzegovina":"Bosnia","North Macedonia":"Macedonia","Türkiye":"Turkey"}
rows = [l.rstrip("\n").split("|") for l in open(f"{SP}/web/crank{Y}.csv", encoding="utf-8")]
c = {r[2]: float(r[-2]) for r in rows}
x = np.log([c[k] for k in ANCLA_LIGA]); yv = np.array([NIV[ANCLA_LIGA[k]] for k in ANCLA_LIGA], float)
b, a = np.polyfit(x, yv, 1)
curva = lambda co: int(round(min(100, max(0, a + b*np.log(co)))))
pais = {k: (NIV[ANCLA_LIGA[k]] if k in ANCLA_LIGA else curva(v)) for k, v in c.items()}
LIGA_PAIS = {"Super League 1 Greece":"Greece","Premiership Scotland":"Scotland","Erovnuli Liga Georgia":"Georgia","Ekstraklasa Poland":"Poland","Eliteserien Norway":"Norway","Czech Liga Czech-Republic":"Czechia","Bundesliga Austria":"Austria","First League Bulgaria":"Bulgaria","HNL Croatia":"Croatia","1. SNL Slovenia":"Slovenia","Super Liga Slovakia":"Slovakia","Veikkausliiga Finland":"Finland","Premier League Ukraine":"Ukraine","NB I Hungary":"Hungary","Premyer Liqa Azerbaijan":"Azerbaijan","Super League Switzerland":"Switzerland","Super Liga Serbia":"Serbia","Premijer Liga Bosnia":"Bosnia-Herzegovina","Superliga Denmark":"Denmark","Liga I Romania":"Romania","Allsvenskan Sweden":"Sweden","1a Divisió Andorra":"Andorra","Superliga Albania":"Albania","Virsliga Latvia":"Latvia","Premier League Kazakhstan":"Kazakhstan","Ligat Ha'al Israel":"Israel","1. Division Cyprus":"Cyprus","A Lyga Lithuania":"Lithuania","Premier Division Gibraltar":"Gibraltar","Premier League Armenia":"Armenia","Úrvalsdeild Iceland":"Iceland"}
api = lambda p: A_API.get(p, p.replace(" ", "-"))
o = []
o.append(f"# Curva ajustada sobre las 9 ligas UEFA de la tabla editorial (sus niveles\n# no se tocan): nivel = {a:.3f} + {b:.3f} * ln(coeficiente UEFA por pais,\n# 5 temporadas, ranking {Y}), acotado a 0-100 y redondeado.")
o.append("NIVEL_LIGA_UEFA = {")
for l, p in sorted(LIGA_PAIS.items(), key=lambda t: -c[t[1]]): o.append(f'    "{l}": {pais[p]},  # {p}, coef {c[p]:.3f}')
o.append("}\n")
o.append("# Nivel por pais (nombres de pais de api-football), para equipos sin liga\n# domestica cargada en copas UEFA. Las 9 asociaciones ancla usan el nivel\n# de su liga en la tabla editorial; el resto, la misma curva.")
o.append("NIVEL_PAIS_UEFA = {")
for p in sorted(c, key=lambda k: -c[k]): o.append(f'    "{api(p)}": {pais[p]},  # coef {c[p]:.3f}')
o.append("}")
o.append(f"# P25 de NIVEL_PAIS_UEFA = {np.percentile(list(pais.values()), 25)}")
open(f"{SP}/codigo{Y}.py", "w", encoding="utf-8").write("\n".join(o) + "\n")
