create table fiados (
    id bigint generated always as identity primary key,
    cliente text not null check (length(cliente) between 1 and 60),
    valor numeric(10, 2) not null check (valor > 0),
    descricao text not null default '',
    criado_em timestamptz not null default now(),
    pago_em timestamptz
);

create index fiados_pendentes_idx on fiados (cliente) where pago_em is null;

-- O Supabase expõe o schema public pela API REST com a chave anon.
-- RLS ligado e sem policies = ninguém lê pela API REST; a aplicação conecta
-- como dono da tabela (postgres), que não é afetado.
alter table fiados enable row level security;
