/* ===== النسخ الاحتياطي، استعادة الجهاز، استعادة الخادم، وبطاقة الخادم ===== */
/* ثلاثة إجراءات منفصلة:
   1. تبادل ملف / دمج: كل السجلات بالتراجعات ومعرّفاتها وأصحابها؛ يُضاف الجديد ولا يُكرَّر.
   2. استعادة جهاز فارغ: السجلات + إعدادات الخادم (بلا رموز الدخول ولا جلسات ولا مؤشرات)، ثم دخول جديد ومطابقة كاملة.
   3. استعادة خادم: ملفات SQL تُشغَّل في SQL Editor؛ كل سجل يُدرج باسم دوره فتنطبق عليه سياسات الخادم نفسها. */
const BACKUP_FORMAT = 'lawhat-muallima-backup';
const DAY_MS = 86400000;

const Backup = {
  /* ما يلزم لإعادة الجهاز فقط */
  SETTINGS_KEYS: ['sbUrl', 'sbKey', 'sounds', 'endAlarm'],
  build() {
    const events = Store.raw.map(e => Store.clean(e));
    const settings = {};
    for (const k of this.SETTINGS_KEYS) if (Store.settings[k] != null && Store.settings[k] !== '') settings[k] = Store.settings[k];
    /* التعارضات بنسختيها وقراراتها جزء من بيانات الجهاز (LM0132-R4-03)؛ بلا علامات خادم */
    const conflicts = Store.conflicts.map(x => Object.assign({ key: x.key, id: x.id, source: x.source, at: x.at, local: Store.clean(x.local), other: Store.clean(x.other) },
      x.resolved ? { resolved: Object.assign({ at: x.resolved.at, by: x.resolved.by, choice: x.resolved.choice }, x.resolved.auto ? { auto: true } : {}) } : {},
      x.localAtDetection ? { localAtDetection: Store.clean(x.localAtDetection) } : {}));
    return {
      format: BACKUP_FORMAT, formatVersion: 3, app: { version: BUILD.version, commit: BUILD.commit },
      exported: new Date().toISOString(), device: Store.settings.deviceId, role: App.role ? App.role.id : null,
      counts: { all: events.length, live: Store.events.length, undo: events.filter(e => e.type === 'undo').length, conflicts: conflicts.length, openConflicts: conflicts.filter(x => !x.resolved).length },
      settings, events, conflicts,
    };
  },
  download() {
    const b = this.build();
    const blob = new Blob([JSON.stringify(b)], { type: 'application/json' });
    const a = el('a', { href: URL.createObjectURL(blob), download: `lawhat-backup-${todayKey()}-${b.role || 'x'}.json` });
    document.body.append(a); a.click(); a.remove();
    Store.settings.lastBackup = { at: Date.now(), count: b.counts.all };
    Store.saveSettings();
    return b;
  },
  /* النسخة الكاملة (0.12+) أو ملف قديم (سجلات حيّة فقط بلا تراجعات) */
  parse(text) {
    const j = JSON.parse(text);
    if (j && j.format === BACKUP_FORMAT) {
      if (!Array.isArray(j.events)) throw new Error('ملف النسخة بلا سجلات');
      if (j.conflicts != null && !Array.isArray(j.conflicts)) throw new Error('ملف النسخة: التعارضات ليست قائمة');
      return { full: true, meta: j, events: j.events, settings: j.settings || {}, conflicts: j.conflicts || [] };
    }
    const list = Array.isArray(j) ? j : j && j.events;
    if (!Array.isArray(list)) throw new Error('ليس ملف سجلات من لوحة المعلمة');
    return { full: false, meta: Array.isArray(j) ? {} : j, events: list, settings: {}, conflicts: [] };
  },
  /* دمج بلا علامة «على الخادم»؛ مع خادم متصل تُطلب مطابقة كاملة تصحّح العلامات وتُظهر ما بقي */
  merge(parsed) {
    const n = Store.importEvents(parsed.events, { source: 'file' });
    this.lastConflicts = Store.lastConflicts || 0;
    this.lastCfImport = Store.importConflicts(parsed.conflicts || []);
    const st = Sync.st();
    if (st) { st.needReconcile = true; Store.saveSettings(); Sync.schedule(); }
    return n;
  },
  restoreDevice(parsed) {
    const n = this.merge(parsed);
    const s = parsed.settings || {};
    if (s.sounds != null) Store.settings.sounds = s.sounds;
    if (s.endAlarm != null) Store.settings.endAlarm = s.endAlarm;
    if (s.sbUrl && s.sbKey) Sync.switchTo(s.sbUrl, s.sbKey); else Store.saveSettings();
    return n;
  },
  /* أيام منذ آخر نسخة إن تجاوزت 7 وفي الجهاز سجلات أحدث منها؛ وإلا null */
  overdue() {
    if (!Store.raw.length) return null;
    const lb = Store.settings.lastBackup;
    if (!lb) return Infinity;
    const days = Math.floor((Date.now() - lb.at) / DAY_MS);
    if (days < 7) return null;
    /* وقت وصول السجل إلى الجهاز (la)، لا وقت إنشائه: سجل قديم وصل بعد آخر نسخة غير مشمول بها (LM0121-R2-12) */
    return Store.raw.some(e => (e.la || e.ts || 0) > lb.at) || Store.conflicts.some(x => Math.max(x.at || 0, x.resolved ? x.resolved.at || 0 : 0) > lb.at) ? days : null;
  },
};

/* ===== التخزين الدائم: يُطلب مرة بعد الدخول، ونتيجته معروضة. قد يُرفض، ولا يغني عن النسخ ===== */
const Persist = {
  state: 'unknown',
  async check() {
    if (!(navigator.storage && navigator.storage.persisted)) return (this.state = 'unsupported');
    try { this.state = (await navigator.storage.persisted()) ? 'granted' : 'denied'; } catch (e) { this.state = 'unsupported'; }
    return this.state;
  },
  async request() {
    if (!(navigator.storage && navigator.storage.persist)) return (this.state = 'unsupported');
    try { this.state = (await navigator.storage.persist()) ? 'granted' : 'denied'; } catch (e) { this.state = 'denied'; }
    Store.settings.persistAsked = Date.now(); Store.saveSettings();
    return this.state;
  },
  async auto() { if ((await this.check()) === 'denied' && !Store.settings.persistAsked) await this.request(); },
  standalone() { return !!((window.matchMedia && matchMedia('(display-mode: standalone)').matches) || navigator.standalone); },
  text() {
    const inst = this.standalone() ? 'البرنامج مثبّت على الشاشة الرئيسية' : 'البرنامج مفتوح في المتصفح (على iPhone ثبّتيه على الشاشة الرئيسية)';
    const st = { granted: 'التخزين الدائم ممنوح', denied: 'التخزين الدائم غير ممنوح — المتصفح قد يمحو البيانات عند ضيق المساحة', unsupported: 'التخزين الدائم غير مدعوم في هذا المتصفح', unknown: 'التخزين الدائم: لم يُفحص' }[this.state];
    return `${st} · ${inst}`;
  },
};

/* ===== استعادة الخادم: SQL يُشغَّل في SQL Editor ===== */
const ServerRestore = {
  PART: 2000,
  /* العادية أولاً ثم التراجعات (هدف التراجع يجب أن يسبقه على الخادم) */
  parts() {
    const evs = Store.raw.map(e => Store.clean(e));
    const byTs = (a, b) => a.ts - b.ts;
    const ordered = evs.filter(e => e.type !== 'undo').sort(byTs).concat(evs.filter(e => e.type === 'undo').sort(byTs));
    const out = [];
    for (let i = 0; i < ordered.length; i += this.PART) out.push(ordered.slice(i, i + this.PART));
    return out;
  },
  sql(chunk, k, total) {
    const json = JSON.stringify(chunk);
    /* فاصلا السلسلتين (JSON داخل الكتلة، والكتلة نفسها) يُختاران غائبين عن كل ما يحيطان به؛ نص أي ملاحظة لا يُنهي أياً منهما */
    const free = (base, text) => { let t = base; while (text.includes('$' + t + '$')) t += '_x'; return t; };
    const tag = free('lm_json', json);
    const body = this.body(json, tag, k);
    const dtag = free('lm_do', body);
    return `-- لوحة المعلمة · استعادة الخادم · الجزء ${k} من ${total} · ${chunk.length} سجل
-- الإصدار ${BUILD.version} (${BUILD.commit}) · أُعدّ ${new Date().toISOString()} من الجهاز ${Store.settings.deviceId}
-- يُشغَّل في SQL Editor لمشروع Supabase بعد إعداد الجداول وإنشاء المستخدمين الثلاثة وأدوارهم في profiles.
-- كل سجل يُدرج باسم دوره (set role authenticated) فتنطبق عليه سياسات الخادم نفسها؛ الموجود بالمحتوى نفسه = exists؛
-- الموجود بمحتوى مختلف = conflict (لا يُغيَّر)؛ المرفوض يُذكر بسببه.
-- آمن للتكرار. شغّلي الأجزاء بالترتيب (التراجعات في الأجزاء الأخيرة).
create temp table if not exists lm_restore_log (part int, id text, by text, type text, status text, reason text);
delete from lm_restore_log where part = ${k};
do $${dtag}$
${body}end $${dtag}$;
select status as "الحالة", count(*) as "العدد",
  string_agg(id || ' — ' || coalesce(reason, ''), E'\\n') filter (where status in ('rejected', 'conflict')) as "المرفوض أو المتعارض وسببه"
from lm_restore_log where part = ${k} group by status order by status;
`;
  },
  body(json, tag, k) {
    return `declare
  js jsonb := $${tag}$${json}$${tag}$::jsonb;
  x jsonb; uid text; n int;
begin
  for x in select value from jsonb_array_elements(js) loop
    select p.user_id::text into uid from public.profiles p where p.role = x->>'by' order by p.user_id limit 1;
    if uid is null then
      insert into lm_restore_log values (${k}, x->>'id', x->>'by', x->>'type', 'rejected', 'لا يوجد في profiles مستخدم بدور ' || coalesce(x->>'by', '؟'));
      continue;
    end if;
    begin
      perform set_config('request.jwt.claim.sub', uid, true);
      perform set_config('request.jwt.claims', json_build_object('sub', uid, 'role', 'authenticated')::text, true);
      perform set_config('role', 'authenticated', true);
      insert into public.events (id, ts, day, by, child, type, dev, payload)
        values (x->>'id', (x->>'ts')::bigint, x->>'day', x->>'by', x->>'child', x->>'type', x->>'dev', x)
        on conflict (id) do nothing;
      get diagnostics n = row_count;
      if n = 0 and not exists (select 1 from public.events t where t.id = x->>'id'
          and jsonb_strip_nulls(t.payload - 'sv' - 'rj' - 'cf' - 'la' - 'synced' - 'pushRejected') = jsonb_strip_nulls(x)) then
        n := -1; /* المعرّف موجود بمحتوى مختلف: تعارض معلن، لا «موجود» */
      end if;
      perform set_config('role', 'none', true);
      insert into lm_restore_log values (${k}, x->>'id', x->>'by', x->>'type',
        case when n = 1 then 'inserted' when n = 0 then 'exists' else 'conflict' end,
        case when n = -1 then 'المعرّف موجود على الخادم بمحتوى مختلف — لم يُغيَّر شيء' end);
    exception when others then
      perform set_config('role', 'none', true);
      insert into lm_restore_log values (${k}, x->>'id', x->>'by', x->>'type', 'rejected', sqlerrm);
    end;
  end loop;
`;
  },
  download(text, k, total) {
    const blob = new Blob([text], { type: 'application/sql' });
    const a = el('a', { href: URL.createObjectURL(blob), download: `lawhat-restore-${todayKey()}-${k}-of-${total}.sql` });
    document.body.append(a); a.click(); a.remove();
  },
};

/* ===== الواجهات ===== */
function roleName(r) { return ROLES[r] ? ROLES[r].name : (r || 'غير معروف'); }

function BackupReminder() {
  const d = Backup.overdue(); if (d == null) return null;
  return el('div', { class: 'alert' }, d === Infinity ? 'لم تُصدَّر نسخة احتياطية من هذا الجهاز بعد. ' : `آخر نسخة احتياطية من هذا الجهاز قبل ${d} يوماً. `,
    el('button', { class: 'ghost small', onclick: () => { Backup.download(); UI.toast('صُدّرت النسخة'); UI.rerender(); } }, 'تصدير نسخة كاملة الآن'));
}

function BackupCard() {
  const lb = Store.settings.lastBackup;
  const fileIn = el('input', { type: 'file', accept: '.json,application/json' });
  fileIn.addEventListener('change', async () => {
    const f = fileIn.files[0]; if (!f) return;
    let p; try { p = Backup.parse(await f.text()); } catch (e) { UI.modal('لم يُقرأ الملف', el('p', null, e.message)); return; } finally { fileIn.value = ''; }
    ImportDialog(p);
  });
  const persistLine = el('p', { class: 'small muted' }, Persist.text());
  Persist.check().then(() => { persistLine.textContent = Persist.text(); });
  return el('div', { class: 'card' }, el('h2', null, 'النسخ الاحتياطي وتبادل الملفات'),
    el('p', { class: 'small muted' }, 'النسخة الكاملة تحمل كل السجلات بالتراجعات ومعرّفاتها وأصحابها، والتعارضات بنسختيها وقراراتها، وإعدادات الخادم بلا كلمات سر ولا جلسات ولا رموز دخول. الاستيراد يدمج ولا يكرر.'),
    el('p', { class: 'small' }, lb ? `آخر تنزيل نسخة من هذا الجهاز: ${fmtDay(dayKey(new Date(lb.at)))} ${hhmm(new Date(lb.at))} (${lb.count} سجل). للتأكد أن الملف المحفوظ صالح: اختاريه في «استيراد ملف» فيُعرض ما يحمله قبل أي دمج.` : 'لم تُصدَّر نسخة من هذا الجهاز بعد'),
    el('p', { class: 'small' + (Store.idbOk ? ' muted' : '') }, Store.idbOk ? 'التخزين: قاعدة الجهاز (IndexedDB).' : '⚠ التخزين البديل (localStorage): تعذّر فتح قاعدة الجهاز، والسعة محدودة (~5 م.ب). صدّري نسخة كاملة، وأغلقي التبويبات الأخرى ثم أعيدي التحميل.'),
    persistLine,
    el('div', { class: 'btns' },
      el('button', { class: 'primary', onclick: () => { Backup.download(); UI.toast('صُدّرت النسخة'); UI.rerender(); } }, `تصدير نسخة كاملة (${Store.raw.length} سجل)`),
      Persist.state !== 'granted' ? el('button', { class: 'ghost', onclick: async () => { await Persist.request(); UI.toast(Persist.text()); UI.rerender(); } }, 'طلب التخزين الدائم') : null),
    label('استيراد ملف (دمج، أو استعادة جهاز فارغ)'), fileIn);
}

function ImportDialog(p) {
  const have = new Map(Store.raw.map(e => [e.id, e]));
  const evs = p.events.filter(e => e && typeof e === 'object');
  const undo = evs.filter(e => e.type === 'undo').length;
  const fresh = evs.filter(e => !have.has(e.id)).length;
  const inFile = new Set(evs.map(e => e.id));
  const missing = Store.raw.filter(e => !inFile.has(e.id)).length;
  const clash = evs.filter(e => have.has(e.id) && Store.fp(have.get(e.id)) !== Store.fp(e)).length;
  const m = p.meta || {};
  const body = el('div', null,
    el('p', null, p.full ? `نسخة من الإصدار ${m.app ? m.app.version : '؟'} (${m.app ? m.app.commit : '؟'})، صُدّرت ${m.exported ? m.exported.slice(0, 16).replace('T', ' ') : '؟'} من دور ${roleName(m.role)}.` : 'ملف بصيغة قديمة (قبل 0.12).'),
    el('p', null, `${evs.length} سجلاً (${undo} تراجعاً)، منها ${fresh} ليست على هذا الجهاز.`),
    Store.raw.length ? el('p', { class: 'small' }, missing ? `لا يحمل ${missing} من سجلات هذا الجهاز (${Store.raw.length}) — ليس نسخة كاملة منه.` : `يحمل كل سجلات هذا الجهاز (${Store.raw.length}).`) : null,
    clash ? el('div', { class: 'alert red' }, `${clash} سجلاً بمعرّف موجود هنا ومحتوى مختلف: لن يُغيَّر شيء منها، وستظهر في «التعارضات» للمراجعة.`) : null,
    p.full ? null : el('div', { class: 'alert' }, 'هذا الملف يحمل السجلات الحيّة فقط بلا تراجعات: ما تراجعتِ عنه في الجهاز المصدِّر لا يصل تراجعه إلى هنا.'),
    p.full && (p.conflicts || []).length ? el('p', { class: 'small' }, `وفيه ${p.conflicts.length} تعارضاً بنسختيه (${p.conflicts.filter(x => x && !x.resolved).length} مفتوحاً): تُضاف إلى «التعارضات» ما انطبقت على سجلات هنا.`) : null,
    p.full && !(m.formatVersion >= 3) ? el('p', { class: 'small muted' }, `نسخة بصيغة أقدم (${m.formatVersion || 1}) لا تحمل التعارضات ونسخها البديلة وقراراتها.`) : null,
    p.full && p.settings.sbUrl ? el('p', { class: 'small muted' }, `وفيه إعدادات الخادم: ${p.settings.sbUrl}`) : null);
  const canRestore = p.full && Store.raw.length === 0 && p.settings.sbUrl && p.settings.sbKey;
  let bg;
  const unlinked = () => { const u = Backup.lastCfImport && Backup.lastCfImport.unlinked; if (u && u.length) UI.modal('تعارضات لم تُربط', el('div', null, el('p', null, `${u.length} تعارضاً مفتوحاً في النسخة لا ينطبق على سجلات هذا الجهاز (محتوى السجل هنا ليس إحدى نسختيه، أو السجل غائب)، فلم يُضف:`), el('p', { class: 'small', dir: 'ltr' }, u.join(', ')), el('p', { class: 'small muted' }, 'الملف نفسه لم يتغير ويحملها كاملة.'))); };
  const merge = () => { bg.remove(); try { const n = Backup.merge(p); unlinked(); UI.savedToast(`أُضيف ${n} سجلاً وحُفظ${Backup.lastConflicts ? ` · ${Backup.lastConflicts} تعارض في «التعارضات»` : ''}${Backup.lastCfImport && Backup.lastCfImport.added ? ` · ${Backup.lastCfImport.added} تعارضاً من النسخة` : ''}`); UI.rerender(); } catch (e) { UI.modal('لم يُستورد الملف', el('p', null, e.message)); } };
  const restore = () => {
    bg.remove();
    try { const n = Backup.restoreDevice(p); App.logout(); unlinked(); UI.savedToast(`استُعيد ${n} سجلاً${Backup.lastCfImport && Backup.lastCfImport.added ? ` و${Backup.lastCfImport.added} تعارضاً بنسختيه` : ''}؛ ادخلي بحسابك على الخادم لتكتمل المطابقة`); }
    catch (e) { UI.modal('لم تُستعد النسخة', el('p', null, e.message)); }
  };
  bg = UI.modal('استيراد ملف', body, [
    canRestore ? el('button', { class: 'primary', onclick: restore }, 'استعادة الجهاز (السجلات + الخادم)') : null,
    el('button', { class: canRestore ? 'ghost' : 'primary', onclick: merge }, 'دمج السجلات فقط'),
    el('button', { class: 'ghost', onclick: () => bg.remove() }, 'إلغاء')]);
  if (canRestore) body.append(el('p', { class: 'small' }, 'استعادة الجهاز: تُضاف السجلات ويتصل الجهاز بالخادم المحفوظ في النسخة. بعد الدخول تُرفع سجلات دورك التي ليست عليه، ويظهر تقرير بما بقي.'));
}

function AdminRestoreCard() {
  const out = el('div');
  return el('div', { class: 'card' }, el('h2', null, 'استعادة الخادم (إجراء إداري)'),
    el('p', { class: 'small muted' }, 'حين يُفقد الخادم أو يُستعاد من نسخة أقدم ولا تتوفر أجهزة كل الأدوار. تُرفع سجلات هذا الجهاز كلها من SQL Editor في لوحة Supabase؛ كل سجل باسم دوره فتنطبق عليه سياسات الخادم نفسها، والموجود يُتجاهل، والمرفوض يُذكر بسببه.'),
    el('ol', { class: 'small' },
      el('li', null, 'مشروع جديد: نفّذي تعليمات الإعداد، وأنشئي المستخدمين الثلاثة وأدوارهم في profiles.'),
      el('li', null, 'شغّلي ملفات الاستعادة بالترتيب، وراجعي نتيجة كل جزء (المرفوض وسببه).'),
      el('li', null, 'على كل جهاز: الإعدادات ← الخادم ← «مطابقة كاملة»، حتى يظهر «اكتملت المطابقة».')),
    el('button', { onclick: () => {
      const parts = ServerRestore.parts(); out.innerHTML = '';
      if (!parts.length) { out.append(el('p', { class: 'small' }, 'لا سجلات على هذا الجهاز.')); return; }
      parts.forEach((ch, i) => out.append(el('button', { class: 'ghost', onclick: () => ServerRestore.download(ServerRestore.sql(ch, i + 1, parts.length), i + 1, parts.length) }, `الجزء ${i + 1} من ${parts.length} (${ch.length} سجل)`)));
    } }, `إعداد ملفات الاستعادة (${Store.raw.length} سجل)`), out);
}

function syncReportView(st) {
  const r = st && st.report; if (!r) return null;
  const when = `${fmtDay(dayKey(new Date(r.at)))} ${hhmm(new Date(r.at))}`;
  if (r.complete) return el('div', { class: 'alert', style: 'background:#e8f5e9;border-color:#a5d6a7' }, `✓ اكتملت المطابقة (${when}): كل سجلات هذا الجهاز على الخادم، وكل ما على الخادم على هذا الجهاز.`);
  const items = [];
  const wt = r.waitingTarget || 0;
  if (r.ownPending - wt > 0) items.push(`${r.ownPending - wt} من سجلات دورك لم تُرفع بعد — تُرفع في الجولة التالية`);
  if (wt) items.push(`${wt} من تراجعاتك بانتظار وصول السجل الأصلي إلى الخادم — يرفعه جهاز صاحبه، ثم يُرفع التراجع تلقائياً`);
  for (const [by, n] of Object.entries(r.others || {})) items.push(`${n} من سجلات ${roleName(by)} ليست على الخادم — يرفعها جهاز ${roleName(by)} عند دخوله، أو «استعادة الخادم» من جهاز ولي الأمر`);
  if (r.rejected) items.push(`${r.rejected} سجلاً رفضها الخادم أو رفضها الجهاز — انظري المرفوضات`);
  if (r.conflicts) items.push(`${r.conflicts} تعارضاً: معرّف واحد بمحتوى مختلف بين الجهاز والخادم — انظري «التعارضات»`);
  if (r.kept) items.push(`${r.kept} سجلاً أُبقيت فيه نسخة الجهاز عمداً فيختلف عن الخادم (استثناء مقصود، لا تطابق) — انظري «التعارضات»`);
  if (r.serverOnly) items.push(`${r.serverOnly} سجلاً على الخادم لم تصل هذا الجهاز بعد — تُسحب في الجولة التالية`);
  if (r.incomplete) items.push('السحب لم يكتمل (دفعة كبيرة) — يُستكمل تلقائياً');
  return el('div', { class: 'alert' }, el('div', null, el('b', null, `المطابقة لم تكتمل (${when}):`)), el('ul', { class: 'small', style: 'margin:4px 0' }, items.map(t => el('li', null, t))));
}

const hoursAr = h => h === 1 ? 'ساعة' : h === 2 ? 'ساعتين' : h <= 10 ? `${h} ساعات` : `${h} ساعة`;
/* تاريخ آخر مطابقة كاملة وموعد التالية (تلقائية كل 6 ساعات) */
function reconcileLine(st) {
  if (!st.reconciledAt) return 'لم تُجرَ مطابقة كاملة مع هذا الخادم بعد؛ تُجرى عند التزامن التالي.';
  const d = new Date(st.reconciledAt);
  const left = st.reconciledAt + Sync.RECONCILE_EVERY_MS - Date.now();
  const next = st.needReconcile || left <= 0 ? 'التالية تلقائياً عند التزامن القادم' : `التالية تلقائياً خلال ${hoursAr(Math.max(1, Math.ceil(left / 3600e3)))}`;
  return `آخر مطابقة كاملة: ${fmtDay(dayKey(d))} ${hhmm(d)} · ${next}`;
}

function ServerCard() {
  const s = Store.settings; const c = Sync.cfg();
  const url = el('input', { value: s.sbUrl || '', placeholder: 'https://xxxx.supabase.co', dir: 'ltr' });
  const key = el('input', { value: s.sbKey || '', placeholder: 'anon public key', dir: 'ltr' });
  const save = () => {
    const u = url.value.trim(), k = key.value.trim();
    if (!u && !k) {
      UI.confirm('فصل هذا الجهاز عن الخادم؟ تبقى السجلات على الجهاز.', () => { s.sbUrl = ''; s.sbKey = ''; s.sbSession = null; s.sbRole = null; Store.saveSettings(); App.logout(); });
      return;
    }
    if (!/^https?:\/\/\S+$/.test(u) || !k) { UI.toast('أدخلي رابط المشروع والمفتاح العام'); return; }
    if (s.sbUrl && serverId(u) === serverId(s.sbUrl) && Sync.isKnown(u)) { s.sbKey = k; Store.saveSettings(); UI.toast('حُفظ'); UI.rerender(); return; }
    ServerSwitchDialog(u, k);
  };
  const card = el('div', { class: 'card' }, el('h2', null, 'الخادم (الحسابات الثلاثة عبر الإنترنت)'),
    el('p', { class: 'small muted' }, 'اختياري. بدونه يعمل البرنامج محلياً مع تبادل بالملفات. مع الخادم تتزامن الأجهزة وتعمل بلا إنترنت ثم ترفع. تغيير الرابط لا ينقل الدخول ولا موضع المزامنة، ولا يرفع شيئاً إلى خادم جديد قبل اختيار صريح.'),
    label('رابط المشروع'), url, label('المفتاح العام'), key,
    s.localMode && s.sbUrl ? el('div', { class: 'alert' }, 'الوضع المحلي مفعّل والمزامنة متوقفة. ', el('button', { class: 'ghost small', onclick: () => { s.localMode = false; Store.saveSettings(); App.logout(); } }, 'العودة للاتصال بالخادم')) : null,
    el('div', { class: 'btns' }, el('button', { class: 'primary', onclick: save }, 'حفظ'),
      el('button', { class: 'ghost', onclick: () => UI.modal('إعداد الخادم', el('div', null, el('p', { class: 'small' }, 'أنشئ مشروعاً في supabase.com، ثم نفّذ هذا في SQL Editor، ثم أنشئ المستخدمين الثلاثة وضع لكل منهم الدور في جدول profiles.'), el('pre', null, SETUP_SQL))) }, 'تعليمات الإعداد')));
  if (c) {
    const k = Sync.counts(); const st = Sync.st();
    const others = Object.entries(k.others).map(([by, n]) => `${roleName(by)} ${n}`).join('، ');
    card.append(el('p', { class: 'small muted' }, Sync.lastOk ? `آخر تزامن ${hhmm(new Date(Sync.lastOk))}` : 'لم يتزامن بعد في هذه الجلسة', Sync.lastError ? ` · ${Sync.lastError}` : ''),
      el('p', { class: 'small' }, Sync.role() ? `سجلات دورك بانتظار الرفع: ${k.ownPending}` : 'لم يُدخل إلى هذا الخادم بعد', k.othersTotal ? ` · سجلات أدوار أخرى ليست على الخادم: ${others}` : ''),
      el('p', { class: 'small muted' }, reconcileLine(st)),
      syncReportView(st),
      el('div', { class: 'btns' },
        el('button', { class: 'ghost small', onclick: async () => { await Sync.run(); UI.rerender(); } }, 'تزامن الآن'),
        el('button', { class: 'ghost small', onclick: async () => { st.needReconcile = true; Store.saveSettings(); UI.toast('تجري المطابقة…'); await Sync.run(); UI.rerender(); } }, 'مطابقة كاملة')));
  }
  return card;
}

/* اختيار صريح عند خادم لم يتصل به الجهاز من قبل: لا رفع تلقائياً لبيانات الأطفال لمجرد تغيير الرابط */
function ServerSwitchDialog(u, k) {
  if (Sync.isKnown(u)) {
    UI.confirm(`الانتقال إلى ${u}؟ اتصل به هذا الجهاز من قبل: تُستأنف مزامنته من موضعها، وتجري مطابقة كاملة، ويلزم الدخول إليه من جديد.`, () => { Sync.switchTo(u, k); App.logout(); });
    return;
  }
  if (!Store.raw.length) { Sync.switchTo(u, k); App.logout(); UI.toast('اتصل الجهاز بالخادم؛ ادخلي بحسابك'); return; }
  const byRole = {}; for (const e of Store.raw) byRole[e.by || '?'] = (byRole[e.by || '?'] || 0) + 1;
  const dist = Object.entries(byRole).map(([r, n]) => `${roleName(r)} ${n}`).join('، ');
  let bg;
  const family = () => UI.confirm('تأكيد: هذا خادم العائلة. بعد الدخول يُسحب ما فيه إلى هذا الجهاز، وتُرفع إليه سجلات دورك التي ليست عليه.', () => { bg.remove(); Sync.switchTo(u, k); App.logout(); UI.toast('ادخلي بحسابك على الخادم الجديد'); });
  const separate = () => {
    bg.remove();
    let b2;
    const exp = el('button', { onclick: () => { Backup.download(); wipe.disabled = false; UI.toast('صُدّرت النسخة'); } }, 'تصدير نسخة كاملة أولاً');
    const wipe = el('button', { class: 'danger', disabled: true, onclick: () => UI.confirm(`حذف ${Store.raw.length} سجلاً من هذا الجهاز ثم الاتصال بالخادم الجديد؟ لا يمس أي خادم.`, async () => {
      b2.remove(); const ok = await Store.reset(); Store.settings.active = null; Store.saveSettings();
      if (!ok) { UI.toast('تعذّر الحذف الكامل؛ لم يتصل الجهاز'); return; }
      Sync.switchTo(u, k); App.logout(); UI.toast('الجهاز نظيف ومتصل بالخادم الجديد؛ ادخلي بحسابك');
    }) }, 'حذف سجلات الجهاز ثم الاتصال');
    b2 = UI.modal('خادم منفصل', el('div', null,
      el('p', null, 'هذا الجهاز يحمل سجلات العائلة، فلا يتصل بخادم منفصل وهي عليه (كانت ستُخلط بسجلاته).'),
      el('p', { class: 'small' }, 'للتجربة: استعملي متصفحاً آخر أو جهازاً آخر. أو ابدئي هذا الجهاز نظيفاً: صدّري نسخة كاملة ثم احذفي سجلاته.')),
      [exp, wipe, el('button', { class: 'ghost', onclick: () => b2.remove() }, 'إلغاء')]);
  };
  bg = UI.modal('خادم جديد لهذا الجهاز', el('div', null,
    el('p', null, `${u} لم يتصل به هذا الجهاز من قبل. على الجهاز ${Store.raw.length} سجلاً (${dist}).`),
    el('p', null, el('b', null, 'خادم العائلة (انتقال أو استعادة): '), 'يُسحب ما فيه، وتُرفع إليه سجلات دورك التي لا يملكها. سجلات الأدوار الأخرى يرفعها أصحابها أو «استعادة الخادم».'),
    el('p', null, el('b', null, 'خادم منفصل (تجربة أو غيره): '), 'لا يُرفع إليه شيء من سجلات هذا الجهاز.')),
    [el('button', { class: 'primary', onclick: family }, 'خادم العائلة'), el('button', { onclick: separate }, 'خادم منفصل'), el('button', { class: 'ghost', onclick: () => bg.remove() }, 'إلغاء')]);
}

/* التعارضات: النسختان محفوظتان؛ القرار صريح وموثَّق (آية أو ولي الأمر)، ولا تعديل صامت */
function evSummary(e) { return `${e.type} · ${roleName(e.by)}${e.child && CHILDREN[e.child] ? ' · ' + CHILDREN[e.child].name : ''} · ${e.day || ''}${e.text ? ' · ' + String(e.text).slice(0, 40) : ''}${e.page ? ' · ص' + e.page : ''}${e.result ? ' · ' + e.result : ''}${e.kind ? ' · ' + e.kind : ''}`; }
function ConflictsCard() {
  const list = Store.openConflicts(); const kept = Store.keptDiffs();
  if (!list.length && !kept.length) return null;
  const can = App.role && (App.role.id === 'aya' || App.role.id === 'parent');
  const srcName = x => x.source === 'file' ? 'الملف' : 'الخادم';
  /* الحسم لا يُعلن قبل ثبوت الاستبدال والقرار معاً؛ وإن فشل الحفظ يبقى التعارض كما كان */
  const resolve = (x, choice) => UI.confirm(choice === 'other' ? `اعتماد نسخة ${srcName(x)} بدل نسخة هذا الجهاز لهذا المعرّف؟ يُوثَّق القرار.` : `إبقاء نسخة هذا الجهاز؟ ${x.source === 'file' ? 'لا يتغير شيء ويُوثَّق القرار.' : 'تبقى مختلفة عن الخادم، ويظهر ذلك استثناءً في تقرير المطابقة حتى تعتمدي نسخة الخادم.'}`, async () => {
    UI.toast('جارٍ حفظ القرار…');
    const op = UI.opGuard();
    const ok = await Store.resolveConflict(x, choice, App.role.id);
    if (ok === null || !op.alive()) { UI.rerender(); return; } /* حُذفت بيانات الجهاز أو تغيّر الحساب أثناء الحسم: لا ملاحظة ولا رسالة نجاح */
    if (!ok) { UI.toast('لم يُحسم التعارض: تعذّر الحفظ (' + (Store.storageError || 'الكتابة لم تثبت') + '). بقي كما كان؛ أعيدي المحاولة.'); UI.rerender(); return; }
    Store.add({ type: 'note', child: x.local.child || null, text: `حُسم تعارض المعرّف ${x.id} (${x.source}): ${choice === 'other' ? 'اعتُمدت النسخة الأخرى' : 'أُبقيت نسخة الجهاز'}` });
    UI.savedToast('حُسم التعارض'); UI.rerender();
  });
  return el('div', { class: 'card' }, el('h2', null, `التعارضات (${list.length})${kept.length ? ` · اختلافات مُبقاة (${kept.length})` : ''}`),
    list.length ? el('p', { class: 'small muted' }, 'معرّف واحد بمحتويين مختلفين. لم يُغيَّر شيء تلقائياً، ولا تُعلن المطابقة مكتملة حتى يُحسم كل تعارض.') : null,
    list.map(x => el('div', { class: 'alert red' }, el('div', { class: 'small' }, el('b', null, x.id), ` · المصدر: ${x.source === 'file' ? 'ملف' : 'الخادم'}`),
      el('div', { class: 'small' }, 'هذا الجهاز الآن: ', evSummary(Store.raw.find(e => e.id === x.id) || x.local)),
      x.localAtDetection ? el('div', { class: 'small muted' }, '(عند اكتشاف التعارض كان: ', evSummary(x.localAtDetection), ')') : null,
      el('div', { class: 'small' }, srcName(x) + ': ', evSummary(x.other)),
      can ? el('div', { class: 'btns' }, el('button', { class: 'ghost', onclick: () => resolve(x, 'local') }, 'إبقاء نسخة الجهاز'), el('button', { class: 'ghost', onclick: () => resolve(x, 'other') }, x.source === 'file' ? 'اعتماد نسخة الملف' : 'اعتماد نسخة الخادم')) : el('div', { class: 'small muted' }, 'تحسمه آية أو ولي الأمر.'))),
    kept.length ? el('p', { class: 'small muted' }, 'اختلافات أُبقيت فيها نسخة الجهاز عمداً: هذا الجهاز يختلف فيها عن الخادم، فلا تُعلن المطابقة كاملة ما بقيت. تُحسم باعتماد نسخة الخادم متى شئتِ.') : null,
    kept.map(x => el('div', { class: 'alert' }, el('div', { class: 'small' }, el('b', null, x.id), ` · أُبقيت نسخة الجهاز ${fmtDay(dayKey(new Date(x.resolved.at)))}`),
      el('div', { class: 'small' }, 'هذا الجهاز: ', evSummary(Store.raw.find(e => e.id === x.id) || x.local)), el('div', { class: 'small' }, 'الخادم: ', evSummary(x.other)),
      can ? el('div', { class: 'btns' }, el('button', { class: 'ghost', onclick: () => resolve(x, 'other') }, 'اعتماد نسخة الخادم')) : null)));
}

function RejectedCard() {
  const st = Sync.st(); const sid = Sync.sid();
  const rej = st ? st.rejected : [];
  if (!rej.length) return null;
  const rp = App.sub.rejPage || 0; const RP = 20; const pages = Math.ceil(rej.length / RP);
  const retry = r => {
    if (r.direction === 'push') {
      const e = Store.raw.find(x => x.id === r.id);
      if (e) { e.rj = (e.rj || []).filter(x => x !== sid); Store.saveEvents([e]); }
      st.rejected = rej.filter(x => x.id !== r.id); Store.saveSettings(); Sync.schedule(); UI.toast('سيُعاد رفعه'); UI.rerender(); return;
    }
    try { Store.importEvents([r.payload], { server: sid }); st.rejected = rej.filter(x => x.id !== r.id); Store.saveSettings(); UI.savedToast('أُدرج السجل'); }
    catch (e) { UI.toast('ما زال مرفوضاً: ' + e.message); }
    UI.rerender();
  };
  const ignore = r => UI.confirm('تجاهل هذا السجل نهائياً على هذا الجهاز؟ (يبقى على الخادم)', () => {
    st.rejected = rej.filter(x => x.id !== r.id); Store.saveSettings();
    Store.add({ type: 'note', child: r.child || null, text: `تجاهل سجل مرفوض من المزامنة: ${r.id} (${r.reason})` }); UI.rerender();
  });
  return el('div', { class: 'card' }, el('h2', null, `المرفوضات من المزامنة (${rej.length})`),
    el('p', { class: 'small muted' }, 'سجلات رفضها الخادم أو رفضها هذا الجهاز عند السحب. تبقى هنا كلها حتى تُعالَج: إعادة محاولة (إن أصلحت الشرط) أو تجاهل موثَّق.'),
    pages > 1 ? el('div', { class: 'row between' },
      el('button', { class: 'ghost small', disabled: rp <= 0, onclick: () => { App.sub.rejPage = rp - 1; UI.rerender(); } }, 'السابق'),
      el('span', { class: 'small muted' }, `صفحة ${rp + 1} من ${pages}`),
      el('button', { class: 'ghost small', disabled: rp >= pages - 1, onclick: () => { App.sub.rejPage = rp + 1; UI.rerender(); } }, 'التالي')) : null,
    rej.slice().reverse().slice(rp * RP, rp * RP + RP).map(r => el('div', { class: 'alert red' },
      el('div', null, el('b', null, `${r.type} · ${roleName(r.by)} · ${r.child && CHILDREN[r.child] ? CHILDREN[r.child].name : ''} · ${fmtDay(r.day)}`)),
      el('div', { class: 'small' }, r.reason),
      el('div', { class: 'btns' }, el('button', { class: 'ghost', onclick: () => retry(r) }, 'إعادة المحاولة'), el('button', { class: 'ghost', onclick: () => ignore(r) }, 'تجاهل موثَّق')))));
}
