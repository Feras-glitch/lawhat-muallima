"""اختبارات انحدار لمراجعة 0.13.1 المستقلة (LM0131-R3-01..06): حفظ التعارضات وحسمها وحذف نسخها، وEnter في نافذة الرقم.
كل حالة من برنامج إعادة الإنتاج في التقرير بمعيار قبوله. IndexedDB حقيقي عبر HTTP، وإعادة تحميل حقيقية.
فرع «إبقاء نسخة الجهاز» واعتماد نسخة الخادم على PostgreSQL بسياساته في tests/restore_e2e.py (C10)."""
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


STATUS = "UI.statusInner().map(n => typeof n === 'string' ? n : n.textContent).join('')"
# كل ما على القرص: IndexedDB (السجلات والتعارضات) وكل مفاتيح localStorage — للبحث عن أي أثر لنص سجل
DISK = """(async () => {
  const db = await new Promise(r => { const q = indexedDB.open('lawhat_muallima'); q.onsuccess = () => r(q.result); q.onerror = () => r(null); });
  const all = await new Promise(r => { const tx = db.transaction(['events', 'conflicts'], 'readonly'); const a = tx.objectStore('events').getAll(), b = tx.objectStore('conflicts').getAll(); tx.oncomplete = () => r({ ev: a.result, cf: b.result }); });
  db.close();
  const ls = {}; for (let i = 0; i < localStorage.length; i++) { const k = localStorage.key(i); ls[k] = localStorage.getItem(k); }
  return { ev: all.ev, cf: all.cf, ls, text: JSON.stringify(all) + JSON.stringify(ls) };
})()"""
# خادم محاكى صغير (للفرع المحلي): صفوف بالمعرّف، ويعيد ما أُدرج فعلاً، ويعدّ طلبات المطابقة
MOCK_SERVER = """(rowsIn) => { const rows = new Map(rowsIn.map(r => [r.id, r])); window.__fetchIds = 0;
  window.fetch = async (u, o) => { const s = String(u); if (s.includes('/profiles?')) return { ok: true, json: async () => [{ role: Store.settings.sbRole }] };
    if (o && o.method === 'POST') { const ins = []; for (const row of JSON.parse(o.body)) if (!rows.has(row.id)) { rows.set(row.id, Object.assign({}, row, { inserted_at: '2026-11-06T21:00:00Z' })); ins.push({ id: row.id }); } return { ok: true, json: async () => ins }; }
    const q = new URL(s).searchParams;
    if (q.get('select') === 'id' && q.get('order')) { window.__fetchIds++; return { ok: true, json: async () => [...rows.keys()].sort().map(id => ({ id })) }; }
    if (q.get('select') === 'id' && q.get('limit') === '1') return { ok: true, headers: { get: () => '0-0/' + rows.size }, json: async () => [] };
    if (q.get('id')) { const want = decodeURIComponent(q.get('id')).replace(/^in\\.\\(|\\)$/g, '').split(',').map(x => x.replace(/^"|"$/g, '')); return { ok: true, json: async () => want.filter(id => rows.has(id)).map(id => rows.get(id)) }; }
    const cur = Sync.st().cursor; return { ok: true, json: async () => [...rows.values()].filter(r => !cur || Date.parse(r.inserted_at) > Date.parse(cur.t) - 5000) }; };
  window.__rows = rows; }"""


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
            pg.on('dialog', lambda d: asyncio.ensure_future(d.accept()))  # تحذير المغادرة أثناء كتابة معلّقة
            await pg.goto(f'http://127.0.0.1:{port}/index.html'); await pg.wait_for_function('Store.raw && Store.idbOk')
            await pg.evaluate("(role) => { Sync.schedule = () => {}; App.setRole(role); }", role)
            return pg

        async def reopen(pg, role='aya'):
            await pg.reload(); await pg.wait_for_function('Store.raw && Store.idbOk')
            await pg.evaluate("(role) => { Sync.schedule = () => {}; App.setRole(role); }", role)

        async def click(pg, name):
            await pg.get_by_role('button', name=name, exact=True).first.click()

        async def confirm(pg):
            await pg.locator('.modal').get_by_role('button', name='نعم', exact=True).click()

        # ================= R3-01 الحذف يمحو كل نسخ بيانات الأحداث =================
        pg = await fresh('parent')
        await pg.evaluate("""(async () => {
            const a = Store.add({ id: 'family-secret', type: 'note', child: 'c1', text: 'معلومة العائلة الأصلية' });
            const b = Store.add({ id: 'kept-secret', type: 'note', child: 'c2', text: 'سر محفوظ أصلي' });
            await Store.durable();
            Store.importEvents([Object.assign(Store.clean(a), { text: 'معلومة العائلة البديلة' })], { source: 'file' });
            Sync.switchTo('https://family-a', 'pub'); const sid = Sync.sid();
            Store.importEvents([Object.assign(Store.clean(b), { text: 'سر محفوظ من الخادم' })], { server: sid });
            await Store.durable();
            await Store.resolveConflict(Store.openConflicts('server:' + sid)[0], 'local', 'parent');   /* محسوم: يبقى بنسختيه */
            Store.settings.active = { sid: 'x', note: 'مسودة سرية للجلسة' }; Store.saveSettings();
        })()""")
        before = await pg.evaluate(DISK)
        ok('R3-01 (تهيئة) تعارض ملف مفتوح وتعارض خادم محسوم، ونسخهما في IndexedDB لا في الإعدادات',
           len(before['cf']) == 2 and 'معلومة العائلة البديلة' in before['text'] and 'conflicts' not in json.loads(before['ls']['lm_settings_v1']),
           {'cf': len(before['cf'])})
        await pg.evaluate("App.view = 'settings'; UI.rerender();")
        await click(pg, 'حذف السجلات المحلية (مع تصفير المؤشر والمرفوضات والجلسة الجارية)'); await confirm(pg)
        await pg.wait_for_function("[...document.querySelectorAll('.toast')].some(t => t.textContent.includes('حُذفت'))")
        await reopen(pg, 'parent')
        await pg.evaluate("Sync.switchTo('https://separate-b', 'pub'); App.view = 'settings'; UI.rerender();")
        after = await pg.evaluate(DISK)
        mem = await pg.evaluate("({ raw: Store.raw.length, open: Store.openConflicts().length, all: Store.conflicts.length, ui: document.querySelector('main').innerText })")
        secrets = ['معلومة العائلة', 'سر محفوظ', 'مسودة سرية']
        ok('R3-01 بعد الحذف وإعادة الفتح والانتقال المنفصل: صفر أحداث وصفر تعارضات، ولا نص سجل على القرص ولا في الواجهة',
           mem['raw'] == 0 and mem['all'] == 0 and after['ev'] == [] and after['cf'] == [] and not any(x in after['text'] or x in mem['ui'] for x in secrets),
           {'raw': mem['raw'], 'all': mem['all'], 'ev': len(after['ev']), 'cf': len(after['cf']), 'leak': [x for x in secrets if x in after['text'] or x in mem['ui']]})

        # فشل حفظ الإعدادات أثناء الحذف: لا يُعلن الاكتمال
        pg = await fresh('parent')
        r = await pg.evaluate("""(async () => { Store.add({ type: 'note', text: 'x' }); await Store.durable();
            const set = Storage.prototype.setItem; Storage.prototype.setItem = function (k, v) { if (k === 'lm_settings_v1') throw new Error('quota'); return set.call(this, k, v); };
            const res = await Store.reset(); Storage.prototype.setItem = set; return res; })()""")
        ok('R3-01 فشل حفظ الإعدادات أثناء الحذف = الحذف لم يكتمل (لا نجاح معلن)', r is False, r)

        # تعارضات الإصدار السابق داخل الإعدادات: تُنقل إلى IndexedDB وتُمحى من الإعدادات، ثم يمحوها الحذف
        pg = await fresh('parent')
        await pg.evaluate("""(async () => { const e = Store.add({ id: 'legacy', type: 'note', text: 'قديم محلي' }); await Store.durable();
            const s = JSON.parse(localStorage.getItem('lm_settings_v1')); s.conflicts = [{ id: 'legacy', source: 'file', at: 1, local: Store.clean(e), other: Object.assign(Store.clean(e), { text: 'قديم من ملف' }) }];
            localStorage.setItem('lm_settings_v1', JSON.stringify(s)); })()""")
        await reopen(pg, 'parent')
        d = await pg.evaluate(DISK)
        r = await pg.evaluate("({ open: Store.openConflicts().length, other: Store.openConflicts()[0] && Store.openConflicts()[0].other.text })")
        ok('R3-01 ترحيل تعارضات 0.13.1 من الإعدادات إلى IndexedDB', r == {'open': 1, 'other': 'قديم من ملف'} and len(d['cf']) == 1 and 'قديم من ملف' not in d['ls']['lm_settings_v1'], {**r, 'cf': len(d['cf'])})
        await pg.evaluate("Store.reset()"); await reopen(pg, 'parent')
        d = await pg.evaluate(DISK)
        ok('R3-01 والحذف يمحو المُرحَّل', d['cf'] == [] and 'قديم' not in d['text'], {'cf': len(d['cf'])})

        # ================= R3-02 اعتماد نسخة أخرى: لا مزيج «نسخة قديمة + حسم مسجل» =================
        SETUP_ADOPT = """(async () => { const x = Store.add({ id: 'replace-me', type: 'note', child: 'c1', text: 'النسخة القديمة' }); await Store.durable();
            Store.importEvents([Object.assign(Store.clean(x), { text: 'النسخة المعتمدة الجديدة' })], { source: 'file' }); await Store.durable(); App.view = 'settings'; UI.rerender(); })()"""
        STATE = """({ text: Store.raw.find(e => e.id === 'replace-me').text, open: Store.openConflicts().length, resolved: (Store.conflicts[0] || {}).resolved || null,
            notes: Store.raw.filter(x => x.type === 'note' && x.id !== 'replace-me').map(x => x.text), saved: Store.saved() })"""
        # (أ) كتابة معلّقة ثم إعادة تحميل (بلا نسخة طوارئ ولا معها)
        for emergency in (False, True):
            pg = await fresh()
            await pg.evaluate(SETUP_ADOPT)
            await pg.evaluate("(() => { Store.putMany = () => new Promise(() => {}); })()")
            await click(pg, 'اعتماد نسخة الملف'); await confirm(pg)
            await pg.wait_for_timeout(200)
            if emergency:
                await pg.evaluate("Store.emergencySave()")
            await reopen(pg)
            r = await pg.evaluate(STATE)
            ok(f'R3-02 اعتماد ثم إعادة تحميل قبل ثبوت الكتابة{" (مع نسخة طوارئ)" if emergency else ""}: النسخة القديمة والتعارض مفتوح، لا حسم مسجل ولا ملاحظة',
               r['text'] == 'النسخة القديمة' and r['open'] == 1 and r['resolved'] is None and r['notes'] == [], r)
            # وبعدها يُحسم حسماً صحيحاً
            await pg.evaluate("App.view = 'settings'; UI.rerender();")
            await click(pg, 'اعتماد نسخة الملف'); await confirm(pg)
            await pg.wait_for_function("Store.openConflicts().length === 0 && Store.saved() && Store.raw.some(x => x.type === 'note' && x.id !== 'replace-me')")
            await reopen(pg)
            r = await pg.evaluate(STATE)
            ok(f'R3-02 إعادة الحسم بعد الفتح{" (طوارئ)" if emergency else ""}: النسخة الجديدة والقرار والملاحظة كلها ثابتة بعد إعادة التحميل',
               r['text'] == 'النسخة المعتمدة الجديدة' and r['open'] == 0 and r['resolved']['choice'] == 'other' and len(r['notes']) == 1, r)
        # (ب) فشل الكتابة: لا حسم، والتعارض باقٍ، ورسالة صريحة؛ وبعد إعادة التحميل كذلك
        pg = await fresh()
        await pg.evaluate(SETUP_ADOPT)
        await pg.evaluate("(() => { window.__put = Store.putMany.bind(Store); Store.putMany = async () => false; })()")
        await click(pg, 'اعتماد نسخة الملف'); await confirm(pg)
        await pg.wait_for_function("[...document.querySelectorAll('.toast')].some(t => t.textContent.includes('لم يُحسم'))")
        r = await pg.evaluate(STATE)
        ok('R3-02 فشل الكتابة: «لم يُحسم» صريحة، والنسخة القديمة والتعارض مفتوح في الذاكرة', r['text'] == 'النسخة القديمة' and r['open'] == 1 and r['resolved'] is None and r['notes'] == [], r)
        await pg.evaluate("Store.putMany = window.__put; Store.flush()")
        await pg.wait_for_function("Store.saved()")
        await reopen(pg)
        r = await pg.evaluate(STATE)
        ok('R3-02 بعد التعافي وإعادة التحميل: لا يظهر الحسم الفاشل (قديمة + مفتوح)', r['text'] == 'النسخة القديمة' and r['open'] == 1 and r['resolved'] is None, r)

        # ================= R3-03 إبقاء نسخة الجهاز لا يُعلن مطابقة كاملة =================
        pg = await fresh()
        await pg.evaluate("""(async () => { Sync.switchTo('https://family', 'pub'); Store.settings.sbRole = 'aya'; Store.settings.sbSession = { sid: 'https://family', access_token: 't', refresh_token: 'r', expires_at: Date.now() + 1e6 };
            const e = Store.add({ id: 'different', type: 'note', text: 'local' }); await Store.durable();
            Store.importEvents([Object.assign(Store.clean(e), { text: 'server' })], { server: Sync.sid() }); await Store.durable();
            Object.assign(Sync.st(), { cursor: { t: '2026-11-06T20:00:00Z', id: 'zz' }, needReconcile: true }); App.view = 'settings'; UI.rerender(); })()""")
        await click(pg, 'إبقاء نسخة الجهاز'); await confirm(pg)
        await pg.wait_for_function("Store.openConflicts().length === 0 && Store.saved()")
        await pg.evaluate(f"({MOCK_SERVER})([{{ id: 'different', by: 'aya', type: 'note', child: null, payload: Object.assign(Store.clean(Store.raw.find(e => e.id === 'different')), {{ text: 'server' }}), inserted_at: '2026-11-06T01:00:00Z' }}])")
        r = await pg.evaluate(f"(async () => {{ await Sync.run(); return {{ counts: Sync.counts(), report: Sync.st().report, status: {STATUS}, local: Store.raw.find(e => e.id === 'different').text, server: window.__rows.get('different').payload.text }}; }})()")
        ok('R3-03 «إبقاء نسخة الجهاز»: التقرير لا يكتمل ويذكر الاختلاف المُبقى، والشريط لا يقول «تمت المزامنة» مجرّدة، والخادم لم يتغير',
           r['report']['complete'] is False and r['report']['kept'] == 1 and r['counts']['kept'] == 1 and r['counts']['conflicts'] == 0 and 'يختلف عن الخادم' in r['status'] and r['local'] == 'local' and r['server'] == 'server', r)
        # لا مطابقة كاملة كل دقيقة بسبب اختلاف مقصود وحده
        n0 = await pg.evaluate("window.__fetchIds")
        await pg.evaluate("Sync.st().reconciledAt = Date.now() - 2 * Sync.RECHECK_MS")
        await pg.evaluate("Sync.run()")
        n1 = await pg.evaluate("window.__fetchIds")
        ok('R3-03 الاختلاف المُبقى وحده لا يستدعي مطابقة متكررة', n1 == n0, {'before': n0, 'after': n1})
        await reopen(pg)
        await pg.evaluate("App.view = 'settings'; UI.rerender();")
        r = await pg.evaluate("({ text: document.querySelector('main').innerText, kept: Store.keptDiffs().length })")
        ok('R3-03 بعد إعادة الفتح: الاختلاف ظاهر في «التعارضات» وفي تقرير الخادم، مع زر اعتماد نسخة الخادم',
           r['kept'] == 1 and 'اختلافات مُبقاة (1)' in r['text'] and 'أُبقيت فيه نسخة الجهاز عمداً' in r['text'] and 'اعتماد نسخة الخادم' in r['text'], {'kept': r['kept']})
        await click(pg, 'اعتماد نسخة الخادم'); await confirm(pg)
        await pg.wait_for_function("Store.keptDiffs().length === 0 && Store.saved()")
        await pg.evaluate("(async () => { while (Sync.busy) await new Promise(r => setTimeout(r, 50)); })()")  # جولة البدء التلقائية بعد إعادة الفتح
        await pg.evaluate(f"(() => {{ Store.settings.sbRole = 'aya'; Store.settings.sbSession = {{ sid: 'https://family', access_token: 't', refresh_token: 'r', expires_at: Date.now() + 1e6 }}; Sync.st().needReconcile = true; ({MOCK_SERVER})([{{ id: 'different', by: 'aya', type: 'note', child: null, payload: Object.assign(Store.clean(Store.raw.find(e => e.id === 'different')), {{ text: 'server' }}), inserted_at: '2026-11-06T01:00:00Z' }}]); }})()")
        r = await pg.evaluate(f"(async () => {{ while (Sync.busy) await new Promise(r => setTimeout(r, 50)); await Sync.run(); return {{ report: Sync.st().report, status: {STATUS}, local: Store.raw.find(e => e.id === 'different').text }}; }})()")
        ok('R3-03 اعتماد نسخة الخادم لاحقاً: تطابق حقيقي و«اكتملت»', r['report']['complete'] is True and r['local'] == 'server' and r['status'].startswith('تمت المزامنة'), r)

        # ================= R3-04 فشل حفظ التعارض معلن، ولا يضيع بعد التعافي =================
        pg = await fresh()
        r = await pg.evaluate("""(async () => { const x = Store.add({ id: 'quota-base', type: 'note', text: 'local' }); await Store.durable();
            window.__put = Store.putMany.bind(Store); Store.putMany = async () => false;
            App.view = 'settings'; UI.rerender();
            Backup.merge({ events: [Object.assign(Store.clean(x), { text: 'incoming' })] });
            const ok = await Store.durable(); return { ok, saved: Store.saved(), err: Store.storageError, open: Store.openConflicts().length, status: """ + STATUS + """ }; })()""")
        ok('R3-04 فشل حفظ التعارض: حالة «غير محفوظ» ورسالة صريحة، لا نجاح وهمي', r['ok'] is False and r['saved'] is False and r['err'] and 'تعذّر' in r['status'], r)
        await pg.evaluate("(() => { Store.putMany = window.__put; Store.flush(); })()")
        await pg.wait_for_function("Store.saved()", timeout=15000)  # إعادة المحاولة التلقائية
        await reopen(pg)
        r = await pg.evaluate("({ open: Store.openConflicts().length, local: (Store.openConflicts()[0] || {}).local, other: (Store.openConflicts()[0] || {}).other, text: Store.raw[0].text })")
        ok('R3-04 بعد التعافي وإعادة الفتح: تعارض واحد كامل بنسختيه', r['open'] == 1 and r['local']['text'] == 'local' and r['other']['text'] == 'incoming' and r['text'] == 'local', r)
        # السحب: تعارض مع الخادم وفشل الحفظ = لا يتقدم المؤشر
        pg = await fresh()
        r = await pg.evaluate(f"""(async () => {{ Sync.switchTo('https://family', 'pub'); Store.settings.sbRole = 'aya'; Store.settings.sbSession = {{ sid: 'https://family', access_token: 't', refresh_token: 'r', expires_at: Date.now() + 1e6 }};
            Object.assign(Sync.st(), {{ needReconcile: false, reconciledAt: Date.now() }});
            const e = Store.add({{ id: 'pc', type: 'note', text: 'local' }}); Store.markOn(e, Sync.sid()); await Store.durable();
            ({MOCK_SERVER})([{{ id: 'pc', by: 'aya', type: 'note', child: null, payload: Object.assign(Store.clean(e), {{ text: 'server' }}), inserted_at: '2026-11-06T01:00:00Z' }}]);
            Store.putMany = async () => false; await Sync.run();
            return {{ cursor: Sync.st().cursor, err: Sync.lastError, saved: Store.saved() }}; }})()""")
        ok('R3-04 تعارض في السحب مع فشل الحفظ: المؤشر لا يتقدم والخطأ معلن', r['cursor'] is None and 'تعذّر' in (r['err'] or '') and r['saved'] is False, r)

        # ================= R3-06 Enter في نافذة الرقم =================
        pg = await fresh('asst')
        await pg.evaluate("(() => { Store.add({ type: 'fluency_page', child: 'c3', page: 600 }); startSession(PLAN.find(s => s.kind === 'young_noon')); Store.settings.active.cur = 1; UI.rerender(); })()")
        n0 = await pg.evaluate("Store.raw.length")
        await click(pg, 'تغيير الصفحة')
        inp = pg.get_by_placeholder('رقم الصفحة', exact=True)
        await inp.fill('12.5'); await inp.press('Enter')
        r = await pg.evaluate("({ modal: !!document.querySelector('.modal'), added: Store.raw.length - %d, value: document.querySelector('.modal input') && document.querySelector('.modal input').value, focus: document.activeElement === document.querySelector('.modal input'), toast: [...document.querySelectorAll('.toast')].map(t => t.textContent) })" % n0)
        ok('R3-06 Enter بقيمة 12.5: النافذة باقية بقيمتها وتركيزها، ورسالة الخطأ، ولا حدث', r['modal'] and r['added'] == 0 and r['value'] == '12.5' and r['focus'] and any('604' in t for t in r['toast']), r)
        await inp.fill('20'); await inp.press('Enter')
        r = await pg.evaluate("({ modal: !!document.querySelector('.modal'), added: Store.raw.length - %d, page: fluencyPage('c3') })" % n0)
        ok('R3-06 Enter بقيمة صحيحة: حدث واحد وتُغلق', r == {'modal': False, 'added': 1, 'page': 20}, r)
        await click(pg, 'تغيير الصفحة')
        await pg.locator('.modal').get_by_role('button', name='إلغاء', exact=True).click()
        r = await pg.evaluate("({ modal: !!document.querySelector('.modal'), added: Store.raw.length - %d, toasts: [...document.querySelectorAll('.toast')].filter(t => t.textContent.includes('604') && t.isConnected).length })" % n0)
        ok('R3-06 «إلغاء» يغلق بلا حدث', r['modal'] is False and r['added'] == 1, r)

        # ترقية قاعدة 0.13.1 (الإصدار 1، مخزن events وحده) إلى الإصدار 2: السجلات سليمة ومخزن التعارضات موجود
        ctx = await b.new_context(); pg = await ctx.new_page()
        pg.on('dialog', lambda d: asyncio.ensure_future(d.accept()))
        await pg.goto(f'http://127.0.0.1:{port}/no-such-page')
        await pg.evaluate("""() => new Promise(res => { const q = indexedDB.open('lawhat_muallima', 1); q.onupgradeneeded = () => q.result.createObjectStore('events', { keyPath: 'id' });
            q.onsuccess = () => { const tx = q.result.transaction('events', 'readwrite'); tx.objectStore('events').put({ id: 'v1-old', type: 'note', by: 'aya', ts: 1, day: '2026-11-01', text: 'من 0.13.1' }); tx.oncomplete = () => { q.result.close(); res(); }; }; })""")
        await pg.goto(f'http://127.0.0.1:{port}/index.html'); await pg.wait_for_function('Store.raw && Store.idbOk')
        r = await pg.evaluate("(async () => { App.setRole('aya'); const x = Store.raw.find(e => e.id === 'v1-old'); Store.importEvents([Object.assign(Store.clean(x), { text: 'معدّل' })], { source: 'file' }); const ok = await Store.durable(); return { text: x.text, ok, stores: [...Store.db.objectStoreNames], version: Store.db.version }; })()")
        await pg.reload(); await pg.wait_for_function('Store.raw && Store.idbOk')
        r2 = await pg.evaluate("({ n: Store.raw.length, open: Store.openConflicts().length })")
        ok('R3 ترقية القاعدة من 0.13.1: السجل القديم سليم، والتعارض يُحفظ ويبقى بعد إعادة الفتح', r['text'] == 'من 0.13.1' and r['ok'] and r['version'] == 2 and 'conflicts' in r['stores'] and r2 == {'n': 1, 'open': 1}, {**r, **r2})
        await ctx.close()

        # تبويب بإصدار أقدم يمسك القاعدة: لا يُفتح البرنامج فارغاً، بل يطلب الإغلاق ويكمل وحده
        ctx = await b.new_context()
        old = await ctx.new_page(); await old.goto(f'http://127.0.0.1:{port}/no-such-page')
        await old.evaluate("""() => new Promise(res => { const q = indexedDB.open('lawhat_muallima', 1); q.onupgradeneeded = () => q.result.createObjectStore('events', { keyPath: 'id' });
            q.onsuccess = () => { window.__db = q.result; const tx = q.result.transaction('events', 'readwrite'); tx.objectStore('events').put({ id: 'held', type: 'note', by: 'aya', ts: 1, day: '2026-11-01', text: 'في تبويب قديم' }); tx.oncomplete = () => res(); }; })""")
        new = await ctx.new_page(); new.on('dialog', lambda d: asyncio.ensure_future(d.accept()))
        await new.goto(f'http://127.0.0.1:{port}/index.html'); await new.wait_for_timeout(1500)
        r1 = await new.evaluate("({ notice: (document.getElementById('lm-block') || {}).textContent || '', loaded: !!(window.Store && Store.raw && Store.raw.length), fallback: !!(window.Store && Store.raw && !Store.idbOk) })")
        await old.close()
        await new.wait_for_function('Store.raw && Store.idbOk', timeout=10000)
        r2 = await new.evaluate("({ n: Store.raw.length, notice: !!document.getElementById('lm-block') })")
        ok('R3 ترقية مع تبويب قديم مفتوح: رسالة إغلاق لا برنامج فارغ، ثم يكتمل وحده بالسجلات', 'أغلقيها' in r1['notice'] and not r1['loaded'] and not r1['fallback'] and r2 == {'n': 1, 'notice': False}, {**r1, **r2})
        await ctx.close()

        assert not errors, errors
        await b.close()
    httpd.shutdown()
    print(f'AUDIT R3 OK ({len(results)} حالة)')

asyncio.run(main())
