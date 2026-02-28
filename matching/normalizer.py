# -*- coding: utf-8 -*-
"""
matching/normalizer.py — Normalización de productos (Método 1+2).

Método 1: Reglas de posición por supermercado para extraer tipo y marca.
Método 2: Taxonomía de categorías a partir del tipo extraído.

Dependencia: matching/marcas.json (junto a este archivo)
"""

import json
import os
import re
import logging
import unicodedata

logger = logging.getLogger(__name__)


def _quitar_acentos(texto):
    nfkd = unicodedata.normalize('NFKD', texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


_MARCAS_PATH = os.path.join(os.path.dirname(__file__), "marcas.json")


def _cargar_marcas():
    try:
        with open(_MARCAS_PATH, encoding="utf-8") as f:
            marcas = json.load(f)
        return sorted(set(marcas), key=len, reverse=True)
    except FileNotFoundError:
        logger.warning("marcas.json no encontrado en %s", _MARCAS_PATH)
        return []


_MARCAS_SORTED = _cargar_marcas()

_RE_FORMATO = re.compile(
    r'[,.]?\s*'
    r'(?:pack\s*(?:de\s*)?)?'
    r'\d+\s*(?:x\s*\d+\s*)?'
    r'(?:[.,]\d+\s*)?'
    r'(?:kg|g|mg|ml|cl|l|litros?|litro|uds?\.?|unidades?|sobres?|'
    r'cápsulas?|capsulas?|latas?|briks?|botellas?|paquetes?|rollos?|'
    r'pastillas?|comprimidos?|tabletas?|tarrinas?|vasos?|cajas?|bolsas?)'
    r'[\s.,]*$',
    re.IGNORECASE,
)

_RE_PRODUCTO_ALCAMPO = re.compile(
    r'\s*[.,]?\s*Producto\s+(?:Económico\s+)?Alcampo\s*$',
    re.IGNORECASE,
)

_EXCL_LECHE_COSMETICA = {
    "corporal", "capilar", "limpiadora", "hidratante", "facial",
    "desmaquillante", "protectora", "solar", "autobronceadora",
    "reafirmante", "anticelulítica", "anticelul",
}

_EXCL_ACEITE_MOTOR = {
    "motor", "sintético", "sintetico", "semi sintético",
    "semi sintetico", "mineral para vehíc", "mineral para vehic",
    "motocicleta", "scooter", "diésel", "diesel",
    "gasolina", "multigrado", "4t ", "2t ",
}

# ═══════════════════════════════════════════════════════════════════════
# TAXONOMÍA — ORDEN: específico antes de genérico
# ═══════════════════════════════════════════════════════════════════════

_TAXONOMIA_RAW = [
    # ── Bebé (antes de Lácteos: "leche de inicio") ──
    (["pañal", "papilla", "potito",
      "leche de inicio", "leche de continuación", "leche de crecimiento",
      "leche infantil", "leche (1)", "leche (2)", "leche (3)", "leche (4)"], "Bebé"),

    # ── Lácteos ──
    (["leche entera", "leche semidesnatada", "leche desnatada",
      "leche sin lactosa", "leche fresca", "leche de vaca",
      "leche fermentada", "leche condensada", "leche evaporada",
      "leche de cabra", "leche de oveja", "leche de pastoreo",
      "leche con omega", "leche con calcio", "leche con zumo",
      "leche en polvo"], "Lácteos"),
    (["yogur", "yoghourt", "kefir", "kéfir", "skyr", "bífidus", "bifidus"], "Lácteos"),
    (["queso ", "quesos", "queso,"], "Lácteos"),
    (["nata ", "nata para", "nata montada", "nata líquida"], "Lácteos"),
    (["mantequilla", "margarina", "materia grasa para untar"], "Lácteos"),
    (["natillas", "flan de", "flan casero", "cuajada", "requesón",
      "arroz con leche", "crema catalana", "mousse de"], "Lácteos"),
    (["batido de cacao", "batido de chocolate", "batido de fresa", "batido de vainilla"], "Lácteos"),

    # ── Bebidas ──
    (["agua mineral", "agua con gas", "agua de mar"], "Bebidas"),
    (["refresco", "bebida de te", "bebida de té", "bebida isotónica",
      "bebida energética", "tónica", "gaseosa", "zumo", "néctar",
      "limonada", "smoothie", "horchata", "tinto de verano",
      "granizado", "red bull"], "Bebidas"),
    (["coca cola", "pepsi", "fanta", "aquarius", "sprite"], "Bebidas"),
    (["bebida de soja", "bebida de avena", "bebida de almendra",
      "bebida de arroz", "bebida de coco", "bebida vegetal",
      "especialidad de soja", "bebida lactea"], "Bebidas vegetales"),
    (["cerveza"], "Cervezas"),
    (["vino ", "vino tinto", "vino blanco", "vino rosado", "cava",
      "champagne", "champán", "sidra", "sangría", "vermouth", "vermut",
      "ginebra", "gin ", "vodka", "whisky", "ron ", "licor", "brandy", "orujo"], "Vinos y licores"),
    (["café ", "café molido", "café en grano", "café soluble",
      "café en cápsulas", "cápsulas de café", "capsulas de cafe",
      "café con leche"], "Cafés e infusiones"),
    (["infusión", "infusion", "té ", "te negro", "te verde",
      "manzanilla", "tila", "poleo", "rooibos", "cacao soluble"], "Cafés e infusiones"),

    # ── Panadería ──
    (["pan ", "pan de molde", "pan integral", "baguette", "panecillos",
      "tostadas", "pan tostado", "hogaza", "chapata", "focaccia",
      "tortita de", "tortilla de trigo", "wrap", "barra de pan",
      "panecillo", "pan bocata", "pan rallado", "picatostes"], "Panadería"),
    (["galletas", "galleta"], "Galletas y bollería"),
    (["magdalena", "bizcocho", "bollo", "bollería", "donut",
      "palmera de", "ensaimada", "berlina", "croissant", "rosquilla",
      "soletilla", "sobaos", "brownie",
      "barritas de cereales", "barrita de cereales", "barrita de chocolate"], "Galletas y bollería"),
    (["arroz ", "cereal", "muesli", "avena ", "granola", "copos de"], "Cereales y legumbres"),
    (["lentejas", "garbanzos", "garbanzo", "alubias", "judías secas"], "Cereales y legumbres"),
    (["pasta ", "espagueti", "spaghetti", "macarron", "macarrones",
      "fideos", "fideo", "tallarines", "lasaña", "canelones",
      "ravioli", "tortellini", "noodles", "penne", "fusilli"], "Pasta"),
    (["harina", "levadura", "sémola", "maicena"], "Harinas y preparados"),
    (["atún ", "atun ", "sardinas", "sardina", "mejillones en",
      "berberechos", "anchoas", "anchoa en", "caballa",
      "bonito del norte", "bonito en"], "Conservas de pescado"),
    (["tomate frito", "tomate triturado", "tomate natural",
      "tomate pelado", "tomate concentrado"], "Conservas vegetales"),
    (["pimientos del piquillo", "espárragos en", "alcachofa",
      "aceitunas", "encurtidos", "pepinillos", "maíz dulce",
      "guisantes en", "menestra de verduras", "alcaparras"], "Conservas vegetales"),
    (["aceite de oliva", "aceite de girasol", "aceite de coco",
      "aceite de sésamo", "aceite vegetal", "aceite oliva"], "Aceites y vinagres"),
    (["vinagre"], "Aceites y vinagres"),
    (["jamón", "jamon", "pechuga de pavo", "pechuga de pollo",
      "lomo embuchado", "lomo adobado", "chorizo", "salchichón",
      "salchichon", "salchicha", "mortadela", "fuet", "sobrasada",
      "bacon", "panceta", "fiambre", "butifarra", "morcilla",
      "longaniza", "chistorra", "paleta de cebo", "paté de", "paté "], "Embutidos y fiambres"),
    (["pollo ", "ternera", "cerdo ", "cordero", "vacuno", "pavo ",
      "hamburguesa", "albóndiga", "carne picada", "carne de",
      "filete de", "solomillo", "entrecot", "chuleta", "costilla",
      "carrillera", "redondo de", "alas de pollo", "muslo de pollo",
      "preparado de carne", "picada de vacuno"], "Carnes"),
    (["merluza", "salmón", "salmon", "bacalao", "pescado", "gamba",
      "langostino", "rape", "lubina", "dorada", "trucha", "surimi",
      "calamar", "pulpo", "sepia", "boquerón", "emperador",
      "lenguado", "taquitos de mar", "palitos de surimi",
      "lomos de merluza"], "Pescados y mariscos"),

    # ═══ MÁS ESPECÍFICOS → ANTES DE GENÉRICOS ═══════════════════
    # "patatas fritas" → Snacks  ANTES de  "patata" → Frutas
    # "tortilla de patata" → Platos  ANTES de  "patata" → Frutas

    (["pizza", "croqueta", "nuggets", "empanadilla", "san jacobo",
      "varitas de merluza", "fingers de",
      "tortilla de patata", "tortilla de patatas",
      "caldo casero", "caldo natural", "sopa de", "crema de verduras",
      "crema de calabacín", "crema de calabaza", "crema de espárrago",
      "puré de", "gazpacho", "salmorejo", "codillo asado",
      "guiso de", "fabada", "garbanzos con", "lentejas con",
      "patatas fritas congeladas"], "Platos preparados"),

    (["patatas fritas", "patatas chip", "patatas onduladas",
      "patatas sabor", "patatas ligeras",
      "snack", "palomitas", "nachos", "frutos secos",
      "pipas ", "cacahuete", "almendras", "nueces ",
      "pistachos", "mix de frutos", "cocktail de frutos",
      "barritas crujientes"], "Snacks y frutos secos"),

    (["helado de", "helado ", "tarrina de helado", "polo de",
      "bombón helado", "bombón almendrado"], "Helados"),

    # ── Frutas y verduras (DESPUÉS de Snacks/Platos) ──
    (["manzana", "plátano", "platano", "naranja", "limón", "limon",
      "fresa ", "uva ", "melocotón", "pera ", "kiwi", "piña ",
      "sandía", "melón", "melon", "cereza", "aguacate", "mango ",
      "papaya", "frambuesa", "arándano", "bolsita de fruta"], "Frutas y verduras"),
    (["tomate ", "tomate cherry", "patata", "cebolla", "ajo ",
      "lechuga", "zanahoria", "pimiento", "calabacín",
      "pepino", "brócoli", "brocoli", "espinaca", "judía verde",
      "champiñón", "seta ", "berenjena", "col ", "coliflor",
      "remolacha", "apio", "rúcula", "canónigo", "ensalada"], "Frutas y verduras"),

    (["huevos"], "Huevos"),
    (["salsa ", "mayonesa", "ketchup", "kétchup", "mostaza",
      "sofrito", "caldo de", "pastillas de caldo"], "Salsas y condimentos"),
    (["sal ", "sal marina", "pimienta", "especias", "orégano",
      "pimentón", "comino", "canela ", "azafrán", "curry", "sazonador"], "Salsas y condimentos"),
    (["azúcar", "azucar", "edulcorante", "sacarina"], "Azúcar y edulcorantes"),
    (["chocolate", "bombón de", "cacao en polvo", "extrafino chocolate"], "Chocolates y cacao"),
    (["mermelada", "miel ", "miel de", "crema de cacao",
      "compota", "dulce de membrillo", "confitura"], "Dulces y untables"),

    # ── Higiene personal ──
    (["gel de ducha", "gel de baño", "champú", "champu", "acondicionador",
      "jabón de manos", "jabón líquido", "desodorante",
      "crema hidratante", "crema facial", "crema de manos",
      "protector solar", "pasta de dientes", "dentífrico", "colutorio",
      "enjuague bucal", "loción corporal", "sérum", "mascarilla capilar",
      "after shave", "espuma de afeitar", "cuchillas de afeitar",
      "maquinilla de afeitar", "maquinilla confort",
      "colonia corporal", "perfume", "eau de toilette", "eau de parfum",
      "contorno de ojos", "desmaquillante", "toallitas",
      "compresa", "tampón", "protegeslip", "tinte ", "coloración",
      "leche limpiadora", "leche corporal", "leche hidratante",
      "leche facial", "leches hidratantes", "leche autobronceadora",
      "perfilador de ojos", "sombra de ojos", "máscara de pestañas",
      "laca de uñas", "pintalabios", "bálsamo labial", "protector labial",
      "crema antiarrugas", "agua de colonia", "agua fresca de",
      "cepillo de dientes", "hilo dental", "colorete", "base de maquillaje"], "Higiene personal"),

    (["detergente", "suavizante", "lavavajillas ", "lejía", "lejia",
      "limpiahogar", "limpiador ", "fregasuelos", "quitagrasa",
      "desinfectante", "estropajo", "bayeta", "fregona", "escoba",
      "papel higiénico", "papel higienico", "papel de cocina",
      "servilleta", "pañuelos de papel", "bolsas de basura",
      "ambientador", "insecticida", "antipolillas", "quitamanchas",
      "guantes de", "recambio mopa", "filtros de café",
      "bolsas de congelación", "film transparente", "papel de aluminio",
      "recambio de fregona", "mopa "], "Limpieza del hogar"),

    (["comida para perro", "comida para gato", "pienso",
      "alimento para perro", "alimento para gato",
      "alimento de pollo", "alimento de salmón", "alimento de buey",
      "alimento de cordero", "alimento de pato", "alimento de atún",
      "alimento seco de", "alimento completo para",
      "alimento húmedo", "comida húmeda para",
      "snack para perro", "snack para gato", "snacks para perro",
      "arena para gato", "comida perro", "comida gato",
      "tartallete de pollo", "tartallete de"], "Mascotas"),

    (["aceite sintético", "aceite semi sintético", "aceite mineral para",
      "aceite motor", "aceite de motor",
      "batería de coche", "anticongelante", "neumático"], "Automoción"),

    (["bombilla", "plancha de vapor", "freidora de aire", "aspirador",
      "secadora por", "lavadora", "microondas", "batidora", "tostador",
      "cafetera", "robot de cocina", "smartphone", "tablet", "portátil",
      "televisor", "auricular", "altavoz", "cargador", "cartucho de tinta",
      "silla de paseo", "almohada de", "edredón", "sábana",
      "vela de cumpleaños"], "Hogar y electrónica"),
]

_TAXONOMIA = []
for _prefijos, _cat in _TAXONOMIA_RAW:
    _TAXONOMIA.append(([_quitar_acentos(p.lower()) for p in _prefijos], _cat))


def _clasificar_tipo(tipo_producto):
    if not tipo_producto:
        return ""
    tipo_norm = _quitar_acentos(tipo_producto.lower().strip())
    if tipo_norm.startswith("leche"):
        for excl in _EXCL_LECHE_COSMETICA:
            if _quitar_acentos(excl) in tipo_norm:
                return "Higiene personal"
    if tipo_norm.startswith("aceite"):
        for excl in _EXCL_ACEITE_MOTOR:
            if _quitar_acentos(excl) in tipo_norm:
                return "Automoción"
    for prefijos, categoria in _TAXONOMIA:
        for prefijo in prefijos:
            if tipo_norm.startswith(prefijo):
                return categoria
    return ""


# ═══════════════════════════════════════════════════════════════════════
# EXTRACCIÓN POR SUPERMERCADO (Método 1)
# ═══════════════════════════════════════════════════════════════════════

def _es_mayusculas(palabra):
    cleaned = re.sub(r'[^a-záéíóúñüàèìòùçA-ZÁÉÍÓÚÑÜÀÈÌÒÙÇ]', '', palabra)
    return len(cleaned) > 1 and cleaned == cleaned.upper()


def _extraer_alcampo(nombre):
    palabras = nombre.split()
    i = 0
    while i < len(palabras):
        p = palabras[i].strip('.,;:()')
        if _es_mayusculas(p) and not p.isdigit():
            i += 1
        else:
            break
    marca = " ".join(palabras[:i]).strip('.,;: ') if i > 0 else ""
    resto = " ".join(palabras[i:]).strip()
    tipo = _RE_FORMATO.sub('', resto).strip().rstrip('.,;: ')
    tipo = _RE_PRODUCTO_ALCAMPO.sub('', tipo).strip()
    return marca, tipo


def _extraer_eroski(nombre):
    partes = nombre.split(',', 1)
    texto = partes[0].strip()
    palabras = texto.split()
    marca_start = len(palabras)
    for i in range(len(palabras) - 1, -1, -1):
        p = palabras[i].strip('.,;:()')
        if _es_mayusculas(p) and p.isalpha() and len(p) > 1:
            marca_start = i
        else:
            break
    if marca_start < len(palabras):
        tipo = " ".join(palabras[:marca_start]).strip()
        marca = " ".join(palabras[marca_start:]).strip()
    else:
        tipo = texto
        marca = ""
    tipo = _RE_FORMATO.sub('', tipo).strip().rstrip('.,;: ')
    return marca, tipo


def _extraer_generico(nombre):
    nombre_upper = nombre.upper()
    for brand in _MARCAS_SORTED:
        brand_upper = brand.upper()
        idx = nombre_upper.find(brand_upper)
        if idx == -1:
            continue
        if idx > 0 and nombre_upper[idx - 1].isalpha():
            continue
        end_idx = idx + len(brand_upper)
        if end_idx < len(nombre_upper) and nombre_upper[end_idx].isalpha():
            continue
        marca = nombre[idx:end_idx]
        tipo_raw = nombre[:idx].strip().rstrip('.,;: ')
        tipo = _RE_FORMATO.sub('', tipo_raw).strip().rstrip('.,;: ')
        if tipo:
            return marca, tipo
    tipo = _RE_FORMATO.sub('', nombre).strip().rstrip('.,;: ')
    return "", tipo


def normalizar_producto(nombre, supermercado):
    """Normaliza un nombre de producto.

    Returns:
        dict: tipo_producto, marca, nombre_normalizado, categoria_normalizada
    """
    nombre = (nombre or "").strip()
    supermercado = (supermercado or "").strip()
    if not nombre:
        return {"tipo_producto": "", "marca": "",
                "nombre_normalizado": "", "categoria_normalizada": ""}

    if supermercado == "Alcampo":
        marca, tipo = _extraer_alcampo(nombre)
    elif supermercado == "Eroski":
        marca, tipo = _extraer_eroski(nombre)
    else:
        marca, tipo = _extraer_generico(nombre)

    nombre_norm = re.sub(r'\s+', ' ', tipo.lower().strip()).rstrip('.,;: ')
    categoria = _clasificar_tipo(tipo)

    return {
        "tipo_producto": tipo,
        "marca": marca,
        "nombre_normalizado": nombre_norm,
        "categoria_normalizada": categoria,
    }
