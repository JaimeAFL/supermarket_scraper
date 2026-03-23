# -*- coding: utf-8 -*-

"""
Tests unitarios para matching/normalizer.py

Verifica la extracción de tipo, marca, categoría y formato
para los 5 supermercados soportados.

Ejecutar con:
    python -m pytest tests/test_normalizer.py -v
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from matching.normalizer import normalizar_producto, normalizar_formato, calcular_precio_unitario


# =============================================================================
# TESTS DE NORMALIZAR_FORMATO
# =============================================================================

class TestNormalizarFormato:
    """Tests para la normalización de formato (ml→L, g→kg)."""

    # ── ml → L ────────────────────────────────────────────────────────
    def test_ml_a_litros(self):
        assert normalizar_formato("1000ml") == "1 L"

    def test_ml_grande(self):
        assert normalizar_formato("6000ml") == "6 L"

    def test_ml_decimal(self):
        assert normalizar_formato("990ml") == "0.99 L"

    def test_ml_pequeno(self):
        """330ml se convierte a 0.33 L."""
        assert normalizar_formato("330ml") == "0.33 L"

    # ── cl → L ────────────────────────────────────────────────────────
    def test_cl_a_litros(self):
        assert normalizar_formato("33 cl") == "0.33 L"

    # ── litro/litros → L ─────────────────────────────────────────────
    def test_litro(self):
        assert normalizar_formato("1 litro") == "1 L"

    def test_litros_con_coma(self):
        assert normalizar_formato("1,5 litros") == "1.5 L"

    # ── g → g (o kg si ≥1000) ────────────────────────────────────────
    def test_gramos_bajo(self):
        assert normalizar_formato("390g") == "390 g"

    def test_gramos_a_kg(self):
        assert normalizar_formato("1000g") == "1 kg"

    def test_gramos_a_kg_decimal(self):
        assert normalizar_formato("1500g") == "1.5 kg"

    def test_gramos_a_kg_grande(self):
        assert normalizar_formato("4000g") == "4 kg"

    # ── Pack ──────────────────────────────────────────────────────────
    def test_pack(self):
        result = normalizar_formato("", "AUCHAN Leche entera de vaca 6 x 1 l.")
        assert result == "6 x 1 L"

    def test_pack_eroski(self):
        result = normalizar_formato("4x85 g")
        assert result == "4 x 85 g"

    # ── Formato genérico → extraer del nombre ─────────────────────────
    def test_kilo_extrae_del_nombre(self):
        result = normalizar_formato("KILO", "Leche condensada 450 g")
        assert result == "450 g"

    def test_l_extrae_del_nombre(self):
        result = normalizar_formato("l", "Aceite de oliva 1 l")
        assert result == "1 L"

    def test_vacio_extrae_del_nombre(self):
        result = normalizar_formato("", "Leche entera Carrefour brik 1 l.")
        assert result == "1 L"

    def test_vacio_con_coma_en_nombre(self):
        result = normalizar_formato("", "Leche Carrefour botella 1,5 l.")
        assert result == "1.5 L"

    # ── Sin formato detectable ────────────────────────────────────────
    def test_sin_formato_devuelve_vacio(self):
        result = normalizar_formato("", "Producto sin formato")
        assert result == ""

    def test_formato_no_numerico(self):
        """Formatos como '40 por envase' se convierten a unidades."""
        result = normalizar_formato("40 por envase")
        assert result == "40 ud"

    # ── Unidades ──────────────────────────────────────────────────────
    def test_unidad_simple(self):
        """UNIDAD sin cantidad en nombre → 1 ud."""
        result = normalizar_formato("UNIDAD", "Lechuga iceberg unidad")
        assert result == "1 ud"

    def test_unidad_con_cantidad(self):
        """UNIDAD con cantidad en nombre → N ud."""
        result = normalizar_formato("UNIDAD", "Cogollos 3 unidades")
        assert result == "3 ud"

    def test_ud_raw(self):
        result = normalizar_formato("ud", "Cebolla")
        assert result == "1 ud"

    def test_por_envase(self):
        """'N por envase' de Alcampo → N ud."""
        result = normalizar_formato("12 por envase")
        assert result == "12 ud"

    def test_numero_solo_gramos(self):
        """Número sin unidad (Alcampo granel) → gramos."""
        assert normalizar_formato("500") == "500 g"

    def test_numero_solo_a_kg(self):
        """Número solo ≥1000 → kg."""
        assert normalizar_formato("1000") == "1 kg"

    def test_numero_solo_decimal_kg(self):
        assert normalizar_formato("1500") == "1.5 kg"

    def test_pack_unidades(self):
        """Pack de unidades tipo Eroski."""
        result = normalizar_formato("8x15 ud")
        assert result == "8 x 15 ud"

    def test_unidades_en_nombre(self):
        """20 unidades extraído del nombre."""
        result = normalizar_formato("UNIDAD", "Cápsulas de café 20 unidades")
        assert result == "20 ud"


# =============================================================================
# TESTS DE EXTRACCIÓN POR SUPERMERCADO (Método 1)
# =============================================================================

class TestExtraerAlcampo:
    """Alcampo: MARCA EN MAYÚSCULAS + tipo + formato."""

    def test_marca_y_tipo(self):
        r = normalizar_producto("AUCHAN Leche entera de vaca 1 l.", "Alcampo")
        assert r["marca"] == "AUCHAN"
        assert "leche entera" in r["nombre_normalizado"]

    def test_marca_multi_palabra(self):
        r = normalizar_producto(
            "CENTRAL LECHERA ASTURIANA Leche entera 1 l.", "Alcampo"
        )
        assert "CENTRAL LECHERA ASTURIANA" in r["marca"]

    def test_sin_marca(self):
        """Producto sin marca en mayúsculas → tipo es todo."""
        r = normalizar_producto("Manzana golden bolsa 1 kg", "Alcampo")
        assert r["marca"] == "" or "manzana" in r["nombre_normalizado"]


class TestExtraerEroski:
    """Eroski: tipo + MARCA EN MAYÚSCULAS + , formato."""

    def test_marca_y_tipo(self):
        r = normalizar_producto(
            "Leche entera del País Vasco EROSKI, brik 1 litro", "Eroski"
        )
        assert "EROSKI" in r["marca"]
        assert "leche entera" in r["nombre_normalizado"]

    def test_marca_multi_palabra(self):
        r = normalizar_producto(
            "Yogur natural DANONE ACTIVIA, pack 4x125 g", "Eroski"
        )
        assert "DANONE" in r["marca"] or "ACTIVIA" in r["marca"]

    def test_sin_marca(self):
        r = normalizar_producto("Manzana golden, bolsa 1 kg", "Eroski")
        assert "manzana" in r["nombre_normalizado"]


class TestExtraerGenerico:
    """Mercadona/Carrefour/Dia: tipo + marca (por diccionario)."""

    def test_mercadona_hacendado(self):
        r = normalizar_producto("Leche entera Hacendado", "Mercadona")
        assert r["marca"].upper() == "HACENDADO"
        assert "leche entera" in r["nombre_normalizado"]

    def test_carrefour_marca_en_nombre(self):
        r = normalizar_producto(
            "Leche entera Carrefour brik 1 l.", "Carrefour"
        )
        assert r["marca"].upper() == "CARREFOUR"
        assert "leche entera" in r["nombre_normalizado"]

    def test_dia_marca_en_nombre(self):
        r = normalizar_producto(
            "Leche entera Dia Láctea pack 6 x 1 L", "Dia"
        )
        # "Dia" o "DIA" debería detectarse como marca
        assert r["marca"] != "" or "leche entera" in r["nombre_normalizado"]


# =============================================================================
# TESTS DE TAXONOMÍA (Método 2)
# =============================================================================

class TestCategorizacion:
    """Clasificación automática en categorías normalizadas."""

    @pytest.mark.parametrize("nombre,categoria_esperada", [
        ("Leche entera Hacendado", "Lácteos"),
        ("Yogur natural Danone", "Lácteos"),
        ("Queso manchego", "Lácteos"),
        ("Cerveza Mahou", "Cervezas"),
        ("Café molido Marcilla", "Cafés e infusiones"),
        ("Aceite de oliva virgen extra", "Aceites y vinagres"),
        ("Gel de ducha Nivea", "Higiene personal"),
        ("Detergente líquido Ariel", "Limpieza del hogar"),
        ("Jamón serrano", "Embutidos y fiambres"),
        ("Arroz basmati", "Cereales y legumbres"),
    ])
    def test_categoria_correcta(self, nombre, categoria_esperada):
        r = normalizar_producto(nombre, "Mercadona")
        assert r["categoria_normalizada"] == categoria_esperada, \
            f"'{nombre}' → '{r['categoria_normalizada']}', esperado '{categoria_esperada}'"

    def test_chocolate_no_es_lacteo(self):
        """'Chocolate con leche' debe ser Chocolates, no Lácteos."""
        r = normalizar_producto("Chocolate con leche Hacendado", "Mercadona")
        assert r["categoria_normalizada"] != "Lácteos"

    def test_cafe_con_leche_no_es_lacteo(self):
        """'Café con leche' debe ser Cafés, no Lácteos."""
        r = normalizar_producto("Café con leche soluble", "Mercadona")
        assert r["categoria_normalizada"] == "Cafés e infusiones"

    def test_sin_categoria(self):
        """Productos no alimentarios no deben tener categoría."""
        r = normalizar_producto("Television Samsung 55 pulgadas", "Alcampo")
        assert r["categoria_normalizada"] == ""


# =============================================================================
# TESTS DE FORMATO NORMALIZADO EN normalizar_producto
# =============================================================================

class TestFormatoEnProducto:
    """El formato se normaliza como parte de normalizar_producto()."""

    def test_formato_incluido(self):
        r = normalizar_producto("Leche entera Hacendado", "Mercadona", "1000ml")
        assert r["formato_normalizado"] == "1 L"

    def test_formato_vacio_extrae_del_nombre(self):
        r = normalizar_producto(
            "Leche entera Carrefour brik 1 l.", "Carrefour", ""
        )
        assert r["formato_normalizado"] == "1 L"

    def test_formato_gramos(self):
        r = normalizar_producto("Pan de molde Hacendado", "Mercadona", "500g")
        assert r["formato_normalizado"] == "500 g"


# =============================================================================
# TESTS DE ROBUSTEZ
# =============================================================================

class TestRobustez:
    """Edge cases y entradas inválidas."""

    def test_nombre_vacio(self):
        r = normalizar_producto("", "Mercadona")
        assert r["tipo_producto"] == ""
        assert r["marca"] == ""

    def test_supermercado_vacio(self):
        r = normalizar_producto("Leche entera", "")
        # No debe fallar, usa extracción genérica
        assert r["nombre_normalizado"] != ""

    def test_nombre_none(self):
        r = normalizar_producto(None, "Mercadona")
        assert r["tipo_producto"] == ""

    def test_supermercado_desconocido(self):
        """Un supermercado no reconocido usa extracción genérica."""
        r = normalizar_producto("Leche entera Hacendado", "Lidl")
        assert "leche" in r["nombre_normalizado"]

    def test_formato_none(self):
        r = normalizar_producto("Test producto", "Mercadona", None)
        assert isinstance(r["formato_normalizado"], str)


# =============================================================================
# TESTS DE CALCULAR_PRECIO_UNITARIO
# =============================================================================
#
# Verificación previa (Tarea 3): ningún test_*.py del proyecto usaba
# calcular_precio_unitario() con la firma antigua (devolvía tuple).
# La función devuelve ahora un dict; todos los tests de abajo usan ese formato.
# Los callers de producción (database_db_manager.py, 2_Comparador.py) ya
# acceden mediante calc['clave'] y no necesitan actualización.

class TestCalcularPrecioUnitario:
    """Tests para calcular_precio_unitario() — devuelve un dict con 6 claves.

    Claves del dict:
        precio_venta          (float)       — precio de entrada sin modificar
        precio_referencia     (float|None)  — precio por kg/L/ud para comparar
        unidad_referencia     (str)         — "€/kg", "€/L", "€/ud", "€/m" o ""
        es_pack               (bool)        — True si el formato es N x cantidad
        precio_por_unidad_pack (float|None) — precio de 1 unidad del pack
        unidades_pack         (int|None)    — número de unidades del pack
    """

    # ── Caso 1: producto normal en gramos ────────────────────────────────────
    def test_gramos_calcula_precio_por_kg(self):
        """Cacao 100 g a 2,15 € → precio de referencia 21,50 €/kg.

        El normalizer convierte gramos a kg antes de dividir:
        2,15 / 0,100 kg = 21,50 €/kg.
        """
        r = calcular_precio_unitario(2.15, "100 g")

        assert r['precio_venta'] == pytest.approx(2.15)
        assert r['precio_referencia'] == pytest.approx(21.50)
        assert r['unidad_referencia'] == "€/kg"
        assert r['es_pack'] is False
        assert r['precio_por_unidad_pack'] is None
        assert r['unidades_pack'] is None

    # ── Caso 2: pack de latas ────────────────────────────────────────────────
    def test_pack_latas_detecta_pack_y_calcula_por_litro(self):
        """Pack 6 × 0,33 L a 8,40 € → es_pack=True, 1,40 €/lata, 4,24 €/L.

        El formato "6 x 0.33 L" viene de normalizar_formato("33 cl") aplicado
        a un pack de 6 latas.  El precio por litro se calcula sobre el total:
        8,40 / (6 × 0,33 L) = 8,40 / 1,98 L ≈ 4,24 €/L.
        """
        r = calcular_precio_unitario(8.40, "6 x 0.33 L")

        assert r['precio_venta'] == pytest.approx(8.40)
        assert r['es_pack'] is True
        assert r['unidades_pack'] == 6
        assert r['precio_por_unidad_pack'] == pytest.approx(1.40)
        assert r['precio_referencia'] == pytest.approx(4.24)
        assert r['unidad_referencia'] == "€/L"

    # ── Caso 3: precio_venta == precio_referencia ────────────────────────────
    def test_arroz_1kg_suprime_referencia_redundante(self):
        """Arroz 1 kg a 1,10 € → precio_referencia suprimido por ser igual al precio_venta.

        Para un paquete de exactamente 1 kg el cociente precio/kg coincide
        con el precio de venta.  Como el dato no aporta información adicional
        al usuario, la función lo elimina (precio_referencia=None, unidad='').
        """
        r = calcular_precio_unitario(1.10, "1 kg")

        assert r['precio_venta'] == pytest.approx(1.10)
        assert r['precio_referencia'] is None   # suprimido: igual al precio_venta
        assert r['unidad_referencia'] == ""
        assert r['es_pack'] is False

    # ── Caso 4: sin formato ──────────────────────────────────────────────────
    def test_sin_formato_no_calcula_referencia(self):
        """Producto sin formato → precio_venta conservado, precio_referencia=None.

        Sin información de cantidad/unidad no es posible calcular un precio
        de referencia normalizado (€/kg, €/L…).
        """
        r = calcular_precio_unitario(2.50, "")

        assert r['precio_venta'] == pytest.approx(2.50)
        assert r['precio_referencia'] is None
        assert r['unidad_referencia'] == ""
        assert r['es_pack'] is False

    # ── Casos 5 y 6: precio_unidad_raw del scraper ───────────────────────────
    @pytest.mark.parametrize("raw, descripcion", [
        ("3,50",  "string con coma decimal (formato europeo)"),
        (3.50,    "float directo (ej: Alcampo / Mercadona bulk_price)"),
    ])
    def test_precio_unidad_raw_usa_valor_del_scraper_sin_recalcular(self, raw, descripcion):
        """Cuando el scraper ya provee precio_unidad_raw, se usa directamente.

        El formato "350 g" permitiría CALCULAR 1,75/0,350 = 5,00 €/kg, pero si
        el scraper envía su propio precio de referencia (ej: 3,50 €/kg)
        ese valor tiene prioridad y no se recalcula.

        Cubre: string con coma decimal ("3,50") y float (3.50).
        """
        r = calcular_precio_unitario(1.75, "350 g", raw)

        assert r['precio_venta'] == pytest.approx(1.75)
        assert r['precio_referencia'] == pytest.approx(3.50), (
            f"Se esperaba el valor del scraper (3,50) para input '{raw}' ({descripcion}), "
            f"no el recalculado desde el formato (5,00 €/kg)"
        )
        assert r['unidad_referencia'] == "€/kg"
        assert r['es_pack'] is False

    # ── Caso 7: granel Mercadona, formato "kg" sin cantidad ──────────────────
    def test_granel_formato_kg_con_bulk_price_del_scraper(self):
        """Producto a granel Mercadona: formato "kg", bulk_price separado como raw.

        Tras la corrección de Petición 3, para productos a granel (approx_size=True):
          - precio_venta    = unit_price = precio ESTIMADO por pieza (ej: 1,49 €)
          - precio_unidad_raw = bulk_price = precio de REFERENCIA €/kg (ej: 2,99 €/kg)

        El formato "kg" (standalone, sin cantidad) viene de size_format="kg" de la API
        de Mercadona cuando no se puede determinar la cantidad exacta.
        La función infiere unidad_referencia="€/kg" desde el formato standalone y
        usa bulk_price como precio_referencia porque es diferente a precio_venta.
        """
        r = calcular_precio_unitario(1.49, "kg", 2.99)

        assert r['precio_venta'] == pytest.approx(1.49)
        assert r['precio_referencia'] == pytest.approx(2.99)
        assert r['unidad_referencia'] == "€/kg"
        assert r['es_pack'] is False
        assert r['precio_por_unidad_pack'] is None
        assert r['unidades_pack'] is None

    # ── Robustez ─────────────────────────────────────────────────────────────
    def test_precio_cero_devuelve_dict_vacio(self):
        """Precio cero (o None) → dict con precio_venta=0 y referencias a None."""
        r = calcular_precio_unitario(0, "500 g")

        assert r['precio_venta'] == 0.0
        assert r['precio_referencia'] is None
        assert r['es_pack'] is False

    def test_formato_none_no_falla(self):
        """formato_normalizado=None no debe lanzar excepción."""
        r = calcular_precio_unitario(1.99, None)

        assert r['precio_venta'] == pytest.approx(1.99)
        assert isinstance(r['unidad_referencia'], str)
