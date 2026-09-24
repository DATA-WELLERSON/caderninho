from pathlib import Path
from typing import Annotated

import sentry_sdk
from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.responses import HTMLResponse, JSONResponse

from app.config import get_settings
from app.models import Devedor, Fiado, FiadoIn
from app.repository import (
    FiadoJaPagoError,
    FiadoNaoEncontradoError,
    FiadoRepository,
    PostgresFiadoRepository,
)

settings = get_settings()

if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        release=settings.release,
        traces_sample_rate=0.2,
        send_default_pii=False,
    )

app = FastAPI(
    title="Caderninho do Fiado",
    description="Quem bebeu e não pagou. API do bar do Seu Elias.",
    version="0.1.0",
)

PAGINA = (Path(__file__).parent / "static" / "index.html").read_text(encoding="utf-8")


def get_repo() -> FiadoRepository:
    return PostgresFiadoRepository(get_settings().database_url)


Repo = Annotated[FiadoRepository, Depends(get_repo)]


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def pagina() -> str:
    return PAGINA


@app.get("/api/health")
def health(repo: Repo) -> JSONResponse:
    db_ok = repo.ping()
    return JSONResponse(
        status_code=status.HTTP_200_OK if db_ok else status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "status": "ok" if db_ok else "sem banco",
            "db": db_ok,
            "release": settings.release,
        },
    )


@app.get("/api/fiados")
def listar_fiados(repo: Repo, pendentes: bool = False) -> list[Fiado]:
    return repo.listar(apenas_pendentes=pendentes)


@app.post("/api/fiados", status_code=status.HTTP_201_CREATED)
def anotar_fiado(novo: FiadoIn, repo: Repo) -> Fiado:
    return repo.criar(novo)


@app.post("/api/fiados/{fiado_id}/pagar")
def pagar_fiado(fiado_id: int, repo: Repo) -> Fiado:
    try:
        return repo.pagar(fiado_id)
    except FiadoNaoEncontradoError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fiado não encontrado") from None
    except FiadoJaPagoError:
        raise HTTPException(status.HTTP_409_CONFLICT, "Esse fiado já foi pago, milagre") from None


@app.get("/api/ranking")
def mural_da_vergonha(repo: Repo, limite: Annotated[int, Query(ge=1, le=50)] = 10) -> list[Devedor]:
    return repo.ranking(limite)


if settings.enable_debug_routes:

    @app.get("/api/debug/erro", include_in_schema=False)
    def erro_proposital() -> None:
        # Usado para conferir se o Sentry está recebendo os erros.
        raise ZeroDivisionError("O caixa dividiu por zero")
