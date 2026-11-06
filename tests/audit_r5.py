"""اختبارات انحدار لمراجعة 0.13.3 المستقلة (LM0133-R5-01..03): تاريخ التعارضات في النسخة (سلسلة A→B→C)،
إلغاء الجلسات بعد حذف الجهاز أو تغيّر الحساب، وتعارضان على سجل واحد. كل حالة بأزرار الواجهة حيث وُصفت كذلك."""
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


TOASTS = "[...document.querySelectorAll('.toast')].map(t => t.textContent)"
CF = "Store.conflicts.map(x => ({ src: x.source.slice(0, 6), res: x.resolved ? x.resolved.choice + (x.resolved.auto ? '*' : '') : null, local: x.local.text, other: x.other.text, det: x.localAtDetection ? x.localAtDetection.text : null }))"


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
            await pg.evaluate("(role) => { Sync.schedule = () => {}; Sync.run = async () => {}; App.setRole(role); App.view = 'settings'; UI.rerender(); }", role)
            return pg

        async def reopen(pg, role='aya'):
            await pg.reload(); await pg.wait_for_function('Store.raw && Store.idbOk')
            await pg.evaluate("(role) => { Sync.schedule = () => {}; Sync.run = async () => {}; App.setRole(role); App.view = 'settings'; UI.rerender(); }", role)

        async def click(pg, name):
            await pg.get_by_role('button', name=name, exact=True).first.click()

        async def yes(pg):
            await pg.locator('.modal').get_by_role('button', name='نعم', exact=True).click()

        # ================= R5-01 تاريخ القرارات في النسخة: A→B→C ثم أطول، ودمج مكرر، ونسخة قديمة، وغير المرتبط =================
        pg = await fresh('parent')
        r = await pg.evaluate("""(async () => { const a = Store.add({ id: 'base', type: 'note', text: 'A' }); await Store.durable();
            for (const t of ['B', 'C', 'D']) { const cur = Store.raw.find(e => e.id === 'base'); Store.importEvents([Object.assign(Store.clean(cur), { text: t })], { source: 'file' }); await Store.durable();
              const ok = await Store.resolveConflict(Store.openConflicts()[0], 'other', 'parent'); if (!ok) throw new Error('resolve ' + t); }
            window.__bk = JSON.stringify(Backup.build()); return { text: Store.raw.find(e => e.id === 'base').text, n: Store.conflicts.length }; })()""")
        ok('R5-01 (تهيئة) سلسلة A→B→C→D: ثلاثة قرارات والنص D', r == {'text': 'D', 'n': 3}, r)
        BK = await pg.evaluate("window.__bk")
        await pg.evaluate(f"(async () => {{ await Store.reset(); ImportDialog(Backup.parse({json.dumps(BK)})); }})()")
        await click(pg, 'دمج السجلات فقط')
        await pg.wait_for_function("Store.saved() && Store.raw.length > 0")
        await reopen(pg, 'parent')
        r = await pg.evaluate(f"({{ text: Store.raw.find(e => e.id === 'base').text, cf: {CF}, open: Store.openConflicts().length }})")
        chain = [(c['local'], c['other'], c['res']) for c in r['cf']]
        ok('R5-01 تصدير ← حذف ← دمج ← إعادة فتح: النص D، والقرارات الثلاثة بنسخها باقية، ولا شيء مفتوح ولا قرار قديم مطبَّق',
           r['text'] == 'D' and sorted(chain) == [('A', 'B', 'other'), ('B', 'C', 'other'), ('C', 'D', 'other')] and r['open'] == 0, r)
        await pg.evaluate(f"(() => {{ ImportDialog(Backup.parse({json.dumps(BK)})); }})()")
        await click(pg, 'دمج السجلات فقط'); await pg.wait_for_function("Store.saved()")
        n = await pg.evaluate("Store.conflicts.length")
        ok('R5-01 دمج النسخة نفسها مرة ثانية: لا تضاعف للتاريخ', n == 3, n)
        # تعارض مفتوح في النسخة لا ينطبق على السجل هنا: يُذكر صراحة
        bk = await pg.evaluate("""(bk) => { const j = JSON.parse(bk); j.conflicts.push({ key: 'base|file|stale', id: 'base', source: 'file', at: 5,
            local: Object.assign({}, j.events[0], { text: 'X' }), other: Object.assign({}, j.events[0], { text: 'Y' }) }); return JSON.stringify(j); }""", BK)
        await pg.evaluate(f"(() => {{ ImportDialog(Backup.parse({json.dumps(bk)})); }})()")
        await click(pg, 'دمج السجلات فقط')
        r = await pg.evaluate("({ modal: [...document.querySelectorAll('.modal h2')].map(h => h.textContent), body: (document.querySelector('.modal') || {}).innerText || '', n: Store.conflicts.length })")
        ok('R5-01 تعارض مفتوح لا ينطبق على سجل هنا: نافذة «تعارضات لم تُربط» بمعرّفه، ولا يُضاف', 'تعارضات لم تُربط' in r['modal'] and 'base' in r['body'] and r['n'] == 3, r)
        await pg.locator('.modal').get_by_role('button', name='✕', exact=True).first.click()
        # نسخة بصيغة أقدم (2): تحذير صريح بأنها بلا تعارضات
        old = await pg.evaluate("(bk) => { const j = JSON.parse(bk); j.formatVersion = 2; delete j.conflicts; return JSON.stringify(j); }", BK)
        await pg.evaluate(f"(() => {{ ImportDialog(Backup.parse({json.dumps(old)})); }})()")
        txt = await pg.evaluate("document.querySelector('.modal').innerText")
        ok('R5-01 نسخة بصيغة 2: النافذة تقول إنها لا تحمل التعارضات (بلا حد إصدار خاطئ)', 'بصيغة أقدم (2) لا تحمل التعارضات' in txt and '0.13.1' not in txt, txt[-200:])

        # ================= R5-02 إلغاء جلسات معلّق ثم حذف الجهاز وتبديل الحساب =================
        SETUP = """(async (pos) => { App.setRole('asst'); Store.settings.timeOffset = Date.parse('2026-11-07T06:00:00Z') - Date.now();
            const list = sessionsFor('asst', App.now()); startSession(list[pos]); await Store.durable();
            const p = Store.putMany.bind(Store); let once = true; Store.putMany = async (...args) => { const ok = await p(...args); if (once) { once = false; await new Promise(r => window.releaseSave = r); } return ok; };
            cancelModal(); return list.length; })"""
        for pos, label in ((0, 'الجارية أول القائمة'), (2, 'الجارية وسط القائمة')):
            pg = await fresh('asst')
            n_sess = await pg.evaluate(f"({SETUP})({pos})")
            await click(pg, 'تأكيد الإلغاء'); await pg.wait_for_function('!!window.releaseSave')
            disabled = await pg.evaluate("[...document.querySelectorAll('.modal button')].find(b => b.textContent === 'تأكيد الإلغاء').disabled")
            await pg.locator('.modal').get_by_role('button', name='✕', exact=True).click()
            await pg.evaluate("(() => { App.setRole('parent'); App.view = 'settings'; UI.rerender(); })()")
            await click(pg, 'حذف السجلات المحلية (مع تصفير المؤشر والمرفوضات والجلسة الجارية)'); await yes(pg)
            await pg.wait_for_function("[...document.querySelectorAll('.toast')].some(t => t.textContent.includes('حُذفت كل نسخ'))")
            await pg.evaluate("(() => { App.setRole('asst'); UI.rerender(); window.releaseSave(); })()"); await pg.wait_for_timeout(500); await pg.evaluate("Store.durable()")
            r = await pg.evaluate(f"({{ raw: Store.raw.map(e => e.type), toasts: {TOASTS} }})")
            await reopen(pg, 'asst')
            n2 = await pg.evaluate("Store.raw.length")
            ok(f'R5-02 إلغاء معلّق ({label}، {n_sess} جلسات) ثم حذف وتبديل حساب: لا إلغاء ولا رسالة بعد الحذف، وصفر بعد إعادة الفتح، والزر معطّل أثناء الانتظار',
               disabled and r['raw'] == [] and not any('أُلغيت' in t for t in r['toasts']) and n2 == 0, {**r, 'afterReload': n2, 'disabled': disabled})
        # تبديل الحساب وحده (بلا حذف): العملية القديمة لا تكتب باسم الحساب الجديد
        pg = await fresh('asst')
        await pg.evaluate(f"({SETUP})(0)")
        await click(pg, 'تأكيد الإلغاء'); await pg.wait_for_function('!!window.releaseSave')
        n0 = await pg.evaluate("Store.raw.length")
        await pg.evaluate("(() => { App.setRole('aya'); window.releaseSave(); })()"); await pg.wait_for_timeout(500)
        r = await pg.evaluate("({ added: Store.raw.length - %d, cancels: Store.raw.filter(e => e.type === 'session_cancel').length })" % n0)
        ok('R5-02 تبديل الحساب أثناء الانتظار: لا إلغاءات بعده باسم أي حساب', r == {'added': 0, 'cancels': 0}, r)
        # فشل الحفظ (بلا حذف): رسالة فشل والزر يعود للعمل
        pg = await fresh('asst')
        await pg.evaluate("""(async () => { Store.settings.timeOffset = Date.parse('2026-11-07T06:00:00Z') - Date.now(); window.__put = Store.putMany.bind(Store); Store.putMany = async () => false; cancelModal(); })()""")
        await click(pg, 'تأكيد الإلغاء')
        await pg.wait_for_function("[...document.querySelectorAll('.toast')].some(t => t.textContent.includes('تعذّر'))")
        r = await pg.evaluate("({ btn: !![...document.querySelectorAll('.modal button')].find(b => b.textContent === 'تأكيد الإلغاء' && !b.disabled) })")
        ok('R5-02 فشل الحفظ: «تعذّر» صريحة والزر متاح لإعادة المحاولة', r['btn'], r)
        await pg.evaluate("(() => { Store.putMany = window.__put; })()")
        await click(pg, 'تأكيد الإلغاء')
        await pg.wait_for_function("[...document.querySelectorAll('.toast')].some(t => /^أُلغيت \\d+ جلسة$/.test(t.textContent))")
        await reopen(pg, 'asst')
        n = await pg.evaluate("Store.raw.filter(e => e.type === 'session_cancel').length")
        ok('R5-02 بعد التعافي: الإلغاءات ثابتة بعد إعادة الفتح', n > 0, n)

        # ================= R5-03 تعارضان مفتوحان على سجل واحد =================
        SETUP3 = """(async () => { const a = Store.add({ id: 'base', type: 'note', text: 'A' }); await Store.durable();
            Store.importEvents([Object.assign(Store.clean(a), { text: 'B' })], { source: 'file' });
            Sync.switchTo('https://family', 'pub'); Store.importEvents([Object.assign(Store.clean(a), { text: 'C' })], { server: Sync.sid() });
            await Store.durable(); App.view = 'settings'; UI.rerender(); window.__C = Object.assign(Store.clean(a), { text: 'C' }); })()"""
        pg = await fresh()
        await pg.evaluate(SETUP3)
        await click(pg, 'اعتماد نسخة الملف'); await yes(pg)
        await pg.wait_for_function("Store.openConflicts().length === 1 && Store.saved()")
        r = await pg.evaluate(f"({{ card: document.querySelector('main').innerText, cf: {CF}, evcf: (Store.raw.find(e => e.id === 'base').cf || []).length }})")
        card = r['card']
        ok('R5-03 بعد اعتماد نسخة الملف: بطاقة تعارض الخادم تعرض المحتوى الحالي B ونسخة الاكتشاف A، والسجل ما زال معلَّماً بالاختلاف مع الخادم',
           'هذا الجهاز الآن: ' in card and 'عند اكتشاف التعارض كان' in card and any(c['src'] == 'server' and c['res'] is None and c['local'] == 'B' and c['det'] == 'A' for c in r['cf']) and r['evcf'] == 1, r['cf'])
        await click(pg, 'إبقاء نسخة الجهاز'); await yes(pg)
        await pg.wait_for_function("Store.openConflicts().length === 0 && Store.saved()")
        r = await pg.evaluate("(async () => { const kept = Store.keptDiffs().length; Store.importEvents([window.__C], { server: Sync.sid() }); await Store.durable(); return { kept, after: Store.keptDiffs().length, open: Store.openConflicts().length, n: Store.conflicts.length, text: Store.raw.find(e => e.id === 'base').text }; })()")
        ok('R5-03 «إبقاء» بعدها مرتبط بـB: اختلاف مُبقى ظاهر، ووصول C نفسها مجدداً لا يفتح تعارضاً', r == {'kept': 1, 'after': 1, 'open': 0, 'n': 2, 'text': 'B'}, r)
        await reopen(pg)
        r = await pg.evaluate("(async () => { Store.importEvents([window.__C || Object.assign(Store.clean(Store.raw.find(e => e.id === 'base')), { text: 'C' })], { server: Sync.sid() }); await Store.durable(); return { kept: Store.keptDiffs().length, open: Store.openConflicts().length, n: Store.conflicts.length }; })()")
        ok('R5-03 بعد إعادة الفتح ووصول C مجدداً: الاختلاف المُبقى باقٍ ولا تعارض مكرر', r == {'kept': 1, 'open': 0, 'n': 2}, r)
        # الفرع الآخر: اعتماد الثاني (الخادم) بدل الإبقاء
        pg = await fresh()
        await pg.evaluate(SETUP3)
        await click(pg, 'اعتماد نسخة الملف'); await yes(pg); await pg.wait_for_function("Store.openConflicts().length === 1 && Store.saved()")
        await click(pg, 'اعتماد نسخة الخادم'); await yes(pg); await pg.wait_for_function("Store.openConflicts().length === 0 && Store.saved()")
        await reopen(pg)
        r = await pg.evaluate("(() => { const e = Store.raw.find(x => x.id === 'base'); return { text: e.text, sv: e.sv || [], cf: e.cf || [], open: Store.openConflicts().length, kept: Store.keptDiffs().length }; })()")
        ok('R5-03 اعتماد الثاني (الخادم): النص C، «على الخادم» بلا علامة اختلاف، ولا مفتوح ولا مُبقى بعد إعادة الفتح', r == {'text': 'C', 'sv': ['https://family'], 'cf': [], 'open': 0, 'kept': 0}, r)
        # اعتماد نسخة تساوي النسخة الأخرى للتعارض الثاني: يُغلق تلقائياً
        pg = await fresh()
        await pg.evaluate("""(async () => { const a = Store.add({ id: 'base', type: 'note', text: 'A' }); await Store.durable();
            Store.importEvents([Object.assign(Store.clean(a), { text: 'B' })], { source: 'file' });
            Sync.switchTo('https://family', 'pub'); Store.importEvents([Object.assign(Store.clean(a), { text: 'B' })], { server: Sync.sid() });
            await Store.durable(); App.view = 'settings'; UI.rerender(); })()""")
        await click(pg, 'اعتماد نسخة الملف'); await yes(pg); await pg.wait_for_function("Store.openConflicts().length === 0 && Store.saved()")
        await reopen(pg)
        r = await pg.evaluate(f"(() => {{ const e = Store.raw.find(x => x.id === 'base'); return {{ text: e.text, sv: e.sv || [], cf: (e.cf || []).length, cfs: {CF} }}; }})()")
        ok('R5-03 النسخة المعتمدة تطابق نسخة الخادم: تعارض الخادم يُغلق تلقائياً و«على الخادم» صحيحة', r['text'] == 'B' and r['sv'] == ['https://family'] and r['cf'] == 0 and any(c['src'] == 'server' and c['res'] == 'other*' for c in r['cfs']), r)
        # فشل الحفظ أثناء حسم يغيّر التعارض الشقيق: يعود الشقيق كما كان
        pg = await fresh()
        await pg.evaluate(SETUP3)
        await pg.evaluate("(() => { window.__put = Store.putMany.bind(Store); Store.putMany = async () => false; })()")
        await click(pg, 'اعتماد نسخة الملف'); await yes(pg)
        await pg.wait_for_function("[...document.querySelectorAll('.toast')].some(t => t.textContent.includes('لم يُحسم'))")
        r = await pg.evaluate(f"({{ text: Store.raw.find(e => e.id === 'base').text, cf: {CF}, open: Store.openConflicts().length }})")
        ok('R5-03 فشل حفظ الحسم: السجل A والتعارضان مفتوحان كما كانا (الشقيق بنسخته الأصلية)', r['text'] == 'A' and r['open'] == 2 and all(c['res'] is None and c['local'] == 'A' and c['det'] is None for c in r['cf']), r)

        assert not errors, errors
        await b.close()
    httpd.shutdown()
    print(f'AUDIT R5 OK ({len(results)} حالة)')

asyncio.run(main())
