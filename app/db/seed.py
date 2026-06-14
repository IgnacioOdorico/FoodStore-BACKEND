"""
Super Seed — FoodStore.

Carga completa del sistema con datos de demostración:
  1. Roles, Estados, Formas de pago, Unidades de medida
  2. Usuarios (staff + 3 clientes)
  3. Direcciones de entrega
  4. Categorías (Pizzas, Hamburguesas, Bebidas, Postres, Ensaladas, Acompañamientos)
  5. Ingredientes (~25)
  6. Productos (~25 con imágenes, recetas y stock)
  7. Pedidos demo en distintos estados (para el dashboard)

Uso:
    python -m app.db.seed

Atención: borra datos existentes de pedidos/pagos y los recrea.
"""

import os
from datetime import datetime, timezone, timedelta
from sqlmodel import Session, select, text

from app.core.database import engine, create_all_tables
from app.core.security import hash_password

# ─── Models ───────────────────────────────────────────────────────────────────
from app.modules.usuarios.model import Usuario, Rol, UsuarioRol
from app.modules.direcciones.models import DireccionEntrega
from app.modules.catalogos.models import UnidadMedida, EstadoPedido, FormaPago
from app.modules.categorias.model import Categoria
from app.modules.ingrediente.models import Ingrediente
from app.modules.producto.models import Producto
from app.modules.producto.associations import ProductoCategoria, ProductoIngrediente
from app.modules.pedidos.models import Pedido, DetallePedido, HistorialEstadoPedido
from app.modules.pagos.models import Pago


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _upsert(session: Session, model, key_field: str, key_value, defaults: dict, extra: dict | None = None):
    """Inserta si no existe; si existe lo devuelve. No actualiza columnas."""
    statement = select(model).where(getattr(model, key_field) == key_value)
    existing = session.exec(statement).first()
    if existing:
        return existing
    merged = {**defaults, **(extra or {})}
    obj = model(**merged)
    session.add(obj)
    session.flush()
    return obj


UNSPLASH = "https://images.unsplash.com/photo-{}?w=600&h=400&fit=crop"
PEXELS = "https://images.pexels.com/photos/{0}/pexels-photo-{0}.jpeg?auto=compress&cs=tinysrgb&w=600"

# Fotos reales de Unsplash
FOOD_IMAGES = {
    # Pizzas
    "Pizza Muzzarella":      UNSPLASH.format("1565299624946-b28f40a0ae38"),
    "Pizza Napolitana":      PEXELS.format("1552635"),  # veggie pizza with mushrooms
    "Pizza Fugazzeta":       UNSPLASH.format("1513104890138-7c749659a591"),
    "Pizza Especial":        UNSPLASH.format("1458642849426-cfb724f15ef7"),
    # Hamburguesas
    "Hamburguesa Clásica":   UNSPLASH.format("1568901346375-23c9450c58cd"),
    "Hamburguesa Completa":  UNSPLASH.format("1572802419224-296b0aeee0d9"),
    "Hamburguesa BBQ":       PEXELS.format("1639557"),  # cheeseburger with bacon
    "Hamburguesa Veggie":    PEXELS.format("1639557"),  # same - burger with veggies
    # Bebidas
    "Coca-Cola 500ml":       UNSPLASH.format("1554866585-cd94860890b7"),
    "Coca-Cola Zero 500ml":  UNSPLASH.format("1554866585-cd94860890b7"),
    "Sprite 500ml":          PEXELS.format("4110256"),  # soda can
    "Agua mineral 500ml":    PEXELS.format("327090"),   # pouring water
    "Cerveza Quilmes 473ml": PEXELS.format("11188308"), # beer mug
    "Cerveza Stella Artois 473ml": PEXELS.format("1089931"), # glass of beer
    # Postres
    "Tiramisú":              UNSPLASH.format("1488477181946-6428a0291777"),
    "Flan con dulce de leche": UNSPLASH.format("1556679343-c7306c1976bc"),
    "Cheesecake de frutos rojos": PEXELS.format("1126359"),  # cheesecake with berries
    "Brownie con helado":    PEXELS.format("29727285"), # chocolate brownies
    "Volcán de chocolate":   PEXELS.format("708490"),   # chocolate dessert with icing
    # Ensaladas
    "Ensalada Caesar":       UNSPLASH.format("1546069901-ba9599a7e63c"),
    "Bowl Veggie":           UNSPLASH.format("1512621776951-a57141f2eefd"),
    "Buddha Bowl":           PEXELS.format("29283885"), # quinoa salad bowl
    "Ensalada Griega":       UNSPLASH.format("1490645935967-10de6ba17061"),
    # Acompañamientos
    "Papas fritas":          UNSPLASH.format("1540189549336-e6e99c3679fe"),
    "Aros de cebolla":       UNSPLASH.format("1555939594-58d7cb561ad1"),
    "Papas rústicas con cheddar": UNSPLASH.format("1573080496219-bb080dd4f877"),
    "Bastones de muzzarella": UNSPLASH.format("1615937722923-67f6deaf2cc9"),
}


def img_url(category_key: str, item_name: str) -> str:
    """Devuelve URL de Unsplash para el producto según categoría y nombre."""
    lookup = {
        ("pizza", "Muzzarella"):     "Pizza Muzzarella",
        ("pizza", "Napolitana"):     "Pizza Napolitana",
        ("pizza", "Fugazzeta"):      "Pizza Fugazzeta",
        ("pizza", "Especial"):       "Pizza Especial",
        ("burger", "Clásica"):       "Hamburguesa Clásica",
        ("burger", "Completa"):      "Hamburguesa Completa",
        ("burger", "BBQ"):           "Hamburguesa BBQ",
        ("burger", "Veggie"):        "Hamburguesa Veggie",
        ("bebida", "Coca-Cola 500ml"): "Coca-Cola 500ml",
        ("bebida", "Coca-Cola Zero"):  "Coca-Cola Zero 500ml",
        ("bebida", "Sprite 500ml"):    "Sprite 500ml",
        ("bebida", "Agua mineral"):    "Agua mineral 500ml",
        ("bebida", "Quilmes"):         "Cerveza Quilmes 473ml",
        ("bebida", "Stella Artois"):   "Cerveza Stella Artois 473ml",
        ("postre", "Tiramisú"):        "Tiramisú",
        ("postre", "Flan"):            "Flan con dulce de leche",
        ("postre", "Cheesecake"):      "Cheesecake de frutos rojos",
        ("postre", "Brownie"):         "Brownie con helado",
        ("postre", "Volcán"):          "Volcán de chocolate",
        ("ensalada", "Caesar"):        "Ensalada Caesar",
        ("ensalada", "Bowl Veggie"):   "Bowl Veggie",
        ("ensalada", "Buddha Bowl"):   "Buddha Bowl",
        ("ensalada", "Griega"):        "Ensalada Griega",
        ("acomp", "Papas fritas"):              "Papas fritas",
        ("acomp", "Aros de cebolla"):           "Aros de cebolla",
        ("acomp", "Papas cheddar"):             "Papas rústicas con cheddar",
        ("acomp", "Bastones muzzarella"):       "Bastones de muzzarella",
    }
    key = lookup.get((category_key, item_name))
    if key and key in FOOD_IMAGES:
        return FOOD_IMAGES[key]
    return UNSPLASH.format("1504674900244-2c6f3e4c6c8f")


# ─── Run ──────────────────────────────────────────────────────────────────────

def run() -> None:
    print("=" * 60)
    print("  SUPER SEED - FoodStore Demo")
    print("=" * 60)
    create_all_tables()

    with Session(engine) as session:
        # ─── 1. ROLES ────────────────────────────────────────────────────
        roles_map: dict[str, Rol] = {}
        for r in (
            {"codigo": "ADMIN", "nombre": "Administrador", "descripcion": "Acceso total al sistema"},
            {"codigo": "STOCK", "nombre": "Gestor de Stock", "descripcion": "Stock y disponibilidad"},
            {"codigo": "PEDIDOS", "nombre": "Gestor de Pedidos", "descripcion": "Ventas y comandas"},
            {"codigo": "CLIENT", "nombre": "Cliente", "descripcion": "Usuario final"},
        ):
            roles_map[r["codigo"]] = _upsert(session, Rol, "codigo", r["codigo"], r)
        print("  [OK] Roles")

        # ─── 2. ESTADOS DE PEDIDO ────────────────────────────────────────
        for e in (
            {"codigo": "PENDIENTE", "descripcion": "Pendiente", "orden": 1, "es_terminal": False},
            {"codigo": "CONFIRMADO", "descripcion": "Confirmado", "orden": 2, "es_terminal": False},
            {"codigo": "EN_PREP", "descripcion": "En preparación", "orden": 3, "es_terminal": False},
            {"codigo": "ENTREGADO", "descripcion": "Entregado", "orden": 4, "es_terminal": True},
            {"codigo": "CANCELADO", "descripcion": "Cancelado", "orden": 5, "es_terminal": True},
        ):
            _upsert(session, EstadoPedido, "codigo", e["codigo"], e)
        print("  [OK] Estados de pedido")

        # ─── 3. FORMAS DE PAGO ───────────────────────────────────────────
        for f in (
            {"codigo": "MERCADOPAGO", "descripcion": "MercadoPago", "habilitado": True},
            {"codigo": "EFECTIVO", "descripcion": "Efectivo en local", "habilitado": True},
            {"codigo": "TRANSFERENCIA", "descripcion": "Transferencia bancaria", "habilitado": True},
        ):
            _upsert(session, FormaPago, "codigo", f["codigo"], f)
        print("  [OK] Formas de pago")

        # ─── 4. UNIDADES DE MEDIDA ───────────────────────────────────────
        unidades_map: dict[str, UnidadMedida] = {}
        for u in (
            {"nombre": "kilogramo", "simbolo": "kg", "tipo": "masa"},
            {"nombre": "gramo", "simbolo": "g", "tipo": "masa"},
            {"nombre": "litro", "simbolo": "L", "tipo": "volumen"},
            {"nombre": "mililitro", "simbolo": "mL", "tipo": "volumen"},
            {"nombre": "pieza", "simbolo": "u", "tipo": "unidad"},
            {"nombre": "docena", "simbolo": "doc", "tipo": "unidad"},
        ):
            unidades_map[u["simbolo"]] = _upsert(session, UnidadMedida, "simbolo", u["simbolo"], u)
        print("  [OK] Unidades de medida")

        # ─── 5. USUARIOS ─────────────────────────────────────────────────
        usuarios_data = [
            {"nombre": "Nacho", "apellido": "Admin", "email": "admin@nachopizza.com", "password": "Admin1234!", "rol": "ADMIN"},
            {"nombre": "Gabi", "apellido": "Stock", "email": "stock@nachopizza.com", "password": "Stock1234!", "rol": "STOCK"},
            {"nombre": "Fede", "apellido": "Pedidos", "email": "pedidos@nachopizza.com", "password": "Pedidos1234!", "rol": "PEDIDOS"},
            {"nombre": "Juan", "apellido": "Cliente", "email": "juan@ejemplo.com", "password": "Juan1234!", "rol": "CLIENT"},
            {"nombre": "María", "apellido": "García", "email": "maria@ejemplo.com", "password": "Maria1234!", "rol": "CLIENT"},
            {"nombre": "Carlos", "apellido": "López", "email": "carlos@ejemplo.com", "password": "Carlos1234!", "rol": "CLIENT"},
        ]
        users_map: dict[str, Usuario] = {}
        for u in usuarios_data:
            user = session.exec(select(Usuario).where(Usuario.email == u["email"])).first()
            if not user:
                user = Usuario(
                    nombre=u["nombre"],
                    apellido=u["apellido"],
                    email=u["email"],
                    password_hash=hash_password(u["password"]),
                )
                session.add(user)
                session.flush()
                session.add(UsuarioRol(usuario_id=user.id, rol_codigo=u["rol"]))
            users_map[u["email"]] = user
        juan = users_map["juan@ejemplo.com"]
        maria = users_map["maria@ejemplo.com"]
        carlos = users_map["carlos@ejemplo.com"]
        print(f"  [OK] Usuarios ({len(usuarios_data)})")

        # ─── 6. DIRECCIONES ──────────────────────────────────────────────
        direcciones_data = [
            {"usuario": juan, "alias": "Casa", "linea1": "Av. Siempre Viva 742", "ciudad": "Rosario", "provincia": "Santa Fe", "codigo_postal": "2000", "es_principal": True},
            {"usuario": juan, "alias": "Trabajo", "linea1": "Córdoba 1234, Piso 5", "ciudad": "Rosario", "provincia": "Santa Fe", "codigo_postal": "2000", "es_principal": False},
            {"usuario": maria, "alias": "Departamento", "linea1": "San Martín 456", "ciudad": "Rosario", "provincia": "Santa Fe", "codigo_postal": "2000", "es_principal": True},
            {"usuario": carlos, "alias": "Casa", "linea1": "Buenos Aires 789", "ciudad": "Rosario", "provincia": "Santa Fe", "codigo_postal": "2000", "es_principal": True},
        ]
        direcciones_map: dict[str, DireccionEntrega] = {}
        for d in direcciones_data:
            key = f"{d['usuario'].id}_{d['alias']}"
            addr = session.exec(
                select(DireccionEntrega).where(
                    DireccionEntrega.usuario_id == d["usuario"].id,
                    DireccionEntrega.alias == d["alias"],
                )
            ).first()
            if not addr:
                addr = DireccionEntrega(
                    usuario_id=d["usuario"].id,
                    alias=d["alias"],
                    linea1=d["linea1"],
                    ciudad=d["ciudad"],
                    provincia=d["provincia"],
                    codigo_postal=d["codigo_postal"],
                    es_principal=d["es_principal"],
                )
                session.add(addr)
                session.flush()
            direcciones_map[key] = addr
        dir_juan_casa = direcciones_map[f"{juan.id}_Casa"]
        dir_maria = direcciones_map[f"{maria.id}_Departamento"]
        dir_carlos = direcciones_map[f"{carlos.id}_Casa"]
        print("  [OK] Direcciones")

        # ─── 7. CATEGORÍAS ───────────────────────────────────────────────
        cats_data = [
            {"nombre": "Pizzas", "descripcion": "Pizzas a la piedra artesanales", "imagen_url": UNSPLASH.format("1565299624946-b28f40a0ae38")},
            {"nombre": "Hamburguesas", "descripcion": "Burgers gourmet con purasagna", "imagen_url": UNSPLASH.format("1568901346375-23c9450c58cd")},
            {"nombre": "Bebidas", "descripcion": "Gaseosas, aguas y cervezas bien frías", "imagen_url": UNSPLASH.format("1554866585-cd94860890b7")},
            {"nombre": "Postres", "descripcion": "Repostería artesanal hecha con amor", "imagen_url": UNSPLASH.format("1488477181946-6428a0291777")},
            {"nombre": "Ensaladas", "descripcion": "Bowls saludables y ensaladas frescas", "imagen_url": UNSPLASH.format("1546069901-ba9599a7e63c")},
            {"nombre": "Acompañamientos", "descripcion": "Papas, aros y más", "imagen_url": UNSPLASH.format("1540189549336-e6e99c3679fe")},
        ]
        cats_map: dict[str, Categoria] = {}
        for c in cats_data:
            cats_map[c["nombre"]] = _upsert(session, Categoria, "nombre", c["nombre"], c)
        print("  [OK] Categorías")

        # ─── 8. INGREDIENTES ─────────────────────────────────────────────
        ings_data = [
            # Pizzas
            {"nombre": "Harina 0000", "descripcion": "Harina de trigo 0000", "es_alergeno": True},
            {"nombre": "Muzzarella", "descripcion": "Queso muzzarella fresco", "es_alergeno": True},
            {"nombre": "Tomate perita", "descripcion": "Tomate perita fresco", "es_alergeno": False},
            {"nombre": "Jamón cocido", "descripcion": "Jamón cocido natural", "es_alergeno": False},
            {"nombre": "Cebolla", "descripcion": "Cebolla criolla", "es_alergeno": False},
            {"nombre": "Morrón", "descripcion": "Morrón rojo asado", "es_alergeno": False},
            # Hamburguesas
            {"nombre": "Medallón de carne", "descripcion": "Medallón de carne vacuna 150g", "es_alergeno": False},
            {"nombre": "Pan de hamburguesa", "descripcion": "Pan de papa artesanal", "es_alergeno": True},
            {"nombre": "Lechuga", "descripcion": "Lechuga criolla fresca", "es_alergeno": False},
            {"nombre": "Queso cheddar", "descripcion": "Queso cheddar en fetas", "es_alergeno": True},
            {"nombre": "Bacon", "descripcion": "Panceta ahumada", "es_alergeno": False},
            {"nombre": "Medallón veggie", "descripcion": "Medallón de lentejas y quinoa", "es_alergeno": False},
            # Bebidas
            {"nombre": "Coca-Cola 500ml", "descripcion": "Botella descartable 500ml", "es_alergeno": False},
            {"nombre": "Coca-Cola Zero 500ml", "descripcion": "Botella descartable 500ml sin azúcar", "es_alergeno": False},
            {"nombre": "Sprite 500ml", "descripcion": "Botella descartable 500ml", "es_alergeno": False},
            {"nombre": "Agua mineral 500ml", "descripcion": "Botella descartable 500ml", "es_alergeno": False},
            {"nombre": "Cerveza Quilmes 473ml", "descripcion": "Lata 473ml", "es_alergeno": True},
            {"nombre": "Cerveza Stella 473ml", "descripcion": "Lata 473ml importada", "es_alergeno": True},
            # Postres
            {"nombre": "Mascarpone", "descripcion": "Queso mascarpone italiano", "es_alergeno": True},
            {"nombre": "Café", "descripcion": "Café expreso", "es_alergeno": False},
            {"nombre": "Vainillas", "descripcion": "Vainillas tradicionales", "es_alergeno": True},
            {"nombre": "Leche entera", "descripcion": "Leche entera fresca", "es_alergeno": True},
            {"nombre": "Huevos", "descripcion": "Huevos de campo", "es_alergeno": True},
            {"nombre": "Dulce de leche", "descripcion": "Dulce de leche repostero", "es_alergeno": True},
            {"nombre": "Queso crema", "descripcion": "Queso crema tipo Philadelphia", "es_alergeno": True},
            {"nombre": "Frutos rojos", "descripcion": "Mix de frutos rojos congelados", "es_alergeno": False},
            {"nombre": "Galletita dulce", "descripcion": "Galletita de vainilla tipo María", "es_alergeno": True},
            {"nombre": "Chocolate 70%", "descripcion": "Chocolate amargo 70% cacao", "es_alergeno": True},
            {"nombre": "Helado crema", "descripcion": "Helado de crema americana", "es_alergeno": True},
            {"nombre": "Nueces", "descripcion": "Nueces peladas", "es_alergeno": True},
            {"nombre": "Manteca", "descripcion": "Manteca sin sal", "es_alergeno": True},
            # Ensaladas
            {"nombre": "Pechuga de pollo", "descripcion": "Pechuga de pollo grillada", "es_alergeno": False},
            {"nombre": "Croutons", "descripcion": "Cuadraditos de pan tostado", "es_alergeno": True},
            {"nombre": "Queso parmesano", "descripcion": "Queso parmesano rallado", "es_alergeno": True},
            {"nombre": "Quinoa", "descripcion": "Quinoa cocida", "es_alergeno": False},
            {"nombre": "Palta", "descripcion": "Palta fresca", "es_alergeno": False},
            {"nombre": "Pepino", "descripcion": "Pepino fresco", "es_alergeno": False},
            {"nombre": "Arroz integral", "descripcion": "Arroz integral cocido", "es_alergeno": False},
            {"nombre": "Garbanzos", "descripcion": "Garbanzos cocidos", "es_alergeno": False},
            {"nombre": "Batata", "descripcion": "Batata asada", "es_alergeno": False},
            {"nombre": "Queso feta", "descripcion": "Queso feta griego", "es_alergeno": True},
            {"nombre": "Aceitunas negras", "descripcion": "Aceitunas negras descarozadas", "es_alergeno": False},
            # Acompañamientos
            {"nombre": "Papa", "descripcion": "Papa blanca", "es_alergeno": False},
            {"nombre": "Pan rallado", "descripcion": "Pan rallado fino", "es_alergeno": True},
        ]

        ings_map: dict[str, Ingrediente] = {}
        for i in ings_data:
            ing = session.exec(select(Ingrediente).where(Ingrediente.nombre == i["nombre"])).first()
            if not ing:
                ing = Ingrediente(**i)
                session.add(ing)
                session.flush()
            ings_map[i["nombre"]] = ing
        print(f"  [OK] Ingredientes ({len(ings_data)})")

        # ─── 9. PRODUCTOS ────────────────────────────────────────────────

        productos_data = [
            # ── PIZZAS ──
            {
                "nombre": "Pizza Muzzarella",
                "descripcion": "Pizza grande a la piedra con muzarella fresca y salsa de tomate.",
                "precio": 8500.0, "stock": 25,
                "categoria": "Pizzas", "img": img_url("pizza", "Muzzarella"),
                "receta": [("Harina 0000", 250.0, "g"), ("Muzzarella", 200.0, "g"), ("Tomate perita", 2.0, "u")],
            },
            {
                "nombre": "Pizza Napolitana",
                "descripcion": "Pizza grande con muzarella, jamón cocido y rodajas de tomate fresco.",
                "precio": 9500.0, "stock": 20,
                "categoria": "Pizzas", "img": img_url("pizza", "Napolitana"),
                "receta": [("Harina 0000", 250.0, "g"), ("Muzzarella", 200.0, "g"), ("Tomate perita", 2.0, "u"), ("Jamón cocido", 100.0, "g")],
            },
            {
                "nombre": "Pizza Fugazzeta",
                "descripcion": "Pizza grande cubierta de muzarella y cebolla, bien argentina.",
                "precio": 9200.0, "stock": 22,
                "categoria": "Pizzas", "img": img_url("pizza", "Fugazzeta"),
                "receta": [("Harina 0000", 250.0, "g"), ("Muzzarella", 250.0, "g"), ("Cebolla", 150.0, "g")],
            },
            {
                "nombre": "Pizza Especial",
                "descripcion": "Pizza grande con muzarella, jamón, morrones asados y aceitunas.",
                "precio": 10500.0, "stock": 18,
                "categoria": "Pizzas", "img": img_url("pizza", "Especial"),
                "receta": [("Harina 0000", 250.0, "g"), ("Muzzarella", 200.0, "g"), ("Tomate perita", 2.0, "u"), ("Jamón cocido", 100.0, "g"), ("Morrón", 80.0, "g")],
            },
            # ── HAMBURGUESAS ──
            {
                "nombre": "Hamburguesa Clásica",
                "descripcion": "Hamburguesa con medallón de carne, lechuga, tomate y mayonesa.",
                "precio": 6200.0, "stock": 30,
                "categoria": "Hamburguesas", "img": img_url("burger", "Clásica"),
                "receta": [("Medallón de carne", 1.0, "u"), ("Pan de hamburguesa", 1.0, "u"), ("Tomate perita", 1.0, "u"), ("Lechuga", 50.0, "g")],
            },
            {
                "nombre": "Hamburguesa Completa",
                "descripcion": "Doble medallón, cheddar, lechuga, tomate y huevo.",
                "precio": 7800.0, "stock": 28,
                "categoria": "Hamburguesas", "img": img_url("burger", "Completa"),
                "receta": [("Medallón de carne", 2.0, "u"), ("Pan de hamburguesa", 1.0, "u"), ("Queso cheddar", 50.0, "g"), ("Lechuga", 50.0, "g"), ("Tomate perita", 1.0, "u")],
            },
            {
                "nombre": "Hamburguesa BBQ",
                "descripcion": "Medallón de carne, cheddar, bacon crocante, cebolla caramelizada y salsa BBQ.",
                "precio": 8500.0, "stock": 25,
                "categoria": "Hamburguesas", "img": img_url("burger", "BBQ"),
                "receta": [("Medallón de carne", 1.0, "u"), ("Pan de hamburguesa", 1.0, "u"), ("Queso cheddar", 50.0, "g"), ("Bacon", 50.0, "g"), ("Cebolla", 50.0, "g")],
            },
            {
                "nombre": "Hamburguesa Veggie",
                "descripcion": "Medallón de lentejas y quinoa, lechuga, tomate y salsa criolla.",
                "precio": 7200.0, "stock": 20,
                "categoria": "Hamburguesas", "img": img_url("burger", "Veggie"),
                "receta": [("Medallón veggie", 1.0, "u"), ("Pan de hamburguesa", 1.0, "u"), ("Lechuga", 50.0, "g"), ("Tomate perita", 1.0, "u")],
            },
            # ── BEBIDAS ──
            {
                "nombre": "Coca-Cola 500ml", "descripcion": "Gaseosa Coca-Cola 500ml.",
                "precio": 1500.0, "stock": 50, "unidad": "u",
                "categoria": "Bebidas", "img": img_url("bebida", "Coca-Cola 500ml"),
                "receta": [("Coca-Cola 500ml", 1.0, "u")],
            },
            {
                "nombre": "Coca-Cola Zero 500ml", "descripcion": "Gaseosa Coca-Cola sin azúcar 500ml.",
                "precio": 1500.0, "stock": 45, "unidad": "u",
                "categoria": "Bebidas", "img": img_url("bebida", "Coca-Cola Zero"),
                "receta": [("Coca-Cola Zero 500ml", 1.0, "u")],
            },
            {
                "nombre": "Sprite 500ml", "descripcion": "Gaseosa Sprite 500ml.",
                "precio": 1500.0, "stock": 45, "unidad": "u",
                "categoria": "Bebidas", "img": img_url("bebida", "Sprite 500ml"),
                "receta": [("Sprite 500ml", 1.0, "u")],
            },
            {
                "nombre": "Agua mineral 500ml", "descripcion": "Agua mineral sin gas 500ml.",
                "precio": 1200.0, "stock": 60, "unidad": "u",
                "categoria": "Bebidas", "img": img_url("bebida", "Agua mineral"),
                "receta": [("Agua mineral 500ml", 1.0, "u")],
            },
            {
                "nombre": "Cerveza Quilmes 473ml", "descripcion": "Cerveza Quilmes lager 473ml.",
                "precio": 2500.0, "stock": 40, "unidad": "u",
                "categoria": "Bebidas", "img": img_url("bebida", "Quilmes"),
                "receta": [("Cerveza Quilmes 473ml", 1.0, "u")],
            },
            {
                "nombre": "Cerveza Stella Artois 473ml", "descripcion": "Cerveza Stella Artois importada 473ml.",
                "precio": 3200.0, "stock": 35, "unidad": "u",
                "categoria": "Bebidas", "img": img_url("bebida", "Stella Artois"),
                "receta": [("Cerveza Stella 473ml", 1.0, "u")],
            },
            # ── POSTRES ──
            {
                "nombre": "Tiramisú",
                "descripcion": "Tiramisú italiano con mascarpone, café y cacao.",
                "precio": 4500.0, "stock": 15,
                "categoria": "Postres", "img": img_url("postre", "Tiramisú"),
                "receta": [("Mascarpone", 200.0, "g"), ("Café", 50.0, "mL"), ("Vainillas", 100.0, "g")],
            },
            {
                "nombre": "Flan con dulce de leche",
                "descripcion": "Flan casero con dulce de leche y crema.",
                "precio": 3800.0, "stock": 18,
                "categoria": "Postres", "img": img_url("postre", "Flan"),
                "receta": [("Leche entera", 200.0, "mL"), ("Huevos", 2.0, "u"), ("Dulce de leche", 80.0, "g")],
            },
            {
                "nombre": "Cheesecake de frutos rojos",
                "descripcion": "Cheesecake horneado con topping de frutos rojos.",
                "precio": 4200.0, "stock": 12,
                "categoria": "Postres", "img": img_url("postre", "Cheesecake"),
                "receta": [("Queso crema", 200.0, "g"), ("Frutos rojos", 80.0, "g"), ("Galletita dulce", 100.0, "g")],
            },
            {
                "nombre": "Brownie con helado",
                "descripcion": "Brownie caliente con helado de crema y nueces.",
                "precio": 4800.0, "stock": 14,
                "categoria": "Postres", "img": img_url("postre", "Brownie"),
                "receta": [("Chocolate 70%", 150.0, "g"), ("Helado crema", 100.0, "g"), ("Nueces", 50.0, "g")],
            },
            {
                "nombre": "Volcán de chocolate",
                "descripcion": "Volcán de chocolate amargo con centro líquido, helado y frutas.",
                "precio": 5200.0, "stock": 10,
                "categoria": "Postres", "img": img_url("postre", "Volcán"),
                "receta": [("Chocolate 70%", 200.0, "g"), ("Manteca", 100.0, "g"), ("Huevos", 2.0, "u")],
            },
            # ── ENSALADAS ──
            {
                "nombre": "Ensalada Caesar",
                "descripcion": "Ensalada Caesar clásica con pollo grillado, croutons y parmesano.",
                "precio": 5500.0, "stock": 20,
                "categoria": "Ensaladas", "img": img_url("ensalada", "Caesar"),
                "receta": [("Lechuga", 200.0, "g"), ("Pechuga de pollo", 150.0, "g"), ("Croutons", 50.0, "g"), ("Queso parmesano", 30.0, "g")],
            },
            {
                "nombre": "Bowl Veggie",
                "descripcion": "Bowl de quinoa con palta, tomate, pepino y dressing de limón.",
                "precio": 6200.0, "stock": 18,
                "categoria": "Ensaladas", "img": img_url("ensalada", "Bowl Veggie"),
                "receta": [("Quinoa", 150.0, "g"), ("Palta", 100.0, "g"), ("Tomate perita", 100.0, "g"), ("Pepino", 80.0, "g")],
            },
            {
                "nombre": "Buddha Bowl",
                "descripcion": "Bowl de arroz integral con garbanzos, palta, batata asada y tahini.",
                "precio": 6800.0, "stock": 15,
                "categoria": "Ensaladas", "img": img_url("ensalada", "Buddha Bowl"),
                "receta": [("Arroz integral", 150.0, "g"), ("Garbanzos", 100.0, "g"), ("Palta", 80.0, "g"), ("Batata", 100.0, "g")],
            },
            {
                "nombre": "Ensalada Griega",
                "descripcion": "Ensalada griega con queso feta, tomate, pepino, aceitunas y orégano.",
                "precio": 5800.0, "stock": 18,
                "categoria": "Ensaladas", "img": img_url("ensalada", "Griega"),
                "receta": [("Lechuga", 150.0, "g"), ("Tomate perita", 100.0, "g"), ("Pepino", 80.0, "g"), ("Queso feta", 80.0, "g"), ("Aceitunas negras", 30.0, "g")],
            },
            # ── ACOMPAÑAMIENTOS ──
            {
                "nombre": "Papas fritas",
                "descripcion": "Papas fritas crocantes con sal marina.",
                "precio": 3500.0, "stock": 40,
                "categoria": "Acompañamientos", "img": img_url("acomp", "Papas fritas"),
                "receta": [("Papa", 300.0, "g")],
            },
            {
                "nombre": "Aros de cebolla",
                "descripcion": "Aros de cebolla empanizados, fritos y crujientes.",
                "precio": 3800.0, "stock": 35,
                "categoria": "Acompañamientos", "img": img_url("acomp", "Aros de cebolla"),
                "receta": [("Cebolla", 200.0, "g"), ("Harina 0000", 100.0, "g")],
            },
            {
                "nombre": "Papas rústicas con cheddar",
                "descripcion": "Papas rústicas horneadas con queso cheddar derretido y bacon.",
                "precio": 4200.0, "stock": 30,
                "categoria": "Acompañamientos", "img": img_url("acomp", "Papas cheddar"),
                "receta": [("Papa", 300.0, "g"), ("Queso cheddar", 80.0, "g")],
            },
            {
                "nombre": "Bastones de muzzarella",
                "descripcion": "Bastones de muzzarella empanizados fritos con salsa marinara.",
                "precio": 4500.0, "stock": 25,
                "categoria": "Acompañamientos", "img": img_url("acomp", "Bastones muzzarella"),
                "receta": [("Muzzarella", 200.0, "g"), ("Pan rallado", 100.0, "g")],
            },
        ]

        for p in productos_data:
            prod = session.exec(select(Producto).where(Producto.nombre == p["nombre"])).first()
            if prod:
                continue
            unidad = unidades_map.get(p.get("unidad", "")) if p.get("unidad") else None
            prod = Producto(
                nombre=p["nombre"],
                descripcion=p["descripcion"],
                precio_base=p["precio"],
                stock_cantidad=p["stock"],
                disponible=True,
                imagenes_url=[p["img"]],
                unidad_venta_id=unidad.id if unidad else None,
            )
            session.add(prod)
            session.flush()

            # Asociar categoría
            session.add(ProductoCategoria(
                producto_id=prod.id,
                categoria_id=cats_map[p["categoria"]].id,
                es_principal=True,
            ))

            # Receta
            removibles = {"Tomate perita", "Cebolla", "Lechuga", "Bacon", "Croutons"}
            for ing_nombre, cant, unidad_simb in p["receta"]:
                session.add(ProductoIngrediente(
                    producto_id=prod.id,
                    ingrediente_id=ings_map.get(ing_nombre).id,
                    cantidad=cant,
                    unidad_medida_id=unidades_map[unidad_simb].id,
                    es_removible=(ing_nombre in removibles),
                ))
        print(f"  [OK] Productos ({len(productos_data)})")

        # ─── 10. PEDIDOS DEMO ─────────────────────────────────────────────

        # Limpia pedidos/pagos existentes para regenerarlos (sin tocar catálogos)
        session.exec(text("DELETE FROM pago"))
        session.exec(text("DELETE FROM historial_estado_pedido"))
        session.exec(text("DELETE FROM detalle_pedido"))
        session.exec(text("DELETE FROM pedido"))
        session.flush()

        # Helper para crear pedidos con fechas relativas
        def make_pedido(
            usuario: Usuario,
            direccion: DireccionEntrega,
            items: list[tuple[str, int]],  # (producto_nombre, cantidad)
            estado: str,
            forma_pago: str,
            horas_atras: int = 0,
            notas: str | None = None,
        ):
            detalles = []
            subtotal = 0.0
            for prod_nombre, cant in items:
                prod = session.exec(select(Producto).where(Producto.nombre == prod_nombre)).first()
                if not prod:
                    print(f"  ⚠️  Producto '{prod_nombre}' no encontrado, saltando")
                    continue
                subtotal += prod.precio_base * cant
                detalles.append((prod, cant))

            if not detalles:
                return None

            costo_envio = 500.0
            total = subtotal + costo_envio
            ahora = datetime.now(timezone.utc) - timedelta(hours=horas_atras)

            pedido = Pedido(
                usuario_id=usuario.id,
                direccion_id=direccion.id,
                estado_codigo=estado,
                forma_pago_codigo=forma_pago,
                subtotal=subtotal,
                descuento=0.0,
                costo_envio=costo_envio,
                total=total,
                notas=notas or "",
                created_at=ahora,
                updated_at=ahora,
            )
            session.add(pedido)
            session.flush()

            for prod, cant in detalles:
                session.add(DetallePedido(
                    pedido_id=pedido.id,
                    producto_id=prod.id,
                    cantidad=cant,
                    nombre_snapshot=prod.nombre,
                    precio_snapshot=prod.precio_base,
                    subtotal_snap=prod.precio_base * cant,
                    personalizacion=None,
                ))

            # Historial — estado inicial
            session.add(HistorialEstadoPedido(
                pedido_id=pedido.id,
                estado_desde=None,
                estado_hacia=estado,
                usuario_id=usuario.id,
                motivo="Creación del pedido" + (" (seed)" if not horas_atras else ""),
                created_at=ahora,
            ))

            return pedido

        # ── Pedidos de Juan ──
        make_pedido(juan, dir_juan_casa,
            [("Pizza Muzzarella", 1), ("Coca-Cola 500ml", 2)],
            estado="PENDIENTE", forma_pago="MERCADOPAGO", horas_atras=0,
            notas="Sin cebolla, por favor",
        )

        make_pedido(juan, dir_juan_casa,
            [("Hamburguesa Clásica", 2), ("Papas fritas", 1), ("Coca-Cola Zero 500ml", 2)],
            estado="ENTREGADO", forma_pago="EFECTIVO", horas_atras=72,
        )

        make_pedido(juan, dir_juan_casa,
            [("Pizza Especial", 1), ("Cerveza Quilmes 473ml", 2), ("Flan con dulce de leche", 1)],
            estado="ENTREGADO", forma_pago="MERCADOPAGO", horas_atras=48,
        )

        make_pedido(juan, dir_juan_casa,
            [("Hamburguesa Completa", 1), ("Papas rústicas con cheddar", 1), ("Sprite 500ml", 1)],
            estado="ENTREGADO", forma_pago="TRANSFERENCIA", horas_atras=24,
        )

        make_pedido(juan, dir_juan_casa,
            [("Pizza Fugazzeta", 1), ("Cerveza Stella Artois 473ml", 1)],
            estado="CANCELADO", forma_pago="MERCADOPAGO", horas_atras=36,
        )

        make_pedido(juan, dir_juan_casa,
            [("Tiramisú", 1), ("Brownie con helado", 1)],
            estado="ENTREGADO", forma_pago="MERCADOPAGO", horas_atras=12,
        )

        # ── Pedidos de María ──
        make_pedido(maria, dir_maria,
            [("Bowl Veggie", 1), ("Agua mineral 500ml", 1)],
            estado="PENDIENTE", forma_pago="MERCADOPAGO", horas_atras=1,
        )

        make_pedido(maria, dir_maria,
            [("Ensalada Caesar", 1), ("Tiramisú", 1), ("Sprite 500ml", 1)],
            estado="ENTREGADO", forma_pago="EFECTIVO", horas_atras=96,
        )

        make_pedido(maria, dir_maria,
            [("Buddha Bowl", 1), ("Volcán de chocolate", 1), ("Agua mineral 500ml", 1)],
            estado="ENTREGADO", forma_pago="MERCADOPAGO", horas_atras=36,
        )

        make_pedido(maria, dir_maria,
            [("Hamburguesa Veggie", 1), ("Papas fritas", 1)],
            estado="CANCELADO", forma_pago="MERCADOPAGO", horas_atras=12,
        )

        # ── Pedidos de Carlos ──
        make_pedido(carlos, dir_carlos,
            [("Hamburguesa BBQ", 2), ("Papas rústicas con cheddar", 1), ("Cerveza Stella Artois 473ml", 2)],
            estado="CONFIRMADO", forma_pago="MERCADOPAGO", horas_atras=4,
        )

        make_pedido(carlos, dir_carlos,
            [("Pizza Napolitana", 1), ("Aros de cebolla", 1), ("Coca-Cola 500ml", 1)],
            estado="EN_PREP", forma_pago="EFECTIVO", horas_atras=2,
        )

        make_pedido(carlos, dir_carlos,
            [("Cheesecake de frutos rojos", 2), ("Bastones de muzzarella", 1)],
            estado="PENDIENTE", forma_pago="MERCADOPAGO", horas_atras=0,
        )

        session.commit()

    print("\n" + "=" * 60)
    print("  SUPER SEED COMPLETADO")
    print("=" * 60)


if __name__ == "__main__":
    run()
