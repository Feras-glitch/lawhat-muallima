"""0.16: مراجعة تجربة الاستخدام — تأكيد «الباقي مستقل» وتراجع الدفعة، إبقاء الشاشة مضاءة، رأس الجلسة المختصر،
العودة لأعلى الشاشة، رقم خريطة المصحف، الرموز الأولية، مرشد الإعداد، الإدارة المتقدمة، خطاب ولي الأمر، التفاصيل المتدرجة."""
import asyncio, pathlib, os, json, threading, http.server, socketserver, functools, re
from playwright.async_api import async_playwright
ROOT = pathlib.Path(__file__).resolve().parent.parent
BROWSER_OPTS = {'executable_path': '/usr/bin/google-chrome', 'args': ['--no-sandbox']} if os.path.exists('/usr/bin/google-chrome') and not os.environ.get('CI') else {'args': ['--no-sandbox']}


class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass


socketserver.TCPServer.allow_reuse_address = True
results = []
BUILD_V = (ROOT / 'VERSION').read_text().strip()


def ok(name, cond, data=None):
    results.append(name)
    assert cond, f'FAIL {name}: {json.dumps(data, ensure_ascii=False, default=str)[:1500]}'
    print('PASS', name, json.dumps(data, ensure_ascii=False, default=str)[:170] if data is not None else '')


SEED = """() => { window.setNow = iso => { Store.settings.timeOffset = Date.parse(iso) - Date.now(); };
  const L = []; let k = 0; const ev = o => L.push(Object.assign({ id: 's' + (++k), ts: Date.parse(o.day + 'T01:00:00Z') + k, dev: 't', by: 'aya' }, o));
  ev({ type: 'names', day: '2026-11-01', names: { c1: 'سين', c2: 'صاد', c3: 'عين' } });
  for (const c of ['c1', 'c2']) for (let p = 562; p <= 604; p++) ev({ type: 'layer', day: '2026-11-20', child: c, page: p, layer: 'far', color: 'green' });
  for (let p = 595; p <= 604; p++) ev({ type: 'layer', day: '2026-11-20', child: 'c3', page: p, layer: 'far', color: 'green' });
  let d = '2026-11-21'; for (let p = 542; p <= 547; p++) { for (const c of ['c1', 'c2']) ev({ type: 'new_page', day: d, child: c, page: p, linesFrom: 1, linesTo: 15 }); const x = new Date(d + 'T00:00:00Z'); x.setUTCDate(x.getUTCDate() + 1); d = x.toISOString().slice(0, 10); }
  Store.importEvents(L); setNow('2026-11-28T23:05:00Z'); }"""
FEM = ['اضغطي', 'ابدئي', 'اكتبي', 'اختاري', 'افتحي', 'سجّلي', 'صدّري', 'أعيدي', 'غيّري', 'ادخلي', 'انظري', 'راجعي']


async def main():
    httpd = socketserver.TCPServer(('127.0.0.1', 0), functools.partial(Q, directory=str(ROOT / 'dist')))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    port = httpd.server_address[1]
    errors = []
    async with async_playwright() as p:
        b = await p.chromium.launch(**BROWSER_OPTS)

        async def fresh(role, seed=True, init=None):
            ctx = await b.new_context(viewport={'width': 360, 'height': 740}, locale='ar', timezone_id='Africa/Cairo')
            pg = await ctx.new_page()
            pg.on('pageerror', lambda e: errors.append(str(e)))
            if init: await pg.add_init_script(init)
            await pg.goto(f'http://127.0.0.1:{port}/index.html'); await pg.wait_for_function('Store.raw && Store.idbOk')
            await pg.evaluate("(role) => { Sync.schedule = () => {}; Sync.run = async () => {}; App.setRole(role); }", role)
            if seed: await pg.evaluate(f"({SEED})()"); await pg.evaluate("UI.rerender()")
            return pg

        # ===== «الباقي مستقل»: تأكيد بالعدد، وتراجع واحد عن الدفعة =====
        pg = await fresh('asst')
        await pg.evaluate("(() => { startSession(PLAN.find(s => s.kind === 'near_review' && s.child === 'c1')); Store.settings.active.cur = 1; UI.rerender(); })()")
        n0 = await pg.evaluate("Store.raw.length")
        r = await pg.evaluate("(() => { const li = document.querySelectorAll('.steps li')[1]; const bs = [...li.querySelectorAll('button')]; return { first: bs[0].textContent, rest: li.querySelector('.restclean').textContent, lastIsRest: bs.indexOf(li.querySelector('.restclean')) > bs.length - 3, rows: li.querySelectorAll('.prow').length, rowH: Math.round(li.querySelector('.prow').getBoundingClientRect().height) }; })()")
        ok('القريب: صفحة في سطر (أقل من 56 بكسل)، و«الباقي مستقل» في آخر القائمة لا أولها', r['rows'] == 6 and r['rowH'] < 56 and r['first'] != r['rest'] and r['rest'] == 'الباقي مستقل (6)' and r['lastIsRest'], r)
        await pg.click('button.restclean'); await pg.wait_for_selector('.modal')
        r = await pg.evaluate(f"({{ added: Store.raw.length - {n0}, text: document.querySelector('.modal').innerText }})")
        ok('ضغطة «الباقي مستقل» لا تسجّل شيئاً قبل التأكيد، والتأكيد يذكر العدد والصفحات', r['added'] == 0 and 'تسجيل 6 صفحات' in r['text'] and '547' in r['text'], r)
        await pg.click('.modal button.primary'); await pg.evaluate('Store.durable()')
        ok('بعد التأكيد تُسجَّل الست', await pg.evaluate(f"Store.raw.length - {n0}") == 6)
        await pg.evaluate("undoLast()"); await pg.wait_for_selector('.modal .undobatch')
        await pg.click('.modal .undobatch'); await pg.evaluate('Store.durable()')
        r = await pg.evaluate("({ live: Store.events.filter(e => e.type === 'outcome' && e.step === 'near').length, undos: Store.raw.filter(e => e.type === 'undo').length })")
        ok('تراجع واحد يلغي الدفعة كلها', r == {'live': 0, 'undos': 6}, r)
        # صفحة واحدة ثم تراجع: نافذة التأكيد العادية لا نافذة الدفعة
        await pg.locator('.prow').first.locator('button.btn-g').click(); await pg.evaluate("undoLast()")
        ok('تسجيل مفرد: تراجع عادي بلا خيار الدفعة', await pg.evaluate("!document.querySelector('.modal .undobatch') && !!document.querySelector('.modal')"))
        await pg.click('.modal button.ghost')
        # التفاصيل المتدرجة
        r = await pg.evaluate("(() => { const row = document.querySelector('.prow'); return { more: !!row.querySelector('.chip.more'), chips: row.querySelectorAll('.chip').length, h: Math.round(row.getBoundingClientRect().height) }; })()")
        ok('في المراجعة: «مستقل» تُبقي التفاصيل مطوية خلف زر واحد والسطر لا يطول', r['more'] and r['chips'] == 1 and r['h'] < 56, r)

        # ===== رأس الجلسة المختصر، الشريط المطوي، الشاشة المضاءة (المتصفح) =====
        WL = "window.wl = { req: 0, rel: 0 }; Object.defineProperty(navigator, 'wakeLock', { configurable: true, value: { request: async () => { window.wl.req++; return { release() { window.wl.rel++; }, addEventListener() {} }; } } });"
        pg = await fresh('aya', init=WL)
        r0 = await pg.evaluate("({ h: Math.round(document.querySelector('header').getBoundingClientRect().height), nav: getComputedStyle(document.querySelector('nav.bottom')).display, wl: window.wl.req })")
        await pg.evaluate("startSession(PLAN.find(s => s.kind === 'gate_new' && s.child === 'c1'))"); await pg.wait_for_timeout(100)
        r1 = await pg.evaluate("({ h: Math.round(document.querySelector('header').getBoundingClientRect().height), nav: getComputedStyle(document.querySelector('nav.bottom')).display, wl: window.wl.req, help: !!document.querySelector('.helpbtn') })")
        ok('أثناء الجلسة: رأس أقصر بثلاثين بكسل على الأقل والشريط السفلي مطوي، وخارجها كما كان', r0['nav'] == 'flex' and r1['nav'] == 'none' and r1['h'] <= r0['h'] - 30, {'out': r0, 'in': r1})
        ok('بدء الجلسة يطلب إبقاء الشاشة مضاءة', r0['wl'] == 0 and r1['wl'] == 1, {'out': r0['wl'], 'in': r1['wl']})
        await pg.click('.navtoggle')
        ok('زر ☰ يُظهر الشريط السفلي أثناء الجلسة', await pg.evaluate("getComputedStyle(document.querySelector('nav.bottom')).display") == 'flex')
        await pg.click('.helpbtn'); txt = await pg.locator('.modal').inner_text()
        ok('زر «؟ المصطلحات» يشرح القريب والبعيد والبوابة', all(k in txt for k in ['القريب', 'البعيد', 'بوابة الأمس', 'القائمة الصفراء']), txt[:80])
        await pg.evaluate("document.querySelector('.modal-bg').remove()")
        # تسميع الجديد: سؤال المعنى ظاهر مع «مستقل»
        await pg.evaluate("(() => { Store.settings.active.cur = 0; UI.rerender(); })()")
        await pg.locator('.steps li').first.locator('button.btn-g').first.click(); await pg.wait_for_timeout(100)
        ok('في تسميع البوابة: «مستقل» تُبقي سؤال المعنى ظاهراً', await pg.evaluate("[...document.querySelectorAll('.steps li')[0].querySelectorAll('.chip')].some(c => c.textContent === 'تحقق')"))
        ok('«إغلاق مؤقت» رابط بعيد عن زر الإنهاء، ولا زر «إغلاق بلا تسجيل»', await pg.evaluate("!!document.querySelector('a.tempclose') && ![...document.querySelectorAll('button')].some(b => b.textContent === 'إغلاق بلا تسجيل')"))
        await pg.evaluate("(() => { Store.settings.active = null; Store.saveSettings(); UI.rerender(); })()"); await pg.wait_for_timeout(100)
        ok('إغلاق الجلسة يحرر قفل الشاشة', await pg.evaluate("window.wl.rel") == 1)
        # داخل تطبيق أندرويد: عبر الجسر
        pg2 = await fresh('aya', init="window.kso = []; window.LawhatAndroid = { keepScreenOn: v => window.kso.push(v) };")
        await pg2.evaluate("startSession(PLAN.find(s => s.kind === 'gate_new' && s.child === 'c1'))"); await pg2.evaluate("(() => { Store.settings.active = null; Store.saveSettings(); UI.rerender(); })()")
        ok('في تطبيق أندرويد: الطلب يمر عبر الجسر keepScreenOn(true) ثم (false)', await pg2.evaluate("window.kso") == [True, False])

        # ===== التنقل يبدأ من أعلى الشاشة، والتنبيهات فوق الجدول، ورسالة الحفظ أعلى =====
        await pg.evaluate("window.scrollTo(0, 700)"); y0 = await pg.evaluate("scrollY")
        await pg.click('nav.bottom button:nth-child(3)'); await pg.wait_for_timeout(100)
        ok('تغيير التبويب يعود لأعلى الشاشة', y0 > 300 and await pg.evaluate("scrollY") == 0, y0)
        await pg.click('nav.bottom button:nth-child(1)')
        r = await pg.evaluate("(() => { const hs = [...document.querySelectorAll('main .card h2')].map(h => h.textContent); return { alerts: hs.indexOf('تنبيهات'), list: hs.indexOf('جدول اليوم') }; })()")
        ok('التنبيهات قبل جدول اليوم', 0 <= r['alerts'] < r['list'], r)
        await pg.evaluate("UI.toast('اختبار')")
        ok('رسالة الحفظ أعلى الشاشة لا فوق الأزرار السفلية', await pg.evaluate("document.querySelector('.toast').getBoundingClientRect().top") < 120)

        # ===== خريطة المصحف: الرقم من العتبة الفعلية =====
        await pg.evaluate("(() => { App.view = 'children'; App.sub = { child: 'c1', ctab: 'map' }; UI.rerender(); })()")
        r = await pg.evaluate("({ txt: document.querySelector('main').innerText, red: deriveChild('c1').gapRed })")
        ok('خريطة المصحف تذكر العتبة الفعلية لا 12 الثابتة', f"تجاوز {r['red']} يوماً" in r['txt'] and 'تجاوزت 12 يوماً' not in r['txt'] and r['red'] == 14, r['red'])

        # ===== الرموز الأولية ومرشد الإعداد =====
        pg = await fresh('aya', seed=False)
        r = await pg.evaluate("({ setup: !!document.querySelector('.card.setup'), rows: [...document.querySelectorAll('.setup .ayahrow b')].map(x => x.textContent) })")
        ok('أول تشغيل: بطاقة «الإعداد الأول» بأربع خطوات مرتبة', r['setup'] and [x[:2] for x in r['rows']] == ['1.', '2.', '3.', '4.'], r['rows'])
        await pg.fill('.pinfield input', '1111'); await pg.click('.pinfield button')
        ok('لا يُقبل رمز أولي رمزاً جديداً', await pg.evaluate("Store.settings.pins.aya") == '1111')
        await pg.fill('.pinfield input', '4827'); await pg.click('.pinfield button'); await pg.wait_for_timeout(100)
        r = await pg.evaluate("({ pin: Store.settings.pins.aya, done: [...document.querySelectorAll('.setup .setupdone b')].map(x => x.textContent) })")
        ok('تغيير الرمز من البطاقة نفسها يُشطب خطوته', r == {'pin': '4827', 'done': ['✓ تغيير رمز الدخول الأولي']}, r)
        await pg.evaluate(f"({SEED})()"); await pg.evaluate("UI.rerender()")
        ok('بعد الأسماء والجرد والرمز تختفي بطاقة الإعداد', await pg.evaluate("!document.querySelector('.card.setup') && !document.querySelector('.pinnudge')"))
        await pg.evaluate("App.logout()")
        txt = await pg.evaluate("document.body.innerText")
        ok('شاشة الدخول لا تذكر رمز الحساب الذي تغيّر رمزه، وتذكر الباقي', 'آية 1111' not in txt and 'المساعدة 2222' in txt and txt.count('ولي الأمر\nولي الأمر') == 0, txt[-200:])
        pg = await fresh('asst')
        ok('المساعدة: بطاقة تغيير الرمز الأولي بلا مرشد الإعداد', await pg.evaluate("!!document.querySelector('.pinnudge') && !document.querySelector('.card.setup')"))

        # ===== ولي الأمر: الإدارة المتقدمة مطوية، والخطاب بلا تأنيث =====
        pg = await fresh('parent')
        await pg.evaluate("(() => { Store.settings.pins.parent = '9321'; Store.settings.timeOffset = 0; Store.saveSettings(); App.view = 'settings'; UI.rerender(); })()")
        r = await pg.evaluate("(() => { const d = document.querySelector('details.adv'); return { open: d.open, inside: [...d.querySelectorAll('h2')].map(h => h.textContent), outside: [...document.querySelectorAll('main > div > .card > h2')].map(h => h.textContent) }; })()")
        ok('إعدادات ولي الأمر: استعادة الخادم والوقت ومسح البيانات داخل «إدارة متقدمة» المطوية', not r['open'] and 'مسح البيانات' in r['inside'] and 'الوقت' in r['inside'] and 'مسح البيانات' not in r['outside'] and 'أسماء الأطفال' in r['outside'], r)
        found = {}
        for v, sub in [('dash', {}), ('children', {'child': 'c1', 'ctab': 'summary'}), ('children', {'child': 'c1', 'ctab': 'map'}), ('logs', {}), ('reports', {}), ('settings', {})]:
            t = await pg.evaluate("([v, sub]) => { App.view = v; App.sub = sub; UI.rerender(); document.querySelectorAll('details').forEach(d => { d.open = true; }); return document.querySelector('main').innerText; }", [v, sub])
            hit = [w for w in FEM if re.search(r'(?<![ء-ي])' + w + r'(?![ء-ي])', t)]
            if hit: found[v + ':' + sub.get('ctab', '')] = hit
        ok('شاشات ولي الأمر بلا أفعال أمر مؤنثة', not found, found)
        r = await pg.evaluate("(() => { App.view = 'dash'; App.sub = {}; UI.rerender(); return document.querySelector('.kpi').innerText; })()")
        ok('لوحة ولي الأمر: رقم أقدم مراجعة مع حدّه', 'الحد 14' in r, r)
        pg = await fresh('aya')
        ok('حساب المعلمة يبقى بخطاب المؤنث', 'ابدئي الجلسة' in await pg.evaluate("document.querySelector('main').innerText"))

        # ===== 0.16.1: ملاحظة للمطوّر، والشاشة العريضة =====
        pg = await fresh('asst')
        await pg.evaluate("(() => { startSession(PLAN.find(s => s.kind === 'near_review' && s.child === 'c1')); })()")
        await pg.click('a.devnote'); await pg.fill('.modal textarea', 'زر المساعدة صغير'); await pg.click('.modal button.primary'); await pg.evaluate('Store.durable()')
        r = await pg.evaluate("(() => { const e = Store.raw.filter(x => x.type === 'note').pop(); return { text: e.text, by: e.by, child: e.child || null, n: devNotes().length }; })()")
        ok('«ملاحظة للمطوّر» من داخل الجلسة: سجل ملاحظة عام يحمل الشاشة والإصدار والحساب', r['n'] == 1 and r['by'] == 'asst' and r['child'] is None and r['text'].startswith('للمطوّر: زر المساعدة صغير [جلسة') and BUILD_V in r['text'] and 'المساعدة' in r['text'], r)
        await pg.evaluate("(() => { Store.settings.active = null; Store.saveSettings(); App.setRole('parent'); App.view = 'settings'; UI.rerender(); })()")
        ok('ولي الأمر يرى ملاحظات المطوّر في الإعدادات مع زر نسخ الكل', await pg.evaluate("(() => { const c = document.querySelector('.card.devnotes'); return !!c && c.innerText.includes('زر المساعدة صغير') && c.innerText.includes('نسخ الكل (1)'); })()"))
        ctx = await b.new_context(viewport={'width': 1280, 'height': 800}, locale='ar'); wide = await ctx.new_page(); wide.on('pageerror', lambda e: errors.append(str(e)))
        await wide.goto(f'http://127.0.0.1:{port}/index.html'); await wide.wait_for_function('Store.raw && Store.idbOk')
        await wide.evaluate("(() => { Sync.schedule = () => {}; Sync.run = async () => {}; App.setRole('asst'); })()"); await wide.evaluate(f"({SEED})()")
        await wide.evaluate("(() => { startSession(PLAN.find(s => s.kind === 'near_review' && s.child === 'c1')); Store.settings.active.cur = 1; UI.rerender(); })()")
        r = await wide.evaluate("(() => { const rows = [...document.querySelectorAll('.prow')].map(x => x.getBoundingClientRect()); const cards = [...document.querySelectorAll('.sessionwrap > .card')].map(x => x.getBoundingClientRect()); return { sameLine: Math.abs(rows[0].top - rows[1].top) < 2, side: Math.abs(cards[1].top - cards[2].top) < 4 && cards[2].width < 340 }; })()")
        ok('شاشة عريضة: صفحات المراجعة في عمودين، وبطاقة التسجيل والإنهاء بجانب الخطوات', r == {'sameLine': True, 'side': True}, r)

        await b.close()
    httpd.shutdown()
    assert not errors, errors
    print(f'AUDIT 0.16 OK ({len(results)} حالة)')

asyncio.run(main())
