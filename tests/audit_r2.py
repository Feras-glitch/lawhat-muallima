"""اختبارات انحدار لمراجعة 0.12.1 المستقلة (LM0121-R2-01..14): كل حالة مأخوذة من برنامج إعادة الإنتاج في التقرير،
ومعيار قبولها كما كُتب فيه. IndexedDB حقيقي عبر HTTP. حالات الخادم (القراءة، تعارض الرفع والسحب وSQL الاستعادة)
في tests/sql_policy_test.sql وtests/restore_e2e.py (C8)."""
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
    assert cond, f'FAIL {name}: {json.dumps(data, ensure_ascii=False, default=str)[:1200]}'
    print('PASS', name, json.dumps(data, ensure_ascii=False, default=str)[:170] if data is not None else '')


STATUS = "UI.statusInner().map(n => typeof n === 'string' ? n : n.textContent).join('')"


async def main():
    httpd = socketserver.TCPServer(('127.0.0.1', 0), functools.partial(Q, directory=str(ROOT / 'dist')))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    port = httpd.server_address[1]
    errors = []
    async with async_playwright() as p:
        b = await p.chromium.launch(**BROWSER_OPTS)

        async def fresh(role='aya', t=None):
            ctx = await b.new_context(viewport={'width': 390, 'height': 844}, locale='ar', timezone_id='Africa/Cairo')
            pg = await ctx.new_page()
            pg.on('pageerror', lambda e: errors.append(str(e)))
            pg.on('dialog', lambda d: asyncio.ensure_future(d.accept()))
            await pg.goto(f'http://127.0.0.1:{port}/index.html'); await pg.wait_for_function('Store.raw && Store.idbOk')
            await pg.evaluate(f"(role) => {{ Sync.schedule = () => {{}}; Store.settings.timeOffset = Date.UTC(2026,10,7,4,50) - Date.now(); App.setRole(role); }}", role)
            return pg

        # R2-03 الحفظ الجاري لا يُعرض محفوظاً، والمغادرة محمية، ولا فقد بعد إعادة الفتح
        pg = await fresh()
        r = await pg.evaluate("""(async () => { const orig = Store.putMany.bind(Store); let resolve; Store.putMany = () => new Promise(r => resolve = r);
            Store.add({ id: 'inflight', type: 'note', text: 'x' }); const pr = Store.flush(); await Promise.resolve();
            const before = { saved: Store.saved(), pending: Store.pendingCount(), status: """ + STATUS + """ };
            const e = new Event('beforeunload', { cancelable: true }); window.dispatchEvent(e); before.unloadPrevented = e.defaultPrevented;
            resolve(true); await pr; Store.putMany = orig; const after = { saved: Store.saved(), status: """ + STATUS + """ }; return { before, after }; })()""")
        ok('R2-03 أثناء كتابة جارية: غير محفوظ، «جارٍ الحفظ»، والمغادرة محمية؛ وبعدها «حُفظ»',
           r['before']['saved'] is False and r['before']['pending'] == 1 and 'جارٍ الحفظ' in r['before']['status'] and r['before']['unloadPrevented'] is True
           and r['after']['saved'] is True and 'جارٍ الحفظ' not in r['after']['status'], r)
        pg = await fresh()
        await pg.evaluate("(() => { Store.putMany = () => new Promise(() => {}); Store.add({ id: 'pending-loss', type: 'note', text: 'x' }); Store.flush(); })()")
        await pg.reload(); await pg.wait_for_function('Store.raw && Store.idbOk')
        r = await pg.evaluate("({ exists: Store.raw.some(e => e.id === 'pending-loss'), ls: localStorage.getItem('lm_events_v1') })")
        ok('R2-03 كتابة معلّقة ثم إعادة تحميل: السجل موجود (نسخة الطوارئ عند المغادرة) ونسخة الطوارئ مُحيت بعد دمجها', r['exists'] is True and r['ls'] is None, r)

        # R2-02 ردّ سحب قديم وصل أثناء الحذف لا يُستورد، ولا يُرفع شيء منه إلى خادم منفصل
        pg = await fresh()
        r = await pg.evaluate("""(async () => { const A = 'https://family-a', B = 'https://separate-b';
            Sync.switchTo(A, 'keyA'); Store.settings.sbRole = 'aya'; Store.settings.sbSession = { sid: A, access_token: 'A', refresh_token: 'r', expires_at: Date.now() + 1e6 };
            const cfg = Sync.cfg(); let giveRows; window.fetch = () => new Promise(r => giveRows = r);
            const pull = Sync.pull(cfg).catch(e => e.message);
            const clear = Store.clearDb.bind(Store); let finishClear; Store.clearDb = async () => { await clear(); await new Promise(r => finishClear = r); return true; };
            const reset = Store.reset(); while (!finishClear) await new Promise(r => setTimeout(r, 1));
            giveRows({ ok: true, json: async () => [{ id: 'private-family-a', by: 'aya', type: 'note', payload: { id: 'private-family-a', by: 'aya', type: 'note', ts: 1, day: todayKey(), text: 'بيانات أ' }, inserted_at: '2026-11-06T01:00:00Z' }] });
            const pullErr = await pull; const during = Store.raw.map(e => e.id); finishClear(); await reset;
            Sync.switchTo(B, 'keyB'); Store.settings.sbRole = 'aya'; Store.settings.sbSession = { sid: B, access_token: 'B', refresh_token: 'r', expires_at: Date.now() + 1e6 };
            const ready = Sync.counts(B).ownPending; const sent = []; window.fetch = async (u, o) => { if (o && o.body) sent.push(...JSON.parse(o.body).map(x => x.id)); return { ok: true, json: async () => [] }; };
            await Sync.push(Sync.cfg()); return { pullErr, during, after: Store.raw.map(e => e.id), ready, sent }; })()""")
        ok('R2-02 الحذف يُبطل السحب الجاري: لا استيراد، ولا شيء منتظر أو مرسل إلى «ب»',
           r['during'] == [] and r['after'] == [] and r['ready'] == 0 and r['sent'] == [] and 'حُذفت سجلات الجهاز' in (r['pullErr'] or ''), r)

        # R2-04 (محلياً) المعرّف نفسه بمحتوى مختلف: تعارض معلن لا «تكرار سليم»؛ والمحتوى نفسه يُدمج
        pg = await fresh()
        r = await pg.evaluate("""(async () => { Store.add({ id: 'same', type: 'note', child: 'c1', text: 'local' }); await Store.durable();
            const remote = { id: 'same', type: 'decision', child: 'c1', kind: 'pause', by: 'aya', ts: Date.now(), day: todayKey() };
            const n = Store.importEvents([remote], { server: 'https://family-b' }); await Store.durable();
            const loc = Store.raw.find(e => e.id === 'same');
            const sameCopy = Object.assign(Store.clean(loc), { child: 'c1', extraNull: null });
            const n2 = Store.importEvents([sameCopy], { server: 'https://family-c' }); await Store.durable();
            return { n, conflicts: Store.openConflicts().map(x => [x.id, x.source, x.other.type]), localType: loc.type, onB: (loc.sv || []).includes('https://family-b'), cf: loc.cf, paused: deriveChild('c1').paused || false,
              n2, onC: (loc.sv || []).includes('https://family-c'), status: """ + STATUS + """ }; })()""")
        ok('R2-04 تعارض المحتوى يُعلن ولا يُعلَّم «على الخادم»، والنسخة المحلية لا تُستبدل صامتاً؛ والمحتوى المطابق (مع null) يُدمج ويُعلَّم',
           r['n'] == 0 and r['conflicts'] == [['same', 'server:https://family-b', 'decision']] and r['localType'] == 'note' and not r['onB'] and r['cf'] == ['https://family-b']
           and not r['paused'] and r['n2'] == 0 and r['onC'] and 'تعارض' in r['status'], r)
        r = await pg.evaluate("""(() => { const x = Store.openConflicts()[0]; App.view = 'settings'; UI.rerender(); const txt = document.querySelector('main').innerText;
            return { card: txt.includes('التعارضات (1)'), both: txt.includes('هذا الجهاز الآن: note') && txt.includes('الخادم: decision') }; })()""")
        ok('R2-04 بطاقة «التعارضات» تعرض النسختين للحسم الصريح', r == {'card': True, 'both': True}, r)
        r = await pg.evaluate("""(() => { const p = Backup.parse(JSON.stringify({ format: 'lawhat-muallima-backup', events: [{ id: 'same', type: 'note', child: 'c1', by: 'aya', ts: 1, day: '2026-11-01', text: 'نص آخر' }], settings: {} }));
            ImportDialog(p); const t = document.querySelector('.modal').innerText; document.querySelector('.modal-bg').remove();
            const n = Backup.merge(p); return { warn: t.includes('بمعرّف موجود هنا ومحتوى مختلف'), n, conflicts: Backup.lastConflicts }; })()""")
        ok('R2-04 ملف متعارض: تحذير قبل الدمج، ولا يُغيَّر شيء، ويُسجَّل التعارض', r == {'warn': True, 'n': 0, 'conflicts': 1}, r)

        # R2-05 نتيجة جزئية وحدها: لا أخضر ولا سقوط
        pg = await fresh()
        r = await pg.evaluate("""(() => { Store.add({ type: 'outcome', child: 'c1', page: 570, step: 'gate', result: 'partial' }); const h = healthOf('c1');
            App.setRole('parent'); App.view = 'reports'; UI.rerender(); const row = [...document.querySelectorAll('tr')].find(x => x.innerText.includes('البوابة'));
            return { light: h.light, evaluated: h.evaluated, gateFails: h.gateFails, partialN: h.partialN, text: lightText(h), row: row && row.innerText }; })()""")
        ok('R2-05 الجزئي وحده: غير مُقيَّم (لا أخضر)، والتقرير لا يعدّه سقوطاً ويذكره مستقلاً',
           r['light'] == 'grey' and r['evaluated'] is False and r['gateFails'] == 0 and r['partialN'] == 1 and 'لم يُقيَّم كاملاً' in r['text'] and 'سقوط 0' in r['row'] and 'لم يُقيَّم كاملاً' in r['row'], r)

        # R2-06 فحص ولي الأمر لا يدخل أرقام فحص المعلمة
        pg = await fresh()
        r = await pg.evaluate("""(() => { Store.add({ type: 'outcome', child: 'c1', page: 570, step: 'exam', result: 'clean' }); App.setRole('parent');
            Store.add({ type: 'outcome', child: 'c1', page: 571, step: 'exam', result: 'red', parent: true }); App.view = 'reports'; UI.rerender();
            const rows = [...document.querySelectorAll('tr')].map(x => x.innerText); const sum = weeklySummaryText();
            return { examN: healthOf('c1').examN, teacher: rows.find(x => x.includes('فحص الخميس')), home: rows.find(x => x.includes('فحص المنزل')), sum }; })()""")
        ok('R2-06 فحص الخميس للمعلمة 1/1 بنسبة 100%، وفحص المنزل صف مستقل، والخلاصة تفصلهما',
           r['examN'] == 1 and r['teacher'].split('\t')[-1].startswith('1 ') and '100%' in r['teacher'] and 'سقوط 1' in r['home'] and 'فحص المنزل: 0/1' in r['sum'], r)

        # R2-07 الاستكمال الكامل يُسقط تنبيه «بقي جزء» ويعلّم الباقي «استُدرك»
        pg = await fresh('asst')
        r = await pg.evaluate("""(async () => { const s = PLAN.find(x => x.kind === 'noon' && x.child === 'c1'); startSession(s); const a = Store.settings.active; a.steps = ['second'];
            await commitEnd(s, a, 'partial', ['far', 'cards'], null, ''); const before = alertsList().filter(x => x.text.includes('بقي جزء')).length;
            const prev = sessionStatus(s, todayKey()); startSession(s, prev); const a2 = Store.settings.active; a2.steps = SESSION_KINDS[s.kind].steps.map(x => x.id);
            await commitEnd(s, a2, 'complete', [], null, '');
            const h = handoffs()[0]; const rem = h.items.filter(x => x.k === 'remaining');
            return { status: sessionStatus(s, todayKey()).status, before, after: alertsList().filter(x => x.text.includes('بقي جزء')).length, rem: rem.map(x => !!x.resolved), last: lastNote('c1') }; })()""")
        ok('R2-07 بعد الاستكمال: لا تنبيه نقص نشط، والباقي القديم «استُدرك» ويبقى في التاريخ',
           r['status'] == 'complete' and r['before'] == 1 and r['after'] == 0 and r['rem'] == [True] and not (r['last'] and 'بقي:' in r['last']['text']), r)

        # R2-08 طلب الاعتماد في النيابة يدخل البطاقة مرة واحدة
        pg = await fresh('asst')
        r = await pg.evaluate("""(async () => { const s = PLAN.find(x => x.kind === 'gate_new' && x.child === 'c1'); startSession(s, null, { orig: 'aya', reason: 'غياب' });
            const a = Store.settings.active; Store.add({ type: 'note', child: 'c1', text: 'طلب اعتماد: حفظ الصفحة — حفظت نصفها' });
            await commitEnd(s, a, 'partial', ['memorize'], null, '');
            const prev = sessionStatus(s, todayKey()); startSession(s, prev, { orig: 'aya', reason: 'غياب' }); const a2 = Store.settings.active; a2.steps = SESSION_KINDS[s.kind].steps.map(x => x.id);
            await commitEnd(s, a2, 'complete', [], null, '');
            const h = handoffs()[0]; App.setRole('aya'); const card = handoffCard(h, true).innerText;
            return { req: h.items.filter(x => x.k === 'request').map(x => x.text), card: card.includes('طلب اعتماد من آية: حفظ الصفحة — حفظت نصفها'), state: h.state }; })()""")
        ok('R2-08 الطلب في بطاقة آية مرة واحدة رغم جولتين، ويبقى حتى قرارها', r['req'] == ['حفظ الصفحة — حفظت نصفها'] and r['card'] and r['state'] == 'new', r)

        # R2-09 زر الخطأ في بوابة الأمس يفتح على صفحة الأمس ومقطعه؛ وفي الحفظ على الجديد
        pg = await fresh()
        await pg.evaluate("(() => { Store.add({ type: 'new_page', child: 'c3', page: 604, linesFrom: 1, linesTo: 15, day: '2026-11-06' }); startSession(PLAN.find(s => s.kind === 'young_new')); })()")
        await pg.get_by_role('button', name='تسجيل خطأ · الطفل الثالث', exact=True).click()
        r1 = await pg.evaluate("({ page: document.querySelector('.modal input[type=number]').value, seg: (document.querySelector('.modal').innerText.match(/الأسطر \\d+–\\d+/) || [''])[0] })")
        await pg.evaluate("document.querySelector('.modal-bg').remove(); const a = Store.settings.active; a.cur = 1; saveActive(); UI.rerender(true);")
        await pg.get_by_role('button', name='تسجيل خطأ · الطفل الثالث', exact=True).click()
        r2 = await pg.evaluate("({ page: document.querySelector('.modal input[type=number]').value, next: deriveChild('c3').nextNew })")
        ok('R2-09 البوابة: ص604 ومقطع الأمس؛ خطوة الحفظ: الجديد ص603', r1 == {'page': '604', 'seg': 'الأسطر 1–15'} and r2 == {'page': '603', 'next': 603}, {'gate': r1, 'memorize': r2})

        # R2-10 بطاقات الطفل الثالث: ثلاث سور في ص604 مستقلة
        pg = await fresh()
        r = await pg.evaluate("""(async () => { for (const [n, t] of [[112, 'الإخلاص'], [113, 'الفلق'], [114, 'الناس']]) { cardModal('c3', 604, n); document.querySelector('.modal textarea').value = 'قصة ' + t; [...document.querySelectorAll('.modal button')].find(b => b.textContent === 'حفظ').click(); }
            cardModal('c3', 604); const picker = [...document.querySelectorAll('.modal .btns button')].map(b => b.textContent).filter(t => ['الإخلاص', 'الفلق', 'الناس'].includes(t));
            [...document.querySelectorAll('.modal .btns button')].find(b => b.textContent === 'الفلق').click(); const falaq = document.querySelector('.modal textarea').value; document.querySelector('.modal-bg').remove();
            Store.add({ type: 'layer', child: 'c3', page: 604, layer: 'far', color: 'green' });
            const cards = cardsFor('c3'); const box = CardsBox('c3').innerText;
            return { keys: Object.keys(cards).sort(), picker, falaq, box: ['الإخلاص', 'الفلق', 'الناس'].map(t => box.includes('سورة ' + t)) }; })()""")
        ok('R2-10 ص604: ثلاث بطاقات مستقلة، واختيار السورة يعرض بطاقتها، وكلها تظهر في المراجعة',
           r['keys'] == ['s112', 's113', 's114'] and r['picker'] == ['الإخلاص', 'الفلق', 'الناس'] and r['falaq'] == 'قصة الفلق' and r['box'] == [True, True, True], r)

        # R2-11 الجرد لآية فقط؛ ولي الأمر يرى من ينفذه
        pg = await fresh('parent')
        r = await pg.evaluate("(() => { App.view = 'settings'; UI.rerender(); const t = document.querySelector('main').innerText; return { btn: [...document.querySelectorAll('button')].some(b => b.textContent.includes('عمّ وتبارك')), note: t.includes('تنفذه آية') }; })()")
        ok('R2-11 ولي الأمر: لا زر جرد، وشرح أن آية تنفذه', r == {'btn': False, 'note': True}, r)
        pg = await fresh('aya')
        await pg.evaluate("App.view = 'settings'; UI.rerender();")
        await pg.get_by_role('button', name='الطفل الأول والطفل الثاني: عمّ وتبارك', exact=True).click()
        await pg.locator('.modal').get_by_role('button', name='نعم', exact=True).click()
        n = await pg.evaluate("Store.raw.filter(e => e.type === 'layer').length")
        ok('R2-11 آية تنفذ الجرد', n == 86, n)

        # R2-12 سجل قديم وصل بعد آخر نسخة يجعلها غير محدثة
        pg = await fresh()
        r = await pg.evaluate("""(() => { Store.settings.lastBackup = { at: Date.now() - 8 * 86400000, count: 0 };
            Store.importEvents([{ id: 'arrived-after-backup', type: 'note', by: 'aya', ts: Date.now() - 10 * 86400000, day: '2026-10-25', text: 'وصل متأخرا' }]);
            const o1 = Backup.overdue(); const e = Store.raw[0]; Store.markOn(e, 'https://x'); Store.settings.lastBackup = { at: Date.now() - 8 * 86400000 + 1000 * 3600 * 24 * 8 + 5000, count: 1 };
            return { o1, o2: Backup.overdue() }; })()""")
        ok('R2-12 التذكير يظهر لسجل قديم وصل بعد النسخة، ولا يُطلب لتغيير علامة رفع', r['o1'] == 8 and r['o2'] is None, r)

        # R2-13 مسودة حقل لا تمحوها المزامنة
        pg = await fresh()
        r = await pg.evaluate("""(async () => { Sync.switchTo('https://original', 'key'); Store.settings.sbRole = 'aya'; Store.settings.sbSession = { sid: 'https://original', access_token: 'x', refresh_token: 'x', expires_at: Date.now() + 1e6 };
            Object.assign(Sync.st(), { needReconcile: false, reconciledAt: Date.now() }); App.view = 'settings'; UI.rerender();
            const inp = document.querySelector('input[placeholder="https://xxxx.supabase.co"]'); inp.focus(); inp.value = 'https://new-typed-url'; inp.setSelectionRange(5, 5);
            window.fetch = async (u, o) => String(u).includes('select=id&limit=1') ? { ok: true, headers: { get: () => '0-0/1' }, json: async () => [] } : { ok: true, json: async () => [{ id: 'newly-arrived', by: 'aya', type: 'note', payload: { ts: 1, day: todayKey(), text: 'remote' }, inserted_at: '2026-11-07T00:00:00Z' }] };
            Sync.serverRole = async () => Store.settings.sbRole; await Sync.run(); const n = document.querySelector('input[placeholder="https://xxxx.supabase.co"]');
            return { arrived: Store.raw.some(e => e.id === 'newly-arrived'), after: n.value, focus: document.activeElement === n, caret: n.selectionStart }; })()""")
        ok('R2-13 بعد مزامنة جلبت سجلاً: النص المكتوب والتركيز والمؤشر باقية', r == {'arrived': True, 'after': 'https://new-typed-url', 'focus': True, 'caret': 5}, r)

        # R2-14 الطلاقة في آخر صفحة
        pg = await fresh('asst')
        await pg.evaluate("(() => { Store.add({ type: 'fluency_page', child: 'c3', page: 604 }); startSession(PLAN.find(s => s.kind === 'young_noon')); Store.settings.active.cur = 1; UI.rerender(); })()")
        await pg.get_by_placeholder('ثوانٍ', exact=True).fill('120')
        await pg.get_by_role('button', name='تسجيل الزمن', exact=True).click()
        r = await pg.evaluate("({ page: fluencyPage('c3'), times: Store.events.filter(x => x.type === 'fluency_time').length, done: Store.settings.active.steps.includes('read'), uiErrors: UI.errors.slice() })")
        ok('R2-14 ص604: يُسجَّل الزمن مرة، ولا 605، والخطوة مكتملة، بلا خطأ', r == {'page': 604, 'times': 1, 'done': True, 'uiErrors': []}, r)

        # تسجيل الدخول بحساب بلا دور لا يحفظ جلسة على الجهاز
        pg = await fresh()
        r = await pg.evaluate("""(async () => { Sync.switchTo('https://srv', 'k'); window.fetch = async (u) => String(u).includes('/auth/') ? { ok: true, json: async () => ({ access_token: 't', refresh_token: 'r', expires_in: 3600, user: { id: 'u4', email: 'x@y' } }) } : { ok: true, json: async () => [] };
            const role = await Sync.login('x@y', 'p'); return { role, session: Store.settings.sbSession }; })()""")
        ok('R2-01 (الجهاز) حساب بلا دور: لا دخول ولا جلسة محفوظة', r == {'role': None, 'session': None}, r)

        # مسح ذاتي: أرقام غير صحيحة تُرفض برسالة مفهومة، ولا يُحفظ شيء، ونافذة الإدخال تبقى مفتوحة
        pg = await fresh('asst')
        await pg.evaluate("(() => { Store.add({ type: 'fluency_page', child: 'c3', page: 600 }); startSession(PLAN.find(s => s.kind === 'young_noon')); Store.settings.active.cur = 1; UI.rerender(); })()")
        n0 = await pg.evaluate("Store.raw.length")
        await pg.get_by_placeholder('ثوانٍ', exact=True).fill('-5')
        await pg.get_by_role('button', name='تسجيل الزمن', exact=True).click()
        t1 = await pg.evaluate("document.querySelector('.toast') && document.querySelector('.toast').textContent")
        await pg.get_by_role('button', name='تغيير الصفحة', exact=True).click()
        await pg.get_by_placeholder('رقم الصفحة', exact=True).fill('12.5')
        await pg.locator('.modal button.primary').click()
        r = await pg.evaluate("({ added: Store.raw.length - %d, modal: !!document.querySelector('.modal'), toast: [...document.querySelectorAll('.toast')].map(x => x.textContent).join(' | '), uiErrors: UI.errors.slice() })" % n0)
        ok('مسح ذاتي: زمن سالب وصفحة كسرية يُرفضان بوضوح، والنافذة باقية، ولا سجل', r['added'] == 0 and r['modal'] and 'بالثواني' in (t1 or '') and '604' in (r['toast'] or '') and r['uiErrors'] == [], {**r, 't1': t1})

        assert not errors, errors
        await b.close()
    httpd.shutdown()
    print(f'AUDIT R2 OK ({len(results)} حالة)')

asyncio.run(main())
