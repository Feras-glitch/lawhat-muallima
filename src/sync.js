/* ===== التزامن الاختياري مع خادم Supabase ===== */
const Sync = {
  timer: null, busy: false, lastError: null, lastOk: null,
  cfg() { const s = Store.settings; return (s.sbUrl && s.sbKey && !s.localMode) ? { url: s.sbUrl.replace(/\/$/, ''), key: s.sbKey } : null; },
  token() { return Store.settings.sbSession && Store.settings.sbSession.access_token; },
  headers(json) {
    const c = this.cfg(); const h = { apikey: c.key, Authorization: 'Bearer ' + (this.token() || c.key) };
    if (json) h['Content-Type'] = 'application/json';
    return h;
  },
  async login(email, password) {
    const c = this.cfg(); if (!c) throw new Error('لم يُضبط الخادم');
    const r = await fetch(`${c.url}/auth/v1/token?grant_type=password`, { method: 'POST', headers: { apikey: c.key, 'Content-Type': 'application/json' }, body: JSON.stringify({ email, password }) });
    const j = await r.json();
    if (!r.ok) throw new Error(j.error_description || j.msg || 'فشل الدخول');
    Store.settings.sbSession = { access_token: j.access_token, refresh_token: j.refresh_token, expires_at: Date.now() + (j.expires_in || 3600) * 1000, email: j.user && j.user.email };
    let role = null;
    try { const pr = await fetch(`${c.url}/rest/v1/profiles?select=role&user_id=eq.${j.user.id}`, { headers: { apikey: c.key, Authorization: 'Bearer ' + j.access_token } }); const rows = await pr.json(); role = rows && rows[0] && rows[0].role; } catch (e) {}
    Store.settings.sbRole = ROLES[role] ? role : null;
    Store.saveSettings();
    return Store.settings.sbRole;
  },
  async refresh() {
    const c = this.cfg(); const s = Store.settings.sbSession; if (!c || !s || !s.refresh_token) return false;
    if (Date.now() < s.expires_at - 60000) return true;
    const r = await fetch(`${c.url}/auth/v1/token?grant_type=refresh_token`, { method: 'POST', headers: { apikey: c.key, 'Content-Type': 'application/json' }, body: JSON.stringify({ refresh_token: s.refresh_token }) });
    if (!r.ok) { Store.settings.sbSession = null; Store.saveSettings(); return false; }
    const j = await r.json();
    Store.settings.sbSession = { access_token: j.access_token, refresh_token: j.refresh_token, expires_at: Date.now() + (j.expires_in || 3600) * 1000, email: s.email };
    Store.saveSettings(); return true;
  },
  logout() { Store.settings.sbSession = null; Store.settings.sbRole = null; Store.saveSettings(); },
  /* تصنيف أخطاء الرفع: دائم (صلاحيات/بيانات) أم مؤقت (دخول، خادم، حدّ طلبات، شبكة) */
  isPermanent(status) { return [400, 403, 404, 409, 422].includes(status); },
  transientMsg(status) { return status === 401 ? 'انتهت الجلسة، أعيدي الدخول' : status === 429 ? 'الخادم مشغول (حدّ الطلبات)؛ سيُعاد الرفع تلقائياً' : status >= 500 ? `عطل مؤقت في الخادم (${status})؛ سيُعاد الرفع تلقائياً` : `تعذّر الرفع مؤقتاً (${status})؛ سيُعاد تلقائياً`; },
  schedule() { if (!this.cfg()) return; clearTimeout(this.timer); this.timer = setTimeout(() => this.run(), 1500); },
  async run() {
    if (!this.cfg() || this.busy || !navigator.onLine) return;
    this.busy = true;
    try {
      if (!(await this.refresh())) { this.lastError = 'انتهت الجلسة، أعيدي الدخول'; this.busy = false; UI.renderStatus(); return; }
      const c = this.cfg();
      // دفع: على مرحلتين — السجلات العادية أولاً ثم التراجعات (سياسة الخادم تتحقق من وجود هدف التراجع، ولا ترى صفوف البيان نفسه)
      const toRow = e => ({ id: e.id, ts: e.ts, day: e.day, by: e.by, child: e.child || null, type: e.type, dev: e.dev || null, payload: e });
      const post = async rows => fetch(`${c.url}/rest/v1/events?on_conflict=id`, { method: 'POST', headers: Object.assign(this.headers(true), { Prefer: 'resolution=ignore-duplicates,return=minimal' }), body: JSON.stringify(rows) });
      const pendingAll = Store.raw.filter(e => !e.synced);
      for (const phase of [pendingAll.filter(e => e.type !== 'undo'), pendingAll.filter(e => e.type === 'undo')]) {
        if (!phase.length) continue;
        const r = await post(phase.map(toRow));
        if (r.ok) { for (const e of phase) e.synced = true; Store.saveEvents(); continue; }
        if (!this.isPermanent(r.status)) throw new Error(this.transientMsg(r.status));
        /* رفض صلاحيات (403/4xx دائم): لا نُوقف المزامنة كلها؛ نعزل السجل المرفوض ونحفظه مع سببه.
           خطأ مؤقت أثناء الفحص الفردي (401/408/425/429/5xx/شبكة) يُبقي السجل منتظراً ويوقف الجولة. */
        for (const e of phase) {
          const r1 = await post([toRow(e)]);
          if (r1.ok) { e.synced = true; Store.saveEvents(); continue; }
          if (!this.isPermanent(r1.status)) { Store.saveEvents(); throw new Error(this.transientMsg(r1.status)); }
          let why = 'رفض الخادم (' + r1.status + ')'; try { const j = await r1.json(); if (j && j.message) why += ': ' + j.message; } catch (x) {}
          e.synced = true; e.pushRejected = why;
          const rej = Store.settings.syncRejected || []; if (!rej.some(x => x.id === e.id)) rej.push({ id: e.id, type: e.type, by: e.by, child: e.child || null, day: e.day, reason: 'لم يقبل الخادم الرفع — ' + why, at: Date.now(), payload: e, direction: 'push' }); Store.settings.syncRejected = rej; Store.saveSettings();
        }
        Store.saveEvents();
      }
      // سحب
      let n = 0;
      for (let round = 0; round < 20; round++) {
        let cur = Store.settings.sbCursor;
        if (typeof cur === 'string') { cur = { t: cur, id: '' }; Store.settings.sbCursor = cur; Store.saveSettings(); } /* ترحيل مؤشر 0.3 */
        if (!cur || typeof cur.t !== 'string') cur = { t: '1970-01-01T00:00:00Z', id: '' };
        const t = encodeURIComponent(cur.t), id = encodeURIComponent(cur.id);
        const r2 = await fetch(`${c.url}/rest/v1/events?select=id,by,type,child,payload,inserted_at&or=(inserted_at.gt.${t},and(inserted_at.eq.${t},id.gt.${id}))&order=inserted_at.asc,id.asc&limit=1000`, { headers: this.headers() });
        if (!r2.ok) throw new Error('رفض الخادم السحب: ' + r2.status);
        const rows = await r2.json();
        if (!rows.length) break;
        /* أعمدة الخادم (المحمية بالسياسات) تغلب ما في payload */
        const incoming = rows.map(r => Object.assign({}, r.payload, { id: r.id, by: r.by, type: r.type, child: r.child || undefined, synced: true }));
        const bad = incoming.filter(e => !Store.validEvent(e, incoming));
        if (bad.length) { /* كل المرفوضات تُحفظ مع سببها بلا حد؛ القائمة السابقة تُحفظ كاملة وتُستعاد عند فشل الحفظ */
          const prev = Store.settings.syncRejected || [];
          const next = prev.slice();
          for (const e of bad) if (!next.some(x => x.id === e.id)) next.push({ id: e.id, type: e.type, by: e.by, child: e.child || null, day: e.day, reason: Store.rejectReason(e, incoming), at: Date.now(), payload: e });
          Store.settings.syncRejected = next;
          try { Store.saveSettings(); } catch (err) { Store.settings.syncRejected = prev; this.lastError = 'تعذّر حفظ السجلات المرفوضة (امتلأت الذاكرة)؛ لن يتقدم المؤشر'; UI.renderStatus(); throw new Error(this.lastError); }
        }
        n += Store.importEvents(incoming.filter(e => !bad.includes(e)));
        const last = rows[rows.length - 1]; Store.settings.sbCursor = { t: last.inserted_at, id: last.id }; Store.saveSettings();
        if (rows.length < 1000) break;
      }
      this.lastOk = Date.now(); this.lastError = (Store.settings.syncRejected || []).length ? `${Store.settings.syncRejected.length} سجل مرفوض بانتظار المعالجة (الإعدادات ← المرفوضات)` : null;
      Store.saveSettings();
      if (n) UI.rerender();
    } catch (err) { this.lastError = err.message; }
    this.busy = false; UI.renderStatus();
  },
  started: false,
  start() { if (this.cfg() && !this.started) { this.started = true; this.run(); setInterval(() => this.run(), 30000); window.addEventListener('online', () => this.run()); } },
};

const SETUP_SQL = `-- يُنفَّذ مرة واحدة في SQL Editor داخل مشروع Supabase
create table if not exists public.events (
  id text primary key,
  ts bigint not null,
  day text not null,
  by text,
  child text,
  type text not null,
  dev text,
  payload jsonb not null,
  inserted_at timestamptz default now()
);
create index if not exists events_ts on public.events (ts);
create index if not exists events_inserted on public.events (inserted_at);
alter table public.events enable row level security;
-- الأدوار: جدول لا يكتبه إلا المالك من لوحة Supabase (لا من التطبيق)
create table if not exists public.profiles (
  user_id uuid primary key references auth.users(id) on delete cascade,
  role text not null check (role in ('aya','asst','parent'))
);
alter table public.profiles enable row level security;
-- ترحيل من 0.3: حذف السياسات القديمة (الإدراج المفتوح) قبل إعادة الإنشاء
drop policy if exists "insert_auth" on public.events;
drop policy if exists "read_all_auth" on public.events;
drop policy if exists "insert_own_role" on public.events;
drop policy if exists "read_own_profile" on public.profiles;
create policy "read_own_profile" on public.profiles for select to authenticated using (user_id = auth.uid());
create or replace function public.my_role() returns text language sql stable security definer as
  $$ select role from public.profiles where user_id = auth.uid() $$;
-- القراءة لكل حساب مسجل؛ لا تعديل ولا حذف لأحد
create policy "read_all_auth" on public.events for select to authenticated using (true);
-- الإدراج: باسم دور الحساب فقط، والحقول الخارجية تطابق الداخلية، ونوع الحدث مسموح للدور
create policy "insert_own_role" on public.events for insert to authenticated with check (
  by = public.my_role()
  and payload->>'id' = id and payload->>'by' = by and payload->>'type' = type
  and coalesce(payload->>'child','') = coalesce(child,'')
  and (
    public.my_role() = 'aya'
    or (public.my_role() = 'asst' and type in ('outcome','error','note','session_done','fluency_time','card','yellow_pass','handoff','handoff_update','undo','session_start','session_cancel','fluency_page','tilawa') and coalesce(payload->>'step','') <> 'exam' and coalesce(payload->>'parent','') <> 'true')
    or (public.my_role() = 'parent' and (type in ('parent_exam','note','undo') or (type = 'outcome' and payload->>'parent' = 'true')))
  )
  -- التراجع: عن سجل صاحبه الحساب نفسه فقط، وآية عن سجلات المساعدة أيضاً؛ الهدف يجب أن يكون موجوداً على الخادم
  and (type <> 'undo' or exists (
    select 1 from public.events t where t.id = payload->>'target' and t.type <> 'undo'
      and (t.by = public.my_role() or (public.my_role() = 'aya' and t.by = 'asst'))))
);
-- ثم: Authentication > Users > أنشئ ثلاثة مستخدمين بالبريد وكلمة السر،
-- ثم في Table Editor > profiles أضف صفاً لكل مستخدم: user_id (من صفحة المستخدم) و role: aya / asst / parent`;
