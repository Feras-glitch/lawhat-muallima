"""0.16.2: عيوب المراجعة المستقلة LM016-01..07 — دورة البعيد مستقلة عن ترتيب التسجيل، الجزئي لا يؤخر القريب،
فحص ولي الأمر منفصل عن أدوات المعلمة، فحص الصغير بالسورة، الفحص الناقص بلا أخضر، حد لقطة النسخة، حجم زر ✓.
DIST=مسار يشغّل الحالات على بناء آخر (تفشل على 0.16.1)."""
import asyncio, pathlib, os, json, threading, http.server, socketserver, functools
from playwright.async_api import async_playwright
ROOT = pathlib.Path(__file__).resolve().parent.parent
DIST = os.environ.get('DIST') or str(ROOT / 'dist')
BROWSER_OPTS = {'executable_path': '/usr/bin/google-chrome', 'args': ['--no-sandbox']} if os.path.exists('/usr/bin/google-chrome') and not os.environ.get('CI') else {'args': ['--no-sandbox']}
SOFT = bool(os.environ.get('SOFT'))


class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass


socketserver.TCPServer.allow_reuse_address = True
results, fails = [], []


def ok(name, cond, data=None):
    results.append(name)
    if not cond:
        fails.append(name)
        if not SOFT:
            raise AssertionError(f'FAIL {name}: {json.dumps(data, ensure_ascii=False, default=str)[:1500]}')
    print('PASS' if cond else 'FAIL', name, json.dumps(data, ensure_ascii=False, default=str)[:200] if data is not None else '')


FAR = "seed(Array.from({length:N},(_,i)=>({type:'layer',by:'aya',day:'2026-12-01',child:'c1',page:562+i,layer:'far',color:'green'})));"


async def main():
    httpd = socketserver.TCPServer(('127.0.0.1', 0), functools.partial(Q, directory=DIST))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    port = httpd.server_address[1]
    errors = []
    async with async_playwright() as p:
        b = await p.chromium.launch(**BROWSER_OPTS)

        async def fresh(role='aya', day='2026-12-07', w=390):
            ctx = await b.new_context(viewport={'width': w, 'height': 844}); pg = await ctx.new_page(); pg.on('pageerror', lambda e: errors.append(str(e)))
            await pg.goto(f'http://127.0.0.1:{port}/index.html'); await pg.wait_for_function('Store.raw && Store.idbOk')
            await pg.evaluate("([r,day])=>{App.setRole(r);Sync.schedule=()=>{};Sync.run=async()=>{};Store.settings.timeOffset=Date.parse(day+'T00:00:00Z')-Date.now();window.seed=(list)=>Store.importEvents(list.map((e,i)=>({id:'s'+Math.random(),ts:Date.parse(e.day+'T01:00:00Z')+i,...e})));window.nextDay=()=>{Store.settings.timeOffset+=86400000;};}", [role, day])
            return pg

        # ===== LM016-01: دورة البعيد =====
        async def cycle(order_js, n=12):
            pg = await fresh('asst')
            return await pg.evaluate("()=>{" + FAR.replace('N', str(n)) + "const d1=deriveChild('c1').todayFar;const rec=p=>Store.add({type:'outcome',child:'c1',page:p,step:'far',result:'clean'});(" + order_js + ")(d1,rec);const same=deriveChild('c1').todayFar;nextDay();return {d1,same,d2:deriveChild('c1').todayFar};}")
        want = [569, 570, 571, 572, 573, 562, 563]
        asc = await cycle("(l,rec)=>l.forEach(rec)")
        desc = await cycle("(l,rec)=>l.slice().reverse().forEach(rec)")
        redo = await cycle("(l,rec)=>{l.forEach(rec);rec(l[0]);}")
        ok('دورة البعيد: الحصة التالية واحدة سواء سُجّلت تصاعدياً أو تنازلياً أو أُعيد تسجيل أول صفحة أخيراً', asc['d2'] == want and desc['d2'] == want and redo['d2'] == want, {'asc': asc['d2'], 'desc': desc['d2'], 'redo': redo['d2']})
        ok('حصة اليوم ثابتة بعد تسجيل نتائجها في اليوم نفسه', asc['same'] == asc['d1'] and redo['same'] == redo['d1'], asc['same'])
        part = await cycle("(l,rec)=>{l.slice(0,3).forEach(rec);Store.add({type:'outcome',child:'c1',page:l[3],step:'far',result:'partial'});}")
        ok('حصة لم تكتمل: ما لم يُسمَّع كاملاً (ومنه «ناقص») يتقدم حصة الغد، وما سُمّع لا يتكرر', part['d2'] == [565, 566, 567, 568, 569, 570, 571], part['d2'])
        pg = await fresh('aya')
        r = await pg.evaluate("()=>{" + FAR.replace('N', '20') + "const d1=deriveChild('c1').todayFar;d1.forEach(p=>Store.add({type:'outcome',child:'c1',page:p,step:'far',result:'clean'}));Store.add({type:'decision',child:'c1',kind:'caps',far:4});nextDay();const d2=deriveChild('c1').todayFar;d2.forEach(p=>Store.add({type:'outcome',child:'c1',page:p,step:'far',result:'clean'}));nextDay();return {d1,d2,d3:deriveChild('c1').todayFar};}")
        ok('تغيير السقف وسط الدورة: الدور يكمل من حيث وصل بلا تكرار', r['d1'] == list(range(562, 569)) and r['d2'] == [569, 570, 571, 572] and r['d3'] == [573, 574, 575, 576], r)

        # ===== LM016-03: الجزئي في القريب =====
        pg = await fresh()
        r = await pg.evaluate("()=>{seed(Array.from({length:20},(_,i)=>({type:'layer',by:'aya',day:'2026-11-01',child:'c1',page:2+i,layer:'near',color:'green'})));const before=deriveChild('c1').nearToday;seed([{type:'outcome',by:'asst',day:'2026-12-06',child:'c1',page:2,step:'near',result:'partial'}]);const mid=deriveChild('c1').nearToday;seed([{type:'outcome',by:'asst',day:'2026-12-06',child:'c1',page:3,step:'near',result:'clean'}]);return {before,mid,after:deriveChild('c1').nearToday,lb:deriveChild('c1').pages[2].lastBefore||null};}")
        ok('«لم يُقيَّم كاملاً» لا يُخرج الصفحة من قريب الغد ولا يُعدّ تسميعاً', r['mid'] == r['before'] and r['lb'] is None, r)
        ok('التسميع الكامل وحده يغيّر ترتيب التناوب', 3 not in r['after'] and 2 in r['after'] and 12 in r['after'], r['after'])

        # ===== LM016-04: فحص ولي الأمر =====
        pg = await fresh()
        r = await pg.evaluate("()=>{seed([{type:'layer',by:'aya',day:'2026-12-01',child:'c1',page:562,layer:'far',color:'green'},{type:'outcome',by:'parent',day:todayKey(),child:'c1',page:562,step:'exam',result:'clean',parent:true}]);const draw=()=>{const dom=PageListOutcome('c1',[562],'exam',{steps:[]},{id:'exam'});document.querySelector('main').replaceChildren(dom);return dom;};let dom=draw();const a={count:dom.querySelector('.muted').textContent,on:!!dom.querySelector('button.on'),rest:!!dom.querySelector('.restclean')};Store.add({type:'outcome',child:'c1',page:562,step:'exam',result:'yellow',prompts:1});dom=draw();const b2={count:dom.querySelector('.muted').textContent,on:dom.querySelector('button.on').textContent};const t=Store.events.filter(e=>e.type==='outcome'&&!e.parent).pop();Store.add({type:'undo',target:t.id,child:'c1',reason:'اختبار'});dom=draw();return {a,b:b2,c:{on:!!dom.querySelector('button.on'),parentLeft:effectiveOutcomes(e=>e.parent).length}};}")
        ok('فحص ولي الأمر وحده: لا زر مختار ولا عدّاد إنجاز في شاشة المعلمة، و«الباقي مستقل» باقٍ', r['a'] == {'count': '0 من 1', 'on': False, 'rest': True}, r['a'])
        ok('نتيجة المعلمة بعده تظهر نتيجتها هي، والتراجع عنها لا يُظهر نتيجة ولي الأمر مكانها ولا يمسّها', r['b'] == {'count': '1 من 1', 'on': 'مساعدة'} and r['c'] == {'on': False, 'parentLeft': 1}, r)

        # ===== LM016-05: فحص الصغير بالسورة =====
        pg = await fresh('aya', '2026-12-10')
        await pg.evaluate("()=>{seed([{type:'layer',by:'aya',day:'2026-12-01',child:'c3',page:604,layer:'far',color:'green'}]);Math.random=()=>0.01;startSession(PLAN.find(s=>s.kind==='thu_young'));Store.settings.active.cur=1;UI.rerender();}")
        await pg.get_by_role('button', name='قرعة سورتَين', exact=True).click()
        r = await pg.evaluate("({draw:Store.settings.active.drawS_c3||null,rows:[...document.querySelectorAll('.prow .plabel b')].map(x=>x.textContent)})")
        ok('قرعة الصغير تحفظ السورتين بهويتهما ولو كانتا في صفحة واحدة', r['draw'] is not None and len(r['draw']) == 2 and len(r['rows']) == 2 and all(x.startswith('سورة ') for x in r['rows']), r)
        await pg.locator('.prow').nth(0).get_by_role('button', name='✓', exact=True).click()
        r1 = await pg.evaluate("(()=>{const h=healthOf('c3');return {n:h.examN,need:h.examNeed,inc:h.examIncomplete,light:h.light,on:document.querySelectorAll('.prow button.on').length,count:document.querySelector('.pagelist .muted').textContent,alerts:alertsList().filter(a=>a.child==='c3'&&a.text.includes('غير مكتمل')).length,lastFar:deriveChild('c3').pages[604].lastFar||null};})()")
        ok('سورة واحدة من اثنتين: «1 من 2» غير مكتمل بلا أخضر، والثانية غير مختارة، ولا تُحسب الصفحة كلها مسمَّعة', r1 == {'n': 1, 'need': 2, 'inc': True, 'light': 'grey', 'on': 1, 'count': '1 من 2', 'alerts': 1, 'lastFar': '2026-12-01'}, r1)
        await pg.locator('.prow').nth(1).get_by_role('button', name='✓', exact=True).click()
        r2 = await pg.evaluate("(()=>{const h=healthOf('c3');return {n:h.examN,need:h.examNeed,inc:h.examIncomplete,pct:h.examGreen,light:h.light,alerts:alertsList().filter(a=>a.child==='c3'&&a.text.includes('غير مكتمل')).length,su:effectiveOutcomes(e=>e.child==='c3'&&e.step==='exam').map(e=>e.surah)};})()")
        ok('سورتان من صفحة واحدة = 2 من 2، بلا إنذار نقص كاذب', r2['n'] == 2 and r2['inc'] is False and r2['pct'] == 100 and r2['light'] == 'green' and r2['alerts'] == 0 and len(set(r2['su'])) == 2, r2)
        pg = await fresh('aya', '2026-12-10')
        r = await pg.evaluate("()=>{Store.add({type:'layer',child:'c3',page:604,layer:'far',color:'green'});Store.add({type:'layer',child:'c3',page:603,layer:'far',color:'green'});const need3=healthOf('c3').examNeed;return need3;}")
        ok('عينة الصغير المطلوبة سورتان', r == 2, r)

        # ===== LM016-06: فحص ناقص =====
        pg = await fresh()
        r = await pg.evaluate("()=>{" + FAR.replace('N', '5') + "seed(Array.from({length:5},(_,i)=>({type:'outcome',by:'aya',day:todayKey(),child:'c1',page:562+i,step:'exam',result:i?'partial':'clean'})));const h=healthOf('c1');App.view='child';App.sub={child:'c1'};return {n:h.examN,need:h.examNeed,inc:h.examIncomplete,light:h.light,alert:alertsList().filter(x=>x.child==='c1').map(x=>x.text).filter(t=>t.includes('غير مكتمل'))};}")
        ok('فحص 1 من 5 مكتمل: لا أخضر عام، ويُعلن «غير مكتمل (1 من 5)»', r['n'] == 1 and r['need'] == 5 and r['inc'] and r['light'] == 'grey' and len(r['alert']) == 1 and '1 من 5' in r['alert'][0], r)
        pg = await fresh()
        r = await pg.evaluate("()=>{" + FAR.replace('N', '5') + "seed([{type:'outcome',by:'aya',day:todayKey(),child:'c1',page:562,step:'exam',result:'red'},{type:'outcome',by:'aya',day:todayKey(),child:'c1',page:563,step:'exam',result:'partial'}]);const h=healthOf('c1');return {light:h.light,inc:h.examIncomplete};}")
        ok('الناقص لا يُحسب ضعفاً: صفحة ساقطة من فحص لم يكتمل لا تُحمِّر الإشارة العامة', r == {'light': 'grey', 'inc': True}, r)
        pg = await fresh()
        r = await pg.evaluate("()=>{" + FAR.replace('N', '5') + "seed(Array.from({length:5},(_,i)=>({type:'outcome',by:'aya',day:todayKey(),child:'c1',page:562+i,step:'exam',result:i<3?'clean':'red'})));const h=healthOf('c1');return {light:h.light,inc:h.examIncomplete,pct:h.examGreen};}")
        ok('فحص مكتمل 3 من 5: أحمر كما كان', r == {'light': 'red', 'inc': False, 'pct': 60}, r)
        pg = await fresh()
        r = await pg.evaluate("()=>{" + FAR.replace('N', '3') + "seed(Array.from({length:3},(_,i)=>({type:'outcome',by:'aya',day:todayKey(),child:'c1',page:562+i,step:'exam',result:'clean'})));const h=healthOf('c1');return {light:h.light,inc:h.examIncomplete,need:h.examNeed};}")
        ok('محفوظ أقل من 5 صفحات: العينة كل المحفوظ ويكتمل الفحص بها', r == {'light': 'green', 'inc': False, 'need': 3}, r)

        # ===== LM016-07: النسخة =====
        pg = await fresh()
        r = await pg.evaluate("async()=>{Store.add({type:'note',text:'A'});await Store.durable();let cb;AppShell.saveFile=(name,mime,text,onSaved)=>{window.backupText=text;cb=onSaved;};Backup.download();await new Promise(r=>setTimeout(r,30));Store.add({type:'note',text:'B'});await Store.durable();await new Promise(r=>setTimeout(r,30));cb();const lb=Store.settings.lastBackup;const now=Date.now;Date.now=()=>lb.at+8*86400000;const overdue=Backup.overdue();Date.now=now;return {inBackup:JSON.parse(window.backupText).events.map(x=>x.text),overdue,snapBefore:lb.snap<lb.at};}")
        ok('سجل وصل أثناء نافذة حفظ الملف يبقى معروفاً أنه خارج النسخة: التذكير يظهر بعد 8 أيام', r == {'inBackup': ['A'], 'overdue': 8, 'snapBefore': True}, r)
        pg = await fresh()
        r = await pg.evaluate("async()=>{Store.add({type:'note',text:'A'});await Store.durable();let cb;AppShell.saveFile=(n,m,t,onSaved)=>{cb=onSaved;};Backup.download();await new Promise(r=>setTimeout(r,30));cb();const lb=Store.settings.lastBackup;const now=Date.now;Date.now=()=>lb.at+8*86400000;const overdue=Backup.overdue();Date.now=now;return overdue;}")
        ok('بلا سجلات بعد اللقطة: لا تذكير كاذب', r is None, r)

        # ===== 0.16.3: LM0162-01..03 =====
        for a_, b_, gone in (('✓', 'ناقص', False), ('مساعدة', 'ناقص', False), ('ناقص', '✓', True)):
            pg = await fresh('aya', '2026-12-07')
            await pg.evaluate("()=>{seed(Array.from({length:20},(_,i)=>({type:'layer',by:'aya',child:'c1',page:2+i,day:'2026-12-01',layer:'near',color:'green'})));window.draw=()=>document.querySelector('main').replaceChildren(PageListOutcome('c1',[2],'near',{steps:[]},{id:'near'}));draw();}")
            await pg.locator('.prow').get_by_role('button', name=a_, exact=True).click(); await pg.evaluate("document.querySelectorAll('.modal-bg,.modalbg').forEach(x=>x.remove());draw()")
            await pg.locator('.prow').get_by_role('button', name=b_, exact=True).click(); await pg.evaluate('Store.durable()')
            await pg.reload(); await pg.wait_for_function('Store.raw && Store.idbOk')
            r = await pg.evaluate("()=>{App.setRole('aya');Store.settings.timeOffset=Date.parse('2026-12-08T00:00:00Z')-Date.now();const d=deriveChild('c1');return {eff:effectiveOutcomes(e=>e.child==='c1'&&e.page===2&&e.step==='near').map(e=>e.result),lb:d.pages[2].lastBefore||null,in:d.nearToday.includes(2)};}")
            ok(f'تصحيح «{a_}» إلى «{b_}» ثم إعادة الفتح: التواريخ تتبع النتيجة النافذة', len(r['eff']) == 1 and ((r['lb'] == '2026-12-07' and not r['in']) if gone else (r['lb'] is None and r['in'])), r)
        pg = await fresh('aya', '2026-12-07')
        r = await pg.evaluate("()=>{" + FAR.replace('N', '12') + "Store.add({type:'outcome',child:'c1',page:562,step:'far',result:'clean'});const fix=Store.add({type:'outcome',child:'c1',page:562,step:'far',result:'partial'});nextDay();const a=deriveChild('c1');const r1={far:a.todayFar[0],lfb:a.pages[562].lastFarBefore||null};Store.add({type:'undo',target:fix.id,child:'c1',reason:'اختبار'});const b2=deriveChild('c1');return {r1,r2:{in:b2.todayFar.slice(0,7).includes(562),lfb:b2.pages[562].lastFarBefore||null}};}")
        ok('البعيد: «مستقل» ثم «ناقص» لا يُعدّ تسميعاً، والتراجع عن التصحيح يعيد أثر المكتمل', r == {'r1': {'far': 562, 'lfb': None}, 'r2': {'in': False, 'lfb': '2026-12-07'}}, r)
        pg = await fresh('aya', '2026-12-10')
        r = await pg.evaluate("()=>{" + FAR.replace('N', '5') + "seed(Array.from({length:5},(_,i)=>({type:'outcome',by:'aya',child:'c1',page:562+i,day:'2026-12-03',step:'exam',result:'clean'})));seed(Array.from({length:5},(_,i)=>({type:'outcome',by:'aya',child:'c1',page:562+i,day:todayKey(),step:'exam',result:'partial'})));const snap=()=>{const h=healthOf('c1');return {day:h.examDay,n:h.examN,inc:h.examIncomplete,light:h.light,al:alertsList().filter(x=>x.child==='c1'&&x.text.includes('غير مكتمل')).length};};const a=snap();const one=Store.add({type:'outcome',child:'c1',page:562,step:'exam',result:'clean'});const b2=snap();Store.add({type:'undo',target:one.id,child:'c1',reason:'اختبار'});const c=snap();return {a,b:b2,c,old:effectiveOutcomes(e=>e.child==='c1'&&e.step==='exam'&&e.day==='2026-12-03').length};}")
        ok('فحص جديد كله ناقص بعد فحص قديم 5/5: «غير مكتمل» للجديد بلا أخضر مبني على القديم، والقديم باقٍ', r['a'] == {'day': '2026-12-10', 'n': 0, 'inc': True, 'light': 'grey', 'al': 1} and r['old'] == 5, r)
        ok('إكمال جزء من الفحص الجديد ثم التراجع عنه', r['b'] == {'day': '2026-12-10', 'n': 1, 'inc': True, 'light': 'grey', 'al': 1} and r['c'] == r['a'], r)
        pg = await fresh('aya', '2026-12-07')
        r = await pg.evaluate("()=>{" + FAR.replace('N', '7') + "seed(Array.from({length:7},(_,i)=>({type:'outcome',by:'asst',child:'c1',page:562+i,day:'2026-12-02',step:'far',result:'clean'})));seed([{type:'layer',by:'aya',child:'c1',page:571,day:'2026-12-04',layer:'far',color:'green'}]);Store.add({type:'layer',child:'c1',page:570,layer:'far',color:'green'});const t=deriveChild('c1').todayFar;t.forEach(p=>Store.add({type:'outcome',child:'c1',page:p,step:'far',result:'clean'}));nextDay();return {today:t,next:deriveChild('c1').todayFar};}")
        ok('صفحة دخلت البعيد بالجرد اليوم تنتظر آخر الدور، والتي دخلت قبل أيام تأتي بعد الأقدم تسميعاً', r['today'] == [562, 563, 564, 565, 566, 567, 568] and r['next'] == [571, 570, 562, 563, 564, 565, 566], r)
        pg = await fresh('aya', '2026-12-07')
        r = await pg.evaluate("()=>{seed(Array.from({length:20},(_,i)=>({type:'layer',by:'aya',child:'c1',page:582+i,day:'2026-11-01',layer:'near',color:'green'})));" + FAR.replace('N', '7') + "seed(Array.from({length:7},(_,i)=>({type:'outcome',by:'asst',child:'c1',page:562+i,day:'2026-12-02',step:'far',result:'clean'})));Store.add({type:'juz_passed',child:'c1',juz:30});const d=deriveChild('c1');return {far:d.far.length,today:d.todayFar};}")
        ok('إجازة جزء اليوم: صفحاته لا تزاحم حصة البعيد الأقدم', r['far'] > 7 and r['today'] == [562, 563, 564, 565, 566, 567, 568], r)

        # ===== حجم الأزرار =====
        for w in (360, 390):
            pg = await fresh('asst', '2026-12-07', w)
            r = await pg.evaluate("()=>{" + FAR.replace('N', '12') + "startSession(PLAN.find(s=>s.kind==='noon'&&s.child==='c1'));Store.settings.active.cur=1;UI.rerender();const bs=[...document.querySelectorAll('.prow')][2].querySelectorAll('button');const rs=[...bs].map(e=>e.getBoundingClientRect());return {ok:Math.round(rs[0].width),h:Math.round(rs[0].height),overflow:document.documentElement.scrollWidth>innerWidth,inside:rs.every(x=>x.left>=0&&x.right<=innerWidth),overlap:rs.some((x,i)=>rs.some((y,j)=>i<j&&x.left<y.right-1&&y.left<x.right-1))};}")
            ok(f'عرض {w}: زر ✓ لا يقل عن 44×40، والأزرار داخل الشاشة بلا تزاحم', r['ok'] >= 44 and r['h'] >= 40 and not r['overflow'] and r['inside'] and not r['overlap'], r)

        await b.close()
    httpd.shutdown()
    if SOFT:
        print(f'SOFT: {len(fails)} فشل من {len(results)}'); return
    assert not errors, errors
    print(f'AUDIT 0.16.2-3 OK ({len(results)} حالة)')

asyncio.run(main())
