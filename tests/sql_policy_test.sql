-- اختبار سياسات الخادم: كل حالة إما «يُقبل» أو «يُرفض». أي خروج عن المتوقع يوقف التشغيل بخطأ.
\set ON_ERROR_STOP 1
grant usage on schema public to authenticated;
grant select, insert, update, delete on public.events to authenticated;
grant select, insert, update, delete on public.profiles to authenticated;
insert into auth.users values ('00000000-0000-0000-0000-0000000000a1'), ('00000000-0000-0000-0000-0000000000a2'), ('00000000-0000-0000-0000-0000000000a3'), ('00000000-0000-0000-0000-0000000000a4');
insert into public.profiles values ('00000000-0000-0000-0000-0000000000a1', 'aya'), ('00000000-0000-0000-0000-0000000000a2', 'asst'), ('00000000-0000-0000-0000-0000000000a3', 'parent');

create or replace function public.t_ok(label text, q text) returns void language plpgsql as $$
begin
  execute q; raise notice 'PASS (قُبل): %', label;
exception when insufficient_privilege or check_violation then raise exception 'FAIL: كان يجب قبول «%» لكنه رُفض: %', label, sqlerrm;
end $$;
create or replace function public.t_deny(label text, q text) returns void language plpgsql as $$
begin
  begin execute q; exception when insufficient_privilege or check_violation then raise notice 'PASS (رُفض): %', label; return; end;
  raise exception 'FAIL: كان يجب رفض «%» لكنه قُبل', label;
end $$;
create or replace function public.t_zero(label text, q text) returns void language plpgsql as $$
declare n int;
begin
  begin execute q; get diagnostics n = row_count; exception when insufficient_privilege then raise notice 'PASS (رُفض): %', label; return; end;
  if n <> 0 then raise exception 'FAIL: «%» أثّر في % صف', label, n; end if;
  raise notice 'PASS (0 صفوف): %', label;
end $$;
grant execute on function public.t_ok(text, text), public.t_deny(text, text), public.t_zero(text, text) to authenticated;

-- مولّد صف حدث متسق (payload يطابق الأعمدة)
create or replace function public.ev(id text, by text, type text, child text, extra jsonb default '{}') returns text language sql immutable as $$
  select format('insert into public.events(id, ts, day, by, child, type, payload) values (%L, 1, %L, %L, %L, %L, %L::jsonb)',
    id, '2026-11-05', by, child, type,
    (jsonb_build_object('id', id, 'by', by, 'type', type, 'ts', 1, 'day', '2026-11-05') || case when child is null then '{}'::jsonb else jsonb_build_object('child', child) end || extra)::text)
$$;
grant execute on function public.ev(text, text, text, text, jsonb) to authenticated;

-- ===== آية =====
set request.jwt.claim.sub = '00000000-0000-0000-0000-0000000000a1'; set role authenticated;
select t_ok('آية: ملاحظة', ev('aya-note', 'aya', 'note', 'dalal', '{"text":"x"}'));
select t_ok('آية: تلوين', ev('aya-color', 'aya', 'color', 'dalal', '{"page":570,"color":"green"}'));
select t_ok('آية: قرار', ev('aya-dec', 'aya', 'decision', 'dalal', '{"kind":"pause"}'));
select t_deny('آية: باسم المساعدة', ev('aya-as-asst', 'asst', 'note', 'dalal', '{"text":"x"}'));
reset role;

-- ===== المساعدة =====
set request.jwt.claim.sub = '00000000-0000-0000-0000-0000000000a2'; set role authenticated;
select t_ok('المساعدة: ملاحظة', ev('asst-note', 'asst', 'note', 'dalal', '{"text":"x"}'));
select t_ok('المساعدة: نتيجة بعيد', ev('asst-out', 'asst', 'outcome', 'dalal', '{"page":570,"step":"far","result":"clean"}'));
select t_ok('المساعدة: بطاقة تسليم', ev('asst-ho', 'asst', 'handoff', 'dalal', '{"key":"k","to":"aya","items":[]}'));
select t_deny('المساعدة: باسم آية', ev('asst-as-aya', 'aya', 'note', 'dalal', '{"text":"x"}'));
select t_deny('المساعدة: تلوين', ev('asst-color', 'asst', 'color', 'dalal', '{"page":570,"color":"green"}'));
select t_deny('المساعدة: حفظ جديد', ev('asst-new', 'asst', 'new_page', 'dalal', '{"page":542,"linesFrom":1,"linesTo":15}'));
select t_deny('المساعدة: قرار', ev('asst-dec', 'asst', 'decision', 'dalal', '{"kind":"pause"}'));
select t_deny('المساعدة: فحص خميس', ev('asst-exam', 'asst', 'outcome', 'dalal', '{"page":570,"step":"exam","result":"clean"}'));
select t_deny('المساعدة: فحص ولي أمر', ev('asst-pexam', 'asst', 'outcome', 'dalal', '{"page":570,"step":"far","result":"clean","parent":true}'));
select t_deny('المساعدة: payload يخالف العمود', format('insert into public.events(id, ts, day, by, child, type, payload) values (%L, 1, %L, %L, %L, %L, %L::jsonb)', 'asst-mismatch', '2026-11-05', 'asst', 'dalal', 'note', '{"id":"asst-mismatch","by":"aya","type":"note","child":"dalal"}'));
select t_deny('المساعدة: child مخالف', format('insert into public.events(id, ts, day, by, child, type, payload) values (%L, 1, %L, %L, %L, %L, %L::jsonb)', 'asst-mischild', '2026-11-05', 'asst', 'dalal', 'note', '{"id":"asst-mischild","by":"asst","type":"note","child":"farah"}'));
-- التراجع (LM0101-01): سجل «مسموم» target=معرّفه لا يفتح باب التراجع عن سجل آية
select t_ok('المساعدة: تراجع عن سجلها', ev('asst-undo-own', 'asst', 'undo', 'dalal', '{"target":"asst-note"}'));
select t_ok('المساعدة: ملاحظة بحقل target إضافي', ev('poison', 'asst', 'note', 'dalal', '{"text":"x","target":"poison"}'));
select t_deny('المساعدة: تراجع عن سجل آية', ev('asst-undo-aya', 'asst', 'undo', 'dalal', '{"target":"aya-color"}'));
select t_deny('المساعدة: تراجع عن هدف غير موجود', ev('asst-undo-none', 'asst', 'undo', 'dalal', '{"target":"no-such-id"}'));
select t_deny('المساعدة: تراجع عن تراجع', ev('asst-undo-undo', 'asst', 'undo', 'dalal', '{"target":"asst-undo-own"}'));
select t_zero('المساعدة: حذف السجلات', 'delete from public.events');
select t_zero('المساعدة: تعديل by', $q$update public.events set by = 'aya' where by = 'asst'$q$);
select t_deny('المساعدة: إضافة دور لنفسها', $q$insert into public.profiles values ('00000000-0000-0000-0000-0000000000a4', 'aya')$q$);
select t_zero('المساعدة: ترقية دورها', $q$update public.profiles set role = 'aya'$q$);
reset role;

-- ===== آية تتراجع عن سجل المساعدة =====
set request.jwt.claim.sub = '00000000-0000-0000-0000-0000000000a1'; set role authenticated;
select t_ok('آية: تراجع عن سجل المساعدة', ev('aya-undo-asst', 'aya', 'undo', 'dalal', '{"target":"asst-out"}'));
reset role;

-- ===== ولي الأمر =====
set request.jwt.claim.sub = '00000000-0000-0000-0000-0000000000a3'; set role authenticated;
select t_ok('ولي الأمر: فحص شهري', ev('par-exam', 'parent', 'outcome', 'dalal', '{"page":570,"step":"exam","result":"clean","parent":true}'));
select t_ok('ولي الأمر: ملاحظة', ev('par-note', 'parent', 'note', 'dalal', '{"text":"x"}'));
select t_deny('ولي الأمر: قرار', ev('par-dec', 'parent', 'decision', 'dalal', '{"kind":"pause"}'));
select t_deny('ولي الأمر: نتيجة معلمة', ev('par-out', 'parent', 'outcome', 'dalal', '{"page":570,"step":"far","result":"clean"}'));
select t_deny('ولي الأمر: تراجع عن سجل آية', ev('par-undo-aya', 'parent', 'undo', 'dalal', '{"target":"aya-note"}'));
reset role;

-- ===== حساب بلا دور =====
set request.jwt.claim.sub = '00000000-0000-0000-0000-0000000000a4'; set role authenticated;
select t_deny('حساب بلا دور: ملاحظة', ev('nop-note', 'aya', 'note', 'dalal', '{"text":"x"}'));
reset role;

-- ===== القراءة (LM0121-R2-01): الأدوار الثلاثة تقرأ؛ حساب بلا دور لا يقرأ؛ سحب الدور يمنع القراءة بالجلسة نفسها =====
create or replace function public.t_reads(label text, want int) returns void language plpgsql as $$
declare n int; begin select count(*) into n from public.events;
  if n <> want then raise exception 'FAIL: %: قرأ % صفاً بدل %', label, n, want; end if;
  raise notice 'PASS (قراءة % صفاً): %', n, label; end $$;
grant execute on function public.t_reads(text, int) to authenticated;
set request.jwt.claim.sub = '00000000-0000-0000-0000-0000000000a1'; set role authenticated; select t_reads('آية تقرأ كل السجلات', 11); reset role;
set request.jwt.claim.sub = '00000000-0000-0000-0000-0000000000a2'; set role authenticated; select t_reads('المساعدة تقرأ كل السجلات', 11); reset role;
set request.jwt.claim.sub = '00000000-0000-0000-0000-0000000000a3'; set role authenticated; select t_reads('ولي الأمر يقرأ كل السجلات', 11); reset role;
set request.jwt.claim.sub = '00000000-0000-0000-0000-0000000000a4'; set role authenticated; select t_reads('حساب مصادَق بلا دور لا يقرأ شيئاً', 0); reset role;
delete from public.profiles where user_id = '00000000-0000-0000-0000-0000000000a3';
set request.jwt.claim.sub = '00000000-0000-0000-0000-0000000000a3'; set role authenticated; select t_reads('سُحب دور ولي الأمر: لا قراءة بالجلسة نفسها', 0); reset role;
insert into public.profiles values ('00000000-0000-0000-0000-0000000000a3', 'parent');
set request.jwt.claim.sub = '00000000-0000-0000-0000-0000000000a3'; set role authenticated; select t_reads('أُعيد الدور: تعود القراءة', 11); reset role;

-- ===== السجل النهائي كما يتوقعه الاختبار =====
do $$ declare n int; begin
  select count(*) into n from public.events; 
  if n <> 11 then raise exception 'FAIL: عدد الصفوف % بدل 11', n; end if;
  if exists (select 1 from public.events where id = 'asst-undo-aya') then raise exception 'FAIL: تراجع المساعدة عن آية موجود'; end if;
  raise notice 'PASS: عدد الصفوف النهائي 11 (كل المقبول فقط) ولا تعديل ولا حذف';
end $$;
