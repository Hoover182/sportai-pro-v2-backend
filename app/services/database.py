import sqlite3
import pandas as pd
from datetime import datetime

HISTORIAL_DB = "historial_apuestas_futbol.db"
CACHE_DB     = "futbol_cache.db"


def _conectar(db):
    """Crea conexion con timeout y foreign keys activados."""
    conn = sqlite3.connect(db, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def iniciar_db():
    """Crea las tablas si no existen y agrega indices para consultas rapidas."""
    try:
        conn = _conectar(HISTORIAL_DB)
        cursor = conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS apuestas_futbol (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            partido      TEXT    NOT NULL,
            mercado      TEXT    NOT NULL,
            linea        REAL,
            probabilidad REAL,
            cuota        REAL,
            value        REAL,
            resultado    TEXT    DEFAULT 'PENDIENTE',
            fecha        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS predicciones_futbol (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha               TEXT    NOT NULL,
            liga                TEXT,
            partido             TEXT    NOT NULL,
            mercado1            TEXT,
            prob1               REAL,
            mercado2            TEXT,
            prob2               REAL,
            mercado3            TEXT,
            prob3               REAL,
            marcador_proyectado TEXT,
            goles_totales       REAL,
            corners_totales     REAL,
            tarjetas_totales    REAL,
            creado_en           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # Indices para consultas rapidas
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_pred_fecha ON predicciones_futbol(fecha)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_pred_liga  ON predicciones_futbol(liga)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_apuesta_fecha ON apuestas_futbol(fecha)")

        conn.commit()
        conn.close()
    except sqlite3.Error as e:
        print(f"⚠️ Error iniciando base de datos: {e}")


def guardar_apuesta(partido, mercado, linea, probabilidad, cuota, value):
    """Guarda una apuesta manual en el historial."""
    try:
        conn = _conectar(HISTORIAL_DB)
        conn.execute("""
            INSERT INTO apuestas_futbol (partido, mercado, linea, probabilidad, cuota, value)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (partido, mercado, float(linea or 0), float(probabilidad or 0),
              float(cuota or 0), float(value or 0)))
        conn.commit()
        conn.close()
        print("💾 Apuesta guardada correctamente")
    except sqlite3.Error as e:
        print(f"⚠️ Error guardando apuesta: {e}")


def guardar_prediccion(
    fecha, liga, partido,
    mercado1, prob1,
    mercado2="", prob2=0,
    mercado3="", prob3=0,
    marcador_proyectado="",
    goles_totales=0,
    corners_totales=0,
    tarjetas_totales=0
):
    """
    Guarda una prediccion automatica.
    Evita duplicados del mismo partido en el mismo dia.
    """
    try:
        conn = _conectar(HISTORIAL_DB)

        # Evitar duplicados — si ya existe el partido hoy no volver a guardar
        existe = conn.execute("""
            SELECT id FROM predicciones_futbol
            WHERE fecha = ? AND partido = ?
            LIMIT 1
        """, (fecha, partido)).fetchone()

        if not existe:
            conn.execute("""
                INSERT INTO predicciones_futbol (
                    fecha, liga, partido,
                    mercado1, prob1,
                    mercado2, prob2,
                    mercado3, prob3,
                    marcador_proyectado,
                    goles_totales, corners_totales, tarjetas_totales
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(fecha), str(liga or ""), str(partido),
                str(mercado1 or ""), float(prob1 or 0),
                str(mercado2 or ""), float(prob2 or 0),
                str(mercado3 or ""), float(prob3 or 0),
                str(marcador_proyectado or ""),
                float(goles_totales or 0),
                float(corners_totales or 0),
                float(tarjetas_totales or 0)
            ))
            conn.commit()

        conn.close()
    except sqlite3.Error as e:
        print(f"⚠️ Error guardando prediccion: {e}")
    except Exception as e:
        print(f"⚠️ Error inesperado en guardar_prediccion: {e}")


def ver_historial(limite=50):
    """Muestra el historial de apuestas manuales."""
    try:
        conn = _conectar(HISTORIAL_DB)
        df = pd.read_sql_query(f"""
            SELECT fecha, partido, mercado, linea, probabilidad, cuota, value, resultado
            FROM apuestas_futbol
            ORDER BY id DESC
            LIMIT {limite}
        """, conn)
        conn.close()

        if df.empty:
            print("\n  No hay apuestas registradas.")
            return

        print(f"\n📚 HISTORIAL DE APUESTAS FUTBOL (ultimas {limite})\n")
        for _, row in df.iterrows():
            value_str = f"{float(row['value'])*100:.1f}%" if row['value'] else "N/A"
            prob_str  = f"{float(row['probabilidad'])*100:.1f}%" if row['probabilidad'] else "N/A"
            print(f"  {row['fecha'][:10]} | {row['partido']}")
            print(f"  → {row['mercado']} | Prob: {prob_str} | Cuota: {row['cuota']} | Value: {value_str} | {row['resultado']}")
            print()

    except sqlite3.Error as e:
        print(f"⚠️ Error leyendo historial: {e}")


def ver_historial_predicciones(limite=30):
    """Muestra el historial de predicciones automaticas."""
    try:
        conn = _conectar(HISTORIAL_DB)
        df = pd.read_sql_query(f"""
            SELECT fecha, liga, partido,
                   mercado1, prob1,
                   mercado2, prob2,
                   mercado3, prob3,
                   marcador_proyectado
            FROM predicciones_futbol
            ORDER BY id DESC
            LIMIT {limite}
        """, conn)
        conn.close()

        if df.empty:
            print("\n  No hay predicciones guardadas.")
            return

        print(f"\n🧠 HISTORIAL DE PREDICCIONES (ultimas {limite})\n")
        liga_actual = ""
        for _, row in df.iterrows():
            if row["liga"] != liga_actual:
                liga_actual = row["liga"]
                print(f"\n🏆 {liga_actual}")
                print("-" * 50)
            print(f"  📅 {row['fecha']} | {row['partido']}")
            if row['mercado1']:
                print(f"  → {row['mercado1']}: {float(row['prob1'])*100:.1f}%")
            if row['mercado2']:
                print(f"  → {row['mercado2']}: {float(row['prob2'])*100:.1f}%")
            if row['mercado3']:
                print(f"  → {row['mercado3']}: {float(row['prob3'])*100:.1f}%")
            if row['marcador_proyectado']:
                print(f"  Marcador proyectado: {row['marcador_proyectado']}")
            print()

    except sqlite3.Error as e:
        print(f"⚠️ Error leyendo predicciones: {e}")


def iniciar_fifa_ranking():
    """Crea la tabla de ranking FIFA si no existe."""
    with _conectar("analista_futbol.db") as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS fifa_ranking (
                equipo      TEXT PRIMARY KEY,
                puntos      INTEGER,
                posicion    INTEGER,
                actualizado TEXT
            )
        """)
        con.commit()

def guardar_fifa_ranking(rankings):
    """
    Guarda o actualiza el ranking FIFA.
    rankings: lista de dicts {equipo, puntos, posicion}
    """
    from datetime import datetime
    hoy = datetime.now().strftime("%Y-%m-%d")
    with _conectar("analista_futbol.db") as con:
        for r in rankings:
            con.execute("""
                INSERT INTO fifa_ranking (equipo, puntos, posicion, actualizado)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(equipo) DO UPDATE SET
                    puntos=excluded.puntos,
                    posicion=excluded.posicion,
                    actualizado=excluded.actualizado
            """, (r["equipo"], r["puntos"], r["posicion"], hoy))
        con.commit()
    print(f"  Ranking FIFA actualizado: {len(rankings)} selecciones guardadas.")

def leer_fifa_ranking():
    """Retorna dict {equipo: puntos} con el ranking FIFA completo."""
    try:
        with _conectar("analista_futbol.db") as con:
            rows = con.execute("SELECT equipo, puntos FROM fifa_ranking ORDER BY posicion").fetchall()
            return {r[0]: r[1] for r in rows}
    except Exception:
        return {}

def iniciar_cache():
    """Inicializa la DB de cache para datos de la API."""
    try:
        conn = _conectar(CACHE_DB)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS partidos_cache (
                clave      TEXT PRIMARY KEY,
                data       TEXT NOT NULL,
                creado_en  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Limpiar cache viejo de mas de 24 horas
        conn.execute("""
            DELETE FROM partidos_cache
            WHERE creado_en < datetime('now', '-24 hours')
        """)
        conn.commit()
        conn.close()
    except sqlite3.Error as e:
        print(f"⚠️ Error iniciando cache: {e}")


def guardar_cache(clave, data):
    """Guarda un dato en cache."""
    try:
        conn = _conectar(CACHE_DB)
        conn.execute("""
            INSERT OR REPLACE INTO partidos_cache (clave, data)
            VALUES (?, ?)
        """, (str(clave), str(data)))
        conn.commit()
        conn.close()
    except sqlite3.Error:
        pass


def leer_cache(clave):
    """Lee un dato del cache. Retorna None si no existe."""
    try:
        conn = _conectar(CACHE_DB)
        row = conn.execute("""
            SELECT data FROM partidos_cache
            WHERE clave = ?
            AND creado_en > datetime('now', '-6 hours')
        """, (str(clave),)).fetchone()
        conn.close()
        return row[0] if row else None
    except sqlite3.Error:
        return None
