-- Payment obligations patch for TBCIS Admission Management System
-- Run this once in Supabase SQL Editor before deploying app.py v2.

drop index if exists public.unique_paid_payment_per_item;
drop index if exists unique_paid_payment_per_item;

alter table public.payments
add column if not exists obligation_id uuid;

alter table public.payments
alter column item type text using item::text;

create table if not exists public.payment_obligations (
  id uuid primary key default gen_random_uuid(),
  lead_id uuid not null references public.leads(id) on delete cascade,
  category text not null,
  description text not null,
  amount_due numeric(14,2) not null check (amount_due >= 0),
  due_date date,
  status text not null default 'OPEN',
  created_by_email text references public.app_users(email),
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.payments
drop constraint if exists payments_obligation_id_fkey;

alter table public.payments
add constraint payments_obligation_id_fkey
foreign key (obligation_id)
references public.payment_obligations(id)
on delete set null;

alter table public.payment_obligations enable row level security;

grant select, insert, update on public.payment_obligations to authenticated;

drop policy if exists payment_obligations_select_policy on public.payment_obligations;
create policy payment_obligations_select_policy
on public.payment_obligations
for select
to authenticated
using (
  public.current_user_role() in ('FINANCE', 'PRINCIPAL')
);

drop policy if exists payment_obligations_insert_policy on public.payment_obligations;
create policy payment_obligations_insert_policy
on public.payment_obligations
for insert
to authenticated
with check (
  public.current_user_role() in ('FINANCE', 'PRINCIPAL')
);

drop policy if exists payment_obligations_update_policy on public.payment_obligations;
create policy payment_obligations_update_policy
on public.payment_obligations
for update
to authenticated
using (
  public.current_user_role() in ('FINANCE', 'PRINCIPAL')
)
with check (
  public.current_user_role() in ('FINANCE', 'PRINCIPAL')
);

drop trigger if exists set_payment_obligations_updated_at on public.payment_obligations;
create trigger set_payment_obligations_updated_at
before update on public.payment_obligations
for each row
execute function public.set_updated_at();

create or replace function public.audit_trigger()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  v_admission_id text;
  v_record_id uuid;
  old_data jsonb;
  new_data jsonb;
begin
  if tg_op in ('UPDATE', 'DELETE') then
    old_data := to_jsonb(old);
  end if;

  if tg_op in ('INSERT', 'UPDATE') then
    new_data := to_jsonb(new);
  end if;

  if tg_op = 'DELETE' then
    v_record_id := old.id;
  else
    v_record_id := new.id;
  end if;

  if tg_table_name = 'leads' then
    if tg_op = 'DELETE' then
      v_admission_id := old.admission_id;
    else
      v_admission_id := new.admission_id;
    end if;

  elsif tg_table_name in ('students', 'payments', 'uniforms', 'payment_obligations') then
    if tg_op = 'DELETE' then
      select admission_id into v_admission_id
      from public.leads
      where id = old.lead_id;
    else
      select admission_id into v_admission_id
      from public.leads
      where id = new.lead_id;
    end if;
  end if;

  insert into public.audit_logs (
    actor_email,
    action,
    table_name,
    record_id,
    admission_id,
    details
  )
  values (
    public.current_user_email(),
    tg_op,
    tg_table_name,
    v_record_id,
    v_admission_id,
    jsonb_strip_nulls(
      jsonb_build_object(
        'old', old_data,
        'new', new_data
      )
    )
  );

  if tg_op = 'DELETE' then
    return old;
  end if;

  return new;
end;
$$;

drop trigger if exists audit_payment_obligations on public.payment_obligations;
create trigger audit_payment_obligations
after insert or update or delete on public.payment_obligations
for each row
execute function public.audit_trigger();

create index if not exists payment_obligations_lead_id_idx
on public.payment_obligations(lead_id);

create index if not exists payments_obligation_id_idx
on public.payments(obligation_id);
