from typing import Dict, Any, List
from datetime import date
from sqlmodel import Session, select, func
from sqlalchemy import cast, Date, desc, or_

from app.modules.pedidos.models import Pedido, DetallePedido
from app.modules.pagos.models import Pago


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
            "ventas_hoy": float(ventas_hoy),
            "ticket_promedio": float(ticket_promedio),
            "pedidos_activos": pedidos_activos,
            "mes_actual": float(mes_actual)
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
        return [{"fecha": row[0].isoformat(), "ingresos": float(row[1] or 0.0), "cantidad": row[2]} for row in rows]

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
        return [{"nombre": row[0], "cantidad": row[1], "ingresos": float(row[2] or 0.0)} for row in rows]

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
        return [{"forma_pago_codigo": row[0], "ingresos": float(row[1] or 0.0)} for row in rows]
