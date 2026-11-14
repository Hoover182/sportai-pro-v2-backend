# Pre-registro: tiros al arco, tiros totales y atajadas (14/11/2026)

Congelado en este commit, ANTES de escribir el harness y de correr nada.
Diseño aprobado por el usuario el 14/11/2026. Nada de lo que sigue se ajusta
mirando resultados.

## Por qué

Tiros al arco, tiros totales y atajadas (total del partido y por equipo)
están en producción: en `/partido`, en Top Picks (Over/Under 6.5 y 7.5 tiros
al arco, 23.5 y 24.5 tiros totales, 4.5 y 5.5 atajadas) y en el análisis IA.
**Nunca se backtestearon contra resultados.** Desde que se ocultaron goles,
ambos marcan, tarjetas y corners, los Top Picks salen sobre todo de 1X2,
doble oportunidad, handicaps, tiros y atajadas: estos dos pesan más sin
validación.

Todos los mercados que se midieron hasta ahora salvo el 1X2 fallaron contra
la tasa de la liga o por exceso de confianza. Decisión del usuario
(14/11/2026): primero verificar que lo que ya se muestra sea sólido, antes de
pensar en mejorarlo (estilo de juego queda después). Por eso **acá no hay
variantes del modelo**: se evalúa el modelo actual tal cual.

## Cómo es el modelo hoy (sin backtest)

- Media de cada equipo: ventana de los últimos 10 partidos con stats, la de
  su condición (local/visitante) en la liga del partido, ajustada por lo que
  concede el rival (`ajustar_medias_con_rival`) y mezclada con cruces
  directos.
- Topes por equipo: tiros al arco 1,5 a 9; tiros totales 5 a 22; atajadas
  1 a 11.
- Muestreo Gamma-Poisson independiente por equipo, con el *k* de corners
  (`n_partidos_stats`); atajadas usa el mismo *k*.
- Total del partido = suma de los dos equipos. "Atajadas local" = atajadas
  del arquero local.
- Se muestran solo si cada equipo tiene 3 o más partidos con stats en los
  últimos 12 meses (#82).

## Lo que ya se miró antes de escribir esto (sin resultados del modelo)

- **Diagnóstico del 17/10/2026** (tiros totales por equipo, sin
  implementar): con partidos del 01/08 al 15/10/2026, la proyección le gana
  al promedio crudo de 10 partidos en error medio, pero los 20 equipos de
  más volumen quedan subproyectados (+2,0 tiros) y los locales también
  (+1,0). Esto toca **tiros totales por equipo en ago-oct 2026**, que cae
  dentro de la evaluación. Tiros al arco, atajadas y los totales del partido
  no se miraron nunca.
- **Cobertura** (solo conteos, CSV de `main` eea826c). Partidos con stats:
  2.963 en jul-dic 2025, 4.369 en ene-jul 2026, 2.950 entre ago y el 28/10
  de 2026. Tiros: casi todos. Atajadas: 87%, 96% y 89% de esos. Antes de
  jul-2025 las atajadas casi no están (1.314 de 13.448).
- **Tasas reales con datos ANTERIORES a jul-2025** (752 partidos con los
  tres datos, jul-2023 a jun-2025; fuera de la elección y de la
  evaluación):
  - Tiros al arco: media 8,7. Over 6.5 sale 74%, 7.5 sale 62%, 8.5 sale 50%.
  - Tiros totales: media 25,5. Over 23.5 sale 60%, 24.5 sale 54%, 25.5
    sale 47%.
  - Atajadas: media 6,1. Over 4.5 sale 73%, 5.5 sale 56%, 6.5 sale 39%.
  - Las líneas de Top Picks no están en el centro: Over 6.5 tiros al arco y
    Over 4.5 atajadas ya salen ~3 de cada 4 veces. Una tasa de la liga
    alta es una referencia difícil de batir en esas líneas.

**Expectativa, escrita antes de correr:** no hay motivo para suponer que
pasan. Las medias de 10 partidos son ruidosas (lo mismo que se vio en goles:
proyecciones demasiado dispersas) y el diagnóstico del 17/10 ya mostró sesgo
en tiros por equipo.

## Modelo de referencia

El de producción: `main` en eea826c (tarjetas f = 0,5, sin multiplicador de
goles, corners y tarjetas ocultos; nada de eso toca tiros ni atajadas, salvo
por la secuencia del azar). Harness point-in-time nuevo
(`harness_tiros.py`) que guarda proyecciones y O/U de tiros y atajadas.
**Antes de correr se verifica** que el harness dé exactamente lo mismo que
`main` en proyecciones y en Over de las líneas de Top Picks en al menos 30
partidos. Si no da igual, se arregla y se anota como enmienda antes de
correr.

## Series que se evalúan

Nueve series, cada una con su decisión:

| Mercado | Total del partido | Local | Visitante |
|---|---|---|---|
| Tiros al arco | T-arco | L-arco | V-arco |
| Tiros totales | T-tiros | L-tiros | V-tiros |
| Atajadas | T-ataj | L-ataj | V-ataj |

## Datos

- **CSV:** `futbol_partidos.csv` de `main` en eea826c (merge del sync #122;
  SHA-256 empieza con 4b6b315f0facfa6e). Copia congelada en
  `datos_tiros_eea826c.csv`. Syncs posteriores no cambian este backtest.
- **Filtros:** partidos jugados con stats verificadas (corners total > 0),
  con los dos datos de la serie (para atajadas: las dos columnas de
  atajadas), con 5 o más previos por equipo, con los dos equipos cumpliendo
  el criterio de producción (3+ partidos con stats en 12 meses) y con el
  modelo devolviendo la serie (no `None`).
- **Elección de la línea central:** julio a diciembre de 2025. Solo con
  resultados reales, sin el modelo (ver abajo).
- **Evaluación:** 01/01 al 28/10/2026 completo (~7.300 partidos con stats).
  Incluye ago-oct 2026, que el diagnóstico del 17/10 miró para tiros totales
  por equipo. Decisión del usuario (14/11/2026): se evalúa en 2026 completo
  igual, dejándolo escrito, como en corners; la confirmación con datos nuevos
  es la prueba limpia.
- **Confirmación con datos nuevos:** partidos del 07/11/2026 al 06/03/2027,
  en la misma corrida única de `PREREGISTRO_capa_liga.md` (después del
  08/03/2027).

## Elección de la línea central (julio a diciembre de 2025)

Para cada serie, entre las líneas que el modelo calcula, la **línea
central** es aquella cuya tasa real de Over en jul-dic 2025 (partidos con
los filtros de arriba) esté más cerca de 50%. Redondeo a 3 decimales; si
empatan, la más baja. No se usa el modelo en este paso.

## Criterios (evaluación 2026)

Por serie, con el modelo actual:

- **C5 (contra la tasa de la liga):** el Brier de Over de la línea central
  mejora contra R1, con límite inferior del IC90 de la mejora > 0. R1 = tasa
  de Over de esa línea en la liga del partido en los 365 días anteriores
  (partidos con los dos datos de la serie; datos de 1 hora antes; con menos
  de 50 partidos, la tasa global de esos 365 días). Para las series por
  equipo, R1 es la tasa del lado que corresponde (local o visitante).
- **C4 (exceso de confianza):** las probabilidades ≥ 70% no se pasan en más
  de 3 pt (límite superior del IC90 de "real − prometido" ≥ −3 pt). En las
  series por equipo: Over y Under de la línea central juntos, como en los
  mercados anteriores. **En los totales también entran las dos líneas de Top
  Picks** (Over y Under), porque de ahí salen los picks de ≥ 70% que ve el
  usuario. Decisión del usuario (14/11/2026): medir la habilidad en la línea
  central, donde se puede medir, y proteger de la sobreconfianza los picks
  que ve el usuario.

Una serie **pasa** si cumple C5 y C4. Cada serie decide sola, también las
de cada equipo (decisión del usuario, 14/11/2026): una serie por equipo
puede mostrarse aunque el total se oculte, y al revés.

Si una serie no tiene ningún pronóstico de 70% o más en las líneas de C4,
C4 se da por cumplido y se anota.

## Qué pasa según el resultado

Mismo criterio que corners y goles (decisión del usuario, 14/11/2026):

- **La serie pasa:** queda como está.
- **Una serie del total falla:** se oculta el pronóstico del modelo (O/U del
  total y su proyección) y en su lugar se muestra el **promedio histórico de
  la liga** de Over/Under de la línea central, con el bloque gris que ya
  existe (`promedio_liga` en `/partido`): misma liga, 365 días, partidos con
  los dos datos, mínimo 50, nada en copas, torneos internacionales ni
  amistosos. Ese mercado sale de Top Picks, value bets y análisis IA.
- **Una serie por equipo falla:** se oculta esa serie sin reemplazo (como
  corners por equipo).

Si todo falla, Top Picks queda con 1X2, doble oportunidad y handicaps. Se
avisa antes de implementar; no se implementa nada sin OK del usuario.

Si una serie que pasó falla después la confirmación con datos nuevos (mismo
C5), se oculta y se charla con el usuario.

## Bootstrap

2.000 remuestreos por bloques de semana ISO, percentiles 5 y 95, semilla
2026, mejora pareada por partido (`analizar.ic_bloques`).

## Informativo (no decide nada)

- Sesgo medio (proyección − real) y calibración por bandas de cada serie.
- Brier de todas las líneas contra R1, en particular las de Top Picks.
- Los 20 equipos de más volumen de tiros (definidos con ene-jun 2025, antes
  de la elección) contra el resto, y local contra visitante.
- Cuántas veces actúan los topes por equipo (por ejemplo 22 tiros totales).
- Ancho de la distribución (varianza/media implícita contra real): el *k*
  de atajadas es el de corners sin haberse medido.
- Si se mezcla más de un mes con cobertura de stats parcial, C5 por tramo de
  cobertura (hasta mar-2026 y desde abr-2026).

## Fuera de este pre-registro

- Arreglar el modelo de tiros o atajadas (estilo de juego, sesgo de los
  equipos de mucho volumen, *k* propio de atajadas): cada arreglo va con su
  propio pre-registro, después de esto.
- Handicaps y doble oportunidad (salen del 1X2, que ya pasó C1).
