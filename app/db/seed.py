"""
Seed — FoodStore (ERD v6).

Carga:
  1.  Roles                (ADMIN, STOCK, PEDIDOS, CLIENT)
  2.  EstadoPedido         (6 estados del FSM)
  3.  FormaPago            (MERCADOPAGO, EFECTIVO, TRANSFERENCIA)
  4.  UnidadMedida         (kg, g, L, mL, u, doc, m²)
  5.  Usuarios             (1 por rol)
  6.  DireccionEntrega     (una principal para el cliente)
  7.  Categorías           (Pizzas, Bebidas, Hamburguesas)
  8.  Ingredientes         (sin stock — el stock vive en Producto)
  9.  Productos            + ProductoCategoria + ProductoIngrediente
  10. Pedido demo          + HistorialEstadoPedido (estado_desde=NULL → PENDIENTE)

Uso:
    python -m app.db.seed
"""

from sqlmodel import Session, select

from app.core.database import engine, create_all_tables
from app.core.security import hash_password

# Identidad
from app.modules.usuarios.model import Usuario, Rol, UsuarioRol
from app.modules.direcciones.models import DireccionEntrega

# Catálogos
from app.modules.catalogos.models import UnidadMedida, EstadoPedido, FormaPago

# Catálogo de productos
from app.modules.categorias.model import Categoria
from app.modules.ingrediente.models import Ingrediente
from app.modules.producto.models import Producto
from app.modules.producto.associations import ProductoCategoria, ProductoIngrediente

# Pedidos
from app.modules.pedidos.models import Pedido, DetallePedido, HistorialEstadoPedido


def _upsert(session: Session, model, key_field: str, key_value, defaults: dict):
    """Inserta si no existe; si existe lo devuelve. No actualiza columnas."""
    statement = select(model).where(getattr(model, key_field) == key_value)
    existing = session.exec(statement).first()
    if existing:
        return existing
    obj = model(**defaults)
    session.add(obj)
    session.flush()
    return obj


def run() -> None:
    print("Sembrando datos (FoodStore ERD v6)...")
    create_all_tables()

    with Session(engine) as session:
        # ─── 1. ROLES ────────────────────────────────────────────────────
        roles_data = [
            {"codigo": "ADMIN",   "nombre": "Administrador",   "descripcion": "Acceso total"},
            {"codigo": "STOCK",   "nombre": "Gestor de Stock", "descripcion": "Stock y disponibilidad"},
            {"codigo": "PEDIDOS", "nombre": "Gestor de Pedidos", "descripcion": "Ventas y comandas"},
            {"codigo": "CLIENT",  "nombre": "Cliente",          "descripcion": "Usuario final"},
        ]
        for r in roles_data:
            if not session.get(Rol, r["codigo"]):
                session.add(Rol(**r))
                print(f"  [+] Rol: {r['codigo']}")
        session.commit()

        # ─── 2. ESTADOS DE PEDIDO ────────────────────────────────────────
        estados_data = [
            {"codigo": "PENDIENTE",  "descripcion": "Pendiente",  "orden": 1, "es_terminal": False},
            {"codigo": "CONFIRMADO", "descripcion": "Confirmado", "orden": 2, "es_terminal": False},
            {"codigo": "EN_PREP",    "descripcion": "En preparación", "orden": 3, "es_terminal": False},
            {"codigo": "ENTREGADO",  "descripcion": "Entregado",  "orden": 4, "es_terminal": True},
            {"codigo": "CANCELADO",  "descripcion": "Cancelado",  "orden": 5, "es_terminal": True},
        ]
        for e in estados_data:
            if not session.get(EstadoPedido, e["codigo"]):
                session.add(EstadoPedido(**e))
                print(f"  [+] EstadoPedido: {e['codigo']}")
        session.commit()

        # ─── 3. FORMAS DE PAGO ───────────────────────────────────────────
        formas_data = [
            {"codigo": "MERCADOPAGO",   "descripcion": "MercadoPago",    "habilitado": True},
            {"codigo": "EFECTIVO",      "descripcion": "Efectivo en local", "habilitado": True},
            {"codigo": "TRANSFERENCIA", "descripcion": "Transferencia bancaria", "habilitado": True},
        ]
        for f in formas_data:
            if not session.get(FormaPago, f["codigo"]):
                session.add(FormaPago(**f))
                print(f"  [+] FormaPago: {f['codigo']}")
        session.commit()

        # ─── 4. UNIDADES DE MEDIDA ───────────────────────────────────────
        unidades_data = [
            {"nombre": "kilogramo",       "simbolo": "kg",  "tipo": "masa"},
            {"nombre": "gramo",           "simbolo": "g",   "tipo": "masa"},
            {"nombre": "litro",           "simbolo": "L",   "tipo": "volumen"},
            {"nombre": "mililitro",       "simbolo": "mL",  "tipo": "volumen"},
            {"nombre": "pieza",           "simbolo": "u",   "tipo": "unidad"},
            {"nombre": "docena",          "simbolo": "doc", "tipo": "unidad"},
            {"nombre": "metro cuadrado",  "simbolo": "m²",  "tipo": "area"},
        ]
        unidades_db: dict[str, UnidadMedida] = {}
        for u in unidades_data:
            existing = session.exec(
                select(UnidadMedida).where(UnidadMedida.simbolo == u["simbolo"])
            ).first()
            if existing:
                unidades_db[u["simbolo"]] = existing
            else:
                obj = UnidadMedida(**u)
                session.add(obj)
                session.flush()
                unidades_db[u["simbolo"]] = obj
                print(f"  [+] UnidadMedida: {u['simbolo']}")
        session.commit()

        # ─── 5. USUARIOS ─────────────────────────────────────────────────
        usuarios_data = [
            {"nombre": "Nacho", "apellido": "Admin",   "email": "admin@nachopizza.com",   "password": "Admin1234!",   "rol": "ADMIN"},
            {"nombre": "Gabi",  "apellido": "Stock",   "email": "stock@nachopizza.com",   "password": "Stock1234!",   "rol": "STOCK"},
            {"nombre": "Fede",  "apellido": "Pedidos", "email": "pedidos@nachopizza.com", "password": "Pedidos1234!", "rol": "PEDIDOS"},
            {"nombre": "Juan",  "apellido": "Cliente", "email": "juan@ejemplo.com",       "password": "Juan1234!",    "rol": "CLIENT"},
        ]
        users_db: dict[str, Usuario] = {}
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
                print(f"  [+] Usuario: {u['email']} ({u['rol']})")
            users_db[u["email"]] = user
        session.commit()

        # ─── 6. DIRECCION ENTREGA (cliente) ──────────────────────────────
        juan = users_db["juan@ejemplo.com"]
        direccion_juan = session.exec(
            select(DireccionEntrega).where(DireccionEntrega.usuario_id == juan.id)
        ).first()
        if not direccion_juan:
            direccion_juan = DireccionEntrega(
                usuario_id=juan.id,
                alias="Casa",
                linea1="Av. Siempre Viva 742",
                ciudad="Rosario",
                provincia="Santa Fe",
                codigo_postal="2000",
                es_principal=True,
            )
            session.add(direccion_juan)
            session.flush()
            print(f"  [+] Dirección principal de {juan.email}")
        session.commit()

        # ─── 7. CATEGORÍAS ───────────────────────────────────────────────
        cats_data = [
            {"nombre": "Pizzas",       "descripcion": "Pizzas a la piedra"},
            {"nombre": "Bebidas",      "descripcion": "Gaseosas y cervezas"},
            {"nombre": "Hamburguesas", "descripcion": "Burgers gourmet"},
        ]
        cats_db: dict[str, Categoria] = {}
        for c in cats_data:
            cat = session.exec(select(Categoria).where(Categoria.nombre == c["nombre"])).first()
            if not cat:
                cat = Categoria(**c)
                session.add(cat)
                session.flush()
                print(f"  [+] Categoría: {c['nombre']}")
            cats_db[c["nombre"]] = cat
        session.commit()

        # ─── 8. INGREDIENTES ─────────────────────────────────────────────
        ings_data = [
            {"nombre": "Harina",           "descripcion": "Harina 0000",       "es_alergeno": True},
            {"nombre": "Muzarella",        "descripcion": "Queso muzarella",   "es_alergeno": True},
            {"nombre": "Tomate",           "descripcion": "Tomate perita",     "es_alergeno": False},
            {"nombre": "Medallón Carne",   "descripcion": "Carne vacuna 150g", "es_alergeno": False},
            {"nombre": "Coca-Cola 500ml",  "descripcion": "Botella 500 ml",    "es_alergeno": False},
        ]
        ings_db: dict[str, Ingrediente] = {}
        for i in ings_data:
            ing = session.exec(select(Ingrediente).where(Ingrediente.nombre == i["nombre"])).first()
            if not ing:
                ing = Ingrediente(**i)
                session.add(ing)
                session.flush()
                print(f"  [+] Ingrediente: {i['nombre']}")
            ings_db[i["nombre"]] = ing
        session.commit()

        # ─── 9. PRODUCTOS + ASOCIACIONES ─────────────────────────────────
        productos_data = [
            {
                "nombre": "Pizza Muzarella",
                "descripcion": "Pizza grande a la piedra con muzarella y salsa de tomate.",
                "precio": 8500.0,
                "stock": 25,
                "unidad": None,  # por pieza
                "categoria": "Pizzas",
                "imagenes": ["https://placehold.co/600x400?text=Pizza+Muzarella"],
                "receta": [
                    ("Harina",     250.0, "g"),
                    ("Muzarella",  200.0, "g"),
                    ("Tomate",       2.0, "u"),
                ],
            },
            {
                "nombre": "Hamburguesa Clásica",
                "descripcion": "Hamburguesa con medallón, queso y tomate.",
                "precio": 6200.0,
                "stock": 30,
                "unidad": None,
                "categoria": "Hamburguesas",
                "imagenes": ["https://placehold.co/600x400?text=Burger"],
                "receta": [
                    ("Medallón Carne", 1.0, "u"),
                    ("Tomate",         1.0, "u"),
                ],
            },
            {
                "nombre": "Coca-Cola",
                "descripcion": "Coca-Cola 500ml.",
                "precio": 1500.0,
                "stock": 50,
                "unidad": "u",
                "categoria": "Bebidas",
                "imagenes": ["https://placehold.co/600x400?text=Coca"],
                "receta": [
                    ("Coca-Cola 500ml", 1.0, "u"),
                ],
            },
        ]

        for p in productos_data:
            prod = session.exec(select(Producto).where(Producto.nombre == p["nombre"])).first()
            if prod:
                continue
            unidad = unidades_db[p["unidad"]] if p["unidad"] else None
            prod = Producto(
                nombre=p["nombre"],
                descripcion=p["descripcion"],
                precio_base=p["precio"],
                stock_cantidad=p["stock"],
                disponible=True,
                imagenes_url=p["imagenes"],
                unidad_venta_id=unidad.id if unidad else None,
            )
            session.add(prod)
            session.flush()

            session.add(ProductoCategoria(
                producto_id=prod.id,
                categoria_id=cats_db[p["categoria"]].id,
                es_principal=True,
            ))
            for ing_nombre, cant, unidad_simb in p["receta"]:
                session.add(ProductoIngrediente(
                    producto_id=prod.id,
                    ingrediente_id=ings_db[ing_nombre].id,
                    cantidad=cant,
                    unidad_medida_id=unidades_db[unidad_simb].id,
                    es_removible=(ing_nombre == "Tomate"),  # tomate removible
                ))
            print(f"  [+] Producto: {p['nombre']}")
        session.commit()

        # ─── 10. PEDIDO DEMO + HISTORIAL ─────────────────────────────────
        existing_pedido = session.exec(
            select(Pedido).where(Pedido.usuario_id == juan.id)
        ).first()

        if not existing_pedido:
            pizza = session.exec(select(Producto).where(Producto.nombre == "Pizza Muzarella")).first()
            coca = session.exec(select(Producto).where(Producto.nombre == "Coca-Cola")).first()

            subtotal = pizza.precio_base + coca.precio_base
            costo_envio = 500.0
            total = subtotal + costo_envio

            pedido = Pedido(
                usuario_id=juan.id,
                direccion_id=direccion_juan.id,
                estado_codigo="PENDIENTE",
                forma_pago_codigo="EFECTIVO",
                subtotal=subtotal,
                descuento=0.0,
                costo_envio=costo_envio,
                total=total,
                notas="Pedido demo del seed.",
            )
            session.add(pedido)
            session.flush()

            session.add(DetallePedido(
                pedido_id=pedido.id,
                producto_id=pizza.id,
                cantidad=1,
                nombre_snapshot=pizza.nombre,
                precio_snapshot=pizza.precio_base,
                subtotal_snap=pizza.precio_base,
                personalizacion=None,
            ))
            session.add(DetallePedido(
                pedido_id=pedido.id,
                producto_id=coca.id,
                cantidad=1,
                nombre_snapshot=coca.nombre,
                precio_snapshot=coca.precio_base,
                subtotal_snap=coca.precio_base,
                personalizacion=None,
            ))

            # Audit trail — RN-02: estado_desde NULL
            session.add(HistorialEstadoPedido(
                pedido_id=pedido.id,
                estado_desde=None,
                estado_hacia="PENDIENTE",
                usuario_id=juan.id,
                motivo="Creación del pedido (seed)",
            ))
            print(f"  [+] Pedido demo para {juan.email}")

        session.commit()

    print("\n Sembrado finalizado con éxito.")


if __name__ == "__main__":
    run()
