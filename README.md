# 📒 Caderninho do Fiado

![CI/CD](https://github.com/SEU_USUARIO/caderninho/actions/workflows/ci-cd.yml/badge.svg)

Um sistema propositalmente simples, o caderninho de fiado do bar: quem bebeu, quanto deve, quem pagou
e o **mural da vergonha** com os maiores devedores.

A graça não está no domínio, e sim no caminho completo até produção: API em Python com testes,
banco gerenciado, deploy automático, migrações versionadas e monitoramento de erros.

**Demo:** https://SEU-PROJETO.vercel.app · **Docs da API:** https://SEU-PROJETO.vercel.app/docs

## Arquitetura

```mermaid
flowchart LR
    dev[git push / PR] --> gha[GitHub Actions]
    gha -->|ruff + pytest com Postgres| gha
    gha -->|python -m app.migrate| supa[(Supabase Postgres)]
    gha -->|vercel deploy| vercel[Vercel Functions<br/>FastAPI]
    user[Navegador] --> vercel
    vercel -->|psycopg via pooler| supa
    vercel -->|exceções e traces| sentry[Sentry]
    gha -->|release = sha do commit| sentry
```

| Peça | Ferramenta | Papel |
|---|---|---|
| API + página | FastAPI, Pydantic, HTML puro | Rotas REST e uma página que consome a própria API |
| Banco | Supabase (Postgres) | Dados em produção; Postgres no Docker local e no CI |
| Hospedagem | Vercel (Python serverless) | Uma função que serve a app inteira |
| Observabilidade | Sentry | Erros com release (sha do commit) e ambiente |
| CI/CD | GitHub Actions | Lint → testes → migração → deploy → smoke test |
| Qualidade | uv, ruff, pytest, pre-commit, Dependabot | Dependências travadas, estilo, testes e atualizações |

## Endpoints

| Método | Rota | O que faz |
|---|---|---|
| GET | `/` | Página do caderninho |
| GET | `/api/health` | Status da app e do banco (503 se o banco cair) |
| GET | `/api/fiados?pendentes=true` | Lista os fiados |
| POST | `/api/fiados` | Anota um fiado `{cliente, valor, descricao}` |
| POST | `/api/fiados/{id}/pagar` | Dá baixa (404 se não existe, 409 se já foi pago) |
| GET | `/api/ranking?limite=10` | Mural da vergonha |
| GET | `/api/debug/erro` | Só com `ENABLE_DEBUG_ROUTES=true`: erro proposital para testar o Sentry |

## Decisões de projeto

- **Repositório como protocolo.** A API depende de `FiadoRepository`, não do Postgres. Os testes da API
  usam a versão em memória (rápidos, sem banco), e um **teste de contrato** roda os mesmos cenários nas
  duas implementações, garantindo que a versão em memória não mente.
- **SQL puro com psycopg em vez de ORM.** São quatro queries, e um ORM seria mais código do que a app.
- **Uma conexão por requisição, pelo pooler do Supabase** (modo transaction, porta 6543), com
  `prepare_threshold=None`, porque o pooler não suporta prepared statements. Funções serverless não mantêm
  pool de conexões entre invocações.
- **Migrações próprias** (`app/migrate.py`): arquivos `.sql` numerados, registrados em
  `schema_migrations` e aplicados pelo CI **antes** do deploy.
- **RLS ligado sem policies.** O Supabase expõe o schema `public` via API REST com a chave anônima.
  Com RLS ligado e nenhuma policy, essa porta fica fechada. A app conecta como dona da tabela e não é afetada.
- **Deploy pelo Actions, não pela integração git da Vercel** (`git.deploymentEnabled: false`), para
  que nada chegue à produção sem passar por lint, testes e migração.
- **`TEST_DATABASE_URL` separado de `DATABASE_URL`**, porque os testes dão `truncate`, e isso nunca pode
  apontar para produção por engano.
- **Dinheiro é `Decimal`/`numeric(10,2)`**, nunca `float`.

## Rodando localmente

Pré-requisitos: [uv](https://docs.astral.sh/uv/) e Docker.

```bash
uv sync                          # cria o .venv e instala tudo
cp .env.example .env
docker compose up -d --wait      # Postgres local na porta 5433
uv run python -m app.migrate
uv run uvicorn app.main:app --reload
```

Abra http://localhost:8000 (a página) ou http://localhost:8000/docs (Swagger).

Testes:

```bash
uv run pytest                                   # só em memória, sem banco
TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5433/caderninho uv run pytest
```

Ganchos de pre-commit (ruff, e o `requirements.txt` sempre em sincronia com o `uv.lock`):

```bash
uv run pre-commit install
```

> A Vercel instala dependências pelo `requirements.txt`. Ele é gerado do `uv.lock` e o CI falha se os
> dois divergirem.

## Pondo no ar (passo a passo)

### 1. Supabase
1. Crie um projeto em https://supabase.com (plano free).
2. Em **Connect → Transaction pooler**, copie a connection string (porta **6543**) e troque a senha.
   Use o pooler, não a conexão direta: a direta é só IPv6, e o GitHub Actions é IPv4.

### 2. Sentry
1. Crie um projeto em https://sentry.io com a plataforma **FastAPI** e copie o **DSN**.
2. (Opcional, para releases) Crie um **Organization Auth Token** em *Settings → Auth Tokens*.

### 3. Vercel
1. Em https://vercel.com, **Add New → Project** e importe o repositório (framework: *Other*).
2. Em *Settings → Environment Variables*, adicione `DATABASE_URL` e `SENTRY_DSN` para Production e Preview.
3. Anote o **Project ID** (*Settings → General*) e o **Team/Org ID** (*Team Settings → General*).
4. Crie um token em https://vercel.com/account/tokens.

### 4. GitHub
Em *Settings → Secrets and variables → Actions*:

| Tipo | Nome | Valor |
|---|---|---|
| Secret | `VERCEL_TOKEN` | token da Vercel |
| Secret | `VERCEL_ORG_ID` | Team/Org ID |
| Secret | `VERCEL_PROJECT_ID` | Project ID |
| Secret | `DATABASE_URL` | string do pooler do Supabase |
| Secret | `SENTRY_AUTH_TOKEN` | opcional; sem ele o passo de release é pulado |
| Variable | `PRODUCTION_URL` | `https://seu-projeto.vercel.app` |
| Variable | `SENTRY_ORG` / `SENTRY_PROJECT` | slugs do Sentry |

Depois, em *Settings → Branches*, proteja a `main` exigindo os checks **Lint e formatação** e
**Testes (com Postgres)**.

### 5. Testando o Sentry
Coloque `ENABLE_DEBUG_ROUTES=true` na Vercel, faça o redeploy, acesse `/api/debug/erro`, veja o erro
chegar no Sentry e desligue a variável de novo.

## Próximos passos (ideias)

- [ ] Autenticação (Supabase Auth) para só o dono do bar anotar
- [ ] Ambiente de preview com banco próprio (hoje o preview usa o mesmo banco)
- [ ] Editar e apagar fiado
- [ ] Juros por atraso (o Seu Elias ia gostar)
- [ ] Uptime check (Sentry Crons ou UptimeRobot) batendo em `/api/health`
