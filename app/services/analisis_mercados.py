"""Analisis IA por mercado de la pantalla pre-partido -- texto por
REGLAS (sin llamada a un modelo generativo, sin costo): titulo + resumen
con un dato numerico + 2-3 bullets con datos reales + disclaimer.

Numeros: salen de la MISMA respuesta de get_analisis_partido() (ya
redondeados como los muestra la tarjeta) y de los hechos que arma
_hechos_para_analisis() desde el CSV. Nada se inventa: un bullet sin
dato se omite, y un mercado sin proyeccion devuelve tono "sin_datos".

Tono (umbrales aprobados), sobre la PROPORCION del favorito frente a la
siguiente opcion: p1 / (p1 + p2). En un mercado de 2 opciones es su
probabilidad tal cual; en 1X2 (3 opciones) la probabilidad cruda del
favorito casi nunca pasa de 55% aunque haya un favorito real, por eso
se mira la proporcion entre las 2 primeras.
    >= 70% favorito_claro | 55-70% moderado | < 55% parejo
Dos tonos con prioridad (calidad del dato, no inclinacion):
    pocos_datos       -- algun equipo con historial chico (pocos_datos
                         del modelo o < MIN_PARTIDOS)
    senales_cruzadas  -- 1X2 / doble oportunidad: la forma reciente
                         contradice lo que muestra el modelo

Variante de titulo/resumen: "aleatoria pero consistente" -- semilla fija
por (fixture_id, mercado) via sha256 (NO hash(): cambia entre procesos
y Render reinicia seguido), mismo criterio que la semilla de simular().
"""
import hashlib
import re

UMBRAL_CLARO = 70.0
UMBRAL_MODERADO = 55.0
MIN_PARTIDOS = 5
MIN_CON_DATO = 3                   # partidos con el stat real para citar el promedio propio de un equipo
GAP_FORMA_CRUZADA = 1.0            # puntos por partido (V=3, E=1) en los ultimos 5
# Linea O/U analizada por mercado: la linea "tipica" del partido, junto a
# la mediana REAL del total por partido en el CSV (>18k partidos FT al
# 2026-09-23: goles 3, corners 9, tarjetas 4, tiros al arco 8, tiros
# totales 25). Con una linea fija el tono dice si ESTE partido se proyecta
# por encima o por debajo de lo tipico. (Se probo "la linea mas respaldada
# entre 60% y 92%": con datos reales elegia lineas extremas -- Under 5.5
# goles 90.4%, Under 16.5 corners 91.5% -- y todo daba favorito_claro.)
LINEAS_REFERENCIA = {"goles": 2.5, "corners": 9.5, "tarjetas": 4.5, "tiros_arco": 8.5, "tiros_total": 24.5}
# Atajadas por equipo: mediana real 3 por equipo y partido (6367 partidos
# FT con el dato al 2026-09-24, solo ~25% del CSV lo tiene).
LINEA_ATAJADAS_EQUIPO = 2.5

DISCLAIMER = ("Las probabilidades y datos de esta pantalla surgen de un modelo matemático-estadístico "
              "integrado con IA basado en datos meramente históricos. En el fútbol cualquier resultado puede pasar.")

EMOJI = {"favorito_claro": "✅", "moderado": "📈", "parejo": "🪙",
         "pocos_datos": "⚠️", "senales_cruzadas": "🔀", "sin_datos": "➖"}

TITULOS = {
    "favorito_claro": ["Favorito con respaldo estadístico", "Los números hablan claro", "Escenario bastante definido",
                       "Inclinación marcada", "Dominio claro en los datos"],
    "moderado": ["Inclinación real, no aplastante", "Ventaja con matices", "Hay un favorito, con margen",
                 "Los datos se inclinan", "Ventaja moderada"],
    "parejo": ["Moneda al aire", "Prácticamente parejo", "Cara o sello", "Sin favorito claro", "Todo abierto"],
    "pocos_datos": ["Pocos datos para opinar", "Muestra muy chica", "Tomalo con pinzas",
                    "Historial demasiado corto", "Lectura con poca base"],
    "senales_cruzadas": ["El modelo y la forma no coinciden", "Señales cruzadas", "Datos que tiran para lados distintos"],
    "sin_datos": ["Sin datos suficientes"],
}

# Handicap europeo: el desenlace que lidera suele ser "el rival evita perder
# por 2 o mas", asi que los titulos genericos ("Favorito con respaldo...")
# confundian (salian en partidos 38/35 en el 1X2). Titulos sobre el MARGEN.
TITULOS_HCP_EUROPEO = {
    "favorito_claro": ["Margen bastante definido", "Los números marcan el margen", "Diferencia clara en los datos",
                       "El margen se ve con claridad"],
    "moderado": ["Margen con matices", "Inclinación en el margen", "El margen se inclina, sin certeza",
                 "Diferencia moderada"],
    "parejo": ["Margen abierto", "Diferencia incierta", "El margen no se define", "Hándicap parejo"],
}

# Resumen por FAMILIA de mercado (gramatica propia) y nivel de inclinacion.
RESUMENES = {
    "resultado": {
        "favorito_claro": ["{Fav} lidera con {p1}% y le saca {dif} puntos a {seg}; los datos sostienen la diferencia.",
                           "Con {p1}% para {fav} contra {p2}% de {seg}, el escenario está bastante definido.",
                           "{Fav} concentra {p1}% de probabilidad, {dif} puntos por encima de {seg}."],
        "moderado": ["{Fav} aparece adelante con {p1}%, {dif} puntos sobre {seg}: ventaja real, pero no definitiva.",
                     "El modelo se inclina por {fav} ({p1}%), aunque {seg} conserva un {p2}%.",
                     "{Fav} le saca {dif} puntos a {seg} ({p1}% contra {p2}%): hay favorito, con margen para la sorpresa."],
        "parejo": ["{Fav} y {seg} quedan a {dif} puntos de distancia: es prácticamente un 50-50.",
                   "{p1}% contra {p2}%: los datos no separan a {fav} de {seg}.",
                   "Apenas {dif} puntos entre {fav} y {seg}; cualquiera de los dos es posible."],
    },
    "doble": {
        "favorito_claro": ["{Fav} cubre el {p1}% de los escenarios; {seg} queda en {p2}%.",
                           "Solo {seg} rompe esta opción, y el modelo le da {p2}%.",
                           "{Fav} tiene {p1}% de probabilidad, {dif} puntos por encima de {seg}."],
        "moderado": ["{Fav} llega a {p1}%, pero {seg} conserva un {p2}% que no es menor.",
                     "El modelo favorece {fav} ({p1}%), con {seg} en {p2}%.",
                     "{Fav} le saca {dif} puntos a {seg}: inclinación real, no aplastante."],
        "parejo": ["{Fav} apenas supera a {seg}: {p1}% contra {p2}%.",
                   "Entre {fav} y {seg} hay solo {dif} puntos: prácticamente parejo.",
                   "{p1}% contra {p2}%: {fav} no se despega de {seg}."],
    },
    "sino": {
        "favorito_claro": ["El {fav} domina con {p1}% contra {p2}%; los datos sostienen la diferencia.",
                           "Con {p1}% para el {fav}, el escenario está bastante definido.",
                           "El {fav} le saca {dif} puntos al {seg}."],
        "moderado": ["El modelo se inclina por el {fav} ({p1}%), aunque el {seg} conserva un {p2}%.",
                     "El {fav} aparece adelante con {p1}%: ventaja real, pero no definitiva.",
                     "El {fav} saca {dif} puntos de diferencia ({p1}% contra {p2}%)."],
        "parejo": ["Sí y No quedan a {dif} puntos de distancia: es prácticamente un 50-50.",
                   "{p1}% contra {p2}%: los datos no se definen entre Sí y No.",
                   "Apenas {dif} puntos separan al {fav} del {seg}."],
    },
    "ou": {
        "favorito_claro": ["El modelo proyecta {proj}: {linea} llega a {p1}% y los datos sostienen la diferencia.",
                           "{Linea} concentra {p1}% de probabilidad con una proyección de {proj}.",
                           "Con {proj} {proyectados}, {linea} tiene {p1}% contra {p2}%: escenario bastante definido."],
        "moderado": ["El modelo proyecta {proj}; {linea} aparece adelante con {p1}%, sin margen amplio.",
                     "{Linea} se inclina con {p1}% ({proj} {proyectados}): ventaja real, no definitiva.",
                     "Con {proj} {proyectados}, {linea} se impone {p1}% a {p2}%."],
        "parejo": ["El modelo proyecta {proj}, justo en la zona de la línea: {linea} queda en {p1}% contra {p2}%.",
                   "Con {proj} {proyectados}, {linea} y su contraria quedan a {dif} puntos: prácticamente un 50-50.",
                   "{Linea} apenas se asoma con {p1}%: cara o sello."],
    },
}

RESUMENES["hcp"] = {
    # {O1}/{o1} y {o2}: desenlaces del handicap ya con el nombre del equipo
    "favorito_claro": ["{O1} lidera con {p1}% y le saca {dif} puntos a {o2}.",
                       "Con {p1}% para {o1} contra {p2}% de {o2}, el hándicap está bastante definido.",
                       "{O1} concentra {p1}% de probabilidad, {dif} puntos por encima de {o2}."],
    "moderado": ["{O1} aparece adelante con {p1}%, {dif} puntos sobre {o2}: ventaja real, pero no definitiva.",
                 "El modelo se inclina por {o1} ({p1}%), aunque {o2} conserva un {p2}%.",
                 "{O1} le saca {dif} puntos a {o2} ({p1}% contra {p2}%)."],
    "parejo": ["{O1} y {o2} quedan a {dif} puntos de distancia: prácticamente parejo.",
               "{p1}% contra {p2}%: los datos no separan a {o1} de {o2}.",
               "Apenas {dif} puntos entre {o1} y {o2}."],
}

# O/U con distribucion muy dispersa (ej. atajadas de un equipo sin datos:
# 37% de chance de 0 y cola larga): el promedio proyectado queda del otro
# lado de la linea respecto del desenlace mas probable. Mismo texto para
# los 3 niveles (el nivel ya lo da el titulo).
_OU_DISPERSO = ["Aunque el promedio proyectado es {proj}, los resultados están muy dispersos y {linea} queda en {p1}% contra {p2}%.",
                "{Linea} es lo más probable ({p1}%), aunque el promedio proyectado sea {proj}: la distribución es muy dispersa.",
                "El promedio proyectado ({proj}) no cuenta toda la historia: con resultados muy dispersos, {linea} tiene {p1}%."]
RESUMENES["ou_disperso"] = {k: _OU_DISPERSO for k in ("favorito_claro", "moderado", "parejo")}

UNIDADES = {"goles": "goles", "corners": "corners", "tarjetas": "tarjetas",
            "tiros_arco": "tiros al arco", "tiros_total": "tiros totales"}
PROYECTADOS = {"tarjetas": "proyectadas"}   # el resto, masculino
# clave de hechos con cuantos de los ultimos partidos tienen el stat real
CLAVE_COBERTURA = {"corners": "n_corners", "tarjetas": "n_tarjetas",
                   "tiros_arco": "n_tiros_arco", "tiros_total": "n_tiros_total"}


def _f(x):
    """Numero como lo muestra la tarjeta: 1 decimal, sin notacion rara."""
    return f"{float(x):.1f}"


def _f2(x):
    return f"{float(x):.2f}"


def _cap(s):
    return s[:1].upper() + s[1:]


def _contracciones(s):
    return s.replace(" a el ", " al ").replace(" de el ", " del ")


def _indice(clave_partido, mercado, sal, n):
    h = hashlib.sha256(f"{clave_partido}|{mercado}|{sal}".encode("utf-8")).digest()
    return int.from_bytes(h[:8], "big") % n


def nivel(p1, p2):
    """Tono por proporcion del favorito frente a la siguiente opcion."""
    total = p1 + p2
    proporcion = 100.0 * p1 / total if total > 0 else 50.0
    if proporcion >= UMBRAL_CLARO:
        return "favorito_claro"
    if proporcion >= UMBRAL_MODERADO:
        return "moderado"
    return "parejo"


def _armar(clave_partido, mercado, familia, tono, base, slots, bullets, titulos=None):
    """titulos: banco propio del mercado para los 3 niveles de inclinacion
    (pocos_datos / senales_cruzadas / sin_datos usan siempre TITULOS)."""
    banco = titulos if titulos and tono in titulos else TITULOS
    titulo = banco[tono][_indice(clave_partido, mercado, "titulo", len(banco[tono]))]
    plantillas = RESUMENES[familia][base]
    resumen = plantillas[_indice(clave_partido, mercado, "resumen", len(plantillas))].format(**slots)
    return {"tono": tono, "emoji": EMOJI[tono], "titulo": titulo, "resumen": _cap(_contracciones(resumen)),
            "bullets": [_contracciones(b) for b in bullets if b][:3], "disclaimer": DISCLAIMER}


def _sin_datos(mercado, motivo):
    return {"tono": "sin_datos", "emoji": EMOJI["sin_datos"], "titulo": TITULOS["sin_datos"][0],
            "resumen": motivo, "bullets": [], "disclaimer": DISCLAIMER}


# ----------------------------------------------------------------------------- bullets comunes
def _b_h2h_resultado(h, local, visitante):
    if not h["n"]:
        return "No hay cruces directos en la base: el análisis se apoya en la forma de cada equipo."
    texto = (f"{local} ganó {h['g']}, empató {h['e']} y perdió {h['p']} "
             f"de los últimos {h['n']} cruces directos con {visitante}")
    if h["ultimo_antiguo"]:
        texto += f" (el más reciente es del {h['ultima_fecha']}, un dato antiguo)"
    return texto + "."


def _b_condicion(hl, hv, local, visitante):
    cl, cv = hl["condicion"], hv["condicion"]
    if cl["n"] < 3 or cv["n"] < 3:
        return None
    return (f"{local} ganó {cl['v']} de sus últimos {cl['n']} partidos de local; "
            f"{visitante}, {cv['v']} de sus últimos {cv['n']} como visitante.")


def _b_forma(hl, hv, local, visitante):
    fl, fv = hl["forma5"], hv["forma5"]
    if not fl["n"] or not fv["n"]:
        return None
    return (f"Forma reciente (V-E-D): {local} {fl['v']}-{fl['e']}-{fl['d']} en {fl['n']} partidos; "
            f"{visitante} {fv['v']}-{fv['e']}-{fv['d']} en {fv['n']}.")


def _b_pocos_datos(r, hechos):
    chicos = [(r[k], hechos[k]["n_total"]) for k in ("local", "visitante")
              if hechos[k]["pocos_datos"]]
    if not chicos:
        return None
    detalle = " y ".join(f"{nombre} tiene {n} partido{'s' if n != 1 else ''}" for nombre, n in chicos)
    return f"Ojo: {detalle} en la base; gran parte de la proyección sale del promedio de la competición."


def _forma_cruzada(hechos, fav_lado):
    """True si la forma de los ultimos 5 separa por >= GAP a los equipos y
    apunta en contra del favorito del modelo (o el modelo los ve parejos)."""
    pl, pv = hechos["local"]["forma5"]["ppg"], hechos["visitante"]["forma5"]["ppg"]
    if pl is None or pv is None or abs(pl - pv) < GAP_FORMA_CRUZADA:
        return False
    mejor_forma = "local" if pl > pv else "visitante"
    return fav_lado in (None, "empate") or fav_lado != mejor_forma


# ----------------------------------------------------------------------------- mercados
def analisis_1x2(r, hechos, clave):
    L, V = r["local"], r["visitante"]
    ops = [(f"{L} (1)", r["prob_local"], "local"), ("el empate (X)", r["prob_empate"], "empate"),
           (f"{V} (2)", r["prob_visitante"], "visitante")]
    (fav, p1, lado), (seg, p2, _) = sorted(ops, key=lambda o: -o[1])[:2]
    base = nivel(p1, p2)
    tono = base
    if hechos["pocos_datos"]:
        tono = "pocos_datos"
    elif _forma_cruzada(hechos, lado if base != "parejo" else None):
        tono = "senales_cruzadas"
    slots = {"fav": fav, "Fav": _cap(fav), "seg": seg, "p1": _f(p1), "p2": _f(p2), "dif": _f(p1 - p2)}
    gl, gv = r["goles_proj"].split(" - ")
    bullets = [
        _b_pocos_datos(r, hechos) if tono == "pocos_datos" else None,
        _b_forma(hechos["local"], hechos["visitante"], L, V) if tono == "senales_cruzadas" else None,
        _b_h2h_resultado(hechos["h2h"], L, V),
        _b_condicion(hechos["local"], hechos["visitante"], L, V),
        f"Proyección de goles del modelo: {L} {gl}, {V} {gv}.",
    ]
    return _armar(clave, "1x2", "resultado", tono, base, slots, bullets)


def analisis_doble_oportunidad(r, hechos, clave):
    L, V = r["local"], r["visitante"]
    ops = [(f"1X ({L} o empate)", r["prob_1x"], f"una victoria de {V}", r["prob_visitante"], "visitante", "local"),
           (f"X2 (empate o {V})", r["prob_x2"], f"una victoria de {L}", r["prob_local"], "local", "visitante"),
           (f"12 (gana cualquiera)", r["prob_12"], "el empate", r["prob_empate"], "empate", None)]
    fav, p1, comp, p2, lado_comp, lado_fav = max(ops, key=lambda o: o[1])
    base = nivel(p1, p2)
    tono = base
    if hechos["pocos_datos"]:
        tono = "pocos_datos"
    elif lado_fav and _forma_cruzada(hechos, lado_fav):
        tono = "senales_cruzadas"
    slots = {"fav": fav, "Fav": _cap(fav), "seg": comp, "p1": _f(p1), "p2": _f(p2), "dif": _f(p1 - p2)}
    if lado_comp in ("local", "visitante"):
        nombre = L if lado_comp == "local" else V
        f5 = hechos[lado_comp]["forma5"]
        b_comp = (f"{nombre} ganó {f5['v']} de sus últimos {f5['n']} partidos." if f5["n"] else None)
    else:
        h = hechos["h2h"]
        b_comp = (f"El empate se dio en {h['e']} de los últimos {h['n']} cruces directos." if h["n"] else None)
    bullets = [
        _b_pocos_datos(r, hechos) if tono == "pocos_datos" else None,
        _b_forma(hechos["local"], hechos["visitante"], L, V) if tono == "senales_cruzadas" else None,
        b_comp,
        _b_h2h_resultado(hechos["h2h"], L, V),
    ]
    return _armar(clave, "doble_oportunidad", "doble", tono, base, slots, bullets)


def analisis_ambos_marcan(r, hechos, clave):
    L, V = r["local"], r["visitante"]
    si = r["prob_ambos_marcan"]
    no = round(100 - si, 1)
    (fav, p1), (seg, p2) = sorted([("Sí", si), ("No", no)], key=lambda o: -o[1])
    base = nivel(p1, p2)
    tono = "pocos_datos" if hechos["pocos_datos"] else base
    slots = {"fav": fav, "Fav": fav, "seg": seg, "p1": _f(p1), "p2": _f(p2), "dif": _f(p1 - p2)}
    h, bl, bv = hechos["h2h"], hechos["local"]["btts"], hechos["visitante"]["btts"]
    sl, sv = r["stats_local"], r["stats_visitante"]
    bullets = [
        _b_pocos_datos(r, hechos) if tono == "pocos_datos" else None,
        (f"Ambos marcaron en {h['btts']} de los últimos {h['n']} cruces directos." if h["n"] else None),
        (f"{L} tuvo gol de los dos equipos en {bl['x']} de sus últimos {bl['n']} partidos; "
         f"{V}, en {bv['x']} de {bv['n']}." if bl["n"] and bv["n"] else None),
        # Con pocos datos el promedio es la estimacion del modelo mezclada con
        # la liga, no un promedio real del equipo: no se cita.
        None if hechos["pocos_datos"] else
        f"{L} convierte {_f(sl['goles_favor'])} y recibe {_f(sl['goles_contra'])} por partido; "
        f"{V}, {_f(sv['goles_favor'])} y {_f(sv['goles_contra'])}.",
    ]
    return _armar(clave, "ambos_marcan", "sino", tono, base, slots, bullets)


def _elegir_linea(ou, mercado):
    """(linea, lado, p1, p2) en la linea de referencia del mercado (o la
    disponible mas cercana a ella); lado = el mas probable."""
    validas = {k: v for k, v in ou.items() if v.get("over") is not None and v.get("under") is not None}
    if not validas:
        return None
    ref = LINEAS_REFERENCIA[mercado]
    linea = min(validas, key=lambda k: (abs(float(k) - ref), float(k)))
    over, under = validas[linea]["over"], validas[linea]["under"]
    lado, p1, p2 = ("Over", over, under) if over >= under else ("Under", under, over)
    return linea, lado, p1, p2


def _analisis_ou(r, hechos, clave, mercado, proj, ou, bullets_extra):
    unidad = UNIDADES[mercado]
    if proj is None or not ou:
        return _sin_datos(mercado, f"No hay suficientes datos de {unidad} de estos equipos para proyectar este mercado.")
    elegido = _elegir_linea(ou, mercado)
    if elegido is None:
        return _sin_datos(mercado, f"No hay suficientes datos de {unidad} de estos equipos para proyectar este mercado.")
    linea, lado, p1, p2 = elegido
    base = nivel(p1, p2)
    tono = "pocos_datos" if hechos["pocos_datos"] else base
    linea_txt = f"{lado} {linea} {unidad}"
    slots = {"linea": linea_txt, "Linea": linea_txt, "proj": f"{_f2(proj)} {unidad}",
             "proyectados": PROYECTADOS.get(mercado, "proyectados"),
             "p1": _f(p1), "p2": _f(p2), "dif": _f(p1 - p2)}
    bullets = [_b_pocos_datos(r, hechos) if tono == "pocos_datos" else None] + bullets_extra
    return _armar(clave, mercado, "ou", tono, base, slots, bullets)


def _b_promedios(nombre_l, nombre_v, fl, cl, fv, cv, unidad):
    if cl is None or cv is None:
        return (f"{nombre_l} promedia {_f(fl)} {unidad} a favor por partido; {nombre_v}, {_f(fv)}."
                if fl is not None and fv is not None else None)
    return (f"{nombre_l} promedia {_f(fl)} {unidad} a favor y {_f(cl)} en contra por partido; "
            f"{nombre_v}, {_f(fv)} y {_f(cv)}.")


def _b_h2h_prom(h, clave_prom, clave_n, unidad):
    n = h.get(clave_n) or 0
    if not n:
        return None
    if n == 1:
        return f"El único cruce directo con datos sumó {_f(h[clave_prom])} {unidad}."
    return f"Los últimos {n} cruces directos con datos promediaron {_f(h[clave_prom])} {unidad} en total."


def _b_promedios_stat(r, hechos, mercado, fl, cl, fv, cv):
    """Promedio propio de cada equipo SOLO si tiene >= MIN_CON_DATO partidos
    con el dato real. Sin datos, football_model usa el promedio de la liga
    (ej. Curico Unido: 0 de 8 partidos con tiros y tiros_total_favor=12.0),
    y presentarlo como "X promedia N" seria inventar un dato del equipo."""
    unidad = UNIDADES[mercado]
    clave_n = CLAVE_COBERTURA[mercado]
    L, V = r["local"], r["visitante"]
    ok_l = hechos["local"][clave_n] >= MIN_CON_DATO and fl is not None
    ok_v = hechos["visitante"][clave_n] >= MIN_CON_DATO and fv is not None
    if ok_l and ok_v:
        return _b_promedios(L, V, fl, cl, fv, cv, unidad)
    if not ok_l and not ok_v:
        return (f"Ni {L} ni {V} tienen datos propios de {unidad} en sus partidos recientes: "
                "la proyección sale del promedio de la competición.")
    bueno, malo, f_, c_ = (L, V, fl, cl) if ok_l else (V, L, fv, cv)
    propio = f"{bueno} promedia {_f(f_)} {unidad} a favor" + (f" y {_f(c_)} en contra" if c_ is not None else "")
    return f"{propio} por partido; {malo} no tiene datos propios de {unidad} recientes (se usa el promedio de la competición)."


def _b_cobertura(hechos, r, mercado):
    """Equipos con algo de dato (>= MIN_CON_DATO) pero menos de la mitad de
    su ventana cubierta; los que no llegan a MIN_CON_DATO ya los explica
    _b_promedios_stat."""
    clave_n, unidad = CLAVE_COBERTURA[mercado], UNIDADES[mercado]
    bajos = [(r[k], hechos[k][clave_n], hechos[k]["n_ventana"]) for k in ("local", "visitante")
             if MIN_CON_DATO <= hechos[k][clave_n] < hechos[k]["n_ventana"] / 2]
    if not bajos:
        return None
    detalle = " y ".join(f"{n} de los últimos {v} partidos de {nombre}" for nombre, n, v in bajos)
    return f"Cobertura baja: solo {detalle} tienen datos de {unidad}, así que la proyección es menos firme."


def analisis_goles(r, hechos, clave):
    L, V = r["local"], r["visitante"]
    gl, gv = (float(x) for x in r["goles_proj"].split(" - "))
    sl, sv = r["stats_local"], r["stats_visitante"]
    return _analisis_ou(r, hechos, clave, "goles", gl + gv, r["goles_ou"], [
        f"Proyección por equipo: {L} {_f2(gl)}, {V} {_f2(gv)}.",
        None if hechos["pocos_datos"] else  # mismo motivo que en analisis_ambos_marcan
        _b_promedios(L, V, sl["goles_favor"], sl["goles_contra"], sv["goles_favor"], sv["goles_contra"], "goles"),
        _b_h2h_prom(hechos["h2h"], "goles_prom", "n", "goles"),
    ])


def analisis_corners(r, hechos, clave):
    L, V = r["local"], r["visitante"]
    sl, sv = r["stats_local"], r["stats_visitante"]
    return _analisis_ou(r, hechos, clave, "corners", r.get("corners_proj"), r.get("corners_ou"), [
        _b_promedios_stat(r, hechos, "corners", sl["corners_favor"], sl["corners_contra"],
                          sv["corners_favor"], sv["corners_contra"]),
        _b_h2h_prom(hechos["h2h"], "corners_prom", "n_corners", "corners"),
        _b_cobertura(hechos, r, "corners"),
    ])


def analisis_tarjetas(r, hechos, clave):
    L, V = r["local"], r["visitante"]
    sl, sv = r["stats_local"], r["stats_visitante"]
    return _analisis_ou(r, hechos, clave, "tarjetas", r.get("tarjetas_proj"), r.get("tarjetas_ou"), [
        _b_promedios_stat(r, hechos, "tarjetas", sl["tarjetas_favor"], None, sv["tarjetas_favor"], None),
        _b_h2h_prom(hechos["h2h"], "tarjetas_prom", "n_tarjetas", "tarjetas"),
        _b_cobertura(hechos, r, "tarjetas"),
    ])


def analisis_tiros(r, hechos, clave, mercado):
    L, V = r["local"], r["visitante"]
    sl, sv = r["stats_local"], r["stats_visitante"]
    campo = "tiros_arco_favor" if mercado == "tiros_arco" else "tiros_total_favor"
    proj = r.get("tiros_arco_proj") if mercado == "tiros_arco" else r.get("tiros_total_proj")
    ou = r.get("tiros_arco_ou") if mercado == "tiros_arco" else r.get("tiros_total_ou")
    return _analisis_ou(r, hechos, clave, mercado, proj, ou, [
        _b_promedios_stat(r, hechos, mercado, sl.get(campo), None, sv.get(campo), None),
        _b_cobertura(hechos, r, mercado),
    ])


def _favorito(r):
    """Favorito = el de mayor probabilidad de ganar en el 1X2 de ESTA
    respuesta (post-Elo). El handicap sale de grid_handicap, reescalada
    por el mismo Elo, asi que el texto nombra siempre al mismo favorito
    que muestra la tarjeta 1X2 (empate de probabilidades -> local)."""
    if r["prob_local"] >= r["prob_visitante"]:
        return "local", r["local"], r["visitante"]
    return "visitante", r["visitante"], r["local"]


def _tono_resultado(hechos, base, fav_lado):
    if hechos["pocos_datos"]:
        return "pocos_datos"
    if _forma_cruzada(hechos, fav_lado):
        return "senales_cruzadas"
    return base


def analisis_hcp_europeo(r, hechos, clave):
    """Un solo analisis por tarjeta sobre la linea representativa "favorito
    -1" (3 desenlaces, misma regla de proporcion que el 1X2)."""
    lado, fav, riv = _favorito(r)
    if lado == "local":   # Local -1 = m1; ganar por 3+/4+ = m2/m3
        pf, pe, pr = r["prob_hcp_local_m1"], r["prob_hcp_empate_m1"], r["prob_hcp_visit_m1"]
        p3, p4 = r.get("prob_hcp_local_m2"), r.get("prob_hcp_local_m3")
    else:                 # Visitante -1 = Local +1 = p1; ganar por 3+/4+ = p2/p3
        pf, pe, pr = r["prob_hcp_visit_p1"], r["prob_hcp_empate_p1"], r["prob_hcp_local_p1"]
        p3, p4 = r.get("prob_hcp_visit_p2"), r.get("prob_hcp_visit_p3")
    ops = [(f"{fav} -1 (gana por 2 o más)", pf), (f"el empate técnico ({fav} gana por 1)", pe),
           (f"{riv} +1 (evita perder por 2 o más)", pr)]
    (o1, p1), (o2, p2) = sorted(ops, key=lambda o: -o[1])[:2]
    base = nivel(p1, p2)
    tono = _tono_resultado(hechos, base, lado)
    slots = {"o1": o1, "O1": _cap(o1), "o2": o2, "p1": _f(p1), "p2": _f(p2), "dif": _f(p1 - p2)}
    m = hechos[lado]["margen"]
    if not m["n"]:
        b_margen = None
    elif m["n"] == 1:
        b_margen = (f"{fav} tiene un solo partido registrado"
                    + (": lo ganó por 2 goles o más." if m["gan2"] else ": lo ganó por 1 gol." if m["gan"] else ", sin victoria."))
    elif m["gan"] == 0:
        b_margen = f"{fav} no ganó ninguno de sus últimos {m['n']} partidos."
    else:
        b_margen = f"{fav} ganó {m['gan']} de sus últimos {m['n']} partidos, {m['gan2']} de ellos por 2 goles o más."
    bullets = [
        _b_pocos_datos(r, hechos) if tono == "pocos_datos" else None,
        _b_forma(hechos["local"], hechos["visitante"], r["local"], r["visitante"]) if tono == "senales_cruzadas" else None,
        (f"Ganar por 3 o más ({fav} -2): {_f(p3)}%; por 4 o más ({fav} -3): {_f(p4)}%."
         if p3 is not None and p4 is not None else None),
        b_margen,
    ]
    return _armar(clave, "hcp_europeo", "hcp", tono, base, slots, bullets, titulos=TITULOS_HCP_EUROPEO)


def analisis_hcp_asiatico(r, hechos, clave):
    """Un solo analisis por tarjeta sobre la linea representativa -0.5/+0.5
    (favorito -0.5 = gana el partido; rival +0.5 = no pierde). Sin push."""
    lado, fav, riv = _favorito(r)
    h = r["handicap_asiatico"]
    if lado == "local":
        pf, pr = h["-0.5"]["cubre"], h["-0.5"]["no_cubre"]
        dos_mas = h["-1.5"]["cubre"]
    else:   # Visitante -0.5 = Local +0.5 visto del otro lado
        pf, pr = h["0.5"]["no_cubre"], h["0.5"]["cubre"]
        dos_mas = h["1.5"]["no_cubre"]
    cero = h["0.0"]
    gana_fav, gana_riv = (cero["cubre"], cero["no_cubre"]) if lado == "local" else (cero["no_cubre"], cero["cubre"])
    ops = [(f"{fav} -0.5 (gana el partido)", pf), (f"{riv} +0.5 (no pierde)", pr)]
    (o1, p1), (o2, p2) = sorted(ops, key=lambda o: -o[1])
    base = nivel(p1, p2)
    tono = _tono_resultado(hechos, base, lado)
    slots = {"o1": o1, "O1": _cap(o1), "o2": o2, "p1": _f(p1), "p2": _f(p2), "dif": _f(p1 - p2)}
    bullets = [
        _b_pocos_datos(r, hechos) if tono == "pocos_datos" else None,
        _b_forma(hechos["local"], hechos["visitante"], r["local"], r["visitante"]) if tono == "senales_cruzadas" else None,
        f"Con la línea 0 (si empatan se devuelve): {fav} {_f(gana_fav)}% contra {riv} {_f(gana_riv)}%, "
        f"con {_f(cero['push'])}% de devolución.",
        f"Que {fav} gane por 2 o más ({fav} -1.5): {_f(dos_mas)}%.",
    ]
    return _armar(clave, "hcp_asiatico", "hcp", tono, base, slots, bullets)


def analisis_atajadas_equipo(r, hechos, clave, lado):
    """Atajadas del arquero de un equipo: O/U sobre LINEA_ATAJADAS_EQUIPO,
    2 bullets (tiros al arco del rival + dato propio). Las atajadas son
    casi exactamente tiros al arco del rival - sus goles (84% exacto en el
    CSV), pero la proyeccion de atajadas del modelo NO cierra con la de
    tiros/goles, asi que la cuenta no se muestra."""
    eq, riv = (r["local"], r["visitante"]) if lado == "local" else (r["visitante"], r["local"])
    mercado = f"atajadas_{lado}"
    ou, proj = r.get(f"atajadas_ou_{lado}"), r.get(f"atajadas_{lado}_proj")
    validas = {k: v for k, v in (ou or {}).items() if v.get("over") is not None and v.get("under") is not None}
    if proj is None or not validas:
        return _sin_datos(mercado, f"No hay suficientes datos de atajadas de {eq} para proyectar este mercado.")
    linea = min(validas, key=lambda k: (abs(float(k) - LINEA_ATAJADAS_EQUIPO), float(k)))
    over, under = validas[linea]["over"], validas[linea]["under"]
    sentido, p1, p2 = ("Over", over, under) if over >= under else ("Under", under, over)
    base = nivel(p1, p2)
    tono = "pocos_datos" if hechos["pocos_datos"] else base
    linea_txt = f"{sentido} {linea} atajadas"
    slots = {"linea": linea_txt, "Linea": linea_txt, "proj": f"{_f2(proj)} atajadas de {eq}",
             "proyectados": "proyectadas", "p1": _f(p1), "p2": _f(p2), "dif": _f(p1 - p2)}
    disperso = (sentido == "Under" and proj > float(linea)) or (sentido == "Over" and proj < float(linea))
    familia = "ou_disperso" if disperso else "ou"
    tiros_riv = r.get(f"tiros_arco_{'visitante' if lado == 'local' else 'local'}_proj")
    he = hechos[lado]
    if he["n_atajadas"] >= MIN_CON_DATO:
        b_propio = f"{eq} promedia {_f(he['atajadas_prom'])} atajadas en {he['n_atajadas']} partidos recientes con el dato."
    elif he["n_ventana"] == 1:
        b_propio = (f"{eq} tiene un solo partido registrado" + ("" if he["n_atajadas"] else ", sin dato de atajadas")
                    + ", así que esta proyección es poco firme.")
    else:
        b_propio = (f"{eq} tiene el dato de atajadas en solo {he['n_atajadas']} de sus últimos {he['n_ventana']} "
                    "partidos, así que esta proyección es poco firme.")
    bullets = [
        _b_pocos_datos(r, hechos) if tono == "pocos_datos" else None,
        (f"Las atajadas dependen de cuánto remate el rival: {riv} proyecta {_f2(tiros_riv)} tiros al arco."
         if tiros_riv is not None else None),
        b_propio,
    ]
    return _armar(clave, mercado, familia, tono, base, slots, bullets)


def armar_analisis_ia(r, hechos, clave_partido):
    """r: respuesta de get_analisis_partido() (sin analisis_ia).
    hechos: _hechos_para_analisis(). clave_partido: fixture_id (o
    local|visitante si no hay). Un mercado que falla no rompe los demas."""
    fabricas = {
        "1x2": analisis_1x2,
        "doble_oportunidad": analisis_doble_oportunidad,
        "ambos_marcan": analisis_ambos_marcan,
        "goles": analisis_goles,
        "corners": analisis_corners,
        "tarjetas": analisis_tarjetas,
        "tiros_arco": lambda r_, h_, c_: analisis_tiros(r_, h_, c_, "tiros_arco"),
        "tiros_total": lambda r_, h_, c_: analisis_tiros(r_, h_, c_, "tiros_total"),
        # Segunda pasada: un analisis por tarjeta de handicap, uno por arquero
        "hcp_europeo": analisis_hcp_europeo,
        "hcp_asiatico": analisis_hcp_asiatico,
        "atajadas_local": lambda r_, h_, c_: analisis_atajadas_equipo(r_, h_, c_, "local"),
        "atajadas_visitante": lambda r_, h_, c_: analisis_atajadas_equipo(r_, h_, c_, "visitante"),
    }
    salida = {}
    for mercado, fabrica in fabricas.items():
        try:
            salida[mercado] = fabrica(r, hechos, clave_partido)
        except Exception as e:
            print(f"AVISO analisis_ia: {mercado}: {type(e).__name__}: {e}")
            salida[mercado] = _sin_datos(mercado, "No se pudo armar el análisis de este mercado.")
    return salida


NUMERO = re.compile(r"\d+(?:\.\d+)?")


def numeros_en_texto(analisis):
    """Todos los numeros que aparecen en resumen + bullets (para pruebas)."""
    texto = " ".join([analisis["resumen"]] + analisis["bullets"])
    return NUMERO.findall(texto)
