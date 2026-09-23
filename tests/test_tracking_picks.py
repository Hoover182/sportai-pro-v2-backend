"""Picks registrados del tracking: armado de la respuesta (funciones puras)
y cache/lectura desde GitHub con la red simulada.
Correr desde backend/: python -m unittest discover -s tests -v"""
import os
import sys
import unittest
from datetime import datetime, timezone
from unittest import mock

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.services import tracking_picks as T

COLS_REG = ["fixture_id", "fecha_partido_utc", "liga", "local", "visitante", "registrado_en_utc",
            "posicion", "nombre_pick", "prob_pct", "cuota", "fuente_real", "commit_backend", "hash_csv"]
COLS_RES = ["fixture_id", "posicion", "mercado_id", "ambito", "lado", "linea", "resultado", "motivo",
            "valor_real", "estado_partido", "resuelto_en_utc", "hash_csv_resultado", "version_reglas"]
COLS_CONT = ["fixture_id", "posicion", "nombre_pick", "motivo", "anotado_en_utc"]
COLS_OMI = ["fixture_id", "fecha_partido_utc", "liga", "local", "visitante", "registrado_en_utc",
            "motivo", "commit_backend", "hash_csv"]

KICKOFF = "2026-09-18T23:30:00Z"
DT_KICKOFF = datetime(2026, 9, 18, 23, 30, tzinfo=timezone.utc)


def reg(fid, pos, nombre="Over 1.5 goles", prob="79.2", cuota="1.16", fuente="Betano", kickoff=KICKOFF):
    return dict(fixture_id=str(fid), fecha_partido_utc=kickoff, liga="MLS", local="NYCFC",
                visitante="NY Red Bulls", registrado_en_utc="2026-09-18T22:05:10Z", posicion=str(pos),
                nombre_pick=nombre, prob_pct=prob, cuota=cuota, fuente_real=fuente,
                commit_backend="f6d8616", hash_csv="a6be51c5fcd0")


def res(fid, pos, resultado="ACIERTO", motivo="", valor="2", mercado="goles_ou", ambito="total",
        lado="over", linea="1.5", estado="FT"):
    return dict(fixture_id=str(fid), posicion=str(pos), mercado_id=mercado, ambito=ambito, lado=lado,
                linea=linea, resultado=resultado, motivo=motivo, valor_real=valor, estado_partido=estado,
                resuelto_en_utc="2026-09-20T03:41:26Z", hash_csv_resultado="416a3a507068",
                version_reglas="v1-amarillas-goles90")


def df(filas, cols):
    return pd.DataFrame(filas, columns=cols)


def indice(registro=(), resultados=(), contaminados=(), omitidos=()):
    return T.construir_indice(
        df(list(registro), COLS_REG),
        df(list(resultados), COLS_RES),
        df([dict(fixture_id=str(f), posicion=str(p), nombre_pick="x", motivo="m", anotado_en_utc="t")
            for f, p in contaminados], COLS_CONT),
        df(list(omitidos), COLS_OMI),
    )


AHORA = datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc)


class ArmarRespuesta(unittest.TestCase):
    def test_registrado_mezcla_acierto_fallo_pendiente(self):
        idx = indice(
            [reg(1, 1), reg(1, 2, nombre="Under 2.5 tarjetas (NYCFC)", prob="77.9", cuota="", fuente=""),
             reg(1, 3, nombre="Gana local", prob="60.0")],
            [res(1, 1, "FALLO", valor="1"), res(1, 3, "ACIERTO", valor="2-1", mercado="resultado_local",
                                                ambito="", lado="", linea="")],
        )
        r = T.armar_picks_fixture(idx, 1, AHORA)
        self.assertEqual(r["estado_tracking"], "registrado")
        self.assertEqual((r["liga"], r["local"], r["visitante"]), ("MLS", "NYCFC", "NY Red Bulls"))
        self.assertEqual(r["fecha_partido_utc"], KICKOFF)
        self.assertEqual([p["posicion"] for p in r["picks"]], [1, 2, 3])
        p1, p2, p3 = r["picks"]
        self.assertEqual((p1["resultado"], p1["valor_real"], p1["prob_pct"], p1["cuota"], p1["linea"]),
                         ("FALLO", "1", 79.2, 1.16, 1.5))
        self.assertEqual((p1["mercado_id"], p1["ambito"], p1["lado"], p1["estado_partido"]),
                         ("goles_ou", "total", "over", "FT"))
        self.assertIsNone(p1["pendiente_motivo"])
        self.assertEqual((p2["resultado"], p2["pendiente_motivo"]), ("PENDIENTE", "esperando_marcado"))
        self.assertIsNone(p2["cuota"])
        self.assertIsNone(p2["fuente_cuota"])
        self.assertIsNone(p2["mercado_id"])
        self.assertEqual(p2["margen_hasta_utc"], "2026-09-25T23:30:00Z")
        self.assertEqual((p3["valor_real"], p3["linea"], p3["lado"]), ("2-1", None, None))
        self.assertEqual(r["picks_excluidos"], 0)
        self.assertEqual(r["resumen"], {"aciertos": 1, "fallos": 1, "pendientes": 1, "no_evaluables": 0,
                                        "anulados": 0, "no_parseables": 0})

    def test_no_evaluable_y_anulado_traen_motivo_sin_valor(self):
        idx = indice([reg(1, 1), reg(1, 2)],
                     [res(1, 1, "NO_EVALUABLE", motivo="prorroga_stats", valor="", estado="AET"),
                      res(1, 2, "ANULADO", motivo="estado_CANC", valor="", estado="CANC")])
        p1, p2 = T.armar_picks_fixture(idx, 1, AHORA)["picks"]
        self.assertEqual((p1["resultado"], p1["motivo"], p1["valor_real"]), ("NO_EVALUABLE", "prorroga_stats", None))
        self.assertEqual((p2["resultado"], p2["motivo"]), ("ANULADO", "estado_CANC"))

    def test_contaminado_se_excluye_y_se_cuenta(self):
        idx = indice([reg(7, 1), reg(7, 2), reg(7, 3)],
                     [res(7, 1), res(7, 2, "FALLO"), res(7, 3, "FALLO")],
                     contaminados=[(7, 3)])
        r = T.armar_picks_fixture(idx, 7, AHORA)
        self.assertEqual([p["posicion"] for p in r["picks"]], [1, 2])
        self.assertEqual(r["picks_excluidos"], 1)
        self.assertEqual(r["resumen"]["fallos"], 1)   # el FALLO contaminado no cuenta

    def test_todos_contaminados_sigue_siendo_registrado(self):
        idx = indice([reg(7, 1), reg(7, 2)], contaminados=[(7, 1), (7, 2)])
        r = T.armar_picks_fixture(idx, 7, AHORA)
        self.assertEqual((r["estado_tracking"], r["picks"], r["picks_excluidos"]), ("registrado", [], 2))

    def test_contaminado_de_otro_fixture_no_afecta(self):
        idx = indice([reg(1, 1)], contaminados=[(2, 1)])
        self.assertEqual(T.armar_picks_fixture(idx, 1, AHORA)["picks_excluidos"], 0)

    def test_omitido(self):
        omi = dict(fixture_id="5", fecha_partido_utc=KICKOFF, liga="FA Cup", local="Redcar", visitante="Darlington",
                   registrado_en_utc="2026-09-18T22:05:10Z", motivo="sin_simulacion", commit_backend="c", hash_csv="h")
        r = T.armar_picks_fixture(indice(omitidos=[omi]), 5, AHORA)
        self.assertEqual((r["estado_tracking"], r["motivo_omision"], r["liga"]), ("omitido", "sin_simulacion", "FA Cup"))
        self.assertEqual(r["picks"], [])

    def test_omitido_varias_veces_vale_la_ultima(self):
        base = dict(fixture_id="5", fecha_partido_utc=KICKOFF, liga="L", local="A", visitante="B",
                    registrado_en_utc="t", commit_backend="c", hash_csv="h")
        idx = indice(omitidos=[{**base, "motivo": "sin_simulacion"},
                               {**base, "motivo": "error: ValueError: lam value too large"}])
        self.assertEqual(T.armar_picks_fixture(idx, 5, AHORA)["motivo_omision"],
                         "error: ValueError: lam value too large")

    def test_sin_registro(self):
        r = T.armar_picks_fixture(indice([reg(1, 1)]), 999, AHORA)
        self.assertEqual((r["estado_tracking"], r["picks"], r["picks_excluidos"]), ("sin_registro", [], 0))

    def test_indice_none_es_no_disponible_no_sin_registro(self):
        r = T.armar_picks_fixture(None, 1, AHORA)
        self.assertEqual(r["estado_tracking"], "tracking_no_disponible")
        self.assertEqual(r["picks"], [])

    def test_misma_forma_en_todos_los_estados(self):
        idx = indice([reg(1, 1)])
        claves = set(T.armar_picks_fixture(idx, 1, AHORA))
        for r in (T.armar_picks_fixture(idx, 2, AHORA), T.armar_picks_fixture(None, 1, AHORA)):
            self.assertEqual(set(r), claves)

    def test_pendiente_motivo_por_tiempo(self):
        idx = indice([reg(1, 1)])
        casos = [
            (datetime(2026, 9, 18, 23, 29, tzinfo=timezone.utc), "partido_no_jugado"),
            (DT_KICKOFF, "esperando_marcado"),
            (datetime(2026, 10, 10, 23, 29, tzinfo=timezone.utc), "esperando_marcado"),  # < kickoff + 22 d
            (datetime(2026, 10, 10, 23, 30, tzinfo=timezone.utc), "atrasado"),
        ]
        for ahora, esperado in casos:
            with self.subTest(ahora=ahora):
                self.assertEqual(T.armar_picks_fixture(idx, 1, ahora)["picks"][0]["pendiente_motivo"], esperado)

    def test_registro_desordenado_sale_por_posicion(self):
        idx = indice([reg(1, 3), reg(1, 1), reg(1, 2)])
        self.assertEqual([p["posicion"] for p in T.armar_picks_fixture(idx, 1, AHORA)["picks"]], [1, 2, 3])


class ValidacionIndice(unittest.TestCase):
    def test_registro_duplicado(self):
        with self.assertRaisesRegex(T.TrackingError, "registro: claves"):
            indice([reg(1, 1), reg(1, 1)])

    def test_resultado_duplicado(self):
        with self.assertRaisesRegex(T.TrackingError, "resultados: claves"):
            indice([reg(1, 1)], [res(1, 1), res(1, 1, "FALLO")])

    def test_resultado_huerfano(self):
        with self.assertRaisesRegex(T.TrackingError, "sin pick en el registro"):
            indice([reg(1, 1)], [res(1, 2)])

    def test_resultado_invalido(self):
        with self.assertRaisesRegex(T.TrackingError, "valor invalido"):
            indice([reg(1, 1)], [res(1, 1, "PUSH")])

    def test_resultados_vacio_sin_columnas_de_resultado(self):
        # Asi llega resultados.csv cuando todavia no existe en el repo (404).
        idx = T.construir_indice(df([reg(1, 1)], COLS_REG), pd.DataFrame(columns=["fixture_id", "posicion"]),
                                 pd.DataFrame(columns=["fixture_id", "posicion"]),
                                 pd.DataFrame(columns=["fixture_id", "posicion"]))
        self.assertEqual(T.armar_picks_fixture(idx, 1, AHORA)["picks"][0]["resultado"], "PENDIENTE")


def csv_de(filas, cols):
    return df(filas, cols).to_csv(index=False).encode("utf-8")


class RespuestaFalsa:
    def __init__(self, status=200, texto="", content=b"", etag=None):
        self.status_code, self.text, self.content = status, texto, content
        self.headers = {"ETag": etag} if etag else {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class GitHubFalso:
    """Simula la API: commits/main (sha + ETag, 304 si coincide) y contents?ref=sha."""

    def __init__(self):
        self.sha = "a" * 40
        self.archivos = {"a" * 40: {"registro": csv_de([reg(1, 1)], COLS_REG),
                                    "resultados": csv_de([res(1, 1)], COLS_RES)}}
        self.caido = False
        self.llamadas = []

    def get(self, url, headers=None, params=None, timeout=None):
        self.llamadas.append(url)
        if self.caido:
            raise ConnectionError("github caido")
        if url.endswith("/commits/main"):
            etag = f'"{self.sha}"'
            if headers.get("If-None-Match") == etag:
                return RespuestaFalsa(304)
            return RespuestaFalsa(200, texto=self.sha, etag=etag)
        clave = next(k for k, v in T.ARCHIVOS.items() if url.endswith(v))
        contenido = self.archivos[params["ref"]].get(clave)
        return RespuestaFalsa(404) if contenido is None else RespuestaFalsa(200, content=contenido)


class CacheGitHub(unittest.TestCase):
    def setUp(self):
        T._cache.update(indice=None, sha=None, etag=None, leido_en_utc=None, proximo_chequeo=0.0,
                        desactualizado=False)
        self.gh = GitHubFalso()
        self.reloj = [1000.0]
        self.parches = [
            mock.patch.object(T.requests, "get", self.gh.get),
            mock.patch.object(T.time, "monotonic", lambda: self.reloj[0]),
            mock.patch.dict(os.environ, {"TRACKING_REPO_TOKEN": "falso"}),
        ]
        for p in self.parches:
            p.start()

    def tearDown(self):
        for p in self.parches:
            p.stop()

    def test_sin_token_no_disponible_sin_llamar(self):
        with mock.patch.dict(os.environ, {"TRACKING_REPO_TOKEN": ""}):
            r = T.get_picks_registrados(1)
        self.assertEqual(r["estado_tracking"], "tracking_no_disponible")
        self.assertEqual(self.gh.llamadas, [])

    def test_primera_lectura_baja_los_4_archivos_del_mismo_commit(self):
        r = T.get_picks_registrados(1)
        self.assertEqual((r["estado_tracking"], r["picks"][0]["resultado"]), ("registrado", "ACIERTO"))
        self.assertEqual(r["fuente"]["commit_tracking"], "aaaaaaa")
        self.assertFalse(r["fuente"]["datos_desactualizados"])
        self.assertEqual(len(self.gh.llamadas), 5)   # sha + 4 CSV (2 dan 404 = vacios)

    def test_dentro_del_ttl_no_llama(self):
        T.get_picks_registrados(1)
        self.reloj[0] += T.TTL_SEGUNDOS - 1
        T.get_picks_registrados(1)
        self.assertEqual(len(self.gh.llamadas), 5)

    def test_vencido_sin_commit_nuevo_solo_chequea_sha(self):
        T.get_picks_registrados(1)
        self.reloj[0] += T.TTL_SEGUNDOS
        T.get_picks_registrados(1)
        self.assertEqual(len(self.gh.llamadas), 6)   # un 304, nada mas

    def test_commit_nuevo_recarga(self):
        T.get_picks_registrados(1)
        nuevo = "b" * 40
        self.gh.archivos[nuevo] = {"registro": csv_de([reg(1, 1)], COLS_REG),
                                   "resultados": csv_de([res(1, 1, "FALLO", valor="1")], COLS_RES)}
        self.gh.sha = nuevo
        self.reloj[0] += T.TTL_SEGUNDOS
        r = T.get_picks_registrados(1)
        self.assertEqual((r["picks"][0]["resultado"], r["fuente"]["commit_tracking"]), ("FALLO", "bbbbbbb"))

    def test_github_caido_sirve_el_ultimo_indice_marcado(self):
        T.get_picks_registrados(1)
        self.gh.caido = True
        self.reloj[0] += T.TTL_SEGUNDOS
        r = T.get_picks_registrados(1)
        self.assertEqual((r["estado_tracking"], r["picks"][0]["resultado"]), ("registrado", "ACIERTO"))
        self.assertTrue(r["fuente"]["datos_desactualizados"])
        # Se recupera en el proximo chequeo (tras REINTENTO_FALLO).
        self.gh.caido = False
        self.reloj[0] += T.REINTENTO_FALLO
        self.assertFalse(T.get_picks_registrados(1)["fuente"]["datos_desactualizados"])

    def test_github_caido_sin_cache_es_no_disponible_y_no_martilla(self):
        self.gh.caido = True
        self.assertEqual(T.get_picks_registrados(1)["estado_tracking"], "tracking_no_disponible")
        T.get_picks_registrados(1)
        self.assertEqual(len(self.gh.llamadas), 1)   # el 2do request no reintenta antes de REINTENTO_FALLO

    def test_datos_invalidos_en_commit_nuevo_conservan_el_indice_anterior(self):
        T.get_picks_registrados(1)
        roto = "c" * 40
        self.gh.archivos[roto] = {"registro": csv_de([reg(1, 1), reg(1, 1)], COLS_REG)}
        self.gh.sha = roto
        self.reloj[0] += T.TTL_SEGUNDOS
        r = T.get_picks_registrados(1)
        self.assertEqual((r["picks"][0]["resultado"], r["fuente"]["commit_tracking"]), ("ACIERTO", "aaaaaaa"))
        self.assertTrue(r["fuente"]["datos_desactualizados"])
        # Tras el fallo no se reusa el ETag del commit roto: se vuelve a intentar bajar.
        self.gh.archivos[roto] = {"registro": csv_de([reg(1, 1)], COLS_REG)}
        self.reloj[0] += T.REINTENTO_FALLO
        r = T.get_picks_registrados(1)
        self.assertEqual((r["fuente"]["commit_tracking"], r["picks"][0]["resultado"]), ("ccccccc", "PENDIENTE"))


if __name__ == "__main__":
    unittest.main()
