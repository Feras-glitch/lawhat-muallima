/* ===== شاشة الآن، اليوم، والجلسة ===== */
function childName(id) { return id === 'both' ? 'دلال وفرح' : id === 'all' ? 'الثلاثة' : (CHILDREN[id] ? CHILDREN[id].name : id); }
function childrenOf(s) { return s.child === 'both' ? ['dalal', 'farah'] : s.child === 'all' ? CHILD_ORDER : [s.child]; }
function resultPill(r) { return r === 'clean' ? el('span', { class: 'pill g' }, 'مستقل') : r === 'yellow' ? el('span', { class: 'pill y' }, 'بمساعدة') : r === 'red' ? el('span', { class: 'pill r' }, 'توقف') : r === 'partial' ? el('span', { class: 'pill n' }, 'لم يُقيَّم كاملاً') : el('span', { class: 'pill n' }, '—'); }
function resultName(r) { return { clean: 'مستقل', yellow: 'بمساعدة', red: 'توقف / 3 تلقينات+', partial: 'لم يُقيَّم كاملاً' }[r] || r; }
/* مقطع كريم اليوم (الأسطر) لربط التقييم بالمقطع لا بالصفحة */
function karimLines(c, page) {
  if (c !== 'karim') return null;
  const np = Store.events.filter(e => e.type === 'new_page' && e.child === c && e.page === page).pop();
  return np ? [np.linesFrom, np.linesTo] : null;
}
/* ===== أداة التقييم الوصفي: الواقعة أولاً، واللون يُحسب لاحقاً ===== */
function OutcomeCtl(c, page, step, extra, onRecord, compact) {
  const today = todayKey();
  if (!mayRecord('outcome', { step })) return requestBox(c, `تسجيل ${step === 'exam' ? 'الفحص' : 'النتيجة'} ${pageLabel(page)}`);
  const seg = extra && extra.lines ? extra.lines : null;
  const cur = effectiveOutcomes(e => e.child === c && e.page === page && e.step === step && e.day === today && sameSeg(e.lines, seg)).pop() || null;
  const base = () => Object.assign({ type: 'outcome', child: c, page, step }, extra || {}, cur ? { result: cur.result, prompts: cur.prompts, tajweed: cur.tajweed, meaning: cur.meaning, selfCorrect: cur.selfCorrect } : {});
  const rec = (patch) => { const ev = Object.assign(base(), patch); for (const k of Object.keys(ev)) if (ev[k] == null) delete ev[k]; Store.add(ev); if (onRecord) onRecord(ev); UI.rerender(true); if (patch.result === 'yellow' && !cur) { /* تفاصيل المساعدة تُطلب فوراً */ } };
  const mk = (r, cls, t) => el('button', { class: cls + (cur && cur.result === r ? ' on' : ''), style: compact ? 'padding:4px 10px' : '', onclick: () => rec({ result: r, prompts: r === 'clean' ? 0 : r === 'yellow' ? Math.max(1, (cur && cur.prompts) || 1) : r === 'red' ? Math.max(3, (cur && cur.prompts) || 3) : (cur ? cur.prompts : undefined) }) }, t);
  const box = el('div', { class: 'ocl' });
  box.append(el('div', { class: 'btns' }, mk('clean', 'btn-g', compact ? '✓' : 'مستقل'), mk('yellow', 'btn-y', compact ? 'مساعدة' : 'بمساعدة'), mk('red', 'btn-r', compact ? 'توقف' : 'توقف / 3+'), mk('partial', 'ghost', compact ? 'ناقص' : 'لم يُقيَّم كاملاً')));
  if (cur && cur.result !== 'partial') {
    const chip = (on, t, f) => el('button', { class: 'chip' + (on ? ' on' : ''), onclick: f }, t);
    const det = el('div', { class: 'chips' });
    if (cur.result !== 'clean') det.append(el('span', { class: 'muted small' }, 'تلقين: '), ...[1, 2, 3].map(n => chip(cur.prompts === n || (n === 3 && cur.prompts >= 3), n === 3 ? '3+' : String(n), () => rec({ prompts: n, result: n >= 3 ? 'red' : 'yellow' }))));
    det.append(chip(cur.selfCorrect > 0, `زلة مصحَّحة ذاتياً${cur.selfCorrect ? ' ' + cur.selfCorrect : ''}`, () => rec({ selfCorrect: (cur.selfCorrect || 0) + 1 })));
    det.append(chip(cur.tajweed === 'issue', 'تجويد ⚠', () => rec({ tajweed: cur.tajweed === 'issue' ? 'ok' : 'issue' })));
    if (['gate', 'first', 'second', 'third'].includes(step)) det.append(el('span', { class: 'muted small' }, ' المعنى: '), chip(cur.meaning === 'ok', 'تحقق', () => rec({ meaning: 'ok' })), chip(cur.meaning === 'support', 'يحتاج دعماً', () => rec({ meaning: 'support' })), chip(!cur.meaning || cur.meaning === 'untested', 'لم يُختبر', () => rec({ meaning: 'untested' })));
    det.append(el('button', { class: 'chip', style: 'border-color:var(--red);color:var(--red)', onclick: () => errorModal(c, page, seg) }, '+ خطأ بموضعه'));
    box.append(det);
  }
  return box;
}
function pagesText(st, page, lines) { return st && st.id === 'karim' && lines ? `${pageLabel(page)} · الأسطر ${lines[0]}–${lines[1]}` : pageLabel(page); }

Views.now = function () {
  const d = App.now(); const { list, current, next } = currentSession(App.role.id, d);
  const wrap = el('div');
  const active = Store.settings.active && Store.settings.active.dayK === todayKey() && Store.settings.active.role === App.role.id ? Store.settings.active : null;
  if (active) { const s = PLAN.find(x => sessionKey(x, active.dayK) === active.key); if (s) return SessionView(s, active); }
  const noInv = CHILD_ORDER.filter(c => !Store.events.some(e => e.type === 'layer' && e.child === c));
  if (noInv.length && App.role.id !== 'asst') wrap.append(el('div', { class: 'card', style: 'border:2px solid var(--yellow)' }, el('h2', null, 'قبل أول جلسة: الجرد الأولي'), el('p', { class: 'small' }, `لم يُسجَّل المحفوظ الحالي لـ${noInv.map(c => CHILDREN[c].name).join(' و')}. بدونه يقترح البرنامج صفحات خاطئة ولا تعمل حصة البعيد.`), el('button', { class: 'primary', onclick: () => { App.view = 'settings'; UI.rerender(); } }, 'تسجيل الجرد من الإعدادات')));
  if (d.getDay() === 5) wrap.append(el('div', { class: 'card' }, el('h2', null, 'الجمعة إجازة'), el('p', { class: 'muted' }, 'لا تسميع ولا سؤال اليوم. يستأنف البرنامج السبت 7:00.')));
  if (current) {
    const sd = sessionStatus(current, todayKey());
    wrap.append(el('div', { class: 'card' },
      el('div', { class: 'row between' }, el('span', { class: 'now-badge' }, 'الآن'), el('span', { class: 'muted small' }, `${timePair(current.start)} – ${fmtTime12(current.end)}`)),
      el('div', { class: 'big', style: 'margin:6px 0' }, `${childName(current.child)} · ${SESSION_KINDS[current.kind].name}`),
      sd ? el('p', { class: 'muted' }, `سُجّلت هذه الجلسة: ${statusName(sd.status)}.`, ['partial', 'stopped'].includes(sd.status) && current.teacher === App.role.id ? el('button', { class: 'ghost small', style: 'margin-right:8px', onclick: () => startSession(current, sd) }, 'استكمال') : null) : el('button', { class: 'primary', onclick: () => startSession(current) }, 'ابدئي الجلسة')));
  } else if (list.length) {
    wrap.append(el('div', { class: 'card' }, el('h2', null, next ? 'لا جلسة الآن' : 'انتهت جلسات اليوم'), next ? el('p', null, `التالية: ${childName(next.child)} · ${SESSION_KINDS[next.kind].name} في ${timePair(next.start)}`) : el('p', { class: 'muted' }, 'سجّلي أي خطأ أو ملاحظة متأخرة من زر التسجيل الحر.')));
  }
  wrap.append(DayList(list, true));
  if (App.role.id !== 'parent' && d.getDay() !== 5) wrap.append(el('div', { class: 'card' }, el('div', { class: 'row between' }, el('h2', { style: 'margin:0' }, 'يوم غير عادي؟'), el('button', { class: 'ghost small', onclick: () => cancelModal() }, 'إلغاء جلسات اليوم بسبب'))));
  wrap.append(el('div', { class: 'card' }, el('h2', null, 'تسجيل حر'), el('p', { class: 'muted small' }, 'خطأ أو ملاحظة خارج الجلسات.'), el('div', { class: 'btns' }, CHILD_ORDER.map(c => el('button', { onclick: () => errorModal(c) }, `خطأ · ${CHILDREN[c].name}`)), el('button', { class: 'ghost', onclick: () => noteModal() }, 'ملاحظة'), el('button', { class: 'ghost', onclick: undoLast }, '↶ تراجع'))));
  wrap.append(HandoffsCard());
  wrap.append(AlertsCard());
  return wrap;
};

Views.today = function () {
  const d = App.now(); const list = sessionsFor(App.role.id, d);
  return el('div', null, el('div', { class: 'card' }, el('div', { class: 'row between' }, el('h2', { style: 'margin:0' }, `جلسات ${DAY_NAMES[d.getDay()]}`), el('button', { class: 'ghost small', onclick: () => { App.view = 'thursday'; UI.rerender(); } }, '🗓 أدوات الخميس')), el('p', { class: 'muted small' }, 'اضغطي أي جلسة لتسجيلها، في وقتها أو بعده.')), DayList(list, false));
};

function DayList(list, compact) {
  const dayK = todayKey(); const d = App.now(); const nowM = d.getHours() * 60 + d.getMinutes();
  if (!list.length) return el('div');
  return el('div', { class: 'card' }, compact ? el('h2', null, 'جدول اليوم') : null,
    el('table', null, el('tbody', null, list.map(s => {
      const sd = sessionStatus(s, dayK); const done = !!sd; const isNow = toMin(s.start) <= nowM && nowM < toMin(s.end);
      return el('tr', { style: isNow ? 'background:var(--soft)' : '' },
        el('td', { style: 'white-space:nowrap' }, fmtTime12(s.start), sameTz() ? null : el('div', { class: 'muted small' }, localOf(dayK, s.start))),
        el('td', null, el('b', null, childName(s.child)), ' · ', SESSION_KINDS[s.kind].name, App.role.id === 'parent' ? el('span', { class: 'muted small' }, ` (${ROLES[s.teacher].name})`) : null),
        el('td', { style: 'white-space:nowrap' }, done ? el('span', null, el('span', { class: 'pill ' + (sd.status === 'complete' ? 'g' : sd.status === 'partial' ? 'y' : sd.status === 'cancelled' ? 'n' : 'r'), title: sd.reason || '' }, statusName(sd.status)), sd.conflicts.length ? el('span', { class: 'pill r', style: 'margin-right:4px', title: sd.conflicts.join('؛ ') }, '⚠ تعارض') : null, sd.status === 'cancelled' ? el('div', { class: 'muted small' }, sd.reason) : null, ['partial', 'stopped'].includes(sd.status) && s.teacher === App.role.id ? el('button', { class: 'ghost small', style: 'margin-right:4px', onclick: () => startSession(s, sd) }, 'استكمال') : null) : (App.role.id !== 'parent' ? el('button', { class: 'ghost small', onclick: () => startSession(s) }, s.teacher === App.role.id ? 'افتحي' : 'نيابة') : el('span', { class: 'pill n' }, 'لم تُسجَّل'))));
    }))));
}

function saveActive() { Store.saveSettings(); }
function startSession(s, prev, proxy) {
  const dayK = todayKey(); const key = sessionKey(s, dayK);
  if (s.teacher !== App.role.id && !proxy) {
    if (App.role.id === 'parent') { UI.toast('هذه جلسة ' + ROLES[s.teacher].name); return; }
    UI.prompt(`هذه جلسة ${ROLES[s.teacher].name}. أخذها نيابةً؟ اكتبي السبب (يُوثَّق)`, 'سبب النيابة', why => { if (!why) return; startSession(s, prev, { orig: s.teacher, reason: why }); });
    return;
  }
  /* تحذير التزامن: معلمة أخرى فتحت الجلسة نفسها ولم تُنهِها */
  const opens = Store.events.filter(e => e.type === 'session_start' && e.key === key && e.by !== App.role.id);
  const open = opens.find(o => !Store.events.some(e => e.type === 'session_done' && e.sid === o.sid));
  const go = () => {
    const sid = prev && prev.sid ? prev.sid : (Date.now().toString(36) + Math.random().toString(36).slice(2, 6));
    Store.settings.active = { key, dayK, role: App.role.id, sid, started: App.realNow().getTime(), steps: prev ? (prev.steps || []).slice() : [], note: prev ? (prev.note || '') : '', half: false, resumed: !!prev, round: prev ? ((prev.round || 1) + 1) : 1, proxy: proxy || null };
    Store.saveSettings();
    try { Store.add({ type: 'session_start', key, sid, child: s.child === 'both' || s.child === 'all' ? undefined : s.child, kind: s.kind, proxyFor: proxy ? proxy.orig : undefined, reason: proxy ? proxy.reason : undefined }); } catch (e) {}
    UI.rerender();
  };
  if (open) UI.confirm(`فتحت ${ROLES[open.by].name} هذه الجلسة (${chinaHHMM(open.ts)}) ولم تُنهِها بعد. المتابعة قد تسجل الجلسة مرتين. أتابعين؟`, go); else go();
}
function endSession(s, note) {
  const a = Store.settings.active; const kind = SESSION_KINDS[s.kind];
  const remaining = kind.steps.filter(st => !a.steps.includes(st.id));
  let status = remaining.length ? 'partial' : 'complete';
  const opts = el('div', { class: 'btns', style: 'flex-direction:column;align-items:stretch' });
  const reasonSel = el('select', null, ['تعب الطفل', 'انقطاع الاتصال', 'طال التسميع', 'سبب آخر'].map(x => el('option', { value: x }, x)));
  const reasonTxt = el('input', { placeholder: 'تفصيل مختصر (اختياري)' });
  const reasonBox = el('div', { style: 'display:none' }, label('السبب'), reasonSel, reasonTxt);
  const remBox = el('div', { class: 'small muted', style: 'display:none' }, 'الباقي: ' + (remaining.length ? remaining.map(x => x.text).join('؛ ') : 'لا شيء'));
  const mk = (v, t, sub) => { const b = el('button', { class: 'ghost' + (status === v ? ' on' : ''), style: 'text-align:right', onclick: () => { status = v; [...opts.children].forEach(x => x.classList.remove('on')); b.classList.add('on'); reasonBox.style.display = v === 'stopped' ? '' : 'none'; remBox.style.display = v === 'partial' ? '' : 'none'; } }, el('b', null, t), el('div', { class: 'small muted' }, sub)); return b; };
  opts.append(mk('complete', 'اكتملت', remaining.length ? `${remaining.length} خطوة غير مُعلَّمة؛ سيُطلب تأكيد أنها نُفّذت` : 'نُفّذت البنود المطلوبة'),
    mk('partial', 'انتهى الوقت وبقي جزء', 'يُحدَّد الباقي ويظهر لآية؛ لا يُحسب على الطفل'),
    mk('stopped', 'توقفت', 'تعب الطفل أو انقطاع أو غيره'));
  remBox.style.display = status === 'partial' ? '' : 'none';
  const bg = UI.modal('إنهاء الجلسة', el('div', null, opts, remBox, reasonBox), [el('button', { class: 'primary', onclick: () => {
    const reason = status === 'stopped' ? (reasonSel.value + (reasonTxt.value.trim() ? ': ' + reasonTxt.value.trim() : '')) : null;
    const go = () => { bg.remove(); commitEnd(s, a, status, status === 'complete' ? [] : remaining.map(x => x.id), reason, note); };
    if (status === 'complete' && remaining.length) UI.confirm(`تأكيد: نُفّذت فعلاً هذه الخطوات دون تعليمها؟\n${remaining.map(x => '• ' + x.text).join('\n')}\nستُعلَّم منفَّذة. لا تُنشأ أي نتيجة تسميع تلقائياً.`, () => { a.steps = kind.steps.map(x => x.id); a.confirmedSteps = remaining.map(x => x.id); saveActive(); go(); });
    else go();
  } }, 'تسجيل')]);
}
/* تسجيل الإنهاء وبطاقة التسليم بمعرّفات ثابتة: إعادة المحاولة بعد فشل الحفظ لا تكرر ولا تفقد */
async function commitEnd(s, a, status, rem, reason, note) {
  const round = a.round || 1;
  try {
    for (const c of childrenOf(s)) {
      const sdId = `sd_${a.sid}_${c}_${round}`;
      if (!Store.events.some(e => e.id === sdId)) Store.add({ id: sdId, type: 'session_done', key: a.key, sid: a.sid, round, child: c, kind: s.kind, start: s.start, proxyFor: a.proxy ? a.proxy.orig : undefined, proxyReason: a.proxy ? a.proxy.reason : undefined, steps: a.steps, confirmedSteps: a.confirmedSteps || [], status, remaining: rem, reason, minutes: Math.round((App.realNow().getTime() - a.started) / 60000), note: note || '' });
      if (App.role.id === 'asst') { /* بطاقة التسليم من المساعدة، سواء جلستها أو جلسة أخذتها نيابة عن آية */
        const prev = handoffFor(a.key, c);
        const items = handoffItems(s, a, c, status, rem, reason, note);
        if (!prev) { const hoId = `ho_${a.sid}_${c}`; if (!Store.events.some(e => e.id === hoId)) Store.add({ id: hoId, type: 'handoff', child: c, key: a.key, sid: a.sid, kind: s.kind, to: 'aya', items }); }
        else { const upId = `hu_${a.sid}_${c}_${round}`; if (!Store.events.some(e => e.id === upId)) Store.add({ id: upId, type: 'handoff_update', handoff: prev.id, child: c, round, items: [{ k: 'update', text: `استُكملت الجلسة (جولة ${round}): ${statusName(status)}` }].concat(items.filter(i => i.k !== 'done' || true)) }); }
      }
    }
    /* لا تُغلق الجلسة باعتبارها محفوظة قبل ثبوت الكتابة */
    if (!(await Store.durable())) throw new Error(Store.storageError || 'تعذّر الحفظ على الجهاز');
  } catch (e) { a.pendingEnd = { status, rem, reason, note }; saveActive(); UI.toast('لم يكتمل التسجيل: ' + e.message + ' — أعيدي المحاولة من «إنهاء الجلسة»'); UI.rerender(true); return false; }
  Store.settings.active = null; Store.saveSettings(); UI.toast('سُجّلت الجلسة وحُفظت'); UI.rerender(); return true;
}
/* بنود بطاقة التسليم من سجلات هذه الجلسة (بمعرّف الجلسة sid، لا بالتوقيت) */
function handoffItems(s, a, c, status, rem, reason, note) {
  const kind = SESSION_KINDS[s.kind]; const round = a.round || 1;
  const mine = e => e.child === c && e.sid === a.sid && e.by === a.role;
  const errs = Store.events.filter(e => e.type === 'error' && mine(e));
  const outs = effectiveOutcomes(e => e.type === 'outcome' && mine(e));
  const items = [];
  const done = kind.steps.filter(st => a.steps.includes(st.id)).map(st => st.text);
  if (done.length && round === 1) items.push({ k: 'done', text: done.join('؛ ') });
  const bad = outs.filter(o => o.result !== 'clean' && o.result !== 'partial');
  if (bad.length) items.push({ k: 'followup', text: bad.map(o => `${pagesText(deriveChild(c), o.page, o.lines)} ${resultName(o.result)}${o.prompts ? ' (تلقين ' + o.prompts + ')' : ''}`).join('، ') });
  const inc = outs.filter(o => o.result === 'partial');
  if (inc.length) items.push({ k: 'remaining', text: 'لم يُسمَّع كاملاً: ' + inc.map(o => pageLabel(o.page)).join('، ') });
  for (const e of errs) {
    if (e.etype === 'jump') { const js = jumpStats(c, e.surah, e.ayah); items.push({ k: 'jump', text: `انتقال إلى موضع مشابه — يحتاج متابعة: ${SURAH_NAMES[e.surah - 1]} ${e.ayah} ← ${e.target ? SURAH_NAMES[e.target.surah - 1] + ' ' + (e.target.ayah || '') : 'موضع غير مسجل'}`, surah: e.surah, ayah: e.ayah, n: js.n }); }
    else items.push({ k: 'error', text: `${ERROR_TYPES.find(t => t.id === e.etype).name}: ${SURAH_NAMES[e.surah - 1]} ${e.ayah}${e.note ? ' — ' + e.note : ''}` });
  }
  if (status !== 'complete') items.push({ k: 'remaining', text: status === 'stopped' ? `توقفت: ${reason}` : 'بقي: ' + rem.map(id => kind.steps.find(x => x.id === id).text).join('؛ ') });
  if (note) items.push({ k: 'note', text: note });
  return items;
}

/* ===== شاشة الجلسة ===== */
/* هل يستطيع الحساب الحالي تسجيل هذا النوع؟ وإن لا: طلب اعتماد يُرسل لآية عبر ملاحظة تدخل بطاقة التسليم */
function mayRecord(type, extra) { return Store.roleAllows(App.role.id, Object.assign({ type }, extra || {})); }
function requestBox(c, what) {
  const sent = Store.events.some(e => e.type === 'note' && e.child === c && e.day === todayKey() && e.text.startsWith('طلب اعتماد: ' + what));
  return el('div', { class: 'alert' }, `لا يُسمح لحسابك بتسجيل ${what} (حتى في النيابة). `, sent ? el('span', { class: 'pill g' }, 'أُرسل الطلب لآية') : el('button', { class: 'ghost small', onclick: () => UI.prompt(`طلب اعتماد ${what} من آية`, 'ما الذي أُنجز فعلاً؟', t => { if (!t) return; Store.add({ type: 'note', child: c, text: `طلب اعتماد: ${what} — ${t}` }); UI.savedToast('أُرسل الطلب ضمن بطاقة التسليم'); UI.rerender(true); }) }, 'طلب اعتماد من آية'));
}
/* ورد النظر والسماع: تسجيل الصفحات المقروءة فعلاً (قراءة لا تسميع؛ لا تغيّر لوناً ولا تاريخ مراجعة) */
function TilawaBox(c, a, st) {
  const d = deriveChild(c); const kind = st.id === 'listen' ? 'listen' : 'nazar';
  const last = lastTilawa(c, kind);
  const dflt = st.id === 'tomorrow' ? (d.nextNew || 582) : st.id === 'listen' ? (d.todayNew[0] || d.nextNew || 582) : (last ? Math.max(...last.pages) + 1 : (d.nextNew || 582));
  const k = `til_${st.id}_${c}`; const sv = a[k] || {};
  const from = el('input', { type: 'number', min: 1, max: 604, value: sv.from || dflt, style: 'width:80px', oninput: e => { a[k] = Object.assign(a[k] || {}, { from: e.target.value }); saveActive(); } });
  const to = el('input', { type: 'number', min: 1, max: 604, value: sv.to || (st.id === 'listen' && st.text.includes('الخمس') ? Math.min(604, dflt + 4) : dflt), style: 'width:80px', oninput: e => { a[k] = Object.assign(a[k] || {}, { to: e.target.value }); saveActive(); } });
  const times = el('input', { type: 'number', min: 1, max: 10, value: sv.times || (st.text.includes('3 مرات') ? 3 : st.text.includes('مرتين') ? 2 : 1), style: 'width:60px', oninput: e => { a[k] = Object.assign(a[k] || {}, { times: e.target.value }); saveActive(); } });
  const todayRec = Store.events.filter(e => e.type === 'tilawa' && e.child === c && e.day === todayKey() && e.kind === kind);
  const box = el('div', { class: 'small' }, el('div', { class: 'muted' }, `${CHILDREN[c].name} · ${kind === 'listen' ? 'سماع' : 'قراءة نظراً'} — ${last ? `آخر مرة: ص${Math.min(...last.pages)}–${Math.max(...last.pages)} (${fmtDay(last.day)})` : 'لا تسجيل سابق'}`),
    el('div', { class: 'row' }, 'من ص', from, 'إلى ص', to, 'مرات', times, el('button', { class: 'btn-g', onclick: () => { const f = Number(from.value), t = Number(to.value); if (!(f >= 1 && t <= 604 && f <= t && t - f < 30)) { UI.toast('نطاق غير صالح (حتى 30 صفحة)'); return; } const pages = []; for (let p = f; p <= t; p++) pages.push(p); Store.add({ type: 'tilawa', child: c, pages, kind, times: Number(times.value) || 1, step: st.id }); if (!a.steps.includes(st.id)) { a.steps.push(st.id); saveActive(); } UI.savedToast('سُجّلت القراءة'); UI.rerender(true); } }, 'تسجيل')));
  if (todayRec.length) box.append(el('div', { class: 'muted' }, 'اليوم: ' + todayRec.map(r => `ص${Math.min(...r.pages)}–${Math.max(...r.pages)} ×${r.times || 1}`).join('، ')));
  return box;
}
/* خطوة لا ينطبق عليها شيء اليوم (مثل بوابة الأمس في أول يوم) تُعلَّم «لا ينطبق» تلقائياً */
function stepNA(s, st) {
  const kids = childrenOf(s);
  if (st.outcome === 'gate' || st.outcome === 'awael') return kids.every(c => !lastNewFor(c, true));
  if (st.outcome === 'near') return kids.every(c => deriveChild(c).near.length === 0);
  if (st.outcome === 'far' || st.outcome === 'exam') return kids.every(c => deriveChild(c).far.length === 0);
  if (st.outcome === 'yellow') return kids.every(c => yellowList(c).active.length === 0);
  if (st.mutashabih) return kids.every(c => mutashabihat(c, weekStartKey(App.now())).length === 0);
  return false;
}
function SessionView(s, a) {
  const kind = SESSION_KINDS[s.kind]; const kids = childrenOf(s);
  const wrap = el('div');
  a.na = a.na || [];
  for (const st of kind.steps) if (!a.steps.includes(st.id) && !a.na.includes(st.id) && stepNA(s, st)) { a.na.push(st.id); a.steps.push(st.id); }
  if (a.na.length) saveActive();
  const curIdx = a.cur != null && a.cur < kind.steps.length ? a.cur : Math.max(0, kind.steps.findIndex(st => !a.steps.includes(st.id)));
  const cur = kind.steps[curIdx] || kind.steps[kind.steps.length - 1];
  /* بطاقة الرأس: الطفل والجلسة، المطلوب، آخر ملاحظة، قرار آية الجاري */
  const head = el('div', { class: 'card' },
    a.pendingEnd ? el('div', { class: 'alert red' }, 'لم يكتمل تسجيل الإنهاء. ', el('button', { class: 'btn-r', onclick: async () => { await Store.flush(); commitEnd(s, a, a.pendingEnd.status, a.pendingEnd.rem, a.pendingEnd.reason, a.pendingEnd.note); } }, 'إعادة محاولة التسجيل')) : null,
    a.resumed ? el('div', { class: 'alert small' }, `استكمال جلسة سبق إنهاؤها (جولة ${a.round}).`) : null,
    a.proxy ? el('div', { class: 'alert small' }, `نيابةً عن ${ROLES[a.proxy.orig].name}: ${a.proxy.reason}. صلاحيات الاعتماد والقرارات تبقى بحسب حسابك.`) : null,
    el('div', { class: 'row between' }, el('span', { class: 'now-badge' }, 'جلسة جارية'), el('span', { class: 'muted small' }, `${timePair(s.start)} – ${fmtTime12(s.end)}`)),
    el('div', { class: 'big', style: 'margin:6px 0' }, `${childName(s.child)} · ${kind.name}`),
    Countdown(s),
    ContextBox(s));
  for (const c of kids) {
    const d = deriveChild(c);
    const dec = [];
    if (d.paused) dec.push('الجديد متوقف'); if (d.reduced) dec.push('المقدار نصف صفحة');
    const rep = Store.events.filter(e => e.type === 'decision' && e.child === c && e.kind === 'repair' && e.day === todayKey()).pop(); if (rep) dec.push('صباح إصلاح اليوم');
    if (dec.length) head.append(el('div', { class: 'alert small' }, el('b', null, `قرار آية الجاري · ${CHILDREN[c].name}: `), dec.join(' · ')));
    const ln = lastNote(c); if (ln) { const full = el('div', { class: 'small', style: 'display:none;white-space:pre-wrap' }, ln.details || ln.text); head.append(el('div', { class: 'small muted' }, el('b', null, `آخر ملاحظة مهمة · ${CHILDREN[c].name}: `), ln.text.length > 70 ? ln.text.slice(0, 70) + '…' : ln.text, ln.details || ln.text.length > 70 ? el('button', { class: 'ghost small', style: 'margin-right:6px', onclick: () => { full.style.display = full.style.display === 'none' ? '' : 'none'; } }, 'التفاصيل') : null), full); }
  }
  head.append(el('div', { class: 'row between', style: 'margin-top:8px' }, el('span', { class: 'small' }, el('b', null, 'الخطوة الحالية: '), cur.text), el('button', { class: 'ghost small', onclick: () => openPresent(s) }, '🖥 عرض')));
  wrap.append(head);
  /* الخطوات: الحالية مفتوحة، والباقي سطر واحد قابل للفتح */
  const steps = el('ul', { class: 'steps' });
  kind.steps.forEach((st, i) => {
    const done = a.steps.includes(st.id); const na = a.na && a.na.includes(st.id); const open = a.all || i === curIdx;
    const li = el('li', { class: (done ? 'done' : '') + (open ? ' open' : ' closed') },
      el('div', { class: 'chk', onclick: () => { if (done) a.steps = a.steps.filter(x => x !== st.id); else { a.steps.push(st.id); a.cur = Math.min(kind.steps.length - 1, i + 1); } saveActive(); UI.rerender(true); } }, done ? '✓' : ''),
      el('div', { class: 'body' }, el('div', { class: 'row between', style: 'cursor:pointer', onclick: () => { a.cur = i; saveActive(); UI.rerender(true); } }, el('span', null, open ? el('b', null, st.text) : st.text, st.min ? el('span', { class: 'min' }, ` · ${st.min} د`) : null, na ? el('span', { class: 'pill n', style: 'margin-right:6px' }, 'لا ينطبق اليوم') : null), el('span', { class: 'muted small' }, open ? '' : '▾')),
        open ? StepControls(s, st, a) : null,
        open ? el('div', { class: 'small muted', style: 'margin-top:6px' }, 'الإجراء التالي: ', nextAction(st, done, i, kind)) : null));
    steps.append(li);
  });
  wrap.append(el('div', { class: 'card' }, el('div', { class: 'row between' }, el('span', { class: 'muted small' }, 'الخطوات'), el('button', { class: 'ghost small', onclick: () => { a.all = !a.all; saveActive(); UI.rerender(true); } }, a.all ? 'الخطوة الحالية فقط' : 'فتح جميع الخطوات')), steps));
  const note = el('textarea', { placeholder: 'ملاحظة على الجلسة (اختياري)', oninput: e => { a.note = e.target.value; saveActive(); } }); note.value = a.note || '';
  wrap.append(el('div', { class: 'card' }, el('div', { class: 'btns' }, kids.map(c => el('button', { class: 'btn-r', onclick: () => { const pg = contextPage(s, c); errorModal(c, pg, c === 'karim' ? (['far', 'cards'].includes((SESSION_KINDS[s.kind].steps[a.cur || 0] || {}).id) ? null : undefined) : undefined); } }, `تسجيل خطأ · ${CHILDREN[c].name}`))), note,
    el('div', { class: 'btns' }, el('button', { class: 'primary', onclick: () => endSession(s, note.value) }, 'إنهاء الجلسة'), el('button', { class: 'ghost', onclick: undoLast }, '↶ تراجع عن آخر تسجيل'), el('button', { class: 'ghost', onclick: () => UI.confirm('إلغاء الجلسة دون تسجيل؟ تبقى الأخطاء والنتائج التي سُجّلت.', () => { Store.settings.active = null; Store.saveSettings(); UI.rerender(); }) }, 'إغلاق بلا تسجيل'))));
  return wrap;
}
function nextAction(st, done, i, kind) {
  if (done) return i + 1 < kind.steps.length ? `افتحي «${kind.steps[i + 1].text}»` : 'اضغطي «إنهاء الجلسة»';
  if (st.outcome) return 'سجّلي الواقعة (مستقل / بمساعدة / توقف / لم يُقيَّم كاملاً)؛ اللون تحسبه اللوحة وتعتمده آية';
  if (st.timer) return mayRecord('new_page') ? 'ابدئي المؤقت، وعند انتهاء الطفل اضغطي «تم الحفظ»' : 'لقّني الصفحة ثم أرسلي طلب اعتماد الحفظ لآية';
  if (st.color) return 'اعتمدي لون كل صفحة';
  return 'علّمي الخطوة ✓ عند إتمامها';
}
/* آخر ملاحظة مهمة للطفل بترتيب الأهمية: متشابه مفتوح، ثم متابعة غير معالجة، ثم باقٍ، ثم آخر خطأ/ملاحظة */
function lastNote(c) {
  const hs = handoffs(x => x.child === c && x.state !== 'handled');
  for (const k of ['jump', 'followup', 'remaining']) {
    for (const h of hs.slice().reverse()) { const it = h.items.find(i => i.k === k); if (it) return { text: `${it.text} (${fmtDay(h.day)})`, details: h.items.map(i => '• ' + i.text).join('\n') }; }
  }
  const e = Store.events.filter(e => e.child === c && (e.type === 'error' || e.type === 'note')).pop();
  if (!e) return null;
  if (e.type === 'note') return { text: `${e.text} (${fmtDay(e.day)})` };
  return { text: `${ERROR_TYPES.find(t => t.id === e.etype).name} في ${SURAH_NAMES[e.surah - 1]} ${e.ayah} (${fmtDay(e.day)})` };
}


function Countdown(s) {
  const d = App.now(); const nowM = d.getHours() * 60 + d.getMinutes() + d.getSeconds() / 60; const a = toMin(s.start), b = toMin(s.end);
  const total = b - a; const left = Math.max(0, b - nowM); const pct = Math.min(100, Math.max(0, 100 * (nowM - a) / total));
  const txt = nowM < a ? `تبدأ بعد ${Math.ceil(a - nowM)} د` : nowM >= b ? 'انتهى وقت الجلسة؛ سجّلي ما بقي ثم «تمت الجلسة»' : `بقي ${Math.ceil(left)} د من ${total}`;
  return el('div', { class: 'small', style: 'margin-top:6px' }, el('div', { style: 'height:6px;border-radius:4px;background:#eee;overflow:hidden' }, el('div', { style: `height:100%;width:${pct}%;background:${left <= 2 && nowM < b ? 'var(--red)' : 'var(--brand)'}` })), el('div', { class: 'muted' }, txt));
}

function contextPage(s, c) {
  const st = deriveChild(c);
  if (['gate_new', 'karim_new'].includes(s.kind)) return st.nextNew;
  if (['near_review', 'thu_yellow'].includes(s.kind)) { const g = lastNewFor(c, true); return g ? g.page : st.nextNew; }
  if (st.todayNew.length) return st.todayNew[st.todayNew.length - 1];
  const g = lastNewFor(c, false); return g ? g.page : st.nextNew;
}

function ContextBox(s) {
  const box = el('div', { class: 'small', style: 'margin-top:8px' });
  for (const c of childrenOf(s)) {
    const st = deriveChild(c); const gate = lastNewFor(c, true);
    const lines = [];
    if (['gate_new', 'karim_new'].includes(s.kind)) {
      lines.push(`بوابة الأمس: ${gate ? pagesText(st, gate.page, gate.lines) : 'لا صفحة أمس (أول يوم)'}`);
      lines.push(`الجديد اليوم: ${st.nextNew ? pagesText(st, st.nextNew, st.nextLines) : 'لم يُحدَّد'}`);
    }
    if (s.kind === 'near_review') { lines.push(`أوائل الآيات لصفحة: ${gate ? pageLabel(gate.page) : '—'}`); lines.push(`القريب (${st.near.length} صفحة): ${st.near.length ? st.near.join('، ') : 'لا صفحات بعد'}`); }
    if (['noon', 'karim_asr'].includes(s.kind)) { lines.push(`صفحة اليوم: ${st.todayNew.length ? pageLabel(st.todayNew[st.todayNew.length - 1]) : 'لم تُسجَّل صباحاً'}`); lines.push(`حصة البعيد (${st.quota}): ${st.todayFar.length ? st.todayFar.join('، ') : 'لا بعيد بعد'}`); }
    if (['third', 'karim_evening', 'circle'].includes(s.kind)) { lines.push(`صفحة اليوم: ${st.todayNew.length ? pageLabel(st.todayNew[st.todayNew.length - 1]) : '—'}`); if (s.kind !== 'third') lines.push(`صفحة الغد: ${st.nextNew ? pagesText(st, st.nextNew, st.nextLines) : '—'}`); }
    if (s.kind === 'fluency') lines.push(`صفحة الطلاقة الحالية: ${fluencyPage(c)}`);
    if (s.kind.startsWith('thu')) lines.push(`المحفوظ البعيد: ${st.far.length} صفحة · القريب: ${st.near.length}`);
    if (lines.length) box.append(el('div', null, el('b', null, CHILDREN[c].name + ': '), lines.join(' · ')));
  }
  return box;
}

/* أدوات كل خطوة */
function StepControls(s, st, a) {
  const kids = childrenOf(s); const box = el('div');
  const mark = () => { if (!a.steps.includes(st.id)) { a.steps.push(st.id); saveActive(); } };
  const outcomeBtns = (c, page, step, extra) => OutcomeCtl(c, page, step, extra, mark, false);
  if (st.outcome === 'gate') for (const c of kids) { const g = lastNewFor(c, true); if (!g) { box.append(el('div', { class: 'muted small' }, 'لا صفحة أمس.')); continue; } box.append(el('div', { class: 'small' }, pagesText(deriveChild(c), g.page, g.lines)), outcomeBtns(c, g.page, 'gate', c === 'karim' && g.lines ? { lines: g.lines } : null)); }
  if (['first', 'second', 'third'].includes(st.outcome)) for (const c of kids) { const d = deriveChild(c); const p = d.todayNew.length ? d.todayNew[d.todayNew.length - 1] : null; if (!p) { box.append(el('div', { class: 'muted small' }, 'لم تُسجَّل صفحة اليوم بعد (تُسجَّل في خطوة الحفظ).')); continue; } const kl = karimLines(c, p); box.append(el('div', { class: 'small' }, pagesText(d, p, kl)), outcomeBtns(c, p, st.outcome, kl ? { lines: kl } : null)); }
  if (st.outcome === 'awael') for (const c of kids) { const g = lastNewFor(c, true); if (g) box.append(outcomeBtns(c, g.page, 'awael')); }
  if (st.outcome === 'near') for (const c of kids) box.append(PageListOutcome(c, deriveChild(c).near, 'near', a, st));
  if (st.outcome === 'far') for (const c of kids) box.append(PageListOutcome(c, deriveChild(c).todayFar, 'far', a, st));
  if (st.outcome === 'week') for (const c of kids) { const ws = weekStartKey(App.now()); const pages = [...new Set(Store.events.filter(e => e.type === 'new_page' && e.child === c && e.day >= ws).map(e => e.page))]; box.append(PageListOutcome(c, pages, 'week', a, st)); }
  if (st.outcome === 'exam') for (const c of kids) box.append(ExamBox(c, a, st, s));
  if (st.outcome === 'yellow') for (const c of kids) box.append(YellowBox(c, a, st));
  if (st.outcome === 'cards') for (const c of kids) box.append(CardsBox(c));
  if (st.outcome === 'fluency') for (const c of kids) box.append(FluencyBox(c, a, st));
  if (st.timer) for (const c of kids) box.append(MemorizeBox(c, a, st));
  if (['tilawa', 'tomorrow', 'listen'].includes(st.id)) for (const c of kids) box.append(TilawaBox(c, a, st));
  if (st.card) for (const c of kids) { const d = deriveChild(c); if (d.nextNew) box.append(el('button', { class: 'ghost', onclick: () => cardModal(c, d.nextNew) }, `بطاقة ${CHILDREN[c].name}: ${pageLabel(d.nextNew)}`)); }
  if (st.color) box.append(ColorBox());
  if (st.mutashabih) for (const c of kids) box.append(MutashabihBox(c));
  if (st.lottery && s.kind === 'thu_karim') { /* القرعة تُدار في ExamBox */ }
  return box;
}

function PageListOutcome(c, pages, step, a, st) {
  if (!pages.length) return el('div', { class: 'muted small' }, 'لا صفحات.');
  const today = todayKey();
  const wrap = el('div', { class: 'small' }, el('div', { class: 'row between' }, el('b', null, CHILDREN[c].name), el('button', { class: 'btn-g', onclick: () => { for (const p of pages) { const has = Store.events.some(e => e.type === 'outcome' && e.child === c && e.page === p && e.step === step && e.day === today); if (!has) Store.add({ type: 'outcome', child: c, page: p, step, result: 'clean' }); } if (!a.steps.includes(st.id)) { a.steps.push(st.id); saveActive(); } UI.rerender(true); } }, 'الباقي مستقل')));
  const list = el('div');
  for (const p of pages) {
    list.append(el('div', { class: 'ayahrow', style: 'flex-wrap:wrap' }, el('span', null, pageLabel(p)), OutcomeCtl(c, p, step, null, ev => { if (ev.result === 'red' || (ev.result === 'yellow' && ev.prompts === 1 && !Store.events.some(x => x.type === 'error' && x.child === c && x.page === p && x.day === today))) errorModal(c, p, c === 'karim' ? null : undefined); }, true)));
  }
  wrap.append(list); return wrap;
}

function ExamBox(c, a, st, s) {
  const d = deriveChild(c); const key = 'draw_' + c;
  const box = el('div', { class: 'small' });
  if (!mayRecord('outcome', { step: 'exam' })) return requestBox(c, 'فحص الخميس');
  if (!a[key]) {
    box.append(el('button', { class: 'primary', onclick: () => {
      let pool = d.far.slice(); const pick = [];
      if (c === 'karim') { const surahs = [...new Set(pool.flatMap(p => surahsOfPage(p)))]; for (let i = 0; i < 2 && surahs.length; i++) { const sIdx = Math.floor(Math.random() * surahs.length); const sNum = surahs.splice(sIdx, 1)[0]; for (const p of pool) if (surahsOfPage(p).includes(sNum) && !pick.includes(p)) pick.push(p); } }
      else for (let i = 0; i < 5 && pool.length; i++) pick.push(pool.splice(Math.floor(Math.random() * pool.length), 1)[0]);
      a[key] = pick.sort((x, y) => x - y); saveActive(); UI.rerender(true);
    } }, c === 'karim' ? 'قرعة سورتَين' : 'قرعة 5 صفحات'));
    if (!d.far.length) box.append(el('div', { class: 'muted' }, 'لا محفوظ بعيد بعد.'));
    return box;
  }
  box.append(el('div', { class: 'muted' }, 'ابدئي بعض الصفحات من وسطها.'), PageListOutcome(c, a[key], 'exam', a, st));
  return box;
}

function YellowBox(c, a, st) {
  const y = yellowList(c); const box = el('div', { class: 'small' });
  if (!y.active.length) return el('div', { class: 'muted small' }, `لا آيات صفراء لـ${CHILDREN[c].name}.`);
  box.append(el('b', null, `${CHILDREN[c].name}: ${y.active.length} آية`));
  for (const it of y.active) {
    box.append(el('div', { class: 'ayahrow' }, el('span', null, `${SURAH_NAMES[it.surah - 1]} ${it.ayah} · ص${it.page}`, el('span', { class: 'muted' }, ` · سالمة ${it.passes.length}/3`)),
      el('span', { class: 'row' }, el('button', { class: 'btn-g', style: 'padding:4px 10px', onclick: () => { Store.add({ type: 'yellow_pass', child: c, surah: it.surah, ayah: it.ayah, page: it.page }); UI.rerender(true); } }, '✓'), el('button', { class: 'btn-r', style: 'padding:4px 10px', onclick: () => { Store.add({ type: 'error', child: c, page: it.page, surah: it.surah, ayah: it.ayah, etype: 'prompt', step: 'yellow' }); UI.toast('سُجّل الخطأ'); UI.rerender(true); } }, '✗'))));
  }
  return box;
}

function CardsBox(c) {
  const d = deriveChild(c); const cards = cardsFor(c); const box = el('div', { class: 'small' });
  const pages = c === 'karim' ? d.todayFar : d.todayFar;
  let n = 0;
  for (const p of pages) { const key = c === 'karim' ? ('s' + (surahsOfPage(p)[0])) : ('p' + p); const card = cards[key]; if (card) { n++; box.append(el('details', null, el('summary', null, (c === 'karim' ? SURAH_NAMES[surahsOfPage(p)[0] - 1] : pageLabel(p))), el('div', { html: cardHtml(card) }))); } }
  if (!n) box.append(el('div', { class: 'muted' }, 'لا بطاقات لصفحات اليوم بعد؛ تُكتب مساءً من آية.'));
  return box;
}
function cardHtml(card) {
  if (card.kind === 'surah') return `<div>القصة: ${esc(card.story)}</div><div>الغريب: ${esc(card.words)}</div><div>موقف: ${esc(card.situation)}</div><div>حركة/صورة: ${esc(card.gesture)}</div>`;
  return `<div>١ غريب: ${esc(card.q1)}</div><div>٢ موضوع: ${esc(card.q2)}</div><div>٣ موضع: ${esc(card.q3)}</div><div>٤ تدبر: ${esc(card.q4)}</div>`;
}

function FluencyBox(c, a, st) {
  const page = fluencyPage(c);
  const sec = el('input', { type: 'number', placeholder: 'ثوانٍ', style: 'width:110px', value: a['sec_' + c] || '', oninput: e => { a['sec_' + c] = e.target.value; saveActive(); } });
  return el('div', { class: 'small row' }, el('span', null, pageLabel(page)), sec, el('button', { onclick: () => { const v = Number(sec.value); if (!v) return; Store.add({ type: 'fluency_time', child: c, page, seconds: v }); if (v < 180) { Store.add({ type: 'fluency_page', child: c, page: page + 1, why: 'نزلت تحت 3 دقائق' }); UI.toast('نزلت تحت 3 دقائق؛ الصفحة التالية غداً'); } if (!a.steps.includes(st.id)) { a.steps.push(st.id); saveActive(); } UI.rerender(true); } }, 'تسجيل الزمن'), el('button', { class: 'ghost', onclick: () => UI.prompt('رقم صفحة الطلاقة', 'رقم الصفحة', v => { const n = Number(v); if (n >= 1 && n <= 604) { Store.add({ type: 'fluency_page', child: c, page: n, why: 'تغيير يدوي' }); UI.rerender(true); } }, String(page)) }, 'تغيير الصفحة'));
}

function MemorizeBox(c, a, st) {
  const d = deriveChild(c); const box = el('div', { class: 'small' });
  if (!d.nextNew) return el('div', { class: 'alert small' }, c === 'karim' ? 'اكتمل المسار الحالي (عمّ ← تبارك ← قد سمع). يحدد ولي الأمر وآية المسار التالي قبل أي حفظ جديد.' : 'اكتمل المسار المبرمج. يحدد ولي الأمر وآية المسار التالي.');
  if (!mayRecord('new_page')) return el('div', { class: 'small' }, el('div', null, `الجديد: ${pagesText(d, d.nextNew, d.nextLines)}`), requestBox(c, `حفظ ${pagesText(d, d.nextNew, d.nextLines)}`));
  const already = d.todayNew.includes(d.nextNew) || (d.todayNew.length && c !== 'karim');
  const tKey = 'timer_' + c;
  const timerEl = el('span', { class: 'timer' }, a[tKey] ? fmtDur(Date.now() - a[tKey]) : '00:00');
  if (a[tKey]) setTimeout(function tick() { if (!document.body.contains(timerEl) || !a[tKey]) return; timerEl.textContent = fmtDur(Date.now() - a[tKey]); setTimeout(tick, 1000); }, 1000);
  /* المعايرة: نصف صفحة افتراضياً في أول 10 أيام حفظ لدلال وفرح، ويمكن تغييره */
  const daysSoFar = c === 'karim' ? 99 : new Set(Store.events.filter(e => e.type === 'new_page' && e.child === c).map(e => e.day)).size;
  if (a['half_' + c] == null) a['half_' + c] = daysSoFar < 10;
  const half = el('input', { type: 'checkbox', onchange: e => { a['half_' + c] = e.target.checked; saveActive(); } }); half.checked = !!a['half_' + c];
  const linesIn = el('input', { type: 'number', min: d.nextLines[0] + 3, max: 15, value: a['lines_' + c] || d.nextLines[1], style: 'width:70px', onchange: e => { a['lines_' + c] = Number(e.target.value); saveActive(); } });
  box.append(el('div', { class: 'row between' }, el('span', null, `الجديد: ${pagesText(d, d.nextNew, c === 'karim' ? [d.nextLines[0], Number(linesIn.value)] : d.nextLines)}`), timerEl));
  if (c === 'karim') box.append(el('div', { class: 'row small' }, 'إلى السطر ', linesIn, el('span', { class: 'muted' }, ' (4 أسطر على الأقل؛ تزيد آية عند الاستطاعة)')));
  if (c !== 'karim' && daysSoFar < 10) box.append(el('div', { class: 'muted' }, `أيام المعايرة: ${daysSoFar + 1} من 10 — نصف صفحة افتراضياً.`));
  if (d.paused && !a['override_' + c]) {
    box.append(el('div', { class: 'alert red' }, 'قرار آية: الجديد متوقف لهذا الطفل. تُسمَّع المراجعة فقط.'), App.can('canDecide') ? el('button', { class: 'ghost', onclick: () => UI.prompt('سبب تجاوز قرار التوقف اليوم', 'السبب (يُوثَّق)', why => { if (!why) return; Store.add({ type: 'decision', child: c, kind: 'override', text: why }); a['override_' + c] = true; saveActive(); UI.rerender(true); }) }, 'تجاوز اليوم بسبب مسجّل') : null);
    return box;
  }
  if (d.reduced) box.append(el('div', { class: 'alert' }, 'قرار آية: المقدار مخفَّض إلى نصف صفحة حتى قرار «استعادة المقدار».'));
  const partial = d.pages[d.nextNew].linesDone > 0;
  if (!already) box.append(el('div', { class: 'btns' },
    !a[tKey] ? el('button', { onclick: () => { a[tKey] = Date.now(); saveActive(); UI.rerender(true); } }, 'بدء المؤقت') : null,
    el('button', { class: 'primary', onclick: () => {
      const mins = a[tKey] ? Math.round((Date.now() - a[tKey]) / 60000) : null;
      let lines = d.nextLines.slice();
      if (c !== 'karim' && !partial && (half.checked || d.reduced)) lines = [1, 8];
      if (c === 'karim') { const to = Math.min(15, Math.max(d.nextLines[0] + 3, Number(linesIn.value) || d.nextLines[1])); lines = [d.nextLines[0], to]; }
      Store.add({ type: 'new_page', child: c, page: d.nextNew, linesFrom: lines[0], linesTo: lines[1], minutes: mins });
      a[tKey] = null; if (!a.steps.includes(st.id)) a.steps.push(st.id); saveActive(); UI.savedToast('سُجّل الحفظ الجديد وحُفظ'); UI.rerender(true);
    } }, partial ? 'تم إكمال الصفحة' : 'تم الحفظ'),
    c !== 'karim' && !partial && !d.reduced ? el('label', { class: 'row', style: 'margin:0' }, half, ' نصف صفحة (المعايرة)') : null));
  else box.append(el('div', { class: 'muted' }, 'سُجّل حفظ اليوم.'));
  return box;
}
function fmtDur(ms) { const s = Math.floor(ms / 1000); return String(Math.floor(s / 60)).padStart(2, '0') + ':' + String(s % 60).padStart(2, '0'); }

function ColorBox() {
  if (!App.can('canColor')) return el('div', { class: 'muted small' }, 'التلوين لآية وحدها.');
  const today = todayKey(); const box = el('div', { class: 'small' });
  for (const c of CHILD_ORDER) {
    const pages = [...new Set(Store.events.filter(e => e.child === c && e.day === today && (e.type === 'outcome' || e.type === 'error' || e.type === 'new_page')).map(e => e.page))].sort((a, b) => a - b);
    if (!pages.length) continue;
    box.append(el('b', null, CHILDREN[c].name));
    for (const p of pages) {
      /* كريم: لون لكل مقطع سُمّع فعلاً؛ الكبيران: الصفحة */
      const segs = c === 'karim' ? [...new Set(effectiveOutcomes(e => e.child === c && e.day === today && e.page === p).map(e => segKey(e.lines)))].map(k => k ? k.split('-').map(Number) : null) : [null];
      for (const kl of segs) {
      const sg = suggestColor(c, p, today, kl);
      const cur = Store.events.filter(e => e.child === c && e.type === 'color' && e.page === p && e.day === today && sameSeg(e.lines, kl)).pop();
      const mk = (col, cls, t) => el('button', { class: cls + ((cur ? cur.color : null) === col ? ' on' : ''), style: 'padding:4px 10px', onclick: () => {
        const ev = { type: 'color', child: c, page: p, color: col, suggested: sg.pending ? 'pending' : sg.color }; if (kl) ev.lines = kl;
        const need = (col !== sg.color && sg.color !== 'none') ? `اللون المقترح ${colorName(sg.color)}؛ سبب الاعتماد المختلف` : (sg.pending && col === 'green') ? 'المعنى لم يُختبر؛ سبب اعتماد الأخضر رغم ذلك' : null;
        if (need) UI.prompt(need, 'السبب (يُوثَّق)', why => { if (!why) return; ev.why = why; Store.add(ev); UI.rerender(true); });
        else { Store.add(ev); UI.rerender(true); } } }, t);
      box.append(el('div', { class: 'ayahrow', style: 'flex-wrap:wrap' }, el('span', null, pagesText(deriveChild(c), p, kl), el('span', { class: 'muted' }, ` · ${sg.n} تسميع · مقترح: `), sg.pending ? el('span', { class: 'pill n', style: 'border:1px dashed var(--brand)' }, 'بانتظار الاعتماد') : sg.color === 'none' ? el('span', { class: 'pill n' }, sg.incomplete ? 'غير مكتمل' : 'لم يُقيَّم') : el('span', { class: 'pill ' + { green: 'g', yellow: 'y', red: 'r' }[sg.color] }, colorName(sg.color)), sg.reasons.length ? el('span', { class: 'muted' }, ` (${sg.reasons.join('، ')})`) : null, cur && cur.why ? el('span', { class: 'muted' }, ` · سبب: ${cur.why}`) : null), el('span', { class: 'row' }, mk('green', 'btn-g', 'أخضر'), mk('yellow', 'btn-y', 'أصفر'), mk('red', 'btn-r', 'أحمر'))));
      }
    }
  }
  if (!box.children.length) box.append(el('div', { class: 'muted' }, 'لا تسميعات اليوم.'));
  return box;
}
function colorName(c) { return { green: 'أخضر', yellow: 'أصفر', red: 'أحمر', none: 'لم يُقيَّم' }[c] || c; }

/* ===== التراجع عن آخر تسجيل (يبقى أثر التصحيح في السجل) ===== */
function undoLast() {
  const mine = Store.events.filter(e => Store.canUndo(App.role.id, e) && e.by === App.role.id && e.day === todayKey() && !['undo', 'session_done', 'handoff', 'handoff_update', 'handoff_status', 'layer'].includes(e.type));
  const last = mine[mine.length - 1];
  if (!last) { UI.toast('لا تسجيل للتراجع عنه اليوم'); return; }
  UI.confirm(`التراجع عن: ${eventText(last)}؟ يُلغى أثره في الحسابات ويبقى أثر التصحيح في السجل.`, () => { Store.add({ type: 'undo', target: last.id, child: last.child || undefined, reason: 'تراجع ' + ROLES[App.role.id].name }); UI.savedToast('تم التراجع'); UI.rerender(true); });
}
function MutashabihBox(c) {
  const ws = weekStartKey(App.now()); const list = mutashabihat(c, ws); const box = el('div', { class: 'small' });
  if (!list.length) return el('div', { class: 'muted small' }, `لا متشابهات مسجلة هذا الأسبوع لـ${CHILDREN[c].name}.`);
  box.append(el('b', null, CHILDREN[c].name));
  for (const e of list) box.append(el('div', { class: 'ayahrow' }, el('span', null, `${SURAH_NAMES[e.surah - 1]} ${e.ayah} ← انتقل إلى ${e.target ? SURAH_NAMES[e.target.surah - 1] + ' ' + e.target.ayah : 'موضع غير مسجل'}`), el('span', { class: 'muted' }, fmtDay(e.day))));
  return box;
}

/* ===== نافذة تسجيل الخطأ ===== */
function errorModal(c, page, lines) {
  const d = deriveChild(c); page = page || d.nextNew || 1;
  if (c === 'karim' && lines === undefined) lines = karimLines(c, page) || null;
  const pageIn = el('input', { type: 'number', min: 1, max: 604, value: page, style: 'width:100px' });
  const surahSel = el('select'); const ayahIn = el('input', { type: 'number', min: 1, placeholder: 'رقم الآية', style: 'width:120px' });
  const fillSurahs = () => { surahSel.innerHTML = ''; for (const s of surahsOfPage(Number(pageIn.value) || 1)) surahSel.append(el('option', { value: s }, SURAH_NAMES[s - 1])); };
  const hint = el('div', { class: 'small muted' });
  const showHint = () => { const rg = ayahRangeOnPage(Number(pageIn.value), Number(surahSel.value)); hint.textContent = rg ? `في هذه الصفحة: ${SURAH_NAMES[Number(surahSel.value) - 1]} ${rg[0]}–${rg[1]}` : ''; };
  fillSurahs(); showHint(); pageIn.addEventListener('input', () => { fillSurahs(); showHint(); }); surahSel.addEventListener('change', showHint);
  let etype = null; const typeBtns = el('div', { class: 'btns' });
  const target = el('div', { style: 'display:none' });
  const tSurah = el('input', { type: 'number', min: 1, max: 114, placeholder: 'رقم السورة', style: 'width:120px' }); const tAyah = el('input', { type: 'number', min: 1, placeholder: 'الآية', style: 'width:100px' });
  target.append(label('الموضع الذي انتقل إليه'), el('div', { class: 'row' }, tSurah, tAyah));
  for (const t of ERROR_TYPES) typeBtns.append(el('button', { class: 'ghost', onclick: e => { etype = t.id; [...typeBtns.children].forEach(b => b.classList.remove('on')); e.currentTarget.classList.add('on'); target.style.display = t.id === 'jump' ? '' : 'none'; } }, t.name));
  const note = el('input', { placeholder: 'ملاحظة (اختياري)' });
  const segBox = c === 'karim' ? el('div', { class: 'small' }, label('المقطع (الأسطر)'), el('div', { class: 'row' }, (lines ? el('span', { class: 'pill n' }, `الأسطر ${lines[0]}–${lines[1]}`) : el('span', { class: 'muted' }, 'غير محدد — سيُعرض للمراجعة ولا يُنسب لكل المقاطع')))) : null;
  const body = el('div', null, el('div', { class: 'row' }, el('div', null, label('الصفحة'), pageIn), el('div', { style: 'flex:1' }, label('السورة'), surahSel), el('div', null, label('الآية'), ayahIn)), hint, segBox, label('نوع الخطأ'), typeBtns, target, label('ملاحظة'), note);
  const bg = UI.modal(`خطأ · ${CHILDREN[c].name}`, body, [el('button', { class: 'primary', onclick: () => {
    if (!etype) { UI.toast('اختاري نوع الخطأ'); return; }
    const pg = Number(pageIn.value), su = Number(surahSel.value), ay = Number(ayahIn.value);
    if (!(pg >= 1 && pg <= 604)) { UI.toast('رقم الصفحة بين 1 و604'); return; }
    if (!(su >= 1 && su <= 114)) { UI.toast('اختاري السورة'); return; }
    if (!(ay >= 1 && ay <= SURAH_AYAT[su - 1])) { UI.toast(`رقم الآية بين 1 و${SURAH_AYAT[su - 1]}`); return; }
    /* الآية يجب أن تكون في الصفحة نفسها (حدود مصحف المدينة) */
    const rg = ayahRangeOnPage(pg, su);
    if (!rg || ay < rg[0] || ay > rg[1]) { UI.toast(`الآية ${SURAH_NAMES[su - 1]} ${ay} في ص${pageOfAyah(su, ay)}، لا في ص${pg}${rg ? ` (آيات ${SURAH_NAMES[su - 1]} هنا ${rg[0]}–${rg[1]})` : ''}`); return; }
    const ev = { type: 'error', child: c, page: pg, surah: su, ayah: ay, etype, note: note.value }; if (lines && pg === page) ev.lines = lines;
    if (etype === 'jump') { const ts = Number(tSurah.value), ta = Number(tAyah.value); if (!(ts >= 1 && ts <= 114)) { UI.toast('اكتبي رقم السورة التي انتقل إليها'); return; } ev.target = { surah: ts, ayah: ta || null }; }
    Store.add(ev); bg.remove(); UI.savedToast('سُجّل الخطأ'); UI.rerender(true);
  } }, 'حفظ')]);
}

function noteModal(c) {
  const sel = el('select', null, el('option', { value: '' }, 'عام'), CHILD_ORDER.map(k => el('option', { value: k }, CHILDREN[k].name)));
  if (c) sel.value = c;
  const t = el('textarea', { placeholder: 'الملاحظة' });
  const bg = UI.modal('ملاحظة', el('div', null, label('الطفل'), sel, label('النص'), t), [el('button', { class: 'primary', onclick: () => { if (!t.value.trim()) return; Store.add({ type: 'note', child: sel.value || null, text: t.value.trim() }); bg.remove(); UI.toast('حُفظت'); } }, 'حفظ')]);
}

/* ===== بطاقات ===== */
function cardModal(c, page) {
  const isSurah = c === 'karim'; const key = isSurah ? 's' + surahsOfPage(page)[0] : 'p' + page;
  const cur = cardsFor(c)[key] || {};
  const f = {};
  const fields = isSurah ? [['story', 'قصة السورة في جملة'], ['words', 'كلمتان أو ثلاث من غريبها بمعناها'], ['situation', 'سؤال موقف: ماذا نفعل عندما…؟'], ['gesture', 'حركة أو صورة ذهنية']]
    : [['q1', '١ غريب: ما معنى …؟'], ['q2', '٢ موضوع: ما الذي تتحدث عنه الآيات من … إلى …؟'], ['q3', '٣ موضع: في أي سورة وبعد أي قصة تأتي آية …؟'], ['q4', '٤ تدبر: ما القاعدة التي أخذناها من …؟']];
  const body = el('div', null, el('p', { class: 'muted small' }, isSurah ? `سورة ${SURAH_NAMES[surahsOfPage(page)[0] - 1]}` : pageLabel(page)));
  for (const [k, lab] of fields) { f[k] = el('textarea', { style: 'min-height:48px' }); f[k].value = cur[k] || ''; body.append(label(lab), f[k]); }
  const bg = UI.modal('بطاقة', body, [el('button', { class: 'primary', onclick: () => { const ev = { type: 'card', child: c, key, kind: isSurah ? 'surah' : 'page', page }; for (const k in f) ev[k] = f[k].value.trim(); Store.add(ev); bg.remove(); UI.toast('حُفظت البطاقة'); UI.rerender(true); } }, 'حفظ')]);
}

/* ===== تنبيهات ===== */
function alertsList() {
  const out = [];
  if (Store.storageError) out.push({ level: 'red', child: null, text: Store.storageError });
  for (const c of CHILD_ORDER) {
    const h = healthOf(c);
    if (h.gateFails >= 2) out.push({ level: 'red', child: c, text: `سقطت بوابة الصباح ${h.gateFails} مرات هذا الأسبوع؛ القاعدة: تخفيض المقدار وإبلاغ ولي الأمر.` });
    if (h.maxGap > 12 && h.st.maxGapPage) out.push({ level: 'red', child: c, text: `الصفحة ${h.st.maxGapPage} بلا تسميع منذ ${h.maxGap} يوماً (الحد 12).` });
    else if (h.maxGap > 10 && h.st.maxGapPage) out.push({ level: 'yellow', child: c, text: `الصفحة ${h.st.maxGapPage} تقترب من حد الـ12 يوماً (${h.maxGap}).` });
    if (h.examGreen != null && h.examGreen < 85) out.push({ level: h.examGreen < 70 ? 'red' : 'yellow', child: c, text: `آخر فحص خميس: ${h.examClean}/${h.examN} أخضر.` });
    if (h.examN && h.examN < (c === 'karim' ? 2 : 5)) out.push({ level: 'yellow', child: c, text: `فحص ${fmtDay(h.examDay)} غير مكتمل (${h.examN} من ${c === 'karim' ? 2 : 5}).` });
    const d = h.st; if (d.far.length && d.nextNew && !cardsFor(c)[c === 'karim' ? 's' + surahsOfPage(d.nextNew)[0] : 'p' + d.nextNew]) out.push({ level: 'yellow', child: c, text: `بطاقة ${c === 'karim' ? 'سورة' : 'صفحة'} الغد (${d.nextNew}) لم تُكتب.` });
  }
  const ws = weekStartKey(App.now());
  for (const s of PLAN) { for (const dk of lastDays(7)) { const st = sessionStatus(s, dk); if (st && st.conflicts.length) out.push({ level: 'red', child: s.child === 'both' || s.child === 'all' ? null : s.child, text: `${fmtDay(dk)} ${childName(s.child)} · ${SESSION_KINDS[s.kind].name}: ${st.conflicts.join('؛ ')} — لم تُحذف أي نتيجة؛ راجعي السجل.` }); } }
  for (const e of Store.events.filter(e => e.type === 'session_done' && e.day >= ws && e.status && e.status !== 'complete')) out.push({ level: 'yellow', child: e.child, text: `${fmtDay(e.day)} ${SESSION_KINDS[e.kind] ? SESSION_KINDS[e.kind].name : e.kind}: ${e.status === 'stopped' ? 'توقفت (' + e.reason + ')' : 'بقي جزء: ' + (e.remaining || []).map(id => { const k = SESSION_KINDS[e.kind]; const st = k && k.steps.find(x => x.id === id); return st ? st.text : id; }).join('؛ ')} — تقرر آية كيف يُستدرك.` });
  for (const e of Store.events.filter(e => e.type === 'decision' && e.day >= ws)) out.push({ level: 'yellow', child: e.child, text: `قرار آية (${fmtDay(e.day)}): ${decisionName(e.kind)} — ${e.text || ''}` });
  return out;
}
function decisionName(k) { return { repair: 'صباح إصلاح', reduce: 'تخفيض المقدار', restore: 'استعادة المقدار', pause: 'توقف الجديد', resume: 'استئناف الجديد', override: 'تجاوز التوقف ليوم', juz: 'إجازة جزء', surah: 'اعتماد سورة' }[k] || k; }
function AlertsCard() {
  const list = alertsList(); if (!list.length) return el('div');
  return el('div', { class: 'card' }, el('h2', null, 'تنبيهات'), list.map(a => el('div', { class: 'alert' + (a.level === 'red' ? ' red' : '') }, el('b', null, CHILDREN[a.child] ? CHILDREN[a.child].name + ': ' : ''), a.text)));
}

/* ===== بطاقات التسليم ===== */
function handoffCard(h, full) {
  const stName = { new: 'جديدة', seen: 'اطلعت عليها آية', handled: 'عولجت', reopened: 'أُعيد فتحها' }[h.state];
  const cls = { new: 'pill y', seen: 'pill n', handled: 'pill g', reopened: 'pill r' }[h.state];
  const box = el('div', { class: 'alert' + (h.items.some(i => i.k === 'jump') && h.state !== 'handled' ? ' red' : ''), style: 'margin:6px 0' },
    el('div', { class: 'row between' }, el('b', null, `${CHILDREN[h.child].name} — إلى آية · ${SESSION_KINDS[h.kind] ? SESSION_KINDS[h.kind].name : h.kind} · ${fmtDay(h.day)}`), el('span', { class: cls }, stName)));
  const lab = { done: 'أُنجز', followup: 'يحتاج متابعة', jump: 'متشابه', error: 'خطأ', remaining: 'الباقي', note: 'ملاحظة', update: 'تحديث' };
  for (const it of h.items) box.append(el('div', { class: 'small' }, el('b', null, (lab[it.k] || it.k) + ': '), it.text, it.k === 'jump' && it.n > 1 ? el('span', { class: 'muted' }, ` · تكرر ${it.n} مرات`) : null, it.addedDay ? el('span', { class: 'muted' }, ` (${fmtDay(it.addedDay)})`) : null));
  if (App.role.id === 'aya') {
    const b = el('div', { class: 'btns' });
    if (h.state === 'new' || h.state === 'reopened') b.append(el('button', { class: 'ghost', onclick: () => { Store.add({ type: 'handoff_status', handoff: h.id, child: h.child, status: 'seen' }); UI.rerender(); } }, 'اطلعتُ'));
    if (h.state !== 'handled') b.append(el('button', { class: 'btn-g', onclick: () => { Store.add({ type: 'handoff_status', handoff: h.id, child: h.child, status: 'handled' }); UI.rerender(); } }, 'عولجت'));
    else b.append(el('button', { class: 'ghost', onclick: () => { Store.add({ type: 'handoff_status', handoff: h.id, child: h.child, status: 'reopened' }); UI.rerender(); } }, 'عاد الخطأ — إعادة فتح'));
    box.append(b);
  }
  return box;
}
function HandoffsCard() {
  if (App.role.id === 'asst') return el('div');
  const open = handoffs(h => h.state !== 'handled');
  if (!open.length) return el('div');
  return el('div', { class: 'card' }, el('h2', null, `بطاقات التسليم (${open.length})`), open.slice(-6).reverse().map(h => handoffCard(h)));
}

function lastDays(n) { const out = []; const d = App.now(); for (let i = 0; i < n; i++) { const x = new Date(d.getTime() - i * 86400000); out.push(dayKey(x)); } return out; }

/* إلغاء جلسات اليوم (غير المنفذة) بسبب موثَّق؛ لا يُحذف أي سجل */
function cancelModal() {
  const d = App.now(); const dayK = todayKey();
  const list = sessionsFor(App.role.id, d).filter(s => !sessionStatus(s, dayK));
  const act = Store.settings.active && Store.settings.active.role === App.role.id && Store.settings.active.dayK === dayK ? Store.settings.active : null;
  if (!list.length) { UI.toast('لا جلسات متبقية اليوم'); return; }
  const checks = list.map(s => { const c = el('input', { type: 'checkbox' }); c.checked = true; return [s, c]; });
  const reasonSel = el('select', null, ['مرض طفل', 'سفر أو ظرف عائلي', 'انقطاع الإنترنت', 'غياب معلمة', 'سبب آخر'].map(x => el('option', { value: x }, x)));
  const txt = el('input', { placeholder: 'تفصيل (اختياري)' });
  const bg = UI.modal('إلغاء جلسات اليوم', el('div', null, el('p', { class: 'small muted' }, 'تُلغى الجلسات المختارة غير المنفذة فقط. النتائج المسجلة سابقاً تبقى. الجلسة الجارية تُحفظ بما أُنجز ويظهر الباقي.'), checks.map(([s, c]) => el('label', { class: 'row', style: 'margin:4px 0' }, c, ` ${fmtTime12(s.start)} ${childName(s.child)} · ${SESSION_KINDS[s.kind].name}`)), label('السبب'), reasonSel, txt),
    [el('button', { class: 'danger', onclick: async () => { const reason = reasonSel.value + (txt.value.trim() ? ': ' + txt.value.trim() : ''); let ok = 0, fail = 0; const failed = []; const added = [];
      for (const [s, c] of checks) { if (!c.checked) continue; const key = sessionKey(s, dayK);
        try {
          if (act && act.key === key) { if (await commitEnd(s, act, 'stopped', SESSION_KINDS[s.kind].steps.filter(st => !act.steps.includes(st.id)).map(st => st.id), 'إلغاء: ' + reason, act.note || '')) ok++; else { fail++; failed.push(s); } continue; }
          for (const ch of childrenOf(s)) if (!Store.events.some(e => e.type === 'session_cancel' && e.key === key && e.child === ch)) Store.add({ type: 'session_cancel', key, child: ch, kind: s.kind, start: s.start, reason });
          added.push([s, c]);
        } catch (e) { fail++; failed.push(s); }
      }
      /* الإلغاءات تُعدّ ناجحة بعد ثبوت حفظها فقط */
      if (added.length) { if (await Store.durable()) { for (const [s, c] of added) { ok++; c.disabled = true; c.checked = false; } } else { for (const [s] of added) { fail++; failed.push(s); } } }
      if (fail) { UI.toast(`أُلغيت ${ok} جلسة، وتعذّر ${fail}: ${failed.map(s => childName(s.child) + ' ' + fmtTime12(s.start)).join('، ')} — أعيدي المحاولة`); UI.rerender(true); return; }
      bg.remove(); UI.toast(`أُلغيت ${ok} جلسة`); UI.rerender(); } }, 'تأكيد الإلغاء')]);
}
