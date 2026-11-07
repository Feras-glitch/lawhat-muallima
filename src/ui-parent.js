/* ===== لوحة ولي الأمر، التقارير، الإعدادات ===== */
Views.dash = function () {
  const wrap = el('div');
  const due = BackupReminder(); if (due) wrap.append(due);
  const upd = AppUpdateBanner(); if (upd) wrap.append(upd);
  wrap.append(el('div', { class: 'grid2' }, CHILD_ORDER.map(c => { const h = healthOf(c); const d = h.st; return el('div', { class: 'card', style: 'margin:0;cursor:pointer', onclick: () => { App.sub.child = c; App.sub.ctab = 'summary'; App.view = 'children'; UI.rerender(); } },
    el('div', { class: 'row between' }, el('h2', { style: 'margin:0' }, CHILDREN[c].name), el('span', { class: 'light ' + h.light })),
    el('div', { class: 'kpi', style: 'margin-top:8px' }, el('div', null, el('div', { class: 'v' }, h.examGreen == null ? '—' : `${h.examClean}/${h.examN}`), el('div', { class: 'k' }, h.examDay ? 'أخضر في الفحص' : 'لم يُفحص')), el('div', null, el('div', { class: 'v' }, h.gateFails), el('div', { class: 'k' }, 'سقوط بوابة')), el('div', null, el('div', { class: 'v' }, d.far.length ? d.maxGap : '—'), el('div', { class: 'k' }, 'أقدم صفحة (يوم)'))),
    el('div', { class: 'small muted', style: 'margin-top:8px' }, `البعيد ${d.far.length} · القريب ${d.near.length} · التالي: ${d.nextNew ? pageLabel(d.nextNew) : '—'}`)); })));
  wrap.append(el('div', { style: 'height:14px' }), BriefCard(), GroupedAlerts());
  const today = todayKey(); const todays = Store.events.filter(e => e.day === today && ['outcome', 'error', 'new_page', 'session_done', 'decision'].includes(e.type));
  wrap.append(el('div', { class: 'card' }, el('h2', null, 'اليوم'), DayList(sessionsFor('parent', App.now()), true).querySelector('table') || el('p', { class: 'muted' }, 'لا جلسات اليوم'), el('div', { class: 'small muted', style: 'margin-top:8px' }, `${todays.filter(e => e.type === 'session_done').length} جلسة مسجلة · ${todays.filter(e => e.type === 'outcome').length} تسميع · ${todays.filter(e => e.type === 'error').length} خطأ`)));
  wrap.append(el('div', { class: 'card' }, el('h2', null, 'فحصك الشهري'), el('p', { class: 'muted small' }, 'خمس صفحات بالقرعة من البعيد لكل طفل، تُسمَّع لك وتُسجَّل نتيجتها وتُقارن بألوان آية.'), el('div', { class: 'btns' }, CHILD_ORDER.map(c => el('button', { onclick: () => parentExam(c) }, CHILDREN[c].name)))));
  return wrap;
};
/* تنبيهات ولي الأمر مجمَّعة بحسب الطفل والإجراء، تُفتح عند الطلب */
function GroupedAlerts() {
  const list = alertsList(); if (!list.length) return el('div');
  const groups = {};
  for (const a of list) { const k = a.child || 'all'; (groups[k] = groups[k] || []).push(a); }
  const card = el('div', { class: 'card' }, el('h2', null, `تنبيهات (${list.length})`));
  for (const k of [...CHILD_ORDER, 'all']) {
    const g = groups[k]; if (!g) continue;
    const reds = g.filter(a => a.level === 'red').length;
    const body = el('div', { style: 'display:none' }, g.map(a => el('div', { class: 'alert' + (a.level === 'red' ? ' red' : '') }, a.text)));
    const kinds = {}; for (const a of g) { const t = a.text.includes('بطاقة') ? 'بطاقات لم تُكتب' : a.text.includes('بقي جزء') || a.text.includes('توقفت') ? 'جلسات لم تكتمل' : a.text.includes('تعارض') ? 'تعارض تسجيل' : a.text.includes('فحص') ? 'الفحص' : a.text.includes('بوابة') ? 'البوابة' : a.text.includes('بلا تسميع') || a.text.includes('حد الـ12') ? 'تأخر مراجعة' : a.text.includes('قرار') ? 'قرارات' : 'أخرى'; kinds[t] = (kinds[t] || 0) + 1; }
    card.append(el('div', { style: 'border-top:1px solid var(--line);padding:6px 0' }, el('div', { class: 'row between', style: 'cursor:pointer', onclick: () => { body.style.display = body.style.display === 'none' ? '' : 'none'; } }, el('span', null, el('b', null, k === 'all' ? 'عام' : CHILDREN[k].name), el('span', { class: 'muted small' }, ' · ' + Object.entries(kinds).map(([t, n]) => `${t} ${n}`).join(' · ')), reds ? el('span', { class: 'pill r', style: 'margin-right:6px' }, `${reds} أحمر`) : null), el('span', { class: 'muted small' }, '▾')), body));
  }
  return card;
}

function parentExam(c) {
  const d = deriveChild(c); if (d.far.length < 1) { UI.toast('لا محفوظ بعيد'); return; }
  const pool = d.far.slice(); const pick = []; for (let i = 0; i < 5 && pool.length; i++) pick.push(pool.splice(Math.floor(Math.random() * pool.length), 1)[0]); pick.sort((a, b) => a - b);
  const res = {}; const body = el('div');
  for (const p of pick) { const row = el('div', { class: 'ayahrow' }, el('span', null, pageLabel(p), ' ', d.pages[p].color ? resultPill(d.pages[p].color === 'green' ? 'clean' : d.pages[p].color) : el('span', { class: 'pill n' }, 'بلا لون')), el('span', { class: 'row' }, ['clean', 'yellow', 'red'].map(r => el('button', { class: ({ clean: 'btn-g', yellow: 'btn-y', red: 'btn-r' })[r], style: 'padding:4px 10px', onclick: e => { res[p] = r; [...e.currentTarget.parentNode.children].forEach(b => b.classList.remove('on')); e.currentTarget.classList.add('on'); } }, ({ clean: '✓', yellow: 'أصفر', red: 'أحمر' })[r])))); body.append(row); }
  const bg = UI.modal(`فحص ${CHILDREN[c].name}`, body, [el('button', { class: 'primary', onclick: () => { const done = Object.keys(res).length; if (done < pick.length) { UI.toast('سجّل كل الصفحات'); return; } for (const p of pick) Store.add({ type: 'outcome', child: c, page: Number(p), step: 'exam', result: res[p], parent: true }); Store.add({ type: 'parent_exam', child: c, pages: pick, green: pick.filter(p => res[p] === 'clean').length }); bg.remove(); UI.savedToast('سُجّل الفحص'); UI.rerender(); } }, 'حفظ')]);
}

Views.reports = function () {
  const f = App.sub.rep || (App.sub.rep = { child: 'c1', from: dayKey(new Date(App.now().getTime() - 13 * 86400000)), to: todayKey() });
  const wrap = el('div');
  const childSel = el('select', { onchange: e => { f.child = e.target.value; UI.rerender(); } }, CHILD_ORDER.map(k => el('option', { value: k }, CHILDREN[k].name))); childSel.value = f.child;
  const from = el('input', { type: 'date', value: f.from, onchange: e => { f.from = e.target.value; UI.rerender(); } });
  const to = el('input', { type: 'date', value: f.to, onchange: e => { f.to = e.target.value; UI.rerender(); } });
  wrap.append(el('div', { class: 'card' }, el('h2', null, 'تقرير حسب الطلب'), el('div', { class: 'row' }, childSel, from, to)));
  const evs = Store.events.filter(e => e.child === f.child && e.day >= f.from && e.day <= f.to);
  const days = [...new Set(evs.map(e => e.day))].sort();
  const news = evs.filter(e => e.type === 'new_page'); const outs = effectiveOutcomes(e => e.child === f.child && e.day >= f.from && e.day <= f.to); const errs = evs.filter(e => e.type === 'error');
  /* (LM0121-R2-05/06) تعريف موحد: الجزئي مستقل عن السالم والساقط؛ فحص ولي الأمر صف مستقل لا يدخل أرقام المعلمتين */
  const tOuts = outs.filter(teacherOutcome); const pOuts = outs.filter(o => o.parent);
  const gates = tOuts.filter(o => o.step === 'gate'); const fars = tOuts.filter(o => o.step === 'far'); const exams = tOuts.filter(o => o.step === 'exam');
  const sx = l => { const x = outcomeStats(l); return `${x.n}${x.partial ? ` (منها ${x.partial} لم يُقيَّم كاملاً)` : ''} · سالم ${x.clean} · سقوط ${x.fail}${x.pct != null ? ` · ${x.pct}%` : ''}`; };
  const byType = {}; for (const e of errs) byType[e.etype] = (byType[e.etype] || 0) + 1;
  const memMins = news.filter(n => n.minutes).map(n => n.minutes);
  wrap.append(el('div', { class: 'card' }, el('h3', null, `${CHILDREN[f.child].name} · ${days.length} يوم عمل`),
    el('table', null, el('tbody', null,
      tr('الجديد', `${news.length} ${isLines(f.child) ? 'مقطع' : 'صفحة'}${memMins.length ? ` · متوسط زمن الحفظ ${Math.round(memMins.reduce((a, b) => a + b, 0) / memMins.length)} د` : ''}`),
      tr('البوابة', gates.length ? sx(gates) : '—'),
      tr('البعيد', fars.length ? sx(fars) : '—'),
      tr('فحص الخميس (المعلمة)', exams.length ? sx(exams) : '—'),
      tr('فحص المنزل (ولي الأمر)', pOuts.length ? sx(pOuts) : '—'),
      tr('كل تسميعات المعلمتين', tOuts.length ? sx(tOuts) : '—'),
      tr('الأخطاء', `${errs.length}${errs.length ? ' · ' + Object.entries(byType).map(([k, v]) => (ERROR_TYPES.find(t => t.id === k) || {}).name + ' ' + v).join('، ') : ''}`),
      tr('الجلسات المسجلة', `${new Set(evs.filter(e => e.type === 'session_done').map(e => e.key)).size}`),
      tr('القرارات', evs.filter(e => e.type === 'decision').map(e => `${fmtDay(e.day)} ${decisionName(e.kind)}`).join('؛ ') || '—')))));
  // اتساق تسجيل المساعدة مع فحص آية
  const asstFar = fars.filter(o => o.by === 'asst'); const ayaExam = exams.filter(o => o.by === 'aya');
  if (asstFar.length && ayaExam.length) wrap.append(el('div', { class: 'card' }, el('h3', null, 'اتساق التسجيل'), el('p', { class: 'small' }, `سالم عند المساعدة في البعيد: ${pct(asstFar)} · أخضر عند آية في الفحص: ${pct(ayaExam)}. فرق كبير مستمر يعني تساهلاً في التسجيل اليومي.`)));
  // أزمنة الطلاقة للطفل الثالث
  if (isLines(f.child)) { const fl = evs.filter(e => e.type === 'fluency_time'); if (fl.length) wrap.append(el('div', { class: 'card' }, el('h3', null, 'الطلاقة'), el('table', null, el('tbody', null, fl.slice(-15).map(e => tr(fmtDay(e.day), `ص${e.page}: ${e.seconds} ث`)))))); }
  wrap.append(el('div', { class: 'card' }, el('h3', null, 'الأيام'), el('table', null, el('tbody', null, days.slice().reverse().map(k => { const de = evs.filter(e => e.day === k); return tr(fmtDay(k), `جديد ${de.filter(e => e.type === 'new_page').map(e => e.page).join('،') || '—'} · تسميعات ${de.filter(e => e.type === 'outcome').length} · أخطاء ${de.filter(e => e.type === 'error').length} · جلسات ${new Set(de.filter(e => e.type === 'session_done').map(e => e.key)).size}`); })))));
  wrap.append(el('div', { class: 'card' }, el('h3', null, 'خلاصة الأسبوع (نص للنسخ)'), el('pre', { style: 'direction:rtl;text-align:right;white-space:pre-wrap' }, weeklySummaryText())));
  return wrap;
};
function tr(a, b) { return el('tr', null, el('th', null, a), el('td', null, b)); }
function pct(list) { const x = outcomeStats(list); return x.pct == null ? '—' : x.pct + '%'; }

/* ===== الإعدادات ===== */
Views.settings = function () {
  const wrap = el('div'); const s = Store.settings;
  const due = BackupReminder(); if (due) wrap.append(due);
  const upd = AppUpdateBanner(); if (upd) wrap.append(upd);
  wrap.append(el('div', { class: 'card' }, el('h2', null, 'الحساب'), el('p', null, `الدخول الحالي: ${App.role.title}`), el('button', { class: 'ghost', onclick: () => App.logout() }, 'خروج')));
  /* الأسماء ليست في الكود المنشور (0.15): يُدخلها ولي الأمر أو آية مرة واحدة، وتُحفظ سجلاً يُزامَن لأصحاب الأدوار فقط */
  if (App.role.id === 'parent' || App.role.id === 'aya') {
    const cur = familyNames() || {};
    const ins = {}; for (const k of CHILD_ORDER) ins[k] = el('input', { maxlength: 30, value: cur[k] || '', placeholder: CHILD_DEFAULT_NAMES[k] });
    const hints = { c1: 'يحفظ بالصفحة', c2: 'يحفظ بالصفحة، ويرافق الأول في الجلسات المشتركة', c3: 'يحفظ بالأسطر (مقطع 4 أسطر)' };
    wrap.append(el('div', { class: 'card' }, el('h2', null, 'أسماء الأطفال'), el('p', { class: 'small muted' }, 'لا تُكتب الأسماء في البرنامج المنشور. تُحفظ هنا سجلاً على هذا الجهاز ثم على خادم العائلة، فلا يقرؤها إلا أصحاب الأدوار.'),
      CHILD_ORDER.map(k => el('div', null, label(`${CHILD_DEFAULT_NAMES[k]} — ${hints[k]}`), ins[k])),
      el('button', { class: 'primary', onclick: () => { const names = {}; for (const k of CHILD_ORDER) { const v = ins[k].value.trim(); if (v) names[k] = v; } if (!Object.keys(names).length) { UI.toast('اكتبي اسماً واحداً على الأقل'); return; } Store.add({ type: 'names', names }); UI.savedToast('حُفظت الأسماء'); UI.rerender(); } }, 'حفظ الأسماء')));
  }
  if (App.role.id === 'parent') wrap.append(el('div', { class: 'card' }, el('h2', null, 'الجرد الأولي'), el('p', { class: 'small muted' }, 'تنفذه آية من حسابها بعد تسميع المحفوظ الحالي (وضع الصفحات في البعيد وألوانها من صلاحيتها وحدها). يظهر هنا أثره بعد المزامنة.')));
  if (App.role.id === 'aya') {
    const inv = el('div', { class: 'card' }, el('h2', null, 'الجرد الأولي'), el('p', { class: 'small muted' }, 'يُنفَّذ مرة واحدة بعد تسميع المحفوظ الحالي. يضع الصفحات في البعيد؛ ثم تُعدَّل ألوان صفحات مفردة من خريطة المصحف.'),
      el('div', { class: 'btns' },
        el('button', { onclick: () => UI.confirm(`وضع جزءي عمّ وتبارك (562–604) في البعيد لـ${childName('both')} باللون الأخضر؟`, () => { for (const c of PAIR) for (let p = 562; p <= 604; p++) Store.add({ type: 'layer', child: c, page: p, layer: 'far', color: 'green' }); UI.savedToast('تم'); UI.rerender(); }) }, `${childName('both')}: عمّ وتبارك`),
        el('button', { onclick: () => UI.prompt(`${CHILDREN.c3.name}: من أي صفحة إلى 604 في البعيد؟ (نصف جزء عمّ ≈ من 595)`, 'رقم الصفحة', v => { if (v == null) return; const n = Number(v); if (!(Number.isInteger(n) && n >= 562 && n <= 604)) { UI.toast('رقم صفحة صحيح بين 562 و604'); return false; } for (let p = n; p <= 604; p++) Store.add({ type: 'layer', child: 'c3', page: p, layer: 'far', color: 'green' }); UI.savedToast('تم'); UI.rerender(); }, '595') }, `${CHILDREN.c3.name}: نصف عمّ`)));
    wrap.append(inv);
  }
  if (App.role.id === 'aya' || App.role.id === 'parent') {
    const pins = el('div', { class: 'card' }, el('h2', null, 'رموز الدخول المحلي'));
    for (const r of Object.values(ROLES)) { const i = el('input', { value: s.pins[r.id], inputmode: 'numeric', style: 'width:120px' }); pins.append(el('div', { class: 'row', style: 'margin:6px 0' }, el('span', { style: 'min-width:110px' }, r.name), i, el('button', { onclick: () => { s.pins[r.id] = i.value; Store.saveSettings(); UI.toast('حُفظ'); } }, 'حفظ'))); }
    wrap.append(pins);
  }
  // الخادم والمرفوضات
  wrap.append(ServerCard());
  const rejCard = RejectedCard(); if (rejCard) wrap.append(rejCard);
  const cfCard = ConflictsCard(); if (cfCard) wrap.append(cfCard);
  // التنبيهات والتقويم
  if (App.role.id !== 'parent') {
    const chk = el('input', { type: 'checkbox' }); chk.checked = Alarms.on();
    const chk2 = el('input', { type: 'checkbox' }); chk2.checked = Store.settings.endAlarm !== false;
    wrap.append(el('div', { class: 'card' }, el('h2', null, 'التنبيهات'),
      el('label', { class: 'row', style: 'margin:0' }, chk, ' نغمة واهتزاز عند بداية كل جلسة وعند الاستراحة (تنبيه واحد)'),
      el('label', { class: 'row', style: 'margin:0' }, chk2, ' نغمة هادئة عند نهاية الجلسة (تُدمج مع بداية التالية إن تلاصقتا)'),
      el('p', { class: 'small muted' }, 'أثناء جلسة مفتوحة تُكتم الأصوات تلقائياً وتظهر إشارة 🔇 في الرأس؛ وعند العودة بعد غياب لا تُطلق التنبيهات الفائتة.'),
      el('div', { class: 'btns' }, el('button', { onclick: () => { Store.settings.sounds = chk.checked; Store.settings.endAlarm = chk2.checked; Store.saveSettings(); Alarms.unlock(); Alarms.beep('start'); UI.toast('حُفظ'); } }, 'حفظ وتجربة النغمة')),
      el('p', { class: 'small muted' }, 'التنبيه الداخلي يعمل ما دام البرنامج مفتوحاً على الشاشة. للتنبيه ولو كان مغلقاً: استوردي جدولك مرة واحدة في تقويم هاتفك (يرنّ قبل كل جلسة بخمس دقائق بتوقيتك المحلي).'),
      el('button', { class: 'ghost', onclick: () => downloadIcs(App.role.id) }, 'تنزيل جدولي كتقويم (.ics)')));
  }
  // النسخ الاحتياطي والاستعادة
  wrap.append(BackupCard());
  const appCard = AppCard(); if (appCard) wrap.append(appCard);
  if (App.role.id === 'parent') wrap.append(AdminRestoreCard());
  // محاكاة الوقت
  if (App.role.id !== 'asst') {
    const off = el('input', { type: 'datetime-local' });
    if (App.role.id === 'parent') wrap.append(el('div', { class: 'card' }, el('h2', null, 'الوقت'), el('p', { class: 'small muted' }, 'للتجربة فقط: ضبط ساعة البرنامج على وقت آخر لمعاينة الجلسات. يعود الوقت الحقيقي بزر الإلغاء.'), el('div', { class: 'row' }, off, el('button', { onclick: () => { if (!off.value) return; s.timeOffset = new Date(off.value).getTime() - Date.now(); Store.saveSettings(); UI.rerender(); } }, 'ضبط'), el('button', { class: 'ghost', onclick: () => { s.timeOffset = 0; Store.saveSettings(); UI.rerender(); } }, 'الوقت الحقيقي')), s.timeOffset ? el('p', { class: 'alert' }, 'الوقت الآن محاكى.') : null));
  }
  if (App.role.id === 'parent') wrap.append(el('div', { class: 'card' }, el('h2', null, 'مسح البيانات'), el('button', { class: 'danger', onclick: () => UI.confirm('حذف كل السجلات من هذا الجهاز؟ (لا يمس الخادم)', async () => { const ok = await Store.reset(); Store.settings.active = null; Store.saveSettings(); UI.toast(ok ? 'حُذفت كل نسخ السجلات من الجهاز' : 'تعذّر حذف بعض النسخ؛ أعيدي المحاولة'); UI.rerender(); }) }, 'حذف السجلات المحلية (مع تصفير المؤشر والمرفوضات والجلسة الجارية)')));
  wrap.append(el('p', { class: 'small muted', style: 'text-align:center' }, `لوحة المعلمة · الإصدار ${BUILD.version} (${BUILD.commit})${AppShell.inApp() ? ' · تطبيق أندرويد ' + (AppShell.version() || '') : ''} · الخطة بتوقيت بكين · مصحف المدينة 15 سطراً`));
  return wrap;
};


/* ===== تصدير التقويم ===== */
function downloadIcs(role) {
  const byday = { 6: 'SA', 0: 'SU', 1: 'MO', 2: 'TU', 3: 'WE', 4: 'TH' };
  const pad = n => String(n).padStart(2, '0');
  // أول حدوث: أقرب يوم مطابق من الأسبوع الحالي
  const base = App.now();
  const lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//lawhat-muallima//AR', 'CALSCALE:GREGORIAN', 'BEGIN:VTIMEZONE', 'TZID:Asia/Shanghai', 'BEGIN:STANDARD', 'DTSTART:19700101T000000', 'TZOFFSETFROM:+0800', 'TZOFFSETTO:+0800', 'TZNAME:CST', 'END:STANDARD', 'END:VTIMEZONE'];
  const items = PLAN.filter(s => s.teacher === role).map(s => ({ day: s.day, start: s.start, end: s.end, title: `${childName(s.child)} · ${SESSION_KINDS[s.kind].name}` }));
  for (const d of WORKDAYS) items.push({ day: d, start: '11:40', end: '12:10', title: 'الاستراحة الرئيسية' });
  let i = 0;
  for (const it of items) {
    const first = new Date(base); first.setDate(first.getDate() + ((it.day - first.getDay() + 7) % 7));
    const ds = `${first.getFullYear()}${pad(first.getMonth() + 1)}${pad(first.getDate())}`;
    const t = hm => hm.replace(':', '') + '00';
    lines.push('BEGIN:VEVENT', `UID:lm-${role}-${i++}@lawhat`, `DTSTAMP:${ds}T000000Z`, `DTSTART;TZID=Asia/Shanghai:${ds}T${t(it.start)}`, `DTEND;TZID=Asia/Shanghai:${ds}T${t(it.end)}`, `RRULE:FREQ=WEEKLY;BYDAY=${byday[it.day]}`, `SUMMARY:${it.title}`, 'BEGIN:VALARM', 'TRIGGER:-PT5M', 'ACTION:DISPLAY', `DESCRIPTION:${it.title}`, 'END:VALARM', 'END:VEVENT');
  }
  lines.push('END:VCALENDAR');
  AppShell.saveFile(`jadwal-${role}.ics`, 'text/calendar', lines.join('\r\n'));
}

/* ===== الموجز لولي الأمر: أُنجز / تحسّن / يحتاج متابعة / قرار الأسبوع ===== */
function briefFor(c) {
  const ws = weekStartKey(App.now()); const d = deriveChild(c);
  const wk = e => e.child === c && e.day >= ws;
  const newPages = [...new Set(Store.events.filter(e => e.type === 'new_page' && wk(e)).map(e => e.page))];
  const farHeard = [...new Set(effectiveOutcomes(e => wk(e) && e.step === 'far' && e.result !== 'partial').map(e => e.page))];
  const colors = Store.events.filter(e => e.type === 'color' && e.child === c);
  const prevColor = {}; const improved = [];
  for (const e of colors) { if (e.day >= ws && prevColor[e.page] && prevColor[e.page] !== 'green' && e.color === 'green') improved.push(e.page); prevColor[e.page] = e.color; }
  const redNow = d.far.concat(d.near).filter(p => d.pages[p].color === 'red');
  const openHand = handoffs(h => h.child === c && h.state !== 'handled');
  const jumps = openHand.flatMap(h => h.items.filter(i => i.k === 'jump'));
  const partials = Store.events.filter(e => e.type === 'session_done' && wk(e) && e.status && e.status !== 'complete');
  const dec = Store.events.filter(e => e.type === 'decision' && e.child === c).pop();
  return { newPages, farHeard, improved: [...new Set(improved)], redNow, openHand, jumps, partials, dec, d };
}
function BriefCard() {
  const card = el('div', { class: 'card' }, el('h2', null, 'الموجز الأسبوعي'), el('p', { class: 'muted small' }, 'ما أُنجز، ما تحسّن، ما يحتاج متابعة، وقرار الأسبوع. التفاصيل في صفحة كل طفل.'));
  for (const c of CHILD_ORDER) {
    const b = briefFor(c);
    card.append(el('div', { style: 'border-top:1px solid var(--line);padding:8px 0' },
      el('div', { class: 'row between' }, el('b', null, CHILDREN[c].name), el('button', { class: 'ghost small', onclick: () => { App.sub.child = c; App.sub.ctab = 'summary'; App.view = 'children'; UI.rerender(); } }, 'التفاصيل')),
      el('div', { class: 'small' }, el('b', null, 'أُنجز: '), `${b.newPages.length} ${isLines(c) ? 'مقطع' : 'صفحة'} جديدة هذا الأسبوع${b.newPages.length ? ' (' + b.newPages.join('، ') + ')' : ''} · سُمّع من البعيد ${b.farHeard.length} صفحة`),
      el('div', { class: 'small' }, el('b', null, 'تحسّن: '), b.improved.length ? `صفحات صارت خضراء: ${b.improved.join('، ')}` : 'لا تغيّر في الألوان هذا الأسبوع'),
      el('div', { class: 'small' }, el('b', null, 'يحتاج متابعة: '), [b.redNow.length ? `${b.redNow.length} صفحة حمراء (${b.redNow.slice(0, 6).join('، ')}${b.redNow.length > 6 ? '…' : ''})` : null, b.jumps.length ? `${b.jumps.length} متشابه مفتوح` : null, b.openHand.length ? `${b.openHand.length} بطاقة تسليم لم تُعالَج` : null, b.partials.length ? `${b.partials.length} جلسة لم تكتمل` : null].filter(Boolean).join(' · ') || 'لا شيء معلّق'),
      el('div', { class: 'small' }, el('b', null, 'قرار الأسبوع: '), b.dec ? `${decisionName(b.dec.kind)} (${fmtDay(b.dec.day)})${b.dec.text ? ' — ' + b.dec.text : ''}` : 'لا قرار مسجل')));
  }
  return card;
}
