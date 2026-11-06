"""اختبارات انحدار لمراجعة 0.13.2 المستقلة (LM0132-R4-01..04): حسم تعارض لم يثبت أول مرة، التخزين البديل،
التعارضات في النسخة الكاملة، وإلغاء الحسم المتأخر بعد حذف بيانات الجهاز. كل حالة من برنامج إعادة الإنتاج في التقرير
بأزرار الواجهة ومعالج المغادرة الحقيقي، وبمعيار قبولها."""
import asyncio, pathlib, os, json, threading, http.server, socketserver, functools
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


STATE = """({ text: (Store.raw.find(e => e.id === 'base') || {}).text, open: Store.openConflicts().length,
  cf: Store.conflicts.map(x => ({ resolved: x.resolved ? x.resolved.choice : null, local: x.local.text, other: x.other.text })),
  saved: Store.saved(), err: Store.storageError || null, notes: Store.raw.filter(e => e.id !== 'base').map(e => e.text),
  card: !!document.querySelector('main') && document.querySelector('main').innerText.includes('اعتماد نسخة الملف') })"""
TOASTS = "[...document.querySelectorAll('.toast')].map(t => t.textContent)"


def consistent(r):
    """لا مزيج «قرار اعتماد النسخة الأخرى + محتوى قديم»"""
    return not any(c['resolved'] == 'other' and r['text'] == c['local'] for c in r['cf'])


async def main():
    httpd = socketserver.TCPServer(('127.0.0.1', 0), functools.partial(Q, directory=str(ROOT / 'dist')))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    port = httpd.server_address[1]
    errors = []
    async with async_playwright() as p:
        b = await p.chromium.launch(**BROWSER_OPTS)

        async def fresh(role='aya', noidb=False):
            ctx = await b.new_context(viewport={'width': 390, 'height': 844}, locale='ar', timezone_id='Africa/Cairo')
            if noidb:
                await ctx.add_init_script("Object.defineProperty(window, 'indexedDB', { value: undefined })")
            pg = await ctx.new_page()
            pg.on('pageerror', lambda e: errors.append(str(e)))
            pg.on('dialog', lambda d: asyncio.ensure_future(d.accept()))
            await pg.goto(f'http://127.0.0.1:{port}/index.html'); await pg.wait_for_function('Store.raw')
            await pg.evaluate("(role) => { Sync.schedule = () => {}; App.setRole(role); App.view = 'settings'; UI.rerender(); }", role)
            return pg

        async def reopen(pg, role='aya'):
            await pg.reload(); await pg.wait_for_function('Store.raw')
            await pg.evaluate("(role) => { Sync.schedule = () => {}; App.setRole(role); App.view = 'settings'; UI.rerender(); }", role)

        async def click(pg, name):
            await pg.get_by_role('button', name=name, exact=True).first.click()

        async def yes(pg):
            await pg.locator('.modal').get_by_role('button', name='نعم', exact=True).click()

        # ================= R4-01 تعارض لم يثبت أول مرة ثم حُسم ثم أُعيد التحميل =================
        pg = await fresh()
        await pg.evaluate("""(async () => { const a = Store.add({ id: 'base', type: 'note', text: 'old' }); await Store.durable();
            Store.putMany = () => new Promise(() => {}); ImportDialog({ events: [Object.assign(Store.clean(a), { text: 'new' })] }); })()""")
        await click(pg, 'دمج السجلات فقط'); await click(pg, 'اعتماد نسخة الملف'); await yes(pg); await pg.wait_for_timeout(200)
        before = await pg.evaluate(STATE)
        await reopen(pg)   # معالج المغادرة الحقيقي يكتب نسخة الطوارئ
        r = await pg.evaluate(STATE)
        ok('R4-01 بعد إعادة التحميل: لا «قرار النسخة الأخرى + محتوى قديم» — التعارض مفتوح بالنسخة القديمة وبطاقة الاعتماد ظاهرة',
           consistent(r) and r['text'] == 'old' and r['open'] == 1 and r['card'] and r['notes'] == [], {'before': before, 'after': r})
        reo = await pg.evaluate("Store.conflicts[0].reopened && Store.conflicts[0].reopened.why")
        ok('R4-01 سبب إعادة الفتح محفوظ مع التعارض', bool(reo), reo)
        await click(pg, 'اعتماد نسخة الملف'); await yes(pg)
        await pg.wait_for_function("Store.openConflicts().length === 0 && Store.saved() && Store.raw.some(e => e.id !== 'base')")
        await reopen(pg)
        r = await pg.evaluate(STATE)
        ok('R4-01 إعادة الحسم: النسخة الجديدة والقرار والملاحظة ثابتة معاً بعد إعادة التحميل', r['text'] == 'new' and r['open'] == 0 and r['cf'][0]['resolved'] == 'other' and len(r['notes']) == 1, r)

        # ================= R4-02 التخزين البديل (بلا IndexedDB): لا قرار جزئي =================
        for failing, label in (('lm_events_v1', 'فشل كتابة السجل'), ('lm_conflicts_v1', 'فشل كتابة القرار')):
            pg = await fresh(noidb=True)
            idb = await pg.evaluate("Store.idbOk")
            await pg.evaluate(f"""(() => {{ const a = Store.add({{ id: 'base', type: 'note', text: 'old' }}); Backup.merge({{ events: [Object.assign(Store.clean(a), {{ text: 'new' }})] }}); UI.rerender();
                window.__set = Storage.prototype.setItem; Storage.prototype.setItem = function (k, v) {{ if (k === {json.dumps(failing)}) throw new Error('quota'); return window.__set.call(this, k, v); }}; }})()""")
            await click(pg, 'اعتماد نسخة الملف'); await yes(pg)
            await pg.wait_for_function("[...document.querySelectorAll('.toast')].some(t => t.textContent.includes('لم يُحسم'))")
            mem = await pg.evaluate(STATE)
            await pg.evaluate("(() => { Storage.prototype.setItem = window.__set; })()")
            await reopen(pg)
            r = await pg.evaluate(STATE)
            ok(f'R4-02 التخزين البديل، {label}: «لم يُحسم» وبعد إعادة الفتح التعارض مفتوح بالنسخة القديمة، لا قرار جزئي',
               idb is False and mem['open'] == 1 and mem['text'] == 'old' and consistent(r) and r['open'] == 1 and r['text'] == 'old', {'mem': mem, 'after': r})
        pg = await fresh(noidb=True)
        await pg.evaluate("""(() => { const a = Store.add({ id: 'base', type: 'note', text: 'old' }); Backup.merge({ events: [Object.assign(Store.clean(a), { text: 'new' })] }); UI.rerender(); })()""")
        await click(pg, 'اعتماد نسخة الملف'); await yes(pg)
        await pg.wait_for_function("Store.openConflicts().length === 0 && Store.raw.some(e => e.id !== 'base')")
        await reopen(pg)
        r = await pg.evaluate(STATE)
        ok('R4-02 التخزين البديل بلا عطل: الحسم والنسخة الجديدة ثابتان', r['text'] == 'new' and r['open'] == 0 and r['cf'][0]['resolved'] == 'other', r)

        # ================= R4-03 النسخة الكاملة تحمل التعارضات =================
        pg = await fresh('parent')
        r = await pg.evaluate("""(async () => {
            const a = Store.add({ id: 'base', type: 'note', text: 'old' }), k = Store.add({ id: 'kept', type: 'note', text: 'kept-local' }), d = Store.add({ id: 'done', type: 'note', text: 'done-old' });
            await Store.durable();
            Store.importEvents([Object.assign(Store.clean(a), { text: 'unique incoming from file' }), Object.assign(Store.clean(d), { text: 'done-new' })], { source: 'file' });
            Sync.switchTo('https://family', 'pub'); Store.importEvents([Object.assign(Store.clean(k), { text: 'kept-server' })], { server: Sync.sid() });
            await Store.durable();
            await Store.resolveConflict(Store.openConflicts('server:' + Sync.sid())[0], 'local', 'parent');
            await Store.resolveConflict(Store.conflicts.find(x => x.id === 'done'), 'other', 'parent');
            const backup = Backup.build(); const json = JSON.stringify(backup);
            await Store.reset();
            Backup.restoreDevice(Backup.parse(json)); await Store.durable();
            const pick = id => { const x = Store.conflicts.find(c => c.id === id); return x && { open: !x.resolved, choice: x.resolved ? x.resolved.choice : null, local: x.local.text, other: x.other.text }; };
            return { v: backup.formatVersion, counts: backup.counts, contains: json.includes('unique incoming'), leak: /"(sv|cf|rj|la|access_token|refresh_token)"/.test(json),
              base: pick('base'), kept: pick('kept'), done: pick('done'), doneText: Store.raw.find(e => e.id === 'done').text, n: Store.conflicts.length };
        })()""")
        ok('R4-03 النسخة تحمل التعارضات بنسختيها وقراراتها، بلا علامات خادم ولا رموز دخول', r['v'] == 3 and r['counts']['conflicts'] == 3 and r['contains'] and not r['leak'], r)
        ok('R4-03 تصدير ثم حذف ثم استعادة: تعارض الملف المفتوح بنسختيه، والاختلاف المُبقى، والاعتماد السابق كلها باقية',
           r['base'] == {'open': True, 'choice': None, 'local': 'old', 'other': 'unique incoming from file'} and r['kept']['choice'] == 'local' and r['done']['choice'] == 'other' and r['doneText'] == 'done-new' and r['n'] == 3, r)
        await reopen(pg, 'parent')
        r = await pg.evaluate("({ n: Store.conflicts.length, open: Store.openConflicts().map(x => x.id), status: Sync.cfg() ? Sync.st().cursor : 'x', session: Store.settings.sbSession })")
        ok('R4-03 بعد إعادة الفتح: التعارضات باقية، ولا جلسة دخول منقولة ولا مؤشر', r['n'] == 3 and r['open'] == ['base'] and r['session'] is None and r['status'] is None, r)
        # ملف يحمل تعارضاً لا ينطبق على سجلات هذا الجهاز: لا يُضاف
        r = await pg.evaluate("""(() => { const res = Store.importConflicts([{ key: 'zz|file|1', id: 'nowhere', source: 'file', at: 1, local: { id: 'nowhere', type: 'note', by: 'aya', ts: 1, day: '2026-11-01', text: 'a' }, other: { id: 'nowhere', type: 'note', by: 'aya', ts: 1, day: '2026-11-01', text: 'b' } },
            { key: 'bad', id: 'base', source: 'x', at: 1 }]); return res; })()""")
        ok('R4-03 تعارض لا ينطبق على سجل هنا أو سجل تالف: يُتخطى', r == {'added': 0, 'skipped': 2}, r)

        # اعتماد نسخة الملف ثم اعتماد نسخة الخادم لتعارض لاحق على السجل نفسه (يعيده إلى الأصل): لا يُعاد فتح الأول عند الفتح ولا بعد نسخة واستعادة
        pg = await fresh('parent')
        r = await pg.evaluate("""(async () => { const a = Store.add({ id: 'base', type: 'note', text: 'orig' }); await Store.durable();
            Store.importEvents([Object.assign(Store.clean(a), { text: 'from-file' })], { source: 'file' }); await Store.durable();
            await Store.resolveConflict(Store.openConflicts()[0], 'other', 'parent');
            Sync.switchTo('https://family', 'pub'); Store.importEvents([Object.assign(Store.clean(a), { text: 'orig' })], { server: Sync.sid() }); await Store.durable();
            await Store.resolveConflict(Store.openConflicts()[0], 'other', 'parent');
            const bk = JSON.stringify(Backup.build()); await Store.reset(); Backup.restoreDevice(Backup.parse(bk)); await Store.durable();
            return { text: Store.raw.find(e => e.id === 'base').text, open: Store.openConflicts().length, n: Store.conflicts.length }; })()""")
        await reopen(pg, 'parent')
        r2 = await pg.evaluate("({ text: Store.raw.find(e => e.id === 'base').text, open: Store.openConflicts().length })")
        ok('R4-01 حسمان متتاليان لسجل واحد (ملف ثم خادم يعيده للأصل): لا يُعاد فتح الأول، بعد الاستعادة وبعد إعادة الفتح', r == {'text': 'orig', 'open': 0, 'n': 2} and r2 == {'text': 'orig', 'open': 0}, {**r, 'after': r2})

        # ================= R4-04 حسم معلّق ثم حذف بيانات الجهاز ثم اكتمال متأخر =================
        pg = await fresh('parent')
        await pg.evaluate("""(async () => { const a = Store.add({ id: 'base', type: 'note', child: 'dalal', text: 'old' }); await Store.durable();
            Backup.merge({ events: [Object.assign(Store.clean(a), { text: 'new' })] }); await Store.durable(); UI.rerender();
            const p = Store.putMany.bind(Store); let once = true; Store.putMany = async (l, c) => { const ok = await p(l, c); if (once) { once = false; await new Promise(r => window.releaseSave = r); } return ok; }; })()""")
        await click(pg, 'اعتماد نسخة الملف'); await yes(pg); await pg.wait_for_function('!!window.releaseSave')
        await click(pg, 'حذف السجلات المحلية (مع تصفير المؤشر والمرفوضات والجلسة الجارية)'); await yes(pg)
        await pg.wait_for_function("[...document.querySelectorAll('.toast')].some(t => t.textContent.includes('حُذفت كل نسخ'))")
        await pg.evaluate('window.releaseSave()'); await pg.wait_for_timeout(400)
        r = await pg.evaluate(f"({{ raw: Store.raw.map(e => e.text), cf: Store.conflicts.length, toasts: {TOASTS} }})")
        ok('R4-04 اكتمال الحسم بعد الحذف: لا ملاحظة حسم ولا رسالة نجاح، وصفر سجلات وتعارضات', r['raw'] == [] and r['cf'] == 0 and not any('حُسم التعارض' in t for t in r['toasts']), r)
        await pg.evaluate('Store.durable()'); await reopen(pg, 'parent')
        r = await pg.evaluate("(() => { let ls = ''; for (let i = 0; i < localStorage.length; i++) ls += localStorage.getItem(localStorage.key(i)); return { raw: Store.raw.length, cf: Store.conflicts.length, leak: ls.includes('old') || ls.includes('new\"') }; })()")
        ok('R4-04 بعد إعادة الفتح: صفر سجلات وتعارضات ونسخ طوارئ', r == {'raw': 0, 'cf': 0, 'leak': False}, r)
        # رسالة «حُفظ» لعملية بدأت قبل الحذف لا تظهر بعده
        pg = await fresh('parent')
        await pg.evaluate("""(() => { const p = Store.putMany.bind(Store); let once = true; Store.putMany = async (l, c) => { const ok = await p(l, c); if (once) { once = false; await new Promise(r => window.releaseSave = r); } return ok; };
            Store.add({ type: 'note', text: 'قبل الحذف' }); UI.savedToast('سُجّلت الملاحظة'); })()""")
        await pg.wait_for_function('!!window.releaseSave')
        await pg.evaluate("Store.reset()"); await pg.evaluate('window.releaseSave()'); await pg.wait_for_timeout(300)
        r = await pg.evaluate(TOASTS)
        ok('R4-04 رسالة الحفظ لعملية سبقت الحذف لا تظهر بعده', not any('سُجّلت الملاحظة' in t for t in r), r)

        assert not errors, errors
        await b.close()
    httpd.shutdown()
    print(f'AUDIT R4 OK ({len(results)} حالة)')

asyncio.run(main())
