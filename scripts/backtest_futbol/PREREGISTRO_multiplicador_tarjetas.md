# Pre-registro: multiplicador de tarjetas (06/11/2026)

Congelado en este commit, ANTES de escribir el código de las variantes y de
correr nada. Diseño aprobado por el usuario el 06/11/2026. Nada de lo que sigue se ajusta
mirando resultados.

## Por qué

El modelo proyecta ~5,0 amarillas por partido y salen ~4,1. En el
retrospectivo 2026 (`resultados_retro.json`, informativo) Over 4.5 tarjetas
prometió 54,0% y salió 41,4% (6.282 partidos), y quedó peor que la tasa del
período. La investigación del 25/09/2026 (walk-forward, 596 partidos de
marzo-mayo y septiembre de 2026) señaló como causa principal a
`multiplicador_tarjetas` (`futbol_service.py`):

    m = 1 + 0,15·presión + 0,10·agresividad (+0,35 si es clásico), tope 1,5

Solo sube, promedia ×1,15, nunca se backtesteó y multiplica la proyección
total, la de cada equipo y vuelve a muestrear todas las líneas de tarjetas
(total y por equipo).

## Modelo de referencia

`main` en a821c8f, el mismo de `PREREGISTRO.md` (enmienda 1). Mismo harness
point-in-time.

## Hipótesis y candidatos

**H-T.** El exceso del multiplicador se multiplica por *f*:

    m' = 1 + f·(m − 1),   f ∈ {0; 0,5}   (hoy f = 1)

Con *f* = 0 no hay multiplicador. Todo lo demás de tarjetas (promedios de
los equipos, ajuste por rival, parejez, k de la mezcla Gamma-Poisson) queda
igual. No toca goles, corners ni el 1X2.

## Datos

- Mismos filtros que el retrospectivo para tarjetas: partidos con stats
  verificadas (corners total > 0; amarillas admiten 0 si hay corners).
- **Elección:** julio a diciembre de 2025 (~2.800 partidos con stats). No se
  usó en la investigación de septiembre.
- **Evaluación:** 2026 **sin los meses que miró la investigación de
  septiembre**: enero, febrero, junio, julio, agosto y 1-28 de octubre
  (~3.200 partidos con stats). Marzo, abril, mayo y septiembre de 2026 quedan
  afuera.
- **Confirmación con datos nuevos:** partidos del 07/11/2026 al 06/03/2027,
  en la misma corrida única de `PREREGISTRO_capa_liga.md` (después del
  08/03/2027).

## Elección (julio a diciembre de 2025)

*f* con menor Brier de Over 4.5 tarjetas (total del partido), entre
{1; 0,5; 0}. Redondeo a 4 decimales; si empatan, el más cercano al actual
(*f* más grande).

## Criterio para que entre (en la evaluación 2026)

H-T entra si, con el *f* elegido:

1. el Brier de Over 4.5 tarjetas mejora contra el modelo actual (límite
   inferior del IC90 de la mejora > 0); y
2. Over 3.5 y Over 5.5 no empeoran de forma demostrada (límite superior del
   IC90 de la mejora ≥ 0 en cada una).

Si entra, se aplica en producción (el mercado de tarjetas hoy está visible).
Si después falla la confirmación con datos nuevos (mismo criterio 1), se
vuelve atrás y se charla con el usuario.

## Mercado de tarjetas contra la tasa de la liga

Con el modelo resultante (con H-T si entró), en la evaluación 2026:

- **C5:** el Brier de Over 4.5 tarjetas mejora contra R1 de tarjetas (tasa de
  Over 4.5 de la liga en los 365 días anteriores, partidos con stats, datos
  de 1 hora antes; con menos de 50 partidos, el global), límite inferior del
  IC90 > 0.
- **C4 de tarjetas:** las probabilidades ≥ 70% de Over y Under 4.5 juntas no
  se pasan en más de 3 pt (límite superior del IC90 de "real − prometido"
  ≥ −3 pt).

Si falla C5 o C4, el O/U de tarjetas (total y por equipo) **se esconde**, con
el mismo criterio que goles y ambos marcan (decisión del usuario, 06/11/2026),
aunque saque los picks de tarjetas del Top3.

## Bootstrap

2.000 remuestreos por bloques de semana ISO, percentiles 5 y 95, semilla
2026, mejora pareada por partido (`analizar.ic_bloques`).

## Informativo (no decide nada)

- Sesgo medio (proyección − real) y calibración por bandas de Over 4.5 con
  cada *f*.
- Las otras líneas del total (2.5 a 7.5) y las de cada equipo (0.5 a 3.5).
- Cada componente por separado (presión, agresividad, clásico) con su propio
  factor 0/0,5/1, sin decidir nada.
- Ancho de la distribución (varianza/media implícita contra real): en
  septiembre salía demasiado ancha. Si se confirma, es otra hipótesis aparte.

## Fuera de este pre-registro

`multiplicador_corners` (intensidad ofensiva, 0,8 a 1,3) y
`multiplicador_goles_local/visitante` (0,9 a 1,15, entra en la grilla de
goles y por lo tanto en el 1X2) tampoco tienen backtest. Cada uno pide su
propio pre-registro.
