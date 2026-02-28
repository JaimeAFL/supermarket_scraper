# -*- coding: utf-8 -*-
"""
matching/product_matcher.py — Matching de productos entre supermercados.

Usa el normalizador para comparar productos por tipo_producto + marca,
con fallback a fuzzy matching si rapidfuzz está disponible.
"""

import logging
import pandas as pd

logger = logging.getLogger(__name__)

try:
    from rapidfuzz import fuzz
    RAPIDFUZZ_DISPONIBLE = True
except ImportError:
    RAPIDFUZZ_DISPONIBLE = False

try:
    from matching.normalizer import normalizar_producto
    NORMALIZER_OK = True
except ImportError:
    NORMALIZER_OK = False


class ProductMatcher:

    def __init__(self, db_manager):
        self.db = db_manager

    def buscar_equivalencias_auto(self, nombre_producto, supermercado=None,
                                  umbral=60, limite=30):
        """Busca productos equivalentes usando normalización + SQL.

        1. Normaliza el producto de entrada para extraer su tipo.
        2. Busca por tipo_producto en la DB (búsqueda precisa).
        3. Opcionalmente puntúa con rapidfuzz para refinar.

        Returns:
            pd.DataFrame con columnas: id, nombre, supermercado, precio,
                                       tipo_producto, marca, puntuacion
        """
        # Paso 1: búsqueda SQL por tipo (rápida, cross-super)
        df = self.db.buscar_para_comparar(nombre_producto, limite_por_super=limite)

        if df.empty:
            return pd.DataFrame()

        # Paso 2: puntuar resultados
        if RAPIDFUZZ_DISPONIBLE:
            query_lower = nombre_producto.lower().strip()
            df['puntuacion'] = df['nombre'].apply(
                lambda n: fuzz.token_sort_ratio(query_lower, n.lower())
            )
            df = df.sort_values('puntuacion', ascending=False)
        else:
            palabras = nombre_producto.lower().split()
            df['puntuacion'] = df['nombre'].apply(
                lambda n: sum(1 for p in palabras if p in n.lower())
                / max(len(palabras), 1) * 100
            )
            df = df.sort_values('puntuacion', ascending=False)

        # Filtrar por supermercado si se pide
        if supermercado:
            df = df[df['supermercado'] != supermercado]

        return df.head(limite * 5)

    def sugerir_equivalencias(self, producto_id, limite=10):
        """Dado un producto existente, sugiere equivalentes en otros supers."""
        cur = self.db._cursor()
        cur.execute(
            "SELECT nombre, supermercado FROM productos WHERE id=?",
            (producto_id,),
        )
        row = cur.fetchone()
        if not row:
            return pd.DataFrame()

        nombre, supermercado = row['nombre'], row['supermercado']

        # Extraer tipo para búsqueda más precisa
        if NORMALIZER_OK:
            norm = normalizar_producto(nombre, supermercado)
            query = norm['tipo_producto'] if norm['tipo_producto'] else nombre
        else:
            query = nombre

        return self.buscar_equivalencias_auto(
            query, supermercado=supermercado, limite=limite
        )
