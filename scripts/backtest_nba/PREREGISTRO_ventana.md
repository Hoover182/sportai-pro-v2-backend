# Pre-registro: ventana de promedios del modelo NBA (24/10/2026)

Congelado en este commit, ANTES de bajar 2021-22/2022-23 y de correr el
backtest. Diseño aprobado por el usuario el 24/10/2026. Nada de lo que sigue
se ajusta mirando resultados.

## Por qué

En el backtest de `PREREGISTRO.md` (`resultados.json`) el modelo no pasó el
criterio 1 por acierto (65,28% contra 66,64% de la regla del mejor récord). En un
análisis exploratorio posterior sobre 2025-26 apareció que la diferencia de
puntos de **toda la temporada** acertaba 66,4%, contra 65,5% de la de los
**últimos 10**. Como la hipótesis salió de mirar 2025-26, esa temporada ya no
es una validación limpia: se suma **2022-23**, que nadie miró.

## Lo que no se toca

- Todo lo aprobado en `resultados.json`: localía h = 1,5 (entró), fatiga
  f = 1,0 (no entró).
- H2H de la misma temporada al 20%, Monte Carlo y semilla.
- El **desvío** de puntos sigue saliendo de los últimos 10 partidos. La
  calibración conservadora queda para otra prueba, y cambiar el desvío
  mezclaría los dos efectos.
- `bt.py` y `PREREGISTRO.md` no cambian.

## Modelo de referencia

`Params(ventaja_local=1.5)`: promedios de los últimos 10 partidos (cruzando
temporadas), es decir el modelo aprobado hoy.

## Variantes (`app/services/nba_model.py`, `Params.ventana`)

Cambian solo los dos promedios: puntos anotados y puntos permitidos.

- **V1 `temporada`**: todos los partidos de la temporada en curso anteriores a la
  fecha, con el mismo peso. Si son menos de *m*, se completan hasta *m* con los
  últimos partidos de la temporada anterior.
  *m* ∈ {5, 10, 15, 20}.
- **V2 `decaimiento`**: todos los partidos anteriores del equipo en el CSV
  (cruzando temporadas). El partido más reciente pesa 1 y el peso se reduce a la
  mitad cada *H* partidos: peso = 0,5^(i/H), con i = 0 para el más reciente.
  *H* ∈ {10, 20, 40, 80}.

## Datos

- `app/services/nba_partidos.csv` con **2021-22 y 2022-23** sumadas (mismo sync
  del CDN, mismo criterio de partidos salteados con aviso), más 2023-24,
  2024-25 y 2025-26 tal como están.
- 2021-22 solo sirve de historial previo.
- **Elección:** 2023-24 + 2024-25 juntas.
- **Evaluación:** 2025-26 (ya mirada en el exploratorio) y 2022-23 (limpia).
- Se saltean los partidos donde algún equipo no tiene partidos previos y se
  reporta cuántos.

## Elección

De los 8 candidatos gana el de **menor Brier** sobre 2023-24 + 2024-25 juntas,
redondeado a 4 decimales como en `bt.py`. Si empatan, gana el más simple: V1
antes que V2, dentro de V1 el *m* más chico y dentro de V2 el *H* más grande.

## Criterio para que entre

En **las dos** temporadas de evaluación, contra la referencia:

1. mejora el Brier: intervalo bootstrap del 90% de la mejora por partido
   (Brier referencia − Brier variante) con límite inferior > 0, y
2. el acierto no empeora (variante ≥ referencia).

Si falla en cualquiera de las dos, no entra.

## Criterio 1 del modelo resultante (se reporta aparte)

Para el modelo final (la variante si entró, si no la referencia), en cada
temporada de evaluación, igual que el criterio 1 de `PREREGISTRO.md`:

- Brier menor que el de la probabilidad fija. La tasa de victorias locales sale
  de las temporadas previas: 2023-24 + 2024-25 para 2025-26 (como en el
  pre-registro original) y 2021-22 para 2022-23.
- Acierto mayor o igual que el de la regla del mejor récord (misma temporada,
  hasta el día anterior; si empatan, el local).

Esto decide si se puede publicar. Si no pasa, no se publica y se charla con el
usuario.

## Bootstrap

2.000 remuestreos pareados por temporada de evaluación, percentiles 5 y 95,
semilla 2026 (`bt.ic_mejora`).

## Informativo

Se reportan también las métricas de los 8 candidatos en las temporadas de
evaluación. No deciden nada: la elección ya se hizo con 2023-24 + 2024-25.
