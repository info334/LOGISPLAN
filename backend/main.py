"""
LogisPLAN - Backend API FastAPI
Sirve los datos de la base de datos existente al frontend React.
"""
import sys
from pathlib import Path

# Añadir raíz del proyecto al path para importar database.py y demás módulos
PROJECT_ROOT = str(Path(__file__).parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import init_database
from backend.routers import dashboard, vehiculos, movimientos, facturacion, configuracion, holded

app = FastAPI(
    title="LogisPLAN API",
    description="API para gestión logística de flota - Severino Logística",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dashboard.router)
app.include_router(vehiculos.router)
app.include_router(movimientos.router)
app.include_router(facturacion.router)
app.include_router(configuracion.router)
app.include_router(holded.router)


@app.on_event("startup")
def startup():
    init_database()


@app.get("/api/health")
def health_check():
    return {"status": "ok", "app": "LogisPLAN"}
