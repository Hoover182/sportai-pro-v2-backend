"""Backtest de la ventana de promedios (temporada completa / decaimiento).
Criterios en PREREGISTRO_ventana.md, congelados antes de correrlo.

Uso desde backend/: python scripts/backtest_nba/bt_ventana.py
Escribe scripts/backtest_nba/resultados_ventana.json y muestra el resumen.
Reusa las funciones de bt.py sin cambiarlas.
"""
import json
import os
import sys

import pandas as pd

AQUI = os.path.dirname(__file__)
sys.path.insert(0, AQUI)
sys.path.insert(0, os.path.join(AQUI, "..", ".."))
import bt  # noqa: E402
from app.services import nba_model as M  # noqa: E402

AJUSTE = ["2023-24", "2024-25"]
EVALUACION = {"2025-26": ["2023-24", "2024-25"],   # temporada -> previas para la prob. fija
              "2022-23": ["2021-22"]}
H_LOCAL = 1.5   # aprobado en resultados.json; fatiga queda en 1.0 (no entro)
REFERENCIA = M.Params(ventaja_local=H_LOCAL)
# Orden = desempate: V1 con m chico primero, despues V2 con H grande primero.
CANDIDATOS = ([("V1", m, M.Params(ventaja_local=H_LOCAL, ventana="temporada", ventana_m=m))
               for m in (5, 10, 15, 20)]
              + [("V2", h, M.Params(ventaja_local=H_LOCAL, ventana="decaimiento", ventana_h=h))
                 for h in (80, 40, 20, 10)])


def correr_varias(partidos, largo, temporadas, params):
    return pd.concat([bt.correr(partidos, largo, t, params) for t in temporadas], ignore_index=True)


def criterio_1(partidos, metr, temporada, previas):
    sub = partidos[partidos["temporada"].isin(previas + [temporada])]
    b = bt.bases(sub, temporada)
    ok = metr["brier"] < b["brier_prob_fija"] and metr["acierto"] >= b["acierto_mejor_record"]
    return b, ok


def main():
    partidos = pd.read_csv(bt.CSV, dtype={"game_id": str})
    temporadas = sorted(partidos["temporada"].unique())
    print("Temporadas en el CSV:", partidos.groupby("temporada").size().to_dict())
    for t in ["2021-22", "2022-23"] + AJUSTE + list(EVALUACION):
        assert t in temporadas, f"falta {t} en el CSV"
    largo = M.partidos_por_equipo(partidos)
    res = {"referencia": {"ventaja_local": H_LOCAL, "ventana": "ultimos10"}}

    # ---- Eleccion: menor Brier en 2023-24 + 2024-25 juntas
    ajuste = {}
    ajuste["referencia"] = bt.metricas(correr_varias(partidos, largo, AJUSTE, REFERENCIA))
    for nombre, valor, p in CANDIDATOS:
        ajuste[f"{nombre}_{valor}"] = bt.metricas(correr_varias(partidos, largo, AJUSTE, p))
        print(f"  ajuste {nombre} {valor}: {ajuste[f'{nombre}_{valor}']}", flush=True)
    i_elegido = min(range(len(CANDIDATOS)),
                    key=lambda i: (ajuste[f"{CANDIDATOS[i][0]}_{CANDIDATOS[i][1]}"]["brier"], i))
    nombre, valor, p_elegido = CANDIDATOS[i_elegido]
    res["ajuste_2023_25"] = ajuste
    res["elegido"] = f"{nombre}_{valor}"
    print(f"\nElegido en 2023-24 + 2024-25: {nombre} {valor}  (referencia: {ajuste['referencia']})")

    # ---- Evaluacion en las dos temporadas
    entra = True
    ev_res, dfs = {}, {}
    for t in EVALUACION:
        ref = bt.correr(partidos, largo, t, REFERENCIA)
        var = bt.correr(partidos, largo, t, p_elegido)
        er, evr = bt.errores(ref), bt.errores(var)
        ic = bt.ic_mejora(er["brier"], evr["brier"])
        ok = ic[1] > 0 and evr["acierto"].mean() >= er["acierto"].mean()
        entra = entra and ok
        ev_res[t] = {"referencia": bt.metricas(ref), "variante": bt.metricas(var),
                     "mejora_brier_ic90": ic, "cumple": ok,
                     "salteados": int((partidos["temporada"] == t).sum()) - len(var)}
        dfs[t] = (ref, var)
        print(f"\n[{t}] referencia: {ev_res[t]['referencia']}")
        print(f"[{t}] variante:   {ev_res[t]['variante']}  mejora Brier IC90 {ic} ->",
              "CUMPLE" if ok else "NO CUMPLE")
    res["evaluacion"] = ev_res
    res["entra"] = entra
    print("\nVentana:", "ENTRA" if entra else "NO ENTRA")

    # ---- Criterio 1 del modelo resultante
    c1 = {}
    for t, previas in EVALUACION.items():
        final = dfs[t][1] if entra else dfs[t][0]
        m = bt.metricas(final)
        b, ok = criterio_1(partidos, m, t, previas)
        c1[t] = {"modelo": "variante" if entra else "referencia", "metricas": m, "bases": b, "pasa": ok}
        print(f"[criterio 1 {t}] {m['brier']} vs {b['brier_prob_fija']} | {m['acierto']} vs "
              f"{b['acierto_mejor_record']} ->", "PASA" if ok else "NO PASA")
    res["criterio_1"] = c1

    # ---- Informativo (no decide nada): todos los candidatos en evaluacion
    info = {}
    for nombre_c, valor_c, p in CANDIDATOS:
        info[f"{nombre_c}_{valor_c}"] = {t: bt.metricas(bt.correr(partidos, largo, t, p)) for t in EVALUACION}
    res["informativo_todos_en_evaluacion"] = info

    with open(os.path.join(AQUI, "resultados_ventana.json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2, ensure_ascii=False, default=str)


if __name__ == "__main__":
    main()
