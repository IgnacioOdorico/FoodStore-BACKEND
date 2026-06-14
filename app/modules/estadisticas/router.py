from fastapi import APIRouter, Depends
from sqlmodel import Session
from app.core.database import get_session
from app.modules.estadisticas.schemas import DashboardResponse
from app.modules.estadisticas.service import EstadisticasService
from app.modules.usuarios.router import get_current_active_user

router = APIRouter(prefix="/api/v1/estadisticas", tags=["estadisticas"])

@router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard_stats(
    session: Session = Depends(get_session),
    current_user = Depends(get_current_active_user)
):
    service = EstadisticasService(session)
    return service.get_dashboard_data()
