"""0.15: الخصوصية (معرّفات بلا أسماء، والأسماء سجل)، جلسة ظهر واحدة للطفل الثالث، سقف القريب والبعيد بأولوياته،
العتبات الممتدة بالأيام التقويمية وتنبيه دورة البعيد، أزرار آيات الصفحة والموضع المشابه المؤجل، التسميع الثالث المشترك،
ونافذة إلغاء اليوم بلا تحديد افتراضي."""
import asyncio, pathlib, os, json, threading, http.server, socketserver, functools, re
from playwright.async_api import async_playwright
ROOT = pathlib.Path(__file__).resolve().parent.parent
BROWSER_OPTS = {'executable_path': '/usr/bin/google-chrome', 'args': ['--no-sandbox']} if os.path.exists('/usr/bin/google-chrome') and not os.environ.get('CI') else {'args': ['--no-sandbox']}


class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass


socketserver.TCPServer.allow_reuse_address = True
results = []


def ok(name, cond, data=None):
    results.append(name)
    assert cond, f'FAIL {name}: {json.dumps(data, ensure_ascii=False, default=str)[:1500]}'
    print('PASS', name, json.dumps(data, ensure_ascii=False, default=str)[:170] if data is not None else '')


# أدوات داخل الصفحة: ضبط الساعة بتوقيت بكين، وإدراج سجلات بأيام محددة
HELPERS = """() => {
  window.setNow = iso => { Store.settings.timeOffset = Date.parse(iso) - Date.now(); };
  window.addDay = (d, n) => { const x = new Date(d + 'T00:00:00Z'); x.setUTCDate(x.getUTCDate() + n); return x.toISOString().slice(0, 10); };
  let k = 0; window.seed = list => Store.importEvents(list.map(o => Object.assign({ id: 'seed' + (++k), ts: Date.parse(o.day + 'T01:00:00Z') + k, dev: 'test' }, o)));
}"""


async def main():
    httpd = socketserver.TCPServer(('127.0.0.1', 0), functools.partial(Q, directory=str(ROOT / 'dist')))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    port = httpd.server_address[1]
    errors = []
    async with async_playwright() as p:
        b = await p.chromium.launch(**BROWSER_OPTS)

        async def fresh(role='aya'):
            ctx = await b.new_context(viewport={'width': 390, 'height': 844}, locale='ar', timezone_id='Africa/Cairo')
            pg = await ctx.new_page()
            pg.on('pageerror', lambda e: errors.append(str(e)))
            pg.on('dialog', lambda d: asyncio.ensure_future(d.accept()))
            await pg.goto(f'http://127.0.0.1:{port}/index.html'); await pg.wait_for_function('Store.raw && Store.idbOk')
            await pg.evaluate("(role) => { Sync.schedule = () => {}; Sync.run = async () => {}; App.setRole(role); }", role)
            await pg.evaluate(f"({HELPERS})()")
            return pg

        # ================= الخصوصية: لا أسماء في البرنامج المنشور، والأسماء سجل =================
        html = (ROOT / 'dist' / 'index.html').read_text(encoding='utf-8')
        ids = re.search(r"const CHILD_ORDER = \[([^\]]*)\]", html).group(1)
        ok('الخصوصية: معرّفات الأطفال في البرنامج المنشور c1/c2/c3 فقط، بلا أعمار', ids == "'c1', 'c2', 'c3'" and 'age:' not in html.split('const CHILD_ORDER')[0][-800:], ids)
        pg = await fresh('parent')
        r = await pg.evaluate("({ names: CHILD_ORDER.map(c => CHILDREN[c].name), both: childName('both'), login: document.body.innerText })")
        ok('بلا سجل أسماء: أسماء افتراضية محايدة', r['names'] == ['الطفل الأول', 'الطفل الثاني', 'الطفل الثالث'] and r['both'] == 'الطفل الأول والطفل الثاني', r['names'])
        await pg.evaluate("(() => { App.view = 'settings'; UI.rerender(); })()")
        card = pg.locator('.card', has=pg.get_by_role('heading', name='أسماء الأطفال', exact=True))
        inputs = card.locator('input')
        await inputs.nth(0).fill('سين'); await inputs.nth(1).fill('صاد'); await inputs.nth(2).fill('عين')
        await card.get_by_role('button', name='حفظ الأسماء', exact=True).click(); await pg.evaluate('Store.durable()')
        await pg.reload(); await pg.wait_for_function('Store.raw && Store.idbOk')
        r = await pg.evaluate("({ names: CHILD_ORDER.map(c => CHILDREN[c].name), both: childName('both'), ev: Store.raw.filter(e => e.type === 'names').map(e => [e.by, e.names]) })")
        ok('ولي الأمر يكتب الأسماء من الإعدادات: سجل «names» يبقى بعد إعادة التحميل ويظهر في كل الشاشات', r['names'] == ['سين', 'صاد', 'عين'] and r['both'] == 'سين وصاد' and r['ev'] == [['parent', {'c1': 'سين', 'c2': 'صاد', 'c3': 'عين'}]], r)
        r = await pg.evaluate("""({ asst: Store.roleAllows('asst', { type: 'names', names: { c1: 'x' } }), aya: Store.roleAllows('aya', { type: 'names', names: { c1: 'x' } }), parent: Store.roleAllows('parent', { type: 'names', names: { c1: 'x' } }),
            badKey: Store.validEvent({ id: 'n1', type: 'names', by: 'parent', ts: 1, day: '2026-11-07', names: { zz9: 'x' } }), empty: Store.validEvent({ id: 'n2', type: 'names', by: 'parent', ts: 1, day: '2026-11-07', names: { c1: '  ' } }) })""")
        ok('الأسماء: يكتبها ولي الأمر وآية فقط، ومفاتيحها معرّفات معروفة وقيمها غير فارغة', r == {'asst': False, 'aya': True, 'parent': True, 'badKey': False, 'empty': False}, r)

        # ================= جدول الطفل الثالث =================
        r = await pg.evaluate("""(() => { const work = PLAN.filter(s => WORKDAYS.includes(s.day));
            const late = work.filter(s => s.start >= '15:00' && s.start < '18:00');
            const noon = PLAN.filter(s => s.kind === 'young_noon'); const k = SESSION_KINDS.young_noon;
            const third = PLAN.filter(s => s.kind === 'third');
            return { late: late.length, noon: noon.map(s => s.start + '-' + s.end + ' ' + s.child + ' ' + s.teacher), noonDays: noon.length, steps: k.steps.map(x => x.id + ':' + x.min), asr: Object.keys(SESSION_KINDS).some(k => /asr/.test(k)) || !!SESSION_KINDS.fluency,
              third: [...new Set(third.map(s => s.start + '-' + s.end + ' ' + s.child))], thirdDays: third.length }; })()""")
        ok('الطفل الثالث: جلسة ظهر واحدة 12:10–12:45 مع المساعدة (تسميع ثانٍ 3، طلاقة 20، مراجعة 12)، ولا جلسة بين 3:00 و6:00',
           r == {'late': 0, 'noon': ['12:10-12:45 c3 asst'] * 5, 'noonDays': 5, 'steps': ['second:3', 'read:20', 'far:12'], 'asr': False, 'third': ['18:25-18:35 both'], 'thirdDays': 5}, r)

        # ================= سقف القريب وأولوياته =================
        pg = await fresh('aya')
        await pg.evaluate("""(() => { setNow('2026-12-19T23:00:00Z'); /* بكين: الأحد 20 ديسمبر 7:00 */
            const L = []; const D0 = '2026-11-01';
            for (let p = 562; p <= 604; p++) L.push({ type: 'layer', by: 'aya', day: D0, child: 'c1', page: p, layer: 'far', color: 'green' });
            let d = '2026-11-02'; const pages = []; for (let p = 542; p <= 561; p++) pages.push(p); for (let p = 522; p <= 526; p++) pages.push(p);
            for (const p of pages) { L.push({ type: 'new_page', by: 'aya', day: d, child: 'c1', page: p, linesFrom: 1, linesTo: 15 }); d = addDay(d, 1); }
            L.push({ type: 'color', by: 'aya', day: '2026-12-18', child: 'c1', page: 545, color: 'red' });
            L.push({ type: 'color', by: 'aya', day: '2026-12-18', child: 'c1', page: 590, color: 'red' });
            seed(L); })()""")
        r = await pg.evaluate("(() => { const d = deriveChild('c1'); return { near: d.near.length, today: d.nearToday, reds: d.reds, wait: d.waitingJuz, cap: d.caps.near }; })()")
        ok('القريب بسقف 10: الحمراء أولاً (من القريب والبعيد)، ثم آخر 5 صفحات، ثم الجزء المختوم المنتظر فحصه بالأقدم تسميعاً',
           r == {'near': 25, 'today': [545, 590, 526, 525, 524, 523, 522, 544, 543, 542], 'reds': [545, 590], 'wait': [28], 'cap': 10}, r)
        await pg.evaluate("(() => { for (const p of deriveChild('c1').nearToday) Store.add({ type: 'outcome', child: 'c1', page: p, step: 'near', result: 'clean' }); })()")
        same = await pg.evaluate("deriveChild('c1').nearToday")
        ok('قائمة اليوم ثابتة بعد تسجيل نتائجها في اليوم نفسه', same == r['today'], same)
        await pg.evaluate("setNow('2026-12-20T23:00:00Z')")
        nxt = await pg.evaluate("deriveChild('c1').nearToday")
        ok('في اليوم التالي يتقدم التناوب إلى صفحات الجزء المنتظر التي لم تُسمّع (والحمراء وآخر 5 باقية)', nxt == [545, 590, 526, 525, 524, 523, 522, 548, 547, 546], nxt)
        await pg.evaluate("(() => { App.setRole('asst'); startSession(PLAN.find(s => s.kind === 'near_review' && s.child === 'c1')); Store.settings.active.cur = 1; UI.rerender(); })()")
        txt = await pg.evaluate("document.querySelector('main').innerText")
        ok('جلسة القريب تعرض صفحات اليوم العشر وتذكر الباقي بالتناوب', 'القريب اليوم (10 من 25' in txt and 'سقف القريب 10' in txt and '(15 صفحة في أيام تالية)' in txt, re.findall(r'القريب اليوم[^\n]*', txt))
        await pg.evaluate("(() => { Store.settings.active = null; Store.saveSettings(); App.setRole('aya'); })()")

        # ================= البعيد: السقف، طول الدورة، العتبات الممتدة، وتنبيه 21 يوماً =================
        await pg.evaluate("""(() => { const L = []; for (let p = 2; p <= 161; p++) L.push({ type: 'layer', by: 'aya', day: '2026-12-01', child: 'c2', page: p, layer: 'far', color: 'green' });
            for (let p = 542; p <= 604; p++) L.push({ type: 'layer', by: 'aya', day: '2026-12-01', child: 'c3', page: p, layer: 'far', color: 'green' }); seed(L); })()""")
        DER = "(() => { const d = deriveChild('c2'), y = deriveChild('c3'); return { far: d.far.length, quota: d.quota, sessions: d.cycleSessions, days: d.cycleDays, yellow: d.gapYellow, red: d.gapRed, gap: d.maxGap, q3: y.quota, c1: [deriveChild('c1').quota, deriveChild('c1').cycleDays, deriveChild('c1').gapYellow, deriveChild('c1').gapRed] }; })()"
        ALERTS = "(role) => { App.setRole(role); return alertsList().filter(a => a.child === 'c2').map(a => a.level + ': ' + a.text); }"
        await pg.evaluate("setNow('2026-12-20T23:00:00Z')")  # 21 ديسمبر بكين: 20 يوماً بعد الجرد
        r = await pg.evaluate(DER)
        ok('البعيد 160 صفحة: الحصة 8 (السقف)، الدورة 20 جلسة = 28 يوماً تقويمياً، والعتبتان 28 و31؛ والصغير 3؛ و43 صفحة تبقى 7 بحد 11/14',
           r == {'far': 160, 'quota': 8, 'sessions': 20, 'days': 28, 'yellow': 28, 'red': 31, 'gap': 20, 'q3': 3, 'c1': [7, 11, 11, 14]}, r)
        a_aya = await pg.evaluate(ALERTS, 'aya'); a_par = await pg.evaluate(ALERTS, 'parent'); a_asst = await pg.evaluate(ALERTS, 'asst')
        cyc = lambda l: [x for x in l if 'دورة البعيد' in x]
        ok('فاصل 20 يوماً ضمن الدورة: لا إشارة صفراء ولا حمراء (القاعدة القديمة كانت تُحمِّرها بعد 12)', not [x for x in a_aya if 'بلا تسميع' in x or 'تجاوزت الفاصل' in x], a_aya)
        ok('تنبيه هادئ لآية وولي الأمر حين تتجاوز الدورة 21 يوماً، ولا يظهر للمساعدة', len(cyc(a_aya)) == 1 and cyc(a_aya)[0].startswith('info: دورة البعيد صارت نحو 28 يوماً') and len(cyc(a_par)) == 1 and not cyc(a_asst), {'aya': cyc(a_aya), 'asst': cyc(a_asst)})
        await pg.evaluate("setNow('2026-12-30T23:00:00Z')")
        r30 = await pg.evaluate(ALERTS, 'aya')
        await pg.evaluate("setNow('2027-01-01T23:00:00Z')")
        r32 = await pg.evaluate(ALERTS, 'aya')
        ok('فاصل 30 يوماً: صفراء بحد 28؛ وفاصل 32: حمراء بحد 31', any(x.startswith('yellow:') and 'الفاصل المتوقع 28' in x for x in r30) and any(x.startswith('red:') and '(الحد 31)' in x for x in r32), {'30': r30, '32': r32})
        await pg.evaluate("(() => { App.setRole('aya'); Store.add({ type: 'decision', child: 'c2', kind: 'caps', far: 12, text: 'متوسط الصفحة بعد المعايرة' }); })()")
        r = await pg.evaluate(DER)
        ok('قرار آية «سقف المراجعة» 12: الحصة 12 والدورة 14 جلسة = 20 يوماً فيختفي تنبيه الدورة', r['quota'] == 12 and r['sessions'] == 14 and r['days'] == 20 and not cyc(await pg.evaluate(ALERTS, 'aya')), r)
        r = await pg.evaluate("""({ asst: Store.roleAllows('asst', { type: 'decision', kind: 'caps', far: 5 }),
            low: Store.validEvent({ id: 'c1x', type: 'decision', by: 'aya', ts: 1, day: '2026-11-07', child: 'c1', kind: 'caps', near: 2 }),
            none: Store.validEvent({ id: 'c2x', type: 'decision', by: 'aya', ts: 1, day: '2026-11-07', child: 'c1', kind: 'caps' }),
            good: Store.validEvent({ id: 'c3x', type: 'decision', by: 'aya', ts: 1, day: '2026-11-07', child: 'c1', kind: 'caps', near: 12, far: 9 }) })""")
        ok('سقف المراجعة قرار آية وحدها، بقيم في حدودها', r == {'asst': False, 'low': False, 'none': False, 'good': True}, r)
        await pg.evaluate("(() => { App.view = 'children'; App.sub = { child: 'c2', ctab: 'summary' }; UI.rerender(); })()")
        await pg.get_by_role('button', name='سقف المراجعة', exact=True).click()
        await pg.locator('.modal input[type=number]').nth(1).fill('9'); await pg.locator('.modal button.primary').click()
        r = await pg.evaluate("({ quota: deriveChild('c2').quota, main: document.querySelector('main').innerText.includes('البعيد 9 صفحات يومياً') })")
        ok('نافذة «سقف المراجعة» في خلاصة الطفل تسجّل القرار وتعرضه', r == {'quota': 9, 'main': True}, r)

        # ================= إدخال الخطأ: أزرار الآيات، والموضع المشابه المؤجل =================
        pg = await fresh('asst')
        await pg.evaluate("(() => { setNow('2026-11-14T04:50:00Z'); startSession(PLAN.find(s => s.kind === 'noon' && s.child === 'c1')); })()")
        await pg.get_by_role('button', name='تسجيل خطأ · الطفل الأول', exact=True).click()
        await pg.locator('.modal input[placeholder="الصفحة"]').fill('582'); await pg.locator('.modal input[placeholder="الصفحة"]').dispatch_event('input')
        r = await pg.evaluate("({ n: document.querySelectorAll('.modal .ayahbtn').length, range: ayahRangeOnPage(582, 78) })")
        ok('أزرار آيات الصفحة: زر لكل آية في ص582', r['n'] == r['range'][1] - r['range'][0] + 1 and r['n'] > 10, r)
        await pg.locator('.modal .ayahbtn[data-a="3"]').click()
        await pg.locator('.modal').get_by_role('button', name='انتقال إلى موضع مشابه', exact=True).click()
        await pg.locator('.modal button.primary').click(); await pg.evaluate('Store.durable()')
        r = await pg.evaluate("(() => { const e = Store.raw.filter(x => x.type === 'error').pop(); return { surah: e.surah, ayah: e.ayah, etype: e.etype, target: e.target || null, sid: e.sid === Store.settings.active.sid, missing: missingTargets().length }; })()")
        ok('ضغطة على رقم الآية تختار السورة والآية، و«انتقال إلى موضع مشابه» يُحفظ بلا موضع دون قطع التلاوة', r == {'surah': 78, 'ayah': 3, 'etype': 'jump', 'target': None, 'sid': True, 'missing': 1}, r)
        await pg.get_by_role('button', name='إنهاء الجلسة', exact=True).click()
        txt = await pg.locator('.modal').inner_text()
        ok('نافذة إنهاء الجلسة تطلب الموضع المؤجل', 'مواضع مشابهة لم تُحدَّد (1)' in txt, txt[:200])
        await pg.locator('.modal').get_by_role('button', name='تحديد', exact=True).click()
        await pg.locator('select.surahpick').last.select_option('79'); await pg.locator('.modal input[placeholder="الآية"]').last.fill('2')
        await pg.locator('.modal-bg').last.locator('button.primary').click(); await pg.evaluate('Store.durable()')
        r = await pg.evaluate("({ missing: missingTargets().length, mut: mutashabihat('c1').map(e => e.target), rec: Store.raw.filter(e => e.type === 'mut_target').map(e => [e.by, e.child, e.target]), err: Store.raw.filter(e => e.type === 'error').pop().target || null, btn: [...document.querySelectorAll('.modal button')].some(b => b.textContent === 'حُدّد') })")
        ok('تحديد الموضع لاحقاً سجل «mut_target» مستقل؛ الخطأ نفسه لا يُعدَّل، والمتشابهات تعرض الموضع', r == {'missing': 0, 'mut': [{'surah': 79, 'ayah': 2}], 'rec': [['asst', 'c1', {'surah': 79, 'ayah': 2}]], 'err': None, 'btn': True}, r)
        await pg.locator('.modal-bg').first.locator('.btns button.primary').last.click(); await pg.wait_for_timeout(300); await pg.evaluate('Store.durable()')
        r = await pg.evaluate("(() => { const h = Store.raw.filter(e => e.type === 'handoff').pop(); return h ? h.items.filter(i => i.k === 'jump').map(i => i.text) : null; })()")
        ok('بطاقة التسليم لآية تحمل الموضع المكتمل', r and any('النازعات 2' in t for t in r), r)
        r = await pg.evaluate("""({ asst: Store.roleAllows('asst', { type: 'mut_target' }), parent: Store.roleAllows('parent', { type: 'mut_target' }),
            noChild: Store.validEvent({ id: 'm1', type: 'mut_target', by: 'asst', ts: 1, day: '2026-11-07', ref: 'x', target: { surah: 59 } }) })""")
        ok('«mut_target» للمعلمتين لا لولي الأمر، ويتطلب الطفل', r == {'asst': True, 'parent': False, 'noChild': False}, r)

        # ================= التسميع الثالث المشترك ونافذة الإلغاء =================
        pg = await fresh('aya')
        await pg.evaluate("(() => { setNow('2026-11-14T10:26:00Z'); startSession(PLAN.find(s => s.kind === 'third')); })()")
        txt = await pg.evaluate("document.querySelector('main').innerText")
        ok('التسميع الثالث جلسة واحدة للاثنين: الطفلان في الشاشة نفسها', txt.count('لم تُسجَّل صفحة اليوم بعد') == 2 or (txt.count('الطفل الأول') >= 1 and txt.count('الطفل الثاني') >= 1), txt[:300])
        await pg.evaluate("(() => { Store.settings.active = null; Store.saveSettings(); setNow('2026-11-13T22:30:00Z'); App.setRole('asst'); cancelModal(); })()")
        r = await pg.evaluate("(() => { const b = document.querySelector('.modal button.danger'); return { checked: [...document.querySelectorAll('.modal input[type=checkbox]')].filter(c => c.checked).length, n: document.querySelectorAll('.modal input[type=checkbox]').length, disabled: b.disabled, text: b.textContent }; })()")
        ok('نافذة إلغاء اليوم: لا جلسة محددة افتراضياً، والزر معطّل', r['checked'] == 0 and r['n'] >= 3 and r['disabled'] and r['text'] == 'اختاري الجلسات أولاً', r)
        await pg.locator('.modal input[type=checkbox]').first.check()
        r = await pg.evaluate("(() => { const b = document.querySelector('.modal button.danger'); return { disabled: b.disabled, text: b.textContent }; })()")
        ok('اختيار جلسة واحدة: الزر يذكر العدد', r == {'disabled': False, 'text': 'تأكيد إلغاء 1 جلسة'}, r)

        await b.close()
    httpd.shutdown()
    assert not errors, errors
    print(f'AUDIT 0.15 OK ({len(results)} حالة)')

asyncio.run(main())
