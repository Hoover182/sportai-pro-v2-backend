# Pre-registro: arreglo de goles O/U y ambos marcan (29/10/2026)

Congelado en este commit, ANTES de escribir el código de las variantes y de
correr nada. Diseño aprobado por el usuario el 29/10/2026. Nada de lo que
sigue se ajusta mirando resultados.

## Por qué

En el retrospectivo 2026 (`PREREGISTRO.md` + enmienda 1, `resultados_retro.json`)
Over/Under 2.5 (C2) y ambos marcan (C3) no le ganaron a la frecuencia de la
liga, y las probabilidades de 70% o más prometieron de más (C4). Los dos
mercados se escondieron de la app (backend #99, frontend 9c17edb).

Un diagnóstico exploratorio, **solo sobre julio a diciembre de 2025**
(3.480 partidos, sin mirar 2026), encontró dos causas distintas:

1. **Ambos marcan:** después de calcular la probabilidad, el modelo la mezcla
   con la tasa de "ambos marcan" de los últimos cruces directos (como mucho
   5, peso de hasta 30%). Esa mezcla empeora el Brier en todos los grupos con
   cruces (0,2481 sin mezcla, 0,2532 con mezcla) y fabrica los extremos
   (probabilidades de 70% o más: 26 casos sin mezcla, que aciertan 69%; 135
   con mezcla, que aciertan 58%).
2. **Goles:** los goles esperados están demasiado abiertos. La pendiente de
   los goles reales del partido sobre los esperados es 0,70 (sería 1 si
   estuvieran bien), igual con o sin cruces.

## Modelo de referencia

`main` en a821c8f (el mismo de la enmienda 1). El ocultamiento de #99 no
cambia `simular()`.

## Hipótesis y candidatos

**H-A, ambos marcan.** El peso de la mezcla con los cruces se multiplica por
*a* ∈ {0; 0,5} (hoy *a* = 1). Con la probabilidad sin mezcla *c* y con
mezcla *f* que da el modelo, la probabilidad con *a* es exactamente
`c + a·(f − c)`.

**H-B, goles.** Los goles esperados de cada equipo (los que entran a la
grilla de goles, después de todos los ajustes actuales) se acercan al
promedio de su liga:

    goles' = μ + s·(goles − μ),   s ∈ {0,6; 0,7; 0,8; 0,9}

- μ: promedio de goles a 90' del local (para el local) o del visitante (para
  el visitante) en la liga del partido, en los 365 días anteriores al
  partido, con los datos disponibles 1 hora antes. Con menos de 50 partidos
  en la liga, el promedio global de todas las ligas válidas en esos 365 días
  (el mismo criterio que R1).
- Cambia la grilla de goles entera: Over/Under, ambos marcan sin mezcla,
  handicaps y **también el 1X2**. Por eso hay un control del 1X2.

La corrección local/visitante (el modelo subestima los goles del local) **no
entra**: es otra hipótesis, aparte.

## Datos

- **Elección:** partidos de julio a diciembre de 2025 (donde se hizo el
  diagnóstico).
- **Evaluación:** el retrospectivo 2026 (01/01 al 28/10/2026) y la
  validación limpia (30/10 al 26/11/2026).
- Mismos partidos incluidos y excluidos, mismo point-in-time y mismo harness
  que `PREREGISTRO.md` (enmienda 1).

## Elección (en julio a diciembre de 2025)

1. *s* de H-B: el de menor Brier de Over/Under 2.5.
2. *a* de H-A: el de menor Brier de ambos marcan, con el *s* elegido aplicado.

Brier redondeado a 4 decimales. Si empatan, el más cercano al modelo actual
(*s* más grande, *a* más grande).

## Criterios para que un arreglo entre (en el retrospectivo 2026)

- **H-B entra** si: (1) mejora el Brier de Over/Under 2.5 contra el modelo
  actual (límite inferior del IC90 de la mejora > 0); (2) el 1X2 no empeora
  de forma demostrada (límite superior del IC90 de la mejora del Brier del
  1X2 ≥ 0); y (3) C1 de `PREREGISTRO.md` sigue pasando.
- **H-A entra** si mejora el Brier de ambos marcan (límite inferior del IC90
  > 0) contra el modelo actual con H-B aplicado si entró (o sin H-B si no
  entró).

## Criterio para volver a mostrar cada mercado

Con el modelo resultante (los arreglos que entraron), en el retrospectivo 2026:

- **Goles O/U** vuelve si pasa C2 de `PREREGISTRO.md` (Brier de Over/Under 2.5
  mejor que R1, límite inferior del IC90 > 0) **y** su parte de C4: las
  probabilidades ≥ 70% de Over y de Under 2.5 juntas no se pasan en más de
  3 pt (límite superior del IC90 de "real − prometido" ≥ −3 pt).
- **Ambos marcan** vuelve si pasa C3 (igual, contra R1) **y** su parte de C4
  (Sí y No juntos, mismo umbral).

Decisión del usuario: el mercado vuelve apenas pase el retrospectivo; si
después falla la validación limpia (mismos criterios), se vuelve a esconder.

**Primer tiempo:** goles y ambos marcan del primer tiempo salen de otro
cálculo (`simular_goles_1t`) que H-A y H-B no tocan y que nunca se evaluó.
Siguen escondidos pase lo que pase acá.

## Bootstrap

2.000 remuestreos por bloques de semana ISO, percentiles 5 y 95, semilla
2026, mejora pareada por partido (`analizar.ic_bloques`).

## Informativo (no decide nada)

- Brier y calibración de Over/Under 1.5 y 3.5 contra R1 (la tasa de la liga
  para esa línea), y de los 6 candidatos en la evaluación.
- Pendiente de goles reales sobre esperados con y sin H-B.
- Efecto en el 1X2 (Brier, acierto, calibración del local).
