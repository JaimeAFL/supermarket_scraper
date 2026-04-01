"""api/main.py - Aplicación FastAPI para el Supermarket Price Tracker.

Ejecutar:
    uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

Docs interactivos:
    http://localhost:8000/docs   (Swagger UI)
    http://localhost:8000/redoc  (ReDoc)
"""

import os
import sys
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Asegurar que el proyecto raíz está en sys.path
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv()

from api.dependencies import cerrar_db
from api.routers import (
    productos,
    precios,
    comparador,
    favoritos,
    listas,
    envios,
    estadisticas,
    rutas,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# ── Rate Limiter ──────────────────────────────────────────────────────

limiter = Limiter(key_func=get_remote_address)

# ── Lifespan (startup / shutdown) ─────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.getLogger(__name__).info("API iniciada.")
    yield
    cerrar_db()
    logging.getLogger(__name__).info("API detenida. Conexión DB cerrada.")

# ── App FastAPI ───────────────────────────────────────────────────────

app = FastAPI(
    title="Supermarket Price Tracker API",
    description=(
        "API REST para consultar precios de supermercados españoles. "
        "Datos de Mercadona, Carrefour, Dia, Alcampo, Eroski, Consum y Condis."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── CORS ──────────────────────────────────────────────────────────────

cors_origins = os.environ.get("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────

app.include_router(estadisticas.router)
app.include_router(productos.router)
app.include_router(precios.router)
app.include_router(comparador.router)
app.include_router(favoritos.router)
app.include_router(listas.router)
app.include_router(envios.router)
app.include_router(rutas.router)


# ── Health check ──────────────────────────────────────────────────────

@app.get("/", tags=["health"])
def root():
    return {"status": "ok", "service": "Supermarket Price Tracker API"}
