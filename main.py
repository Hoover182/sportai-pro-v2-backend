from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import nba, futbol
from app.barra_codificada import BarraCodificadaMiddleware

app = FastAPI(title="SportAI Pro API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
# Equipos con "/" en el nombre (Bodo/Glimt): ver app/barra_codificada.py.
app.add_middleware(BarraCodificadaMiddleware)

app.include_router(nba.router, prefix="/nba", tags=["NBA"])
app.include_router(futbol.router, prefix="/futbol", tags=["Futbol"])

@app.get("/")
def root():
    return {"status": "SportAI Pro API running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
