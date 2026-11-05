/* ===== الأطفال، السجلات، الخميس ===== */
Views.children = function () {
  const c = App.sub.child || 'dalal'; const tab = App.sub.ctab || 'summary';
  const wrap = el('div');
  wrap.append(el('div', { class: 'tabs' }, CHILD_ORDER.map(k => el('button', { class: c === k ? 'active' : '', onclick: () => { App.sub.child = k; UI.rerender(); } }, CHILDREN[k].name))));
  const tabs = [['summary', 'الخلاصة'], ['map', 'خريطة المصحف'], ['yellow', 'القائمة الصفراء'], ['mut', 'المتشابهات'], ['cards', 'البطاقات'], ['history', 'سجل الطفل']];
  wrap.append(el('div', { class: 'tabs' }, tabs.map(([k, n]) => el('button', { class: tab === k ? 'active' : '', onclick: () => { App.sub.ctab = k; UI.rerender(); } }, n))));
  if (tab === 'summary') wrap.append(ChildSummary(c));
  if (tab === 'map') wrap.append(MushafMap(c));
  if (tab === 'yellow') wrap.append(YellowView(c));
  if (tab === 'mut') wrap.append(MutView(c));
  if (tab === 'cards') wrap.append(CardsView(c));
  if (tab === 'history') wrap.append(HistoryView(c));
  return wrap;
};

function ChildSummary(c) {
  const h = healthOf(c); const d = h.st; const wrap = el('div');
  const greens = d.far.filter(p => d.pages[p].color === 'green').length;
  wrap.append(el('div', { class: 'card' }, el('div', { class: 'row between' }, el('h2', null, CHILDREN[c].name), el('span', null, el('span', { class: 'light ' + h.light }), ' ', lightText(h))),
    el('div', { class: 'kpi' }, el('div', null, el('div', { class: 'v' }, d.far.length), el('div', { class: 'k' }, 'صفحة في البعيد')), el('div', null, el('div', { class: 'v' }, d.near.length), el('div', { class: 'k' }, 'صفحة في القريب')), el('div', null, el('div', { class: 'v' }, d.quota), el('div', { class: 'k' }, 'حصة البعيد اليومية'))),
    el('div', { class: 'kpi', style: 'margin-top:10px' }, el('div', null, el('div', { class: 'v' }, h.examGreen == null ? '—' : `${h.examClean}/${h.examN}`), el('div', { class: 'k' }, h.examDay ? `أخضر في فحص ${fmtDay(h.examDay)}` : 'لم يُفحص بعد')), el('div', null, el('div', { class: 'v' }, h.gateFails), el('div', { class: 'k' }, 'سقوط بوابة هذا الأسبوع')), el('div', null, el('div', { class: 'v' }, d.far.length ? d.maxGap : '—'), el('div', { class: 'k' }, 'أطول صفحة بلا تسميع (يوم)')))));
  wrap.append(el('div', { class: 'card' }, el('h3', null, 'الآن'),
    el('div', null, 'الجديد التالي: ', el('b', null, d.nextNew ? pagesText(d, d.nextNew, d.nextLines) : '—')),
    el('div', null, 'الجزء الحالي: ', el('b', null, d.currentJuz ? juzLabel(d.currentJuz) : '—'), d.near.length ? ` · القريب: ${d.near[0]}–${d.near[d.near.length - 1]}` : ''),
    el('div', null, 'حصة البعيد اليوم: ', el('b', null, d.todayFar.length ? d.todayFar.join('، ') : '—')),
    el('div', null, 'آخر صفحة جديدة: ', el('b', null, d.lastNewPage ? pageLabel(d.lastNewPage) : '—'))));
  const hs = handoffs(h => h.child === c); if (hs.length) wrap.append(el('div', { class: 'card' }, el('h3', null, 'بطاقات التسليم'), hs.slice(-5).reverse().map(h => handoffCard(h))));
  if (d.paused || d.reduced) wrap.append(el('div', { class: 'alert' }, d.paused ? 'الجديد متوقف بقرار آية. ' : '', d.reduced ? 'المقدار مخفَّض إلى نصف صفحة بقرار آية.' : ''));
  if (App.can('canDecide')) wrap.append(el('div', { class: 'card' }, el('h3', null, 'قرارات آية'), el('p', { class: 'small muted' }, 'القرار يغيّر ما يقترحه البرنامج في الجلسة التالية، ويبقى حتى يُلغى بقرار آخر.'), el('div', { class: 'btns' },
    el('button', { class: 'btn-y', onclick: () => decisionModal(c, 'repair') }, 'صباح إصلاح'),
    d.reduced ? el('button', { class: 'btn-g', onclick: () => decisionModal(c, 'restore') }, 'استعادة المقدار') : (c !== 'karim' ? el('button', { class: 'btn-y', onclick: () => decisionModal(c, 'reduce') }, 'تخفيض إلى نصف صفحة') : null),
    d.paused ? el('button', { class: 'btn-g', onclick: () => decisionModal(c, 'resume') }, 'استئناف الجديد') : el('button', { class: 'btn-r', onclick: () => decisionModal(c, 'pause') }, 'توقف الجديد'),
    el('button', { class: 'btn-g', onclick: () => juzPassModal(c) }, c === 'karim' ? 'اعتماد سورة' : 'إجازة جزء'))));
  const decisions = Store.events.filter(e => e.type === 'decision' && e.child === c).slice(-5).reverse();
  if (decisions.length) wrap.append(el('div', { class: 'card' }, el('h3', null, 'آخر القرارات'), decisions.map(e => el('div', { class: 'small' }, `${fmtDay(e.day)} · ${decisionName(e.kind)}: ${e.text || ''}`))));
  return wrap;
}

function decisionModal(c, kind) {
  const t = el('textarea', { placeholder: 'السبب بإيجاز' });
  const bg = UI.modal(decisionName(kind), el('div', null, el('p', { class: 'muted small' }, `${CHILDREN[c].name}`), t), [el('button', { class: 'primary', onclick: () => { Store.add({ type: 'decision', child: c, kind, text: t.value.trim() }); bg.remove(); UI.toast('سُجّل القرار'); UI.rerender(); } }, 'تسجيل')]);
}
function juzPassModal(c) {
  const d = deriveChild(c);
  if (c === 'karim') {
    const surahs = [...new Set(d.near.flatMap(p => surahsOfPage(p)))];
    const sel = el('select', null, surahs.map(s => el('option', { value: s }, SURAH_NAMES[s - 1])));
    const bg = UI.modal('اعتماد سورة', el('div', null, el('p', { class: 'small muted' }, 'تُعتمد السورة بعد تسميعها خضراء مرتين في يومين متباعدين. تنتقل الصفحة إلى البعيد حين تُعتمد كل السور التي فيها.'), sel), [el('button', { class: 'primary', onclick: () => { const s = Number(sel.value); Store.add({ type: 'surah_passed', child: c, surah: s }); Store.add({ type: 'decision', child: c, kind: 'surah', text: SURAH_NAMES[s - 1] }); bg.remove(); UI.rerender(); } }, 'اعتماد')]);
    return;
  }
  const juzs = [...new Set(d.near.map(p => juzOfPage(p)))].sort((a, b) => b - a);
  if (!juzs.length) { UI.toast('لا صفحات في القريب'); return; }
  const sel = el('select', null, juzs.map(j => el('option', { value: j }, `${juzLabel(j)} · ${d.near.filter(p => juzOfPage(p) === j).length} صفحة في القريب`)));
  /* اختبار الإجازة: خطوة اختيارية تُسجَّل نتيجتها حين تُنفَّذ؛ عدم تنفيذها ليس فشلاً.
     الإجازة تستند إلى اختبار سابق يُختار صراحةً، أو تُسجَّل «بلا اختبار» صراحةً. */
  const basis = el('select');
  const refreshBasis = () => { const ex = juzExams(c, Number(sel.value)).slice().reverse(); basis.innerHTML = ''; basis.append(el('option', { value: '' }, 'إجازة بلا الاستناد إلى اختبار (تُوثَّق كذلك)')); for (const x of ex) basis.append(el('option', { value: x.id }, `اختبار ${fmtDay(x.day)}: ${resultName(x.result)}${x.prompts != null ? ' · تلقين ' + x.prompts : ''}${x.note ? ' — ' + x.note : ''}`)); if (ex.length) basis.value = ex[0].id; };
  sel.addEventListener('change', refreshBasis); refreshBasis();
  const exRes = el('select', null, [['', 'لا تسجيل اختبار جديد'], ['clean', 'مستقل — بلا تلقين'], ['yellow', 'بمساعدة (تلقين 1–2)'], ['red', 'توقف / 3 تلقينات+']].map(([v, n]) => el('option', { value: v }, n)));
  const exPrompts = el('input', { type: 'number', min: 0, max: 99, placeholder: 'عدد التلقينات', style: 'width:130px' });
  const exNote = el('input', { placeholder: 'ملاحظة الاختبار (اختياري)' });
  const syncPrompts = () => { if (exRes.value === 'clean') { exPrompts.value = '0'; exPrompts.disabled = true; } else if (exRes.value === 'yellow') { exPrompts.disabled = false; exPrompts.min = 1; exPrompts.max = 2; if (!(Number(exPrompts.value) >= 1 && Number(exPrompts.value) <= 2)) exPrompts.value = '1'; } else { exPrompts.disabled = exRes.value === ''; exPrompts.min = 0; exPrompts.max = 99; } };
  exRes.addEventListener('change', syncPrompts); syncPrompts();
  const newExam = () => { if (!exRes.value) return null; const pr = exPrompts.value === '' ? undefined : Number(exPrompts.value); if (exRes.value === 'yellow' && !(pr >= 1 && pr <= 2)) { UI.toast('«بمساعدة» تعني تلقيناً أو اثنين'); return false; } if (exRes.value === 'clean' && pr > 0) { UI.toast('«مستقل» يعني بلا تلقين'); return false; } return { type: 'juz_exam', child: c, juz: Number(sel.value), result: exRes.value, prompts: exRes.value === 'clean' ? 0 : pr, note: exNote.value.trim() || undefined }; };
  const bg = UI.modal('إجازة جزء', el('div', null, el('p', { class: 'small' }, 'يُجاز الجزء بعد تسميعه كاملاً لآية يوم الخميس بلا تلقين، فتنتقل صفحاته إلى البعيد.'), sel,
      label('الاستناد إلى اختبار إجازة سابق'), basis,
      label('أو تسجيل اختبار جديد الآن'), el('div', { class: 'row' }, exRes, exPrompts), exNote),
    [el('button', { class: 'ghost', onclick: () => { const ex = newExam(); if (!ex) { if (ex === null) UI.toast('اختاري نتيجة الاختبار'); return; } Store.add(ex); UI.toast('سُجّل الاختبار دون إجازة'); bg.remove(); UI.rerender(); } }, 'تسجيل الاختبار فقط'),
     el('button', { class: 'primary', onclick: () => { const juz = Number(sel.value);
      const ex = newExam(); if (ex === false) return;
      let basisEv = null, exId;
      if (ex) { basisEv = Store.add(ex); exId = basisEv.id; } else if (basis.value) { basisEv = Store.events.find(e => e.id === basis.value); exId = basis.value; }
      const go = () => { Store.add({ type: 'juz_passed', child: c, juz, exam: exId }); Store.add({ type: 'decision', child: c, kind: 'juz', text: juzLabel(juz) + (basisEv ? ` — استناداً إلى اختبار ${fmtDay(basisEv.day)}: ${resultName(basisEv.result)}` : ' — بلا الاستناد إلى اختبار') }); bg.remove(); UI.rerender(); };
      if (!basisEv) UI.confirm('إجازة الجزء بلا الاستناد إلى اختبار مسجل؟ (تُوثَّق)', go);
      else if (basisEv.result !== 'clean') UI.confirm(`الاختبار المستند إليه (${fmtDay(basisEv.day)}) نتيجته «${resultName(basisEv.result)}». إجازة الجزء رغم ذلك؟ (تُوثَّق)`, go);
      else go(); } }, 'إجازة')]);
}

function MushafMap(c) {
  const d = deriveChild(c); const today = todayKey();
  const grid = el('div', { class: 'map' });
  const cell = p => {
    const pg = d.pages[p]; let cls = 'c ' + (pg.layer === 'none' ? '' : pg.layer);
    if (pg.layer === 'far' && pg.color) cls = 'c ' + pg.color;
    const gap = pg.layer === 'far' ? ((pg.lastFar || pg.lastReview) ? daysBetween(pg.lastFar || pg.lastReview, today) : 99) : 0;
    if (pg.layer === 'far' && gap > 12) cls += ' stale';
    if (d.todayNew.includes(p) || d.todayFar.includes(p)) cls += ' today';
    return el('div', { class: cls, title: `ص${p}`, onclick: () => pageModal(c, p) }, p);
  };
  /* الأجزاء المحفوظة أو الجارية أولاً (مفصّلة)، ثم الباقي مطوي */
  const touched = new Set(); for (let p = 1; p <= 604; p++) if (d.pages[p].layer !== 'none') for (let j = 1; j <= 30; j++) if (p >= JUZ_START[j - 1] && p < (JUZ_START[j] || 605)) touched.add(j);
  const showAll = App.sub.mapAll;
  for (let j = 30; j >= 1; j--) {
    if (!touched.has(j) && !showAll) continue;
    const from = JUZ_START[j - 1], to = (JUZ_START[j] || 605) - 1;
    grid.append(el('div', { class: 'jl' }, `الجزء ${j} · ص${from}–${to}`));
    const g = el('div', { class: 'juz' }); for (let p = from; p <= to; p++) g.append(cell(p)); grid.append(g);
  }
  grid.append(el('button', { class: 'ghost small', style: 'margin-top:8px', onclick: () => { App.sub.mapAll = !showAll; UI.rerender(); } }, showAll ? 'إخفاء الأجزاء غير المحفوظة' : 'إظهار كل الأجزاء الثلاثين'));
  return el('div', { class: 'card' }, el('h2', null, `خريطة المصحف · ${CHILDREN[c].name}`),
    el('div', { class: 'legend', style: 'margin-bottom:8px' }, lg('#2e9e5b', 'بعيد أخضر'), lg('#e0a800', 'أصفر'), lg('#d14b3f', 'أحمر'), lg('#cfe9d7', 'بعيد بلا لون'), lg('#cfe0f5', 'قريب'), lg('#f3e3b8', 'جديد'), lg('#ececec', 'لم يُحفظ')),
    el('p', { class: 'small muted' }, 'الإطار الأحمر: تجاوزت 12 يوماً بلا تسميع. الإطار الأزرق: صفحات اليوم. اضغطي أي صفحة لتاريخها.'), grid);
}
function lg(color, t) { return el('span', null, el('i', { style: 'background:' + color }), t); }

function pageModal(c, p) {
  const evs = Store.events.filter(e => e.child === c && e.page === p).slice().reverse();
  const d = deriveChild(c); const pg = d.pages[p];
  const body = el('div', null, el('p', null, `الطبقة: ${({ far: 'البعيد', near: 'القريب', new: 'الجديد', none: 'لم تُحفظ' })[pg.layer]} · اللون: `, pg.color ? resultPill(pg.color === 'green' ? 'clean' : pg.color) : '—', ` · آخر تسميع: ${pg.lastReview ? fmtDay(pg.lastReview) : '—'}`));
  if (App.can('canColor')) {
    const layerSel = el('select', null, [['none', 'لم تُحفظ'], ['near', 'القريب'], ['far', 'البعيد']].map(([v, n]) => el('option', { value: v }, n))); layerSel.value = pg.layer === 'new' ? 'near' : pg.layer;
    const colSel = el('select', null, [['', 'بلا لون'], ['green', 'أخضر'], ['yellow', 'أصفر'], ['red', 'أحمر']].map(([v, n]) => el('option', { value: v }, n))); colSel.value = pg.color || '';
    body.append(el('details', null, el('summary', null, 'تعديل الطبقة أو اللون (الجرد الأولي)'), el('div', { class: 'row' }, layerSel, colSel, el('button', { onclick: () => { Store.add({ type: 'layer', child: c, page: p, layer: layerSel.value, color: colSel.value || null }); UI.toast('حُفظ'); bg.remove(); UI.rerender(); } }, 'حفظ'))));
  }
  const tbl = el('table', null, el('tbody', null, evs.slice(0, 40).map(e => el('tr', null, el('td', { style: 'white-space:nowrap' }, fmtDay(e.day)), el('td', null, eventText(e)), el('td', { class: 'muted small' }, ROLES[e.by] ? ROLES[e.by].name : e.by)))));
  body.append(evs.length ? tbl : el('p', { class: 'muted' }, 'لا أحداث لهذه الصفحة.'));
  const bg = UI.modal(pageLabel(p), body);
}

function eventText(e) {
  const stepN = { gate: 'بوابة', first: 'تسميع أول', second: 'تسميع ثانٍ', third: 'تسميع ثالث', near: 'قريب', far: 'بعيد', exam: 'فحص', week: 'سرد الأسبوع', awael: 'أوائل الآيات', yellow: 'صفراء', cards: 'بطاقات', fluency: 'طلاقة' };
  switch (e.type) {
    case 'outcome': return ['', stepN[e.step] || e.step, e.lines ? ` (الأسطر ${e.lines[0]}–${e.lines[1]})` : '', ': ', resultPill(e.result), e.prompts ? ` · تلقين ${e.prompts}` : '', e.tajweed === 'issue' ? ' · تجويد ⚠' : '', e.meaning === 'ok' ? ' · المعنى ✓' : e.meaning === 'support' ? ' · المعنى يحتاج دعماً' : ''];
    case 'error': { const t = ERROR_TYPES.find(x => x.id === e.etype); return `خطأ ${t ? t.name : e.etype}${e.surah ? ' · ' + SURAH_NAMES[e.surah - 1] + (e.ayah ? ' ' + e.ayah : '') : ''}${e.target ? ' ← ' + SURAH_NAMES[e.target.surah - 1] + ' ' + (e.target.ayah || '') : ''}${e.note ? ' · ' + e.note : ''}`; }
    case 'color': return ['لون: ', resultPill(e.color === 'green' ? 'clean' : e.color)];
    case 'new_page': return `حفظ جديد${e.linesFrom && e.linesTo < 15 ? ` (الأسطر ${e.linesFrom}–${e.linesTo})` : ''}${e.minutes ? ` · ${e.minutes} د` : ''}`;
    case 'layer': return `جرد: ${({ far: 'بعيد', near: 'قريب', none: 'غير محفوظ' })[e.layer]}${e.color ? ' ' + e.color : ''}`;
    case 'yellow_pass': return `آية سالمة ${SURAH_NAMES[e.surah - 1]} ${e.ayah}`;
    case 'session_done': return `جلسة: ${SESSION_KINDS[e.kind] ? SESSION_KINDS[e.kind].name : e.kind} · ${{ complete: 'اكتملت', partial: 'بقي جزء', stopped: 'توقفت' }[e.status] || 'اكتملت'}${e.proxyFor ? ' · نيابةً عن ' + ROLES[e.proxyFor].name : ''}${e.reason ? ' (' + e.reason + ')' : ''}${e.note ? ' · ' + e.note : ''}`;
    case 'decision': return `قرار: ${decisionName(e.kind)} ${e.text || ''}`;
    case 'card': return 'بطاقة';
    case 'note': return `ملاحظة: ${e.text}`;
    case 'handoff': return `بطاقة تسليم إلى آية (${e.items.length} بند)`;
    case 'juz_exam': return `اختبار إجازة ${juzLabel(e.juz)}: ${resultName(e.result)}${e.prompts ? ' · تلقين ' + e.prompts : ''}${e.note ? ' — ' + e.note : ''}`;
    case 'tilawa': return `${e.kind === 'listen' ? 'سماع' : 'قراءة نظراً'} ص${Math.min(...e.pages)}–${Math.max(...e.pages)}${e.times ? ' ×' + e.times : ''}`;
    case 'session_start': return `فتح جلسة ${SESSION_KINDS[e.kind] ? SESSION_KINDS[e.kind].name : e.kind}${e.proxyFor ? ' نيابةً عن ' + ROLES[e.proxyFor].name + ' (' + e.reason + ')' : ''}`;
    case 'session_cancel': return `إلغاء جلسة ${SESSION_KINDS[e.kind] ? SESSION_KINDS[e.kind].name : e.kind}: ${e.reason}`;
    case 'fluency_page': return `صفحة الطلاقة → ص${e.page}${e.why ? ' (' + e.why + ')' : ''}`;
    case 'undo': { const t = Store.raw.find(x => x.id === e.target); return `↶ تراجع عن: ${t ? eventText(t) : e.target}${e.reason ? ' — ' + e.reason : ''}`; }
    case 'handoff_update': return `تحديث بطاقة تسليم (${e.items.length} بند)`;
    case 'handoff_status': return `بطاقة تسليم: ${{ seen: 'اطلعت', handled: 'عولجت', reopened: 'أُعيد فتحها' }[e.status]}`;
    case 'fluency_time': return `طلاقة ص${e.page}: ${e.seconds} ث`;
    case 'juz_passed': return `إجازة ${juzLabel(e.juz)}${e.exam ? ' (باختبار مسجل)' : ' (بلا اختبار مسجل)'}`;
    case 'surah_passed': return `اعتماد سورة ${SURAH_NAMES[e.surah - 1]}`;
    case 'parent_exam': return `فحص ولي الأمر: ${e.pages.join('، ')} · أخضر ${e.green}/${e.pages.length}`;
    default: return e.type;
  }
}

function YellowView(c) {
  const y = yellowList(c);
  const row = it => el('div', { class: 'ayahrow' }, el('span', null, `${SURAH_NAMES[it.surah - 1]} ${it.ayah} · ص${it.page}`, el('span', { class: 'muted small' }, ` · ${it.count} خطأ · ${Object.entries(it.types).map(([k, v]) => (ERROR_TYPES.find(t => t.id === k) || {}).short + ' ' + v).join('، ')}`)), el('span', { class: 'pill ' + (it.passes.length >= 3 ? 'g' : 'y') }, `سالمة ${it.passes.length}/3`));
  return el('div', null, el('div', { class: 'card' }, el('h2', null, `القائمة الصفراء · ${y.active.length}`), y.active.length ? y.active.map(row) : el('p', { class: 'muted' }, 'لا آيات.')), el('div', { class: 'card' }, el('details', null, el('summary', null, `مشطوبة · ${y.cleared.length}`), y.cleared.map(row))));
}
function MutView(c) {
  const list = mutashabihat(c).slice().reverse();
  return el('div', { class: 'card' }, el('h2', null, 'المتشابهات'), list.length ? list.map(e => el('div', { class: 'ayahrow' }, el('span', null, `${SURAH_NAMES[e.surah - 1]} ${e.ayah} (ص${e.page}) ← ${e.target ? SURAH_NAMES[e.target.surah - 1] + ' ' + (e.target.ayah || '') : 'موضع غير مسجل'}`), el('span', { class: 'muted small' }, fmtDay(e.day)))) : el('p', { class: 'muted' }, 'لا متشابهات مسجلة.'));
}
function CardsView(c) {
  const cards = Object.values(cardsFor(c)).sort((a, b) => (a.page || 0) - (b.page || 0));
  const d = deriveChild(c);
  return el('div', { class: 'card' }, el('h2', null, 'البطاقات'), App.can('canDecide') && d.nextNew ? el('button', { onclick: () => cardModal(c, d.nextNew) }, `بطاقة الغد: ${pageLabel(d.nextNew)}`) : null,
    cards.length ? cards.map(cd => el('details', null, el('summary', null, cd.kind === 'surah' ? 'سورة ' + SURAH_NAMES[Number(cd.key.slice(1)) - 1] : pageLabel(cd.page)), el('div', { class: 'small', html: cardHtml(cd) }), App.can('canDecide') ? el('button', { class: 'ghost small', onclick: () => cardModal(c, cd.page) }, 'تعديل') : null)) : el('p', { class: 'muted' }, 'لا بطاقات بعد.'));
}
function HistoryView(c) {
  const days = {}; for (const e of Store.events.filter(e => e.child === c)) (days[e.day] = days[e.day] || []).push(e);
  const keys = Object.keys(days).sort().reverse().slice(0, 30);
  return el('div', { class: 'card' }, el('h2', null, 'آخر 30 يوماً'), keys.length ? keys.map(k => { const evs = days[k]; const news = evs.filter(e => e.type === 'new_page').map(e => e.page); const outs = evs.filter(e => e.type === 'outcome'); const errs = evs.filter(e => e.type === 'error').length; return el('div', { class: 'ayahrow' }, el('span', null, fmtDay(k)), el('span', { class: 'small muted' }, `جديد: ${news.join('،') || '—'} · تسميعات: ${outs.length} · أخطاء: ${errs} · أخضر: ${outs.filter(o => o.result === 'clean').length}`)); }) : el('p', { class: 'muted' }, 'لا سجل بعد.'));
}

/* ===== السجلات والبحث ===== */
Views.logs = function () {
  const f = App.sub.logf || (App.sub.logf = { child: '', type: '', q: '', day: '' });
  const wrap = el('div');
  const childSel = el('select', { onchange: e => { f.child = e.target.value; UI.rerender(); } }, el('option', { value: '' }, 'كل الأطفال'), CHILD_ORDER.map(k => el('option', { value: k }, CHILDREN[k].name))); childSel.value = f.child;
  const typeSel = el('select', { onchange: e => { f.type = e.target.value; UI.rerender(); } }, [['', 'كل الأنواع'], ['error', 'أخطاء'], ['outcome', 'تسميعات'], ['color', 'ألوان'], ['new_page', 'حفظ جديد'], ['decision', 'قرارات'], ['session_done', 'جلسات'], ['note', 'ملاحظات'], ['card', 'بطاقات'], ['handoff', 'تسليم'], ['undo', 'تراجع']].map(([v, n]) => el('option', { value: v }, n))); typeSel.value = f.type;
  const q = el('input', { placeholder: 'بحث: رقم صفحة، اسم سورة، كلمة من ملاحظة', value: f.q, oninput: e => { f.q = e.target.value; render(); } });
  const dayIn = el('input', { type: 'date', value: f.day, onchange: e => { f.day = e.target.value; render(); } });
  wrap.append(el('div', { class: 'card' }, el('div', { class: 'row' }, childSel, typeSel, dayIn), q));
  const list = el('div', { class: 'card' }); wrap.append(list);
  function render() {
    list.innerHTML = '';
    let evs = Store.raw.slice().reverse(); const undone = new Set(Store.raw.filter(e => e.type === 'undo').map(e => e.target));
    evs = evs.map(e => undone.has(e.id) ? Object.assign({}, e, { _undone: true }) : e);
    if (f.child) evs = evs.filter(e => e.child === f.child);
    if (f.type) evs = evs.filter(e => e.type === f.type);
    if (f.day) evs = evs.filter(e => e.day === f.day);
    if (f.q.trim()) { const ql = f.q.trim(); evs = evs.filter(e => { const s = JSON.stringify(e) + ' ' + (e.page ? pageLabel(e.page) : '') + ' ' + (e.surah ? SURAH_NAMES[e.surah - 1] : ''); return s.includes(ql); }); }
    list.append(el('div', { class: 'muted small' }, `${evs.length} سجل`), el('table', null, el('tbody', null, evs.slice(0, 200).map(e => el('tr', { style: e._undone ? 'opacity:.5;text-decoration:line-through' : '' }, el('td', { style: 'white-space:nowrap' }, fmtDay(e.day), el('div', { class: 'muted small' }, chinaHHMM(e.ts))), el('td', null, e.child && CHILDREN[e.child] ? el('b', null, CHILDREN[e.child].name + ' · ') : null, e.page ? `ص${e.page} · ` : '', eventText(e)), el('td', { class: 'muted small' }, ROLES[e.by] ? ROLES[e.by].name : e.by))))));
  }
  render(); return wrap;
};

/* ===== الخميس ===== */
Views.thursday = function () {
  const wrap = el('div'); const ws = weekStartKey(App.now());
  wrap.append(el('div', { class: 'card' }, el('h2', null, 'أدوات الخميس'), el('p', { class: 'muted small' }, 'الجلسات نفسها تُفتح من جدول اليوم. هنا الأدوات المساعدة وخلاصة الأسبوع.')));
  for (const c of CHILD_ORDER) {
    const d = deriveChild(c); const y = yellowList(c); const mut = mutashabihat(c, ws);
    const weekPages = [...new Set(Store.events.filter(e => e.type === 'new_page' && e.child === c && e.day >= ws).map(e => e.page))];
    wrap.append(el('div', { class: 'card' }, el('h3', null, CHILDREN[c].name),
      el('div', { class: 'small' }, `صفحات الأسبوع: ${weekPages.join('، ') || '—'} · الصفراء النشطة: ${y.active.length} · متشابهات الأسبوع: ${mut.length} · البعيد: ${d.far.length}`),
      mut.length ? el('details', null, el('summary', null, 'قائمة المتشابهات للمجلس'), MutashabihBox(c)) : null,
      y.active.length ? el('details', null, el('summary', null, 'الصفراء للكتابة والتصفية'), y.active.map(it => el('div', { class: 'small' }, `• ${SURAH_NAMES[it.surah - 1]} ${it.ayah} (ص${it.page})${it.target ? ' ← ' + SURAH_NAMES[it.target.surah - 1] + ' ' + (it.target.ayah || '') : ''}`))) : null));
  }
  wrap.append(el('div', { class: 'card' }, el('h3', null, 'خلاصة الأسبوع'), el('pre', { style: 'direction:rtl;text-align:right' }, weeklySummaryText()), el('button', { onclick: () => { navigator.clipboard && navigator.clipboard.writeText(weeklySummaryText()); UI.toast('نُسخت'); } }, 'نسخ الخلاصة')));
  return wrap;
};

function weeklySummaryText() {
  const ws = weekStartKey(App.now()); const lines = [`خلاصة الأسبوع من ${fmtDay(ws)}`];
  for (const c of CHILD_ORDER) {
    const h = healthOf(c); const d = h.st; const evs = Store.events.filter(e => e.child === c && e.day >= ws);
    const news = [...new Set(evs.filter(e => e.type === 'new_page').map(e => e.page))];
    const outs = effectiveOutcomes(e => e.child === c && e.day >= ws); const errs = evs.filter(e => e.type === 'error');
    const sess = new Set(evs.filter(e => e.type === 'session_done').map(e => e.key)).size;
    const decisions = evs.filter(e => e.type === 'decision').map(e => decisionName(e.kind));
    lines.push(`\n${CHILDREN[c].name} — ${lightText(h)}`);
    lines.push(`• الجديد: ${news.length} ${c === 'karim' ? 'مقطع' : 'صفحة'} (${news.join('، ') || '—'})`);
    lines.push(`• التسميعات: ${outs.length}، منها سالم ${outs.filter(o => o.result === 'clean').length} · الأخطاء المسجلة: ${errs.length}`);
    lines.push(`• البوابة: ${h.gateN} تسميع، سقط ${h.gateFails} · آخر فحص خميس: ${h.examGreen == null ? 'لم يُفحص' : `${h.examClean}/${h.examN} أخضر`}`);
    lines.push(`• البعيد ${d.far.length} صفحة، أطول صفحة بلا تسميع ${d.far.length ? d.maxGap + ' يوم' : '—'} · القريب ${d.near.length} · الصفراء النشطة ${yellowList(c).active.length}`);
    lines.push(`• الجلسات المسجلة: ${sess}${decisions.length ? ' · قرارات: ' + decisions.join('، ') : ''}`);
  }
  return lines.join('\n');
}

/* ثلاث حالات مختلفة الإجراء: «لم يُقيَّم بعد» = لا بوابة ولا فحص؛ «لم يُقيَّم كاملاً» = تسميع ناقص لصفحة؛ «بانتظار اعتماد آية» = لون مقترح لم يُعتمد */
function lightText(h) { return h.light === 'grey' ? 'لم يُقيَّم بعد: لا بوابة ولا فحص خميس' : h.light === 'green' ? 'سليم' : h.light === 'yellow' ? 'يحتاج انتباهاً' : 'يحتاج قراراً'; }
