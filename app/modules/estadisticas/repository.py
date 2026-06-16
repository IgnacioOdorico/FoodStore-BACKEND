from typing import Dict, Any, List
from datetime import date
from decimal import Decimal
from sqlmodel import Session, select, func
from sqlalchemy import cast, Date, desc, or_
from app.modules.pedidos.models import Pedido, DetallePedido
from app.modules.pagos.models import Pago
from app.modules.catalogos.models import EstadoPedido


class EstadisticasRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_resumen_kpis(self) -> dict:
        today = date.today()
        ventas_hoy_stmt = select(func.sum(Pedido.total)).where(
            Pedido.deleted_at == None,
            Pedido.estado_codigo != 'CANCELADO',
            cast(Pedido.created_at, Date) == today
        )
        ventas_hoy = self.session.scalar(ventas_hoy_stmt) or 0.0

        ticket_stmt = select(func.avg(Pedido.total)).where(
            Pedido.deleted_at == None,
            Pedido.estado_codigo != 'CANCELADO'
        )
        ticket_promedio = self.session.scalar(ticket_stmt) or 0.0

        activos_stmt = select(func.count(Pedido.id)).where(
            Pedido.deleted_at == None,
            Pedido.estado_codigo.notin_(['CANCELADO', 'ENTREGADO'])
        )
        pedidos_activos = self.session.scalar(activos_stmt) or 0

        mes_stmt = select(func.sum(Pedido.total)).where(
            Pedido.deleted_at == None,
            Pedido.estado_codigo != 'CANCELADO',
            func.extract('month', Pedido.created_at) == today.month,
            func.extract('year', Pedido.created_at) == today.year
        )
        mes_actual = self.session.scalar(mes_stmt) or 0.0

        return {
            "ventas_hoy": Decimal(str(ventas_hoy or 0)),
            "ticket_promedio": Decimal(str(ticket_promedio or 0)),
            "pedidos_activos": pedidos_activos,
            "mes_actual": Decimal(str(mes_actual or 0))
        }

    def get_ventas_periodo(self, desde: date, hasta: date, agrupacion: str) -> list:
        if agrupacion == "mes":
            periodo = cast(func.date_trunc('month', Pedido.created_at), Date)
        elif agrupacion == "semana":
            periodo = cast(func.date_trunc('week', Pedido.created_at), Date)
        else:  # dia (default)
            periodo = cast(Pedido.created_at, Date)

        stmt = (
            select(
                periodo.label("fecha"),
                func.sum(Pedido.total).label("ingresos"),
                func.count(Pedido.id).label("cantidad")
            )
            .where(
                Pedido.deleted_at == None, 
                Pedido.estado_codigo != 'CANCELADO',
                cast(Pedido.created_at, Date).between(desde, hasta)
            )
            .group_by(periodo)
            .order_by(periodo)
        )
        rows = self.session.exec(stmt).all()
        return [{"fecha": row[0].isoformat(), "ingresos": Decimal(str(row[1] or 0)), "cantidad": row[2]} for row in rows]

    def get_productos_top(self, limit: int) -> list:
        stmt = (
            select(
                DetallePedido.nombre_snapshot,
                func.sum(DetallePedido.cantidad).label("cantidad"),
                func.sum(DetallePedido.subtotal_snap).label("ingresos")
            )
            .join(Pedido)
            .where(Pedido.deleted_at == None, Pedido.estado_codigo != 'CANCELADO')
            .group_by(DetallePedido.nombre_snapshot)
            .order_by(desc("ingresos"))
            .limit(limit)
        )
        rows = self.session.exec(stmt).all()
        return [{"nombre": row[0], "cantidad": row[1], "ingresos": Decimal(str(row[2] or 0))} for row in rows]

    def get_pedidos_por_estado(self) -> dict:
        stmt = select(Pedido.estado_codigo, func.count(Pedido.id)).where(Pedido.deleted_at == None).group_by(Pedido.estado_codigo)
        return {row[0]: row[1] for row in self.session.exec(stmt).all()}

    def get_ingresos_por_forma_pago(self, desde: date, hasta: date) -> list:
        stmt = (
            select(
                Pedido.forma_pago_codigo,
                func.sum(DetallePedido.subtotal_snap).label("ingresos")
            )
            .join(DetallePedido, DetallePedido.pedido_id == Pedido.id)
            .join(Pago, Pago.pedido_id == Pedido.id, isouter=True)
            .where(
                Pedido.deleted_at == None,
                Pedido.estado_codigo != 'CANCELADO',
                cast(Pedido.created_at, Date).between(desde, hasta),
                or_(
                    Pago.mp_status == 'approved',
                    Pago.id == None
                )
            )
            .group_by(Pedido.forma_pago_codigo)
        )
        rows = self.session.exec(stmt).all()
        return [{"forma_pago_codigo": row[0], "ingresos": Decimal(str(row[1] or 0))} for row in rows]

    def _get_ventas_por_dia(self, desde: date, hasta: date) -> list:
        stmt = (
            select(cast(Pedido.created_at, Date), func.sum(Pedido.total))
            .where(
                Pedido.deleted_at == None,
                Pedido.estado_codigo != "CANCELADO",
                cast(Pedido.created_at, Date) >= desde,
                cast(Pedido.created_at, Date) <= hasta,
            )
            .group_by(cast(Pedido.created_at, Date))
            .order_by(cast(Pedido.created_at, Date))
        )
        rows = self.session.exec(stmt).all()
        return [{"fecha": row[0].isoformat(), "ingresos": Decimal(str(row[1] or 0))} for row in rows]

    def get_dashboard(self) -> dict:
        """
        Agrega métricas de alto nivel para el panel de control:
        totalProductos, totalPedidos, totalUsuarios, pedidosPorEstado,
        topProductos, resumenStock.
        """
        from app.modules.producto.models import Producto
        from app.modules.usuarios.model import Usuario

        total_productos = self.session.scalar(
            select(func.count(Producto.id)).where(Producto.deleted_at == None)
        ) or 0

        total_pedidos = self.session.scalar(
            select(func.count(Pedido.id)).where(Pedido.deleted_at == None)
        ) or 0

        total_usuarios = self.session.scalar(
            select(func.count(Usuario.id))
        ) or 0

        # Pedidos por estado
        estado_rows = self.session.exec(
            select(Pedido.estado_codigo, func.count(Pedido.id))
            .where(Pedido.deleted_at == None)
            .group_by(Pedido.estado_codigo)
        ).all()
        pedidos_por_estado = {row[0]: row[1] for row in estado_rows}

        # Top 5 productos por cantidad vendida (excluyendo CANCELADO)
        top_stmt = (
            select(
                Producto.nombre,
                func.sum(DetallePedido.cantidad),
                func.sum(DetallePedido.subtotal_snap),
            )
            .join(DetallePedido, Producto.id == DetallePedido.producto_id)
            .join(Pedido, DetallePedido.pedido_id == Pedido.id)
            .where(Pedido.estado_codigo != "CANCELADO", Pedido.deleted_at == None)
            .group_by(Producto.nombre)
            .order_by(desc(func.sum(DetallePedido.cantidad)))
            .limit(5)
        )
        top_rows = self.session.exec(top_stmt).all()
        top_productos = [
            {"nombre": r[0], "cantidad": r[1], "ingresos": Decimal(str(r[2] or 0))}
            for r in top_rows
        ]

        # Resumen de stock
        stock_stmt = select(Producto.stock_cantidad).where(Producto.deleted_at == None)
        stocks = [r for r in self.session.exec(stock_stmt).all()]
        resumen_stock = {
            "total": len(stocks),
            "sinStock": sum(1 for s in stocks if s == 0),
            "bajo": sum(1 for s in stocks if 0 < s <= 5),
            "normal": sum(1 for s in stocks if s > 5),
        }

        return {
            "totalProductos": total_productos,
            "totalPedidos": total_pedidos,
            "totalUsuarios": total_usuarios,
            "pedidosPorEstado": pedidos_por_estado,
            "topProductos": top_productos,
            "resumenStock": resumen_stock,
        }
