# Pre-registro: paso final hacia la tasa de la liga (06/11/2026)

Congelado en este commit, ANTES de escribir el código del paso final, de
calcular *w* y de mirar ningún partido posterior al 28/10/2026. Diseño
aprobado por el usuario el 06/11/2026. Nada de lo que sigue se ajusta
mirando resultados.

## Por qué

En `PREREGISTRO_goles_ambos.md` (resultados en `resultados_goles_ambos.json`)
ni Over/Under 2.5 ni ambos marcan le ganaron a la tasa de la liga (R1), y las
probabilidades de 70% o más prometieron de más. Los arreglos dentro de la
grilla de goles no sirven porque la misma grilla arma el 1X2 (H-B mejoraba
O/U pero empeoraba el 1X2).

La idea salió de mirar la calibración de 2026, así que 2026 NO se usa para
decidir si funciona: solo para calcular *w* (abajo). La evaluación es con
partidos nuevos.

## Modelo

- **Base:** el modelo final de `PREREGISTRO_goles_ambos.md`: `main` en
  a821c8f, sin templar los goles (*s* = 1) y ambos marcan **sin** la mezcla
  con los cruces directos (*a* = 0). Mismo harness (`harness_goles_ambos.py`,
  columnas `o25_s1` y `ambos_s1`).
- **Paso final**, solo para la probabilidad de Over 2.5 y la de ambos marcan
  "Sí", después de todo lo demás:

      p_final = R1 + w · (p_modelo − R1)

  - R1: la tasa de la liga para ese mercado, exactamente como en
    `PREREGISTRO.md` (últimos 365 días antes del partido, datos de 1 hora
    antes, liga con 50 partidos o más; si no, el global de las ligas
    válidas).
  - Under 2.5 = 1 − Over 2.5 y ambos "No" = 1 − "Sí" (en goles a 90' no hay
    empate en una línea .5).
  - Un *w* para Over/Under 2.5 y otro para ambos marcan. Un solo valor para
    todas las ligas.
- La grilla de goles, el 1X2, los handicaps y todo lo demás **no cambian**.

## Cómo se calcula *w*

Con todos los partidos que ya están predichos con el modelo base: julio a
diciembre de 2025 (`pred_ga_2025h2.csv`, 3.480 evaluados) y 01/01 al 28/10/2026
(`pred_ga_2026.csv`, 9.320 evaluados), con los mismos filtros de partidos que
`analizar_goles_ambos.py`.

*w* es el que minimiza el Brier en esos partidos, que tiene fórmula cerrada:

    w = Σ (y − R1)·(p_modelo − R1) / Σ (p_modelo − R1)²

(y = 1 si pasó, 0 si no). Se recorta a [0; 1] y se redondea a 2 decimales.
El cálculo usa solo partidos hasta el 28/10/2026, así que no depende de cuándo
se corra. El valor de cada *w* se commitea antes de la evaluación y no se toca
más.

Si algún *w* da 0, ese mercado queda descartado sin evaluar (sería R1 y no
puede ganarle a R1).

## Datos de evaluación

- Partidos con inicio entre el **07/11/2026 y el 06/03/2027** (UTC), con los
  mismos filtros y el mismo point-in-time que `PREREGISTRO.md` (enmienda 1).
- Se corre **una sola vez**, después del 08/03/2027, con el CSV del backend
  en `main` (solo datos; el código es el congelado).
- Si quedan menos de 2.000 partidos evaluados, se extiende de a un mes entero
  (hasta el 06/05/2027 como máximo) mirando **solo la cantidad**, no los
  resultados. Si aun así no llega, se corre con lo que haya y se anota.
- No hay miradas intermedias.

## Criterios para volver a mostrar (en esos partidos)

- **Over/Under 2.5** vuelve si:
  1. **C2:** el Brier de Over 2.5 con el paso final es mejor que el de R1
     (límite inferior del IC90 de la mejora > 0); y
  2. **C4:** las probabilidades finales ≥ 70% de Over y de Under 2.5 juntas
     no se pasan en más de 3 pt (límite superior del IC90 de
     "real − prometido" ≥ −3 pt). Si no hay ningún caso ≥ 70%, C4 pasa (no
     se prometió nada fuerte) y se anota.
- **Ambos marcan** vuelve si pasa **C3** (igual que C2, contra R1 de ambos
  marcan) y su **C4** (Sí y No juntos, mismo umbral y misma regla sin casos).

Bootstrap igual que siempre: 2.000 remuestreos por bloques de semana ISO,
percentiles 5 y 95, semilla 2026, mejora pareada por partido
(`analizar.ic_bloques`).

## Si pasa con un *w* bajo

Decidido ahora: **es aceptable**. Un mercado conservador que le gana de forma
demostrada a la tasa de la liga se muestra aunque casi nunca llegue a 70% y
casi nunca entre al Top de picks; los umbrales de picks actuales (70/55) no
se tocan para compensar. C2/C3 ya impiden mostrar algo que sea solo la tasa
de la liga con otro nombre.

## Qué se muestra si vuelve

- Solo Over/Under **2.5** del total del partido y ambos marcan (Sí/No).
- Siguen escondidas pase lo que pase: las otras líneas del total (0.5, 1.5,
  3.5 a 7.5), los goles por equipo y todo el primer tiempo
  (`simular_goles_1t`). Ninguna se evalúa acá; mostrarlas pide otro
  pre-registro.
- Para mostrarlos, producción tiene que usar el mismo cálculo: *a* = 0 en
  ambos marcan (hoy la mezcla con cruces sigue activa en `futbol_service.py`),
  el mismo R1 y los mismos *w*. Antes de publicar se compara contra el harness
  en una muestra de partidos (diferencia máxima 0,005).
- Si para marzo de 2027 la grilla de goles de `main` cambió respecto de
  a821c8f, el resultado vale para el modelo congelado: se charla con el
  usuario antes de mostrar nada.

## Informativo (no decide nada)

- Los *w*, el Brier del modelo sin el paso final, y la calibración por bandas
  de 10 pt con y sin el paso final.
- Cuántos partidos dan ≥ 70% con el paso final.
- Over/Under 1.5 y 3.5 con su propio *w* (misma fórmula, mismos datos), sin
  decidir nada.
