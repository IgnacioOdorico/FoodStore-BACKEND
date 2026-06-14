from typing import Dict, Any, List
from sqlmodel import Session, select, func
from sqlalchemy import cast, Date, desc

from app.modules.pedidos.models import Pedido, DetallePedido
from app.modules.pagos.models import Pago
from app.modules.producto.models import Producto
from app.modules.ingrediente.models import Ingrediente
from app.modules.categorias.model import Categoria
from app.modules.usuarios.model import Usuario


class EstadisticasRepository:
    def __init__(self, session: Session):
        self.session = session

    def _get_ventas_por_dia(self) -> list:
        ventas_stmt = (
            select(
                cast(Pedido.created_at, Date).label("fecha"),
                func.count(Pedido.id).label("cantidad"),
                func.sum(Pedido.total).label("ingresos")
            )
            .where(Pedido.deleted_at == None, Pedido.estado_codigo != 'CANCELADO')
            .group_by(cast(Pedido.created_at, Date))
            .order_by(cast(Pedido.created_at, Date))
        )
        ventas_rows = self.session.exec(ventas_stmt).all()
        result = []
        for row in ventas_rows:
            fecha_str = row[0].isoformat() if row[0] else ""
            result.append({
                "fecha": fecha_str,
                "fechaLabel": row[0].strftime("%d %b") if row[0] else "",
                "cantidad": row[1],
                "ingresos": float(row[2] or 0)
            })
        return result

    def get_dashboard_data(self) -> Dict[str, Any]:
        total_categorias = self.session.scalar(select(func.count(Categoria.id))) or 0
        total_productos = self.session.scalar(select(func.count(Producto.id)).where(Producto.deleted_at == None)) or 0
        total_ingredientes = self.session.scalar(select(func.count(Ingrediente.id))) or 0
        total_usuarios = self.session.scalar(select(func.count(Usuario.id)).where(Usuario.deleted_at == None)) or 0
        total_pedidos = self.session.scalar(select(func.count(Pedido.id)).where(Pedido.deleted_at == None)) or 0
        pedidos_estado_stmt = select(Pedido.estado_codigo, func.count(Pedido.id)).where(Pedido.deleted_at == None).group_by(Pedido.estado_codigo)
        pedidos_por_estado = {row[0]: row[1] for row in self.session.exec(pedidos_estado_stmt).all()}
        pedidos_pago_stmt = select(Pedido.forma_pago_codigo, func.count(Pedido.id)).where(Pedido.deleted_at == None).group_by(Pedido.forma_pago_codigo)
        pedidos_por_forma_pago = {row[0]: row[1] for row in self.session.exec(pedidos_pago_stmt).all()}

        pedidos_por_dia = self._get_ventas_por_dia()

        top_stmt = (
            select(
                DetallePedido.nombre_snapshot,
                func.sum(DetallePedido.cantidad).label("cantidad"),
                func.sum(DetallePedido.subtotal_snap).label("ingresos")
            )
            .join(Pedido)
            .where(Pedido.deleted_at == None, Pedido.estado_codigo != 'CANCELADO')
            .group_by(DetallePedido.nombre_snapshot)
            .order_by(desc("cantidad"))
            .limit(10)
        )
        top_rows = self.session.exec(top_stmt).all()
        top_productos = [
            {
                "nombre": row[0],
                "cantidad": row[1],
                "ingresos": float(row[2] or 0)
            }
            for row in top_rows
        ]

        productos_todos = self.session.exec(select(Producto).where(Producto.deleted_at == None)).all()
        bajo = sum(1 for p in productos_todos if p.stock_cantidad is not None and 0 < p.stock_cantidad < 10)
        sin_stock = sum(1 for p in productos_todos if p.stock_cantidad == 0 and p.disponible)
        normal = sum(1 for p in productos_todos if p.stock_cantidad is None or p.stock_cantidad >= 10)

        resumen_stock = {
            "bajo": bajo,
            "sinStock": sin_stock,
            "normal": normal,
            "total": len(productos_todos)
        }

        recientes_stmt = select(Pedido).where(Pedido.deleted_at == None).order_by(Pedido.created_at.desc()).limit(8)
        ordenes_recientes = self.session.exec(recientes_stmt).all()

        productos_stock_bajo = [p for p in productos_todos if p.stock_cantidad is not None and p.stock_cantidad < 10][:8]

        ingredientes_todos = self.session.exec(select(Ingrediente)).all()
        ingredientes_stock_bajo = [i for i in ingredientes_todos if i.stock_cantidad is not None and 0 < i.stock_cantidad < 10][:8]

        prod_cat = []
        for p in productos_todos:
            cats = [c.nombre for c in p.categorias] if p.categorias else []
            prod_cat.append({"nombre": p.nombre, "categorias": cats})

        return {
            "totalCategorias": total_categorias,
            "totalProductos": total_productos,
            "totalIngredientes": total_ingredientes,
            "totalPedidos": total_pedidos,
            "totalUsuarios": total_usuarios,
            "pedidosPorEstado": pedidos_por_estado,
            "pedidosPorFormaPago": pedidos_por_forma_pago,
            "ordenesRecientes": [orden.model_dump() for orden in ordenes_recientes],
            "productosStockBajo": [p.model_dump() for p in productos_stock_bajo],
            "ingredientesStockBajo": [i.model_dump() for i in ingredientes_stock_bajo],
            "pedidosPorDia": pedidos_por_dia,
            "topProductos": top_productos,
            "productosConCategoria": prod_cat,
            "resumenStock": resumen_stock
        }
