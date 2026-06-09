-- Fase 2: tabela profiles + trigger de criação + RLS (defesa em duas camadas).

create table if not exists public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  email text not null,
  full_name text,
  company text,
  role text not null default 'user' check (role in ('user', 'admin')),
  status text not null default 'pending' check (status in ('pending', 'approved', 'rejected')),
  created_at timestamptz not null default now()
);

comment on table public.profiles is
  'Perfil de cada usuário (1:1 com auth.users). status controla a lista de espera.';

-- ── Trigger: ao criar usuário no Auth, insere profile com status pending ──
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id, email, full_name)
  values (
    new.id,
    new.email,
    coalesce(new.raw_user_meta_data ->> 'full_name', new.raw_user_meta_data ->> 'name')
  )
  on conflict (id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- ── Helper: is_admin() com security definer para evitar recursão de RLS ──
create or replace function public.is_admin()
returns boolean
language sql
security definer
set search_path = public
stable
as $$
  select exists (
    select 1 from public.profiles
    where id = auth.uid() and role = 'admin'
  );
$$;

-- ── RLS ──
alter table public.profiles enable row level security;

-- Usuário lê o próprio perfil; admin lê todos.
drop policy if exists "profiles_select_own_or_admin" on public.profiles;
create policy "profiles_select_own_or_admin"
  on public.profiles for select
  using (id = auth.uid() or public.is_admin());

-- Usuário atualiza apenas dados cadastrais do próprio perfil.
-- role e status são protegidos por trigger abaixo (não pelo client).
drop policy if exists "profiles_update_own" on public.profiles;
create policy "profiles_update_own"
  on public.profiles for update
  using (id = auth.uid())
  with check (id = auth.uid());

-- Admin atualiza qualquer perfil (aprovação/rejeição da lista de espera).
drop policy if exists "profiles_update_admin" on public.profiles;
create policy "profiles_update_admin"
  on public.profiles for update
  using (public.is_admin())
  with check (public.is_admin());

-- Sem insert/delete pelo client: insert vem do trigger; delete via cascade.

-- ── Proteção de colunas sensíveis: não-admin não altera role/status ──
create or replace function public.protect_profile_columns()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  if (new.role is distinct from old.role or new.status is distinct from old.status) then
    if not public.is_admin() and auth.uid() is not null then
      raise exception 'Apenas administradores podem alterar role ou status.';
    end if;
  end if;
  return new;
end;
$$;

drop trigger if exists protect_profile_columns on public.profiles;
create trigger protect_profile_columns
  before update on public.profiles
  for each row execute function public.protect_profile_columns();
