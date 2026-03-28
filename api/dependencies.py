"""api/dependencies.py - Dependencias compartidas: DB, autenticación, rate limiting."""

import os
import logging

from fastapi import Depends, HTTPException, Security, Request
from fastapi.security import APIKeyHeader

logger = logging.getLogger(__name__)

# ── Base de datos (singleton) ─────────────────────────────────────────

_db_instance = None


def _get_db_instance():
    """Crea o reutiliza la instancia global de DatabaseManager."""
    global _db_instance
    if _db_instance is None:
        from database.init_db import inicializar_base_datos
        from database.database_db_manager import DatabaseManager
        inicializar_base_datos()
        _db_instance = DatabaseManager()
    return _db_instance


def get_db():
    """Dependencia FastAPI que inyecta DatabaseManager."""
    return _get_db_instance()


def cerrar_db():
    """Cierra la conexión global. Se llama al apagar la app."""
    global _db_instance
    if _db_instance is not None:
        _db_instance.cerrar()
        _db_instance = None
        logger.info("Conexión a DB cerrada.")


# ── Autenticación por API Key ─────────────────────────────────────────

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def _get_valid_keys() -> set[str]:
    raw = os.environ.get("API_KEYS", "")
    return {k.strip() for k in raw.split(",") if k.strip()}


def verify_api_key(api_key: str | None = Security(_api_key_header)):
    """Valida la API key. Si API_KEYS no está configurada, permite todo."""
    valid_keys = _get_valid_keys()
    if not valid_keys:
        return  # sin keys configuradas → acceso libre (desarrollo)
    if not api_key or api_key not in valid_keys:
        raise HTTPException(status_code=401, detail="API key inválida o no proporcionada.")
