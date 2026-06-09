-- Fase 3: jobs, job_steps, deliverables, messages + RLS.

create table if not exists public.jobs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles (id) on delete cascade,
  title text not null,
  prompt text not null,
  status text not null default 'queued'
    check (status in ('queued', 'planning', 'running', 'delivered', 'failed', 'cancelled')),
  plan jsonb,
  error text,
  created_at timestamptz not null default now(),
  started_at timestamptz,
  finished_at timestamptz
);

create index if not exists jobs_user_id_created_at_idx
  on public.jobs (user_id, created_at desc);

create table if not exists public.job_steps (
  id uuid primary key default gen_random_uuid(),
  job_id uuid not null references public.jobs (id) on delete cascade,
  ordem int not null,
  descricao text not null,
  status text not null default 'queued'
    check (status in ('queued', 'running', 'done', 'failed')),
  output jsonb,
  started_at timestamptz,
  finished_at timestamptz
);

create index if not exists job_steps_job_id_ordem_idx
  on public.job_steps (job_id, ordem);

create table if not exists public.deliverables (
  id uuid primary key default gen_random_uuid(),
  job_id uuid not null references public.jobs (id) on delete cascade,
  tipo text not null check (tipo in ('pptx', 'pdf', 'docx', 'xlsx')),
  filename text not null,
  storage_path text not null,
  size_bytes bigint,
  created_at timestamptz not null default now()
);

create index if not exists deliverables_job_id_idx
  on public.deliverables (job_id);

create table if not exists public.messages (
  id uuid primary key default gen_random_uuid(),
  job_id uuid not null references public.jobs (id) on delete cascade,
  role text not null check (role in ('user', 'eva', 'system')),
  content text not null,
  created_at timestamptz not null default now()
);

create index if not exists messages_job_id_created_at_idx
  on public.messages (job_id, created_at);

-- ── Helper: usuário é dono do job? ──
create or replace function public.owns_job(target_job_id uuid)
returns boolean
language sql
security definer
set search_path = public
stable
as $$
  select exists (
    select 1 from public.jobs
    where id = target_job_id and user_id = auth.uid()
  );
$$;

-- ── RLS: jobs ──
alter table public.jobs enable row level security;

drop policy if exists "jobs_select_own_or_admin" on public.jobs;
create policy "jobs_select_own_or_admin"
  on public.jobs for select
  using (user_id = auth.uid() or public.is_admin());

drop policy if exists "jobs_insert_own" on public.jobs;
create policy "jobs_insert_own"
  on public.jobs for insert
  with check (user_id = auth.uid());

-- Transições de status são feitas pelo worker (service role, ignora RLS).
-- Usuário só pode cancelar o próprio job enquanto na fila.
drop policy if exists "jobs_cancel_own" on public.jobs;
create policy "jobs_cancel_own"
  on public.jobs for update
  using (user_id = auth.uid())
  with check (user_id = auth.uid());

-- ── RLS: job_steps (leitura via posse do job; escrita só service role) ──
alter table public.job_steps enable row level security;

drop policy if exists "job_steps_select_own_or_admin" on public.job_steps;
create policy "job_steps_select_own_or_admin"
  on public.job_steps for select
  using (public.owns_job(job_id) or public.is_admin());

-- ── RLS: deliverables (leitura via posse do job; escrita só service role) ──
alter table public.deliverables enable row level security;

drop policy if exists "deliverables_select_own_or_admin" on public.deliverables;
create policy "deliverables_select_own_or_admin"
  on public.deliverables for select
  using (public.owns_job(job_id) or public.is_admin());

-- ── RLS: messages ──
alter table public.messages enable row level security;

drop policy if exists "messages_select_own_or_admin" on public.messages;
create policy "messages_select_own_or_admin"
  on public.messages for select
  using (public.owns_job(job_id) or public.is_admin());

drop policy if exists "messages_insert_own_user" on public.messages;
create policy "messages_insert_own_user"
  on public.messages for insert
  with check (public.owns_job(job_id) and role = 'user');
