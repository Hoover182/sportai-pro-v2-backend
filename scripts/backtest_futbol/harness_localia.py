"""Harness de PREREGISTRO_tiros_localia.md (congelado 74e9dfa).

Es harness_tiros.py (point-in-time, main sin cambios en un worktree aparte)
con una sola diferencia: a la media de tiros del LOCAL que futbol_service.
simular() le pasa a simular_partido_futbol() (despues de
ajustar_medias_con_rival, antes de los topes y del muestreo) se le suma

    --suma-arco   (= c * b_arco)   a tiros al arco del local
    --suma-tiros  (= c * b_tiros)  a tiros totales del local

El visitante y todo lo demas quedan igual. Con las dos sumas en 0 el harness
es el de harness_tiros.py (sumar 0.0 no cambia nada).

Uso desde backend/ (este worktree), mismos argumentos que harness_tiros.py:
  python scripts/backtest_futbol/harness_localia.py --suma-arco 0.3 --suma-tiros 1.0 \
      --servicios RUTA_MAIN/app/services --csv datos_tiros_eea826c.csv \
      --desde 2025-07-01 --hasta 2025-12-31 --salida pred_loc_xxx.csv
  ... --verificar 30   (solo con las dos sumas en 0: contra main sin parches)
"""
import math
import os
import sys

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import harness as H  # noqa: E402
import harness_tiros as HT  # noqa: E402

# posiciones en simular_partido_futbol(goles_a, goles_b, std_a, std_b,
# corners_a, corners_b, tarjetas, tiros_arco_a, tiros_arco_b,
# tiros_total_a, tiros_total_b, ...)
POS_ARCO_LOCAL, POS_TIROS_LOCAL = 7, 9


def _valida(x):
    return x is not None and not (isinstance(x, float) and math.isnan(x))


def _sumas():
    return float(os.environ.get("SUMA_ARCO", "0")), float(os.environ.get("SUMA_TIROS", "0"))


_iniciar_original = HT._iniciar


# Enmienda 1 (PREREGISTRO_tiros_localia.md): np.random.poisson consume una
# cantidad de numeros aleatorios que depende de la media, asi que sumarle al
# local corria la secuencia y cambiaba el muestreo del visitante (que se
# muestrea despues, en el mismo bloque de tiros). Para que la unica diferencia
# sea la del local: en las dos llamadas del local (arco y totales) se guarda el
# estado, se muestrea con la media SIN corregir solo para saber en que estado
# queda la secuencia, se vuelve al estado guardado, se muestrea con la media
# corregida (mismos numeros de partida) y se deja la secuencia donde la habria
# dejado la media sin corregir. Con suma 0 da exactamente lo mismo.
# Las dos llamadas del local se reconocen por su LUGAR, no por el valor de la
# media (una media de corners puede coincidir con la de tiros, ej. 5,25): el
# bloque de tiros de simular_partido_futbol() empieza con el primer
# np.random.get_state() de la funcion y muestrea, en orden, arco local, arco
# visitante, totales local, totales visitante. Se cuenta desde ahi.
_PLAN = {"armado": False, "en_bloque": False, "i": 0, "esperado": {}}


class _RandomProxy:
    def __getattr__(self, nombre):
        if nombre == "get_state":
            def get_state(*a, **kw):
                if _PLAN["armado"] and not _PLAN["en_bloque"] and _PLAN["i"] == 0:
                    _PLAN["en_bloque"] = True
                return np.random.get_state(*a, **kw)
            return get_state
        return getattr(np.random, nombre)


class _NpProxy:
    random = _RandomProxy()

    def __getattr__(self, nombre):
        return getattr(np, nombre)


def _iniciar_con_localia():
    _iniciar_original()
    FS = H._G["FS"]
    SIM = sys.modules["simulator"]
    SIM.np = _NpProxy()
    orig = FS.simular_partido_futbol
    muestrear = SIM._muestrear_conteo
    s_arco, s_tiros = _sumas()

    def con_tope(x, lo, hi):
        return float(np.clip(x, lo, hi))

    def muestrear_cr(media, k, sims):
        if not _PLAN["en_bloque"]:
            return muestrear(media, k, sims)
        i = _PLAN["i"]
        _PLAN["i"] += 1
        if i == 3:
            _PLAN["en_bloque"], _PLAN["armado"] = False, False
        if i not in _PLAN["esperado"]:
            return muestrear(media, k, sims)
        corr, sin_corr = _PLAN["esperado"].pop(i)
        if media != corr:
            raise RuntimeError(f"enmienda 1: llamada {i} del bloque de tiros con media {media}, se esperaba {corr}")
        st0 = np.random.get_state()
        muestrear(sin_corr, k, sims)
        st1 = np.random.get_state()
        np.random.set_state(st0)
        out = muestrear(media, k, sims)
        np.random.set_state(st1)
        return out

    SIM._muestrear_conteo = muestrear_cr

    def spf(*a, **kw):
        a = list(a)
        _PLAN.update(armado=False, en_bloque=False, i=0, esperado={})
        if all(_valida(a[i]) for i in (7, 8, 9, 10)):
            arco0, tiros0 = a[POS_ARCO_LOCAL], a[POS_TIROS_LOCAL]
            a[POS_ARCO_LOCAL] = arco0 + s_arco
            a[POS_TIROS_LOCAL] = tiros0 + s_tiros
            _PLAN["esperado"] = {
                0: (con_tope(a[POS_ARCO_LOCAL], SIM.TIROS_ARCO_MIN, SIM.TIROS_ARCO_MAX),
                    con_tope(arco0, SIM.TIROS_ARCO_MIN, SIM.TIROS_ARCO_MAX)),
                2: (con_tope(a[POS_TIROS_LOCAL], SIM.TIROS_TOTAL_MIN, SIM.TIROS_TOTAL_MAX),
                    con_tope(tiros0, SIM.TIROS_TOTAL_MIN, SIM.TIROS_TOTAL_MAX)),
            }
            _PLAN["armado"] = True
        try:
            return orig(*a, **kw)
        finally:
            if _PLAN["esperado"]:
                raise RuntimeError(f"enmienda 1: quedaron muestreos del local sin aplicar: {_PLAN}")
            _PLAN.update(armado=False, en_bloque=False, i=0)

    FS.simular_partido_futbol = spf


# Reemplazo a nivel de modulo: lo usan HT.verificar, HT._iniciar_pool y HT.main
# (y los procesos hijos, que re-importan este archivo en Windows).
HT._iniciar = _iniciar_con_localia


def main():
    argv = sys.argv[1:]
    for flag, env in (("--suma-arco", "SUMA_ARCO"), ("--suma-tiros", "SUMA_TIROS")):
        if flag in argv:
            i = argv.index(flag)
            os.environ[env] = argv[i + 1]
            del argv[i:i + 2]
    if "--verificar" in argv and _sumas() != (0.0, 0.0):
        sys.exit("--verificar es contra main sin parches: solo con las dos sumas en 0")
    print(f"sumas al local: arco {_sumas()[0]:+.2f}, tiros {_sumas()[1]:+.2f}", flush=True)
    sys.argv = [sys.argv[0]] + argv
    return HT.main()


if __name__ == "__main__":
    sys.exit(main())
