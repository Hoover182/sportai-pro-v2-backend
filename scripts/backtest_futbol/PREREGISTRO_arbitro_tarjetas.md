# Pre-registro: árbitro en tarjetas (09/11/2026)

Congelado en este commit, ANTES de escribir el código de las variantes y de
correr nada. Diseño aprobado por el usuario el 10/11/2026. Nada de lo que sigue
se ajusta mirando resultados.

## Por qué

Idea del usuario (06/11/2026): el árbitro como dato del pronóstico de
tarjetas. El modelo no lo usa (el comentario del multiplicador de tarjetas lo
nombra, el código no).

Hoy en producción (#112, 06/11/2026) el multiplicador de tarjetas va con
f = 0,5 y el O/U de tarjetas (total y por equipo) está **oculto**, porque en
la evaluación 2026 de `PREREGISTRO_multiplicador_tarjetas.md` falló C5: el
Brier de Over 4.5 dio 0,2380 contra 0,2320 de la tasa de la liga (R1).
Esta hipótesis es el camino para que tarjetas vuelva a mostrarse.

## Lo que ya se miró antes de escribir esto (sin resultados del modelo)

Con el CSV del sync #115 (ver Datos), solo descriptivos:

- **Cobertura.** Partidos jugados con stats que también tienen árbitro:
  99% en 2023-2025, 98% en jul-dic 2025 y 99% en 2026 (el backfill de
  analista #17 llenó el 83% de los jugados).
- **Antes del partido.** En los partidos programados del CSV, el árbitro
  está en ~63% de los del día siguiente y en ninguno a más de 2 días. En
  producción va a faltar en ~1 de cada 3 partidos del día.
- **Nombres.** Vienen mezclados ("S. Stegemann" / "Sascha Stegemann",
  "Kadir Saglam, Türkiye"). Con la clave inicial + último apellido quedan
  63 claves con más de un nombre de pila sobre 1.568, casi todas variantes
  del mismo ("andrew"/"andy", "a."/"angel"); hay choques reales del tipo
  "A. Gonzalez". Contar solo dentro de la misma liga los achica.
- **Tamaño del efecto, con datos ANTERIORES a julio de 2025** (13.307
  partidos, fuera de la elección y de la evaluación): la dispersión de las
  amarillas por árbitro, respecto de la media de la liga, supera a la del
  azar (permutando árbitros dentro de liga-año): desvío entre árbitros de
  **~10%**. La contracción óptima aproximada equivale a **~23 partidos** del
  árbitro.
- **Historia disponible.** Partidos previos del árbitro en la misma liga:
  mediana 17 en jul-dic 2025 y 14 en la evaluación 2026; 0 previos en 6% y
  16%; 25 o más en 34% y 37%.

**Expectativa, escrita antes de correr:** con ~10% de desvío y la historia
que hay, la mejora esperable en Brier de Over 4.5 es chica (del orden de
0,001). La distancia a R1 es 0,006. Es poco probable que alcance para
mostrar tarjetas de nuevo; se corre igual porque es barato y la respuesta
sirve.

## Modelo de referencia

El de producción para tarjetas: `main` en a821c8f con el multiplicador de
tarjetas en f = 0,5 (`FACTOR_MULTIPLICADOR_TARJETAS` de #112). Lo que cambió
en `main` después (sacar el multiplicador de goles, ocultar corners, chat) no
toca tarjetas. Antes de correr se verifica que el harness con f = 0,5 y sin
árbitro dé lo mismo que `main` actual en `tarjetas_totales_proj` y Over 4.5
en al menos 30 partidos.

## Hipótesis y candidatos

**H-R.** Multiplicar la proyección de tarjetas por un factor del árbitro:

    m_arb = (Σ y_i + k · μ̄) / (Σ μ_i + k · μ̄)

- *y_i*: amarillas totales de cada partido previo del árbitro.
- *μ_i*: media de amarillas totales de esa liga en los 365 días anteriores
  a ese partido (partidos con stats; con menos de 50, la media global de
  esos 365 días).
- *μ̄* = Σ μ_i / n: lleva *k* a unidades de partido.
- **Candidatos:** *k* ∈ {10; 25; 50} partidos, más "sin árbitro" (el actual,
  m_arb = 1).

Sin árbitro en la fila, o sin partidos previos en la liga, m_arb = 1.

**Historial del árbitro:** partidos de la misma clave en la misma liga
(nombre exacto), jugados, con stats (corners total > 0) y con las dos
columnas de amarillas, con fecha anterior al partido menos 1 hora
(point-in-time, igual que el harness).

**Clave del árbitro:** se saca lo que va después de la coma (país), se
quitan acentos, todo en minúsculas, se parte por espacios y puntos. Clave =
inicial del primer pedazo + último pedazo.

**Dónde se aplica:** sobre el multiplicador actual,

    multiplicador final = (1 + 0,5 · (m − 1)) · m_arb

en el mismo lugar del código (proyección total, la de cada equipo y nuevo
muestreo de todas las líneas, total y por equipo). Sin tope adicional. Todo
lo demás de tarjetas queda igual. No toca goles, corners, tiros ni 1X2.

## Datos

- **CSV:** `futbol_partidos.csv` de `main` en 6e660fe (merge del sync #115,
  10/11/2026; SHA-256 empieza con d8862ad91ffed996). Es el primero con los
  árbitros del backfill. Syncs posteriores no cambian este backtest.
- Mismos filtros de tarjetas que el pre-registro del multiplicador.
- **Elección:** julio a diciembre de 2025.
- **Evaluación:** los mismos meses de 2026 que el pre-registro del
  multiplicador: enero, febrero, junio, julio, agosto y 1-28 de octubre.
  Ahí se midió el C5 que falló. Marzo, abril, mayo y septiembre quedan
  afuera.
- **Confirmación con datos nuevos:** 07/11/2026 al 06/03/2027, en la corrida
  única de `PREREGISTRO_capa_liga.md` (después del 08/03/2027).

**Ojo:** en el backtest el árbitro viene del CSV (cargado después del
partido). La designación es previa al partido, así que no hay fuga del
resultado, pero la cobertura es mayor que la que hay en producción antes del
partido (ver "Si entra").

## Elección (julio a diciembre de 2025)

Se elige el candidato con menor Brier de Over 4.5 tarjetas (total del
partido) entre {sin árbitro; 10; 25; 50}. Redondeo a 4 decimales. Si
empatan, gana el más cercano al actual: "sin árbitro" primero, después el
*k* más grande.

## Criterio para que entre (evaluación 2026)

H-R entra si, con el *k* elegido contra el modelo actual (f = 0,5, sin
árbitro):

1. el Brier de Over 4.5 mejora (límite inferior del IC90 de la mejora > 0); y
2. Over 3.5 y Over 5.5 no empeoran de forma demostrada (límite superior del
   IC90 de la mejora ≥ 0 en cada una).

## Mercado de tarjetas contra la tasa de la liga

Solo si H-R entra. Se mide en los partidos de la evaluación que en
producción se mostrarían: los que tienen árbitro con al menos 1 partido
previo en la liga.

- **C5:** el Brier de Over 4.5 mejora contra R1 de tarjetas (la misma R1 del
  pre-registro del multiplicador), con límite inferior del IC90 > 0.
- **C4:** las probabilidades ≥ 70% de Over y Under 4.5 juntas no se pasan en
  más de 3 pt (límite superior del IC90 de "real − prometido" ≥ −3 pt).

## Si entra

- **Con C5 y C4:** se implementa y el O/U de tarjetas (total y por equipo)
  **se muestra solo en los partidos con árbitro conocido y con historial**.
  En los demás el pronóstico queda oculto y se muestra el bloque gris con el
  promedio de la liga de Over/Under 4.5 tarjetas (mismo patrón que corners y
  goles; decisión del usuario, 10/11/2026).
- **Con C5 o C4 fallando:** tarjetas sigue oculto y el ajuste **no se mete en
  el código**. Queda escrito y se revisa en la confirmación de marzo, junto
  con el filtro de recalibración (decisión del usuario, 10/11/2026).

Si después falla la confirmación con datos nuevos (mismo criterio 1), se
vuelve atrás y se charla con el usuario.

## Si no entra

No cambia nada. Tarjetas sigue oculto.

## Bootstrap

2.000 remuestreos por bloques de semana ISO, percentiles 5 y 95, semilla
2026, mejora pareada por partido (`analizar.ic_bloques`).

## Informativo (no decide nada)

- Distribución de m_arb (media, percentiles, extremos) con cada *k*.
- Mejora en Brier por tramo de historial del árbitro (0, 1-9, 10-24, 25+).
- Sesgo medio y calibración por bandas de Over 4.5.
- Las otras líneas del total (2.5 a 7.5) y las de cada equipo (0.5 a 3.5).
- C5 y C4 en todos los partidos de la evaluación (no solo los que se
  mostrarían).
- Variante con el historial del árbitro en **todas** las competiciones (no
  solo la misma liga), con el *k* elegido.
- Los árbitros fuertes suelen dirigir los partidos grandes, que ya traen más
  tarjetas por los equipos. Parte del efecto del árbitro puede estar ya en
  las medias de los equipos. Se reporta la correlación entre m_arb y la
  proyección sin árbitro.

## Fuera de este pre-registro

- Volver a elegir *f* del multiplicador: ya se decidió con su propio
  pre-registro y la evaluación 2026 ya se vio.
- Estilo de juego para tiros y backtest de tiros/atajadas: siguen en la
  cola, cada uno con su pre-registro.
