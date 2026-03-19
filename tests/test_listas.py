# -*- coding: utf-8 -*-
"""Tests para los métodos de listas y envíos en DatabaseManager.

Usa mocks para evitar dependencia de PostgreSQL real.

    python -m pytest tests/test_listas.py -v
"""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock, PropertyMock
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


# ═════════════════════════════════════════════════════════════════════
# FIXTURES
# ═════════════════════════════════════════════════════════════════════

@pytest.fixture
def mock_db():
    """Crea un DatabaseManager con conexión mockeada."""
    with patch.dict(os.environ, {"DATABASE_URL": "postgresql://fake:5432/test"}):
        with patch("database.database_db_manager.psycopg2") as mock_pg:
            mock_conn = MagicMock()
            mock_pg.connect.return_value = mock_conn
            mock_conn.autocommit = False

            from database.database_db_manager import DatabaseManager
            db = DatabaseManager.__new__(DatabaseManager)
            db._conn = mock_conn

            yield db, mock_conn


def _make_cursor(rows, fetchone_val=None):
    """Helper: crea un mock de cursor con RealDictCursor."""
    cur = MagicMock()
    cur.fetchall.return_value = rows
    cur.fetchone.return_value = fetchone_val
    return cur


# ═════════════════════════════════════════════════════════════════════
# TESTS DE LISTAS — CRUD
# ═════════════════════════════════════════════════════════════════════

class TestCrearLista:

    def test_crear_lista_devuelve_id(self, mock_db):
        db, conn = mock_db
        cur = _make_cursor([], fetchone_val={"id": 42})
        db._cursor = MagicMock(return_value=cur)

        lista_id = db.crear_lista("Compra semanal", "Compra semanal", "")
        assert lista_id == 42
        cur.execute.assert_called_once()
        conn.commit.assert_called()

    def test_crear_lista_con_notas(self, mock_db):
        db, conn = mock_db
        cur = _make_cursor([], fetchone_val={"id": 7})
        db._cursor = MagicMock(return_value=cur)

        lista_id = db.crear_lista("BBQ", "Barbacoa", "traer carbón")
        assert lista_id == 7
        args = cur.execute.call_args[0]
        assert "BBQ" in args[1]
        assert "traer carbón" in args[1]


class TestObtenerListas:

    def test_obtener_listas_con_datos(self, mock_db):
        db, _ = mock_db
        rows = [
            {"id": 1, "nombre": "Semanal", "etiqueta": "Compra semanal",
             "notas": "", "fecha_creacion": "2026-01-01T00:00:00",
             "fecha_actualizacion": "2026-01-02T00:00:00",
             "num_productos": 5, "coste_total": 32.50},
        ]
        cur = _make_cursor(rows)
        db._cursor = MagicMock(return_value=cur)

        df = db.obtener_listas()
        assert not df.empty
        assert len(df) == 1
        assert df.iloc[0]['nombre'] == "Semanal"
        assert df.iloc[0]['num_productos'] == 5

    def test_obtener_listas_vacia(self, mock_db):
        db, _ = mock_db
        cur = _make_cursor([])
        db._cursor = MagicMock(return_value=cur)

        df = db.obtener_listas()
        assert df.empty


class TestObtenerListaDetalle:

    def test_detalle_con_productos(self, mock_db):
        db, _ = mock_db
        rows = [
            {"lista_producto_id": 1, "cantidad": 2, "notas_producto": "",
             "producto_id": 10, "nombre": "Leche", "supermercado": "Mercadona",
             "marca": "Hacendado", "formato_normalizado": "1L",
             "categoria_normalizada": "Lácteos", "url": "", "precio": 0.89},
        ]
        cur = _make_cursor(rows)
        db._cursor = MagicMock(return_value=cur)

        df = db.obtener_lista_detalle(1)
        assert not df.empty
        assert df.iloc[0]['nombre'] == "Leche"
        assert df.iloc[0]['precio'] == 0.89

    def test_detalle_lista_vacia(self, mock_db):
        db, _ = mock_db
        cur = _make_cursor([])
        db._cursor = MagicMock(return_value=cur)

        df = db.obtener_lista_detalle(999)
        assert df.empty


class TestAñadirProductoALista:

    def test_añadir_producto_ok(self, mock_db):
        db, conn = mock_db
        cur = MagicMock()
        db._cursor = MagicMock(return_value=cur)

        ok = db.añadir_producto_a_lista(1, 10, 2)
        assert ok is True
        assert cur.execute.call_count == 2  # INSERT + UPDATE timestamp
        conn.commit.assert_called()

    def test_añadir_producto_error(self, mock_db):
        db, conn = mock_db
        cur = MagicMock()
        cur.execute.side_effect = Exception("FK violation")
        db._cursor = MagicMock(return_value=cur)

        ok = db.añadir_producto_a_lista(1, 99999)
        assert ok is False


class TestQuitarProductoDeLista:

    def test_quitar_producto_ok(self, mock_db):
        db, conn = mock_db
        cur = MagicMock()
        db._cursor = MagicMock(return_value=cur)

        ok = db.quitar_producto_de_lista(1, 10)
        assert ok is True
        assert cur.execute.call_count == 2  # DELETE + UPDATE timestamp
        conn.commit.assert_called()

    def test_quitar_producto_error(self, mock_db):
        db, conn = mock_db
        cur = MagicMock()
        cur.execute.side_effect = Exception("error")
        db._cursor = MagicMock(return_value=cur)

        ok = db.quitar_producto_de_lista(1, 10)
        assert ok is False


class TestActualizarCantidad:

    def test_actualizar_cantidad_ok(self, mock_db):
        db, conn = mock_db
        cur = MagicMock()
        db._cursor = MagicMock(return_value=cur)

        ok = db.actualizar_cantidad_lista(1, 10, 5)
        assert ok is True
        conn.commit.assert_called()

    def test_actualizar_cantidad_error(self, mock_db):
        db, conn = mock_db
        cur = MagicMock()
        cur.execute.side_effect = Exception("error")
        db._cursor = MagicMock(return_value=cur)

        ok = db.actualizar_cantidad_lista(1, 10, 5)
        assert ok is False


class TestEliminarLista:

    def test_eliminar_lista_ok(self, mock_db):
        db, conn = mock_db
        cur = MagicMock()
        db._cursor = MagicMock(return_value=cur)

        ok = db.eliminar_lista(1)
        assert ok is True
        conn.commit.assert_called()

    def test_eliminar_lista_error(self, mock_db):
        db, conn = mock_db
        cur = MagicMock()
        cur.execute.side_effect = Exception("error")
        db._cursor = MagicMock(return_value=cur)

        ok = db.eliminar_lista(1)
        assert ok is False


class TestRenombrarLista:

    def test_renombrar_solo_nombre(self, mock_db):
        db, conn = mock_db
        cur = MagicMock()
        db._cursor = MagicMock(return_value=cur)

        db.renombrar_lista(1, "Nuevo nombre")
        cur.execute.assert_called_once()
        conn.commit.assert_called()
        sql = cur.execute.call_args[0][0]
        assert "nombre" in sql

    def test_renombrar_con_etiqueta_y_notas(self, mock_db):
        db, conn = mock_db
        cur = MagicMock()
        db._cursor = MagicMock(return_value=cur)

        db.renombrar_lista(1, "BBQ", etiqueta="Barbacoa", notas="Sábado")
        params = cur.execute.call_args[0][1]
        assert "BBQ" in params
        assert "Barbacoa" in params
        assert "Sábado" in params


class TestDuplicarLista:

    def test_duplicar_lista_ok(self, mock_db):
        db, conn = mock_db
        cur = MagicMock()

        # Primera llamada: SELECT etiqueta, notas
        # Segunda llamada (dentro de crear_lista): INSERT RETURNING id
        # Tercera: SELECT productos de la lista original
        cur.fetchone.side_effect = [
            {"etiqueta": "Compra semanal", "notas": ""},  # original
            {"id": 99},  # nueva lista
        ]
        cur.fetchall.return_value = [
            {"producto_id": 10, "cantidad": 2, "notas": ""},
            {"producto_id": 20, "cantidad": 1, "notas": "sin gluten"},
        ]
        db._cursor = MagicMock(return_value=cur)

        nuevo_id = db.duplicar_lista(1, "Copia semanal")
        assert nuevo_id == 99
        conn.commit.assert_called()

    def test_duplicar_lista_no_encontrada(self, mock_db):
        db, _ = mock_db
        cur = MagicMock()
        cur.fetchone.return_value = None
        db._cursor = MagicMock(return_value=cur)

        with pytest.raises(ValueError, match="no encontrada"):
            db.duplicar_lista(999, "Copia")


class TestCargarListaEnCesta:

    def test_cargar_lista_con_productos(self, mock_db):
        db, _ = mock_db
        rows = [
            {"lista_producto_id": 1, "cantidad": 3, "notas_producto": "",
             "producto_id": 10, "nombre": "Leche", "supermercado": "Mercadona",
             "marca": "Hacendado", "formato_normalizado": "1L",
             "categoria_normalizada": "Lácteos", "url": "", "precio": 0.89},
            {"lista_producto_id": 2, "cantidad": 1, "notas_producto": "",
             "producto_id": 20, "nombre": "Pan", "supermercado": "Dia",
             "marca": "", "formato_normalizado": "500g",
             "categoria_normalizada": "Panadería", "url": "", "precio": 1.20},
        ]
        cur = _make_cursor(rows)
        db._cursor = MagicMock(return_value=cur)

        cesta = db.cargar_lista_en_cesta(1)
        assert len(cesta) == 2
        assert cesta[0]['producto_id'] == 10
        assert cesta[0]['cantidad'] == 3
        assert cesta[0]['precio'] == 0.89
        assert cesta[0]['alternativa_id'] is None
        assert cesta[1]['nombre'] == "Pan"

    def test_cargar_lista_vacia(self, mock_db):
        db, _ = mock_db
        cur = _make_cursor([])
        db._cursor = MagicMock(return_value=cur)

        cesta = db.cargar_lista_en_cesta(999)
        assert cesta == []


# ═════════════════════════════════════════════════════════════════════
# TESTS DE ENVÍOS (paso 2.4)
# ═════════════════════════════════════════════════════════════════════

class TestObtenerEnvios:

    def test_obtener_envios_con_datos(self, mock_db):
        db, _ = mock_db
        rows = [
            {"id": 1, "supermercado": "Dia", "coste_envio": 3.99,
             "umbral_gratis": 39.0, "pedido_minimo": None,
             "notas": "", "fecha_verificacion": "2026-01-01"},
            {"id": 2, "supermercado": "Mercadona", "coste_envio": 7.70,
             "umbral_gratis": None, "pedido_minimo": 50.0,
             "notas": "", "fecha_verificacion": "2026-01-01"},
        ]
        cur = _make_cursor(rows)
        db._cursor = MagicMock(return_value=cur)

        df = db.obtener_envios()
        assert len(df) == 2
        assert "supermercado" in df.columns

    def test_obtener_envios_vacio(self, mock_db):
        db, _ = mock_db
        cur = _make_cursor([])
        db._cursor = MagicMock(return_value=cur)

        df = db.obtener_envios()
        assert df.empty


class TestObtenerEnvioSupermercado:

    def test_envio_existente(self, mock_db):
        db, _ = mock_db
        row = {"id": 1, "supermercado": "Dia", "coste_envio": 3.99,
               "umbral_gratis": 39.0, "pedido_minimo": None,
               "notas": "Envío gratis a partir de 39€ con Club Dia.",
               "fecha_verificacion": "2026-01-01"}
        cur = _make_cursor([], fetchone_val=row)
        db._cursor = MagicMock(return_value=cur)

        envio = db.obtener_envio_supermercado("Dia")
        assert envio is not None
        assert envio['coste_envio'] == 3.99
        assert envio['umbral_gratis'] == 39.0

    def test_envio_no_existente(self, mock_db):
        db, _ = mock_db
        cur = _make_cursor([], fetchone_val=None)
        db._cursor = MagicMock(return_value=cur)

        envio = db.obtener_envio_supermercado("SuperInventado")
        assert envio is None
