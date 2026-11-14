# Pre-registro: corrección de tiros del equipo local (14/11/2026)

Congelado en este commit, ANTES de escribir el código de las variantes, de
medir nada en la elección y de correr. Diseño aprobado por el usuario el
14/11/2026, con dos decisiones: corrección **sumada** (número fijo de tiros,
no proporcional; lo proporcional y los equipos de mucho volumen quedan como
hipótesis aparte) y **un único b̂ global por serie**, no uno por liga (para no
sobreajustar con pocos partidos por liga). Nada de lo que sigue se ajusta
mirando resultados.

## Por qué

El backtest de tiros y atajadas (`PREREGISTRO_tiros_atajadas.md`,
resultados en `resultados_tiros.json`, ef93610) mostró en el informativo de la
**evaluación 2026** que el modelo actual se queda corto con el equipo local y
no con el visitante:

| Serie | Proyección media | Real medio | Real − proyección |
|---|---|---|---|
| Tiros totales local | 13,50 | 14,57 | +1,07 |
| Tiros al arco local | 4,65 | 4,98 | +0,33 |
| Tiros totales visitante | 11,80 | 11,67 | −0,12 |
| Tiros al arco visitante | 4,06 | 3,98 | −0,08 |

El diagnóstico del 17/10/2026 (tiros totales por equipo, ago-oct 2026) ya
había visto lo mismo (+1,0 en los locales).

**Lo que ya se vio de 2026, escrito antes de correr.** La hipótesis de este
pre-registro sale de esos números, que están dentro de la evaluación. Por eso:

1. **La magnitud de la corrección se mide solo con la elección (jul-dic
   2025)**, con una regla fija escrita acá. No se usa el +1,07 ni el +0,33 de
   2026 para nada: ni para elegir la magnitud ni como tope, ni para redondear.
2. La evaluación en 2026 **no es independiente** de la hipótesis (se eligió
   corregir el local porque en 2026 se vio el sesgo). Decisión del usuario
   (14/11/2026): se evalúa en 2026 igual, dejándolo escrito, como en corners.
   **La prueba limpia es la confirmación con datos nuevos de marzo.**
3. Las predicciones de jul-dic 2025 (`pred_ti_2025h2.csv`) ya existen (se
   corrieron para el backtest anterior), pero **no se calculó ni se miró el
   sesgo del local en la elección**: ese backtest solo usó resultados reales
   de 2025 para elegir la línea central, y todo el informativo es de 2026.
   El sesgo de 2025 se calcula recién después de congelar esto.

Lo que este pre-registro **no** toca: el sesgo de los 20 equipos de más
volumen (+1,9 en 2026), el estilo de juego y el *k* de la Gamma-Poisson. Son
otras hipótesis, con su propio pre-registro.

## Cómo es el modelo hoy

- Media de tiros del local = (tiros a favor del local en sus últimos 10
  partidos de local en la liga + tiros que concede el visitante en sus últimos
  10 de visitante) / 2, mezclada con cruces directos y, con pocos datos, con
  el promedio de la liga (que es local y visitante promediados, sin
  localía).
- Topes por equipo: tiros al arco 1,5 a 9; tiros totales 5 a 22.
- Muestreo Gamma-Poisson independiente por equipo. Total del partido = suma
  de los dos.

## Modelo de referencia

El de producción: `main` en 4ce424d (el #126 solo oculta salidas; `simular`,
`football_model` y `simulator` no cambiaron desde eea826c). Harness
`harness_tiros.py` con un parámetro nuevo para la corrección. **Antes de
correr se verifica:**

1. con corrección 0, el harness da exactamente lo mismo que `main` sin
   parches en proyecciones y Over de todas las líneas de tiros, en al menos 30
   partidos (modo `--verificar`); y
2. con corrección 0, reproduce exactamente `pred_ti_2025h2.csv` y
   `pred_ti_2026a/b.csv` en las columnas de tiros (muestra de 200 partidos de
   cada uno); y
3. con una corrección distinta de 0, las series del visitante no cambian (ni
   proyección ni Over).

Si algo no da, se arregla y se anota como enmienda antes de correr.

## Hipótesis y candidatos

**H-L.** A la media de tiros del **equipo local**, después de
`ajustar_medias_con_rival` y antes de los topes y del muestreo, se le suma

    c · b̂_serie,   c ∈ {0; 0,5; 1}

por separado para tiros al arco (b̂_arco) y tiros totales (b̂_tiros). Los
topes siguen igual. El visitante no se toca. Las atajadas no se tocan (tienen
su propia media, no salen de los tiros).

**b̂ se mide en la elección (jul-dic 2025) con esta regla, y solo esta:**

- b̂_serie = media de (real − proyección) del local en la serie, con el
  modelo actual, en los partidos de la elección que cumplen los filtros de
  abajo. Redondeo a 2 decimales.
- IC90 de b̂ por bootstrap (mismo método de abajo). **Si el IC90 incluye 0, o
  b̂ < 0, esa serie no tiene corrección:** se anota y no entra nada para esa
  serie.

## Datos

- **CSV:** el mismo del backtest anterior, `datos_tiros_eea826c.csv`
  (SHA-256 4b6b315f0facfa6e...). Así 2026 se compara partido por partido con
  lo ya corrido.
- **Filtros:** los mismos de `PREREGISTRO_tiros_atajadas.md` (stats
  verificadas, los dos datos de la serie, 5 o más previos por equipo, 3+
  partidos con stats en 12 meses por equipo, el modelo devuelve la serie).
- **Elección:** julio a diciembre de 2025 (~2.800 partidos).
- **Evaluación:** 01/01 al 28/10/2026 (~6.150 partidos). Ya visto el sesgo
  agregado (ver arriba).
- **Confirmación con datos nuevos:** 07/11/2026 al 06/03/2027, en la misma
  corrida única de `PREREGISTRO_capa_liga.md` (después del 08/03/2027).

## Elección de *c* (julio a diciembre de 2025)

Por serie (L-arco y L-tiros, cada una sola): el *c* con menor Brier de Over de
la **línea central** del local (4.5 tiros al arco; 13.5 tiros totales, las de
`resultados_tiros.json`) en la elección, entre {0; 0,5; 1}. Redondeo a 4
decimales; si empatan, el *c* más chico (el más cercano al actual).

b̂ y *c* salen de los mismos datos de la elección; se acepta así (es la
elección), y la evaluación decide.

## Criterios (evaluación 2026)

### 1. ¿Entra la corrección? (por serie)

Si la elección deja *c* = 0 (o no hay b̂), esa serie no cambia.

Si no, la corrección de esa serie entra si, con el *c* elegido, el Brier de
Over de la línea central del local **mejora contra el modelo actual** (límite
inferior del IC90 de la mejora > 0).

### 2. Series por equipo del local (con la corrección que haya entrado)

L-arco y L-tiros hoy se muestran porque pasaron. Con la corrección tienen que
seguir pasando, con las mismas definiciones del backtest anterior:

- **C5:** Brier de Over de la línea central mejora contra R1 del local (tasa
  de Over del local en la liga, 365 días anteriores, mínimo 50, si no la
  global), límite inferior del IC90 > 0.
- **C4:** probabilidades ≥ 70% de Over y Under de la línea central juntas:
  límite superior del IC90 de "real − prometido" ≥ −3 pt.

### 3. Totales del partido (T-arco y T-tiros, hoy ocultos)

La corrección del local también mueve el total. Con la corrección de la serie
correspondiente (T-arco usa la de tiros al arco; T-tiros la de tiros
totales), mismas definiciones que antes:

- **C5:** Brier de Over de la línea central (8.5 tiros al arco; 24.5 tiros
  totales) contra R1, límite inferior del IC90 > 0.
- **C4:** probabilidades ≥ 70% de Over y Under de la línea central **y de las
  dos líneas de Top Picks** (6.5 y 7.5 tiros al arco; 23.5 y 24.5 tiros
  totales), juntas: límite superior del IC90 ≥ −3 pt.

Si la corrección de esa serie no entró (punto 1), el total no se vuelve a
evaluar: sigue oculto.

Si una serie no tiene ningún pronóstico ≥ 70% en las líneas de C4, C4 se da
por cumplido y se anota.

## Qué pasa según el resultado

| Resultado | Qué se hace |
|---|---|
| La corrección no entra en ninguna serie | Nada cambia. |
| Entra y las series del local siguen pasando C5 y C4 | Se aplica la corrección en producción. |
| Entra pero una serie del local deja de pasar C5 o C4 | No se aplica esa corrección; se charla con el usuario. |
| Entra y además el total pasa C5 y C4 | Se propone volver a mostrar ese total (O/U y proyección, y que vuelva a Top Picks, value bets y análisis IA), en lugar del bloque gris del promedio de la liga. |
| Entra pero el total sigue fallando | El total sigue oculto con el promedio de la liga. |

Nada se implementa sin OK del usuario. Si algo que entró falla en la
confirmación con datos nuevos (mismo criterio que lo hizo entrar), se vuelve
atrás y se charla con el usuario.

## Bootstrap

2.000 remuestreos por bloques de semana ISO, percentiles 5 y 95, semilla
2026, mejora pareada por partido (`analizar.ic_bloques`). Lo mismo para el IC90
de b̂.

## Informativo (no decide nada)

- b̂ del visitante en la elección (no se corrige; solo para ver si el sesgo es
  de localía o general).
- Sesgo medio y calibración por bandas de cada serie con cada *c*, en
  elección y evaluación.
- Las otras líneas del local y del total (Brier contra el modelo actual y
  contra R1).
- C5 por tramo de cobertura (hasta mar-2026 y desde abr-2026).
- Los 20 equipos de más volumen (la misma definición de ene-jun 2025) contra
  el resto: cuánto del sesgo queda después de la corrección.
- Cuántas veces actúa el tope de 22 tiros totales y el de 9 al arco con la
  corrección.

## Fuera de este pre-registro

- Sesgo de los equipos de mucho volumen (+1,9): otra hipótesis.
- Estilo de juego (posesión del rival): pendiente de decidir si se recupera la
  posesión de jul-2025 a jul-2026.
- Atajadas: siguen ocultas; no las toca esta corrección.
- Corrección por liga (un b̂ por liga): no; un único b̂ global por serie.
