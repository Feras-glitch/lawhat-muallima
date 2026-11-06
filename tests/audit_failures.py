"""اختبارات الفشل المستقلة (مأخوذة من تقرير المراجعة 0.10.1): IndexedDB حقيقي عبر HTTP، وحقن أعطال في التخزين والشبكة.
كل حالة تطبع PASS أو ترفع AssertionError."""
import asyncio, pathlib, os, json, threading, http.server, socketserver, functools
from playwright.async_api import async_playwright
ROOT = pathlib.Path(__file__).resolve().parent.parent
BROWSER_OPTS = {'executable_path': '/usr/bin/google-chrome', 'args': ['--no-sandbox']} if os.path.exists('/usr/bin/google-chrome') and not os.environ.get('CI') else {'args': ['--no-sandbox']}

class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
socketserver.TCPServer.allow_reuse_address = True

def serve():
    httpd = socketserver.TCPServer(('127.0.0.1', 0), functools.partial(Q, directory=str(ROOT / 'dist')))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd

FAIL_STORAGE = """(() => { window.__put = Store.putMany.bind(Store); window.__set = Storage.prototype.setItem;
  Store.putMany = async () => false;
  Storage.prototype.setItem = function (k, v) { if (k === 'lm_events_v1') throw new Error('quota'); return window.__set.call(this, k, v); }; })()"""
FAIL_IDB_ONLY = "(() => { window.__put = Store.putMany.bind(Store); Store.putMany = async () => false; })()"
RESTORE = "(() => { if (window.__put) Store.putMany = window.__put; if (window.__set) Storage.prototype.setItem = window.__set; })()"
STATUS = "UI.statusInner().map(n => typeof n === 'string' ? n : n.textContent).join('')"

async def main():
    srv = serve(); results = []
    def ok(name, cond, data):
        results.append(name); assert cond, f'{name}: {json.dumps(data, ensure_ascii=False)}'; print('PASS', name, json.dumps(data, ensure_ascii=False)[:160])
    async with async_playwright() as p:
        b = await p.chromium.launch(**BROWSER_OPTS)
        port = srv.server_address[1]
        async def fresh():
            ctx = await b.new_context(viewport={'width': 390, 'height': 844})
            pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
            await pg.goto(f'http://127.0.0.1:{port}/index.html'); await pg.wait_for_function('Store.raw && Store.idbOk')
            await pg.evaluate("App.setRole('aya'); Sync.schedule = () => {}; UI.rerender();")
            return pg, errs
        async def reload(pg):
            await pg.reload(); await pg.wait_for_function('Store.raw && document.querySelector(".login, nav.bottom")')

        # 02: لا «حُفظ» قبل ثبوت الكتابة؛ durable() يعيد false؛ إنهاء الجلسة لا يُغلق
        pg, errs = await fresh()
        await pg.evaluate(FAIL_STORAGE)
        r = await pg.evaluate("(async () => { Store.add({ id: 'lost', type: 'note', text: 'x' }); const st1 = " + STATUS + "; const d = await Store.durable(); const st2 = " + STATUS + "; return { st1, d, st2, err: Store.storageError }; })()")
        ok('02 حالة الحفظ صادقة', 'حُفظ على الجهاز' not in r['st1'] and 'جارٍ الحفظ' in r['st1'] and r['d'] is False and 'تعذّر' in r['st2'], r)
        r = await pg.evaluate("""(async () => { Store.settings.timeOffset = Date.UTC(2026,10,9,12-8,55) - Date.now(); App.setRole('asst'); const s = PLAN.find(x => x.kind === 'noon' && x.child === 'dalal'); startSession(s);
            const a = Store.settings.active; a.steps = ['far']; const res = await commitEnd(s, a, 'partial', ['second','cards'], null, '');
            return { res, active: !!Store.settings.active, pending: !!(Store.settings.active && Store.settings.active.pendingEnd) }; })()""")
        ok('02 الجلسة لا تُغلق عند فشل الحفظ', r == {'res': False, 'active': True, 'pending': True}, r)
        await pg.evaluate(RESTORE)
        r = await pg.evaluate("""(async () => { await Store.flush(); const s = PLAN.find(x => x.kind === 'noon' && x.child === 'dalal'); const a = Store.settings.active;
            const res = await commitEnd(s, a, a.pendingEnd.status, a.pendingEnd.rem, a.pendingEnd.reason, a.pendingEnd.note);
            return { res, active: !!Store.settings.active, saved: Store.saved(), ls: localStorage.getItem('lm_events_v1') === null }; })()""")
        ok('02 إعادة المحاولة بعد التعافي تُغلق الجلسة وتمحو نسخة الطوارئ', r == {'res': True, 'active': False, 'saved': True, 'ls': True}, r)
        await reload(pg)
        n = await pg.evaluate("Store.raw.filter(e => e.id === 'lost' || e.type === 'session_done').length")
        ok('02 بعد إعادة الفتح: السجلات موجودة', n == 2, {'n': n})

        # 05: نسخة الطوارئ لا تُحيي ما حُذف
        pg, errs = await fresh()
        r = await pg.evaluate("(async () => { " + FAIL_IDB_ONLY + "; Store.add({ id: 'resurrect', type: 'note', text: 'e' }); await Store.flush(); const ls1 = !!localStorage.getItem('lm_events_v1'); " + RESTORE + "; const f = await Store.flush(); const ls2 = localStorage.getItem('lm_events_v1'); const rs = await Store.reset(); return { ls1, f, ls2, rs }; })()")
        ok('05 نسخة الطوارئ تُكتب عند الفشل وتُمحى عند التعافي', r == {'ls1': True, 'f': True, 'ls2': None, 'rs': True}, r)
        await reload(pg)
        ids = await pg.evaluate("Store.raw.map(e => e.id)")
        ok('05 الحذف بعد التعافي لا يعيد شيئاً', ids == [], {'ids': ids})
        r = await pg.evaluate("(async () => { " + FAIL_IDB_ONLY + "; Store.add({ id: 'r2', type: 'note', text: 'e' }); await Store.flush(); const ls1 = !!localStorage.getItem('lm_events_v1'); const rs = await Store.reset(); " + RESTORE + "; return { ls1, rs, ls2: localStorage.getItem('lm_events_v1') }; })()")
        await reload(pg)
        ids = await pg.evaluate("Store.raw.map(e => e.id)")
        ok('05 الحذف أثناء الفشل (دون تعافٍ) يمحو نسخة الطوارئ', r['ls1'] and r['ls2'] is None and ids == [], {**r, 'ids': ids})
        r = await pg.evaluate("(async () => { Store.add({ id: 'k1', type: 'note', text: 'a' }); const pr = Store.reset(); Store.add({ id: 'k2', type: 'note', text: 'b' }); await pr; await Store.durable(); return Store.raw.map(e => e.id); })()")
        await reload(pg)
        ids = await pg.evaluate("Store.raw.map(e => e.id)")
        ok('05 ما يُضاف بعد الحذف مباشرة يبقى وما قبله يُمحى', ids == ['k2'], {'mem': r, 'ids': ids})

        # 03: المؤشر لا يتقدم قبل ثبوت السحب
        pg, errs = await fresh()
        rows = [{'id': 'early', 'by': 'aya', 'type': 'note', 'child': None, 'inserted_at': '2026-11-05T00:00:00Z', 'payload': {'ts': 1, 'day': '2026-11-05', 'text': 'a'}},
                {'id': 'late', 'by': 'aya', 'type': 'note', 'child': None, 'inserted_at': '2026-11-05T01:00:00Z', 'payload': {'ts': 2, 'day': '2026-11-05', 'text': 'b'}}]
        MOCK = "(rows) => { Sync.switchTo('https://mock.invalid', 'x'); Sync.st().needReconcile = false; Store.settings.sbRole = 'aya'; Store.settings.sbSession = { sid: Sync.sid(), access_token: 't' }; Store.saveSettings(); Sync.refresh = async () => true; window.__pulls = 0; window.fetch = async (u, o) => { if (o && o.method === 'POST') return { ok: true, status: 201, json: async () => ({}) }; const or = new URL(u).searchParams.get('or'); if (!or) return { ok: true, headers: { get: () => null }, json: async () => [] }; window.__pulls++; const tm = or.match(/inserted_at.gt.([^,]+)/)[1], id = (or.match(/id.gt.([^)]*)/) || [])[1] || ''; return { ok: true, json: async () => rows.filter(r => Date.parse(r.inserted_at) > Date.parse(tm) || (Date.parse(r.inserted_at) === Date.parse(tm) && r.id > id)).slice(0, 1000) }; }; }"
        await pg.evaluate(f"({MOCK})({json.dumps(rows)})")
        await pg.evaluate(FAIL_STORAGE)
        r = await pg.evaluate("(async () => { await Sync.run(); return { n: Store.raw.length, cur: Sync.st().cursor || null, err: Sync.lastError }; })()")
        ok('03 فشل الحفظ: المؤشر لا يتقدم والخطأ معلن', r['cur'] is None and r['err'] and 'لن يتقدم المؤشر' in r['err'], r)
        await pg.evaluate(RESTORE)
        await reload(pg)
        await pg.evaluate(f"({MOCK})({json.dumps(rows)})")
        r = await pg.evaluate("(async () => { const before = Store.raw.length; await Sync.run(); return { before, n: Store.raw.map(e => e.id).sort(), cur: Sync.st().cursor, err: Sync.lastError }; })()")
        ok('03 بعد التعافي يصل الجميع دون ضبط يدوي', r['n'] == ['early', 'late'] and r['cur']['id'] == 'late' and r['err'] is None, r)

        # 04: أكثر من 1000 سجل بتوقيت واحد، وأكثر من صفحة داخل 5 ثوانٍ
        pg, errs = await fresh()
        rows = [{'id': 'r%04d' % i, 'by': 'aya', 'type': 'note', 'child': None, 'inserted_at': '2026-11-05T00:00:00Z', 'payload': {'ts': i + 1, 'day': '2026-11-05', 'text': 't'}} for i in range(1001)]
        rows += [{'id': 's%04d' % i, 'by': 'aya', 'type': 'note', 'child': None, 'inserted_at': '2026-11-05T00:00:0%d.%03dZ' % (1 + i // 1000, i % 1000), 'payload': {'ts': 5000 + i, 'day': '2026-11-05', 'text': 't'}} for i in range(2500)]
        await pg.evaluate(f"({MOCK})({json.dumps(rows)})")
        r = await pg.evaluate("(async () => { await Sync.run(); const first = { n: Store.raw.length, pulls: window.__pulls, err: Sync.lastError }; window.__pulls = 0; await Sync.run(); return { first, second: { n: Store.raw.length, pulls: window.__pulls, err: Sync.lastError }, cur: Sync.st().cursor }; })()")
        ok('04 كل 3501 سجل تصل في جولة واحدة دون خطأ', r['first']['n'] == 3501 and r['first']['err'] is None and r['first']['pulls'] <= 6, r)
        ok('04 الجولة التالية بلا جديد: لا تكرار ولا خطأ (تعيد فقط نافذة الثواني الخمس)', r['second']['n'] == 3501 and r['second']['err'] is None and r['second']['pulls'] <= r['first']['pulls'] and r['cur']['id'] == 's2499', r)
        rows2 = [{'id': 'z%05d' % i, 'by': 'aya', 'type': 'note', 'child': None, 'inserted_at': '2026-11-06T00:00:00Z', 'payload': {'ts': 9000 + i, 'day': '2026-11-06', 'text': 't'}} for i in range(51000)]
        await pg.evaluate(f"({MOCK})({json.dumps(rows2)})")
        r = await pg.evaluate("(async () => { await Sync.run(); return { n: Store.raw.length, inc: Sync.incomplete, err: Sync.lastError }; })()")
        ok('04 بلوغ حد الصفحات يُعلن «لم تكتمل» لا نجاحاً', r['inc'] is True and r['err'] and 'لم تكتمل' in r['err'], r)

        # 06 و07: حدود السور وفحص ولي الأمر
        pg, errs = await fresh()
        r = await pg.evaluate("""(() => ({ p600: surahsOfPage(600), p575: surahsOfPage(575), p599: surahsOfPage(599), p596: surahsOfPage(596), p1: surahsOfPage(1), p604: surahsOfPage(604),
            r600: ayahRangeOnPage(600, 100), a: pageOfAyah(100, 11), b: pageOfAyah(73, 20), c: pageOfAyah(2, 286), d: pageOfAyah(1, 1) }))()""")
        ok('06 حدود السور مطابقة للمصحف', r['p600'] == [100, 101, 102] and r['p575'] == [73, 74] and r['p599'] == [98, 99, 100] and r['p596'] == [92, 93, 94] and r['p1'] == [1] and r['p604'] == [112, 113, 114] and r['r600'] == [10, 11] and r['a'] == 600 and r['b'] == 575 and r['c'] == 49 and r['d'] == 1, r)
        r = await pg.evaluate("""(() => { for (let p = 595; p <= 604; p++) Store.add({ type: 'layer', child: 'karim', page: p, layer: 'far', color: 'green' });
            Store.add({ type: 'new_page', child: 'karim', page: 600, linesFrom: 1, linesTo: 15 }); Store.add({ type: 'surah_passed', child: 'karim', surah: 101 }); Store.add({ type: 'surah_passed', child: 'karim', surah: 102 });
            const l1 = deriveChild('karim').pages[600].layer; Store.add({ type: 'surah_passed', child: 'karim', surah: 100 }); return { l1, l2: deriveChild('karim').pages[600].layer }; })()""")
        ok('06 اعتماد بعض سور الصفحة لا ينقلها', r == {'l1': 'near', 'l2': 'far'}, r)
        r = await pg.evaluate("""(() => { Store.add({ type: 'layer', child: 'dalal', page: 570, layer: 'far', day: '2026-10-01', ts: Date.UTC(2026, 9, 1) });
            App.setRole('parent'); Store.add({ type: 'outcome', child: 'dalal', page: 570, step: 'exam', parent: true, result: 'clean' }); App.setRole('aya');
            const pg = deriveChild('dalal').pages[570]; return { lastFar: pg.lastFar, lastReview: pg.lastReview }; })()""")
        ok('07 فحص ولي الأمر لا يغيّر تاريخ مراجعة البعيد', r == {'lastFar': '2026-10-01', 'lastReview': '2026-10-01'}, r)
        assert not errs, errs
        await b.close()
    srv.shutdown()
    print(f'AUDIT OK ({len(results)} حالة)')

asyncio.run(main())
