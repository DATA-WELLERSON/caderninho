"""Testes de contrato: as duas implementações do repositório precisam se comportar igual.

A versão Postgres só roda com TEST_DATABASE_URL definido (no CI sobe um Postgres de verdade).
Usamos uma variável separada de DATABASE_URL para nunca truncar o banco de produção sem querer.
"""

import os
from decimal import Decimal

import psycopg
import pytest

from app.migrate import aplicar_migracoes
from app.models import FiadoIn
from app.repository import (
    FiadoJaPagoError,
    FiadoNaoEncontradoError,
    InMemoryFiadoRepository,
    PostgresFiadoRepository,
)

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")


@pytest.fixture(params=["memoria", "postgres"])
def repo(request):
    if request.param == "memoria":
        return InMemoryFiadoRepository()
    if not TEST_DATABASE_URL:
        pytest.skip("TEST_DATABASE_URL não definido")
    aplicar_migracoes(TEST_DATABASE_URL)
    with psycopg.connect(TEST_DATABASE_URL) as conn:
        conn.execute("truncate fiados restart identity")
    return PostgresFiadoRepository(TEST_DATABASE_URL)


def novo(cliente="Zé", valor="10.00"):
    return FiadoIn(cliente=cliente, valor=Decimal(valor))


def test_criar_e_listar(repo):
    primeiro = repo.criar(novo())
    segundo = repo.criar(novo("Tião"))
    assert [f.id for f in repo.listar()] == [segundo.id, primeiro.id]


def test_pagar_tira_dos_pendentes(repo):
    fiado = repo.criar(novo())
    pago = repo.pagar(fiado.id)
    assert pago.pago_em is not None
    assert repo.listar(apenas_pendentes=True) == []
    assert len(repo.listar()) == 1


def test_pagar_erros(repo):
    fiado = repo.criar(novo())
    repo.pagar(fiado.id)
    with pytest.raises(FiadoJaPagoError):
        repo.pagar(fiado.id)
    with pytest.raises(FiadoNaoEncontradoError):
        repo.pagar(12345)


def test_ranking(repo):
    repo.criar(novo("Zé", "10.00"))
    repo.criar(novo("Zé", "5.50"))
    repo.criar(novo("Tião", "20.00"))
    repo.criar(novo("Bia", "1.00"))

    ranking = repo.ranking(limite=2)

    assert [(d.cliente, d.total, d.quantidade) for d in ranking] == [
        ("Tião", Decimal("20.00"), 1),
        ("Zé", Decimal("15.50"), 2),
    ]


def test_migracoes_sao_idempotentes(repo):
    if isinstance(repo, InMemoryFiadoRepository):
        pytest.skip("só faz sentido no Postgres")
    assert aplicar_migracoes(TEST_DATABASE_URL) == []


def test_ping(repo):
    assert repo.ping() is True
