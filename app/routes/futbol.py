from fastapi import APIRouter
from app.services import futbol_service

router = APIRouter()

@router.get("/partidos-hoy")
async def partidos_hoy():
    partidos = futbol_service.get_partidos_hoy()
    return {"partidos": partidos}


@router.get("/partidos-rango")
async def partidos_rango(dias: int = 3):
    partidos = futbol_service.get_partidos_rango(dias=dias)
    return {"partidos": partidos}

@router.get("/top-picks")
async def top_picks():
    picks = futbol_service.get_top_picks()
    return {"picks": picks}

@router.get("/partido/{local}/{visitante}")
async def partido(local: str, visitante: str):
    try:
        resultado, error = futbol_service.get_analisis_partido(local, visitante)
        if error:
            return {"error": error}
        return resultado
    except Exception as e:
        return {"error": str(e)}

@router.get("/buscar-jugador")
async def buscar_jugador(q: str, limite: int = 20):
    try:
        resultados = futbol_service.buscar_jugador_general(q, limite=limite)
        return {"jugadores": resultados}
    except Exception as e:
        return {"error": str(e)}


@router.get("/jugadores/{local}/{visitante}")
async def jugadores(local: str, visitante: str):
    try:
        resultado, error = futbol_service.get_jugadores_partido(local, visitante)
        if error:
            return {"error": error}
        return resultado
    except Exception as e:
        return {"error": str(e)}


@router.get("/value-bet-manual/{local}/{visitante}")
async def value_bet_manual(local: str, visitante: str, mercado: str, linea: float, lado: str, cuota: float):
    try:
        resultado, error = futbol_service.calcular_value_bet_manual(local, visitante, mercado, linea, lado, cuota)
        if error:
            return {"error": error}
        return resultado
    except Exception as e:
        return {"error": str(e)}


@router.get("/jugador-historial/{equipo}/{jugador}")
async def jugador_historial(equipo: str, jugador: str, n: int = 5):
    try:
        resultado, error = futbol_service.get_historial_jugador(equipo, jugador, n=n)
        if error:
            return {"error": error}
        return {"historial": resultado}
    except Exception as e:
        return {"error": str(e)}

@router.get("/value-bets-hoy")
async def value_bets_hoy():
    value_bets = futbol_service.get_value_bets_hoy()
    return {"value_bets": value_bets}

@router.post("/chat")
async def chat(payload: dict):
    try:
        resultado, error = futbol_service.chat_ia(payload.get("mensajes", []), payload.get("contexto", ""))
        if error:
            return {"error": error}
        return {"respuesta": resultado}
    except Exception as e:
        return {"error": str(e)}
