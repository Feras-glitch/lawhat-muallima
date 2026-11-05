/* ===== وضع العرض: شاشة نظيفة تُشارك مع الأطفال في برنامج الاجتماع ===== */
function openPresent(s) {
  const kids = childrenOf(s); let child = kids[0]; let mode = 'page';
  const bg = el('div', { class: 'present' });
  const render = () => {
    bg.innerHTML = '';
    const d = deriveChild(child); const cards = cardsFor(child);
    const page = contextPage(s, child);
    const top = el('div', { class: 'ptop' },
      el('div', { class: 'row' }, kids.length > 1 ? kids.map(k => el('button', { class: child === k ? 'primary' : 'ghost', onclick: () => { child = k; render(); } }, CHILDREN[k].name)) : el('span', { class: 'big' }, CHILDREN[child].name)),
      el('div', { class: 'row' }, [['page', 'الصفحة'], ['far', 'حصة البعيد'], ['card', 'البطاقة'], ['mut', 'المتشابهات'], ['yellow', 'الصفراء']].map(([m, n]) => el('button', { class: mode === m ? 'primary' : 'ghost', onclick: () => { mode = m; render(); } }, n)), el('button', { class: 'danger', onclick: () => bg.remove() }, '✕ إغلاق')));
    const body = el('div', { class: 'pbody' }); const add = (...x) => body.append(...x.flat().filter(v => v !== null && v !== false && v !== undefined));
    if (mode === 'page') add(el('div', { class: 'phuge' }, page ? `صفحة ${page}` : '—'), el('div', { class: 'pbig' }, page ? surahsOfPage(page).map(n => SURAH_NAMES[n - 1]).join(' · ') : ''), child === 'karim' && d.nextLines && page === d.nextNew ? el('div', { class: 'pbig' }, `الأسطر ${d.nextLines[0]}–${d.nextLines[1]}`) : null, el('div', { class: 'muted' }, `${juzLabel(juzOfPage(page || 1))} · مصحف المدينة`));
    if (mode === 'far') add(el('div', { class: 'pbig' }, 'صفحات المراجعة اليوم'), el('div', { class: 'pchips' }, d.todayFar.length ? d.todayFar.map(p => el('span', { class: 'pchip' }, p)) : el('span', { class: 'muted' }, 'لا صفحات')));
    if (mode === 'card') { const key = child === 'karim' ? 's' + surahsOfPage(page || 1)[0] : 'p' + page; const c = cards[key]; add(el('div', { class: 'pbig' }, child === 'karim' ? 'سورة ' + SURAH_NAMES[surahsOfPage(page || 1)[0] - 1] : `بطاقة صفحة ${page}`), c ? el('div', { class: 'pcard', html: cardHtml(c) }) : el('div', { class: 'muted' }, 'لا بطاقة لهذه الصفحة بعد')); }
    if (mode === 'mut') { const list = mutashabihat(child, weekStartKey(App.now())); add(el('div', { class: 'pbig' }, 'المتشابهات'), list.length ? list.map(e => el('div', { class: 'pline' }, `${SURAH_NAMES[e.surah - 1]} ${e.ayah} (ص${e.page})  ⟷  ${e.target ? SURAH_NAMES[e.target.surah - 1] + ' ' + (e.target.ayah || '') : '؟'}`)) : el('div', { class: 'muted' }, 'لا متشابهات هذا الأسبوع')); }
    if (mode === 'yellow') { const y = yellowList(child).active; add(el('div', { class: 'pbig' }, 'آيات نعيدها'), y.length ? y.map(it => el('div', { class: 'pline' }, `${SURAH_NAMES[it.surah - 1]} ${it.ayah} · صفحة ${it.page}`)) : el('div', { class: 'muted' }, 'لا آيات')); }
    bg.append(top, body);
  };
  render(); document.body.append(bg);
}
