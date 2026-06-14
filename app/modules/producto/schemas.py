from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List
from datetime import datetime


class ProductoBase(BaseModel):
    nombre:          str
    descripcion:     Optional[str] = None
    precio_base:     float = Field(ge=0)
    imagenes_url:    Optional[List[str]] = None
    stock_cantidad:  int = Field(default=0, ge=0)
    disponible:      bool = True
    unidad_venta_id: Optional[int] = None
    es_apto_celiaco: bool = False
    es_apto_vegano:  bool = False


class IngredienteEnReceta(BaseModel):
    id:               int
    cantidad:         float = Field(gt=0)
    unidad_medida_id: Optional[int] = None
    es_removible:     bool = False


class ProductoCreate(ProductoBase):
    categoria_ids:       List[int] = Field(..., min_length=1)
    ingredientes_receta: List[IngredienteEnReceta] = []


class ProductoUpdate(BaseModel):
    nombre:              Optional[str] = None
    descripcion:         Optional[str] = None
    precio_base:         Optional[float] = Field(default=None, ge=0)
    imagenes_url:        Optional[List[str]] = None
    stock_cantidad:      Optional[int] = Field(default=None, ge=0)
    disponible:          Optional[bool] = None
    unidad_venta_id:     Optional[int] = None
    es_apto_celiaco:     Optional[bool] = None
    es_apto_vegano:      Optional[bool] = None
    categoria_ids:       Optional[List[int]] = None
    ingredientes_receta: Optional[List[IngredienteEnReceta]] = None


class ProductoDisponibilidadUpdate(BaseModel):
    disponible: bool


class ProductoRead(ProductoBase):
    id:         int
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

from app.modules.categorias.schemas import CategoriaPublic as CategoriaRead
from app.modules.ingrediente.schemas import IngredienteRead


class CategoriaConExtra(CategoriaRead):
    es_principal: bool = False


class IngredienteConExtra(IngredienteRead):
    cantidad:         float = 0.0
    unidad_medida_id: Optional[int] = None
    es_removible:     bool = False


class ProductoReadWithDetails(ProductoRead):
    categorias:   List[CategoriaConExtra] = []
    ingredientes: List[IngredienteConExtra] = []


class PaginatedProductos(BaseModel):
    """Respuesta paginada."""
    items: List[ProductoReadWithDetails]
    total: int
    page: int
    size: int
    pages: int
