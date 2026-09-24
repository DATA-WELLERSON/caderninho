import os

# Variáveis de ambiente têm prioridade sobre o .env: os testes não dependem do .env de quem roda.
os.environ["ENABLE_DEBUG_ROUTES"] = "false"
os.environ["SENTRY_DSN"] = ""

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app, get_repo  # noqa: E402
from app.repository import InMemoryFiadoRepository


@pytest.fixture
def repo() -> InMemoryFiadoRepository:
    return InMemoryFiadoRepository()


@pytest.fixture
def client(repo: InMemoryFiadoRepository):
    app.dependency_overrides[get_repo] = lambda: repo
    yield TestClient(app)
    app.dependency_overrides.clear()
