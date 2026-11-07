"""اختبار ضغط: سنة استخدام كاملة (3 أطفال × 5 أيام × 50 أسبوعاً) ثم قياس الحجم والزمن والصحة."""
import asyncio, pathlib, json, time
from playwright.async_api import async_playwright
import os
BROWSER_OPTS = {'executable_path': '/usr/bin/google-chrome', 'args': ['--no-sandbox']} if os.path.exists('/usr/bin/google-chrome') and not os.environ.get('CI') else {'args': ['--no-sandbox']}
HTML = pathlib.Path('dist/index.html').resolve()
import threading, http.server, socketserver, functools
def serve():
    class Q(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    handler = functools.partial(Q, directory=str(HTML.parent))
    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.TCPServer(('127.0.0.1', 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd.server_address[1]
PORT = serve()
URL = f'http://127.0.0.1:{PORT}/index.html'
GEN = r"""
async (weeks) => {
  const out = { days: 0 };
  const dayMs = 86400000;
  const base = Date.UTC(2026, 10, 7, 0, 0); // السبت 7 نوفمبر 2026 بتوقيت بكين = 6 نوفمبر 16:00 UTC
  const setT = (dayIdx, h, m) => { Store.settings.timeOffset = (base - 8 * 3600000 + dayIdx * dayMs + h * 3600000 + m * 60000) - Date.now(); };
  // الجرد
  setT(0, 6, 0); App.setRole('aya');
  for (const c of ['c1', 'c2']) for (let p = 562; p <= 604; p++) Store.add({ type: 'layer', child: c, page: p, layer: 'far', color: 'green' });
  for (let p = 595; p <= 604; p++) Store.add({ type: 'layer', child: 'c3', page: p, layer: 'far', color: 'green' });
  let rnd = 7; const R = () => { rnd = (rnd * 1103515245 + 12345) & 0x7fffffff; return rnd / 0x7fffffff; };
  const t0 = performance.now();
  for (let d = 0; d < weeks * 7; d++) {
    const dow = (6 + d) % 7; // 6=السبت
    if (dow === 5) continue; // الجمعة
    setT(d, 7, 5);
    if (dow === 4) { // الخميس: فحص
      App.setRole('aya');
      for (const c of CHILD_ORDER) { const st = deriveChild(c); const pool = st.far.slice(); for (let i = 0; i < Math.min(5, pool.length); i++) { const p = pool.splice(Math.floor(R() * pool.length), 1)[0]; Store.add({ type: 'outcome', child: c, page: p, step: 'exam', result: R() < 0.85 ? 'clean' : 'yellow' }); } }
      continue;
    }
    // الصباح: آية — البوابة والحفظ والتسميع الأول
    App.setRole('aya');
    for (const c of CHILD_ORDER) {
      const st = deriveChild(c); const g = lastNewFor(c, true);
      if (g) Store.add({ type: 'outcome', child: c, page: g.page, step: 'gate', result: R() < 0.9 ? 'clean' : 'yellow', prompts: 0, meaning: 'ok', lines: c === 'c3' ? g.lines : undefined });
      if (st.nextNew) { const lines = st.nextLines; Store.add({ type: 'new_page', child: c, page: st.nextNew, linesFrom: lines[0], linesTo: c === 'c3' ? lines[1] : 15, minutes: 20 });
        Store.add({ type: 'outcome', child: c, page: st.nextNew, step: 'first', result: 'clean', prompts: 0, meaning: 'ok', lines: c === 'c3' ? lines : undefined }); }
    }
    // الظهر: المساعدة — الثاني والبعيد والأخطاء
    setT(d, 12, 55); App.setRole('asst');
    for (const c of CHILD_ORDER) {
      const st = deriveChild(c); const p = st.todayNew[st.todayNew.length - 1];
      if (p) Store.add({ type: 'outcome', child: c, page: p, step: 'second', result: 'clean', prompts: 0, meaning: 'ok' });
      for (const fp of st.todayFar) { const r = R(); Store.add({ type: 'outcome', child: c, page: fp, step: 'far', result: r < 0.9 ? 'clean' : r < 0.97 ? 'yellow' : 'red', prompts: r < 0.9 ? 0 : r < 0.97 ? 1 : 3 });
        if (r >= 0.9) { const ss = surahsOfPage(fp); Store.add({ type: 'error', child: c, page: fp, surah: ss[0], ayah: 1 + Math.floor(R() * Math.min(10, SURAH_AYAT[ss[0] - 1])), etype: R() < 0.3 ? 'jump' : 'prompt', target: R() < 0.3 ? { surah: ss[0], ayah: 2 } : undefined }); } }
    }
    // المساء: آية — الثالث والتلوين
    setT(d, 18, 30); App.setRole('aya');
    for (const c of CHILD_ORDER) {
      const st = deriveChild(c); const p = st.todayNew[st.todayNew.length - 1];
      if (p) { Store.add({ type: 'outcome', child: c, page: p, step: 'third', result: 'clean', prompts: 0, meaning: 'ok' });
        const sg = suggestColor(c, p, todayKey()); Store.add({ type: 'color', child: c, page: p, color: sg.color === 'none' ? 'green' : sg.color }); }
      for (const fp of st.todayFar) { const sg = suggestColor(c, fp, todayKey()); if (sg.color !== 'none') Store.add({ type: 'color', child: c, page: fp, color: sg.color }); }
      // إجازة جزء عند اكتمال جزء في القريب (كل صفحاته لُوِّنت) أو اعتماد سور الثالث
      if (c !== 'c3') { const juzs = [...new Set(st.near.map(p => juzOfPage(p)))]; for (const j of juzs) { const pages = juzPages(j); if (pages.every(x => st.pages[x].layer === 'near' || st.pages[x].layer === 'far') && pages.filter(x => st.pages[x].layer === 'near').length >= 19) { Store.add({ type: 'juz_passed', child: c, juz: j }); } } }
      else { const ss = [...new Set(st.near.flatMap(p => surahsOfPage(p)))]; for (const s of ss) { const sp = []; for (let p = 1; p <= 604; p++) if (surahsOfPage(p).includes(s)) sp.push(p); if (sp.every(x => st.pages[x].layer !== 'none' && st.pages[x].layer !== 'new') && !st.passedSurahs.has(s) && sp.every(x => x < 595)) { const nd = Store.events.filter(e => e.type === 'new_page' && e.child === c && sp.includes(e.page)).pop(); if (nd && daysBetween(nd.day, todayKey()) > 3) Store.add({ type: 'surah_passed', child: c, surah: s }); } } }
    }
    out.days++;
  }
  out.genMs = Math.round(performance.now() - t0);
  Store.settings.timeOffset = (base - 8 * 3600000 + weeks * 7 * dayMs + 9 * 3600000) - Date.now(); Store.saveSettings();
  return out;
}
"""
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(**BROWSER_OPTS)
        ctx = await b.new_context(viewport={'width': 390, 'height': 844}, locale='ar', timezone_id='Africa/Cairo')
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto(URL)
        await pg.click('.roles button:nth-child(1)'); await pg.fill('input[type=password]', '1111'); await pg.click('button.primary')
        weeks = int(os.environ.get("WEEKS","8"))
        gen = await pg.evaluate(f"({GEN})({weeks})")
        print('generated', gen)
        stats = await pg.evaluate(r"""() => {
          const t = (f) => { const a = performance.now(); const r = f(); return [Math.round((performance.now() - a) * 10) / 10, r]; };
          const bytes = new Blob([JSON.stringify(Store.raw)]).size;
          const keys = Object.keys(localStorage); const total = keys.reduce((s, k) => s + new Blob([localStorage.getItem(k)]).size, 0);
          const out = { idb: Store.idbOk, lsLen: (localStorage.getItem("lm_events_v1")||"").length, events: Store.raw.length, eventsMB: +(bytes / 1048576).toFixed(2), totalMB: +(total / 1048576).toFixed(2), keys };
          for (const c of CHILD_ORDER) {
            const [ms, d] = t(() => deriveChild(c)); const [hms, h] = t(() => healthOf(c)); const [yms, y] = t(() => yellowList(c));
            const gaps = d.far.map(p => { const x = d.pages[p]; const dd = x.lastFar || x.lastReview; return dd ? daysBetween(dd, todayKey()) : 99; });
            out[c] = { deriveMs: ms, healthMs: hms, yellowMs: yms, far: d.far.length, near: d.near.length, nextNew: d.nextNew, quota: d.quota, todayFar: d.todayFar.length, maxGap: Math.max(...gaps), gapsOver12: gaps.filter(g => g > 12).length, light: h.light, examGreen: h.examGreen, yellowActive: y.active.length, yellowCleared: y.cleared.length };
          }
          const views = {};
          for (const v of ['now', 'today', 'children', 'logs', 'thursday', 'settings']) { App.view = v; const [ms] = t(() => UI.rerender()); views[v] = ms; }
          App.sub.ctab = 'map'; App.view = 'children'; const [mm] = t(() => UI.rerender()); views.map = mm;
          App.sub.ctab = 'history'; const [hm] = t(() => UI.rerender()); views.history = hm;
          const [am] = t(() => alertsList()); views.alerts = am;
          App.setRole('parent'); App.view = 'dash'; const [dm] = t(() => UI.rerender()); views.parentDash = dm;
          App.view = 'reports'; const [rm] = t(() => UI.rerender()); views.reports = rm;
          out.views = views; return JSON.stringify(out); }""")
        print(stats)
        dbg = await pg.evaluate(r"""() => { const d = deriveChild('c1'); const td = todayKey(); const rows = d.far.map(p => { const x = d.pages[p]; const dd = x.lastFar || x.lastReview; return [p, x.lastFar, x.lastReview, dd ? daysBetween(dd, td) : 99]; }).filter(r => r[3] > 12);
          const farOuts = Store.events.filter(e => e.type === 'outcome' && e.child === 'c1' && e.step === 'far'); const days = [...new Set(farOuts.map(e => e.day))];
          const perDay = days.slice(-6).map(dk => [dk, farOuts.filter(e => e.day === dk).map(e => e.page).join(',')]);
          return JSON.stringify({ today: td, over12: rows, perDay, juzPassed: Store.events.filter(e => e.type === 'juz_passed' && e.child === 'c1').map(e => [e.juz, e.day]) }); }""")
        print('DBG', dbg)
        t = time.time(); await pg.reload(); await pg.wait_for_selector('nav.bottom, .login'); print('reload s', round(time.time() - t, 2))
        print('ERRS', errs[:5])
        await b.close()
asyncio.run(main())
