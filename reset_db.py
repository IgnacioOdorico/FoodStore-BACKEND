from sqlmodel import SQLModel, Session, text
from app.core.database import engine, create_all_tables
from app.core.config import settings

print("Dropping all tables...")
with engine.connect() as conn:
    conn.execute(text("DROP TABLE IF EXISTS productoingrediente CASCADE"))
    conn.execute(text("DROP TABLE IF EXISTS productocategoria CASCADE"))
    conn.execute(text("DROP TABLE IF EXISTS detallepedido CASCADE"))
    conn.execute(text("DROP TABLE IF EXISTS pedido CASCADE"))
    conn.execute(text("DROP TABLE IF EXISTS producto CASCADE"))
    conn.execute(text("DROP TABLE IF EXISTS ingrediente CASCADE"))
    conn.execute(text("DROP TABLE IF EXISTS categoria CASCADE"))
    conn.execute(text("DROP TABLE IF EXISTS usuario_rol CASCADE"))
    conn.execute(text("DROP TABLE IF EXISTS refresh_token CASCADE"))
    conn.execute(text("DROP TABLE IF EXISTS usuario CASCADE"))
    conn.execute(text("DROP TABLE IF EXISTS rol CASCADE"))
    conn.commit()

print("Creating all tables...")
create_all_tables()
print("Done!")
