# Pre-registro: multiplicador de goles por intensidad ofensiva (06/11/2026)

Congelado en este commit, ANTES de escribir el código de las variantes y de
correr nada. Diseño aprobado por el usuario el 06/11/2026. Nada de lo que sigue se ajusta
mirando resultados.

## Por qué

`futbol_service.simular()` multiplica los goles esperados de cada equipo por

    m = 0,95 + 0,10 · intensidad   (tope entre 0,9 y 1,15, que nunca actúa)

con `intensidad` ∈ [0; 1] = (tiros totales propios por partido − 8) / 12, en
sus últimos 10 partidos de la misma liga (`modelo_presion.
calcular_indice_intensidad_ofensiva`). Sin datos de tiros o sin partidos en
esa liga, intensidad = 0,5 → m = 1. Rango real: ×0,95 a ×1,05 por equipo,
promedio ×0,989. Entró el 04/08/2026 (088e133) sin backtest. La función dice
que está pensada para corners y se reusó para goles.

Entra a la grilla de goles, así que mueve el 1X2 (lo único visible que sale
de esa grilla, junto con doble oportunidad y handicaps). El 1X2 pasó C1 del
retrospectivo CON este multiplicador. La pregunta es si sin él, o con la
mitad, el 1X2 mejora. No se buscó en los datos: salió de leer el código
(06/11/2026).

## Modelo de referencia

`main` en a821c8f, el mismo de `PREREGISTRO.md` (enmienda 1) y del
retrospectivo, con el mismo harness point-in-time. El cambio de tarjetas del
06/11 no toca goles ni el 1X2.

## Hipótesis y candidatos

**H-G.** El desvío del multiplicador se multiplica por *f*, igual para local
y visitante:

    m' = 1 + f · (m − 1),   f ∈ {0; 0,5}   (hoy f = 1)

Con *f* = 0 no hay multiplicador de goles. No cambia nada más (corners,
tarjetas, Elo, ajuste de liga, mezcla con cruces).

## Datos

- Mismos filtros, mismo point-in-time y mismo harness que `PREREGISTRO.md`
  (enmienda 1): partidos con 5 o más previos por equipo, resultado a 90'.
- **Elección:** julio a diciembre de 2025 (~3.480 partidos).
- **Evaluación:** el retrospectivo 2026 completo (01/01 al 28/10/2026,
  ~9.320 partidos). Ahí ya se miró el 1X2 del modelo actual, pero nunca una
  variante de este multiplicador, y la hipótesis no salió de esos datos.
- **Confirmación con datos nuevos:** partidos del 07/11/2026 al 06/03/2027,
  en la misma corrida única de `PREREGISTRO_capa_liga.md` (después del
  08/03/2027).

## Elección (julio a diciembre de 2025)

*f* con menor Brier del 1X2 (3 resultados) entre {1; 0,5; 0}. Redondeo a 4
decimales; si empatan, el más cercano al actual (*f* más grande).

## Criterio para que entre (en la evaluación 2026)

Si la elección deja *f* = 1, no entra nada y termina acá.

Si no, H-G entra si con el *f* elegido:

1. el Brier del 1X2 mejora contra el modelo actual (límite inferior del IC90
   de la mejora > 0); y
2. **C1 sigue pasando** (Brier del 1X2 mejor que R1 con límite inferior del
   IC90 > 0, y acierto ≥ R2); y
3. la parte de 1X2 de C4 (probabilidades ≥ 70% de cualquiera de los 3
   resultados: límite superior del IC90 de "real − prometido" ≥ −3 pt) pasa,
   si pasa con el modelo actual.

Si entra, se aplica en producción. Si después falla la confirmación con datos
nuevos (mismo criterio 1), se vuelve atrás y se charla con el usuario.

**Si no entra** (la elección deja *f* = 1, o la mejora no es demostrable),
se mira *f* = 0 contra el actual en la evaluación (Brier del 1X2):

- si el IC90 de la mejora queda **entero dentro de ±0,0010**, el multiplicador
  de goles **se saca del código** (decisión del usuario, 06/11/2026: un ajuste
  sin backtest que no cambia nada medible solo agrega riesgo y mantenimiento);
- si no, se deja como está.

Sacarlo también exige que C1 siga pasando con *f* = 0.

## Bootstrap

2.000 remuestreos por bloques de semana ISO, percentiles 5 y 95, semilla
2026, mejora pareada por partido (`analizar.ic_bloques`).

## Informativo (no decide nada)

- Log-loss y acierto del 1X2, y calibración del local por bandas, con cada *f*.
- Handicap europeo ±1 y doble oportunidad (Brier) con cada *f*.
- Over/Under 2.5 y ambos marcan (ocultos) con cada *f*.
- Cuántos partidos tienen intensidad neutra (sin datos de tiros) y el
  resultado separado por con/sin datos.

## Fuera de este pre-registro

`multiplicador_corners` (misma intensidad, ×0,8 a ×1,3): su propio
pre-registro, después de este.
