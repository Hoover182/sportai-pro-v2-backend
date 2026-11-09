# Pre-registro: multiplicador de corners por intensidad ofensiva (08/11/2026)

Congelado en este commit, ANTES de escribir el código de las variantes y de
correr nada. Diseño aprobado por el usuario el 08/11/2026. Nada de lo que sigue
se ajusta mirando resultados.

## Por qué

`futbol_service.simular()` multiplica los corners proyectados por

    m = 0,9 + 0,3 · (intensidad_local + intensidad_visitante) / 2
    (tope entre 0,8 y 1,3, que nunca actúa)

con `intensidad` ∈ [0; 1] = (tiros totales propios por partido − 8) / 12, en
los últimos 10 partidos del equipo en la misma liga
(`modelo_presion.calcular_indice_intensidad_ofensiva`). Sin datos de tiros o
sin partidos en esa liga, intensidad = 0,5.

Con los dos equipos neutros (intensidad 0,5) el multiplicador da **×1,05, no
×1**: sin datos, los corners suben 5%. Rango real ×0,90 a ×1,20. En las
corridas ya hechas (solo entradas, sin mirar resultados): media ×1,022 en
jul-dic 2025 y ×1,029 en 2026; sube en el 69% y el 75% de los partidos; en el
20% y el 34% ningún equipo tiene datos de tiros.

Se aplica después de simular: multiplica la proyección total y la de cada
equipo, y vuelve a muestrear todas las líneas de corners (total y por equipo).
Nunca se backtesteó. No toca goles, 1X2, tarjetas ni tiros. Es el último de
los tres multiplicadores sin backtest (tarjetas: f = 0,5 en producción desde
el 06/11; goles: sacado el 08/11).

**Lo que ya se vio de 2026.** El informativo del retrospectivo
(`resultados_retro.json`) mostró Over 9.5 corners en 2026 con el modelo
actual: promete 46,9%, sale 48,4% (6.282 partidos); Brier 0,2484 contra 0,2497
de la tasa del período (que mira el futuro). Por bandas, las puntas se pasan
(20-30% sale 41%; 60-70% sale 57%). Achicar el multiplicador acerca las
proyecciones al centro, así que la hipótesis no es del todo independiente de
ese dato. La hipótesis salió del código (mismo patrón que tarjetas y goles), y
el mismo informativo del retro no sacó meses de la evaluación de tarjetas.
Decisión del usuario (08/11/2026): se evalúa en todo 2026 igual, dejando esto
escrito; la confirmación con datos nuevos es la prueba limpia.

## Modelo de referencia

`main` en a821c8f, el mismo de `PREREGISTRO.md` (enmienda 1), con el mismo
harness point-in-time (`harness.py` con el arreglo del caché de nombres,
aed912c). Los cambios posteriores en producción (tarjetas f = 0,5, sin
multiplicador de goles) no tocan los corners.

## Hipótesis y candidatos

**H-C.** El desvío del multiplicador se multiplica por *f*:

    m' = 1 + f · (m − 1),   f ∈ {0; 0,5}   (hoy f = 1)

Con *f* = 0 no hay multiplicador (tampoco el ×1,05 de los neutros). Todo lo
demás de corners (promedios de los equipos, ajuste por rival, mezcla con
cruces, k de la Gamma-Poisson) queda igual.

## Datos

- Mismos filtros que el retrospectivo para corners: partidos con stats
  verificadas (corners total > 0) y 5 o más previos por equipo.
- **Elección:** julio a diciembre de 2025 (~2.800 partidos con stats).
- **Evaluación:** el retrospectivo 2026 completo (01/01 al 28/10/2026,
  ~6.300 partidos con stats).
- **Confirmación con datos nuevos:** partidos del 07/11/2026 al 06/03/2027,
  en la misma corrida única de `PREREGISTRO_capa_liga.md` (después del
  08/03/2027).

## Elección (julio a diciembre de 2025)

*f* con menor Brier de Over 9.5 corners (total del partido), entre
{1; 0,5; 0}. Redondeo a 4 decimales; si empatan, el más cercano al actual
(*f* más grande).

## Criterio para que entre (en la evaluación 2026)

Si la elección deja *f* = 1, no entra nada (ver "Si no entra").

Si no, H-C entra si, con el *f* elegido:

1. el Brier de Over 9.5 corners mejora contra el modelo actual (límite
   inferior del IC90 de la mejora > 0); y
2. Over 8.5 y Over 10.5 no empeoran de forma demostrada (límite superior del
   IC90 de la mejora ≥ 0 en cada una).

Si entra, se aplica en producción. Si después falla la confirmación con datos
nuevos (mismo criterio 1), se vuelve atrás y se charla con el usuario.

## Si no entra

Misma regla que goles (decisión del usuario, 08/11/2026): se mira *f* = 0
contra el actual en la evaluación (Brier de Over 9.5). Si el IC90 de la mejora
queda entero dentro de ±0,0010, el multiplicador se saca del código (y con él
el ×1,05 de los partidos sin datos de tiros); si no, se deja como está.

**Modelo resultante:** el *f* elegido si H-C entra; *f* = 0 si se saca; si
no, el actual (*f* = 1).

## Mercado de corners contra la tasa de la liga

Con el modelo resultante (con H-C si entró), en la evaluación 2026:

- **C5:** el Brier de Over 9.5 corners mejora contra R1 de corners (tasa de
  Over 9.5 de la liga en los 365 días anteriores, partidos con stats, datos de
  1 hora antes; con menos de 50 partidos, el global), límite inferior del
  IC90 > 0.
- **C4 de corners:** las probabilidades ≥ 70% de Over y Under 9.5 juntas no se
  pasan en más de 3 pt (límite superior del IC90 de "real − prometido"
  ≥ −3 pt).

Si falla C5 o C4 (decisión del usuario, 08/11/2026), se usa el mismo patrón
que goles y ambos marcan: **se oculta el pronóstico del modelo** (O/U de
corners total y por equipo, y las proyecciones de corners), y en su lugar se
muestra el **promedio histórico de la liga** para Over/Under 9.5 corners,
etiquetado como tal, con el mecanismo que ya existe (`promedio_liga` en
`/partido` y el bloque gris del frontend): partidos de la misma liga en los
365 días anteriores con stats verificadas, mínimo 50, nada en copas, torneos
internacionales ni amistosos. Los corners salen de Top Picks, value bets y
análisis IA, como goles. Las líneas por equipo quedan ocultas sin reemplazo.

## Bootstrap

2.000 remuestreos por bloques de semana ISO, percentiles 5 y 95, semilla
2026, mejora pareada por partido (`analizar.ic_bloques`).

## Informativo (no decide nada)

- Sesgo medio (proyección − real) y calibración por bandas de Over 9.5 con
  cada *f*.
- Las otras líneas del total y las de cada equipo.
- Solo los partidos con los dos equipos neutros (sin tiros): cuánto pesa el
  ×1,05.
- Ancho de la distribución (varianza/media implícita contra real). Si sale
  mal, es otra hipótesis aparte.

## Fuera de este pre-registro

El árbitro (tarjetas) y el estilo de juego (tiros), cada uno con su propio
pre-registro y en ese orden.
