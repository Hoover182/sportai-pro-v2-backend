from fastapi import APIRouter
from app.services import futbol_service

router = APIRouter()

@router.get("/partidos-hoy")
async def partidos_hoy():
    partidos = futbol_service.get_partidos_hoy()
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

@router.get("/jugadores/{fixture_id}")
async def jugadores(fixture_id: int, liga: str = None):
    try:
        resultado, error = futbol_service.get_jugadores_partido(fixture_id, liga)
        if error:
            return {"error": error}
        return {"jugadores": resultado}
    except Exception as e:
        return {"error": str(e)}