# Validación limpia (tramo 2 de PREREGISTRO.md)

Partidos con inicio entre el **30/10/2026 y el 26/11/2026** (UTC). Se corre
**después del 28/11/2026**, cuando estén los resultados en el CSV.

## Código congelado

El modelo es el de `main` en a821c8f (con el arreglo del Elo y las ligas,
PR #98; ver la enmienda 1 de PREREGISTRO.md) y el harness/análisis del commit
que agrega este archivo a la rama `feat/backtest-futbol`. Aunque `main` cambie, la validación se
corre con ESE código, cambiando solo los datos:

```bash
git fetch origin
git worktree add ../bt-limpia 824dfff   # codigo congelado (enmienda 1)
cd ../bt-limpia
# datos frescos: solo el CSV del backend en main (el Elo sale de ese CSV)
git show origin/main:app/services/futbol_partidos.csv > app/services/futbol_partidos.csv
python scripts/backtest_futbol/harness.py --desde 2026-10-30 --hasta 2026-11-26 \
   --salida /ruta/scratch/pred_limpia.csv
python scripts/backtest_futbol/analizar.py --pred /ruta/scratch/pred_limpia.csv \
   --salida scripts/backtest_futbol/resultados_limpia.json
```

## Antes de correr, chequear

- Que el CSV tenga resultados hasta el 26/11 (último sync mergeado).
- Que `ligas_auto_detectadas.json` sea el del commit congelado (no se toca),
  y anotar si la de `main` cambió desde entonces.

Mismos criterios C1-C4 que el retrospectivo. Si el retrospectivo pasa y este
no, se charla con el usuario: nada se decide automáticamente.
