"""Veredicto de auto-merge del sync (scripts/veredicto_sync.py, modo
observacion): cada criterio por separado, con datos sinteticos. No toca
la red ni el CSV real.
Correr desde backend/: python -m unittest discover -s tests -v"""
import os
import sys
import unittest

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import veredicto_sync as V

AHORA = pd.Timestamp("2026-09-26T16:00:00Z")
META_AYER = {"datos_actualizados_en": "2026-09-25T16:00:00Z"}
DATOS = ["app/services/futbol_partidos.csv", "app/services/datos_meta.json"]
HUMO_OK = (True, "HUMO OK")


def fila(fid, fecha, estado="FT", liga="Liga Colombia", local="Chico", visitante="Deportivo Pasto", gl=1, gv=0, corners=5.0):
    return {"fixture_id": float(fid), "fecha": fecha, "estado": estado, "liga": liga,
            "equipo_local": local, "equipo_visitante": visitante,
            "goles_local": gl, "goles_visitante": gv, "corners_local": corners}


def base():
    return pd.DataFrame([
        fila(1, "2026-08-01T20:00:00"),                                             # vieja (>7 dias)
        fila(2, "2026-09-24T20:00:00", local="Once Caldas", visitante="Bucaramanga"),  # reciente
        fila(3, "2026-09-27T20:00:00", estado="NS", gl=None, gv=None, corners=None),   # proxima
    ])


class Veredicto(unittest.TestCase):
    def evaluar(self, despues, antes=None, ids=({"Chico": 1}, {"Chico": 1}), cuotas=({"1": {}}, {"1": {}}),
                meta=META_AYER, humo=HUMO_OK, archivos=DATOS):
        antes = base() if antes is None else antes
        return V.evaluar(antes, despues, ids[0], ids[1], cuotas[0], cuotas[1], meta, AHORA,
                         humo=humo, archivos_cambiados=archivos)

    def assertManual(self, v, fragmento):
        self.assertFalse(v["auto_merge"], v)
        self.assertTrue(any(fragmento in f for f in v["fallos"]), v["fallos"])

    # --- caso limpio ---
    def test_sync_normal_se_auto_mergea(self):
        d = base()
        d.loc[2, ["estado", "goles_local", "goles_visitante"]] = ["FT", 2, 1]   # se jugo la proxima
        d = pd.concat([d, pd.DataFrame([fila(4, "2026-09-30T20:00:00", estado="NS", gl=None, gv=None)])])
        v = self.evaluar(d)
        self.assertTrue(v["auto_merge"], v["fallos"])
        self.assertEqual((v["metricas"]["filas_nuevas"], v["metricas"]["filas_actualizadas"]), (1, 1))

    def test_enteros_leidos_como_float_no_son_cambio(self):
        # main sin NaN en la columna (se lee int: "1"); la rama con un NaN en
        # otra fila (se lee float: "1.0") -> no es un cambio real
        a = base().iloc[:2].astype({"goles_local": "int64"})
        d = pd.concat([a.astype({"goles_local": "float64"}),
                       pd.DataFrame([fila(4, "2026-09-30T20:00:00", estado="NS", gl=None, gv=None)])])
        self.assertEqual(str(a["goles_local"].iloc[0]), "1")
        self.assertEqual(str(d["goles_local"].iloc[0]), "1.0")
        self.assertEqual(self.evaluar(d, antes=a)["metricas"]["filas_actualizadas"], 0)

    # --- F. solo archivos de datos ---
    def test_codigo_en_el_diff_bloquea(self):
        self.assertManual(self.evaluar(base(), archivos=DATOS + ["scripts/check_sync.py"]), "no son datos del sync")

    def test_workflow_en_el_diff_bloquea(self):
        self.assertManual(self.evaluar(base(), archivos=[".github/workflows/sync-check.yml"]), "no son datos del sync")

    def test_json_que_no_es_del_sync_bloquea(self):
        # la lista es exacta: un .json cualquiera no alcanza
        self.assertManual(self.evaluar(base(), archivos=["app/services/ligas_auto_detectadas.json"]), "no son datos del sync")

    def test_sin_lista_de_archivos_bloquea(self):
        self.assertManual(self.evaluar(base(), archivos=None), "lista de archivos")

    # --- A. integridad ---
    def test_celda_vaciada_bloquea(self):
        d = base()
        d.loc[0, "corners_local"] = None
        self.assertManual(self.evaluar(d), "quedan vacias")

    def test_fila_perdida_bloquea(self):
        self.assertManual(self.evaluar(base().iloc[1:]), "desaparecen")

    def test_columna_agregada_bloquea(self):
        d = base()
        d["goles_90_local"] = None
        self.assertManual(self.evaluar(d), "Cambio de estructura")

    def test_columna_quitada_bloquea(self):
        self.assertManual(self.evaluar(base().drop(columns=["corners_local"])), "Cambio de estructura")

    def test_finalizado_que_vuelve_a_ns_bloquea(self):
        d = base()
        d.loc[1, "estado"] = "NS"
        self.assertManual(self.evaluar(d), "vuelven a un estado no final")

    def test_goles_de_partido_viejo_cambian_bloquea(self):
        d = base()
        d.loc[0, "goles_local"] = 3
        self.assertManual(self.evaluar(d), "hace mas de 7 dias")

    def test_goles_de_partido_reciente_pueden_corregirse(self):
        d = base()
        d.loc[1, "goles_local"] = 3
        self.assertTrue(self.evaluar(d)["auto_merge"])

    def test_humo_fallido_bloquea(self):
        self.assertManual(self.evaluar(base(), humo=(False, "cargar_df() devolvio 0 filas")), "Prueba de humo fallo")

    def test_sin_humo_bloquea(self):
        self.assertManual(self.evaluar(base(), humo=None), "No se corrio la prueba de humo")

    # --- B. volumen ---
    def _con_nuevas(self, n):
        extra = [fila(1000 + i, "2026-09-28T20:00:00", estado="NS", local=f"Equipo {i}", gl=None, gv=None) for i in range(n)]
        return pd.concat([base(), pd.DataFrame(extra)])

    def test_volumen_en_el_tope_pasa(self):
        self.assertTrue(self.evaluar(self._con_nuevas(V.TOPE_NUEVAS_BASE))["auto_merge"])

    def test_volumen_sobre_el_tope_bloquea(self):
        self.assertManual(self.evaluar(self._con_nuevas(V.TOPE_NUEVAS_BASE + 1)), "Volumen anomalo")

    def test_tope_escala_con_los_dias(self):
        # 5 dias sin sync: tope max(600, 200*5) = 1000
        meta = {"datos_actualizados_en": "2026-09-21T16:00:00Z"}
        self.assertTrue(self.evaluar(self._con_nuevas(1000), meta=meta)["auto_merge"])
        self.assertManual(self.evaluar(self._con_nuevas(1001), meta=meta), "Volumen anomalo")

    def test_filas_sin_fixture_id_no_cuentan_como_nuevas(self):
        a = pd.concat([base(), pd.DataFrame([fila(9, "2025-03-29T18:30:00")]).assign(fixture_id=None)])
        v = self.evaluar(a.copy(), antes=a)
        self.assertEqual(v["metricas"]["filas_nuevas"], 0)
        self.assertTrue(v["auto_merge"], v["fallos"])

    def test_aumentan_filas_sin_fixture_id_bloquea(self):
        d = pd.concat([base(), pd.DataFrame([fila(9, "2026-09-25T18:30:00")]).assign(fixture_id=None)])
        self.assertManual(self.evaluar(d), "sin fixture_id")

    # --- C. alertas que empeoran ---
    def test_liga_ambigua_nueva_bloquea(self):
        d = pd.concat([base(), pd.DataFrame([fila(5, "2026-09-28T20:00:00", estado="NS", liga="Serie A Brasil")])])
        self.assertManual(self.evaluar(d), "nombre ambiguo")

    def test_liga_ambigua_que_main_ya_tenia_no_bloquea(self):
        a = pd.concat([base(), pd.DataFrame([fila(5, "2026-09-20T20:00:00", liga="Copa Venezuela")])])
        d = pd.concat([a, pd.DataFrame([fila(6, "2026-09-28T20:00:00", estado="NS", liga="Copa Venezuela")])])
        self.assertTrue(self.evaluar(d, antes=a)["auto_merge"])

    def test_partido_duplicado_nuevo_bloquea(self):
        # mismo partido con otro fixture_id (caso real: Venezuela 16/09 en el PR #41)
        dup = base().iloc[[1]].assign(fixture_id=77.0)
        self.assertManual(self.evaluar(pd.concat([base(), dup])), "duplicados con fixture_id distinto")

    def test_encoding_roto_nuevo_bloquea(self):
        d = pd.concat([base(), pd.DataFrame([fila(5, "2026-09-28T20:00:00", estado="NS", local="AtlÃ©tico")])])
        self.assertManual(self.evaluar(d), "Encoding roto")

    def test_fila_nueva_en_el_futuro_lejano_bloquea(self):
        d = pd.concat([base(), pd.DataFrame([fila(5, "2028-01-01T20:00:00", estado="NS")])])
        self.assertManual(self.evaluar(d), "fila(s) nueva(s)")

    def test_historial_de_equipos_conocidos_se_acepta(self):
        d = pd.concat([base(), pd.DataFrame([fila(5, "2019-05-01T20:00:00")])])   # Chico-Pasto 2019
        v = self.evaluar(d)
        self.assertTrue(v["auto_merge"], v["fallos"])
        self.assertEqual(v["metricas"]["filas_nuevas_historial_aceptadas"], 1)

    def test_historial_con_equipo_desconocido_bloquea(self):
        d = pd.concat([base(), pd.DataFrame([fila(5, "2019-05-01T20:00:00", visitante="Cerro")])])
        self.assertManual(self.evaluar(d), "fila(s) nueva(s)")

    def test_historial_con_liga_desconocida_bloquea(self):
        d = pd.concat([base(), pd.DataFrame([fila(5, "2019-05-01T20:00:00", liga="Primera B")])])
        self.assertManual(self.evaluar(d), "fila(s) nueva(s)")

    def test_historial_no_finalizado_bloquea(self):
        d = pd.concat([base(), pd.DataFrame([fila(5, "2019-05-01T20:00:00", estado="NS")])])
        self.assertManual(self.evaluar(d), "fila(s) nueva(s)")

    # --- D. caches ---
    def test_team_id_cambiado_bloquea(self):
        self.assertManual(self.evaluar(base(), ids=({"Chico": 1}, {"Chico": 2})), "team_id cambiado")

    def test_team_id_nuevo_no_bloquea(self):
        self.assertTrue(self.evaluar(base(), ids=({"Chico": 1}, {"Chico": 1, "Pasto": 3}))["auto_merge"])

    def test_cuotas_vacias_bloquea(self):
        self.assertManual(self.evaluar(base(), cuotas=({"1": {}}, {})), "cuotas_cache.json queda vacio")

    # --- comentario ---
    def test_comentario_dice_modo_observacion_y_motivos(self):
        v = self.evaluar(base(), archivos=["scripts/x.py"])
        c = V.armar_comentario(v)
        self.assertIn("MODO OBSERVACION", c)
        self.assertIn("NO se habria mergeado", c)
        self.assertIn("scripts/x.py", c)


if __name__ == "__main__":
    unittest.main()
