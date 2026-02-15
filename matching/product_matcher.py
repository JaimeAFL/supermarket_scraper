# -*- coding: utf-8 -*-

"""
Sistema de equivalencias entre productos de distintos supermercados.

Proporciona dos modos de vinculación:
- Manual: El usuario define directamente qué productos son equivalentes.
- Automático: Usa similitud de texto para sugerir equivalencias.

Ejemplo de uso:
    matcher = ProductMatcher(db)
    
    # Modo manual
    matcher.crear_equivalencia_manual("Coca-Cola 2L", [101, 202, 303])
    
    # Modo automático
    sugerencias = matcher.buscar_equivalencias_auto("Coca-Cola", umbral=75)
"""

import logging
from rapidfuzz import fuzz, process
import pandas as pd

logger = logging.getLogger(__name__)


class ProductMatcher:
    """
    Busca y gestiona equivalencias entre productos de distintos supermercados.
    """

    def __init__(self, db_manager):
        """
        Args:
            db_manager (DatabaseManager): Instancia del gestor de base de datos.
        """
        self.db = db_manager

    # =========================================================================
    # MODO MANUAL
    # =========================================================================

    def crear_equivalencia_manual(self, nombre_comun, lista_producto_ids):
        """
        Crea una equivalencia definida manualmente por el usuario.
        
        Args:
            nombre_comun (str): Nombre descriptivo (ej: "Leche entera 1L").
            lista_producto_ids (list): IDs internos de productos equivalentes.
        """
        self.db.crear_equivalencia(nombre_comun, lista_producto_ids)

    # =========================================================================
    # MODO AUTOMÁTICO
    # =========================================================================

    def buscar_equivalencias_auto(self, nombre_producto, umbral=70, limite=10):
        """
        Busca productos similares en todos los supermercados usando similitud de texto.
        
        Usa el algoritmo token_sort_ratio de RapidFuzz, que es robusto ante
        diferencias de orden en las palabras (ej: "Coca-Cola Zero 2L" vs "2L Coca-Cola Zero").
        
        Args:
            nombre_producto (str): Nombre del producto a buscar.
            umbral (int): Puntuación mínima de similitud (0-100). 70 es un buen punto de partida.
            limite (int): Número máximo de resultados.
        
        Returns:
            pd.DataFrame: Productos similares con columnas: id, nombre, supermercado, puntuacion.
        """
        # Obtener todos los productos de la base de datos
        df_todos = self.db.obtener_productos_con_precio_actual()
        
        if df_todos.empty:
            logger.warning("No hay productos en la base de datos.")
            return pd.DataFrame()

        # Crear lista de nombres para la búsqueda
        nombres = df_todos['nombre'].tolist()

        # Buscar los más similares
        resultados = process.extract(
            nombre_producto,
            nombres,
            scorer=fuzz.token_sort_ratio,
            limit=limite,
            score_cutoff=umbral
        )

        if not resultados:
            logger.info(f"No se encontraron productos similares a '{nombre_producto}' con umbral {umbral}.")
            return pd.DataFrame()

        # Construir DataFrame con resultados
        indices = [r[2] for r in resultados]
        puntuaciones = [r[1] for r in resultados]

        df_resultado = df_todos.iloc[indices][['id', 'nombre', 'supermercado', 'precio']].copy()
        df_resultado['puntuacion'] = puntuaciones
        df_resultado = df_resultado.sort_values('puntuacion', ascending=False)

        return df_resultado

    def sugerir_equivalencias_para_producto(self, producto_id, umbral=70):
        """
        Dado un producto, busca equivalentes en otros supermercados.
        
        Args:
            producto_id (int): ID interno del producto de referencia.
            umbral (int): Puntuación mínima de similitud.
        
        Returns:
            pd.DataFrame: Productos equivalentes sugeridos (de OTROS supermercados).
        """
        # Obtener el producto de referencia
        df_ref = self.db.buscar_productos()
        producto_ref = df_ref[df_ref['id'] == producto_id]
        
        if producto_ref.empty:
            logger.warning(f"Producto con ID {producto_id} no encontrado.")
            return pd.DataFrame()

        nombre = producto_ref.iloc[0]['nombre']
        supermercado_origen = producto_ref.iloc[0]['supermercado']

        # Buscar similares
        df_similares = self.buscar_equivalencias_auto(nombre, umbral=umbral)
        
        if df_similares.empty:
            return pd.DataFrame()

        # Filtrar: solo productos de OTROS supermercados
        df_similares = df_similares[df_similares['supermercado'] != supermercado_origen]

        return df_similares

    def auto_crear_equivalencias(self, umbral=85):
        """
        Intenta crear equivalencias automáticamente para todos los productos.
        Usa un umbral alto (85) para evitar falsos positivos.
        
        Solo crea equivalencias cuando encuentra exactamente un producto
        equivalente por supermercado (para evitar ambigüedades).
        
        Args:
            umbral (int): Puntuación mínima (recomendado >= 85 para auto).
        
        Returns:
            int: Número de equivalencias creadas.
        """
        df_todos = self.db.obtener_productos_con_precio_actual()
        
        if df_todos.empty:
            return 0

        # Agrupar por supermercado
        supermercados = df_todos['supermercado'].unique()
        
        if len(supermercados) < 2:
            logger.info("Se necesitan al menos 2 supermercados para crear equivalencias.")
            return 0

        # Tomar el primer supermercado como referencia
        supermercado_ref = supermercados[0]
        df_ref = df_todos[df_todos['supermercado'] == supermercado_ref]

        equivalencias_creadas = 0

        for _, producto in df_ref.iterrows():
            nombre = producto['nombre']
            ids_equivalentes = [producto['id']]
            
            # Buscar en cada otro supermercado
            for otro_super in supermercados[1:]:
                df_otro = df_todos[df_todos['supermercado'] == otro_super]
                nombres_otro = df_otro['nombre'].tolist()
                
                resultado = process.extractOne(
                    nombre,
                    nombres_otro,
                    scorer=fuzz.token_sort_ratio,
                    score_cutoff=umbral
                )
                
                if resultado:
                    idx = resultado[2]
                    ids_equivalentes.append(df_otro.iloc[idx]['id'])

            # Solo crear si encontramos al menos un equivalente en otro super
            if len(ids_equivalentes) > 1:
                self.db.crear_equivalencia(nombre, ids_equivalentes)
                equivalencias_creadas += 1

        logger.info(f"Equivalencias automáticas creadas: {equivalencias_creadas}")
        return equivalencias_creadas
