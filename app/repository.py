"""Acesso a dados do caderninho.

A API depende só do protocolo `FiadoRepository`. Em produção usamos Postgres (Supabase);
nos testes da API usamos a versão em memória, que roda sem banco nenhum.
"""

from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from typing import Protocol

import psycopg
from psycopg.rows import dict_row

from app.models import Devedor, Fiado, FiadoIn


class FiadoNaoEncontradoError(Exception):
    pass


class FiadoJaPagoError(Exception):
    pass


class FiadoRepository(Protocol):
    def listar(self, *, apenas_pendentes: bool = False) -> list[Fiado]: ...
    def criar(self, novo: FiadoIn) -> Fiado: ...
    def pagar(self, fiado_id: int) -> Fiado: ...
    def ranking(self, limite: int = 10) -> list[Devedor]: ...
    def ping(self) -> bool: ...


class InMemoryFiadoRepository:
    def __init__(self) -> None:
        self._fiados: dict[int, Fiado] = {}
        self._proximo_id = 1

    def listar(self, *, apenas_pendentes: bool = False) -> list[Fiado]:
        fiados = sorted(self._fiados.values(), key=lambda f: f.id, reverse=True)
        return [f for f in fiados if not apenas_pendentes or f.pago_em is None]

    def criar(self, novo: FiadoIn) -> Fiado:
        fiado = Fiado(
            id=self._proximo_id, criado_em=datetime.now(UTC), pago_em=None, **novo.model_dump()
        )
        self._fiados[fiado.id] = fiado
        self._proximo_id += 1
        return fiado

    def pagar(self, fiado_id: int) -> Fiado:
        fiado = self._fiados.get(fiado_id)
        if fiado is None:
            raise FiadoNaoEncontradoError(fiado_id)
        if fiado.pago_em is not None:
            raise FiadoJaPagoError(fiado_id)
        pago = fiado.model_copy(update={"pago_em": datetime.now(UTC)})
        self._fiados[fiado_id] = pago
        return pago

    def ranking(self, limite: int = 10) -> list[Devedor]:
        totais: dict[str, Decimal] = defaultdict(Decimal)
        quantidades: dict[str, int] = defaultdict(int)
        for f in self.listar(apenas_pendentes=True):
            totais[f.cliente] += f.valor
            quantidades[f.cliente] += 1
        devedores = [
            Devedor(cliente=c, total=t, quantidade=quantidades[c]) for c, t in totais.items()
        ]
        devedores.sort(key=lambda d: (-d.total, d.cliente))
        return devedores[:limite]

    def ping(self) -> bool:
        return True


class PostgresFiadoRepository:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    def _conectar(self) -> psycopg.Connection:
        # prepare_threshold=None: o pooler do Supabase (modo transaction) não suporta
        # prepared statements. Uma conexão por chamada é o jeito simples em serverless.
        return psycopg.connect(
            self._database_url, row_factory=dict_row, prepare_threshold=None, connect_timeout=5
        )

    def listar(self, *, apenas_pendentes: bool = False) -> list[Fiado]:
        sql = "select * from fiados"
        if apenas_pendentes:
            sql += " where pago_em is null"
        sql += " order by id desc"
        with self._conectar() as conn:
            return [Fiado(**row) for row in conn.execute(sql)]

    def criar(self, novo: FiadoIn) -> Fiado:
        with self._conectar() as conn:
            row = conn.execute(
                "insert into fiados (cliente, valor, descricao) values (%s, %s, %s) returning *",
                (novo.cliente, novo.valor, novo.descricao),
            ).fetchone()
        return Fiado(**row)

    def pagar(self, fiado_id: int) -> Fiado:
        with self._conectar() as conn:
            row = conn.execute(
                "update fiados set pago_em = now() where id = %s and pago_em is null returning *",
                (fiado_id,),
            ).fetchone()
            if row is not None:
                return Fiado(**row)
            existe = conn.execute("select 1 from fiados where id = %s", (fiado_id,)).fetchone()
        if existe:
            raise FiadoJaPagoError(fiado_id)
        raise FiadoNaoEncontradoError(fiado_id)

    def ranking(self, limite: int = 10) -> list[Devedor]:
        with self._conectar() as conn:
            rows = conn.execute(
                """
                select cliente, sum(valor) as total, count(*) as quantidade
                from fiados
                where pago_em is null
                group by cliente
                order by total desc, cliente
                limit %s
                """,
                (limite,),
            )
            return [Devedor(**row) for row in rows]

    def ping(self) -> bool:
        try:
            with self._conectar() as conn:
                conn.execute("select 1")
            return True
        except psycopg.Error:
            return False
