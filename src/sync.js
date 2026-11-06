/* ===== التزامن الاختياري مع خادم Supabase ===== */
/* هوية الخادم = رابط المشروع مطبَّعاً. لكل خادم حالته المستقلة في settings.servers:
   قبول صريح (accepted)، مؤشر السحب، المرفوضات، وتقرير آخر مطابقة.
   وفي كل سجل: e.sv = الخوادم التي ثبت وجوده عليها، e.rj = الخوادم التي رفضته رفضاً دائماً.
   الجلسة مربوطة بالخادم الذي أصدرها (sbSession.sid) فلا تنتقل إلى غيره. */
function serverId(url) { return String(url || '').trim().replace(/\/+$/, '').toLowerCase(); }
const hasIn = (arr, v) => Array.isArray(arr) && arr.includes(v);
const PUSH_CHUNK = 500;
const PAGE = 1000;

const Sync = {
  timer: null, busy: false, lastError: null, lastOk: null, incomplete: false, lastIds: null,
  cfg() {
    const s = Store.settings;
    if (!s.sbUrl || !s.sbKey || s.localMode) return null;
    const id = serverId(s.sbUrl);
    if (!(s.servers && s.servers[id] && s.servers[id].accepted)) return null;
    return { url: s.sbUrl.trim().replace(/\/+$/, ''), key: s.sbKey.trim(), id };
  },
  sid() { const c = this.cfg(); return c ? c.id : null; },
  st(id) { id = id || this.sid(); if (!id) return null; return (Store.settings.servers || {})[id] || null; },
  session() { const s = Store.settings.sbSession; return s && s.sid && s.sid === this.sid() ? s : null; },
  role() { return this.session() && ROLES[Store.settings.sbRole] ? Store.settings.sbRole : null; },
  token() { const s = this.session(); return s && s.access_token; },
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
    Store.settings.sbSession = { sid: c.id, access_token: j.access_token, refresh_token: j.refresh_token, expires_at: Date.now() + (j.expires_in || 3600) * 1000, email: j.user && j.user.email };
    let role = null;
    try {
      const pr = await fetch(`${c.url}/rest/v1/profiles?select=role&user_id=eq.${j.user.id}`, { headers: { apikey: c.key, Authorization: 'Bearer ' + j.access_token } });
      const rows = await pr.json(); role = rows && rows[0] && rows[0].role;
    } catch (e) {}
    Store.settings.sbRole = ROLES[role] ? role : null;
    Store.saveSettings();
    return Store.settings.sbRole;
  },
  async refresh() {
    const c = this.cfg(); const s = this.session(); if (!c || !s || !s.refresh_token) return false;
    if (Date.now() < s.expires_at - 60000) return true;
    const r = await fetch(`${c.url}/auth/v1/token?grant_type=refresh_token`, { method: 'POST', headers: { apikey: c.key, 'Content-Type': 'application/json' }, body: JSON.stringify({ refresh_token: s.refresh_token }) });
    if (!r.ok) { Store.settings.sbSession = null; Store.saveSettings(); return false; }
    const j = await r.json();
    Store.settings.sbSession = { sid: c.id, access_token: j.access_token, refresh_token: j.refresh_token, expires_at: Date.now() + (j.expires_in || 3600) * 1000, email: s.email };
    Store.saveSettings(); return true;
  },
  logout() { Store.settings.sbSession = null; Store.settings.sbRole = null; Store.saveSettings(); },

  /* ===== تغيير الخادم ===== */
  isKnown(url) { const all = Store.settings.servers || {}; const x = all[serverId(url)]; return !!(x && x.accepted); },
  /* الانتقال إلى خادم مقبول (أو قبوله الآن بعد اختيار صريح): لا تنتقل الجلسة ولا المؤشر، وتُجرى مطابقة كاملة عند أول تزامن */
  switchTo(url, key) {
    const s = Store.settings; const id = serverId(url);
    s.servers = s.servers || {};
    if (!s.servers[id]) s.servers[id] = { cursor: null, rejected: [], since: Date.now() };
    Object.assign(s.servers[id], { accepted: true, needReconcile: true });
    s.sbUrl = url.trim(); s.sbKey = key.trim(); s.localMode = false;
    s.sbSession = null; s.sbRole = null;
    this.lastError = null; this.lastOk = null; this.incomplete = false; this.lastIds = null;
    Store.saveSettings();
  },
  /* عدد سجلات هذا الجهاز بحسب حالتها على خادم: سجلات الدور الحالي المنتظرة، وسجلات أدوار أخرى ليست عليه */
  counts(id) {
    id = id || this.sid(); const me = this.role(); const r = { ownPending: 0, waitingTarget: 0, others: {}, othersTotal: 0, rejected: 0 };
    if (!id) return r;
    let byId = null;
    for (const e of Store.raw) {
      if (hasIn(e.sv, id)) continue;
      if (hasIn(e.rj, id)) { r.rejected++; continue; }
      if (me && e.by === me) {
        r.ownPending++;
        if (e.type === 'undo') { byId = byId || new Map(Store.raw.map(x => [x.id, x])); const t = byId.get(e.target); if (!t || !hasIn(t.sv, id)) r.waitingTarget++; }
      } else { const k = e.by || '?'; r.others[k] = (r.others[k] || 0) + 1; r.othersTotal++; }
    }
    return r;
  },

  /* ===== تصنيف الأخطاء ===== */
  /* ترتيب المؤشرات: الوقت ثم المعرّف (نصوص الخادم بصيغة واحدة فتُقارن نصاً عند تساوي الميلي ثانية) */
  cmpCursor(a, b) { if (a.t === b.t) return a.id < b.id ? -1 : a.id > b.id ? 1 : 0; const d = Date.parse(a.t) - Date.parse(b.t); return d || (a.t < b.t ? -1 : 1); },
  isPermanent(status) { return [400, 403, 409, 422].includes(status); },
  transientMsg(status) { return status === 401 ? 'انتهت الجلسة، أعيدي الدخول' : status === 429 ? 'الخادم مشغول (حدّ الطلبات)؛ سيُعاد الرفع تلقائياً' : status >= 500 ? `عطل مؤقت في الخادم (${status})؛ سيُعاد الرفع تلقائياً` : `تعذّر الرفع مؤقتاً (${status})؛ سيُعاد تلقائياً`; },
  schedule() { if (!this.cfg()) return; clearTimeout(this.timer); this.timer = setTimeout(() => this.run(), 1500); },
  /* أي تغيير للخادم أثناء الجولة يوقفها: لا يُكتب مؤشر أو علامة لخادم على خادم آخر */
  guard(c) { if (this.sid() !== c.id) throw new Error('تغيّر الخادم أثناء المزامنة؛ أُوقفت الجولة'); },

  async run() {
    const c = this.cfg();
    if (!c || this.busy || !navigator.onLine) return;
    this.busy = true;
    try {
      if (!(await this.refresh())) { this.lastError = 'انتهت الجلسة، أعيدي الدخول'; return; }
      const st = this.st(c.id);
      const full = !!st.needReconcile;
      if (full) await this.reconcile(c);
      await this.push(c);
      let n = await this.pull(c);
      /* فحص رخيص كل جولة: خادم يحمل أقل مما ثبت رفعه إليه = استُعيد من نسخة أقدم أو فُقد منه شيء */
      if (!full && !this.incomplete && await this.countMismatch(c)) { await this.reconcile(c); await this.push(c); n += await this.pull(c); }
      if (this.lastIds && this.lastIds.sid === c.id) this.writeReport(c);
      this.guard(c);
      const rejN = st.rejected.length;
      this.lastOk = Date.now();
      this.lastError = this.incomplete ? 'المزامنة لم تكتمل بعد (دفعة كبيرة)؛ تُستكمل تلقائياً' : rejN ? `${rejN} سجل مرفوض بانتظار المعالجة (الإعدادات ← المرفوضات)` : null;
      Store.saveSettings();
      if (n) UI.rerender();
    } catch (err) { this.lastError = err.message; }
    finally { this.busy = false; UI.renderStatus(); }
  },

  /* ===== الرفع: سجلات الدور الحالي التي ليست على هذا الخادم؛ العادية أولاً ثم التراجعات، بدفعات ===== */
  toRow(e) { return { id: e.id, ts: e.ts, day: e.day, by: e.by, child: e.child || null, type: e.type, dev: e.dev || null, payload: Store.clean(e) }; },
  async push(c) {
    const me = this.role(); if (!me) return;
    const post = rows => fetch(`${c.url}/rest/v1/events?on_conflict=id`, { method: 'POST', headers: Object.assign(this.headers(true), { Prefer: 'resolution=ignore-duplicates,return=minimal' }), body: JSON.stringify(rows) });
    const all = Store.raw.filter(e => e.by === me && !hasIn(e.sv, c.id) && !hasIn(e.rj, c.id));
    const byId = new Map(Store.raw.map(e => [e.id, e]));
    /* التراجع يُرفع بعد أن يثبت هدفه على هذا الخادم (سياسة الخادم تشترطه)؛ هدف لم يصل بعد (سجل دور آخر لم يرفعه صاحبه) = ينتظر ولا يُعدّ مرفوضاً */
    const undoReady = () => all.filter(e => e.type === 'undo' && !hasIn(e.sv, c.id) && (t => t && hasIn(t.sv, c.id))(byId.get(e.target)));
    for (const getPhase of [() => all.filter(e => e.type !== 'undo'), undoReady]) {
      const phase = getPhase();
      for (let i = 0; i < phase.length; i += PUSH_CHUNK) {
        const chunk = phase.slice(i, i + PUSH_CHUNK);
        const r = await post(chunk.map(e => this.toRow(e)));
        this.guard(c);
        if (r.ok) { for (const e of chunk) Store.markOn(e, c.id); Store.saveEvents(chunk); continue; }
        if (!this.isPermanent(r.status)) throw new Error(this.transientMsg(r.status));
        /* رفض دائم: يُعزل السجل المرفوض وحده مع سببه ولا تتوقف البقية.
           خطأ مؤقت أثناء الفحص الفردي يُبقي السجل منتظراً ويوقف الجولة. */
        for (const e of chunk) {
          const r1 = await post([this.toRow(e)]);
          this.guard(c);
          if (r1.ok) { Store.markOn(e, c.id); Store.saveEvents([e]); continue; }
          if (!this.isPermanent(r1.status)) throw new Error(this.transientMsg(r1.status));
          let why = 'رفض الخادم (' + r1.status + ')'; try { const j = await r1.json(); if (j && j.message) why += ': ' + j.message; } catch (x) {}
          e.rj = (e.rj || []).filter(x => x !== c.id).concat(c.id);
          const st = this.st(c.id);
          if (!st.rejected.some(x => x.id === e.id)) st.rejected.push({ id: e.id, type: e.type, by: e.by, child: e.child || null, day: e.day, reason: 'لم يقبل الخادم الرفع — ' + why, at: Date.now(), payload: Store.clean(e), direction: 'push' });
          Store.saveEvents([e]); Store.saveSettings();
        }
      }
    }
  },

  /* ===== السحب بمؤشر (inserted_at, id) خاص بهذا الخادم ===== */
  async pull(c) {
    const st = this.st(c.id);
    let n = 0;
    const EPOCH = '1970-01-01T00:00:00Z';
    let cur = st.cursor;
    if (!cur || typeof cur.t !== 'string') cur = { t: EPOCH, id: '' };
    /* نافذة تداخل 5 ثوانٍ مرة واحدة في بداية الجولة (صف التُزم متأخراً لا يضيع؛ المكرر يُزال بالمعرّف)، ثم مؤشر متقدم حصراً */
    let q = cur.t === EPOCH ? { t: cur.t, id: cur.id } : { t: new Date(Math.max(0, Date.parse(cur.t) - 5000)).toISOString(), id: '' };
    let best = cur, complete = false;
    for (let round = 0; round < 50; round++) {
      const t = encodeURIComponent(q.t), id = encodeURIComponent(q.id);
      const r2 = await fetch(`${c.url}/rest/v1/events?select=id,by,type,child,payload,inserted_at&or=(inserted_at.gt.${t},and(inserted_at.eq.${t},id.gt.${id}))&order=inserted_at.asc,id.asc&limit=${PAGE}`, { headers: this.headers() });
      this.guard(c);
      if (!r2.ok) throw new Error((this.isPermanent(r2.status) ? 'رفض الخادم السحب: ' + r2.status : this.transientMsg(r2.status)));
      const rows = await r2.json();
      if (!rows.length) { complete = true; break; }
      /* أعمدة الخادم (المحمية بالسياسات) تغلب ما في payload؛ والحقول المحلية في payload قديم تُهمل */
      const incoming = rows.map(r => Object.assign(Store.clean(r.payload || {}), { id: r.id, by: r.by, type: r.type, child: r.child || undefined }));
      const bad = incoming.filter(e => !Store.validEvent(e, incoming) || !Store.roleAllows(e.by, e));
      if (bad.length) { /* كل المرفوضات تُحفظ مع سببها بلا حد؛ القائمة السابقة تُستعاد عند فشل الحفظ */
        const prev = st.rejected; const next = prev.slice();
        for (const e of bad) if (!next.some(x => x.id === e.id)) next.push({ id: e.id, type: e.type, by: e.by, child: e.child || null, day: e.day, reason: Store.rejectReason(e, incoming), at: Date.now(), payload: e });
        st.rejected = next;
        try { Store.saveSettings(); } catch (err) { st.rejected = prev; this.lastError = 'تعذّر حفظ السجلات المرفوضة (امتلأت الذاكرة)؛ لن يتقدم المؤشر'; UI.renderStatus(); throw new Error(this.lastError); }
      }
      n += Store.importEvents(incoming.filter(e => !bad.includes(e)), { server: c.id });
      /* المؤشر لا يتقدم إلا بعد ثبوت السجلات على القرص */
      if (!(await Store.durable())) throw new Error('تعذّر حفظ السجلات المسحوبة على الجهاز؛ لن يتقدم المؤشر وستُعاد المحاولة');
      this.guard(c);
      const last = rows[rows.length - 1]; q = { t: last.inserted_at, id: last.id };
      if (this.cmpCursor(q, best) > 0) { best = q; st.cursor = best; Store.saveSettings(); }
      if (rows.length < PAGE) { complete = true; break; }
    }
    this.incomplete = !complete;
    if (!complete) setTimeout(() => this.run(), 2000);
    return n;
  },

  /* ===== المطابقة الكاملة: كل معرّفات الخادم مقابل سجلات الجهاز ===== */
  async fetchIds(c) {
    const ids = new Set(); let after = null;
    for (let i = 0; i < 2000; i++) {
      const r = await fetch(`${c.url}/rest/v1/events?select=id&order=id.asc&limit=${PAGE}${after !== null ? '&id=gt.' + encodeURIComponent(after) : ''}`, { headers: this.headers() });
      this.guard(c);
      if (!r.ok) throw new Error(this.isPermanent(r.status) ? 'رفض الخادم المطابقة: ' + r.status : this.transientMsg(r.status));
      const rows = await r.json();
      for (const x of rows) ids.add(x.id);
      if (rows.length < PAGE) return ids;
      after = rows[rows.length - 1].id;
    }
    throw new Error('تعذّرت المطابقة: الخادم أكبر من المتوقع');
  },
  async reconcile(c) {
    const ids = await this.fetchIds(c);
    const st = this.st(c.id); const changed = [];
    for (const e of Store.raw) {
      const on = ids.has(e.id), had = hasIn(e.sv, c.id);
      if (on && !had) { Store.markOn(e, c.id); changed.push(e); }
      else if (!on && had) { e.sv = e.sv.filter(x => x !== c.id); changed.push(e); }
    }
    /* ما على الخادم وليس هنا يُسحب من البداية (المكرر يُزال بالمعرّف) */
    const local = new Set(Store.raw.map(e => e.id)); const rej = new Set(st.rejected.map(x => x.id));
    for (const id of ids) if (!local.has(id) && !rej.has(id)) { st.cursor = null; break; }
    if (changed.length) Store.saveEvents(changed);
    st.needReconcile = false; st.reconciledAt = Date.now();
    this.lastIds = { sid: c.id, ids };
    Store.saveSettings();
  },
  async countMismatch(c) {
    try {
      const r = await fetch(`${c.url}/rest/v1/events?select=id&limit=1`, { headers: Object.assign(this.headers(), { Prefer: 'count=exact' }) });
      if (!r.ok) return false;
      const m = /\/(\d+)\s*$/.exec(r.headers.get('content-range') || ''); if (!m) return false;
      const server = Number(m[1]);
      const known = Store.raw.reduce((k, e) => k + (hasIn(e.sv, c.id) ? 1 : 0), 0);
      const st = this.st(c.id); st.serverCount = server;
      /* أقل مما ثبت رفعه = فُقد شيء من الخادم. (الزيادة طبيعية: أجهزة أخرى ترفع، والسحب يأتي بها) */
      return server < known;
    } catch (e) { return false; }
  },
  /* تقرير بعد مطابقة كاملة: لا يُعلن الاكتمال إلا إن لم يبقَ شيء، وإلا يُذكر ما بقي وسببه */
  writeReport(c) {
    const st = this.st(c.id); const k = this.counts(c.id);
    const local = new Set(Store.raw.map(e => e.id)); const rej = new Set(st.rejected.map(x => x.id));
    let serverOnly = 0; for (const id of this.lastIds.ids) if (!local.has(id) && !rej.has(id)) serverOnly++;
    const rep = { at: Date.now(), ownPending: k.ownPending, waitingTarget: k.waitingTarget, others: k.others, othersTotal: k.othersTotal, rejected: st.rejected.length, serverOnly, incomplete: this.incomplete };
    rep.complete = !rep.ownPending && !rep.othersTotal && !rep.rejected && !rep.serverOnly && !rep.incomplete;
    st.report = rep; this.lastIds = null;
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
create or replace function public.my_role() returns text language sql stable security definer set search_path = '' as
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
    select 1 from public.events t where t.id = events.payload->>'target' and t.type <> 'undo'
      and (t.by = public.my_role() or (public.my_role() = 'aya' and t.by = 'asst'))))
);
-- ثم: Authentication > Users > أنشئ ثلاثة مستخدمين بالبريد وكلمة السر،
-- ثم في Table Editor > profiles أضف صفاً لكل مستخدم: user_id (من صفحة المستخدم) و role: aya / asst / parent`;
