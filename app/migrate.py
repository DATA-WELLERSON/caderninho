"""Aplica as migrações de `migrations/*.sql` em ordem, uma única vez cada.

Uso: DATABASE_URL=... python -m app.migrate
"""

from pathlib import Path

import psycopg

from app.config import get_settings

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def aplicar_migracoes(database_url: str) -> list[str]:
    with psycopg.connect(
        database_url, autocommit=True, prepare_threshold=None, connect_timeout=10
    ) as conn:
        conn.execute(
            """
            create table if not exists schema_migrations (
                version text primary key,
                applied_at timestamptz not null default now()
            )
            """
        )
        aplicadas = {row[0] for row in conn.execute("select version from schema_migrations")}
        novas = []
        for arquivo in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if arquivo.stem in aplicadas:
                continue
            with conn.transaction():
                conn.execute(arquivo.read_text(encoding="utf-8"))
                conn.execute("insert into schema_migrations (version) values (%s)", (arquivo.stem,))
            novas.append(arquivo.stem)
    return novas


if __name__ == "__main__":
    novas = aplicar_migracoes(get_settings().database_url)
    print(f"Migrações aplicadas: {novas or 'nenhuma, banco já está em dia'}")
