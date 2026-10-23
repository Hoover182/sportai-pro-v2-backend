# Pre-registro: backtest del modelo de partido NBA (23/10/2026)

Congelado en este commit, ANTES de correr el backtest. Criterios aprobados por
el usuario el 23/10/2026. Nada de lo que sigue se ajusta mirando resultados.

## Modelo

`app/services/nba_model.py` tal como está en este commit: port del script del
usuario con los arreglos aprobados (H2H de cada lado, sin pretemporada, ventana
de 10 que cruza temporadas, semilla fija, solo partidos anteriores a la fecha).
`analizar_partido` se llama tal cual, sin atajos.

## Datos

- `app/services/nba_partidos.csv` (cdn.nba.com): 2023-24, 2024-25, 2025-26.
  Entran todos los tipos guardados: fase regular, play-in, playoffs y final de
  la Copa (la pretemporada no está en el CSV).
- **Ajuste:** 2024-25 (2023-24 solo sirve de historial previo).
- **Evaluación:** 2025-26, temporada que no se usa para elegir nada.
- Se saltean los partidos donde algún equipo no tiene partidos previos
  (`analizar_partido` devuelve None). Se reporta cuántos.
- Resultado real: puntos finales con prórroga incluida (total y margen).

## Métricas

- **Brier del ganador** (principal): promedio de (prob_local − gana_local)².
- % de acierto del ganador (prob_local ≥ 0,5 → elige local).
- Error absoluto medio del total (proy_local + proy_visitante vs. puntos reales).
- Error absoluto medio del margen (proy_local − proy_visitante vs. real).

## Bases de comparación

- **Probabilidad fija:** % de victorias locales de las temporadas anteriores a
  la evaluada (para 2025-26: 2023-24 + 2024-25 juntas).
- **Mejor récord:** gana el de mejor % de victorias en la misma temporada hasta
  el día anterior; si empatan (incluido 0-0), el local.

## Criterios

1. **La base sirve para producción** si en 2025-26 cumple las dos:
   - Brier menor que el de la probabilidad fija.
   - Acierto mayor o igual que el de la regla de mejor récord.

   Si no pasa, no se publica y se charla con el usuario.
2. **Localía.** h ∈ {0; 0,5; …; 5} puntos (`Params.ventaja_local`). Se elige el
   h con menor Brier en 2024-25 (empate → el h más chico). Entra si, en 2025-26:
   - mejora el Brier de la base, con intervalo bootstrap del 90% de la mejora
     por partido (Brier base − Brier variante) con límite inferior > 0, y
   - el error del margen no empeora (variante ≤ base).
3. **Fatiga.** Encima del resultado del punto 2 (h elegido si entró, si no 0).
   f ∈ {0,85; 0,86; …; 1,00} (`Params.factor_fatiga`). Se elige el f con menor
   error del total en 2024-25 (empate → el f más cercano a 1). Entra si, en
   2025-26:
   - mejora el error del total, con intervalo bootstrap del 90% de la mejora
     por partido (|error| referencia − |error| variante) con límite inferior > 0, y
   - el Brier no empeora (variante ≤ referencia).

   Se reporta además qué habría dado f = 0,85 (el valor original del script).

## Bootstrap

2.000 remuestreos de los partidos de 2025-26 con reposición, pareados (el mismo
remuestreo para base y variante), percentiles 5 y 95, semilla 2026.
