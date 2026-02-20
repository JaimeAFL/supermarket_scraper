# -*- coding: utf-8 -*-
"""
Sistema de equivalencias entre productos de distintos supermercados.

Usa búsqueda SQL por palabras clave como método principal (rápido y preciso).
Fuzzy matching (rapidfuzz) se usa solo como refinamiento opcional.
"""

import logging
import pandas as pd

logger = logging.getLogger(__name__)

# Intentar importar rapidfuzz (opcional)
try:
    from rapidfuzz import fuzz, process
    RAPIDFUZZ_DISPONIBLE = True
except ImportError:
    RAPIDFUZZ_DISPONIBLE = False
    logger.info("rapidfuzz no disponible — se usará solo búsqueda SQL.")


class ProductMatcher:
    def __init__(self, db_manager):
        self.db = db_manager

    # ── Manual ────────────────────────────────────────────────────────────────
    def crear_equivalencia_manual(self, nombre_comun, lista_producto_ids):
        self.db.crear_equivalencia(nombre_comun, lista_producto_ids)

    # ── Búsqueda principal: SQL LIKE ──────────────────────────────────────────
    def buscar_equivalencias_auto(self, nombre_producto, umbral=70, limite=30):
        """Busca productos similares usando SQL LIKE por palabras clave.

        Mucho más rápido y preciso que fuzzy matching contra 30K productos.
        Si rapidfuzz está disponible, se usa como segunda pasada para
        puntuar y ordenar los resultados.
        """
        # Paso 1: Búsqueda SQL (rápida, cubre todos los supermercados)
        df = self.db.buscar_para_comparar(nombre_producto, limite_por_super=limite)

        if df.empty:
            logger.info("No se encontraron productos para '%s'.", nombre_producto)
            return pd.DataFrame()

        # Paso 2 (opcional): Puntuar con rapidfuzz si está disponible
        if RAPIDFUZZ_DISPONIBLE:
            df['puntuacion'] = df['nombre'].apply(
                lambda n: fuzz.token_sort_ratio(nombre_producto.lower(), n.lower())
            )
            df = df[df['puntuacion'] >= umbral].sort_values(
                'puntuacion', ascending=False,
            )
        else:
            # Sin rapidfuzz, asignar puntuación básica por coincidencia
            palabras = nombre_producto.lower().split()
            df['puntuacion'] = df['nombre'].apply(
                lambda n: sum(
                    1 for p in palabras if p in n.lower()
                ) / len(palabras) * 100
            )
            df = df.sort_values('puntuacion', ascending=False)

        return df

    # ── Sugerencias para un producto específico ───────────────────────────────
    def sugerir_equivalencias_para_producto(self, producto_id, umbral=60):
        df_ref = self.db.buscar_productos()
        producto_ref = df_ref[df_ref['id'] == producto_id]

        if producto_ref.empty:
            return pd.DataFrame()

        nombre = producto_ref.iloc[0]['nombre']
        supermercado_origen = producto_ref.iloc[0]['supermercado']

        df_similares = self.buscar_equivalencias_auto(nombre, umbral=umbral)

        if df_similares.empty:
            return pd.DataFrame()

        return df_similares[
            df_similares['supermercado'] != supermercado_origen
        ]

    # ── Auto-crear equivalencias ──────────────────────────────────────────────
    def auto_crear_equivalencias(self, umbral=85):
        """Crea equivalencias automáticas para productos con nombre muy similar."""
        if not RAPIDFUZZ_DISPONIBLE:
            logger.warning(
                "rapidfuzz no disponible. "
                "Instala con: pip install rapidfuzz"
            )
            return 0

        df_todos = self.db.obtener_productos_con_precio_actual()
        if df_todos.empty:
            return 0

        supermercados = df_todos['supermercado'].unique()
        if len(supermercados) < 2:
            return 0

        supermercado_ref = supermercados[0]
        df_ref = df_todos[df_todos['supermercado'] == supermercado_ref]

        equivalencias_creadas = 0

        for _, producto in df_ref.iterrows():
            nombre = producto['nombre']
            ids_equivalentes = [producto['id']]

            for otro_super in supermercados[1:]:
                df_otro = df_todos[df_todos['supermercado'] == otro_super]
                nombres_otro = df_otro['nombre'].tolist()

                resultado = process.extractOne(
                    nombre, nombres_otro,
                    scorer=fuzz.token_sort_ratio,
                    score_cutoff=umbral,
                )
                if resultado:
                    idx = resultado[2]
                    ids_equivalentes.append(df_otro.iloc[idx]['id'])

            if len(ids_equivalentes) > 1:
                self.db.crear_equivalencia(nombre, ids_equivalentes)
                equivalencias_creadas += 1

        logger.info("Equivalencias automáticas creadas: %d", equivalencias_creadas)
        return equivalencias_creadas
