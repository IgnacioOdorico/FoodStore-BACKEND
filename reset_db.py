from sqlmodel import text

from app.core.database import engine, create_all_tables


TABLAS = [
    "historial_estado_pedido",
    "detalle_pedido",
    "pedido",
    "producto_ingrediente",
    "producto_categoria",
    "productocategoria",
    "producto",
    "ingrediente",
    "categoria",
    "direccion_entrega",
    "refresh_token",
    "usuario_rol",
    "usuario",
    "rol",
    "unidad_medida",
    "estado_pedido",
    "forma_pago",
]


def main() -> None:
    print("Dropping all tables...")
    with engine.connect() as conn:
        for tbl in TABLAS:
            conn.execute(text(f"DROP TABLE IF EXISTS {tbl} CASCADE"))
        conn.commit()

    print("Creating all tables (ERD v6)...")
    create_all_tables()
    print("Done!")


if __name__ == "__main__":
    main()
