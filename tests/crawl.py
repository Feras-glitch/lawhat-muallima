"""مسح شامل للواجهة: كل زر في كل شاشة لكل دور، وداخل كل نوع جلسة (ومنها النيابة)، على بيانات واقعية.
بعد كل نقرة: إن ظهرت نافذة يُضغط زرها الرئيسي (ثم «نعم» إن طُلب تأكيد). أي خطأ في الواجهة (UI.errors)
أو خطأ غير معالج في الصفحة أو شاشة «تعذّر عرض» = فشل، مع اسم الشاشة والزر. الأزرار الهدّامة (خروج، حذف، تنزيل) تُستثنى."""
import asyncio, pathlib, os, json, threading, http.server, socketserver, functools, sys
from playwright.async_api import async_playwright
ROOT = pathlib.Path(__file__).resolve().parent.parent
BROWSER_OPTS = {'executable_path': '/usr/bin/google-chrome', 'args': ['--no-sandbox']} if os.path.exists('/usr/bin/google-chrome') and not os.environ.get('CI') else {'args': ['--no-sandbox']}


class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass


socketserver.TCPServer.allow_reuse_address = True

SEED = r"""(async () => {
  window.__pageErrors = []; window.addEventListener('error', e => __pageErrors.push(String(e.message))); window.addEventListener('unhandledrejection', e => __pageErrors.push(String(e.reason && e.reason.message || e.reason)));
  Sync.schedule = () => {}; Store.settings.timeOffset = Date.UTC(2026, 10, 8, 0, 30) - Date.now(); Store.saveSettings();
  const y = dayKey(new Date(App.realNow().getTime() - 86400000)), t = todayKey();
  App.setRole('aya');
  for (const c of ['c1', 'c2']) for (let p = 562; p <= 604; p++) Store.add({ type: 'layer', child: c, page: p, layer: 'far', color: p % 7 ? 'green' : 'yellow' });
  for (let p = 595; p <= 604; p++) Store.add({ type: 'layer', child: 'c3', page: p, layer: 'far', color: 'green' });
  for (const c of ['c1', 'c2']) { Store.add({ type: 'new_page', child: c, page: 542, linesFrom: 1, linesTo: 15, day: y }); Store.add({ type: 'outcome', child: c, page: 542, step: 'gate', result: 'yellow', prompts: 1 }); }
  Store.add({ type: 'new_page', child: 'c3', page: 594, linesFrom: 1, linesTo: 4, day: y });
  Store.add({ type: 'error', child: 'c1', page: 542, surah: 58, ayah: 2, etype: 'jump', target: { surah: 79, ayah: 2 } });
  Store.add({ type: 'error', child: 'c3', page: 594, surah: 91, ayah: 5, etype: 'prompt', lines: [1, 4] });
  Store.add({ type: 'card', child: 'c1', page: 542, key: 'p542', kind: 'page', q1: 'س', q2: 'م', q3: 'ض', q4: 'ت' });
  Store.add({ type: 'card', child: 'c3', page: 604, key: 's113', kind: 'surah', surah: 113, story: 'الفلق' });
  Store.add({ type: 'outcome', child: 'c1', page: 570, step: 'exam', result: 'clean' });
  Store.add({ type: 'note', child: 'c2', text: 'ملاحظة' });
  App.setRole('asst');
  const s = PLAN.find(x => x.kind === 'noon' && x.child === 'c1'); startSession(s); const a = Store.settings.active; a.steps = ['second'];
  Store.add({ type: 'outcome', child: 'c1', page: 562, step: 'far', result: 'red', prompts: 3 });
  Store.add({ type: 'note', child: 'c1', text: 'طلب اعتماد: فحص الخميس — سُمّع' });
  await commitEnd(s, a, 'partial', ['far', 'cards'], null, 'ملاحظة الجلسة');
  App.setRole('parent'); Store.add({ type: 'outcome', child: 'c1', page: 571, step: 'exam', result: 'yellow', prompts: 1, parent: true });
  await Store.durable(); return Store.raw.length;
})()"""

CRAWL = r"""async ([screens, fill]) => {
  const SKIP = ['خروج', 'حذف', 'مسح', 'فصل', 'تنزيل', 'تصدير', 'العودة للاتصال', 'إعداد ملفات الاستعادة', 'الوقت الحقيقي', 'ضبط'];
  const wait = ms => new Promise(r => setTimeout(r, ms));
  const report = []; let clicks = 0;
  const setup = sc => {
    document.querySelectorAll('.modal-bg, .present').forEach(x => x.remove());
    if (!App.role || App.role.id !== sc.role) App.setRole(sc.role);
    if (sc.session) {
      const s = PLAN[sc.session.idx]; const key = sessionKey(s, todayKey()); const act = Store.settings.active;
      if (!act || act.key !== key || act.role !== sc.role) { Store.settings.active = null; startSession(s, sessionStatus(s, todayKey()), sc.session.proxy ? { orig: s.teacher, reason: 'اختبار' } : undefined); }
      const a2 = Store.settings.active; if (a2) { a2.all = true; }
    } else if (Store.settings.active) { Store.settings.active = null; }
    App.view = sc.view; Object.assign(App.sub, sc.sub || {}); UI.rerender();
  };
  for (const sc of screens) {
    setup(sc);
    if (document.body.innerText.includes('تعذّر عرض هذه الشاشة')) { report.push({ screen: sc.name, label: '(عرض)', errors: [document.querySelector('main').innerText.slice(0, 200)] }); continue; }
    const n = document.querySelectorAll('main button').length;
    for (let i = 0; i < n; i++) {
      setup(sc);
      const b = [...document.querySelectorAll('main button')][i]; if (!b || b.disabled) continue;
      const label = b.textContent.trim().slice(0, 40);
      if (SKIP.some(w => label.includes(w))) continue;
      const e0 = UI.errors.length, p0 = __pageErrors.length; clicks++;
      try { b.click(); } catch (e) { __pageErrors.push('click: ' + e.message); }
      await wait(15);
      for (let k = 0; k < 3; k++) {
        const m = [...document.querySelectorAll('.modal')].pop(); if (!m) break;
        if (fill) { /* المرور الثاني: ملء الحقول الفارغة بقيم معقولة قبل الحفظ، ليُختبر مسار الحفظ لا رسائل التحقق وحدها */
          for (const inp of m.querySelectorAll('input, textarea')) { if (inp.value || inp.disabled || inp.type === 'file' || inp.type === 'checkbox') continue;
            inp.value = inp.type === 'number' ? (inp.min && Number(inp.min) > 0 ? inp.min : '1') : inp.type === 'date' ? todayKey() : 'اختبار'; inp.dispatchEvent(new Event('input', { bubbles: true })); }
          const tb = [...m.querySelectorAll('.btns button.ghost')].find(x => !x.classList.contains('on') && x.textContent.trim().length > 1); if (tb && k === 0) try { tb.click(); } catch (e) {}
        }
        const p = m.querySelector('button.primary') || [...m.querySelectorAll('button')].find(x => x.textContent === 'نعم');
        if (!p) break; try { p.click(); } catch (e) { __pageErrors.push('modal: ' + e.message); } await wait(15);
      }
      document.querySelectorAll('.modal-bg, .present').forEach(x => x.remove());
      await Store.durable();
      const bad = document.body.innerText.includes('تعذّر عرض هذه الشاشة');
      if (UI.errors.length > e0 || __pageErrors.length > p0 || bad) report.push({ screen: sc.name, label, errors: UI.errors.slice(e0), page: __pageErrors.slice(p0), render: bad });
    }
  }
  return { report, clicks };
}"""


async def main():
    httpd = socketserver.TCPServer(('127.0.0.1', 0), functools.partial(Q, directory=str(ROOT / 'dist')))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    port = httpd.server_address[1]
    async with async_playwright() as p:
        b = await p.chromium.launch(**BROWSER_OPTS)
        ctx = await b.new_context(viewport={'width': 390, 'height': 844}, locale='ar', timezone_id='Africa/Cairo', accept_downloads=True)
        pg = await ctx.new_page()
        perr = []; pg.on('pageerror', lambda e: perr.append(str(e))); pg.on('dialog', lambda d: asyncio.ensure_future(d.accept()))
        await pg.goto(f'http://127.0.0.1:{port}/index.html'); await pg.wait_for_function('Store.raw && Store.idbOk')
        n = await pg.evaluate(SEED)
        plan = await pg.evaluate("PLAN.map((s, i) => ({ i, kind: s.kind, child: s.child, teacher: s.teacher }))")
        screens = []
        tabs = ['summary', 'map', 'yellow', 'mut', 'cards', 'history']
        for role, views in (('aya', ['now', 'today', 'thursday', 'logs', 'settings']), ('asst', ['now', 'today', 'thursday', 'logs', 'settings']), ('parent', ['dash', 'reports', 'logs', 'settings'])):
            for v in views:
                screens.append({'name': f'{role}/{v}', 'role': role, 'view': v})
            for c in ('c1', 'c2', 'c3'):
                for t in tabs:
                    screens.append({'name': f'{role}/children/{c}/{t}', 'role': role, 'view': 'children', 'sub': {'child': c, 'ctab': t}})
        seen = set()
        for s in plan:  # جلسة واحدة لكل نوع وطفل، لصاحبتها؛ وجلسات آية نيابةً للمساعدة
            k = (s['kind'], s['child'])
            if k in seen: continue
            seen.add(k)
            screens.append({'name': f"{s['teacher']}/جلسة/{s['kind']}/{s['child']}", 'role': s['teacher'], 'view': 'now', 'session': {'idx': s['i']}})
            if s['teacher'] == 'aya':
                screens.append({'name': f"asst/نيابة/{s['kind']}/{s['child']}", 'role': 'asst', 'view': 'now', 'session': {'idx': s['i'], 'proxy': True}})
        out = await pg.evaluate(CRAWL, [screens, False])
        out2 = await pg.evaluate(CRAWL, [screens, True])
        out = {'report': out['report'] + [dict(r, pass2=True) for r in out2['report']], 'clicks': out['clicks'] + out2['clicks']}
        await b.close()
    httpd.shutdown()
    rep = out['report']
    print(json.dumps({'seeded': n, 'screens': len(screens), 'clicks': out['clicks'], 'failures': len(rep)}, ensure_ascii=False))
    for r in rep:
        print('FAIL', json.dumps(r, ensure_ascii=False)[:400])
    if perr:
        print('PAGEERRORS', perr[:10])
    if rep or perr:
        sys.exit(1)
    print(f"CRAWL OK ({len(screens)} شاشة، {out['clicks']} نقرة)")

asyncio.run(main())
