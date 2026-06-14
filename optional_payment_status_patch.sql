-- Optional patch
-- Run this in Supabase SQL Editor only if you want payment insert to update lead status automatically.

create or replace function public.set_lead_payment_verified()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  if new.status = 'PAID' then
    update public.leads
    set status = 'PAYMENT_VERIFIED',
        updated_at = now()
    where id = new.lead_id
      and status in (
        'DEAL',
        'REGISTRATION_FORM_PURCHASED',
        'PAYMENT_PENDING'
      );
  end if;

  return new;
end;
$$;

drop trigger if exists payment_updates_lead_status on public.payments;

create trigger payment_updates_lead_status
after insert or update on public.payments
for each row
execute function public.set_lead_payment_verified();
