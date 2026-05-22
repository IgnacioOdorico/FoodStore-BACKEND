from pydantic import ConfigDict
from sqlmodel import SQLModel


class UnidadMedidaPublic(SQLModel):
    id:      int
    nombre:  str
    simbolo: str
    tipo:    str

    model_config = ConfigDict(from_attributes=True)


class EstadoPedidoPublic(SQLModel):
    codigo:      str
    descripcion: str
    orden:       int
    es_terminal: bool

    model_config = ConfigDict(from_attributes=True)


class FormaPagoPublic(SQLModel):
    codigo:      str
    descripcion: str
    habilitado:  bool

    model_config = ConfigDict(from_attributes=True)
