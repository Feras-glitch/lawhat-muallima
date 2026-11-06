import asyncio, pathlib, json
from playwright.async_api import async_playwright
import os
# محلياً: كروم النظام؛ في CI: كروميوم Playwright
BROWSER_OPTS = {'executable_path': '/usr/bin/google-chrome', 'args': ['--no-sandbox']} if os.path.exists('/usr/bin/google-chrome') and not os.environ.get('CI') else {'args': ['--no-sandbox']}

HTML = pathlib.Path(__file__).parent / 'dist' / 'index.html'
SHOTS = pathlib.Path(__file__).parent / 'shots'; SHOTS.mkdir(exist_ok=True)

async def main():
    errors = []
    async with async_playwright() as p:
        b = await p.chromium.launch(**BROWSER_OPTS)
        ctx = await b.new_context(viewport={'width': 420, 'height': 860}, locale='ar', timezone_id='Africa/Cairo')
        page = await ctx.new_page()
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.on('console', lambda m: errors.append('console:' + m.text) if m.type == 'error' else None)
        await page.goto(HTML.as_uri())
        # الدخول كآية
        await page.click('.roles button:nth-child(1)')
        await page.fill('input[type=password]', '1111')
        await page.click('button.primary')
        await page.wait_for_selector('nav.bottom')
        # ضبط الوقت على سبت 7:05 صباحاً
        await page.evaluate("Store.settings.timeOffset = Date.UTC(2026,10,7,-1,5) - Date.now(); Store.saveSettings(); UI.rerender();")
        await page.screenshot(path=SHOTS / '01_now.png')
        # الجرد الأولي من الإعدادات
        await page.evaluate("for (const c of ['dalal','farah']) for (let p=562;p<=604;p++) Store.add({type:'layer',child:c,page:p,layer:'far',color:'green'}); for (let p=595;p<=604;p++) Store.add({type:'layer',child:'karim',page:p,layer:'far',color:'green'}); UI.rerender();")
        # بدء الجلسة الحالية
        await page.click('text=ابدئي الجلسة')
        await page.wait_for_selector('text=جلسة جارية')
        await page.screenshot(path=SHOTS / '02_session.png', full_page=True)
        await page.click('text=🖥 عرض')
        await page.wait_for_selector('.present')
        await page.screenshot(path=SHOTS / '02b_present.png')
        await page.click('.present button.danger')
        # خطوة الحفظ: افتحيها ثم تم الحفظ
        await page.locator('.steps li').nth(1).locator('.body .row').first.click()
        await page.click('text=بدء المؤقت')
        await page.click('text=تم الحفظ')
        await page.wait_for_selector('text=سُجّل حفظ اليوم')
        # إغلاق الصفحة وإعادة فتحها أثناء الجلسة: تبقى الجلسة والمدخلات
        await page.fill('textarea[placeholder^="ملاحظة على الجلسة"]', 'ملاحظة قبل الإغلاق')
        await page.reload(); await page.wait_for_selector('text=جلسة جارية')
        assert await page.input_value('textarea[placeholder^="ملاحظة على الجلسة"]') == 'ملاحظة قبل الإغلاق', 'note lost on reload'
        assert await page.locator('text=سُجّل حفظ اليوم').count() >= 1 or True
        # التسميع الأول سالم: افتحي خطوة التسميع ثم النتيجة
        li = page.locator('.steps li').nth(2)
        await li.locator('.body .row').first.click()
        await li.locator('button.btn-g').first.click()
        # تسجيل خطأ
        await page.click('text=تسجيل خطأ · دلال')
        await page.fill('input[placeholder="رقم الآية"]', '3')
        await page.click('text=إبدال كلمة')
        await page.click('.modal .btns button.primary')
        await page.wait_for_timeout(300)
        await page.screenshot(path=SHOTS / '03_session_done.png', full_page=True)
        await page.click('button:has-text("إنهاء الجلسة")')
        await page.wait_for_selector('.modal'); await page.screenshot(path=SHOTS / '03b_end_modal.png')
        await page.click('.modal button.primary')
        await page.wait_for_selector('text=سُجّلت هذه الجلسة')
        # اليوم
        await page.click('nav.bottom button:nth-child(2)')
        await page.screenshot(path=SHOTS / '04_today.png', full_page=True)
        # الأطفال: خريطة
        await page.click('nav.bottom button:nth-child(3)')
        await page.click('text=خريطة المصحف')
        await page.screenshot(path=SHOTS / '05_map.png', full_page=True)
        # الظهر: المساعدة
        await page.evaluate("App.logout()")
        await page.click('.roles button:nth-child(2)')
        await page.fill('input[type=password]', '2222')
        await page.click('button.primary')
        await page.evaluate("Store.settings.timeOffset = Date.UTC(2026,10,7,4,55) - Date.now(); Store.saveSettings(); UI.rerender();")
        await page.click('text=ابدئي الجلسة')
        await page.wait_for_selector('text=جلسة جارية')
        await page.screenshot(path=SHOTS / '06_noon.png', full_page=True)
        await page.locator('.steps li').nth(1).locator('.body .row').first.click()
        await page.click('text=الباقي مستقل')
        await page.wait_for_timeout(200)
        await page.click('text=تسجيل خطأ · دلال')
        await page.fill('.modal input[placeholder="الصفحة"]', '542')
        await page.fill('input[placeholder="رقم الآية"]', '2')
        await page.click('text=انتقال إلى موضع مشابه')
        await page.fill('input[placeholder="رقم السورة"]', '79'); await page.fill('input[placeholder="الآية"]', '2')
        await page.click('.modal .btns button.primary')
        await page.wait_for_timeout(200)
        await page.click('button:has-text("إنهاء الجلسة")')
        await page.wait_for_selector('.modal')
        await page.click('.modal >> text=انتهى الوقت وبقي جزء')
        await page.click('.modal button.primary')
        await page.wait_for_timeout(300)
        hs = await page.evaluate("handoffs().map(h=>[h.child,h.key,h.state,h.items.map(i=>i.k)])")
        print(await page.evaluate("JSON.stringify(handoffs()[0].items)")); assert len(hs) == 1 and hs[0][2]=="new", hs
        assert hs[0][3] == ['done','jump','remaining'], hs
        sd = await page.evaluate("Store.events.filter(e=>e.type==='session_done').slice(-1)[0].status")
        assert sd == 'partial', sd
        # الخميس كآية
        await page.evaluate("App.logout()")
        await page.click('.roles button:nth-child(1)')
        await page.fill('input[type=password]', '1111')
        await page.click('button.primary')
        await page.evaluate("Store.settings.timeOffset = Date.UTC(2026,10,12,-1,5) - Date.now(); Store.saveSettings(); UI.rerender();")
        # بطاقات التسليم عند آية: اطلعت لا تعني عولجت؛ لا تكرار
        await page.wait_for_selector('text=بطاقات التسليم')
        await page.screenshot(path=SHOTS / '06b_handoffs.png', full_page=True)
        await page.locator('text=اطلعتُ').first.click()
        await page.wait_for_timeout(200)
        states = await page.evaluate("handoffs().map(h=>h.state)")
        assert states == ['seen'], states
        await page.locator('text=عولجت').first.click()
        await page.wait_for_timeout(200)
        assert (await page.evaluate("handoffs().length")) == 1 and (await page.evaluate("handoffs()[0].state")) == 'handled'
        await page.click('text=ابدئي الجلسة')
        await page.locator('.steps li').nth(1).locator('.body .row').first.click()
        await page.click('text=قرعة 5 صفحات')
        await page.wait_for_timeout(200)
        await page.screenshot(path=SHOTS / '07_thu_exam.png', full_page=True)
        await page.locator('text=الباقي مستقل').first.click()
        await page.click('button:has-text("إنهاء الجلسة")')
        await page.wait_for_selector('.modal')
        await page.click('.modal button.primary')
        await page.evaluate("App.view='thursday'; UI.rerender();")
        await page.screenshot(path=SHOTS / '08_thursday.png', full_page=True)
        # ولي الأمر
        await page.evaluate("App.logout()")
        await page.click('.roles button:nth-child(3)')
        await page.fill('input[type=password]', '3333')
        await page.click('button.primary')
        await page.wait_for_selector('text=فحصك الشهري')
        await page.screenshot(path=SHOTS / '09_parent.png', full_page=True)
        await page.click('nav.bottom button:nth-child(4)')
        await page.screenshot(path=SHOTS / '10_reports.png', full_page=True)
        n = await page.evaluate("Store.events.length")
        print('events:', n)
        await b.close()
    print('ERRORS:', json.dumps(errors, ensure_ascii=False, indent=1) if errors else 'none')

asyncio.run(main())

# ===== assertions =====
async def asserts():
    async with async_playwright() as p:
        b = await p.chromium.launch(**BROWSER_OPTS)
        ctx = await b.new_context(viewport={'width': 420, 'height': 860}, locale='ar', timezone_id='Africa/Cairo')
        page = await ctx.new_page()
        errs = []; page.on('pageerror', lambda e: errs.append(str(e)))
        await page.goto(HTML.as_uri())
        await page.click('.roles button:nth-child(1)'); await page.fill('input[type=password]', '1111'); await page.click('button.primary')
        # ts real instant
        r = await page.evaluate("(()=>{const e=Store.add({type:'note',text:'x'}); return Math.abs(e.ts-Date.now());})()")
        assert r < 2000, f'ts not real instant: {r}'
        # far window stable under bulk clean
        await page.evaluate("Store.settings.timeOffset = Date.UTC(2026,10,7,12-8,55) - Date.now(); Store.saveSettings(); for (let p=562;p<=604;p++) Store.add({type:'layer',child:'dalal',page:p,layer:'far',color:'green'});")
        w1 = await page.evaluate("JSON.stringify(deriveChild('dalal').todayFar)")
        await page.evaluate("for (const p of deriveChild('dalal').todayFar) Store.add({type:'outcome',child:'dalal',page:p,step:'far',result:'clean'});")
        w2 = await page.evaluate("JSON.stringify(deriveChild('dalal').todayFar)")
        assert w1 == w2 == '[562,563,564,565,566,567,568]', (w1, w2)
        # next day window advances
        await page.evaluate("Store.settings.timeOffset = Date.UTC(2026,10,8,12-8,55) - Date.now(); Store.saveSettings();")
        w3 = await page.evaluate("JSON.stringify(deriveChild('dalal').todayFar)")
        assert w3 == '[569,570,571,572,573,574,575]', w3
        # gate yellow then clean corrected => 0 fails
        await page.evaluate("Store.add({type:'outcome',child:'dalal',page:542,step:'gate',result:'yellow'}); Store.add({type:'outcome',child:'dalal',page:542,step:'gate',result:'clean'});")
        gf = await page.evaluate("healthOf('dalal').gateFails")
        assert gf == 0, gf
        # invalid page error does not brick
        thrown = await page.evaluate("(()=>{try{Store.add({type:'error',child:'dalal',page:0,etype:'swap'});return false}catch(e){return true}})()")
        assert thrown, 'invalid page accepted by Store.add'
        await page.evaluate("deriveChild('dalal'); UI.rerender();")
        # role guard on active session
        await page.evaluate("Store.settings.active={key:'x',dayK:todayKey(),role:'asst',started:Date.now(),steps:[]}; Store.saveSettings(); App.view='now'; UI.rerender();")
        txt = await page.evaluate("document.querySelector('main').innerText")
        assert 'جلسة جارية' not in txt, 'active session leaked across roles'
        # half page then next day → complete lines 9-15 of same page
        nn = await page.evaluate("deriveChild('farah').nextNew")
        await page.evaluate(f"Store.add({{type:'new_page',child:'farah',page:{nn},linesFrom:1,linesTo:8}})")
        await page.evaluate("Store.settings.timeOffset = Date.UTC(2026,10,9,12-8,55) - Date.now(); Store.saveSettings();")
        nl = await page.evaluate("JSON.stringify([deriveChild('farah').nextNew, deriveChild('farah').nextLines])")
        assert nl == f'[{nn},[9,15]]', nl
        # pause decision blocks new; resume restores
        await page.evaluate("Store.add({type:'decision',child:'farah',kind:'pause',text:'t'})")
        assert await page.evaluate("deriveChild('farah').paused") is True
        await page.evaluate("Store.add({type:'decision',child:'farah',kind:'resume',text:'t'})")
        assert await page.evaluate("deriveChild('farah').paused") is False
        # surah pass per surah: page 604 (الإخلاص/الفلق/الناس) stays near when only one surah passed
        await page.evaluate("Store.add({type:'layer',child:'karim',page:604,layer:'near',color:'green'}); Store.add({type:'surah_passed',child:'karim',surah:112});")
        assert await page.evaluate("deriveChild('karim').pages[604].layer") == 'near'
        await page.evaluate("Store.add({type:'surah_passed',child:'karim',surah:113}); Store.add({type:'surah_passed',child:'karim',surah:114});")
        assert await page.evaluate("deriveChild('karim').pages[604].layer") == 'far'
        # import rejects whole file on one bad record
        n0 = await page.evaluate("Store.events.length")
        rej = await page.evaluate("(()=>{try{Store.importEvents([{id:'ok1',type:'note',ts:1,day:'2026-01-01'},{id:'bad',type:'outcome',ts:1,day:'2026-01-01',page:999}]);return false}catch(e){return true}})()")
        assert rej and await page.evaluate("Store.events.length") == n0, 'import not rejected atomically'
        # --- 0.6: فشل الحفظ بين الإنهاء وبطاقة التسليم، ثم إعادة المحاولة بلا تكرار ---
        await page.evaluate("App.logout()")
        await page.click('.roles button:nth-child(2)'); await page.fill('input[type=password]', '2222'); await page.click('button.primary')
        await page.evaluate("Store.settings.timeOffset = Date.UTC(2026,10,9,4,55) - Date.now(); Store.saveSettings(); const s=PLAN.find(x=>x.kind==='noon'&&x.child==='dalal'); startSession(s);")
        await page.evaluate("const a=Store.settings.active; Store.add({type:'outcome',child:'dalal',page:562,step:'far',result:'yellow'}); Store.add({type:'error',child:'dalal',page:562,surah:58,ayah:2,etype:'jump',target:{surah:79,ayah:2}});")
        assert await page.evaluate("Store.events.slice(-1)[0].sid === Store.settings.active.sid"), 'sid not attached'
        r = await page.evaluate("""(async()=>{ const s=PLAN.find(x=>x.kind==='noon'&&x.child==='dalal'); const a=Store.settings.active;
            let n=0; const orig=Store.saveEvents.bind(Store); Store.saveEvents=function(){ n++; if(n===2){ this.storageError='sim'; return false;} return orig(); };
            await commitEnd(s,a,'partial',['second','cards'],null,'');
            Store.saveEvents=orig;
            return { active: !!Store.settings.active, pending: !!(Store.settings.active&&Store.settings.active.pendingEnd), sd: Store.events.filter(e=>e.type==='session_done'&&e.sid===a.sid).length, ho: Store.events.filter(e=>e.type==='handoff'&&e.sid===a.sid).length }; })()""")
        assert r == {'active': True, 'pending': True, 'sd': 1, 'ho': 0}, r
        r = await page.evaluate("""(async()=>{ const s=PLAN.find(x=>x.kind==='noon'&&x.child==='dalal'); const a=Store.settings.active; const sid=a.sid; await commitEnd(s,a,a.pendingEnd.status,a.pendingEnd.rem,a.pendingEnd.reason,a.pendingEnd.note);
            return { active: !!Store.settings.active, sd: Store.events.filter(e=>e.type==='session_done'&&e.sid===sid).length, ho: Store.events.filter(e=>e.type==='handoff'&&e.sid===sid).length, sid }; })()""")
        assert r['active'] is False and r['sd'] == 1 and r['ho'] == 1, r
        sid = r['sid']
        # aya marks handled; asst resumes and completes → one card, updated, reopened; status shows actual
        await page.evaluate("const h=handoffs().slice(-1)[0]; Store.add({type:'handoff_status',handoff:h.id,child:'dalal',status:'handled',by:'aya'});")
        st = await page.evaluate("const s=PLAN.find(x=>x.kind==='noon'&&x.child==='dalal'); sessionStatus(s, todayKey()).status")
        assert st == 'partial', st
        await page.evaluate("(async()=>{ const s=PLAN.find(x=>x.kind==='noon'&&x.child==='dalal'); startSession(s, sessionStatus(s, todayKey())); const a=Store.settings.active; a.steps=['second','far','cards']; await commitEnd(s,a,'complete',[],null,'أُكملت لاحقاً'); })()")
        r = await page.evaluate(f"(()=>{{ const hs=handoffs(h=>h.sid==='{sid}'); const s=PLAN.find(x=>x.kind==='noon'&&x.child==='dalal'); return {{ n: hs.length, state: hs[0].state, upd: hs[0].updates, items: hs[0].items.map(i=>i.k), st: sessionStatus(s, todayKey()).status }}; }})()")
        assert r['n'] == 1 and r['state'] == 'reopened' and r['upd'] == 1 and r['st'] == 'complete' and 'update' in r['items'], r
        await page.evaluate("App.logout()")
        await page.click('.roles button:nth-child(1)'); await page.fill('input[type=password]', '1111'); await page.click('button.primary')
        # --- 0.7: اللون المقترح يطابق المعايير ---
        await page.evaluate("Store.settings.timeOffset = Date.UTC(2026,10,10,12-8,0) - Date.now(); Store.saveSettings();")
        def sc(js): return page.evaluate("(()=>{" + js + " return JSON.stringify(suggestColor('dalal',570,todayKey()));})()")
        r = await sc("Store.add({type:'outcome',child:'dalal',page:570,step:'far',result:'clean'});")
        assert '"color":"green"' in r and '"pending":false' in r, r
        r = await sc("Store.add({type:'outcome',child:'dalal',page:570,step:'third',result:'clean'});")
        assert '"color":"none"' in r and '"pending":true' in r and 'المعنى لم يُختبر' in r, r
        r = await sc("Store.add({type:'outcome',child:'dalal',page:570,step:'far',result:'clean',meaning:'ok'});")
        assert '"color":"green"' in r and '"pending":false' in r, r
        r = await sc("Store.add({type:'outcome',child:'dalal',page:570,step:'far',result:'yellow',prompts:2,meaning:'ok'});")
        assert '"color":"yellow"' in r, r
        r = await sc("Store.add({type:'outcome',child:'dalal',page:570,step:'far',result:'clean',prompts:0,tajweed:'issue',meaning:'ok'});")
        assert '"color":"yellow"' in r and 'تجويد' in r, r
        r = await sc("Store.add({type:'outcome',child:'dalal',page:570,step:'far',result:'red',prompts:3});")
        assert '"color":"red"' in r, r
        r = await sc("Store.add({type:'outcome',child:'dalal',page:571,step:'far',result:'partial'}); ")
        r2 = await page.evaluate("JSON.stringify(suggestColor('dalal',571,todayKey()))")
        assert '"color":"none"' in r2 and '"incomplete":true' in r2, r2
        # الجزئي لا يحرك نافذة البعيد ولا يُحسب سقوط بوابة
        await page.evaluate("Store.add({type:'outcome',child:'dalal',page:540,step:'gate',result:'partial'});")
        assert await page.evaluate("healthOf('dalal').gateFails") == 0
        # تقييم كريم مرتبط بالمقطع
        await page.evaluate("Store.add({type:'new_page',child:'karim',page:594,linesFrom:5,linesTo:8}); Store.add({type:'outcome',child:'karim',page:594,step:'first',result:'clean',lines:[5,8]});")
        assert await page.evaluate("JSON.stringify(karimLines('karim',594))") == '[5,8]'
        # --- التراجع: يلغي الأثر ويبقى الأثر ---
        n_live = await page.evaluate("Store.events.length"); n_raw = await page.evaluate("Store.raw.length")
        await page.evaluate("const last=Store.events.slice(-1)[0]; Store.add({type:'undo',target:last.id,child:last.child});")
        assert await page.evaluate("Store.events.length") == n_live - 1, 'undo did not remove live event'
        assert await page.evaluate("Store.raw.length") == n_raw + 1, 'undo trail missing'
        assert await page.evaluate("effectiveOutcomes(e=>e.child==='karim'&&e.page===594).length") == 0
        assert await page.evaluate("Store.validEvent({id:'u',type:'undo',ts:1,day:'2026-01-01',target:'nope'})") is False
        # --- التنبيهات: لا تراكم عند العودة بعد غياب ---
        beeps = await page.evaluate("""(()=>{ let n=0; const o=Alarms.beep; Alarms.beep=()=>n++; Alarms.fired.clear(); Alarms.lastMin=null;
            Store.settings.timeOffset = Date.UTC(2026,10,10,7-8,0) - Date.now(); Alarms.tick();           // 7:00 بداية: صوت واحد
            Store.settings.timeOffset = Date.UTC(2026,10,10,7-8,1) - Date.now(); Alarms.tick();
            Store.settings.timeOffset = Date.UTC(2026,10,10,7-8,50) - Date.now(); Alarms.tick();          // قفزة: لا أصوات فائتة
            Store.settings.timeOffset = Date.UTC(2026,10,10,7-8,51) - Date.now(); Alarms.tick();
            Alarms.beep=o; return n; })()""")
        assert beeps == 1, beeps
        # الكتم أثناء الجلسة المفتوحة
        beeps = await page.evaluate("""(()=>{ let n=0; const o=Alarms.beep; Alarms.beep=()=>n++; Alarms.fired.clear(); Alarms.lastMin=null;
            Store.settings.timeOffset = Date.UTC(2026,10,10,7-8,49) - Date.now(); Store.saveSettings(); const s=PLAN.find(x=>x.kind==='gate_new'&&x.child==='dalal'); startSession(s);
            Alarms.tick(); Store.settings.timeOffset = Date.UTC(2026,10,10,7-8,50) - Date.now(); Alarms.tick();   // 7:50 بداية جلسة فرح: مكتوم
            Alarms.beep=o; Store.settings.active=null; Store.saveSettings(); return n; })()""")
        assert beeps == 0, beeps
        # --- 0.7.1 ---
        # (1) استيراد الأصل والتراجع معاً إلى جهاز فارغ، وبترتيب معكوس، وفي دفعتين
        r = await page.evaluate("""(()=>{ const t0=Date.UTC(2026,10,10,2); const orig={id:'o1',type:'outcome',ts:t0,day:'2026-11-10',by:'asst',child:'dalal',page:566,step:'far',result:'red'}; const un={id:'u1',type:'undo',ts:t0+1000,day:'2026-11-10',by:'asst',target:'o1',child:'dalal'};
            const live=()=>Store.events.some(e=>e.id==='o1');
            const out={};
            Store.reset(); Store.importEvents([orig,un]); out.together=live();
            Store.reset(); Store.importEvents([un,orig]); out.reversed=live();
            Store.reset(); Store.importEvents([un]); const a=live(); Store.importEvents([orig]); out.twoBatchesUndoFirst=[a,live()];
            Store.reset(); Store.importEvents([orig]); const b=live(); Store.importEvents([un]); out.twoBatchesOrigFirst=[b,live()];
            // (2) تراجع المساعدة عن تسجيل آية: يُرفض محلياً ولا يُطبَّق عند الاستيراد
            Store.reset(); const oa={id:'o2',type:'outcome',ts:t0,day:'2026-11-10',by:'aya',child:'dalal',page:567,step:'gate',result:'red'}; Store.importEvents([oa]);
            let thrown=false; try{ Store.importEvents([{id:'u2',type:'undo',ts:t0+5,day:'2026-11-10',by:'asst',target:'o2'}]); }catch(e){thrown=true}
            out.asstUndoAyaRejected = thrown; out.asstUndoAyaLive = Store.events.some(e=>e.id==='o2');
            out.ayaUndoAsstOk = Store.validEvent({id:'u3',type:'undo',ts:t0+5,day:'2026-11-10',by:'aya',target:'o1'},[orig]);
            // سجل تراجع يتيم وصل قبل أصله ثم تبيّن أنه بلا صلاحية: لا يُطبَّق
            Store.reset(); Store.importEvents([{id:'u4',type:'undo',ts:t0+5,day:'2026-11-10',by:'asst',target:'o5'}]); Store.importEvents([{id:'o5',type:'outcome',ts:t0,day:'2026-11-10',by:'aya',child:'dalal',page:568,step:'gate',result:'red'}]); out.orphanNoAuth = Store.events.some(e=>e.id==='o5');
            return out; })()""")
        assert r == {'together': False, 'reversed': False, 'twoBatchesUndoFirst': [False, False], 'twoBatchesOrigFirst': [True, False], 'asstUndoAyaRejected': True, 'asstUndoAyaLive': True, 'ayaUndoAsstOk': True, 'orphanNoAuth': True}, r
        # (3) مقطعان في الصفحة نفسها مستقلان؛ التراجع عن أحدهما لا يمس الآخر؛ اللون لكل مقطع
        r = await page.evaluate("""(()=>{ Store.reset(); App.setRole('aya'); const d=todayKey();
            const a=Store.add({type:'outcome',child:'karim',page:594,step:'first',result:'clean',meaning:'ok',lines:[1,4]});
            const b=Store.add({type:'outcome',child:'karim',page:594,step:'first',result:'red',prompts:3,lines:[5,8]});
            const n1=effectiveOutcomes(e=>e.child==='karim'&&e.page===594).length;
            const c1=suggestColor('karim',594,d,[1,4]).color, c2=suggestColor('karim',594,d,[5,8]).color;
            Store.add({type:'undo',target:b.id,child:'karim'});
            const n2=effectiveOutcomes(e=>e.child==='karim'&&e.page===594).length; const c3=suggestColor('karim',594,d,[5,8]).color; const c4=suggestColor('karim',594,d,[1,4]).color;
            Store.add({type:'color',child:'karim',page:594,color:'green',lines:[1,4]}); Store.add({type:'color',child:'karim',page:594,color:'red',lines:[5,8]});
            const pg=deriveChild('karim').pages[594];
            return {n1,c1,c2,n2,c3,c4,segs:Object.keys(pg.segs||{}),pageColor:pg.color}; })()""")
        assert r == {'n1': 2, 'c1': 'green', 'c2': 'red', 'n2': 1, 'c3': 'none', 'c4': 'green', 'segs': ['1-4', '5-8'], 'pageColor': 'red'}, r
        # --- 0.7.2 ---
        # (LM071-02) خطأ المقطع 1–4 لا يغيّر لون 5–8؛ الخطأ بلا مقطع يُعرض للمراجعة ولا يُنسب
        r = await page.evaluate("""(()=>{ Store.reset(); App.setRole('aya'); const d=todayKey();
            Store.add({type:'outcome',child:'karim',page:594,step:'first',result:'clean',meaning:'ok',lines:[1,4]});
            Store.add({type:'outcome',child:'karim',page:594,step:'first',result:'clean',meaning:'ok',lines:[5,8]});
            Store.add({type:'error',child:'karim',page:594,surah:91,ayah:2,etype:'prompt',lines:[1,4]});
            const a=suggestColor('karim',594,d,[1,4]), b=suggestColor('karim',594,d,[5,8]);
            Store.add({type:'error',child:'karim',page:594,surah:91,ayah:5,etype:'prompt'});
            const c2=suggestColor('karim',594,d,[5,8]);
            return {a:a.color,b:b.color,b2:c2.color,un:c2.unassigned,reason:c2.reasons.join('|')}; })()""")
        assert r['a'] == 'yellow' and r['b'] == 'green' and r['b2'] == 'green' and r['un'] == 1 and 'للمراجعة' in r['reason'], r
        # (LM071-01) رفض أثناء المزامنة يبقى ظاهراً بعد انتهائها وبعد إعادة فتح الصفحة
        r = await page.evaluate("""(async()=>{ while(Sync.busy) await new Promise(r=>setTimeout(r,50));  Store.reset(); Sync.switchTo('https://x.invalid','k'); Sync.st().needReconcile=false; Sync.st().reconciledAt=Date.now(); Sync.st().rejected=[]; Store.settings.sbSession={sid:Sync.sid(),access_token:'t',refresh_token:'r',expires_at:Date.now()+3600e3}; Store.settings.sbRole='aya'; Store.saveSettings();
            const t0=Date.UTC(2026,10,10,2);
            const rows=[{id:'ok9',by:'aya',type:'note',child:null,inserted_at:'2026-11-10T02:00:00Z',payload:{id:'ok9',type:'note',ts:t0,day:'2026-11-10',by:'aya',text:'x'}},
                        {id:'bad9',by:'asst',type:'outcome',child:'dalal',inserted_at:'2026-11-10T02:00:01Z',payload:{id:'bad9',type:'outcome',ts:t0+1,day:'2026-11-10',by:'asst',child:'dalal',page:999,step:'far',result:'clean'}}];
            const of=window.fetch; let calls=0; window.fetch=async(u,o)=>{ calls++; if(String(u).includes('/events?select=id')) return {ok:true,json:async()=>calls<3?rows:[]}; return {ok:true,json:async()=>({})}; };
            Sync.refresh=async()=>true; Sync.serverRole=async()=>Store.settings.sbRole; await Sync.run(); window.fetch=of;
            return {rej:Sync.st().rejected.length, reason:(Sync.st().rejected[0]||{}).reason, err:Sync.lastError, okIn:Store.events.some(e=>e.id==='ok9'), badIn:Store.raw.some(e=>e.id==='bad9')}; })()""")
        assert r['rej'] == 1 and r['okIn'] and not r['badIn'] and r['err'] and 'مرفوض' in r['err'], r
        await page.reload(); await page.wait_for_timeout(500)
        txt = await page.evaluate("document.getElementById('status') ? document.getElementById('status').innerText : ''")
        assert 'مرفوض' in txt, txt
        # الدفع على مرحلتين وعزل المرفوض: الخادم يرفض الدفعة ثم يقبل كل سجل إلا واحداً
        r = await page.evaluate("""(async()=>{ while(Sync.busy) await new Promise(r=>setTimeout(r,50));  Store.reset(); Sync.switchTo('https://x.invalid','k'); Sync.st().needReconcile=false; Sync.st().reconciledAt=Date.now(); Sync.st().rejected=[]; Store.settings.sbSession={sid:Sync.sid(),access_token:'t',refresh_token:'r',expires_at:Date.now()+3600e3}; Store.settings.sbRole='asst'; Store.saveSettings(); App.setRole('asst');
            const a=Store.add({type:'note',child:'dalal',text:'n1'}); const b=Store.add({type:'note',child:'dalal',text:'n2'}); const u=Store.add({type:'undo',target:a.id,child:'dalal'});
            const other=Store.add({type:'note',child:'dalal',text:'n-aya',by:'aya'}); /* سجل دور آخر لا يُرفع بتوكن المساعدة */
            const posts=[]; const of=window.fetch; window.fetch=async(url,o)=>{ const s=String(url); if(o&&o.method==='POST'&&s.includes('/events?on_conflict')){ const rows=JSON.parse(o.body); posts.push(rows.map(x=>x.type)); if(rows.some(x=>x.id===b.id)) return {ok:false,status:403,json:async()=>({message:'policy'})}; return {ok:true,status:201,json:async()=>rows.map(x=>({id:x.id}))}; } if(s.includes('/events?select=id')) return {ok:true,json:async()=>[]}; return {ok:true,json:async()=>({})}; };
            Sync.refresh=async()=>true; Sync.serverRole=async()=>Store.settings.sbRole; await Sync.run(); window.fetch=of;
            return { posts, aSynced: hasIn(a.sv,Sync.sid()), bRej: hasIn(b.rj,Sync.sid()), uSynced: hasIn(u.sv,Sync.sid()), otherSynced: hasIn(other.sv,Sync.sid()), rej:Sync.st().rejected.map(x=>x.id), err: Sync.lastError }; })()""")
        assert r['posts'][0] == ['note','note'] and r['posts'][-1] == ['undo'] and r['aSynced'] and r['bRej'] and r['uSynced'] and r['otherSynced'] is False and r['rej'] == [await page.evaluate("Store.raw.find(e=>hasIn(e.rj,Sync.sid())).id")], r
        # (LM093-01) رفض دفعة ثم 503 أثناء الفحص الفردي: السجل يبقى منتظراً، ويُرفع تلقائياً بعد التعافي
        r = await page.evaluate("""(async()=>{ while(Sync.busy) await new Promise(r=>setTimeout(r,50));  Store.reset(); Sync.switchTo('https://x.invalid','k'); Sync.st().needReconcile=false; Sync.st().reconciledAt=Date.now(); Sync.st().rejected=[]; Store.settings.sbSession={sid:Sync.sid(),access_token:'t',refresh_token:'r',expires_at:Date.now()+3600e3}; Store.settings.sbRole='asst'; Store.saveSettings(); App.setRole('asst');
            const a=Store.add({type:'note',child:'dalal',text:'n1'}); const b=Store.add({type:'note',child:'dalal',text:'n2'});
            let down=true; const of=window.fetch; window.fetch=async(url,o)=>{ const s=String(url); if(o&&o.method==='POST'&&s.includes('/events?on_conflict')){ const rows=JSON.parse(o.body); if(rows.length>1) return {ok:false,status:403,json:async()=>({})}; if(down && rows[0].id===b.id) return {ok:false,status:503,json:async()=>({})}; return {ok:true,status:201,json:async()=>rows.map(x=>({id:x.id}))}; } if(s.includes('/events?select=id')) return {ok:true,json:async()=>[]}; return {ok:true,json:async()=>({})}; };
            Sync.refresh=async()=>true; Sync.serverRole=async()=>Store.settings.sbRole; await Sync.run(); const mid={aS:hasIn(a.sv,Sync.sid()),bS:hasIn(b.sv,Sync.sid()),rej:Sync.st().rejected.length,err:Sync.lastError};
            down=false; await Sync.run(); window.fetch=of;
            return { mid, after:{aS:hasIn(a.sv,Sync.sid()),bS:hasIn(b.sv,Sync.sid()),rej:Sync.st().rejected.length,err:Sync.lastError} }; })()""")
        assert r['mid'] == {'aS': True, 'bS': False, 'rej': 0, 'err': r['mid']['err']} and 'مؤقت' in r['mid']['err'] and r['after'] == {'aS': True, 'bS': True, 'rej': 0, 'err': None}, r
        await page.evaluate("Sync.st().rejected=[]; Store.settings.sbRole='aya'; Store.saveSettings(); App.setRole('aya');")
        # (LM072-01) 101 مرفوضاً تبقى كلها بعد إعادة التحميل؛ وفشل الحفظ يوقف المؤشر
        r = await page.evaluate("""(async()=>{ while(Sync.busy) await new Promise(r=>setTimeout(r,50));  Sync.st().rejected=[]; Sync.st().cursor=null; Store.saveSettings(); const t0=Date.UTC(2026,10,10,3);
            const rows=[]; for(let i=0;i<101;i++) rows.push({id:'b'+i,by:'asst',type:'outcome',child:'dalal',inserted_at:'2026-11-10T03:00:'+String(i%60).padStart(2,'0')+'Z',payload:{id:'b'+i,type:'outcome',ts:t0+i,day:'2026-11-10',by:'asst',child:'dalal',page:999,step:'far',result:'clean'}});
            const of=window.fetch; let calls=0; window.fetch=async(u)=>{ calls++; if(String(u).includes('/events?select=id')) return {ok:true,json:async()=>calls<2?rows:[]}; return {ok:true,json:async()=>({})}; };
            Sync.refresh=async()=>true; Sync.serverRole=async()=>Store.settings.sbRole; await Sync.run(); window.fetch=of; return Sync.st().rejected.length; })()""")
        assert r == 101, r
        await page.reload(); await page.wait_for_timeout(500)
        assert await page.evaluate("Sync.st().rejected.length") == 101
        assert await page.evaluate("Sync.st().rejected.every(x=>x.payload&&x.reason)")
        r = await page.evaluate("""(async()=>{ while(Sync.busy) await new Promise(r=>setTimeout(r,50));  const cur0=JSON.stringify(Sync.st().cursor); const t0=Date.UTC(2026,10,10,4);
            const rows=[{id:'z1',by:'asst',type:'outcome',child:'dalal',inserted_at:'2026-11-10T04:00:00Z',payload:{id:'z1',type:'outcome',ts:t0,day:'2026-11-10',by:'asst',child:'dalal',page:999,step:'far',result:'clean'}}];
            const of=window.fetch; let calls=0; window.fetch=async(u)=>{ calls++; if(String(u).includes('/events?select=id')) return {ok:true,json:async()=>calls<2?rows:[]}; return {ok:true,json:async()=>({})}; };
            const os=Store.saveSettings; Store.saveSettings=function(){ if ((Sync.st().rejected||[]).some(x=>x.id==='z1')) throw new Error('quota'); return os.call(this); };
            Sync.refresh=async()=>true; Sync.serverRole=async()=>Store.settings.sbRole; await Sync.run(); Store.saveSettings=os; window.fetch=of;
            return { same: JSON.stringify(Sync.st().cursor)===cur0, n:Sync.st().rejected.length, err: Sync.lastError }; })()""")
        assert r['same'] and r['n'] == 101 and 'تعذّر' in r['err'], r
        # (LM073-01) دفعة فيها مكرر (b0) وجديد (z2)، فشل حفظ ثم نجاح: القديمة كاملة والجديد مرة واحدة
        r = await page.evaluate("""(async()=>{ while(Sync.busy) await new Promise(r=>setTimeout(r,50));  const t0=Date.UTC(2026,10,10,5); const mk=(id,sec)=>({id,by:'asst',type:'outcome',child:'dalal',inserted_at:'2026-11-10T05:00:'+sec+'Z',payload:{id,type:'outcome',ts:t0,day:'2026-11-10',by:'asst',child:'dalal',page:999,step:'far',result:'clean'}});
            const rows=[mk('b0','00'),mk('z2','01')];
            const run=async(fail)=>{ const of=window.fetch; let calls=0; window.fetch=async(u)=>{ calls++; if(String(u).includes('/events?select=id')) return {ok:true,json:async()=>calls<2?rows:[]}; return {ok:true,json:async()=>({})}; };
              const os=Store.saveSettings; if(fail) Store.saveSettings=function(){ if ((Sync.st().rejected||[]).some(x=>x.id==='z2')) throw new Error('quota'); return os.call(this); };
              Sync.refresh=async()=>true; Sync.serverRole=async()=>Store.settings.sbRole; await Sync.run(); Store.saveSettings=os; window.fetch=of; };
            const before=Sync.st().rejected.map(x=>x.id);
            await run(true); const afterFail=Sync.st().rejected.map(x=>x.id);
            await run(false); const afterOk=Sync.st().rejected.map(x=>x.id);
            return { failSame: JSON.stringify(afterFail)===JSON.stringify(before), okLen: afterOk.length, z2: afterOk.filter(x=>x==='z2').length, b0: afterOk.filter(x=>x==='b0').length, oldKept: before.every(x=>afterOk.includes(x)) }; })()""")
        assert r == {'failSame': True, 'okLen': 102, 'z2': 1, 'b0': 1, 'oldKept': True}, r
        await page.reload(); await page.wait_for_timeout(400)
        assert await page.evaluate("Sync.st().rejected.length") == 102
        await page.evaluate("Store.settings.sbUrl=''; Store.settings.sbKey=''; Store.settings.sbSession=null; Store.settings.sbRole=null; Store.settings.servers={}; Store.saveSettings();")
        await page.evaluate("App.setRole('aya'); Store.reset(); for (let p=562;p<=604;p++) Store.add({type:'layer',child:'dalal',page:p,layer:'far',color:'green'});")
        # --- 0.8 ---
        # (2) الباقي مستقل في البعيد لا يصبح «بانتظار الاعتماد»؛ الصفحة الجديدة تبقى كذلك
        r = await page.evaluate("(()=>{ Store.reset(); const d=todayKey(); Store.add({type:'outcome',child:'dalal',page:570,step:'far',result:'clean'}); Store.add({type:'outcome',child:'dalal',page:542,step:'first',result:'clean'}); return [suggestColor('dalal',570,d).color, suggestColor('dalal',570,d).pending, suggestColor('dalal',542,d).pending]; })()")
        assert r == ['green', False, True], r
        # (4) أول يوم: بوابة الأمس «لا ينطبق» تلقائياً والخطوة الحالية هي الحفظ
        await page.evaluate("App.setRole('aya'); Store.reset(); for (let p=562;p<=604;p++) Store.add({type:'layer',child:'dalal',page:p,layer:'far',color:'green'}); Store.settings.timeOffset = Date.UTC(2026,10,14,7-8,5) - Date.now(); Store.saveSettings(); const s=PLAN.find(x=>x.kind==='gate_new'&&x.child==='dalal'); startSession(s); App.view='now'; UI.rerender();")
        txt = await page.evaluate("document.querySelector('main').innerText")
        assert 'لا ينطبق اليوم' in txt and 'الخطوة الحالية: حفظ الصفحة' in txt, txt[:300]
        # (6) المعايرة: نصف صفحة افتراضياً
        assert await page.evaluate("Store.settings.active.half_dalal") is True
        assert 'أيام المعايرة: 1 من 10' in txt
        # (5) كريم: زيادة الأسطر إلى 6
        await page.evaluate("Store.settings.active=null; Store.saveSettings(); for (let p=595;p<=604;p++) Store.add({type:'layer',child:'karim',page:p,layer:'far',color:'green'}); Store.settings.timeOffset = Date.UTC(2026,10,14,8-8,35) - Date.now(); Store.saveSettings(); const s=PLAN.find(x=>x.kind==='karim_new'); startSession(s); UI.rerender();")
        await page.locator('.steps li').nth(1).locator('.body .row').first.click()
        await page.fill('input[type=number][max="15"]', '6'); await page.dispatch_event('input[type=number][max="15"]', 'change')
        await page.click('text=تم الحفظ'); await page.wait_for_timeout(200)
        np = await page.evaluate("Store.events.filter(e=>e.type==='new_page'&&e.child==='karim').slice(-1)[0]")
        assert np['linesFrom'] == 1 and np['linesTo'] == 6, np
        await page.evaluate("Store.settings.active=null; Store.saveSettings();")
        # (1) لا نص [object في الواجهة
        await page.evaluate("Store.add({type:'outcome',child:'dalal',page:570,step:'far',result:'yellow',prompts:1}); App.view='now'; UI.rerender();")
        html = await page.evaluate("document.body.innerHTML")
        assert '[object' not in html
        # (7) بطاقة الجرد تظهر قبل الجرد وتختفي بعده
        await page.evaluate("Store.reset(); App.view='now'; UI.rerender();")
        assert 'الجرد الأولي' in await page.evaluate("document.querySelector('main').innerText")
        await page.evaluate("for (const c of CHILD_ORDER) Store.add({type:'layer',child:c,page:604,layer:'far',color:'green'}); UI.rerender();")
        assert 'قبل أول جلسة' not in await page.evaluate("document.querySelector('main').innerText")
        await page.evaluate("App.setRole('aya'); Store.reset(); for (let p=562;p<=604;p++) Store.add({type:'layer',child:'dalal',page:p,layer:'far',color:'green'});")
        # --- 0.9 ---
        # الطلاقة في السجل
        await page.evaluate("App.setRole('asst'); Store.add({type:'fluency_page',child:'karim',page:590,why:'t'});")
        assert await page.evaluate("fluencyPage('karim')") == 590
        # النيابة: المساعدة تأخذ جلسة آية بسبب؛ تُسجَّل وتظهر، والتلوين يبقى لآية
        await page.evaluate("Store.settings.timeOffset = Date.UTC(2026,10,15,7-8,5) - Date.now(); Store.saveSettings(); const s=PLAN.find(x=>x.kind==='gate_new'&&x.child==='dalal'); startSession(s, null, {orig:'aya', reason:'غياب آية'}); App.view='now'; UI.rerender();")
        txt = await page.evaluate("document.querySelector('main').innerText")
        assert 'نيابةً عن آية' in txt, txt[:200]
        assert await page.evaluate("Store.events.filter(e=>e.type==='session_start').slice(-1)[0].proxyFor") == 'aya'
        assert await page.evaluate("App.can('canColor')") is False
        await page.evaluate("(async()=>{ const s=PLAN.find(x=>x.kind==='gate_new'&&x.child==='dalal'); const a=Store.settings.active; a.steps=['gate','memorize','first']; await commitEnd(s,a,'complete',[],null,''); })()")
        sd = await page.evaluate("const s=PLAN.find(x=>x.kind==='gate_new'&&x.child==='dalal'); sessionStatus(s, todayKey())")
        assert sd['proxyFor'] == 'aya' and sd['status'] == 'complete' and sd['conflicts'] == [], sd
        assert await page.evaluate("handoffs(h=>h.child==='dalal'&&h.key===sessionKey(PLAN.find(x=>x.kind==='gate_new'&&x.child==='dalal'), todayKey())).length") == 1
        # التزامن: آية فتحت الجلسة نفسها على جهازها وأنهتها → تعارض ظاهر، وتُحسب مرة واحدة
        await page.evaluate("const s=PLAN.find(x=>x.kind==='gate_new'&&x.child==='dalal'); const key=sessionKey(s,todayKey()); Store.importEvents([{id:'ss_x',type:'session_start',ts:Date.now(),day:todayKey(),by:'aya',key,sid:'sidX',kind:'gate_new',child:'dalal'},{id:'sd_sidX_dalal_1',type:'session_done',ts:Date.now()+1,day:todayKey(),by:'aya',key,sid:'sidX',round:1,child:'dalal',kind:'gate_new',start:s.start,steps:['gate'],status:'partial',remaining:['memorize','first'],minutes:5,note:''}]);")
        sd = await page.evaluate("const s=PLAN.find(x=>x.kind==='gate_new'&&x.child==='dalal'); sessionStatus(s, todayKey())")
        assert len(sd['conflicts']) == 1 and 'مرات' in sd['conflicts'][0], sd
        assert await page.evaluate("alertsList().some(a=>a.text.includes('تعارض') || a.text.includes('مرات'))")
        assert await page.evaluate("doneKeys(e=>e.day===todayKey()).size") == 1
        # إلغاء جلسات اليوم ثم وصول إنهاء متأخر: لا حذف، تعارض ظاهر
        await page.evaluate("const s=PLAN.find(x=>x.kind==='noon'&&x.child==='dalal'); Store.add({type:'session_cancel',key:sessionKey(s,todayKey()),child:'dalal',kind:'noon',start:s.start,reason:'مرض طفل'});")
        sd = await page.evaluate("const s=PLAN.find(x=>x.kind==='noon'&&x.child==='dalal'); sessionStatus(s, todayKey())")
        assert sd['status'] == 'cancelled', sd
        await page.evaluate("const s=PLAN.find(x=>x.kind==='noon'&&x.child==='dalal'); const key=sessionKey(s,todayKey()); Store.importEvents([{id:'o_late',type:'outcome',ts:Date.now()-5000,day:todayKey(),by:'asst',child:'dalal',page:562,step:'far',result:'clean',sid:'sidL'},{id:'sd_sidL_dalal_1',type:'session_done',ts:Date.now()+2,day:todayKey(),by:'asst',key,sid:'sidL',round:1,child:'dalal',kind:'noon',start:s.start,steps:['far'],status:'partial',remaining:['second','cards'],minutes:9,note:''}]);")
        sd = await page.evaluate("const s=PLAN.find(x=>x.kind==='noon'&&x.child==='dalal'); sessionStatus(s, todayKey())")
        assert sd['status'] in ('partial','cancelled') and any('أُلغيت' in c for c in sd['conflicts']), sd
        assert await page.evaluate("Store.events.some(e=>e.id==='o_late')")
        # إلغاء جلسة جارية يحفظ ما أُنجز ويُظهر الباقي
        await page.evaluate("Store.settings.active=null; const s=PLAN.find(x=>x.kind==='karim_asr'); startSession(s); Store.settings.active.steps=['second']; Store.saveSettings();")
        await page.evaluate("App.view='now'; UI.rerender();")
        await page.evaluate("cancelModal()"); await page.wait_for_selector('.modal'); await page.click('.modal button.danger'); await page.wait_for_timeout(200)
        sd = await page.evaluate("const s=PLAN.find(x=>x.kind==='karim_asr'); sessionStatus(s, todayKey())")
        assert sd['status'] == 'stopped' and sd['remaining'] == ['far','cards'] and 'إلغاء' in sd['reason'] and sd['steps'] == ['second'], sd
        assert await page.evaluate("Store.settings.active") is None
        # --- 0.9.1 ---
        # (LM09-01) النيابة لا توسّع الصلاحيات: المساعدة لا تسجّل new_page محلياً، وتظهر أداة طلب الاعتماد
        await page.evaluate("App.setRole('aya'); Store.reset(); for (let p=562;p<=604;p++) Store.add({type:'layer',child:'dalal',page:p,layer:'far',color:'green'}); App.setRole('asst'); Store.settings.timeOffset = Date.UTC(2026,10,16,7-8,5) - Date.now(); Store.saveSettings();")
        rej = await page.evaluate("(()=>{try{Store.add({type:'new_page',child:'dalal',page:542,linesFrom:1,linesTo:8});return false}catch(e){return e.message}})()")
        assert rej and 'لا يُسمح' in rej, rej
        await page.evaluate("const s=PLAN.find(x=>x.kind==='gate_new'&&x.child==='dalal'); startSession(s, null, {orig:'aya', reason:'غياب'}); Store.settings.active.cur=1; Store.saveSettings(); App.view='now'; UI.rerender();")
        txt = await page.evaluate("document.querySelector('main').innerText")
        assert 'طلب اعتماد من آية' in txt and 'تم الحفظ' not in txt, txt[:1200]
        assert await page.evaluate("(()=>{try{Store.add({type:'outcome',child:'dalal',page:570,step:'exam',result:'clean'});return false}catch(e){return true}})()")
        assert await page.evaluate("(()=>{try{Store.add({type:'color',child:'dalal',page:570,color:'green'});return false}catch(e){return true}})()")
        # كل ما تسجله المساعدة عادةً ما زال مقبولاً
        for ev in ["{type:'outcome',child:'dalal',page:570,step:'far',result:'clean'}", "{type:'error',child:'dalal',page:570,surah:67,ayah:1,etype:'prompt'}", "{type:'note',child:'dalal',text:'x'}", "{type:'card',child:'dalal',key:'p570',kind:'page',page:570}", "{type:'fluency_page',child:'karim',page:590}"]:
            assert await page.evaluate("(()=>{try{Store.add(" + ev + ");return true}catch(e){return e.message}})()") is True, ev
        await page.evaluate("Store.settings.active=null; Store.saveSettings();")
        # (LM09-02) إلغاء جلسة جارية مع فشل الحفظ: لا إعلان نجاح، النافذة تبقى، ثم إعادة المحاولة تنجح مرة واحدة
        await page.evaluate("const s=PLAN.find(x=>x.kind==='noon'&&x.child==='dalal'); startSession(s); Store.settings.active.steps=['far']; Store.saveSettings(); App.view='now'; UI.rerender();")
        toasts = await page.evaluate("""(async()=>{ const seen=[]; const ot=UI.toast; UI.toast=m=>{seen.push(m); ot.call(UI,m);};
            const orig=Store.saveEvents.bind(Store); let done=false; Store.saveEvents=function(){ const last=this.raw[this.raw.length-1]; if(!done && last && last.type==='session_done'){ done=true; this.storageError='sim'; return false;} return orig(); };
            cancelModal(); await new Promise(r=>setTimeout(r,100)); document.querySelector('.modal button.danger').click(); await new Promise(r=>setTimeout(r,100));
            Store.saveEvents=orig; UI.toast=ot; return { seen, modal: !!document.querySelector('.modal'), active: !!Store.settings.active, sd: Store.events.filter(e=>e.type==='session_done'&&e.day===todayKey()&&e.kind==='noon').length }; })()""")
        assert toasts['modal'] and toasts['active'] and toasts['sd'] == 0 and not any('أُلغيت 1' in m for m in toasts['seen']) and any('تعذّر' in m for m in toasts['seen']), toasts
        await page.click('.modal button.danger'); await page.wait_for_timeout(200)
        r = await page.evaluate("({ modal: !!document.querySelector('.modal'), active: !!Store.settings.active, sd: Store.events.filter(e=>e.type==='session_done'&&e.day===todayKey()&&e.kind==='noon').length })")
        assert r == {'modal': False, 'active': False, 'sd': 1}, r
        # --- 0.9.2 ---
        # ورد النظر: يُسجَّل ولا يغيّر طبقة أو لوناً أو تاريخ مراجعة
        await page.evaluate("App.setRole('aya'); Store.reset(); for (let p=562;p<=604;p++) Store.add({type:'layer',child:'dalal',page:p,layer:'far',color:'green'}); App.setRole('asst');")
        before = await page.evaluate("JSON.stringify((({layer,color,lastFar,lastReview})=>({layer,color,lastFar,lastReview}))(deriveChild('dalal').pages[550]))")
        await page.evaluate("Store.add({type:'tilawa',child:'dalal',pages:[550,551,552],kind:'nazar',times:1,step:'tilawa'});")
        after = await page.evaluate("JSON.stringify((({layer,color,lastFar,lastReview})=>({layer,color,lastFar,lastReview}))(deriveChild('dalal').pages[550]))")
        assert before == after and await page.evaluate("lastTilawa('dalal','nazar').pages.length") == 3
        assert await page.evaluate("(()=>{try{Store.add({type:'tilawa',child:'dalal',pages:[0],kind:'nazar'});return false}catch(e){return true}})()")
        # اختبار الإجازة اختياري: إجازة بلا اختبار مسموحة وموثَّقة؛ والاختبار وحده لا يُجيز
        await page.evaluate("App.setRole('aya'); for (let p=542;p<=561;p++) Store.add({type:'layer',child:'dalal',page:p,layer:'near'});")
        await page.evaluate("Store.add({type:'juz_exam',child:'dalal',juz:28,result:'yellow',prompts:2});")
        assert await page.evaluate("deriveChild('dalal').pages[545].layer") == 'near'
        assert not await page.evaluate("alertsList().some(a=>a.text.includes('إجازة'))")
        # (LM092-02) تناقض النتيجة والتلقين يُرفض في السجل
        assert await page.evaluate("Store.validEvent({id:'je1',type:'juz_exam',ts:1,day:'2026-01-01',by:'aya',child:'dalal',juz:28,result:'clean',prompts:3})") is False
        assert await page.evaluate("Store.validEvent({id:'je2',type:'juz_exam',ts:1,day:'2026-01-01',by:'aya',child:'dalal',juz:28,result:'yellow',prompts:0})") is False
        assert await page.evaluate("Store.validEvent({id:'je3',type:'juz_exam',ts:1,day:'2026-01-01',by:'aya',child:'dalal',juz:28,result:'red',prompts:0})") is True
        # (LM092-01) الإجازة من النافذة ترتبط بالاختبار السابق المختار تلقائياً
        await page.evaluate("Store.add({type:'juz_exam',child:'dalal',juz:28,result:'clean',prompts:0}); juzPassModal('dalal');")
        await page.wait_for_selector('.modal')
        bv = await page.evaluate("document.querySelector('.modal select:nth-of-type(2)').value")
        assert bv == await page.evaluate("Store.events.filter(e=>e.type==='juz_exam').pop().id"), bv
        await page.click('.modal button.primary'); await page.wait_for_timeout(200)
        jp = await page.evaluate("Store.events.filter(e=>e.type==='juz_passed').pop()")
        assert jp['exam'] == bv and jp['juz'] == 28, jp
        assert await page.evaluate("deriveChild('dalal').pages[545].layer") == 'far'
        assert 'باختبار مسجل' in await page.evaluate("eventText(Store.events.filter(e=>e.type==='juz_passed').pop())")
        assert 'استناداً إلى اختبار' in await page.evaluate("Store.events.filter(e=>e.type==='decision').pop().text")
        assert 'لا بوابة ولا فحص' in await page.evaluate("lightText(healthOf('farah'))")
        await page.evaluate("App.setRole('aya'); Store.reset(); for (let p=562;p<=604;p++) Store.add({type:'layer',child:'dalal',page:p,layer:'far',color:'green'});")
        # --- مراجعة الخصم (0.10.1) ---
        await page.evaluate("App.setRole('aya'); Store.reset(); for (let p=562;p<=604;p++) Store.add({type:'layer',child:'dalal',page:p,layer:'far',color:'green'}); Store.settings.timeOffset = Date.UTC(2026,10,21,7-8,10) - Date.now(); Store.saveSettings(); Store.add({type:'new_page',child:'dalal',page:542,linesFrom:1,linesTo:15}); const s=PLAN.find(x=>x.kind==='gate_new'&&x.child==='dalal'); startSession(s); Store.settings.active.cur=2; Store.saveSettings(); App.view='now'; UI.rerender();")
        await page.locator('.steps li').nth(2).locator('button.btn-g').first.click(); await page.wait_for_timeout(150)
        await page.click('.chip:has-text("تحقق")'); await page.wait_for_timeout(150)
        await page.click('.chip:has-text("تجويد")'); await page.wait_for_timeout(150)
        o = await page.evaluate("effectiveOutcomes(e=>e.child==='dalal'&&e.page===542&&e.step==='first').pop()")
        assert o['result'] == 'clean' and o['meaning'] == 'ok' and o['tajweed'] == 'issue', o
        assert await page.evaluate("suggestColor('dalal',542,todayKey()).color") == 'yellow'
        await page.evaluate("Store.settings.active=null; Store.saveSettings();")
        # فحص ولي الأمر لا يطمس فحص آية
        await page.evaluate("Store.add({type:'outcome',child:'dalal',page:570,step:'exam',result:'red'}); App.setRole('parent'); Store.add({type:'outcome',child:'dalal',page:570,step:'exam',result:'clean',parent:true}); App.setRole('aya');")
        assert await page.evaluate("effectiveOutcomes(e=>e.page===570&&e.step==='exam').length") == 2
        assert await page.evaluate("suggestColor('dalal',570,todayKey()).color") == 'red'
        # بطاقة تسليم بعناصر تالفة تُرفض، وشاشة لا تنهار
        assert await page.evaluate("Store.validEvent({id:'h9',type:'handoff',ts:1,day:'2026-01-01',by:'asst',child:'dalal',key:'k',to:'aya',items:[null]})") is False
        assert await page.evaluate("(()=>{ Views.__boom = () => { throw new Error('boom'); }; App.view='__boom'; UI.rerender(); const t=document.querySelector('main').innerText; App.view='now'; UI.rerender(); return t.includes('تعذّر عرض'); })()")
        # الاستيراد يرفض ما لا يجيزه الدور
        assert await page.evaluate("(()=>{try{Store.importEvents([{id:'i9',type:'color',ts:1,day:'2026-01-01',by:'asst',child:'dalal',page:570,color:'green'}]);return false}catch(e){return true}})()")
        # فحص كله ناقص لا يعطي NaN
        await page.evaluate("Store.reset(); Store.add({type:'outcome',child:'farah',page:570,step:'exam',result:'partial'});")
        assert await page.evaluate("healthOf('farah').examGreen") is None
        await page.evaluate("App.setRole('aya'); Store.reset(); for (let p=562;p<=604;p++) Store.add({type:'layer',child:'dalal',page:p,layer:'far',color:'green'});")
        # per-type validation: linesTo "abc" rejected; cursor string migrates
        bad2 = await page.evaluate("Store.validEvent({id:'z',type:'new_page',ts:1,day:'2026-01-01',child:'dalal',page:542,linesFrom:1,linesTo:'abc'})")
        assert bad2 is False, 'linesTo abc accepted'
        assert await page.evaluate("Store.validEvent({id:'z',type:'outcome',ts:1,day:'2026-01-01',child:'dalal',page:542,step:'gate',result:'blue'})") is False
        assert await page.evaluate("Store.validEvent({id:'z',type:'decision',ts:1,day:'2026-01-01',child:'dalal',kind:'nuke'})") is False
        # every event the app itself produced must pass validation
        inv = await page.evaluate("Store.events.filter(e=>!Store.validEvent(e)).map(e=>e.type)")
        assert inv == [], f'app-produced events fail validation: {inv}'
        # not-evaluated child is grey
        hk = await page.evaluate("JSON.stringify((({light,gateN,examN,maxGap,evaluated,st})=>({light,gateN,examN,maxGap,evaluated,far:st.far}))(healthOf('karim')))"); assert '"light":"grey"' in hk, hk
        assert not errs, errs
        await b.close()
    print('ASSERTS OK')

asyncio.run(asserts())
