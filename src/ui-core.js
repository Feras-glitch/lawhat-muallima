/* ===== الهيكل العام: التطبيق، الدخول، التنقل، النوافذ ===== */
const App = {
  role: null, view: 'now', sub: {}, timeOffset: 0,
  realNow() { return new Date(Date.now() + (Store.settings.timeOffset || 0)); },
  now() { return wallClock(this.realNow()); },
  setRole(r) { this.role = ROLES[r]; sessionStorage.setItem(LS_SESSION, r); this.view = r === 'parent' ? 'dash' : 'now'; Alarms.unlock(); UI.rerender(); Persist.auto(); },
  logout() { this.role = null; sessionStorage.removeItem(LS_SESSION); if (Sync.cfg()) Sync.logout(); UI.rerender(); },
  can(perm) { return !!(this.role && this.role[perm]); },
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
  for (const c of children.flat()) if (c !== null && c !== undefined && c !== false) n.append(c.nodeType ? c : document.createTextNode(String(c)));
  return n;
};
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
    this.restoreDrafts(drafts);
    if (soft) window.scrollTo(0, scroll);
  },
  header() {
    const d = App.now();
    return el('header', { class: 'top' },
      el('div', null, el('div', { class: 'title' }, 'لوحة المعلمة · برنامج القرآن'), el('div', { class: 'sub' }, `${App.role.title} · ${DAY_NAMES[d.getDay()]} ${d.getDate()}/${d.getMonth() + 1} · ${fmtTime12(hhmm(d))} بكين${sameTz() ? '' : ' · ' + App.realNow().toLocaleTimeString('ar-EG-u-nu-latn', { hour: 'numeric', minute: '2-digit' }) + ' ' + tzShort()}`)),
      el('div', { class: 'status', id: 'status' }, this.statusInner()),
      Store.settings.timeOffset ? el('div', { class: 'alert red', style: 'width:100%;margin:6px 0 0;padding:4px 8px' }, '⚠ الوقت محاكى! ', el('button', { class: 'ghost small', onclick: () => { Store.settings.timeOffset = 0; Store.saveSettings(); UI.rerender(); } }, 'العودة للوقت الحقيقي')) : null);
  },
  statusInner() {
    const m = Alarms.muted() && Alarms.on() ? ' · 🔇 الأصوات مكتومة أثناء الجلسة' : '';
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
  savedToast(msg) { Store.durable().then(ok => this.toast(ok ? msg : 'لم يُحفظ بعد: ' + (Store.storageError || 'تعذّر الحفظ'))); },
  renderStatus() { const s = document.getElementById('status'); if (s) { s.innerHTML = ''; s.append(...this.statusInner()); } },
  nav() {
    const items = App.role.id === 'parent'
      ? [['dash', '🏠', 'اللوحة'], ['children', '👧', 'الأطفال'], ['logs', '📒', 'السجلات'], ['reports', '📊', 'التقارير'], ['settings', '⚙️', 'الإعدادات']]
      : [['now', '⏱', 'الآن'], ['today', '📅', 'اليوم'], ['children', '👧', 'الأطفال'], ['logs', '📒', 'السجلات'], ['settings', '⚙️', 'الإعدادات']];
    return el('nav', { class: 'bottom' }, items.map(([v, ico, name]) => el('button', { class: App.view === v || (v === 'today' && App.view === 'thursday') ? 'active' : '', onclick: () => { App.view = v; UI.rerender(); } }, el('span', { class: 'ico' }, ico), name)));
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
  wrap.append(el('h1', { style: 'color:var(--brand);margin-bottom:4px' }, 'لوحة المعلمة'), el('p', { class: 'muted' }, 'برنامج حفظ القرآن وتدبره — دلال وفرح وكريم'));
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
  for (const r of Object.values(ROLES)) roles.append(el('button', { onclick: e => { sel = r.id; [...roles.children].forEach(b => b.classList.remove('sel')); e.currentTarget.classList.add('sel'); pin.focus(); } }, el('div', { class: 'big' }, r.name), el('div', { class: 'muted small' }, r.title)));
  const go = () => { if (!sel) { msg.textContent = 'اختاري الحساب أولاً'; return; } if (pin.value !== Store.settings.pins[sel]) { msg.textContent = 'الرمز غير صحيح'; return; } App.setRole(sel); };
  pin.addEventListener('keydown', e => { if (e.key === 'Enter') go(); });
  wrap.append(roles, pin, el('button', { class: 'primary', style: 'width:100%;margin-top:12px', onclick: go }, 'دخول'), msg,
    el('p', { class: 'small muted', style: 'margin-top:20px' }, 'الرموز الأولية: آية 1111 · المساعدة 2222 · ولي الأمر 3333، وتُغيَّر من الإعدادات. لربط الحسابات الثلاثة عبر الإنترنت: الإعدادات ← الخادم.'));
  return wrap;
};
function label(t) { return el('label', null, t); }
/* نسخ نص: «نُسخت» فقط إن نجح النسخ فعلاً؛ وإلا نافذة بالنص محدداً للنسخ اليدوي (المتصفح قد يمنع الحافظة) */
async function copyText(text) {
  try { if (!navigator.clipboard) throw new Error('no clipboard'); await navigator.clipboard.writeText(text); UI.toast('نُسخت'); }
  catch (e) { const t = el('textarea', { style: 'min-height:200px' }, text); UI.modal('انسخي النص', el('div', null, el('p', { class: 'small muted' }, 'منع المتصفح النسخ التلقائي: النص محدد، انسخيه يدوياً.'), t)); t.focus(); t.select(); }
}
