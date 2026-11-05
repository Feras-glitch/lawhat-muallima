/* ===== التخزين والنموذج: أحداث تُضاف ولا تُعدَّل، وحالة تُشتق منها ===== */
const LS_EVENTS = 'lm_events_v1';
const LS_SETTINGS = 'lm_settings_v1';
const LS_SESSION = 'lm_session_v1';

const Store = {
  events: [],
  settings: {},
  /* ===== التخزين: IndexedDB (سعة كبيرة، كتابة سجل واحد لا الكل) مع ترحيل تلقائي من localStorage وبديل عند تعذّر IDB ===== */
  db: null, idbOk: false, pending: new Map(), flushTimer: null,
  async openDb() {
    if (!window.indexedDB) return null;
    return new Promise((res) => {
      let req; try { req = indexedDB.open('lawhat_muallima', 1); } catch (e) { res(null); return; }
      req.onupgradeneeded = () => { const db = req.result; if (!db.objectStoreNames.contains('events')) db.createObjectStore('events', { keyPath: 'id' }); };
      req.onsuccess = () => res(req.result); req.onerror = () => res(null); req.onblocked = () => res(null);
    });
  },
  async load() {
    try { this.settings = JSON.parse(localStorage.getItem(LS_SETTINGS) || '{}'); } catch (e) { this.settings = {}; }
    if (!this.settings.pins) this.settings.pins = { aya: '1111', asst: '2222', parent: '3333' };
    if (!this.settings.deviceId) this.settings.deviceId = 'd' + Math.random().toString(36).slice(2, 10);
    this.saveSettings();
    let lsRaw = []; try { lsRaw = JSON.parse(localStorage.getItem(LS_EVENTS) || '[]'); } catch (e) { lsRaw = []; }
    this.db = await this.openDb();
    if (this.db) {
      const fromDb = await new Promise((res) => { try { const tx = this.db.transaction('events', 'readonly'); const r = tx.objectStore('events').getAll(); r.onsuccess = () => res(r.result || []); r.onerror = () => res(null); } catch (e) { res(null); } });
      if (fromDb) {
        this.idbOk = true;
        const have = new Set(fromDb.map(e => e.id));
        const migrate = lsRaw.filter(e => e && e.id && !have.has(e.id));
        this.raw = fromDb.concat(migrate).sort((a, b) => a.ts - b.ts);
        if (migrate.length) { const ok = await this.putMany(migrate); if (ok) { try { localStorage.removeItem(LS_EVENTS); } catch (e) {} } }
        else if (lsRaw.length && !migrate.length) { try { localStorage.removeItem(LS_EVENTS); } catch (e) {} }
      } else { this.raw = lsRaw; }
    } else { this.raw = lsRaw; }
    this.refresh();
  },
  /* كتابة سجلات بعينها إلى IDB */
  putMany(list) {
    if (!this.idbOk || !this.db) return Promise.resolve(false);
    return new Promise((res) => { try { const tx = this.db.transaction('events', 'readwrite'); const st = tx.objectStore('events'); for (const e of list) st.put(e); tx.oncomplete = () => res(true); tx.onerror = () => res(false); tx.onabort = () => res(false); } catch (e) { res(false); } });
  },
  clearDb() { if (!this.idbOk || !this.db) return Promise.resolve(false); return new Promise((res) => { try { const tx = this.db.transaction('events', 'readwrite'); tx.objectStore('events').clear(); tx.oncomplete = () => res(true); tx.onerror = () => res(false); } catch (e) { res(false); } }); },
  /* الحفظ: مع IDB تُكتب السجلات المتغيرة فقط (دفعة قصيرة)؛ بدونه يُكتب الكل في localStorage.
     القيمة المرجعة: هل التخزين سليم الآن (فشل سابق في IDB أو امتلاء localStorage يعيد false). */
  dirty: new Set(),
  saveEvents(changed) {
    if (this.idbOk) {
      for (const e of (changed || this.raw)) this.dirty.add(e.id);
      clearTimeout(this.flushTimer); this.flushTimer = setTimeout(() => this.flush(), 20);
      return true;
    }
    try { localStorage.setItem(LS_EVENTS, JSON.stringify(this.raw)); this.storageError = null; return true; } catch (e) { this.storageError = 'تعذّر الحفظ: امتلأت ذاكرة الجهاز. صدّري البيانات وأبلغي ولي الأمر.'; return false; } },
  async flush() {
    if (!this.dirty.size) return true;
    const ids = this.dirty; this.dirty = new Set();
    const list = this.raw.filter(e => ids.has(e.id));
    const ok = await this.putMany(list);
    if (!ok) { for (const id of ids) this.dirty.add(id);
      /* طوارئ: نسخة كاملة في localStorage إن اتسعت، ويبقى التحذير حتى ينجح IDB */
      let lsOk = false; try { localStorage.setItem(LS_EVENTS, JSON.stringify(this.raw)); lsOk = true; } catch (e) {}
      this.storageError = lsOk ? 'تعذّر الحفظ في قاعدة الجهاز (حُفظت نسخة احتياطية مؤقتة)؛ صدّري البيانات' : 'تعذّر الحفظ في قاعدة الجهاز وامتلأت الذاكرة؛ صدّري البيانات فوراً'; try { UI.toast(this.storageError); UI.renderStatus(); } catch (x) {} }
    else if (this.storageError && this.storageError.startsWith('تعذّر الحفظ في قاعدة')) { this.storageError = null; try { UI.renderStatus(); } catch (x) {} }
    return ok;
  },
  /* السجل الخام append-only؛ events = السجلات الحيّة (غير المتراجَع عنها). التراجع نفسه يبقى في الخام */
  /* مرآة محلية لسياسة الخادم: ما يجوز لكل دور تسجيله (النيابة لا توسّعها) */
  roleAllows(by, ev) {
    if (by === 'aya') return true;
    if (by === 'asst') return ['outcome', 'error', 'note', 'session_done', 'fluency_time', 'card', 'yellow_pass', 'handoff', 'handoff_update', 'undo', 'session_start', 'session_cancel', 'fluency_page', 'tilawa'].includes(ev.type) && !(ev.type === 'outcome' && (ev.step === 'exam' || ev.parent));
    if (by === 'parent') return ['parent_exam', 'note', 'undo'].includes(ev.type) || (ev.type === 'outcome' && ev.parent === true);
    return false;
  },
  /* من يجوز له التراجع عن سجل: صاحبه، وآية عن سجلات المساعدة */
  canUndo(by, target) { return !!target && target.type !== 'undo' && (target.by === by || (by === 'aya' && target.by === 'asst')); },
  refresh() {
    const byId = new Map(this.raw.map(e => [e.id, e]));
    const undone = new Set();
    for (const u of this.raw) if (u.type === 'undo') { const t = byId.get(u.target); if (t && this.canUndo(u.by, t)) undone.add(u.target); }
    this.events = this.raw.filter(e => e.type !== 'undo' && !undone.has(e.id));
    /* فهارس للأداء: بالنوع وبمفتاح الجلسة */
    this.byTypeMap = new Map(); this.byKeyMap = new Map();
    for (const e of this.events) { let a = this.byTypeMap.get(e.type); if (!a) this.byTypeMap.set(e.type, a = []); a.push(e); if (e.key && (e.type === 'session_done' || e.type === 'session_cancel' || e.type === 'session_start')) { let k = this.byKeyMap.get(e.key); if (!k) this.byKeyMap.set(e.key, k = []); k.push(e); } }
  },
  ofType(t) { return this.byTypeMap.get(t) || []; },
  ofKey(k) { return this.byKeyMap.get(k) || []; },
  reset() { this.raw = []; this.dirty = new Set(); this.refresh(); if (this.idbOk) this.clearDb(); else this.saveEvents(); },
  saveSettings() { localStorage.setItem(LS_SETTINGS, JSON.stringify(this.settings)); },
  add(ev) {
    ev.id = ev.id || (Date.now().toString(36) + Math.random().toString(36).slice(2, 8));
    ev.ts = ev.ts || App.realNow().getTime();
    ev.day = ev.day || dayKey(wallClock(new Date(ev.ts)));
    ev.by = ev.by || (App.role && App.role.id) || 'unknown';
    ev.dev = this.settings.deviceId;
    const act = this.settings.active;
    if (act && act.sid && !ev.sid && ev.by === act.role && ['outcome', 'error', 'new_page', 'fluency_time', 'fluency_page', 'yellow_pass', 'card', 'note', 'tilawa', 'juz_exam'].includes(ev.type)) ev.sid = act.sid;
    ev.synced = false;
    if (!this.validEvent(ev)) { const msg = 'سجل غير صالح لم يُحفظ: ' + ev.type; try { UI.toast(msg); } catch (x) {} throw new Error(msg); }
    if (!this.roleAllows(ev.by, ev)) { const msg = `لا يُسمح لحساب ${ROLES[ev.by] ? ROLES[ev.by].name : ev.by} بتسجيل «${ev.type}»؛ يُطلب من آية`; try { UI.toast(msg); } catch (x) {} throw new Error(msg); }
    this.raw.push(ev);
    if (!this.saveEvents([ev])) { this.raw.pop(); try { UI.toast(this.storageError); UI.renderStatus(); } catch (x) {} throw new Error(this.storageError); }
    this.refresh();
    Sync.schedule();
    return ev;
  },
  byType(type, child) { return this.ofType(type).filter(e => !child || e.child === child); },
  rejectReason(e, batch) {
    if (!e || typeof e !== 'object') return 'ليس كائناً';
    if (typeof e.id !== 'string' || typeof e.type !== 'string' || typeof e.ts !== 'number' || !/^\d{4}-\d{2}-\d{2}$/.test(e.day || '')) return 'حقول أساسية ناقصة أو غير صالحة';
    if (e.by != null && !ROLES[e.by]) return 'دور غير معروف: ' + e.by;
    if (e.child != null && !CHILDREN[e.child]) return 'طفل غير معروف';
    if (e.type === 'undo') { const t = this.raw.find(x => x.id === e.target) || (batch || []).find(x => x && x.id === e.target); return t ? `لا صلاحية لـ${ROLES[e.by] ? ROLES[e.by].name : e.by} للتراجع عن سجل ${ROLES[t.by] ? ROLES[t.by].name : t.by}` : 'هدف التراجع غير موجود'; }
    return 'حقول النوع ' + e.type + ' غير صالحة';
  },
  validEvent(e, batch) {
    if (!e || typeof e !== 'object') return false;
    if (typeof e.id !== 'string' || typeof e.type !== 'string' || typeof e.ts !== 'number' || !/^\d{4}-\d{2}-\d{2}$/.test(e.day || '')) return false;
    if (e.by != null && !ROLES[e.by]) return false;
    if (e.sid != null && typeof e.sid !== 'string') return false;
    if (e.child != null && !CHILDREN[e.child]) return false;
    const isPage = v => Number.isInteger(v) && v >= 1 && v <= 604;
    const isInt = (v, a, b) => Number.isInteger(v) && v >= a && v <= b;
    const oneOf = (v, arr) => arr.includes(v);
    const needChild = ['juz_exam', 'tilawa', 'handoff', 'layer', 'color', 'new_page', 'outcome', 'error', 'decision', 'surah_passed', 'juz_passed', 'card', 'fluency_time', 'parent_exam', 'yellow_pass'];
    if (needChild.includes(e.type) && !CHILDREN[e.child]) return false;
    if (e.page != null && !isPage(e.page)) return false;
    switch (e.type) {
      case 'layer': return isPage(e.page) && oneOf(e.layer, ['none', 'new', 'near', 'far']) && (e.color == null || oneOf(e.color, ['green', 'yellow', 'red']));
      case 'color': return isPage(e.page) && oneOf(e.color, ['green', 'yellow', 'red', 'none']) && (e.lines == null || (Array.isArray(e.lines) && isInt(e.lines[0], 1, 15) && isInt(e.lines[1], 1, 15)));
      case 'new_page': return isPage(e.page) && isInt(e.linesFrom, 1, 15) && isInt(e.linesTo, 1, 15) && e.linesFrom <= e.linesTo && (e.minutes == null || isInt(e.minutes, 0, 600));
      case 'outcome': return isPage(e.page) && typeof e.step === 'string' && e.step.length <= 20 && oneOf(e.result, ['clean', 'yellow', 'red', 'partial']) && (e.parent == null || e.parent === true)
        && (e.prompts == null || isInt(e.prompts, 0, 99)) && (e.tajweed == null || oneOf(e.tajweed, ['ok', 'issue'])) && (e.meaning == null || oneOf(e.meaning, ['ok', 'support', 'untested'])) && (e.selfCorrect == null || isInt(e.selfCorrect, 0, 99))
        && (e.lines == null || (Array.isArray(e.lines) && isInt(e.lines[0], 1, 15) && isInt(e.lines[1], 1, 15) && e.lines[0] <= e.lines[1]));
      case 'undo': {
        if (typeof e.target !== 'string' || e.target === e.id || (e.reason != null && typeof e.reason !== 'string')) return false;
        const t = this.raw.find(x => x.id === e.target) || (batch ? batch.find(x => x && x.id === e.target) : null);
        if (!t) return !!batch; /* عند الاستيراد/المزامنة: قد يصل الأصل في دفعة لاحقة؛ لا أثر له حتى يصل */
        return this.canUndo(e.by, t);
      }
      case 'error': return isPage(e.page) && oneOf(e.etype, ERROR_TYPES.map(t => t.id)) && (e.lines == null || (Array.isArray(e.lines) && isInt(e.lines[0], 1, 15) && isInt(e.lines[1], 1, 15) && e.lines[0] <= e.lines[1])) && (e.surah == null || isInt(e.surah, 1, 114)) && (e.ayah == null || isInt(e.ayah, 1, 286)) && (e.target == null || (typeof e.target === 'object' && isInt(e.target.surah, 1, 114) && (e.target.ayah == null || isInt(e.target.ayah, 1, 286))));
      case 'decision': return oneOf(e.kind, ['repair', 'reduce', 'restore', 'pause', 'resume', 'override', 'juz', 'surah']) && (e.text == null || typeof e.text === 'string');
      case 'surah_passed': return isInt(e.surah, 1, 114);
      case 'juz_passed': return isInt(e.juz, 1, 30) && (e.exam == null || typeof e.exam === 'string');
      case 'juz_exam': return isInt(e.juz, 1, 30) && oneOf(e.result, ['clean', 'yellow', 'red']) && (e.prompts == null || isInt(e.prompts, 0, 99)) && (e.minutes == null || isInt(e.minutes, 0, 600)) && (e.note == null || typeof e.note === 'string')
        /* الاتساق: مستقل = 0 تلقين؛ بمساعدة = 1–2؛ توقف = أي عدد (حتى بلا تلقين) */
        && !(e.result === 'clean' && e.prompts > 0) && !(e.result === 'yellow' && (e.prompts == null || e.prompts < 1 || e.prompts > 2));
      case 'tilawa': return Array.isArray(e.pages) && e.pages.length >= 1 && e.pages.length <= 30 && e.pages.every(x => isPage(x)) && oneOf(e.kind, ['nazar', 'listen']) && (e.times == null || isInt(e.times, 1, 10));
      case 'yellow_pass': return isPage(e.page) && isInt(e.surah, 1, 114) && isInt(e.ayah, 1, 286);
      case 'fluency_time': return (e.page == null || isPage(e.page)) && isInt(e.seconds, 1, 7200);
      case 'parent_exam': return Array.isArray(e.pages) && e.pages.length >= 1 && e.pages.every(x => isPage(Number(x))) && isInt(e.green, 0, e.pages.length);
      case 'card': return isPage(e.page) && oneOf(e.kind, ['surah', 'page']) && typeof e.key === 'string';
      case 'note': return typeof e.text === 'string';
      case 'session_start': return typeof e.key === 'string' && typeof e.sid === 'string' && (e.proxyFor == null || ROLES[e.proxyFor] != null) && (e.reason == null || typeof e.reason === 'string');
      case 'session_cancel': return typeof e.key === 'string' && typeof e.reason === 'string' && e.reason.length > 0;
      case 'fluency_page': return isPage(e.page);
      case 'session_done': return typeof e.key === 'string' && (e.status == null || oneOf(e.status, ['complete', 'partial', 'stopped'])) && (e.remaining == null || Array.isArray(e.remaining)) && (e.reason == null || typeof e.reason === 'string');
      case 'handoff': return typeof e.key === 'string' && typeof e.to === 'string' && ROLES[e.to] != null && Array.isArray(e.items);
      case 'handoff_status': return typeof e.handoff === 'string' && oneOf(e.status, ['seen', 'handled', 'reopened']);
      case 'handoff_update': return typeof e.handoff === 'string' && Array.isArray(e.items);
      default: return false;
    }
  },
  importEvents(list) {
    if (!Array.isArray(list)) throw new Error('الملف ليس قائمة أحداث');
    const bad = list.filter(e => !this.validEvent(e, list));
    if (bad.length) throw new Error(`رُفض الملف كاملاً: ${bad.length} سجل غير صالح (مثال: ${JSON.stringify(bad[0]).slice(0, 80)})`);
    const have = new Set(this.raw.map(e => e.id));
    const before = this.raw.slice();
    let n = 0; const added = [];
    for (const e of list) if (!have.has(e.id)) { this.raw.push(e); have.add(e.id); n++; added.push(e); }
    this.raw.sort((a, b) => a.ts - b.ts);
    if (!this.saveEvents(added)) { this.raw = before; throw new Error(this.storageError); }
    this.refresh();
    return n;
  },
};

function dayKey(d) { const y = d.getFullYear(), m = String(d.getMonth() + 1).padStart(2, '0'), dd = String(d.getDate()).padStart(2, '0'); return `${y}-${m}-${dd}`; }
function parseDay(k) { const [y, m, d] = k.split('-').map(Number); return new Date(y, m - 1, d); }
function daysBetween(a, b) { return Math.round((parseDay(b) - parseDay(a)) / 86400000); }
function todayKey() { return dayKey(App.now()); }
/* ===== التوقيت: الخطة بتوقيت الأطفال (الصين)، والعرض بتوقيت المعلمة أيضاً ===== */
const PLAN_TZ = 'Asia/Shanghai';
const _tzFmt = new Intl.DateTimeFormat('en-US', { timeZone: PLAN_TZ, hourCycle: 'h23', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' });
function wallClock(instant) { // Date مزيفة تحمل أرقام ساعة الصين في حقولها المحلية
  const parts = {}; for (const x of _tzFmt.formatToParts(instant)) parts[x.type] = x.value;
  return new Date(Number(parts.year), Number(parts.month) - 1, Number(parts.day), Number(parts.hour) % 24, Number(parts.minute), Number(parts.second));
}
function deviceTz() { try { return Intl.DateTimeFormat().resolvedOptions().timeZone; } catch (e) { return ''; } }
function planInstant(dayK, hm) { // لحظة حقيقية من يوم ووقت بتوقيت الصين (+8 بلا توقيت صيفي)
  const [y, m, d] = dayK.split('-').map(Number); const [h, mi] = hm.split(':').map(Number);
  return new Date(Date.UTC(y, m - 1, d, h - 8, mi));
}
function localOf(dayK, hm) { // نفس اللحظة بساعة جهاز المعلمة
  const inst = planInstant(dayK, hm);
  return inst.toLocaleTimeString('ar-EG-u-nu-latn', { hour: 'numeric', minute: '2-digit' });
}
function sameTz() { return deviceTz() === PLAN_TZ; }
function timePair(hm, dayK) { return sameTz() ? fmtTime12(hm) : `${fmtTime12(hm)} بكين · ${localOf(dayK || todayKey(), hm)} ${tzShort()}`; }
function tzShort() { const t = deviceTz(); return t === 'Africa/Cairo' ? 'القاهرة' : t === PLAN_TZ ? 'بكين' : (t.split('/').pop() || 'محلي').replace('_', ' '); }
function chinaHHMM(ts) { return hhmm(wallClock(new Date(ts))); }
function hhmm(d) { return String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0'); }
function fmtTime12(s) { const [h, m] = s.split(':').map(Number); const hh = ((h + 11) % 12) + 1; return `${hh}:${String(m).padStart(2, '0')} ${h < 12 ? 'ص' : 'م'}`; }
function fmtDay(k) { const d = parseDay(k); return `${DAY_NAMES[d.getDay()]} ${d.getDate()}/${d.getMonth() + 1}`; }

/* ترتيب الحفظ الجديد لكل طفل */
function newOrder(childId) {
  const seq = [];
  if (childId === 'karim') {
    for (let p = 604; p >= 582; p--) seq.push(p); // جزء عمّ صاعداً من الناس
    for (let p = 562; p <= 581; p++) seq.push(p); // ثم تبارك
    for (let p = 542; p <= 561; p++) seq.push(p);
  } else {
    for (const j of [28, 27, 26]) for (const p of juzPages(j)) seq.push(p);
    for (let p = 2; p <= 501; p++) seq.push(p);
  }
  return seq;
}

/* الحالة المشتقة لطفل */
function deriveChild(childId) {
  const evs = Store.events.filter(e => e.child === childId);
  const pages = {};
  for (let p = 1; p <= 604; p++) pages[p] = { page: p, layer: 'none', color: null, colorDay: null, lastReview: null, lastFar: null, errors: 0, linesDone: 0 };
  let currentJuz = null;
  let lastNewPage = null;
  const newPages = [];
  const passedSurahs = new Set(); const passedDay = {};
  let paused = false, reduced = false;
  for (const e of evs) {
    if (e.page != null && !pages[e.page]) continue; // حدث بصفحة غير صالحة لا يُسقط العرض
    if (e.type === 'layer') { const pg = pages[e.page]; pg.layer = e.layer; if (e.color) { pg.color = e.color; pg.colorDay = e.day; } if (e.layer === 'far') { pg.lastReview = e.day; pg.lastFar = e.day; } }
    if (e.type === 'new_page') {
      newPages.push(e);
      const pg = pages[e.page];
      pg.linesDone = Math.max(pg.linesDone, e.linesTo || 15);
      pg.lastReview = e.day;
      if (pg.linesDone >= 15) { pg.layer = 'near'; lastNewPage = e.page; }
      else { pg.layer = 'new'; lastNewPage = e.page; }
      currentJuz = juzOfPage(e.page);
    }
    if (e.type === 'color') { const pg = pages[e.page]; if (e.lines) { pg.segs = pg.segs || {}; pg.segs[segKey(e.lines)] = { color: e.color, day: e.day, lines: e.lines }; const order = { red: 3, yellow: 2, green: 1, none: 0 }; const worst = Object.values(pg.segs).reduce((w, x) => order[x.color] > order[w] ? x.color : w, 'none'); pg.color = worst === 'none' ? e.color : worst; pg.colorDay = e.day; } else { pg.color = e.color; pg.colorDay = e.day; } }
    if (e.type === 'outcome') {
      pages[e.page].lastReview = e.day;
      if ((e.step === 'far' || e.step === 'exam') && e.result !== 'partial') pages[e.page].lastFar = e.day;
    }
    if (e.type === 'error') pages[e.page].errors++;
    if (e.type === 'juz_passed') { const jp = juzPages(e.juz); for (const p of jp) if (pages[p].layer === 'near') { pages[p].lastFar = e.day; pages[p].lastReview = e.day; } for (const p of juzPages(e.juz)) if (pages[p].layer === 'near') pages[p].layer = 'far'; }
    if (e.type === 'surah_passed') { passedSurahs.add(e.surah); passedDay[e.surah] = e.day; }
    if (e.type === 'decision') { if (e.kind === 'pause') paused = true; if (e.kind === 'resume') paused = false; if (e.kind === 'reduce') reduced = true; if (e.kind === 'restore') reduced = false; }
  }
  /* صفحة القريب تنتقل إلى البعيد حين تُعتمد كل سورها التي بدأها الطفل */
  if (passedSurahs.size) for (const p of Object.keys(pages).map(Number)) { const pg = pages[p]; if (pg.layer !== 'near') continue; const ss = surahsOfPage(p); if (ss.every(x => passedSurahs.has(x))) { pg.layer = 'far'; const d = ss.map(x => passedDay[x]).sort().pop(); if (!pg.lastFar || pg.lastFar < d) { pg.lastFar = d; pg.lastReview = d; } } }
  const far = Object.values(pages).filter(p => p.layer === 'far').map(p => p.page).sort((a, b) => a - b);
  const near = Object.values(pages).filter(p => p.layer === 'near').map(p => p.page).sort((a, b) => a - b);
  const order = newOrder(childId);
  let nextNew = null, nextLines = null;
  for (const p of order) {
    const pg = pages[p];
    if (pg.layer === 'none') { nextNew = p; nextLines = [1, childId === 'karim' ? 4 : (reduced ? 8 : 15)]; break; }
    if (pg.layer === 'new' && pg.linesDone < 15) { nextNew = p; nextLines = [pg.linesDone + 1, childId === 'karim' ? Math.min(15, pg.linesDone + 4) : 15]; break; }
  }
  // حصة البعيد
  /* الحصة: المحفوظ ÷ 8 جلسات بعيد (5 في الأسبوع) ≈ دورة 12 يوماً تقويمياً */
  const quota = far.length === 0 ? 0 : (childId === 'karim' ? Math.max(3, Math.ceil(far.length / 8)) : Math.max(7, Math.ceil(far.length / 8)));
  const today = todayKey();
  let lastFarPage = null, lastFarTs = 0;
  for (const e of evs) if (e.type === 'outcome' && e.step === 'far' && e.result !== 'partial' && e.day < today && e.ts >= lastFarTs) { lastFarTs = e.ts; lastFarPage = e.page; }
  let startIdx = 0;
  if (lastFarPage != null) { const i = far.indexOf(lastFarPage); startIdx = i >= 0 ? (i + 1) % far.length : 0; }
  const todayFar = [];
  for (let k = 0; k < Math.min(quota, far.length); k++) todayFar.push(far[(startIdx + k) % far.length]);
  // أطول صفحة بلا تسميع
  let maxGap = 0, maxGapPage = null;
  for (const p of far) { const d = pages[p].lastFar || pages[p].lastReview; const gap = d ? daysBetween(d, today) : 99; if (gap > maxGap) { maxGap = gap; maxGapPage = p; } }
  const todayNew = newPages.filter(e => e.day === today).map(e => e.page);
  const yesterdayNew = lastNewFor(childId, 1);
  return { id: childId, pages, far, near, currentJuz, lastNewPage, nextNew, nextLines, quota, todayFar, maxGap, maxGapPage, todayNew, yesterdayNew, paused, reduced, passedSurahs };
}

/* آخر صفحة جديدة قبل اليوم (للبوابة) */
function lastNewFor(childId, skipToday) {
  const today = todayKey();
  const list = Store.events.filter(e => e.child === childId && e.type === 'new_page' && (!skipToday || e.day !== today));
  if (!list.length) return null;
  const e = list[list.length - 1];
  return { page: e.page, lines: e.linesFrom ? [e.linesFrom, e.linesTo] : null, day: e.day };
}

/* القائمة الصفراء: مفتاح الآية = سورة:آية */
function yellowList(childId) {
  const items = {};
  for (const e of Store.events.filter(e => e.child === childId)) {
    if (e.type === 'error' && e.surah && e.ayah) {
      const k = `${e.surah}:${e.ayah}`;
      if (!items[k]) items[k] = { key: k, surah: e.surah, ayah: e.ayah, page: e.page, first: e.day, last: e.day, count: 0, types: {}, passes: [], target: null };
      const it = items[k]; it.count++; it.last = e.day; it.types[e.etype] = (it.types[e.etype] || 0) + 1;
      if (e.etype === 'jump' && e.target) it.target = e.target;
    }
    if (e.type === 'yellow_pass' && items[`${e.surah}:${e.ayah}`]) {
      const it = items[`${e.surah}:${e.ayah}`];
      if (!it.passes.includes(e.day) && e.day > it.last) it.passes.push(e.day);
    }
    if (e.type === 'error' && e.surah && e.ayah) { items[`${e.surah}:${e.ayah}`].passes = items[`${e.surah}:${e.ayah}`].passes.filter(d => d > e.day); }
  }
  const all = Object.values(items);
  return { active: all.filter(i => i.passes.length < 3), cleared: all.filter(i => i.passes.length >= 3) };
}

function mutashabihat(childId, sinceDay) {
  return Store.events.filter(e => e.child === childId && e.type === 'error' && e.etype === 'jump' && (!sinceDay || e.day >= sinceDay));
}

/* بطاقات */
function cardsFor(childId) {
  const map = {};
  for (const e of Store.events.filter(e => e.child === childId && e.type === 'card')) map[e.key] = e; // الأحدث يغلب
  return map;
}

/* أسبوع العمل الحالي: من السبت */
function weekStartKey(d) { const x = new Date(d); const diff = (x.getDay() + 1) % 7; x.setDate(x.getDate() - diff); return dayKey(x); }

/* النتيجة النافذة: آخر حدث لكل (طفل، صفحة، خطوة، يوم) — إعادة النقر تصحيح لا تكرار */
function effectiveOutcomes(filter) {
  const map = new Map();
  for (const e of Store.events) if (e.type === 'outcome' && (!filter || filter(e))) map.set(`${e.child}|${e.page}|${e.step}|${e.day}|${segKey(e.lines)}`, e);
  return [...map.values()].sort((a, b) => a.ts - b.ts);
}

function segKey(lines) { return lines ? `${lines[0]}-${lines[1]}` : ''; }
function sameSeg(a, b) { return segKey(a) === segKey(b); }
/* مؤشرات الصحة لطفل */
function healthOf(childId) {
  const st = deriveChild(childId);
  const ws = weekStartKey(App.now());
  const gates = effectiveOutcomes(e => e.child === childId && e.day >= ws && e.step === 'gate');
  const gateFails = gates.filter(e => e.result !== 'clean' && e.result !== 'partial').length;
  const exams = effectiveOutcomes(e => e.child === childId && e.step === 'exam' && !e.parent);
  let examGreen = null, examN = 0, examClean = 0, examDay = null;
  if (exams.length) { examDay = exams[exams.length - 1].day; const last = exams.filter(e => e.day === examDay && e.result !== 'partial'); examN = last.length; examClean = last.filter(e => e.result === 'clean').length; examGreen = Math.round(100 * examClean / examN); }
  const evaluated = gates.length > 0 || exams.length > 0;
  let light = evaluated ? 'green' : 'grey';
  if (gateFails >= 2 || (st.far.length && st.maxGap > 12) || (examGreen != null && examGreen < 70)) light = 'red';
  else if (gateFails === 1 || (st.far.length && st.maxGap > 10) || (examGreen != null && examGreen < 85)) light = 'yellow';
  return { st, gateFails, gateN: gates.length, examGreen, examN, examClean, examDay, maxGap: st.maxGap, light, evaluated };
}

/* الجلسة الحالية والقادمة حسب الساعة */
function sessionsFor(role, date) {
  const d = date.getDay();
  return PLAN.filter(s => s.day === d && (!role || role === 'parent' || s.teacher === role)).sort((a, b) => a.start.localeCompare(b.start));
}
function toMin(s) { const [h, m] = s.split(':').map(Number); return h * 60 + m; }
function currentSession(role, date) {
  const list = sessionsFor(role, date); const nowM = date.getHours() * 60 + date.getMinutes();
  let current = null, next = null;
  for (const s of list) {
    if (toMin(s.start) <= nowM && nowM < toMin(s.end)) current = s;
    else if (toMin(s.start) > nowM && !next) next = s;
  }
  return { list, current, next };
}
function sessionKey(s, dayK) { return `${dayK}|${s.start}|${s.kind}|${s.child}`; }
function sessionDone(s, dayK) { return !!sessionStatus(s, dayK); }
/* آخر سجل إنهاء للجلسة (أو null) */
/* حالة الجلسة: آخر إنهاء أو إلغاء، مع كشف التعارض (تسجيل من معلمتين بمعرّفين، أو إلغاء ثم إنهاء متأخر) */
function sessionStatus(s, dayK) {
  const k = sessionKey(s, dayK);
  const ks = Store.ofKey(k);
  const dones = ks.filter(e => e.type === 'session_done');
  const cancels = ks.filter(e => e.type === 'session_cancel');
  if (!dones.length && !cancels.length) return null;
  const last = [...dones, ...cancels].sort((a, b) => a.ts - b.ts).pop();
  const sids = new Set(dones.map(e => e.sid)); const bys = new Set(dones.map(e => e.proxyFor ? e.by : e.by));
  const conflicts = [];
  if (sids.size > 1) conflicts.push(`سُجّلت ${sids.size} مرات بمعرّفين مختلفين (${[...bys].map(b => ROLES[b] ? ROLES[b].name : b).join('، ')})`);
  if (cancels.length && dones.length) conflicts.push('أُلغيت ووصل لها إنهاء أيضاً');
  const st = last.type === 'session_cancel' ? 'cancelled' : (last.status || 'complete');
  return Object.assign({}, last, { status: st, conflicts, dones, cancels });
}
function statusName(st) { return { complete: 'اكتملت', partial: 'بقي جزء', stopped: 'توقفت', cancelled: 'أُلغيت' }[st] || 'اكتملت'; }
/* جلسات اليوم المسجلة بلا تكرار (بالمفتاح لا بعدد السجلات) */
function doneKeys(filter) { return new Set(Store.events.filter(e => e.type === 'session_done' && (!filter || filter(e))).map(e => e.key)); }
/* صفحة الطلاقة الحالية لكريم: آخر حدث في السجل، لا إعداد الجهاز */
function fluencyPage(c) { const l = Store.events.filter(e => e.type === 'fluency_page' && e.child === c); return l.length ? l[l.length - 1].page : (Store.settings['fluency_' + c] || 582); }

/* ===== بطاقات التسليم ===== */
function handoffs(filter) {
  const st = {};
  const upd = {};
  for (const e of Store.events) {
    if (e.type === 'handoff_status') st[e.handoff] = { status: e.status, day: e.day, by: e.by, ts: e.ts };
    if (e.type === 'handoff_update') { (upd[e.handoff] = upd[e.handoff] || []).push(e); if (st[e.handoff] && st[e.handoff].status === 'handled' && st[e.handoff].ts < e.ts) st[e.handoff] = { status: 'reopened', day: e.day, by: e.by, ts: e.ts }; }
  }
  return Store.events.filter(e => e.type === 'handoff').map(h => { const us = upd[h.id] || []; const items = h.items.concat(...us.map(u => u.items.map(i => Object.assign({}, i, { addedDay: u.day })))); return Object.assign({}, h, { items, updates: us.length, state: st[h.id] ? st[h.id].status : 'new', stateDay: st[h.id] ? st[h.id].day : null }); }).filter(h => !filter || filter(h));
}
function handoffFor(key, child) { return Store.events.filter(e => e.type === 'handoff' && e.key === key && e.child === child).pop() || null; }
/* تكرار موضع انتقال معيّن (سورة/آية) وآخر ظهوره */
function jumpStats(child, surah, ayah) {
  const l = Store.events.filter(e => e.type === 'error' && e.child === child && e.etype === 'jump' && e.surah === surah && e.ayah === ayah);
  return { n: l.length, last: l.length ? l[l.length - 1].day : null };
}

/* ===== اللون المقترح من المعايير الكاملة (الوثيقة: أخضر = بلا تلقين، زلة واحدة مصحَّحة ذاتياً، تجويد سليم، إجابة المعنى) ===== */
function suggestColor(child, page, day, lines) {
  const outs = effectiveOutcomes(e => e.child === child && e.day === day && e.page === page && (lines ? sameSeg(e.lines, lines) : true));
  const allErrs = Store.events.filter(e => e.child === child && e.day === day && e.type === 'error' && e.page === page);
  /* مع مقطع محدد: تُحسب أخطاء المقطع نفسه فقط؛ الأخطاء بلا مقطع تُعرض للمراجعة ولا تُنسب لكل المقاطع */
  const errs = lines ? allErrs.filter(e => e.lines && sameSeg(e.lines, lines)) : allErrs;
  const unassigned = lines ? allErrs.filter(e => !e.lines) : [];
  const full = outs.filter(o => o.result !== 'partial');
  const incomplete = outs.length > 0 && full.length === 0;
  const prompts = Math.max(full.reduce((m, o) => Math.max(m, o.prompts != null ? o.prompts : (o.result === 'yellow' ? 1 : o.result === 'red' ? 3 : 0)), 0), errs.filter(e => e.etype === 'prompt').length);
  const hesit = errs.filter(e => e.etype === 'hesitate').length + full.reduce((a, o) => a + (o.selfCorrect || 0), 0);
  const tajweedIssue = full.some(o => o.tajweed === 'issue') || errs.some(e => e.etype === 'tajweed');
  /* شرط المعنى يخص الصفحة الجديدة (البوابة والتسميعات الثلاثة)؛ البعيد والفحص أسئلتهما من البطاقات في خطوة مستقلة */
  const NEW_STEPS = ['gate', 'first', 'second', 'third'];
  const needsMeaning = full.some(o => NEW_STEPS.includes(o.step));
  const meaning = full.some(o => o.meaning === 'support') ? 'support' : full.some(o => o.meaning === 'ok') ? 'ok' : (needsMeaning ? 'untested' : 'n/a');
  const stop = full.some(o => o.result === 'red');
  const reasons = [];
  let color, pending = false;
  if (!outs.length) color = 'none';
  else if (incomplete) { color = 'none'; reasons.push('لم يُسمَّع كاملاً'); }
  else if (stop || prompts >= 3) { color = 'red'; reasons.push(stop ? 'توقف تام أو حكم أحمر' : `${prompts} تلقينات`); }
  else if (prompts >= 1 || hesit > 1 || tajweedIssue || meaning === 'support' || errs.some(e => ['swap', 'jump', 'skip'].includes(e.etype))) {
    color = 'yellow';
    if (prompts) reasons.push(`تلقين ${prompts}`); if (hesit > 1) reasons.push(`${hesit} زلات`); if (tajweedIssue) reasons.push('تجويد'); if (meaning === 'support') reasons.push('المعنى يحتاج دعماً');
    for (const t of ['swap', 'jump', 'skip']) { const n = errs.filter(e => e.etype === t).length; if (n) reasons.push(`${ERROR_TYPES.find(x => x.id === t).short || t} ${n}`); }
  } else if (meaning === 'untested') { color = 'none'; pending = true; reasons.push('الحفظ مستقل — المعنى لم يُختبر — بانتظار الاعتماد'); }
  else color = 'green';
  if (unassigned.length) reasons.push(`${unassigned.length} خطأ بلا مقطع — للمراجعة`);
  return { color, pending, reasons, prompts, hesit, tajweedIssue, meaning, incomplete, n: outs.length, lines: lines || null, unassigned: unassigned.length };
}

/* آخر ورد نظر للطفل (لا يمس طبقات الحفظ ولا تواريخ المراجعة) */
function lastTilawa(c, kind) { const l = Store.events.filter(e => e.type === 'tilawa' && e.child === c && (!kind || e.kind === kind)); return l.length ? l[l.length - 1] : null; }
function juzExams(c, juz) { return Store.events.filter(e => e.type === 'juz_exam' && e.child === c && e.juz === juz); }
