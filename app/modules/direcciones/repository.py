from typing import List, Optional
from sqlmodel import Session, select

from app.core.base_repository import BaseRepository
from app.modules.direcciones.models import DireccionEntrega


class DireccionRepository(BaseRepository[DireccionEntrega]):
    def __init__(self, session: Session):
        super().__init__(DireccionEntrega, session)

    def list_by_usuario(self, usuario_id: int) -> List[DireccionEntrega]:
        return list(self.session.exec(
            select(DireccionEntrega).where(
                DireccionEntrega.usuario_id == usuario_id,
                DireccionEntrega.deleted_at == None,  # noqa: E711
            )
        ).all())

    def get_principal(self, usuario_id: int) -> Optional[DireccionEntrega]:
        return self.session.exec(
            select(DireccionEntrega).where(
                DireccionEntrega.usuario_id == usuario_id,
                DireccionEntrega.es_principal == True,  # noqa: E712
                DireccionEntrega.deleted_at == None,    # noqa: E711
            )
        ).first()

    def unset_principal(self, usuario_id: int) -> None:
        items = self.session.exec(
            select(DireccionEntrega).where(
                DireccionEntrega.usuario_id == usuario_id,
                DireccionEntrega.es_principal == True,  # noqa: E712
            )
        ).all()
        for d in items:
            d.es_principal = False
            self.session.add(d)
