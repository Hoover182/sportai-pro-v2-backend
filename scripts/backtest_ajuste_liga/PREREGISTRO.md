# Pre-registro: ajuste de liga A + B (16/10/2026)

Congelado en este commit, ANTES de correr el backtest. Nada de lo que sigue se
ajusta mirando resultados.

## Tablas y defaults (app/services/liga_ranking.py)

- **A, ligas europeas** (`NIVEL_LIGA_UEFA`, 31 ligas = las 30 domésticas de las
  55 auto-detectadas + Úrvalsdeild Iceland): nivel = −103,435 + 42,620 · ln(coef),
  donde coef es el coeficiente UEFA por país de 5 temporadas, en el **ranking 2025**
  (fin de la temporada 2024/25, `crank2025.csv`, de kassiesa.net). El ranking 2025 no
  incluye ningún resultado de los partidos del backtest, que van desde 07/2025.
  - La recta se ajusta por mínimos cuadrados sobre las 9 anclas: Premier 100,
    La Liga 95, Bundesliga 90, Serie A 88, Ligue 1 82, Primeira 72, Eredivisie 68,
    Turquía 65 y Bélgica 62. Sus niveles no se tocan. RMSE 4,9.
  - Desvíos de la curva respecto de cada ancla: Inglaterra −1,1; España −4,6;
    Alemania −3,4; Italia +3,6; Francia −2,5; Portugal +0,6; Países Bajos +7,9;
    Turquía −7,2; Bélgica +6,8.
  - El nivel se acota a 0–100 y se redondea. De las 55 asociaciones, 17 quedan en 0 y 23 en 8 o menos
    (de Kazajistán para abajo: Lituania, Albania, Georgia, Andorra, Gibraltar…).
- **A, sin validar** (`NIVEL_LIGA_SIN_VALIDAR`, criterio editorial):
  - Primera Nacional Argentina 35
  - Liga de Expansión MX 35
  - 2. Lig Turquía 25
  - Primera C Argentina 10
  - "Segunda Liga Portugal" no aparece como liga válida en los datos, así que no
    entra. Las otras válidas sin nivel (Serie D Brasil, Division 1 Arabia,
    Segunda Uruguay/Perú, Liga Pro Serie B, Challenger Pro League, Nacional B
    Bolivia, Liga 3 Portugal) quedan fuera porque no estaban en el plan aprobado.
- **B.1, país**: `NIVEL_PAIS_UEFA` sale de la misma curva, con las 9 anclas en el
  nivel de su liga. `NIVEL_PAIS_AMERICA` usa el nivel de la primera división de la
  tabla.
  - El país lo da api-football (`/teams?league&season` de CL, EL, ECL,
    Libertadores y Sudamericana, temporadas 2025 y 2026): 432 equipos en
    `pais_equipos.json`.
- **B.2, default por confederación** (P25 de las asociaciones): UEFA 0, CONMEBOL
  43, CONCACAF 59.
  - Distribución real de los 72 equipos UEFA sin liga: 71 tienen país, y todos son
    de asociaciones fuera del top 10 (Estonia, Feroe, Islandia, Irlanda, Kosovo,
    Luxemburgo, Malta, Moldavia, Montenegro, Irlanda del Norte, Gales: 4 cada una).
    Solo Saburtalo usa el default.
  - El percentil no se ajusta: con un solo equipo afectado no hay con qué
    ajustarlo.
- **B.3**: en un partido que no es de copa internacional, el equipo sin referencia
  toma la liga del propio partido, si esa liga tiene nivel.
- **Ambos sin referencia**: queda neutro.
- La magnitud no cambia: /60, tope ±0,30.

## Backtest

- **Datos**: `an16.csv` (CSV de analista del 16/10,
  sha256 818554e5…2e8de8), con las 55 ligas auto-detectadas de analista
  (`auto_an.json`, sha256 6276ed78…965c). Para la variante de producción se usan
  las 19 del backend (`ligas_auto_detectadas.json`, sha256 171d71b0…351e).
- **Point-in-time**: para cada partido se usan las filas con fecha anterior, más la
  fila del propio partido marcada como NS. Se usa el cargador de producción
  (`cargar_partidos_csv` + `filtrar_ligas_validas`) y se resetean los caches de
  equipos en cada partido (`bt.py`).
- **Conjuntos**: partidos FT/AET/PEN desde el 2025-07-01.
  - Europa: CL, EL y ECL, 569 partidos.
  - Control: Libertadores, Sudamericana y copas domésticas, 1.796 partidos.
  - La comparación es pareada, solo sobre los partidos simulados en las 5
    variantes.
- **Variantes**:
  - prod: 19 ligas, A y B apagados.
  - 55: 55 ligas, A y B apagados.
  - 55A, 55B y 55AB: 55 ligas con A, con B y con ambos.
- **Métricas**:
  - log-loss y Brier del 1X2 a 90' (goles_90 si existe; si no, goles);
  - −log-verosimilitud Poisson de goles a 90';
  - −log-verosimilitud Poisson de corners, solo en partidos con corners
    cargados;
  - desvío del grupo "top-5 contra rival sin referencia": se define con las
    referencias de prod, es fijo para todas las variantes y se calcula como
    (dif real − dif esperada) desde el lado del top-5.
- **Intervalos**: bootstrap por bloques de mes, 2000 réplicas, semilla 20261016,
  percentiles 2,5–97,5.
- **Criterios de éxito** (conjunto Europa, A+B = 55AB contra prod):
  1. Log-loss: no cumple si el IC95 de Δ(55AB − prod) queda entero por encima
     de 0, es decir, si es peor con significancia.
  2. Desvío: el gap de 55AB tiene que ser menor que el de prod, y el extremo
     superior de su IC95 tiene que quedar por debajo del gap de prod medido en
     esta misma corrida. También se informa contra +1,57.
- **Control**: 55AB no puede ser peor que prod en log-loss con significancia
  (misma regla). Si lo es, se marca.
- **Sensibilidad**, solo descriptiva: 55A, 55B y 55AB con el ranking 2026
  (`crank2026.csv`).

## No regresión

1. `tests/test_ajuste_liga.py`: mismos factores en los 34×34 pares de la tabla
   editorial. La tabla tiene 34 ligas, no 37: el "37" del plan era un error de
   conteo.
2. Listado de todo equipo cuya referencia pase de un valor a otro (no de None a
   un valor). Tiene que dar 0, o cada caso justificado.
3. Código viejo contra nuevo en el mismo minuto, sobre los pronósticos activos:
   todo partido en el que ningún equipo cambia de referencia ni de nivel tiene
   que dar idéntico.
4. La suite completa en verde.
