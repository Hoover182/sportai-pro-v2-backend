import sys, os, json, pandas as pd
SP = sys.argv[1]
D = r"C:\Users\hoove\sportai-pro-v2\backend\app\services"; sys.path.insert(0, D); os.chdir(D)
import data_loader as dl
dl._cache_ligas_auto_detectadas = json.load(open(f"{SP}/auto_an.json", encoding="utf-8")); dl.CSV_FUTBOL = f"{SP}/an16.csv"
df = dl.filtrar_ligas_validas(dl.cargar_partidos_csv())
ft = df[df.estado.isin(["FT","AET","PEN"]) & (df.fecha >= pd.Timestamp("2025-07-01", tz="America/Bogota"))]
EUR = ["Champions League","Europa League","Conference League"]
CONMEBOL = ["Copa Libertadores","Copa Sudamericana"]
COPAS_DOM = ["FA Cup","Turkiye Kupasi","Copa Chile","Taça de Portugal","Copa Colombia","EFL Cup Inglaterra","Copa do Brasil",
 "Copa de la Division Profesional Bolivia","KNVB Beker","Coppa Italia","Copa Belgica","DFB Pokal","Copa Argentina","Copa Uruguay",
 "Copa del Rey","King Cup Arabia Saudita","Coupe de France","Taça da Liga Portugal","Copa Egipto",
 "Cup Greece","NM Cupen Norway","Cup Austria","League Cup Scotland","DBU Pokalen Denmark","Cup Croatia","Cup Czech-Republic",
 "Cup Lithuania","David Kipiani Cup Georgia","Cup Slovakia","Schweizer Cup Switzerland","Svenska Cupen Sweden","Magyar Kupa Hungary",
 "Cup Latvia","Cup Ukraine","Cupa României Romania","FA Cup Scotland"]
for nom, ligas in (("europa", EUR), ("control", CONMEBOL + COPAS_DOM)):
    s = ft[ft.liga.isin(ligas)].sort_values("fecha")
    s[["fixture_id","fecha","liga"]].rename(columns={"fixture_id":"fid"}).drop_duplicates("fid").to_csv(f"{SP}/partidos_{nom}.csv", index=False)
    print(nom, len(s)); print(s.liga.value_counts().to_string())
