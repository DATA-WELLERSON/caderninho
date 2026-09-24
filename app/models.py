from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

NomeCliente = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
Descricao = Annotated[str, StringConstraints(strip_whitespace=True, max_length=140)]
Valor = Annotated[Decimal, Field(gt=0, max_digits=10, decimal_places=2)]


class FiadoIn(BaseModel):
    cliente: NomeCliente
    valor: Valor
    descricao: Descricao = ""


class Fiado(BaseModel):
    id: int
    cliente: str
    valor: Decimal
    descricao: str
    criado_em: datetime
    pago_em: datetime | None


class Devedor(BaseModel):
    cliente: str
    total: Decimal
    quantidade: int
