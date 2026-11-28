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
        r = await pg.evaluate("()=>{" + FAR.replace('N', '5') + "seed(Array.from({length:5},(_,i)=>({type:'outcome',by:'aya',child:'c1',page:562+i,day:'2026-12-03',step:'exam',result:'clean'})));seed(Array.from({length:5},(_,i)=>({type:'outcome',by:'aya',child:'c1',page:562+i,day:todayKey(),step:'exam',result:'partial'})));const snap=()=>{const h=healthOf('c1');return {day:h.examDay,n:h.examN,inc:h.examIncomplete,light:h.light,al:alertsList().filter(x=>x.child==='c1'&&x.text.includes('غير مكتمل')).length};};const a=snap();Store.settings.timeOffset+=7200000;const one=Store.add({type:'outcome',child:'c1',page:562,step:'exam',result:'clean'});const b2=snap();Store.add({type:'undo',target:one.id,child:'c1',reason:'اختبار'});const c=snap();return {a,b:b2,c,old:effectiveOutcomes(e=>e.child==='c1'&&e.step==='exam'&&e.day==='2026-12-03').length};}")
        ok('فحص جديد كله ناقص بعد فحص قديم 5/5: «غير مكتمل» للجديد بلا أخضر مبني على القديم، والقديم باقٍ', r['a'] == {'day': '2026-12-10', 'n': 0, 'inc': True, 'light': 'grey', 'al': 1} and r['old'] == 5, r)
        ok('إكمال جزء من الفحص الجديد ثم التراجع عنه', r['b'] == {'day': '2026-12-10', 'n': 1, 'inc': True, 'light': 'grey', 'al': 1} and r['c'] == r['a'], r)
        pg = await fresh('aya', '2026-12-07')
        r = await pg.evaluate("()=>{" + FAR.replace('N', '7') + "seed(Array.from({length:7},(_,i)=>({type:'outcome',by:'asst',child:'c1',page:562+i,day:'2026-12-02',step:'far',result:'clean'})));seed([{type:'layer',by:'aya',child:'c1',page:571,day:'2026-12-04',layer:'far',color:'green'}]);Store.add({type:'layer',child:'c1',page:570,layer:'far',color:'green'});const t=deriveChild('c1').todayFar;t.forEach(p=>Store.add({type:'outcome',child:'c1',page:p,step:'far',result:'clean'}));nextDay();return {today:t,next:deriveChild('c1').todayFar};}")
        ok('صفحة دخلت البعيد بالجرد اليوم تنتظر آخر الدور، والتي دخلت قبل أيام تأتي بعد الأقدم تسميعاً', r['today'] == [562, 563, 564, 565, 566, 567, 568] and r['next'] == [571, 570, 562, 563, 564, 565, 566], r)
        pg = await fresh('aya', '2026-12-07')
        r = await pg.evaluate("()=>{seed(Array.from({length:20},(_,i)=>({type:'layer',by:'aya',child:'c1',page:582+i,day:'2026-11-01',layer:'near',color:'green'})));" + FAR.replace('N', '7') + "seed(Array.from({length:7},(_,i)=>({type:'outcome',by:'asst',child:'c1',page:562+i,day:'2026-12-02',step:'far',result:'clean'})));Store.add({type:'juz_passed',child:'c1',juz:30});const d=deriveChild('c1');return {far:d.far.length,today:d.todayFar};}")
        ok('إجازة جزء اليوم: صفحاته لا تزاحم حصة البعيد الأقدم', r['far'] > 7 and r['today'] == [562, 563, 564, 565, 566, 567, 568], r)

        # ===== 0.16.5: سقف القريب حد فعلي يشمل الحمراء =====
        pg = await fresh('aya')
        r = await pg.evaluate("()=>{seed(Array.from({length:15},(_,i)=>({type:'layer',by:'aya',day:'2026-12-01',child:'c1',page:542+i,layer:'near',color:'red'})));const d1=deriveChild('c1');const al=alertsList().filter(a=>a.child==='c1'&&a.text.includes('سقف القريب')).map(a=>a.text);App.setRole('asst');const alA=alertsList().filter(a=>a.child==='c1'&&a.text.includes('سقف القريب')).length;d1.nearToday.forEach(p=>Store.add({type:'outcome',child:'c1',page:p,step:'near',result:'yellow',prompts:1}));const same=deriveChild('c1').nearToday;nextDay();const d2=deriveChild('c1');return {cap:d1.caps.near,reds:d1.reds.length,t1:d1.nearToday,over1:d1.redsOver,al,alA,same,t2:d2.nearToday};}")
        ok('15 صفحة حمراء بسقف 10: حصة اليوم 10 فقط، والخمس الزائدة تُعرض لآية وحدها بأرقامها', r['cap'] == 10 and r['reds'] == 15 and r['t1'] == list(range(542, 552)) and r['over1'] == list(range(552, 557)) and len(r['al']) == 1 and '5 منها خارج حصة اليوم' in r['al'][0] and r['alA'] == 0, r)
        ok('الحمراء تتناوب بالأقدم تسميعاً: الخمس المؤجلة تتقدم حصة الغد، والحصة ثابتة داخل اليوم', r['same'] == r['t1'] and set(range(552, 557)) <= set(r['t2']) and len(r['t2']) == 10, r['t2'])
        pg = await fresh('aya')
        r = await pg.evaluate("()=>{seed(Array.from({length:15},(_,i)=>({type:'layer',by:'aya',day:'2026-12-01',child:'c1',page:542+i,layer:'near',color:'red'})));Store.add({type:'decision',child:'c1',kind:'caps',near:15});const d=deriveChild('c1');return {n:d.nearToday.length,over:d.redsOver.length,al:alertsList().filter(a=>a.child==='c1'&&a.text.includes('سقف القريب')).length};}")
        ok('رفع السقف بقرار آية إلى 15 يُدخل الحمراء كلها ويُسكت التنبيه', r == {'n': 15, 'over': 0, 'al': 0}, r)

        # ===== 0.16.7: LM0166-01..03 =====
        RED = "seed(Array.from({length:15},(_,i)=>({type:'layer',by:'aya',day:'2026-12-01',child:'c1',page:542+i,layer:'near',color:'red'})));"
        pg = await fresh('aya')
        r = await pg.evaluate("async()=>{" + RED + "const a=deriveChild('c1').nearToday;for(const p of a)Store.add({type:'outcome',child:'c1',page:p,step:'near',result:'clean'});Store.add({type:'color',child:'c1',page:542,color:'yellow'});let d=deriveChild('c1');const one={list:d.nearToday.slice().sort((x,y)=>x-y),over:d.redsOver};for(const p of a.slice(1))Store.add({type:'color',child:'c1',page:p,color:'yellow'});d=deriveChild('c1');const all={list:d.nearToday.slice().sort((x,y)=>x-y),over:d.redsOver,al:alertsList().filter(x=>x.child==='c1'&&x.text.includes('سقف القريب')).length};await Store.durable();return {a,one,all};}")
        ten = list(range(542, 552)); five = list(range(552, 557))
        ok('عشر حمراء سُمّعت ثم تحسن لون واحدة: الحصة هي العشر نفسها، لا صفحة بديلة', r['a'] == ten and r['one'] == {'list': ten, 'over': five}, r['one'])
        ok('ثم تحسن لون العشر كلها: المجموع يبقى 10، والخمس الحمراء الباقية خارج الحصة وتنبيهها باقٍ', r['all'] == {'list': ten, 'over': five, 'al': 1}, r['all'])
        await pg.reload(); await pg.wait_for_function('Store.raw && Store.idbOk')
        r = await pg.evaluate("()=>{App.setRole('aya');Store.settings.timeOffset=Date.parse('2026-12-07T00:00:00Z')-Date.now();const d=deriveChild('c1');const same=d.nearToday.slice().sort((x,y)=>x-y);const dec=Store.add({type:'decision',child:'c1',kind:'caps',near:5});const down=deriveChild('c1').nearToday.length;Store.add({type:'undo',child:'c1',target:dec.id,reason:'اختبار'});Store.add({type:'decision',child:'c1',kind:'caps',near:12});const up=deriveChild('c1');return {same,down,up:up.nearToday.slice().sort((x,y)=>x-y),over:up.redsOver};}")
        ok('بعد إعادة الفتح الحصة نفسها؛ خفض السقف إلى 5 لا يمحو المنجز، ورفعه إلى 12 يضيف صفحتين فقط', r == {'same': ten, 'down': 10, 'up': list(range(542, 554)), 'over': [554, 555, 556]}, r)
        pg = await fresh('aya')
        r = await pg.evaluate("()=>{" + RED + "seed([{type:'layer',by:'aya',day:'2026-12-01',child:'c1',page:562,layer:'far',color:'green'}]);const a=deriveChild('c1').nearToday;a.slice(0,4).forEach(p=>Store.add({type:'outcome',child:'c1',page:p,step:'near',result:'clean'}));Store.add({type:'outcome',child:'c1',page:a[4],step:'near',result:'partial'});Store.add({type:'color',child:'c1',page:562,color:'red'});const d=deriveChild('c1');return {n:d.nearToday.length,has:d.nearToday.includes(562),over:d.redsOver.includes(562),done:a.slice(0,4).every(p=>d.nearToday.includes(p))};}")
        ok('حمراء من البعيد تُضاف وسط اليوم والميزانية ممتلئة: لا تتضخم الحصة، وتظهر في الزائد', r == {'n': 10, 'has': False, 'over': True, 'done': True}, r)
        pg = await fresh('aya')
        r = await pg.evaluate("()=>{" + RED + "const a=deriveChild('c1').nearToday;const o=Store.add({type:'outcome',child:'c1',page:542,step:'near',result:'clean'});Store.add({type:'color',child:'c1',page:542,color:'yellow'});const kept=deriveChild('c1').nearToday.includes(542);Store.add({type:'undo',child:'c1',target:o.id,reason:'اختبار'});const d=deriveChild('c1');return {kept,after:d.nearToday.includes(542),n:d.nearToday.length};}")
        ok('التراجع عن التسميع يردّ الميزانية: الصفحة التي لم تعد حمراء ولا منجزة تخرج ويدخل غيرها', r == {'kept': True, 'after': False, 'n': 10}, r)

        outs = {}
        for rev in (False, True):
            pg = await fresh('aya')
            a_ = await pg.evaluate("rev=>{seed([{type:'layer',by:'aya',day:'2026-12-01',child:'c1',page:562,layer:'far',color:'green'}]);const ts=Date.parse('2026-12-07T01:00:00Z');const a={id:'same-a',ts,day:'2026-12-07',by:'asst',type:'outcome',child:'c1',page:562,step:'far',result:'clean'};const b={...a,id:'same-b',result:'partial'};if(rev===2){Store.importEvents([b]);Store.importEvents([a]);}else Store.importEvents(rev?[b,a]:[a,b]);return {eff:effectiveOutcomes(e=>e.child==='c1').map(e=>[e.id,e.result]),lastFar:deriveChild('c1').pages[562].lastFar,order:Store.raw.filter(e=>e.type==='outcome').map(e=>e.id)};}", rev)
            await pg.evaluate('Store.durable()'); await pg.reload(); await pg.wait_for_function('Store.raw && Store.idbOk')
            b_ = await pg.evaluate("()=>{App.setRole('aya');Store.settings.timeOffset=Date.parse('2026-12-07T00:00:00Z')-Date.now();return {eff:effectiveOutcomes(e=>e.child==='c1').map(e=>[e.id,e.result]),lastFar:deriveChild('c1').pages[562].lastFar,order:Store.raw.filter(e=>e.type==='outcome').map(e=>e.id)};}")
            outs[rev] = (a_, b_)
        pg = await fresh('aya')
        split = await pg.evaluate("()=>{seed([{type:'layer',by:'aya',day:'2026-12-01',child:'c1',page:562,layer:'far',color:'green'}]);const ts=Date.parse('2026-12-07T01:00:00Z');const a={id:'same-a',ts,day:'2026-12-07',by:'asst',type:'outcome',child:'c1',page:562,step:'far',result:'clean'};const b={...a,id:'same-b',result:'partial'};Store.importEvents([b]);Store.importEvents([a]);const eff=effectiveOutcomes(e=>e.child==='c1').map(e=>[e.id,e.result]);Store.add({type:'undo',child:'c1',target:eff[0][0],reason:'اختبار'});return {eff,afterUndo:effectiveOutcomes(e=>e.child==='c1').map(e=>[e.id,e.result]),lastFar:deriveChild('c1').pages[562].lastFar};}")
        ok('سجلان بتوقيت واحد: النتيجة النافذة واحدة سواء وصلا [أ،ب] أو [ب،أ] أو في دفعتين، وقبل إعادة الفتح وبعدها', outs[False][0] == outs[True][0] == outs[False][1] == outs[True][1] and split['eff'] == outs[False][0]['eff'] and outs[False][0]['order'] == ['same-a', 'same-b'], {'ab': outs[False], 'ba': outs[True], 'split': split})
        ok('والتراجع عن الفائزة يُظهر الأخرى', split['eff'] == [['same-b', 'partial']] and split['afterUndo'] == [['same-a', 'clean']] and split['lastFar'] == '2026-12-07', split)
        pg = await fresh('aya')
        r = await pg.evaluate("()=>{const t=Date.now;const fixed=t();Date.now=()=>fixed;const x=Store.add({type:'note',text:'1'}),y=Store.add({type:'note',text:'2'}),z=Store.add({type:'note',text:'3'});Date.now=t;return {inc:x.ts<y.ts&&y.ts<z.ts,order:Store.raw.filter(e=>e.type==='note').map(e=>e.text)};}")
        ok('سجلات الجهاز نفسه في الميلي ثانية نفسها تبقى بترتيب إنشائها', r == {'inc': True, 'order': ['1', '2', '3']}, r)

        pg = await fresh('aya')
        r = await pg.evaluate("()=>{Store.add({type:'layer',child:'c1',page:562,layer:'far',color:'green'});Store.add({type:'outcome',child:'c1',page:562,step:'far',result:'clean'});const one=briefFor('c1').farHeard;const fix=Store.add({type:'outcome',child:'c1',page:562,step:'far',result:'partial'});const zero=briefFor('c1').farHeard;Store.add({type:'undo',child:'c1',target:fix.id,reason:'اختبار'});const back=briefFor('c1').farHeard;return {one,zero,back};}")
        ok('الموجز الأسبوعي: تسميع بعيد صُحّح إلى «ناقص» لا يُحتسب، والتراجع عن التصحيح يعيده', r == {'one': [562], 'zero': [], 'back': [562]}, r)
        pg = await fresh('aya', '2026-12-08')
        r = await pg.evaluate("()=>{seed([{type:'layer',by:'aya',day:'2026-12-01',child:'c1',page:562,layer:'far',color:'green'},{type:'outcome',by:'asst',day:'2026-12-07',child:'c1',page:562,step:'far',result:'clean'}]);Store.add({type:'outcome',child:'c1',page:562,step:'far',result:'partial'});return briefFor('c1').farHeard;}")
        ok('تسميع مكتمل في يوم آخر من الأسبوع يبقى محتسباً رغم محاولة ناقصة لاحقة', r == [562], r)

        # ===== 0.16.8: الإعدادات والجلسة الجارية تنجو من رجوع localStorage (إغلاق مفاجئ في WebView) =====
        pg = await fresh('asst')
        r0 = await pg.evaluate("async()=>{" + FAR.replace('N', '12') + "await Store.durable();const stale=localStorage.getItem('lm_settings_v1');startSession(PLAN.find(s=>s.kind==='noon'&&s.child==='c1'));Store.settings.active.cur=1;saveActive();Store.settings.pins.asst='7788';Store.saveSettings();await Store.durable();const sid=Store.settings.active.sid;localStorage.setItem('lm_settings_v1',stale);return {sid,staleActive:!!JSON.parse(stale).active};}")
        await pg.reload(); await pg.wait_for_function('Store.raw && Store.idbOk')
        r = await pg.evaluate("({sid:Store.settings.active&&Store.settings.active.sid,cur:Store.settings.active&&Store.settings.active.cur,pin:Store.settings.pins.asst,ls:JSON.parse(localStorage.getItem('lm_settings_v1')).active.cur})")
        ok('localStorage عاد إلى ما قبل بدء الجلسة: الجلسة وخطوتها ورقم الدخول الجديد تعود من قاعدة الجهاز', r0['staleActive'] is False and r == {'sid': r0['sid'], 'cur': 1, 'pin': '7788', 'ls': 1}, {'r0': r0, 'r': r})
        r = await pg.evaluate("async()=>{endActiveForTest=()=>{Store.settings.active=null;Store.saveSettings();};endActiveForTest();await Store.durable();return true;}")
        await pg.reload(); await pg.wait_for_function('Store.raw && Store.idbOk')
        ok('والأحدث يُعتمد في الاتجاه الآخر: إنهاء الجلسة لا تُرجعه نسخة أقدم', await pg.evaluate("Store.settings.active === null"))
        await pg.evaluate("()=>{const st=JSON.parse(localStorage.getItem('lm_settings_v1'));st.fluency_c3=590;localStorage.setItem('lm_settings_v1',JSON.stringify(st));}")
        await pg.reload(); await pg.wait_for_function('Store.raw && Store.idbOk')
        ok('عند تساوي الرقم التسلسلي يُعتمد localStorage (لا تُفرض النسخة الثانية بلا سبب)', await pg.evaluate("Store.settings.fluency_c3") == 590)

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
    print(f'AUDIT 0.16.2-8 OK ({len(results)} حالة)')

asyncio.run(main())
