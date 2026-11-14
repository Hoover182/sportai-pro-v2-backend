# Pre-registro: backtest del modelo de fútbol (29/10/2026)

Congelado en este commit, ANTES de escribir el harness y de correr nada.
Diseño aprobado por el usuario el 29/10/2026. Nada de lo que sigue se ajusta
mirando resultados.

## Por qué

Antes de lanzar hace falta saber si el modelo base le gana a reglas simples.
Nunca se hizo un backtest del modelo entero. Lo que hay es parcial: el
tracking prospectivo del Top3 (18/09-11/10: promete 76,8%, acierta 74,7%;
X2 promete 68% y acierta 59%), el ajuste de liga (16/10, solo partidos
europeos) y el sesgo de tarjetas (25/09).

## Modelo evaluado

`futbol_service.simular()` de `main` en el commit donde se congela este
archivo, sin cambios: el mismo código que produce las probabilidades de la
app, **sin el ajuste de IA** (no es reproducible para partidos pasados) y
sin cuotas.

## Sin mirar el futuro (point-in-time)

Para cada partido, el modelo corre "como si fuera" 1 hora antes del inicio:

- Datos: solo filas con fecha anterior a ese momento. El partido evaluado
  entra como programado (NS, sin goles ni stats), igual que en producción.
- Hora actual congelada en ese momento: peso por antigüedad de los cruces,
  semilla del Monte Carlo (local|visitante|fecha), temporada y cualquier
  otro uso de la hora actual.
- Elo: el rating de cada equipo al último partido anterior, sacado de
  `elo_historico.csv` de analista-futbol (las mismas constantes que
  producción), en vez de la foto de hoy (`elo_ratings.json`).
- Ligas válidas y fuente de cruces: el mismo filtrado que `cargar_df()`,
  aplicado a los datos recortados.

Las tablas fijas (nivel de liga, países) se usan tal como están hoy. Es una
filtración menor y conocida: se ajustaron mirando la historia (ver "Tramos").

## Tramos

Varias piezas del modelo se ajustaron mirando la historia hasta octubre de
2026, así que no hay un período retrospectivo limpio.

1. **Retrospectivo (decide), parcialmente contaminado:** partidos con inicio
   entre el 01/01/2026 00:00 UTC y el 28/10/2026 23:59 UTC.
2. **Validación limpia (confirma):** partidos con inicio entre el 30/10/2026
   00:00 UTC y el 26/11/2026 23:59 UTC, con el **código congelado en este
   commit** (aunque después cambie `main`) y los datos disponibles al
   evaluar, recortados igual que arriba. Se evalúa cuando estén los
   resultados, alrededor del 28/11/2026.

## Partidos incluidos

- Estado FT, AET o PEN, en ligas válidas (`filtrar_ligas_validas`).
- **1X2, goles y ambos marcan se liquidan a los 90':** `goles_90_*` si
  existen. Si no existen, se usan los `goles_*` de los partidos FT, y los
  AET/PEN sin `goles_90` quedan afuera.
- Afuera: partidos donde algún equipo tiene menos de 5 partidos previos, o
  donde `simular()` devuelve None. Se informa cuántos son.

## Mercados y métricas

- **Principal, 1X2:** Brier de 3 resultados (suma de los 3 cuadrados, de 0 a
  2), log-loss y acierto (el resultado más probable).
- **Secundarios:** Over/Under 2.5 goles y ambos marcan: Brier, log-loss y
  acierto.
- **Solo informativo:** corners 9.5 y tarjetas 4.5, en los partidos con
  stats verificadas (el mismo filtro del tracking: total > 0 en corners;
  amarillas admiten 0 si hay corners).

## Referencias simples

- **R1, frecuencia de la liga:** porcentaje de local, empate y visitante de
  la misma liga en los 365 días anteriores al partido (resultado a 90'). Con
  menos de 50 partidos se usa el global de todas las ligas en esos 365
  días. Lo mismo para over 2.5 y ambos marcan.
- **R2, mejores puntos por partido (solo acierto 1X2):** gana el equipo con
  más puntos por partido (3/1/0, a 90') en sus últimos 10 partidos
  terminados de cualquier competición. Si empatan, el local.

## Criterios

Iguales en los dos tramos. La mejora se mide por partido, pareada:
métrica de la referencia − métrica del modelo.

- **C1, 1X2 (obligatorio para lanzar):** el Brier mejora contra R1 (límite
  inferior del intervalo bootstrap del 90% > 0) **y** el acierto es mayor o
  igual que el de R2.
- **C2, Over/Under 2.5:** el Brier mejora contra R1 (límite inferior del
  intervalo del 90% > 0).
- **C3, Ambos marcan:** igual que C2.
- **C4, probabilidades fuertes:** se juntan todas las probabilidades ≥ 70%
  que da el modelo en 1X2 (cada uno de los 3 resultados), Over/Under 2.5
  (los dos lados) y ambos marcan (sí y no). Diferencia = tasa real −
  probabilidad media. **No pasa** si el límite superior del intervalo del
  90% de esa diferencia es menor que −3 puntos (sobreconfianza demostrada
  de más de 3 puntos).

Decisión:

- Si falla C1 en el retrospectivo, no se lanza y se charla con el usuario.
- Si falla C2, C3 o C4, ese mercado (o las probabilidades fuertes) se marca
  o se esconde, a decidir con el usuario.
- Si el retrospectivo pasa y la validación limpia no, se charla con el
  usuario. Nada se decide automáticamente.

## Bootstrap

2.000 remuestreos por bloques de semana ISO (los partidos de la misma
semana no son independientes), percentiles 5 y 95, semilla 2026.

## Informativo (no decide nada)

- Desglose por tipo de competición: ligas, copas nacionales, copas
  internacionales, amistosos.
- Calibración por bandas de 10 puntos para 1X2, O/U 2.5 y ambos marcan.
- Doble oportunidad X2 (prob_empate + prob_visitante) por bandas, para ver
  si el problema del tracking aparece también acá.
- Log-loss de todos los mercados y comparación con R1.

## Fuera de alcance

La recalibración continua según los resultados reales queda para después de
este backtest, por decisión del usuario: si se mezcla ahora, no se distingue
si el modelo es bueno o si los ajustes tapan el problema.

## Enmienda 1 (29/10/2026, antes de ver cualquier resultado)

Al armar el harness apareció que el Elo de producción era una foto fija del
24/08 que nunca se actualizaba, y que `ligas_auto_detectadas.json` no se
sincronizaba. El usuario decidió arreglar los dos bugs en producción
(PR #98, merge 1dafd64) **antes** de evaluar, para que el backtest mida el
modelo que se va a lanzar.

- **Modelo evaluado:** `main` en a821c8f (incluye #98) en lugar de 86baf3f.
- **Elo:** el de cada fecha sale de `elo_ranking.calcular_elo`, la misma
  función que usa producción desde el arreglo, redondeado a 2 decimales como
  en producción. Reemplaza al `elo_historico.csv` de analista-futbol.
- **Ligas válidas:** las de la lista sincronizada (56 ligas auto-detectadas).
- Se mantiene **sin cambios** la fórmula del rating inicial (1500 para ligas
  sin tabla). Usar las tablas de nivel del 16/10 queda como cambio de modelo
  aparte, con su propio pre-registro.
- Ya había una corrida completa del tramo retrospectivo con el Elo viejo. Se
  descartó **sin analizarla**: no se calculó ninguna métrica sobre ella.
- Todo lo demás (tramos, criterios, referencias, bootstrap) no cambia.
