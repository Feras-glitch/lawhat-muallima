"""اختبارات المرحلة 1 (الاستعادة والخادم) من طرف إلى طرف: أجهزة حقيقية (Playwright، IndexedDB لكل جهاز)
تتزامن عبر طبقة REST فوق PostgreSQL حقيقي بسياسات SETUP_SQL نفسها.

الحالات:
 C1 الحاسمة: نسخة خادم قديمة + سجلات أحدث على جهازين بدورين مختلفين + تراجعات لم تصل النسخة ← استعادة، مزامنة، إعادة فتح، تراجع تالٍ.
 C2 استعادة إدارية من SQL Editor: كل سجل باسم دوره؛ آمنة للتكرار؛ المزوَّر يُرفض بسببه.
 C3 الدمج مع جهاز قديم يحمل السجل المتراجَع عنه؛ والملف القديم يُعرَّف بأنه ناقص.
 C4 استعادة جهاز فارغ: السجلات + الخادم، بلا رموز ولا جلسات ولا علامات.
 C5 الانتقال من «أ» إلى «ب» ثم العودة إلى «أ»: لا فقد، لا خلط مؤشرات، لا عودة لمتراجَع عنه.
 C6 خادم استُعيد في مكانه من نسخة أقدم: يُكتشف تلقائياً ويُعاد الرفع.
 C7 تغيير الرابط لا ينقل الجلسة ولا يرفع شيئاً قبل اختيار صريح (عبر الواجهة)."""
import asyncio, json, os, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from pgkit import PG, Shim, USERS, PASSWORD
from playwright.async_api import async_playwright

BROWSER_OPTS = {'executable_path': '/usr/bin/google-chrome', 'args': ['--no-sandbox']} if os.path.exists('/usr/bin/google-chrome') and not os.environ.get('CI') else {'args': ['--no-sandbox']}
EMAIL = {r: e for e, (_, r) in USERS.items()}
results = []


def ok(name, cond, data=None):
    results.append(name)
    assert cond, f'FAIL {name}: {json.dumps(data, ensure_ascii=False, default=str)[:1500]}'
    print('PASS', name, json.dumps(data, ensure_ascii=False, default=str)[:180] if data is not None else '')


HELPERS = """(() => {
  Sync.schedule = () => {}; Sync.started = true; Sync.RECHECK_MS = 0;
  window.T = {
    digest() { const ids = a => a.map(e => e.id).sort(); const pages = {};
      for (const c of CHILD_ORDER) { const d = deriveChild(c); pages[c] = Object.keys(d.pages).sort((a, b) => a - b).map(p => [p, d.pages[p].layer, d.pages[p].color].join(':')).join(','); }
      return { raw: ids(Store.raw), live: ids(Store.events), pages }; },
    async sync() { while (Sync.busy) await new Promise(r => setTimeout(r, 50)); await Sync.run(); const st = Sync.st();
      return { err: Sync.lastError, report: st && st.report, counts: Sync.counts(), cursor: st && st.cursor }; },
  };
})()"""


async def main():
    pg = PG(); shim = Shim(pg)
    async with async_playwright() as p:
        b = await p.chromium.launch(**BROWSER_OPTS)
        errors = []

        async def device(name):
            ctx = await b.new_context(viewport={'width': 390, 'height': 844})
            pg_ = await ctx.new_page()
            pg_.on('pageerror', lambda e: errors.append(f'{name}: {e}'))
            await pg_.goto(f'http://127.0.0.1:{shim.port}/index.html')
            await pg_.wait_for_function('Store.raw && Store.idbOk')
            await pg_.evaluate(HELPERS)
            return pg_

        async def reopen(d):
            await d.reload(); await d.wait_for_function('Store.raw && Store.idbOk && document.querySelector(".login, nav.bottom")')
            await d.evaluate(HELPERS)

        async def connect(d, db):
            await d.evaluate(f"Sync.switchTo({json.dumps(shim.url(db))}, 'anon')")

        async def login(d, role):
            r = await d.evaluate(f"(async () => {{ const r = await Sync.login({json.dumps(EMAIL[role])}, {json.dumps(PASSWORD)}); App.setRole(r); return r; }})()")
            assert r == role, r

        async def add(d, ev):
            return await d.evaluate(f"Store.add({json.dumps(ev, ensure_ascii=False)}).id")

        async def sync(d):
            return await d.evaluate('T.sync()')

        async def full(d):
            await d.evaluate('Sync.st().needReconcile = true; Store.saveSettings();')
            return await sync(d)

        dig = lambda d: d.evaluate('T.digest()')
        S = {'C': 'dalal'}

        # ================= C0 ترحيل 0.11 =================
        pg.create_server('srv_m')
        mig = await device('mig')
        murl = shim.url('srv_m'); uid = USERS['aya@lm.test'][0]
        ok_ev = {'id': 'M_OK', 'type': 'note', 'by': 'aya', 'ts': 1, 'day': '2026-11-01', 'text': 'ok'}
        pg.psql('srv_m', f"insert into public.events (id, ts, day, by, type, payload) values ('M_OK', 1, '2026-11-01', 'aya', 'note', '{json.dumps(ok_ev)}'::jsonb);")
        old_settings = {'pins': {'aya': '1111', 'asst': '2222', 'parent': '3333'}, 'deviceId': 'dold', 'sbUrl': murl + '/', 'sbKey': 'anon', 'sbRole': 'aya',
                        'sbSession': {'access_token': f'srv_m|{uid}', 'refresh_token': f'srv_m|{uid}', 'expires_at': 9999999999999, 'email': 'aya@lm.test'},
                        'sbCursor': '1970-01-01T00:00:00Z', 'syncRejected': [{'id': 'M_RJ', 'type': 'note', 'by': 'aya', 'day': '2026-11-01', 'reason': 'قديم', 'at': 1, 'payload': {}, 'direction': 'push'}]}
        old_events = [dict(ok_ev, synced=True), {'id': 'M_PEND', 'type': 'note', 'by': 'aya', 'ts': 2, 'day': '2026-11-01', 'text': 'p', 'synced': False},
                      {'id': 'M_RJ', 'type': 'note', 'by': 'aya', 'ts': 3, 'day': '2026-11-01', 'text': 'r', 'synced': True, 'pushRejected': 'رفض'}]
        await mig.evaluate(f"(async () => {{ localStorage.setItem('lm_settings_v1', {json.dumps(json.dumps(old_settings, ensure_ascii=False))}); await Store.putMany({json.dumps(old_events, ensure_ascii=False)}); }})()")
        await mig.route('**/p/srv_m/**', lambda route: route.abort())  # بلا شبكة: نفحص الترحيل قبل أي تزامن
        await reopen(mig)
        r = await mig.evaluate("""(() => { const s = Store.settings; const id = serverId(s.sbUrl); const st = s.servers[id]; const f = x => Store.raw.find(e => e.id === x);
            return { schema: s.schema, legacy: 'sbCursor' in s || 'syncRejected' in s, accepted: st.accepted, need: st.needReconcile, cur: st.cursor, rej: st.rejected.map(x => x.id), sid: s.sbSession.sid === id, role: Sync.role(),
              ok: f('M_OK').sv, pend: f('M_PEND').sv || null, rj: f('M_RJ').rj, leftovers: Store.raw.filter(e => 'synced' in e || 'pushRejected' in e).length }; })()""")
        ok('C0 ترحيل 0.11: المؤشر والمرفوضات إلى حالة الخادم، والعلامات لكل خادم، والجلسة مربوطة به، ومطابقة مطلوبة',
           r['schema'] == 2 and not r['legacy'] and r['accepted'] and r['need'] and r['cur'] == {'t': '1970-01-01T00:00:00Z', 'id': ''} and r['rej'] == ['M_RJ'] and r['sid'] and r['role'] == 'aya'
           and r['ok'] == [murl.lower()] and r['pend'] is None and r['rj'] == [murl.lower()] and r['leftovers'] == 0, r)
        await reopen(mig)
        r2 = await mig.evaluate("Store.raw.filter(e => 'synced' in e).length")
        ok('C0 الترحيل ثابت على القرص ولا يتكرر', r2 == 0, r2)
        await mig.unroute('**/p/srv_m/**')
        r = await sync(mig)
        ok('C0 أول تزامن بعد الترحيل: مطابقة، ورفع المنتظر، والمرفوض القديم يبقى مذكوراً فلا يُعلن الاكتمال',
           'M_PEND' in pg.ids('srv_m') and 'M_RJ' not in pg.ids('srv_m') and r['report']['rejected'] == 1 and r['report']['complete'] is False, r['report'])

        # ================= C1 =================
        pg.create_server('srv_a')
        aya, asst, par = await device('aya'), await device('asst'), await device('parent')
        for d, r in ((aya, 'aya'), (asst, 'asst'), (par, 'parent')):
            await connect(d, 'srv_a'); await login(d, r)
        for pgn in range(562, 567):
            await add(aya, {'id': f'L{pgn}', 'type': 'layer', 'child': 'dalal', 'page': pgn, 'layer': 'far', 'color': 'green'})
        await add(aya, {'id': 'A1', 'type': 'note', 'child': 'dalal', 'text': 'آية 1'})
        await add(asst, {'id': 'O1', 'type': 'outcome', 'child': 'dalal', 'page': 562, 'step': 'far', 'result': 'yellow'})
        await add(asst, {'id': 'S1', 'type': 'note', 'child': 'dalal', 'text': 'مساعدة 1'})
        for d in (aya, asst, aya, par):
            r = await sync(d); assert r['err'] is None, r
        t0 = set(pg.ids('srv_a'))
        pg.snapshot('srv_a', 'snap_t0')  # نسخة الخادم الاحتياطية عند T0
        # بعد النسخة: سجلات وتراجعات على جهازين بدورين مختلفين
        await add(asst, {'id': 'O2', 'type': 'outcome', 'child': 'dalal', 'page': 563, 'step': 'far', 'result': 'clean'})
        await add(asst, {'id': 'U1', 'type': 'undo', 'target': 'O1', 'child': 'dalal'})
        await add(asst, {'id': 'S2', 'type': 'note', 'child': 'dalal', 'text': 'مساعدة 2'})
        await add(aya, {'id': 'A2', 'type': 'note', 'child': 'dalal', 'text': 'آية 2'})
        await add(aya, {'id': 'U2', 'type': 'undo', 'target': 'S1', 'child': 'dalal'})  # آية تتراجع عن سجل المساعدة
        await sync(asst); await sync(aya)
        await add(aya, {'id': 'U4', 'type': 'undo', 'target': 'S2', 'child': 'dalal'})  # تراجع عن سجل للمساعدة لم تحمله النسخة
        for d in (aya, asst, aya, par):
            r = await sync(d); assert r['err'] is None, r
        full_ids = set(pg.ids('srv_a'))
        ok('C1 قبل العطل: الخادم يحمل كل شيء، والتراجعات بعد النسخة', full_ids - t0 == {'O2', 'U1', 'S2', 'A2', 'U2', 'U4'}, sorted(full_ids - t0))
        ref = await dig(aya)
        ok('C1 قبل العطل: الأجهزة الثلاثة متطابقة، والمتراجَع عنه ليس حياً', ref == await dig(asst) == await dig(par) and not {'O1', 'S1', 'S2'} & set(ref['live']), ref['live'])

        # العطل: خادم جديد «ب» من نسخة T0
        pg.snapshot('snap_t0', 'srv_b')
        cur_a = await aya.evaluate('Sync.st().cursor')
        shim.log.clear()
        for d in (aya, asst, par):
            await connect(d, 'srv_b')
        r = await aya.evaluate("({ token: Sync.token(), role: Sync.role(), cur: Sync.st().cursor, curA: Store.settings.servers[serverId(%s)].cursor })" % json.dumps(shim.url('srv_a')))
        ok('C1 تغيير الرابط: لا جلسة ولا مؤشر من الخادم السابق، ومؤشر «أ» محفوظ في حالته', r['token'] is None and r['role'] is None and r['cur'] is None and r['curA'] == cur_a, r)
        r = await sync(aya)
        ok('C1 قبل الدخول: لا طلب إلى «ب» بأي توكن', 'الجلسة' in (r['err'] or '') and not [x for x in shim.log if x['db'] == 'srv_b' and x['token']], {'err': r['err'], 'log': shim.log[-3:]})
        await login(aya, 'aya')
        r = await sync(aya)
        rep = r['report']
        ok('C1 آية على «ب»: رُفع ما يمكن، وتراجعها عن سجل لم يصل ينتظر ولا يُرفض، والتقرير يسمّي ما بقي وسببه',
           r['err'] is None and rep and rep['complete'] is False and rep['ownPending'] == 1 and rep['waitingTarget'] == 1 and rep['rejected'] == 0 and rep['others'] == {'asst': 3}
           and {'A2', 'U2'} <= set(pg.ids('srv_b')) and 'U4' not in pg.ids('srv_b'), rep)
        txt = await aya.evaluate("(() => { App.view = 'settings'; UI.rerender(); return document.querySelector('main').innerText; })()")
        ok('C1 الواجهة تعرض «المطابقة لم تكتمل» وسببها', 'المطابقة لم تكتمل' in txt and 'يرفعها جهاز المساعدة' in txt and 'بانتظار وصول السجل الأصلي' in txt, txt[txt.find('المطابقة'):][:200])
        await login(asst, 'asst')
        r = await sync(asst)
        ok('C1 المساعدة على «ب»: رفعت O2 وU1 وS2؛ وتقريرها يسمّي تراجع آية الذي لم يصل', r['err'] is None and {'O2', 'U1', 'S2'} <= set(pg.ids('srv_b')) and r['report']['others'] == {'aya': 1}, r['report'])
        r = await sync(aya)
        ok('C1 آية بعد رفع المساعدة (جولة عادية): يُرفع التراجع المنتظر ويتحول التقرير إلى «اكتملت» تلقائياً', r['err'] is None and r['report']['complete'] is True and 'U4' in pg.ids('srv_b'), {**r, 'U4': 'U4' in pg.ids('srv_b'), 'S2': 'S2' in pg.ids('srv_b')})
        r = await sync(asst)
        ok('C1 المساعدة (جولة عادية): تسحب التراجع ويتحول تقريرها إلى «اكتملت» تلقائياً', r['err'] is None and r['report']['complete'] is True, r['report'])
        await login(par, 'parent'); r = await sync(par)
        ok('C1 ولي الأمر على «ب»: مكتمل', r['err'] is None and r['report']['complete'] is True, r['report'])
        ok('C1 «ب» بعد الاستعادة = «أ» قبل العطل تماماً', set(pg.ids('srv_b')) == full_ids, sorted(full_ids ^ set(pg.ids('srv_b'))))
        d3 = [await dig(d) for d in (aya, asst, par)]
        ok('C1 الأجهزة الثلاثة متطابقة مع ما قبل العطل (الخام والحي وحالة الصفحات)', d3[0] == d3[1] == d3[2] == ref, [x['live'] for x in d3])
        for d in (aya, asst, par):
            await reopen(d)
        d4 = [await dig(d) for d in (aya, asst, par)]
        ok('C1 بعد إعادة الفتح: متطابقة', d4 == d3)
        for d in (aya, asst, par):
            r = await sync(d); assert r['err'] is None, r
        ok('C1 بعد مزامنة جديدة: لا تكرار ولا تغيير', [await dig(d) for d in (aya, asst, par)] == d3)
        await add(aya, {'id': 'U3', 'type': 'undo', 'target': 'A2', 'child': 'dalal'})
        for d in (aya, asst, par):
            await sync(d)
        d5 = [await dig(d) for d in (aya, asst, par)]
        ok('C1 تراجع تالٍ بعد الاستعادة يسري على الجميع', d5[0] == d5[1] == d5[2] and 'A2' not in d5[0]['live'] and 'U3' in pg.ids('srv_b'), d5[0]['live'])

        # ================= C2 =================
        pg.snapshot('snap_t0', 'srv_b2')
        parts = await par.evaluate("ServerRestore.parts().map((ch, i, all) => ServerRestore.sql(ch, i + 1, all.length))")
        outs = [pg.psql('srv_b2', sql)[1].strip() for sql in parts]
        summary = {}
        for o in outs:
            for line in o.split('\n'):
                if '|' in line:
                    st, n = line.split('|')[:2]; summary[st] = summary.get(st, 0) + int(n)
        par_raw = set((await dig(par))['raw'])
        ok('C2 استعادة إدارية: أُدرج الناقص، والموجود تُجوهل، ولا مرفوض', summary.get('inserted') == len(par_raw - t0) and summary.get('exists') == len(t0) and 'rejected' not in summary and set(pg.ids('srv_b2')) == par_raw, summary)
        again = pg.psql('srv_b2', parts[0])[1]
        ok('C2 إعادة التشغيل آمنة: كله «موجود»', 'inserted' not in again and 'exists' in again, again.strip())
        rows = pg.psql('srv_b2', "select count(*) from public.events where payload->>'id' <> id or payload->>'by' <> by or payload ? 'sv' or payload ? 'synced';")[1].strip()
        ok('C2 الأعمدة تطابق payload، ولا حقول محلية على الخادم', rows == '0', rows)
        # سجل مزوَّر: المساعدة «تلوّن» صفحة (غير مسموح لدورها) — يُرفض بسبب سياسة الخادم نفسها
        forged = await device('forged')
        await forged.evaluate("Store.raw.push({ id: 'FORGED', type: 'color', by: 'asst', child: 'dalal', page: 570, color: 'green', ts: 5, day: '2026-11-06' })")
        sql = await forged.evaluate("ServerRestore.sql(ServerRestore.parts()[0], 1, 1)")
        out = pg.psql('srv_b2', sql)[1]
        ok('C2 المزوَّر يُرفض بسببه ولا يصل الخادم', 'rejected' in out and 'row-level security' in out and 'FORGED' not in pg.ids('srv_b2'), out.strip())
        await connect(aya, 'srv_b2'); await login(aya, 'aya'); r = await sync(aya)
        ok('C2 آية على الخادم المستعاد إدارياً: «اكتملت» دون جهاز المساعدة', r['err'] is None and r['report']['complete'] is True, r['report'])

        # ================= C2ب (LM012-02) نص يحمل فواصل SQL =================
        pg.snapshot('snap_t0', 'srv_b3')
        nasty = await device('nasty')
        texts = ['$lm_do$', '$lm_json$', '$lm_do_x$ و $lm_json_x$', '$$ end $$; drop table public.events; --', "' ; select 1; -- \\ E'\\n' ـ", 'end $lm_do$; select pg_sleep(0); do $lm_do$ begin']
        await nasty.evaluate("App.setRole('aya')")
        for i, t in enumerate(texts):
            await add(nasty, {'id': f'NASTY{i}', 'type': 'note', 'child': 'dalal', 'text': t})
        sqls = await nasty.evaluate("ServerRestore.parts().map((ch, i, all) => ServerRestore.sql(ch, i + 1, all.length))")
        rc, out, err = pg.psql('srv_b3', sqls[0], check=False)
        got = pg.psql('srv_b3', "select json_agg(json_build_array(id, payload->>'text') order by id) from public.events where id like 'NASTY%';")[1].strip()
        got = {k: v for k, v in json.loads(got or '[]')}
        ok('C2ب ملاحظات تحمل فواصل الكتلة وJSON ونصوص SQL: الملف يعمل، والنصوص تُستعاد حرفياً، والجدول سليم',
           rc == 0 and got == {f'NASTY{i}': t for i, t in enumerate(texts)} and len(pg.ids('srv_b3')) == len(t0) + len(texts), {'rc': rc, 'err': err.strip()[:300], 'got': got})

        # ================= C3 =================
        new, old, old2 = await device('new'), await device('old'), await device('old2')
        for d in (new, old, old2):
            await d.evaluate("App.setRole('aya')")
        await add(new, {'id': 'X1', 'type': 'note', 'child': 'dalal', 'text': 'x'})
        x1 = await new.evaluate("Store.clean(Store.raw.find(e => e.id === 'X1'))")
        for d in (old, old2):
            await d.evaluate(f"Store.importEvents([{json.dumps(x1, ensure_ascii=False)}])")
        await add(new, {'id': 'K1', 'type': 'note', 'child': 'dalal', 'text': 'k'})
        await add(new, {'id': 'UX1', 'type': 'undo', 'target': 'X1', 'child': 'dalal'})
        full_file = await new.evaluate("JSON.stringify(Backup.build())")
        legacy_file = await new.evaluate("JSON.stringify({ exported: new Date().toISOString(), by: 'aya', events: Store.events })")
        r = await old.evaluate(f"(() => {{ const p = Backup.parse({json.dumps(full_file)}); const n = Backup.merge(p); return {{ full: p.full, n, x1Live: Store.events.some(e => e.id === 'X1') }}; }})()")
        ok('C3 النسخة الكاملة على جهاز قديم يحمل السجل: يصل التراجع فلا يبقى حياً', r == {'full': True, 'n': 2, 'x1Live': False}, r)
        await reopen(old)
        ok('C3 بعد إعادة الفتح: يبقى متراجَعاً عنه', not await old.evaluate("Store.events.some(e => e.id === 'X1')"))
        r = await old2.evaluate(f"(() => {{ const p = Backup.parse({json.dumps(legacy_file)}); const n = Backup.merge(p); return {{ full: p.full, n, x1Live: Store.events.some(e => e.id === 'X1') }}; }})()")
        ok('C3 الملف القديم يُعرَّف بأنه ناقص (بلا تراجعات) ولا يدّعي غير ذلك', r == {'full': False, 'n': 1, 'x1Live': True}, r)
        txt = await old2.evaluate(f"(() => {{ ImportDialog(Backup.parse({json.dumps(legacy_file)})); const t = document.querySelector('.modal').innerText; document.querySelector('.modal-bg').remove(); return t; }})()")
        ok('C3 نافذة الاستيراد تحذّر من الملف القديم', 'بلا تراجعات' in txt and '1 سجلاً (0 تراجعاً)' in txt, txt[:160])

        # ================= C4 =================
        bk = await par.evaluate("JSON.stringify(Backup.build())")
        ok('C4 النسخة لا تحمل رموز الدخول ولا الجلسات ولا العلامات المحلية', all(k not in bk for k in ('"pins"', 'access_token', 'refresh_token', '"sv"', '"rj"', '"servers"', '"synced"')), [k for k in ('"pins"', 'access_token', '"sv"') if k in bk])
        fresh = await device('fresh')
        r = await fresh.evaluate(f"(() => {{ const p = Backup.parse({json.dumps(bk)}); const n = Backup.restoreDevice(p); return {{ n, url: Store.settings.sbUrl, cfg: !!Sync.cfg(), token: Sync.token(), pins: Store.settings.pins, need: Sync.st().needReconcile, onServer: Store.raw.filter(e => e.sv && e.sv.length).length }}; }})()")
        ok('C4 استعادة جهاز فارغ: السجلات والخادم، بلا جلسة، ورموز افتراضية، ومطابقة مطلوبة، ولا علامة «على الخادم»',
           r['n'] == json.loads(bk)['counts']['all'] and r['cfg'] and r['token'] is None and r['pins'] == {'aya': '1111', 'asst': '2222', 'parent': '3333'} and r['need'] is True and r['onServer'] == 0, r)
        await login(fresh, 'asst'); r = await sync(fresh)
        ok('C4 بعد الدخول: مطابقة كاملة ومكتملة', r['err'] is None and r['report']['complete'] is True, r['report'])

        # ================= C5 =================
        pg.create_server('srv_x'); pg.create_server('srv_y')
        a2, s2 = await device('aya2'), await device('asst2')
        for d, role in ((a2, 'aya'), (s2, 'asst')):
            await connect(d, 'srv_x'); await login(d, role)
        await add(a2, {'id': 'Y1', 'type': 'note', 'child': 'farah', 'text': 'y1'})
        await add(a2, {'id': 'Y2', 'type': 'note', 'child': 'farah', 'text': 'y2'})
        await add(s2, {'id': 'Z1', 'type': 'note', 'child': 'farah', 'text': 'z1'})
        for d in (a2, s2, a2):
            await sync(d)
        cur_x = await a2.evaluate('Sync.st().cursor')
        await connect(a2, 'srv_y'); await login(a2, 'aya'); r = await sync(a2)
        ok('C5 «ب»: رفعت آية سجلاتها، والتقرير يسمّي سجل المساعدة الناقص', r['report']['others'] == {'asst': 1} and {'Y1', 'Y2'} <= set(pg.ids('srv_y')), r['report'])
        await add(a2, {'id': 'EB', 'type': 'note', 'child': 'farah', 'text': 'على ب'})
        await add(a2, {'id': 'UY1', 'type': 'undo', 'target': 'Y1', 'child': 'farah'})
        await sync(a2)
        await a2.evaluate(f"(() => {{ if (!Sync.isKnown({json.dumps(shim.url('srv_x'))})) throw new Error('«أ» يجب أن يكون معروفاً'); }})()")
        await connect(a2, 'srv_x')
        r = await a2.evaluate('({ cur: Sync.st().cursor, token: Sync.token() })')
        ok('C5 العودة إلى «أ»: مؤشره كما تُرك، ولا جلسة من «ب»', r['cur'] == cur_x and r['token'] is None, {'cur': r['cur'], 'cur_x': cur_x})
        await login(a2, 'aya'); r = await sync(a2)
        ok('C5 «أ» يستلم ما سُجّل على «ب»، والتقرير مكتمل', r['err'] is None and r['report']['complete'] is True and {'EB', 'UY1'} <= set(pg.ids('srv_x')), r['report'])
        await sync(s2)
        da, ds = await dig(a2), await dig(s2)
        ok('C5 لا فقد ولا عودة لمتراجَع عنه: الجهازان متطابقان وY1 ليس حياً', da == ds and 'Y1' not in da['live'] and set(da['raw']) <= set(pg.ids('srv_x')), da['live'])

        # ================= C6 =================
        pg.snapshot('srv_x', 'snap_x')
        await add(a2, {'id': 'W1', 'type': 'note', 'child': 'farah', 'text': 'w1'})
        await sync(a2)
        ok('C6 W1 على «أ»', 'W1' in pg.ids('srv_x'))
        pg.snapshot('snap_x', 'srv_x')  # استعادة في المكان من نسخة أقدم
        ok('C6 بعد الاستعادة في المكان: W1 فُقد من الخادم', 'W1' not in pg.ids('srv_x'))
        r = await sync(a2)
        ok('C6 الفحص الرخيص يكتشف الفقد فيُعاد الرفع تلقائياً دون تدخل', 'W1' in pg.ids('srv_x') and r['err'] is None and r['report'] and r['report']['complete'] is True, r)

        # ================= C6ج (LM012-01) فقد سجل مع تساوي العدد =================
        await a2.evaluate("Sync.st().reconciledAt = Date.now(); Store.saveSettings();")
        n_srv = len(pg.ids('srv_x'))
        ghost = {'id': 'GHOST', 'type': 'note', 'by': 'asst', 'child': 'farah', 'ts': 7, 'day': '2026-11-01', 'text': 'g'}
        pg.psql('srv_x', f"delete from public.events where id = 'Y2'; insert into public.events (id, ts, day, by, child, type, payload, inserted_at) values ('GHOST', 7, '2026-11-01', 'asst', 'farah', 'note', '{json.dumps(ghost)}'::jsonb, '2000-01-01');")
        ok('C6ج تجهيز: العدد على الخادم كما هو، وY2 مفقود، وGHOST قبل مؤشر السحب', len(pg.ids('srv_x')) == n_srv and 'Y2' not in pg.ids('srv_x'))
        r = await sync(a2)
        r1 = {'Y2': 'Y2' in pg.ids('srv_x'), 'ghost': await a2.evaluate("Store.raw.some(e => e.id === 'GHOST')")}
        await a2.evaluate("Sync.st().reconciledAt = Date.now() - 7 * 3600e3; Store.saveSettings();")  # مضت نافذة المطابقة الدورية
        r = await sync(a2)
        r2 = {'Y2': 'Y2' in pg.ids('srv_x'), 'ghost': await a2.evaluate("Store.raw.some(e => e.id === 'GHOST')"), 'report': r['report']}
        ok('C6ج المطابقة الدورية بالمعرّفات تكتشف الفقد رغم تساوي العدد: يُعاد رفع Y2 (سجل آية) ويُسحب GHOST، والتقرير مكتمل',
           r2['Y2'] and r2['ghost'] and r2['report']['complete'] is True, {'قبل النافذة': r1, 'بعدها': r2})
        txt = await a2.evaluate("(() => { App.view = 'settings'; UI.rerender(); return document.querySelector('main').innerText; })()")
        ok('C6ج الإعدادات تعرض تاريخ آخر مطابقة كاملة وموعد التالية', 'آخر مطابقة كاملة' in txt and 'التالية تلقائياً' in txt, txt[txt.find('آخر مطابقة'):][:120])

        # ================= C6ب حذف السجلات المحلية =================
        n_before = len((await dig(a2))['raw'])
        await a2.evaluate("(async () => { await Store.reset(); Store.settings.active = null; Store.saveSettings(); })()")
        r = await sync(a2)
        d = await dig(a2)
        ok('C6ب بعد «حذف السجلات المحلية»: يُسحب كل شيء من جديد والمطابقة مكتملة (لا مؤشر قديم يخفي السجلات)',
           len(d['raw']) == n_before and set(d['raw']) == set(pg.ids('srv_x')) and r['report']['complete'] is True, {'n': len(d['raw']), 'before': n_before, 'report': r['report']})

        # ================= C7 =================
        shim.log.clear()
        before = await a2.evaluate('({ url: Store.settings.sbUrl, n: Store.raw.length })')
        zurl = shim.url('srv_z')
        await a2.evaluate("App.view = 'settings'; UI.rerender();")
        card = a2.locator('.card', has=a2.locator('h2', has_text='الحسابات الثلاثة'))
        await card.locator('input[placeholder="https://xxxx.supabase.co"]').fill(zurl)
        await card.get_by_role('button', name='حفظ', exact=True).click()
        title = await a2.locator('.modal h2').inner_text()
        await a2.locator('.modal').get_by_role('button', name='إلغاء').click()
        after = await a2.evaluate('({ url: Store.settings.sbUrl, n: Store.raw.length })')
        ok('C7 خادم لم يُعرف: نافذة اختيار صريح، والإلغاء لا يغيّر شيئاً', title == 'خادم جديد لهذا الجهاز' and after == before, {'title': title, 'after': after})
        await card.locator('input[placeholder="https://xxxx.supabase.co"]').fill(zurl)
        await card.get_by_role('button', name='حفظ', exact=True).click()
        await a2.locator('.modal').get_by_role('button', name='خادم منفصل').click()
        r = await a2.evaluate("({ title: document.querySelector('.modal h2').innerText, wipeDisabled: [...document.querySelectorAll('.modal button')].find(b => b.textContent.includes('حذف سجلات الجهاز')).disabled })")
        await a2.locator('.modal').get_by_role('button', name='إلغاء').click()
        after = await a2.evaluate('({ url: Store.settings.sbUrl, n: Store.raw.length })')
        ok('C7 «خادم منفصل»: لا اتصال وسجلات العائلة عليه، والحذف مقفل قبل التصدير', r == {'title': 'خادم منفصل', 'wipeDisabled': True} and after == before, r)
        await a2.evaluate(f"Store.settings.sbUrl = {json.dumps(zurl)}; Store.saveSettings();")
        r = await a2.evaluate("(async () => ({ cfg: Sync.cfg(), r: await T.sync() }))()")
        ok('C7 رابط غير مقبول وُضع يدوياً: لا مزامنة إطلاقاً', r['cfg'] is None and not [x for x in shim.log if x['db'] == 'srv_z'], {'cfg': r['cfg'], 'log': shim.log[-3:]})

        # ================= C8 (LM0121-R2-04) تعارض محتوى معرّف واحد مع الخادم =================
        pg.create_server('srv_cf')
        d1, d2, d3 = await device('cf1'), await device('cf2'), await device('cf3')
        for d in (d1, d2, d3):
            await connect(d, 'srv_cf'); await login(d, 'aya')
        await add(d1, {'id': 'X', 'type': 'note', 'child': 'dalal', 'text': 'نسخة الخادم'})
        await add(d1, {'id': 'Y', 'type': 'note', 'child': 'dalal', 'text': 'ي على الخادم'})
        await sync(d1)
        xv = await d1.evaluate("Store.clean(Store.raw.find(e => e.id === 'X'))")
        # الرفع: جهاز يحمل X بمحتوى آخر لم يُرفع بعد
        await d2.evaluate(f"Store.importEvents([Object.assign({json.dumps(xv, ensure_ascii=False)}, {{ text: 'نسخة الجهاز' }})], {{ source: 'file' }})")
        r = await sync(d2)
        srv = pg.psql('srv_cf', "select payload->>'text' from public.events where id = 'X';")[1].strip()
        st = await d2.evaluate("({ sv: (Store.raw.find(e => e.id === 'X').sv || []).length, cf: (Store.raw.find(e => e.id === 'X').cf || []).length, conflicts: Store.openConflicts().length, status: UI.statusInner().map(n => typeof n === 'string' ? n : n.textContent).join('') })")
        ok('C8 الرفع: المعرّف موجود بمحتوى آخر = تعارض معلن، لا «على الخادم»، والخادم لم يتغير، والتقرير لا يكتمل',
           srv == 'نسخة الخادم' and st['sv'] == 0 and st['cf'] == 1 and st['conflicts'] == 1 and 'تعارض' in st['status'] and r['report']['conflicts'] == 1 and r['report']['complete'] is False, {'srv': srv, **st, 'report': r['report']})
        r2 = await sync(d2)
        posts = [x for x in shim.log if x['db'] == 'srv_cf' and x['method'] == 'POST' and x['token'].startswith('srv_cf|')]
        n_before = len(posts)
        await sync(d2)
        posts2 = [x for x in shim.log if x['db'] == 'srv_cf' and x['method'] == 'POST' and x['token'].startswith('srv_cf|')]
        ok('C8 المتعارض لا يُعاد رفعه في كل جولة', len(posts2) == n_before, {'before': n_before, 'after': len(posts2)})
        await d2.evaluate("""(() => { App.view = 'settings'; UI.rerender(); [...document.querySelectorAll('button')].find(b => b.textContent === 'اعتماد نسخة الخادم').click(); [...document.querySelectorAll('.modal button')].find(b => b.textContent === 'نعم').click(); })()""")
        r = await sync(d2)
        st = await d2.evaluate("({ text: Store.raw.find(e => e.id === 'X').text, on: (Store.raw.find(e => e.id === 'X').sv || []).length, open: Store.openConflicts().length })")
        ok('C8 الحسم الصريح باعتماد نسخة الخادم: تُستبدل النسخة المحلية وتُوثَّق، ثم تكتمل المطابقة', st == {'text': 'نسخة الخادم', 'on': 1, 'open': 0} and r['report']['complete'] is True, {**st, 'report': r['report']})
        # السحب/المطابقة: Y مستورد من ملف بمحتوى آخر ولم يُتحقق منه
        yv = await d1.evaluate("Store.clean(Store.raw.find(e => e.id === 'Y'))")
        await d3.evaluate(f"Store.importEvents([Object.assign({json.dumps(yv, ensure_ascii=False)}, {{ text: 'ي مختلفة' }})], {{ source: 'file' }}); Sync.st().needReconcile = true;")
        r = await sync(d3)
        st = await d3.evaluate("({ on: (Store.raw.find(e => e.id === 'Y').sv || []).length, conflicts: Store.openConflicts().map(x => x.id) })")
        ok('C8 المطابقة لا تعلّم «على الخادم» بالمعرّف وحده: Y يُقارن عند السحب ويُعلن تعارضاً', st == {'on': 0, 'conflicts': ['Y']} and r['report']['conflicts'] == 1 and r['report']['complete'] is False, {**st, 'report': r['report']})
        # SQL الاستعادة: موجود بمحتوى مختلف = conflict، لا exists
        sql = await d3.evaluate("ServerRestore.sql(ServerRestore.parts()[0], 1, 1)")
        out = pg.psql('srv_cf', sql)[1]
        srv = pg.psql('srv_cf', "select payload->>'text' from public.events where id = 'Y';")[1].strip()
        ok('C8 الاستعادة الإدارية: المعرّف الموجود بمحتوى مختلف = conflict بسببه، والخادم لم يتغير', 'conflict|1|Y — المعرّف موجود على الخادم بمحتوى مختلف' in out and srv == 'ي على الخادم', out.strip())

        # ================= C9 سحب الدور أثناء عمل الجهاز (read_family تعيد صفراً، والرفع 403) =================
        pg.create_server('srv_rv')
        rv, demo = await device('rv'), await device('rv-old')
        asst_uid = USERS['asst@lm.test'][0]
        for d in (rv, demo):
            await connect(d, 'srv_rv'); await login(d, 'asst')
        for i in range(3):
            await add(rv, {'id': f'RV{i}', 'type': 'note', 'child': 'dalal', 'text': f'م{i}'})
        await sync(rv); await sync(demo)
        await add(rv, {'id': 'RV_PEND', 'type': 'note', 'child': 'dalal', 'text': 'بعد سحب الدور'})
        pg.psql('srv_rv', f"delete from public.profiles where user_id = '{asst_uid}';")
        # بلا فحص الدور (سلوك ما قبل الإصلاح): المطابقة ترى خادماً فارغاً فتُعيد الرفع، و403 يُعلَّم مرفوضاً — هذا ما يمنعه الإصلاح
        r = await demo.evaluate("(async () => { Sync.serverRole = async () => Store.settings.sbRole; Sync.st().needReconcile = true; await T.sync(); return Store.raw.filter(e => (e.rj || []).length).length; })()")
        ok('C9 (إثبات العيب) بلا فحص الدور: سجلات حساب سُحب دوره تُعلَّم مرفوضة', r == 3, r)
        r = await rv.evaluate("(async () => { Sync.st().needReconcile = true; Store.saveSettings(); const x = await T.sync(); return { err: x.err, session: Store.settings.sbSession, role: Sync.role(), rj: Store.raw.filter(e => (e.rj || []).length).length, rejected: Sync.st().rejected.length, on: Store.raw.filter(e => (e.sv || []).length).map(e => e.id).sort() }; })()")
        ok('C9 الدور سُحب: يخرج الجهاز من الحساب برسالة صريحة، ولا يُعلَّم شيء مرفوضاً، وعلامات «على الخادم» باقية',
           r['session'] is None and r['role'] is None and 'دور' in (r['err'] or '') and r['rj'] == 0 and r['rejected'] == 0 and r['on'] == ['RV0', 'RV1', 'RV2'], r)
        # سباق: الدور سُحب بعد بدء الجولة (الرفع يلقى 403): لا رفض قبل التحقق من الدور
        pg.psql('srv_rv', f"insert into public.profiles values ('{asst_uid}', 'asst');")
        await login(rv, 'asst')
        pg.psql('srv_rv', f"delete from public.profiles where user_id = '{asst_uid}';")
        r = await rv.evaluate("(async () => { let err = null; try { await Sync.push(Sync.cfg()); } catch (e) { err = e.message; } return { err, session: Store.settings.sbSession, rj: Store.raw.filter(e => (e.rj || []).length).length }; })()")
        ok('C9 سباق: 403 أثناء الرفع والدور سُحب = خروج من الحساب، لا مرفوضات', r['session'] is None and r['rj'] == 0 and 'دور' in (r['err'] or ''), r)
        pg.psql('srv_rv', f"insert into public.profiles values ('{asst_uid}', 'asst');")
        await login(rv, 'asst')
        r = await full(rv)
        ok('C9 بعد إعادة الدور والدخول: يُرفع المنتظر، وتكتمل المطابقة بلا مرفوضات', 'RV_PEND' in pg.ids('srv_rv') and r['report']['complete'] is True and r['report']['rejected'] == 0 and r['err'] is None, {'report': r['report'], 'err': r['err']})

        # ================= C10 (LM0131-R3-03) فرعا الحسم مع خادم حقيقي =================
        pg.create_server('srv_kp')
        k1, k2 = await device('kp1'), await device('kp2')
        for d in (k1, k2):
            await connect(d, 'srv_kp'); await login(d, 'aya')
        await add(k1, {'id': 'K', 'type': 'note', 'child': 'dalal', 'text': 'نسخة الخادم'})
        await sync(k1)
        kv = await k1.evaluate("Store.clean(Store.raw.find(e => e.id === 'K'))")
        await k2.evaluate(f"Store.importEvents([Object.assign({json.dumps(kv, ensure_ascii=False)}, {{ text: 'نسخة الجهاز' }})], {{ source: 'file' }})")
        await sync(k2)
        r = await k2.evaluate("(async () => { const ok = await Store.resolveConflict(Store.openConflicts('server:' + Sync.sid())[0], 'local', 'aya'); return ok; })()")
        r = await full(k2)
        srv = pg.psql('srv_kp', "select payload->>'text' from public.events where id = 'K';")[1].strip()
        st = await k2.evaluate("({ text: Store.raw.find(e => e.id === 'K').text, status: UI.statusInner().map(n => typeof n === 'string' ? n : n.textContent).join('') })")
        ok('C10 «إبقاء نسخة الجهاز»: لا «اكتملت»، والاختلاف المُبقى مذكور، والخادم لم يتغير',
           r['report']['complete'] is False and r['report']['kept'] == 1 and r['report']['conflicts'] == 0 and srv == 'نسخة الخادم' and st['text'] == 'نسخة الجهاز' and 'يختلف عن الخادم' in st['status'], {'report': r['report'], 'srv': srv, **st})
        # (LM0132-R4-03) نسخة كاملة ← حذف ← استعادة جهاز ← دخول ومطابقة: الاختلاف المُبقى يعود كما كان، لا تعارض جديد ولا «اكتملت»
        bk = await k2.evaluate("JSON.stringify(Backup.build())")
        await k2.evaluate(f"(async () => {{ await Store.reset(); Backup.restoreDevice(Backup.parse({json.dumps(bk)})); await Store.durable(); }})()")
        await login(k2, 'aya')
        r = await full(k2)
        st = await k2.evaluate("({ text: Store.raw.find(e => e.id === 'K').text, open: Store.openConflicts().length, kept: Store.keptDiffs().length })")
        ok('C10 بعد نسخة ← حذف ← استعادة ← مطابقة: الاختلاف المُبقى باقٍ بقراره، لا تعارض مفتوح جديد، ولا «اكتملت»',
           st == {'text': 'نسخة الجهاز', 'open': 0, 'kept': 1} and r['report']['complete'] is False and r['report']['kept'] == 1, {'report': r['report'], **st})
        await k2.evaluate("(async () => { await Store.resolveConflict(Store.keptDiffs()[0], 'other', 'aya'); })()")
        r = await full(k2)
        st = await k2.evaluate("({ text: Store.raw.find(e => e.id === 'K').text, kept: Store.keptDiffs().length })")
        ok('C10 اعتماد نسخة الخادم بعدها: تطابق حقيقي و«اكتملت»', r['report']['complete'] is True and st == {'text': 'نسخة الخادم', 'kept': 0}, {'report': r['report'], **st})

        assert not errors, errors
        await b.close()
    shim.close(); pg.close()
    print(f'RESTORE E2E OK ({len(results)} حالة)')

asyncio.run(main())
