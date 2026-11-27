/* ===== الهيكل العام: التطبيق، الدخول، التنقل، النوافذ ===== */
const App = {
  role: null, view: 'now', sub: {}, timeOffset: 0,
  realNow() { return new Date(Date.now() + (Store.settings.timeOffset || 0)); },
  now() { return wallClock(this.realNow()); },
  setRole(r) { this.role = ROLES[r]; sessionStorage.setItem(LS_SESSION, r); this.view = r === 'parent' ? 'dash' : 'now'; Alarms.unlock(); UI.rerender(); Persist.auto(); if (AppShell.inApp()) AppUpdate.check().then(v => { if (v && AppUpdate.available()) UI.rerender(); }); },
  logout() { this.role = null; sessionStorage.removeItem(LS_SESSION); if (Sync.cfg()) Sync.logout(); UI.rerender(); },
  can(perm) { return !!(this.role && this.role[perm]); },
};

/* ===== داخل تطبيق أندرويد (غلاف WebView): جسر LawhatAndroid للحفظ والنسخ وفتح الروابط، وزر الرجوع ===== */
const AppShell = {
  inApp() { return !!(window.LawhatAndroid && typeof window.LawhatAndroid.saveFile === 'function'); },
  version() { try { return this.inApp() && window.LawhatAndroid.appVersion ? String(window.LawhatAndroid.appVersion()) : null; } catch (e) { return null; } },
  preview() { try { return this.inApp() && !!(window.LawhatAndroid.isPreview && window.LawhatAndroid.isPreview()); } catch (e) { return false; } },
  pending: {}, seq: 0,
  /* حفظ ملف: في المتصفح تنزيل مباشر (لا يُعرف إن أُلغي)؛ في التطبيق نافذة «حفظ باسم» من النظام، وonSaved لا يُستدعى إلا بعد كتابة الملف فعلاً */
  saveFile(name, mime, text, onSaved) {
    if (this.inApp()) {
      const id = 'f' + (++this.seq); this.pending[id] = { name, onSaved };
      try { window.LawhatAndroid.saveFile(id, name, mime, text); } catch (e) { delete this.pending[id]; UI.toast('تعذّر فتح نافذة الحفظ: ' + e.message); }
      return;
    }
    const a = el('a', { href: URL.createObjectURL(new Blob([text], { type: mime })), download: name });
    document.body.append(a); a.click(); a.remove();
    if (onSaved) onSaved();
  },
  openExternal(url) { if (this.inApp() && window.LawhatAndroid.openExternal) window.LawhatAndroid.openExternal(url); else window.open(url, '_blank', 'noopener'); },
};
window.LM_fileSaved = (id, ok, err) => {
  const p = AppShell.pending[id]; delete AppShell.pending[id]; if (!p) return;
  if (ok) { UI.toast('حُفظ الملف: ' + p.name); if (p.onSaved) guardHandler(p.onSaved)(); }
  else UI.toast(err ? 'لم يُحفظ الملف: ' + err : 'أُلغي الحفظ — لم يُكتب الملف');
};
/* زر الرجوع في التطبيق: يغلق النافذة المفتوحة، ثم يعود إلى الشاشة الرئيسية للدور؛ وإلا يُترك للتطبيق (رجوع مرتين للخروج) */
window.LM_back = () => {
  const ms = document.querySelectorAll('.modal-bg'); if (ms.length) { ms[ms.length - 1].remove(); return true; }
  if (!App.role) return false;
  const home = App.role.id === 'parent' ? 'dash' : 'now';
  if (App.view !== home) { App.view = home; App.sub = {}; UI.rerender(); return true; }
  return false;
};

/* كل فعل من أفعال الواجهة: خطأ متزامن أو وعد مرفوض يظهر رسالةً ويُسجَّل في UI.errors، ولا يبقى خطأً غير معالج */
function guardHandler(fn) {
  return function (ev) {
    const fail = err => { const msg = (err && err.message) || String(err); try { UI.errors.push(msg); console.error(err); if (!/^سجل غير صالح|^لا يُسمح لحساب/.test(msg)) UI.toast('تعذّر تنفيذ الإجراء: ' + msg); } catch (x) {} };
    try { const r = fn.call(this, ev); if (r && typeof r.then === 'function') r.catch(fail); return r; } catch (err) { fail(err); }
  };
}
const el = (tag, attrs, ...children) => {
  const n = document.createElement(tag);
  if (attrs) for (const [k, v] of Object.entries(attrs)) {
    if (k === 'class') n.className = v; else if (k === 'html') n.innerHTML = v; else if (k.startsWith('on')) n.addEventListener(k.slice(2), guardHandler(v)); else if (v !== null && v !== undefined) n.setAttribute(k, v);
  }
  for (const c of children.flat()) if (c !== null && c !== undefined && c !== false) n.append(c.nodeType ? c : document.createTextNode(neutral(String(c))));
  return n;
};
/* خطاب ولي الأمر (0.16): نصوص البرنامج تخاطب المعلمة بالمؤنث؛ في حساب ولي الأمر تُحوَّل أفعال الأمر إلى صيغة المذكر */
const NEUTRAL = { 'أعيدي': 'أعد', 'اختاري': 'اختر', 'صدّري': 'صدّر', 'اكتبي': 'اكتب', 'ادخلي': 'ادخل', 'أدخلي': 'أدخل', 'ابدئي': 'ابدأ', 'اضغطي': 'اضغط', 'انظري': 'انظر', 'افتحي': 'افتح', 'سجّلي': 'سجّل', 'شغّلي': 'شغّل', 'أبلغي': 'أبلغ', 'غيّري': 'غيّر', 'تسجّلي': 'تسجّل', 'أغلقي': 'أغلق', 'نفّذي': 'نفّذ', 'أنشئي': 'أنشئ', 'راجعي': 'راجع', 'استعملي': 'استعمل', 'احذفي': 'احذف', 'تعتمدي': 'تعتمد', 'تغلقي': 'تغلق', 'استوردي': 'استورد', 'انسخي': 'انسخ', 'أرسلي': 'أرسل', 'اعتمدي': 'اعتمد', 'علّمي': 'علّم', 'احفظي': 'احفظ', 'حسابكِ': 'حسابك', 'بنفسكِ': 'بنفسك' };
const NEUTRAL_RE = new RegExp('(^|[^\\u0621-\\u064A\\u0651])([وف]?)(' + Object.keys(NEUTRAL).join('|') + ')(?![\\u0621-\\u0652])', 'g');
function neutral(t) { return (typeof App !== 'undefined' && App.role && App.role.id === 'parent' && t.length > 3) ? t.replace(NEUTRAL_RE, (m, a, w, v) => a + w + NEUTRAL[v]) : t; }
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

const UI = {
  root: null, errors: [],
  init() {
    this.root = document.getElementById('app');
    const saved = sessionStorage.getItem(LS_SESSION);
    if (saved && ROLES[saved]) { App.role = ROLES[saved]; App.view = saved === 'parent' ? 'dash' : 'now'; }
    if (Sync.role()) { App.role = ROLES[Sync.role()]; if (!saved) App.view = App.role.id === 'parent' ? 'dash' : 'now'; }
    this.rerender();
    setInterval(() => { const ae = document.activeElement; const typing = ae && (ae.tagName === 'INPUT' || ae.tagName === 'TEXTAREA' || ae.tagName === 'SELECT'); if (App.view === 'now' && App.role && !document.querySelector('.modal-bg') && !typing) this.rerender(true); }, 30000);
    setInterval(() => Alarms.tick(), 15000);
    /* مغادرة وفي الذاكرة ما لم يثبت (معلّق أو دفعة جارية): تحذير، ونسخة طوارئ متزامنة تُدمج عند الفتح التالي */
    window.addEventListener('beforeunload', e => { if (Store.idbOk && !Store.saved()) { Store.emergencySave(); e.preventDefault(); e.returnValue = ''; } });
    window.addEventListener('pagehide', () => { Store.emergencySave(); });
    document.addEventListener('click', () => Alarms.unlock(), { once: true });
  },
  /* مسودات الحقول (LM0121-R2-13): ما كُتب ولم يُحفظ يبقى عبر أي إعادة رسم (مزامنة، تحديث دوري، حفظ في مكان آخر)
     ما دام الحقل نفسه في الشاشة نفسها وقيمته المخزنة لم تتغير. الحفظ أو الإلغاء الصريح وحده يحسم المسودة */
  draftKey(n, i) { return [App.view, App.role && App.role.id, n.tagName, n.type || '', n.getAttribute('placeholder') || '', n.getAttribute('name') || '', i].join('|'); },
  collectDrafts() {
    const out = new Map(); const seen = {};
    for (const n of this.root.querySelectorAll('input:not([type=file]), textarea')) {
      const sig = this.draftKey(n, ''); const i = seen[sig] = (seen[sig] || 0) + 1;
      const isBox = n.type === 'checkbox' || n.type === 'radio';
      const dirty = isBox ? n.checked !== n.defaultChecked : n.value !== n.defaultValue;
      if (dirty || n === document.activeElement) out.set(this.draftKey(n, i), { value: n.value, checked: n.checked, def: isBox ? n.defaultChecked : n.defaultValue, dirty, focus: n === document.activeElement, sel: (() => { try { return [n.selectionStart, n.selectionEnd]; } catch (e) { return null; } })() });
    }
    return out;
  },
  restoreDrafts(drafts) {
    if (!drafts.size) return; const seen = {};
    for (const n of this.root.querySelectorAll('input:not([type=file]), textarea')) {
      const sig = this.draftKey(n, ''); const i = seen[sig] = (seen[sig] || 0) + 1;
      const d = drafts.get(this.draftKey(n, i)); if (!d) continue;
      const isBox = n.type === 'checkbox' || n.type === 'radio';
      if (d.dirty && (isBox ? n.defaultChecked : n.defaultValue) === d.def) { if (isBox) n.checked = d.checked; else n.value = d.value; }
      if (d.focus) { n.focus({ preventScroll: true }); if (d.sel) try { n.setSelectionRange(d.sel[0], d.sel[1]); } catch (e) {} }
    }
  },
  rerender(soft) {
    if (!App.role) { this.root.innerHTML = ''; this.root.append(Views.login()); return; }
    const scroll = window.scrollY;
    const drafts = this.collectDrafts();
    this.root.innerHTML = '';
    let main; try { main = el('main', null, (Views[App.view] || Views.now)()); }
    catch (err) { console.error(err); main = el('main', null, el('div', { class: 'card' }, el('h2', null, 'تعذّر عرض هذه الشاشة'), el('p', { class: 'small' }, 'سجل تالف وصل بالمزامنة أو خطأ في البرنامج: ', String(err && err.message || err)), el('div', { class: 'btns' }, el('button', { onclick: () => { App.view = 'settings'; UI.rerender(); } }, 'الإعدادات (تصدير البيانات)'), el('button', { class: 'ghost', onclick: () => { App.view = 'now'; UI.rerender(); } }, 'الآن')))); }
    this.root.append(this.header(), main, this.nav());
    document.body.classList.toggle('insession', inSession());
    Wake.sync();
    this.restoreDrafts(drafts);
    if (soft) window.scrollTo(0, scroll);
  },
  header() {
    const d = App.now();
    const times = `${fmtTime12(hhmm(d))} بكين${sameTz() ? '' : ' · ' + App.realNow().toLocaleTimeString('ar-EG-u-nu-latn', { hour: 'numeric', minute: '2-digit' }) + ' ' + tzShort()}`;
    const sim = Store.settings.timeOffset ? el('div', { class: 'alert red', style: 'width:100%;margin:6px 0 0;padding:4px 8px' }, '⚠ الوقت محاكى! ', el('button', { class: 'ghost small', onclick: () => { Store.settings.timeOffset = 0; Store.saveSettings(); UI.rerender(); } }, 'العودة للوقت الحقيقي')) : null;
    /* أثناء الجلسة (0.16): رأس من سطر واحد، والشريط السفلي مطوي يُفتح بزر ☰؛ الشاشة للتسجيل */
    if (inSession()) return el('header', { class: 'top slim' },
      el('div', { class: 'sub' }, times),
      el('button', { class: 'ghost small navtoggle', title: 'القائمة', onclick: () => { App.navOpen = !App.navOpen; UI.rerender(true); } }, App.navOpen ? '✕' : '☰'),
      el('div', { class: 'status', id: 'status' }, this.statusInner()), sim);
    return el('header', { class: 'top' },
      el('div', null, el('div', { class: 'title' }, `لوحة المعلمة · ${App.role.name}`), el('div', { class: 'sub' }, `${DAY_NAMES[d.getDay()]} ${d.getDate()}/${d.getMonth() + 1} · ${times}`)),
      el('div', { class: 'status', id: 'status' }, this.statusInner()), sim);
  },
  statusInner() {
    const m = !inSession() && Alarms.muted() && Alarms.on() ? ' · 🔇 الأصوات مكتومة أثناء الجلسة' : '';
    if (Store.storageError) return [el('span', { class: 'dot bad' }), Store.storageError + m];
    if (Store.idbOk && Store.pendingCount()) return [el('span', { class: 'dot off' }), `جارٍ الحفظ… (${Store.pendingCount()})` + m];
    if (!Store.idbOk) { const used = (localStorage.getItem('lm_events_v1') || '').length / 1048576; if (used > 2.5) return [el('span', { class: 'dot bad' }), `تخزين محدود (${used.toFixed(1)} من 5 م.ب) — افتحي البرنامج من الرابط لا من الملف` + m]; }
    const cfN = Store.openConflicts().length; if (cfN) return [el('span', { class: 'dot bad' }), `${cfN} تعارض بين نسختين لسجل واحد — الإعدادات ← التعارضات` + m];
    const st = Sync.st(); const rejN = st ? st.rejected.length : 0; if (rejN) return [el('span', { class: 'dot bad' }), `${rejN} سجل مرفوض من المزامنة — الإعدادات` + m];
    if (Store.settings.localMode && Store.settings.sbUrl) return [el('span', { class: 'dot off' }), 'وضع محلي — المزامنة متوقفة (الإعدادات ← الخادم ← العودة للاتصال)' + m];
    if (!Sync.cfg()) return [el('span', { class: 'dot' }), 'حُفظ على الجهاز' + m];
    if (!navigator.onLine) return [el('span', { class: 'dot off' }), 'بلا إنترنت، سيُرفع لاحقاً'];
    if (Sync.lastError) return [el('span', { class: 'dot bad' }), Sync.lastError];
    const k = Sync.counts();
    if (k.ownPending) return [el('span', { class: 'dot ok' }), `حُفظ على الجهاز · ${k.ownPending} بانتظار الرفع` + m];
    if (k.othersTotal) return [el('span', { class: 'dot off' }), `تمت مزامنة سجلاتك · ${k.othersTotal} لأدوار أخرى ليست على الخادم (الإعدادات ← الخادم)` + m];
    if (k.kept) return [el('span', { class: 'dot off' }), `تمت المزامنة · ${k.kept} سجل يختلف عن الخادم بقرار «إبقاء نسخة الجهاز» (الإعدادات ← التعارضات)` + m];
    return [el('span', { class: 'dot ok' }), 'تمت المزامنة' + m];
  },
  /* رسالة نجاح لا تظهر إلا بعد ثبوت الحفظ؛ وإلا رسالة الفشل */
  /* رسالة نجاح لا تظهر إلا بعد ثبوت الحفظ؛ ولا تظهر إطلاقاً إن حُذفت بيانات الجهاز أثناء الانتظار (ما سُجّل حُذف) */
  savedToast(msg) { const op = this.opGuard(); Store.durable().then(ok => { if (!op.alive()) return; this.toast(ok ? msg : 'لم يُحفظ بعد: ' + (Store.storageError || 'تعذّر الحفظ')); }); },
  /* عملية تنتظر (حفظاً أو خادماً): تبقى «حيّة» ما دامت بيانات الجهاز لم تُحذف والحساب نفسه داخل. بعد أي انتظار تُفحص قبل أي كتابة أو رسالة (LM0133-R5-02) */
  opGuard() { const gen = Store.gen, role = App.role && App.role.id; return { alive: () => Store.gen === gen && (App.role && App.role.id) === role }; },
  renderStatus() { const s = document.getElementById('status'); if (s) { s.innerHTML = ''; s.append(...this.statusInner()); } },
  nav() {
    const items = App.role.id === 'parent'
      ? [['dash', '🏠', 'اللوحة'], ['children', '👧', 'الأطفال'], ['logs', '📒', 'السجلات'], ['reports', '📊', 'التقارير'], ['settings', '⚙️', 'الإعدادات']]
      : [['now', '⏱', 'الآن'], ['today', '📅', 'اليوم'], ['children', '👧', 'الأطفال'], ['logs', '📒', 'السجلات'], ['settings', '⚙️', 'الإعدادات']];
    /* تغيير التبويب يبدأ من أعلى الشاشة الجديدة (0.16) */
    return el('nav', { class: 'bottom' + (inSession() && !App.navOpen ? ' collapsed' : '') }, items.map(([v, ico, name]) => el('button', { class: App.view === v || (v === 'today' && App.view === 'thursday') ? 'active' : '', onclick: () => { const same = App.view === v; App.view = v; App.navOpen = false; UI.rerender(); if (!same) window.scrollTo(0, 0); } }, el('span', { class: 'ico' }, ico), name)));
  },
  modal(title, bodyEl, actions) {
    const bg = el('div', { class: 'modal-bg', onclick: e => { if (e.target === bg) bg.remove(); } });
    const m = el('div', { class: 'modal' }, el('div', { class: 'row between' }, el('h2', { style: 'margin:0;color:var(--brand)' }, title), el('button', { class: 'ghost', onclick: () => bg.remove() }, '✕')), bodyEl, actions ? el('div', { class: 'btns', style: 'margin-top:14px' }, actions) : null);
    bg.append(m); document.body.append(bg); return bg;
  },
  toast(msg) { const t = el('div', { class: 'toast' }, msg); document.body.append(t); setTimeout(() => t.remove(), 2200); },
  /* بديل prompt() الأصلي: نافذة داخلية؛ cb(text) أو null عند الإلغاء */
  prompt(title, placeholder, cb, initial) {
    const t = el('input', { placeholder: placeholder || '', value: initial || '' });
    /* إرسال واحد للزر وEnter: النافذة لا تُغلق إلا إذا قُبلت القيمة (cb لا يعيد false)؛ عند الرفض تبقى بقيمتها وتركيزها */
    const submit = () => { const v = t.value.trim(); if (!v) { this.toast('اكتبي ' + (placeholder || 'القيمة')); t.focus(); return; } if (cb(v) === false) { t.focus(); return; } bg.remove(); };
    const bg = this.modal(title, el('div', null, t), [el('button', { class: 'primary', onclick: submit }, 'حفظ'), el('button', { class: 'ghost', onclick: () => { bg.remove(); cb(null); } }, 'إلغاء')]);
    setTimeout(() => t.focus(), 50); t.addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); submit(); } }); return bg;
  },
  confirm(msg, cb) { const bg = this.modal('تأكيد', el('p', null, msg), [el('button', { class: 'primary', onclick: () => { bg.remove(); cb(); } }, 'نعم'), el('button', { class: 'ghost', onclick: () => bg.remove() }, 'لا')]); },
};

const Views = {};

/* ===== التنبيهات الصوتية داخل البرنامج ===== */
const Alarms = {
  ctx: null, fired: new Set(), day: null,
  on() { return Store.settings.sounds !== false; },
  unlock() { try { if (!this.ctx) this.ctx = new (window.AudioContext || window.webkitAudioContext)(); if (this.ctx.state === 'suspended') this.ctx.resume(); } catch (e) {} },
  beep(kind) {
    if (!this.on()) return; this.unlock(); if (!this.ctx) return;
    const seq = kind === 'start' ? [[880, 0.15], [1175, 0.25]] : kind === 'end' ? [[660, 0.25]] : [[740, 0.2]];
    let t = this.ctx.currentTime;
    for (const [f, d] of seq) { const o = this.ctx.createOscillator(), g = this.ctx.createGain(); o.frequency.value = f; o.type = 'sine'; g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(0.4, t + 0.02); g.gain.exponentialRampToValueAtTime(0.0001, t + d); o.connect(g).connect(this.ctx.destination); o.start(t); o.stop(t + d + 0.02); t += d + 0.08; }
    if (navigator.vibrate) navigator.vibrate(kind === 'end' ? [120, 60, 120] : 150);
  },
  muted() { const a = Store.settings.active; return !!(a && a.dayK === dayKey(App.now()) && a.role === (App.role && App.role.id)); },
  tick() {
    if (!App.role || App.role.id === 'parent' || !this.on()) return;
    const d = App.now(); const dayK = dayKey(d); if (this.day !== dayK) { this.day = dayK; this.fired.clear(); }
    const nowM = d.getHours() * 60 + d.getMinutes();
    if (this.lastMin != null && nowM - this.lastMin > 2) { /* عودة بعد غياب: لا أصوات متراكمة */ this.lastMin = nowM; return; }
    this.lastMin = nowM;
    const list = sessionsFor(App.role.id, d).slice();
    if (WORKDAYS.includes(d.getDay())) list.push({ start: '11:40', end: '12:10', kind: 'break', child: 'all' });
    const starts = new Set(list.map(s => toMin(s.start)));
    const muted = this.muted();
    for (const s of list) {
      const a = toMin(s.start), b = toMin(s.end); const name = s.kind === 'break' ? 'الاستراحة الرئيسية' : `${childName(s.child)} · ${SESSION_KINDS[s.kind].name}`;
      const ev = [[a, 'start', `الآن: ${name}`]];
      /* نهاية هادئة اختيارية، وتُدمج مع بداية التالية إن تلاصقتا */
      if (Store.settings.endAlarm !== false && !starts.has(b)) ev.push([b, 'end', `انتهى وقت: ${name}`]);
      for (const [m, k, msg] of ev) { const key = `${s.start}|${s.kind}|${s.child}|${k}`; if (nowM === m && !this.fired.has(key)) { this.fired.add(key); if (!muted) this.beep(k); UI.toast((muted ? '🔇 ' : '') + msg); } }
    }
  },
};

/* ===== الدخول ===== */
Views.login = function () {
  const online = !!Sync.cfg();
  const wrap = el('div', { class: 'login' });
  wrap.append(el('h1', { style: 'color:var(--brand);margin-bottom:4px' }, 'لوحة المعلمة'), el('p', { class: 'muted' }, 'برنامج حفظ القرآن وتدبره'));
  if (online) {
    const email = el('input', { type: 'email', placeholder: 'البريد', autocomplete: 'username' });
    const pass = el('input', { type: 'password', placeholder: 'كلمة السر', autocomplete: 'current-password' });
    const msg = el('div', { class: 'muted small' });
    const btn = el('button', { class: 'primary', style: 'width:100%;margin-top:12px', onclick: async () => {
      btn.disabled = true; msg.textContent = 'جارٍ الدخول…';
      try { const role = await Sync.login(email.value.trim(), pass.value); if (!role) { msg.textContent = 'الحساب بلا دور؛ اطلب من ولي الأمر ضبط الدور.'; btn.disabled = false; return; } App.setRole(role); Sync.start(); }
      catch (e) { msg.textContent = e.message; btn.disabled = false; }
    } }, 'دخول');
    wrap.append(el('div', { class: 'card' }, label('البريد'), email, label('كلمة السر'), pass, btn, msg));
    wrap.append(el('p', { class: 'small muted' }, 'الخادم مضبوط. ', el('a', { href: '#', onclick: e => { e.preventDefault(); Store.settings.localMode = true; Store.saveSettings(); UI.rerender(); } }, 'الدخول المحلي بدلاً من ذلك')));
    return wrap;
  }
  let sel = null; const pin = el('input', { type: 'password', inputmode: 'numeric', placeholder: 'الرمز', style: 'text-align:center;font-size:1.3em;letter-spacing:6px' });
  const roles = el('div', { class: 'roles' });
  const msg = el('div', { class: 'muted small' });
  for (const r of Object.values(ROLES)) roles.append(el('button', { onclick: e => { sel = r.id; [...roles.children].forEach(b => b.classList.remove('sel')); e.currentTarget.classList.add('sel'); pin.focus(); } }, el('div', { class: 'big' }, r.name), r.title !== r.name ? el('div', { class: 'muted small' }, r.title) : null));
  const go = () => { if (!sel) { msg.textContent = 'اختاري الحساب أولاً'; return; } if (pin.value !== Store.settings.pins[sel]) { msg.textContent = 'الرمز غير صحيح'; return; } App.setRole(sel); };
  pin.addEventListener('keydown', e => { if (e.key === 'Enter') go(); });
  wrap.append(roles, pin, el('button', { class: 'primary', style: 'width:100%;margin-top:12px', onclick: go }, 'دخول'), msg,
    /* الرموز الأولية تُذكر فقط للحسابات التي لم تغيّر رمزها بعد (0.16) */
    (() => { const left = Object.values(ROLES).filter(r => Store.settings.pins[r.id] === PIN_DEFAULTS[r.id]); return el('p', { class: 'small muted', style: 'margin-top:20px' }, left.length ? `الرموز الأولية: ${left.map(r => r.name + ' ' + PIN_DEFAULTS[r.id]).join(' · ')}، وتُغيَّر بعد أول دخول. ` : '', 'لربط الحسابات الثلاثة عبر الإنترنت: الإعدادات ← الخادم.'); })());
  return wrap;
};
function label(t) { return el('label', null, t); }
const PIN_DEFAULTS = { aya: '1111', asst: '2222', parent: '3333' };
/* هل الحساب الحالي داخل جلسة مفتوحة اليوم وعلى شاشة «الآن»؟ */
function inSession() { const a = Store.settings && Store.settings.active; return !!(App.role && a && App.view === 'now' && a.role === App.role.id && a.dayK === todayKey()); }
/* إبقاء الشاشة مضاءة ما دامت جلسة مفتوحة (0.16): المعلمة تستمع ولا تلمس الهاتف دقائق؛ بلا هذا تُقفل الشاشة وسط التسميع */
const Wake = {
  lock: null, want: false,
  sync() {
    const a = Store.settings && Store.settings.active;
    const want = !!(App.role && a && a.role === App.role.id && a.dayK === todayKey());
    if (want === this.want && (this.lock || !want)) return; this.want = want;
    try { if (window.LawhatAndroid && window.LawhatAndroid.keepScreenOn) { window.LawhatAndroid.keepScreenOn(want); return; } } catch (e) {}
    if (!want) { if (this.lock) { try { this.lock.release(); } catch (e) {} this.lock = null; } return; }
    if (navigator.wakeLock && document.visibilityState === 'visible') navigator.wakeLock.request('screen').then(l => { this.lock = l; l.addEventListener('release', () => { if (this.lock === l) this.lock = null; }); if (!this.want) { l.release(); } }).catch(() => {});
  },
};
document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible' && Wake.want && !Wake.lock) { Wake.want = false; Wake.sync(); } });
/* بطاقة «غيّري الرمز الأولي»: تبقى أعلى الشاشة الرئيسية حتى يُغيَّر رمز الحساب (في الدخول المحلي) */
function pinField() {
  const id = App.role.id;
  const i = el('input', { type: 'password', inputmode: 'numeric', placeholder: 'رمز جديد (4 أرقام أو أكثر)', style: 'max-width:220px' });
  return el('div', { class: 'row pinfield' }, i, el('button', { class: 'primary', onclick: () => { const v = i.value.trim(); if (!/^\d{4,}$/.test(v)) { UI.toast('الرمز 4 أرقام أو أكثر'); return; } if (Object.values(PIN_DEFAULTS).includes(v)) { UI.toast('اختاري رمزاً غير الرموز الأولية'); return; } Store.settings.pins[id] = v; Store.saveSettings(); UI.toast('حُفظ الرمز الجديد'); UI.rerender(); } }, 'حفظ الرمز'));
}
function pinIsDefault() { const id = App.role.id; return (!Sync.cfg() || Store.settings.localMode) && Store.settings.pins[id] === PIN_DEFAULTS[id]; }
function PinNudge() {
  if (!pinIsDefault()) return null;
  return el('div', { class: 'card pinnudge', style: 'border:2px solid var(--yellow)' }, el('h2', null, 'غيّري رمز الدخول الأولي'), el('p', { class: 'small' }, `رمز هذا الحساب ما زال الرمز الأولي (${PIN_DEFAULTS[App.role.id]}) المكتوب على شاشة الدخول، فيعرفه كل من يفتح البرنامج.`), pinField());
}
/* معاني المصطلحات (0.16) */
const GLOSSARY = [
  ['الجديد', 'صفحة اليوم (أو مقطع اليوم للصغير). تُسمَّع ثلاث مرات في يومها ثم صباح الغد.'],
  ['بوابة الأمس', 'تسميع صفحة آخر يوم حفظ غيباً أول الجلسة. إن لم تكن سالمة فلا جديد اليوم. صباح السبت بوابته صفحة الأربعاء.'],
  ['القريب', 'صفحات الجزء الجاري. تُراجع كل يوم بسقف: الحمراء، ثم آخر 5 صفحات، ثم الجزء المنتظر فحصه، ثم الباقي بالتناوب.'],
  ['البعيد', 'الأجزاء المختومة المجازة. لها حصة يومية تدور عليها كلها بالترتيب.'],
  ['القائمة الصفراء', 'كل آية وقع فيها خطأ. تُشطب بعد ثلاثة تسميعات سالمة في ثلاثة أيام مختلفة.'],
  ['المتشابهات', 'مواضع انتقل فيها الطفل إلى آية تشبهها. تُعالج في مجلس الخميس.'],
  ['مستقل / بمساعدة / توقف', 'مستقل: بلا تلقين. بمساعدة: تلقين أو اثنان. توقف: ثلاثة فأكثر أو عجز عن الإكمال. اللون يحسبه البرنامج وتعتمده آية.'],
  ['صباح إصلاح', 'قرار آية حين تسقط البوابة: الصباح لإصلاح صفحة الأمس بلا جديد.'],
  ['بطاقة التسليم', 'ملخص جلسة المساعدة (النتائج والأخطاء والباقي) يصل إلى آية تلقائياً.'],
  ['سقف المراجعة', 'أقصى عدد صفحات يومياً في القريب والبعيد. تضبطه آية لكل طفل.'],
];
function glossaryModal() { UI.modal('معاني المصطلحات', el('div', null, GLOSSARY.map(([k, v]) => el('p', { class: 'small', style: 'margin:8px 0' }, el('b', null, k + ': '), v)))); }
function helpButton() { return el('button', { class: 'ghost small helpbtn', title: 'معاني المصطلحات', onclick: glossaryModal }, '؟ المصطلحات'); }
/* نسخ نص: «نُسخت» فقط إن نجح النسخ فعلاً؛ وإلا نافذة بالنص محدداً للنسخ اليدوي (المتصفح قد يمنع الحافظة) */
async function copyText(text) {
  try {
    if (AppShell.inApp() && window.LawhatAndroid.copy) { if (!window.LawhatAndroid.copy(text)) throw new Error('copy'); UI.toast('نُسخت'); return; }
    if (!navigator.clipboard) throw new Error('no clipboard'); await navigator.clipboard.writeText(text); UI.toast('نُسخت');
  }
  catch (e) { const t = el('textarea', { style: 'min-height:200px' }, text); UI.modal('انسخي النص', el('div', null, el('p', { class: 'small muted' }, 'منع المتصفح النسخ التلقائي: النص محدد، انسخيه يدوياً.'), t)); t.focus(); t.select(); }
}
