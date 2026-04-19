from fastapi import APIRouter

router = APIRouter()

@router.get("/scanner")
async def scanner():
    return {"jugadores": []}

@router.get("/top-hoy")
async def top_hoy():
    return {"picks": []}

@router.post("/partido")
async def partido():
    return {"resultado": {}}

@router.get("/jugador/{nombre}")
async def jugador(nombre: str):
    return {"jugador": nombre}
