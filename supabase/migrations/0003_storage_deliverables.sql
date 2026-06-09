-- Fase 5: bucket privado para entregáveis.
-- Download sempre via URL assinada (1h) gerada server-side; sem acesso público.

insert into storage.buckets (id, name, public)
values ('deliverables', 'deliverables', false)
on conflict (id) do nothing;

-- Nenhuma policy de SELECT/INSERT em storage.objects para este bucket:
-- escrita e assinatura de URLs acontecem exclusivamente com service role
-- (worker e route handler), que ignora RLS. Clientes anon/authenticated
-- não têm acesso direto aos objetos.
