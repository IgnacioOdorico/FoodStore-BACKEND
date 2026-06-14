from typing import Dict, Any
from sqlmodel import Session
from app.modules.estadisticas.repository import EstadisticasRepository
from app.modules.estadisticas.schemas import DashboardResponse


class EstadisticasService:
    def __init__(self, session: Session):
        self.repository = EstadisticasRepository(session)

    def get_dashboard_data(self) -> DashboardResponse:
        data = self.repository.get_dashboard_data()
        return DashboardResponse(**data)
