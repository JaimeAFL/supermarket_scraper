# -*- coding: utf-8 -*-
"""
matching/normalizer.py — Normalización de productos (Método 1+2) + formato.

Dependencia: matching/marcas.json (junto a este archivo)
"""

import json
import os
import re
import logging
import unicodedata

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# UTILIDADES
# ═══════════════════════════════════════════════════════════════════════

def _quitar_acentos(texto):
    nfkd = unicodedata.normalize('NFKD', texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


# ═══════════════════════════════════════════════════════════════════════
# DICCIONARIO DE MARCAS
# ═══════════════════════════════════════════════════════════════════════

_MARCAS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "marcas.json")


def _cargar_marcas():
    try:
        with open(_MARCAS_PATH, encoding="utf-8") as f:
            marcas = json.load(f)
        return sorted(set(marcas), key=len, reverse=True)
    except FileNotFoundError:
        logger.warning("marcas.json no encontrado en %s", _MARCAS_PATH)
        return []


_MARCAS_SORTED = _cargar_marcas()


# ═══════════════════════════════════════════════════════════════════════
# REGEX
# ═══════════════════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════════════════
# NORMALIZACIÓN DE FORMATO
# ═══════════════════════════════════════════════════════════════════════

# Regex para extraer pack: "6 x 1 l", "pack 4 x 125 g"
_RE_FMT_PACK = re.compile(
    r'(?:pack\s*(?:de\s*)?)?'
    r'(\d+)\s*x\s*'
    r'(\d+(?:\.\d+)?)\s*'
    r'(ml|cl|dl|l|litros?|litro|g|gr|kg|mg)\b',
    re.IGNORECASE,
)

# Regex para formato simple: "1000 ml", "1.5 l", "450 g"
_RE_FMT_SIMPLE = re.compile(
    r'(\d+(?:\.\d+)?)\s*'
    r'(ml|cl|dl|l|litros?|litro|g|gr|kg|mg)\b',
    re.IGNORECASE,
)


def normalizar_formato(formato_raw, nombre=""):
    """Normaliza formato a unidades estándar: L (líquidos), kg (sólidos).

    Convierte ml→L, cl→L, dl→L, g≥1000→kg.
    Si formato_raw está vacío o es genérico ("KILO", "l"), extrae del nombre.

    Returns:
        str: "1 L", "0.33 L", "6 x 1 L", "450 g", "1.5 kg", "" si no hay dato
    """
    texto = (formato_raw or "").strip()

    # Formato vacío o solo unidad → extraer del nombre
    if not texto or texto.upper() in ("KILO", "LITRO", "L", "KG"):
        texto = nombre or ""

    if not texto:
        return ""

    # Normalizar coma decimal: "1,5" → "1.5"
    texto_norm = re.sub(r'(\d),(\d)', r'\1.\2', texto)

    # Intentar pack primero, luego simple
    pack_match = _RE_FMT_PACK.search(texto_norm)
    if pack_match:
        pack_n = int(pack_match.group(1))
        cantidad = float(pack_match.group(2))
        unidad = pack_match.group(3).lower()
    else:
        simple_match = _RE_FMT_SIMPLE.search(texto_norm)
        if not simple_match:
            raw = (formato_raw or "").strip()
            return raw if raw and raw.upper() not in ("KILO", "LITRO", "L", "KG") else ""
        pack_n = None
        cantidad = float(simple_match.group(1))
        unidad = simple_match.group(2).lower()

    # ── Convertir a L / kg ──
    if unidad in ('ml',):
        cantidad = round(cantidad / 1000, 4)
        unidad_final = 'L'
    elif unidad in ('cl',):
        cantidad = round(cantidad / 100, 4)
        unidad_final = 'L'
    elif unidad in ('dl',):
        cantidad = round(cantidad / 10, 4)
        unidad_final = 'L'
    elif unidad in ('l', 'litro', 'litros'):
        unidad_final = 'L'
    elif unidad in ('g', 'gr'):
        if cantidad >= 1000:
            cantidad = round(cantidad / 1000, 4)
            unidad_final = 'kg'
        else:
            unidad_final = 'g'
    elif unidad == 'mg':
        unidad_final = 'mg'
    elif unidad == 'kg':
        unidad_final = 'kg'
    else:
        unidad_final = unidad

    # Número limpio: 1.0 → "1", 0.330 → "0.33", 1.500 → "1.5"
    if cantidad == int(cantidad):
        num_str = str(int(cantidad))
    else:
        num_str = f"{cantidad:.4f}".rstrip('0').rstrip('.')

    if pack_n:
        return f"{pack_n} x {num_str} {unidad_final}"
    else:
        return f"{num_str} {unidad_final}"


# ═══════════════════════════════════════════════════════════════════════
# TAXONOMÍA (Método 2)
# ═══════════════════════════════════════════════════════════════════════

_TAXONOMIA_RAW = [
    (["leche entera", "leche semidesnatada", "leche desnatada",
      "leche sin lactosa", "leche fresca", "leche de vaca",
      "leche fermentada", "leche condensada", "leche evaporada",
      "leche de cabra", "leche de oveja"], "Lácteos"),
    (["yogur", "yoghourt", "kefir", "kéfir", "skyr"], "Lácteos"),
    (["queso ", "quesos"], "Lácteos"),
    (["nata ", "nata para", "nata montada", "nata líquida"], "Lácteos"),
    (["mantequilla", "margarina"], "Lácteos"),
    (["natillas", "flan de", "flan casero", "cuajada", "requesón"], "Lácteos"),
    (["agua mineral", "agua con gas"], "Bebidas"),
    (["refresco", "bebida de", "bebida isotónica", "bebida energética",
      "tónica", "gaseosa", "zumo", "néctar", "limonada", "smoothie",
      "horchata"], "Bebidas"),
    (["cerveza"], "Cervezas"),
    (["vino ", "vino tinto", "vino blanco", "vino rosado", "cava",
      "champagne", "champán", "sidra", "sangría", "vermouth", "vermut",
      "ginebra", "gin ", "vodka", "whisky", "ron ", "licor", "brandy",
      "orujo"], "Vinos y licores"),
    (["café ", "café molido", "café en grano", "café soluble",
      "café en cápsulas", "cápsulas de café", "capsulas de cafe",
      "café con leche"], "Cafés e infusiones"),
    (["infusión", "infusion", "té ", "manzanilla", "tila", "poleo",
      "rooibos"], "Cafés e infusiones"),
    (["pan ", "pan de molde", "pan integral", "baguette", "panecillos",
      "tostadas", "pan tostado", "hogaza", "chapata", "focaccia",
      "tortita", "tortilla de trigo", "wrap"], "Panadería"),
    (["galletas", "galleta"], "Galletas y bollería"),
    (["magdalena", "bizcocho", "bollo", "bollería", "donut",
      "palmera", "ensaimada", "berlina", "croissant", "rosquilla",
      "soletilla"], "Galletas y bollería"),
    (["arroz ", "cereal", "muesli", "avena", "granola", "copos de"],
     "Cereales y legumbres"),
    (["lentejas", "garbanzos", "alubias", "judías secas", "frijoles"],
     "Cereales y legumbres"),
    (["pasta ", "espagueti", "macarron", "fideos", "tallarines",
      "lasaña", "canelones", "ravioli", "tortellini", "noodles",
      "spaghetti", "penne", "fusilli", "rigatoni"], "Pasta"),
    (["harina", "levadura", "sémola", "maicena"], "Harinas"),
    (["atún ", "atun ", "sardinas", "mejillones", "berberechos",
      "anchoas", "caballa", "bonito del norte", "bonito en"],
     "Conservas de pescado"),
    (["tomate frito", "tomate triturado", "tomate natural",
      "tomate pelado", "tomate concentrado"], "Conservas vegetales"),
    (["pimientos del piquillo", "espárragos", "alcachofa",
      "aceitunas", "encurtidos", "pepinillos"], "Conservas vegetales"),
    (["aceite de oliva", "aceite de girasol", "aceite de coco",
      "aceite de sésamo", "aceite vegetal"], "Aceites y vinagres"),
    (["vinagre"], "Aceites y vinagres"),
    (["jamón", "jamon", "pechuga de pavo", "pechuga de pollo",
      "lomo embuchado", "lomo adobado", "chorizo", "salchichón",
      "salchichon", "salchicha", "mortadela", "fuet", "sobrasada",
      "bacon", "panceta", "fiambre", "butifarra", "morcilla",
      "longaniza", "chistorra"], "Embutidos y fiambres"),
    (["pollo ", "ternera", "cerdo", "cordero", "vacuno", "pavo ",
      "hamburguesa", "albóndiga", "carne picada", "carne de",
      "filete", "solomillo", "entrecot", "chuleta", "costilla",
      "carrillera", "redondo de", "presa ibérica", "secreto ibérico"],
     "Carnes"),
    (["merluza", "salmón", "salmon", "bacalao", "pescado", "gamba",
      "langostino", "rape", "lubina", "dorada", "trucha", "surimi",
      "calamar", "pulpo", "sepia", "mejillón", "boquerón",
      "emperador", "pez espada", "rodaballo", "lenguado"],
     "Pescados y mariscos"),
    (["manzana", "plátano", "platano", "naranja", "limón", "limon",
      "fresa", "uva", "melocotón", "pera ", "kiwi", "piña",
      "sandía", "melón", "cereza", "aguacate", "mango ", "papaya"],
     "Frutas y verduras"),
    (["tomate ", "tomate cherry", "patata", "cebolla", "ajo ",
      "lechuga", "zanahoria", "pimiento", "calabacín", "calabacin",
      "pepino", "brócoli", "brocoli", "espinaca", "judía verde",
      "champiñón", "seta", "berenjena", "col ", "coliflor",
      "remolacha", "apio", "rúcula", "canónigo", "endibias",
      "ensalada"], "Frutas y verduras"),
    (["pizza", "croqueta", "nuggets", "empanadilla", "san jacobo",
      "varitas de merluza", "fingers"], "Congelados y preparados"),
    (["huevos"], "Huevos"),
    (["salsa ", "mayonesa", "ketchup", "mostaza", "sofrito",
      "caldo de", "pastillas de caldo"], "Salsas y condimentos"),
    (["sal ", "sal marina", "pimienta", "especias", "orégano",
      "pimentón", "comino", "canela", "azafrán", "curry"],
     "Salsas y condimentos"),
    (["azúcar", "azucar", "edulcorante", "sacarina"],
     "Azúcar y edulcorantes"),
    (["chocolate", "bombón", "bombon", "cacao soluble", "cacao en polvo"],
     "Chocolates y cacao"),
    (["mermelada", "miel ", "miel de", "crema de cacao",
      "compota", "dulce de membrillo", "confitura"],
     "Dulces y untables"),
    (["patatas fritas", "patatas chip", "snack", "palomitas",
      "nachos", "frutos secos", "pipas", "cacahuete", "almendras",
      "nueces", "pistachos"], "Snacks y frutos secos"),
    (["gel de ducha", "gel de baño", "champú", "champu", "acondicionador",
      "jabón", "jabon", "desodorante", "crema hidratante", "crema facial",
      "protector solar", "pasta de dientes", "dentífrico", "colutorio",
      "enjuague bucal", "loción", "sérum", "mascarilla capilar",
      "after shave", "espuma de afeitar", "cuchillas", "maquinilla",
      "colonia", "perfume", "eau de toilette", "eau de parfum",
      "crema de manos", "contorno de ojos", "desmaquillante",
      "toallitas", "compresa", "tampón", "protegeslip",
      "tinte ", "coloración"], "Higiene personal"),
    (["detergente", "suavizante", "lavavajillas", "lejía", "lejia",
      "limpiahogar", "limpiador", "fregasuelos", "quitagrasa",
      "desinfectante", "estropajo", "bayeta", "fregona", "escoba",
      "papel higiénico", "papel higienico", "papel de cocina",
      "servilleta", "pañuelos", "panuelos", "bolsas de basura",
      "ambientador", "insecticida", "antipolillas",
      "guantes de", "recambio mopa"], "Limpieza del hogar"),
    (["pañal", "panal", "papilla", "potito",
      "leche de inicio", "leche de continuación", "leche de crecimiento",
      "leche infantil"], "Bebé"),
    (["comida para perro", "comida para gato", "pienso",
      "alimento para perro", "alimento para gato",
      "snacks para perro", "snacks para gato",
      "arena para gato", "comida húmeda"], "Mascotas"),
]

_TAXONOMIA = []
for _prefijos, _cat in _TAXONOMIA_RAW:
    _TAXONOMIA.append(
        ([_quitar_acentos(p.lower()) for p in _prefijos], _cat)
    )


def _clasificar_tipo(tipo_producto):
    if not tipo_producto:
        return ""
    tipo_norm = _quitar_acentos(tipo_producto.lower().strip())
    for prefijos, categoria in _TAXONOMIA:
        for prefijo in prefijos:
            if tipo_norm.startswith(prefijo):
                return categoria
    return ""


# ═══════════════════════════════════════════════════════════════════════
# EXTRACCIÓN POR SUPERMERCADO (Método 1)
# ═══════════════════════════════════════════════════════════════════════

def _extraer_alcampo(nombre):
    palabras = nombre.split()
    i = 0
    while i < len(palabras):
        c = palabras[i].strip('.,;:()[]"\'-')
        if c == c.upper() and len(c) > 0 and not c.isdigit():
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
        c = palabras[i].strip('.,;:()[]"\'-')
        if c == c.upper() and c.isalpha() and len(c) > 1:
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
        brand_upper = brand if brand == brand.upper() else brand.upper()
        idx = nombre_upper.find(brand_upper)
        if idx == -1:
            continue
        if idx > 0 and nombre_upper[idx - 1].isalpha():
            continue
        marca = nombre[idx:idx + len(brand_upper)]
        tipo_raw = nombre[:idx].strip().rstrip('.,;: ')
        tipo = _RE_FORMATO.sub('', tipo_raw).strip().rstrip('.,;: ')
        if tipo:
            return marca, tipo
    tipo = _RE_FORMATO.sub('', nombre).strip().rstrip('.,;: ')
    return "", tipo


# ═══════════════════════════════════════════════════════════════════════
# FUNCIÓN PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════

def normalizar_producto(nombre, supermercado, formato_raw=""):
    """Normaliza un nombre de producto y su formato.

    Returns:
        dict: tipo_producto, marca, nombre_normalizado,
              categoria_normalizada, formato_normalizado
    """
    nombre = (nombre or "").strip()
    supermercado = (supermercado or "").strip()
    if not nombre:
        return {"tipo_producto": "", "marca": "",
                "nombre_normalizado": "", "categoria_normalizada": "",
                "formato_normalizado": ""}

    if supermercado == "Alcampo":
        marca, tipo = _extraer_alcampo(nombre)
    elif supermercado == "Eroski":
        marca, tipo = _extraer_eroski(nombre)
    else:
        marca, tipo = _extraer_generico(nombre)

    nombre_norm = re.sub(r'\s+', ' ', tipo.lower().strip()).rstrip('.,;: ')
    categoria = _clasificar_tipo(tipo)
    formato_norm = normalizar_formato(formato_raw, nombre)

    return {
        "tipo_producto": tipo,
        "marca": marca,
        "nombre_normalizado": nombre_norm,
        "categoria_normalizada": categoria,
        "formato_normalizado": formato_norm,
    }
