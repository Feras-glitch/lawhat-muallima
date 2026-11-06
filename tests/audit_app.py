"""0.14: التراجع عن سجل بعينه من «السجلات»، وجسر تطبيق أندرويد (حفظ الملفات، النسخ، زر الرجوع، التحديث).
الجسر يُحاكى في المتصفح (window.LawhatAndroid) بالواجهة نفسها التي يقدّمها MainActivity."""
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
# محاكاة جسر MainActivity: يسجّل النداءات، والحفظ ينتظر «اختيار المكان» (window.__finishSave)
BRIDGE = """() => { window.__calls = []; window.LawhatAndroid = {
  saveFile: (id, name, mime, text) => { window.__calls.push(['save', id, name, mime, text.length]); window.__finishSave = (ok, err) => window.LM_fileSaved(id, ok, err); },
  copy: t => { window.__calls.push(['copy', t]); return true; },
  openExternal: u => window.__calls.push(['open', u]),
  appVersion: () => '0.14.0 (1400)' }; }"""


async def main():
    httpd = socketserver.TCPServer(('127.0.0.1', 0), functools.partial(Q, directory=str(ROOT / 'dist')))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    port = httpd.server_address[1]
    errors = []
    async with async_playwright() as p:
        b = await p.chromium.launch(**BROWSER_OPTS)

        async def fresh(role='aya', bridge=False):
            ctx = await b.new_context(viewport={'width': 390, 'height': 844}, locale='ar', timezone_id='Africa/Cairo')
            if bridge:
                await ctx.add_init_script(f"({BRIDGE})()")
            pg = await ctx.new_page()
            pg.on('pageerror', lambda e: errors.append(str(e)))
            pg.on('dialog', lambda d: asyncio.ensure_future(d.accept()))
            await pg.goto(f'http://127.0.0.1:{port}/index.html'); await pg.wait_for_function('Store.raw && Store.idbOk')
            await pg.evaluate("(role) => { Sync.schedule = () => {}; Sync.run = async () => {}; App.setRole(role); }", role)
            return pg

        async def logs(pg):
            await pg.evaluate("(() => { App.view = 'logs'; App.sub = {}; UI.rerender(); })()")

        async def undo_buttons(pg):
            return await pg.evaluate("[...document.querySelectorAll('main tr')].filter(tr => [...tr.querySelectorAll('button')].some(b => b.textContent === 'تراجع')).map(tr => tr.innerText.replace(/\\s+/g, ' ').slice(0, 60))")

        SEED = """(() => { const mk = (by, o) => { App.role = ROLES[by]; const e = Store.add(o); return e.id; };
            window.__ids = { asstOut: mk('asst', { type: 'outcome', child: 'dalal', page: 582, step: 'far', result: 'clean' }),
              ayaNote: mk('aya', { type: 'note', child: 'farah', text: 'ملاحظة آية' }),
              parNote: mk('parent', { type: 'note', child: 'karim', text: 'ملاحظة ولي الأمر' }) }; })()"""

        # ================= الصلاحيات: زر التراجع يظهر حيث يسمح الخادم فقط =================
        seen = {}
        for role in ('aya', 'asst', 'parent'):
            pg = await fresh(role)
            await pg.evaluate(SEED); await pg.evaluate(f"App.setRole('{role}')"); await logs(pg)
            seen[role] = sorted(x.split(' · ')[-1][:12] if ' · ' in x else x[:12] for x in await undo_buttons(pg))
            seen[role] = await pg.evaluate("""(() => { const rows = [...document.querySelectorAll('main tr')]; const has = t => rows.some(tr => tr.innerText.includes(t) && [...tr.querySelectorAll('button')].some(b => b.textContent === 'تراجع'));
                return { asstOut: has('سالم') || has('ص582'), ayaNote: has('ملاحظة آية'), parNote: has('ملاحظة ولي الأمر') }; })()""")
        ok('زر التراجع بالصلاحيات نفسها: آية (سجلها وسجل المساعدة)، المساعدة (سجلها)، ولي الأمر (سجله)',
           seen == {'aya': {'asstOut': True, 'ayaNote': True, 'parNote': False}, 'asst': {'asstOut': True, 'ayaNote': False, 'parNote': False}, 'parent': {'asstOut': False, 'ayaNote': False, 'parNote': True}}, seen)

        # ================= التراجع من الواجهة: ملخص، سبب، تأكيد، شطب، أثر محفوظ =================
        pg = await fresh('aya')
        await pg.evaluate(SEED); await pg.evaluate("App.setRole('aya')"); await logs(pg)
        row = pg.locator('main tr').filter(has_text='ص582')
        await row.get_by_role('button', name='تراجع', exact=True).click()
        body = await pg.evaluate("document.querySelector('.modal').innerText")
        ok('نافذة التراجع: ملخص السجل وتاريخه ومن سجّله، وأن لا شيء يُحذف', 'دلال' in body and 'ص582' in body and 'المساعدة' in body and 'لا يُحذف شيء' in body, body[:200])
        await pg.locator('.modal select').select_option('أخرى')
        await pg.get_by_role('button', name='تراجع عن هذا السجل', exact=True).click()
        r = await pg.evaluate(f"({{ modal: !!document.querySelector('.modal'), undos: Store.raw.filter(e => e.type === 'undo').length, toasts: {TOASTS} }})")
        ok('«أخرى» بلا توضيح: لا تراجع ورسالة، والنافذة باقية', r['modal'] and r['undos'] == 0 and any('سبب' in t for t in r['toasts']), r)
        await pg.locator('.modal input').fill('سُجّلت لدلال بدل فرح')
        await pg.get_by_role('button', name='تراجع عن هذا السجل', exact=True).click()
        await pg.wait_for_function("!document.querySelector('.modal') && Store.saved()")
        r = await pg.evaluate("""(() => { const u = Store.raw.find(e => e.type === 'undo'); const t = Store.raw.find(e => e.id === window.__ids.asstOut);
            return { by: u.by, target: u.target === t.id, reason: u.reason, live: Store.events.some(e => e.id === t.id), struck: [...document.querySelectorAll('main tr')].some(tr => tr.innerText.includes('ص582') && tr.getAttribute('style') && tr.getAttribute('style').includes('line-through')),
              btn: [...document.querySelectorAll('main tr')].some(tr => tr.innerText.includes('ص582') && [...tr.querySelectorAll('button')].some(b => b.textContent === 'تراجع')) }; })()""")
        ok('التراجع: حدث undo باسم آية وسببه، والسجل مشطوب بلا زر، وخارج الحسابات', r == {'by': 'aya', 'target': True, 'reason': 'سُجّلت لدلال بدل فرح', 'live': False, 'struck': True, 'btn': False}, r)
        await pg.reload(); await pg.wait_for_function('Store.raw && Store.idbOk'); await pg.evaluate("(() => { Sync.run = async () => {}; App.setRole('aya'); App.view = 'logs'; UI.rerender(); })()")
        r = await pg.evaluate("({ undos: Store.raw.filter(e => e.type === 'undo').length, live: Store.events.some(e => e.id === Store.raw.find(x => x.type === 'outcome').id), undoRowBtn: [...document.querySelectorAll('main tr')].filter(tr => tr.innerText.includes('تراجع') && [...tr.querySelectorAll('button')].length).length })")
        ok('بعد إعادة الفتح: التراجع ثابت، وسطر التراجع نفسه بلا زر', r['undos'] == 1 and r['live'] is False, r)
        # ضغطتان سريعتان = تراجع واحد
        pg = await fresh('aya')
        await pg.evaluate(SEED); await pg.evaluate("App.setRole('aya')"); await logs(pg)
        await pg.locator('main tr').filter(has_text='ملاحظة آية').get_by_role('button', name='تراجع', exact=True).click()
        await pg.evaluate("(() => { const b = [...document.querySelectorAll('.modal button')].find(x => x.textContent === 'تراجع عن هذا السجل'); b.click(); b.click(); b.click(); })()")
        await pg.wait_for_function("Store.saved()"); await pg.wait_for_timeout(200)
        n = await pg.evaluate("Store.raw.filter(e => e.type === 'undo').length")
        ok('ثلاث ضغطات سريعة = تراجع واحد', n == 1, n)
        # حذف بيانات الجهاز أثناء انتظار حفظ التراجع: لا شيء بعده
        pg = await fresh('aya')
        await pg.evaluate(SEED); await pg.evaluate("App.setRole('aya')"); await logs(pg)
        await pg.evaluate("""(() => { const p = Store.putMany.bind(Store); let once = true; Store.putMany = async (...a) => { const ok = await p(...a); if (once) { once = false; await new Promise(r => window.releaseSave = r); } return ok; }; })()""")
        await pg.locator('main tr').filter(has_text='ملاحظة آية').get_by_role('button', name='تراجع', exact=True).click()
        await pg.get_by_role('button', name='تراجع عن هذا السجل', exact=True).click(); await pg.wait_for_function('!!window.releaseSave')
        await pg.evaluate("Store.reset()"); await pg.evaluate('window.releaseSave()'); await pg.wait_for_timeout(400)
        r = await pg.evaluate(f"({{ raw: Store.raw.length, toasts: {TOASTS} }})")
        ok('حذف الجهاز أثناء حفظ التراجع: لا رسالة «تم التراجع» ولا سجلات بعده', r['raw'] == 0 and not any('تم التراجع' in t for t in r['toasts']), r)

        # ================= جسر التطبيق =================
        pg = await fresh('parent', bridge=True)
        await pg.evaluate("Store.add({ type: 'note', text: 'x' })"); await pg.evaluate("(() => { App.view = 'settings'; UI.rerender(); })()")
        txt = await pg.evaluate("document.querySelector('main').innerText")
        ok('داخل التطبيق: بطاقة «تطبيق أندرويد» برقم الإصدار، ونص التخزين يصف مساحة التطبيق', 'تطبيق أندرويد' in txt and '0.14.0 (1400)' in txt and 'مساحة التطبيق الخاصة' in txt, txt[-300:])
        await pg.get_by_role('button', name='تصدير نسخة كاملة', exact=False).first.click()
        r = await pg.evaluate("({ calls: window.__calls, lb: Store.settings.lastBackup || null })")
        ok('التصدير في التطبيق: نافذة «حفظ باسم» عبر الجسر، و«آخر نسخة» لا تُسجَّل قبل الكتابة', r['calls'] and r['calls'][0][0] == 'save' and r['calls'][0][2].startswith('lawhat-backup-') and r['calls'][0][3] == 'application/json' and r['lb'] is None, r)
        await pg.evaluate("window.__finishSave(false, null)")
        r = await pg.evaluate(f"({{ lb: Store.settings.lastBackup || null, toasts: {TOASTS} }})")
        ok('إلغاء الحفظ: لا «آخر نسخة»، ورسالة «أُلغي الحفظ»', r['lb'] is None and any('أُلغي الحفظ' in t for t in r['toasts']), r)
        await pg.get_by_role('button', name='تصدير نسخة كاملة', exact=False).first.click()
        await pg.evaluate("window.__finishSave(true)")
        r = await pg.evaluate(f"({{ lb: Store.settings.lastBackup || null, toasts: {TOASTS} }})")
        ok('حفظ الملف فعلاً: «آخر نسخة» تُسجَّل ورسالة باسم الملف', r['lb'] is not None and any('حُفظ الملف: lawhat-backup-' in t for t in r['toasts']), r)
        await pg.evaluate("copyText('نص للنسخ')")
        r = await pg.evaluate("window.__calls.filter(c => c[0] === 'copy')")
        ok('النسخ عبر حافظة أندرويد', r == [['copy', 'نص للنسخ']], r)
        # زر الرجوع: يغلق النافذة، ثم يعود للرئيسية، ثم يترك الخروج للتطبيق
        await pg.evaluate("UI.confirm('اختبار', () => {})")
        r1 = await pg.evaluate("[window.LM_back(), !!document.querySelector('.modal')]")
        r2 = await pg.evaluate("[window.LM_back(), App.view]")
        r3 = await pg.evaluate("window.LM_back()")
        ok('زر الرجوع: يغلق النافذة، ثم يعود إلى اللوحة، ثم يُترك للتطبيق', r1 == [True, False] and r2 == [True, 'dash'] and r3 is False, [r1, r2, r3])
        # التحديث: إصدار أحدث منشور = لافتة وزر تنزيل يفتح المتصفح؛ الإصدار نفسه = لا لافتة
        for tag, expect in (('v99.0.0', True), ('v' + await pg.evaluate("BUILD.version"), False)):
            await pg.evaluate(f"""(async () => {{ window.fetch = async u => ({{ ok: true, json: async () => ({{ tag_name: {json.dumps(tag)} }}) }}); delete Store.settings.updateCheck; await AppUpdate.check(true); App.view = 'dash'; UI.rerender(); }})()""")
            banner = await pg.evaluate("document.querySelector('main').innerText.includes('يتوفر إصدار أحدث من التطبيق')")
            ok(f'التحديث ({tag}): لافتة {"ظاهرة" if expect else "غائبة"}', banner == expect, banner)
        await pg.evaluate(f"""(async () => {{ window.fetch = async u => ({{ ok: true, json: async () => ({{ tag_name: 'v99.0.0' }}) }}); await AppUpdate.check(true); App.view = 'dash'; UI.rerender(); }})()""")
        await pg.get_by_role('button', name='تنزيل التحديث', exact=True).first.click()
        r = await pg.evaluate("window.__calls.filter(c => c[0] === 'open').map(c => c[1])")
        ok('تنزيل التحديث يفتح رابط APK الثابت في المتصفح', r == ['https://github.com/Feras-glitch/lawhat-muallima/releases/latest/download/lawhat-muallima.apk'], r)
        # في المتصفح العادي: لا بطاقة تطبيق ولا لافتة تحديث ولا جسر
        pg = await fresh('parent')
        await pg.evaluate("(() => { Store.settings.updateCheck = { at: Date.now(), v: '99.0.0' }; App.view = 'settings'; UI.rerender(); })()")
        txt = await pg.evaluate("document.querySelector('main').innerText")
        ok('في المتصفح: لا بطاقة «تطبيق أندرويد» ولا لافتة تحديث', 'تطبيق أندرويد' not in txt and 'يتوفر إصدار أحدث' not in txt, txt[-120:])

        assert not errors, errors
        await b.close()
    httpd.shutdown()
    print(f'AUDIT APP OK ({len(results)} حالة)')

asyncio.run(main())
