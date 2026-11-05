import asyncio, pathlib, json
from playwright.async_api import async_playwright
HTML=pathlib.Path('dist/index.html').resolve(); OUT=pathlib.Path('review'); OUT.mkdir(exist_ok=True)
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(executable_path='/usr/bin/google-chrome',args=['--no-sandbox'])
        ctx=await b.new_context(viewport={'width':390,'height':844},locale='ar',timezone_id='Africa/Cairo')
        pg=await ctx.new_page(); errs=[]; pg.on('pageerror',lambda e:errs.append('PAGE:'+str(e))); pg.on('console',lambda m: errs.append('CON:'+m.text) if m.type=='error' else None)
        await pg.goto(HTML.as_uri()); await pg.screenshot(path=OUT/'r01_login.png',full_page=True)
        async def login(i,pin):
            await pg.evaluate("App.role&&App.logout()"); await pg.click(f'.roles button:nth-child({i})'); await pg.fill('input[type=password]',pin); await pg.click('button.primary')
        async def t(y,m,d,h,mi): await pg.evaluate(f"Store.settings.timeOffset = Date.UTC({y},{m-1},{d},{h}-8,{mi}) - Date.now(); Store.saveSettings(); UI.rerender();")
        async def nav(i): await pg.click(f'nav.bottom button:nth-child({i})'); await pg.wait_for_timeout(150)
        async def shot(n): await pg.screenshot(path=OUT/f'{n}.png',full_page=True)
        await login(1,'1111')
        # empty state: first day, no inventory
        await t(2026,11,7,7,5); await shot('r02_aya_now_empty')
        await nav(3); await shot('r03_children_empty')
        await nav(5); await shot('r04_settings_aya')
        # inventory
        await pg.evaluate("for (const c of ['dalal','farah']) for (let p=562;p<=604;p++) Store.add({type:'layer',child:c,page:p,layer:'far',color:'green'}); for (let p=595;p<=604;p++) Store.add({type:'layer',child:'karim',page:p,layer:'far',color:'green'}); UI.rerender();")
        await nav(1); await shot('r05_aya_now_day1')
        # start dalal gate_new
        await pg.click('text=ابدئي الجلسة'); await pg.wait_for_selector('text=جلسة جارية'); await shot('r06_session_gate_day1')
        # open memorize, half page
        await pg.locator('.steps li').nth(1).locator('.body .row').first.click(); await shot('r07_memorize_step')
        await pg.click('text=بدء المؤقت'); await pg.check('input[type=checkbox]'); await pg.click('text=تم الحفظ'); await pg.wait_for_timeout(200)
        await pg.locator('.steps li').nth(2).locator('.body .row').first.click(); await pg.locator('.steps li').nth(2).locator('button.btn-y').first.click(); await pg.wait_for_timeout(200); await shot('r08_first_outcome_detail')
        await pg.click('button:has-text("إنهاء الجلسة")'); await pg.wait_for_selector('.modal'); await shot('r09_end_modal'); await pg.click('.modal button.primary'); await pg.wait_for_timeout(300)
        # farah near_review is asst; aya next: farah gate 7:50
        await t(2026,11,7,7,55); await shot('r10_aya_now_755')
        # karim 8:30
        await t(2026,11,7,8,32); await pg.click('text=ابدئي الجلسة'); await pg.wait_for_selector('text=جلسة جارية'); await shot('r11_karim_new')
        await pg.locator('.steps li').nth(1).locator('.body .row').first.click(); await pg.click('text=بدء المؤقت'); await pg.click('text=تم الحفظ'); await pg.wait_for_timeout(200)
        await pg.locator('.steps li').nth(2).locator('.body .row').first.click(); await shot('r12_karim_first'); await pg.locator('.steps li').nth(2).locator('button.btn-g').first.click(); await pg.wait_for_timeout(200)
        await pg.click('button:has-text("إنهاء الجلسة")'); await pg.wait_for_selector('.modal'); await pg.click('.modal button.primary'); await pg.wait_for_timeout(200)
        # asst day1 noon + fluency
        await login(2,'2222'); await t(2026,11,7,12,12); await shot('r13_asst_now_fluency'); await pg.click('text=ابدئي الجلسة'); await pg.wait_for_selector('text=جلسة جارية'); await shot('r14_fluency_session')
        await pg.click('button:has-text("إنهاء الجلسة")'); await pg.wait_for_selector('.modal'); await pg.click('.modal button.primary'); await pg.wait_for_timeout(200)
        await t(2026,11,7,12,52); await pg.click('text=ابدئي الجلسة'); await pg.wait_for_selector('text=جلسة جارية'); await shot('r15_noon_dalal')
        await pg.locator('.steps li').nth(1).locator('.body .row').first.click(); await shot('r16_noon_far_step')
        await pg.click('button:has-text("إنهاء الجلسة")'); await pg.wait_for_selector('.modal'); await pg.click('.modal button.primary'); await pg.wait_for_timeout(200)
        await t(2026,11,7,15,22); await pg.click('text=ابدئي الجلسة'); await pg.wait_for_selector('text=جلسة جارية'); await shot('r17_karim_asr')
        await pg.click('button:has-text("إنهاء الجلسة")'); await pg.wait_for_selector('.modal'); await pg.click('.modal button.primary'); await pg.wait_for_timeout(200)
        # aya evening: circle, third, karim evening, prep
        await login(1,'1111'); await t(2026,11,7,18,2); await pg.click('text=ابدئي الجلسة'); await pg.wait_for_selector('text=جلسة جارية'); await shot('r18_circle')
        await pg.click('button:has-text("إنهاء الجلسة")'); await pg.wait_for_selector('.modal'); await pg.click('.modal button.primary'); await pg.wait_for_timeout(200)
        await t(2026,11,7,18,52); await pg.click('text=ابدئي الجلسة'); await pg.wait_for_selector('text=جلسة جارية'); await shot('r19_prep_color')
        await pg.click('button:has-text("إنهاء الجلسة")'); await pg.wait_for_selector('.modal'); await pg.click('.modal button.primary'); await pg.wait_for_timeout(200)
        await nav(2); await shot('r20_today_end'); await nav(3); await shot('r21_children_summary')
        await pg.click('text=خريطة المصحف'); await shot('r22_map')
        for tab in ['القائمة الصفراء','المتشابهات','البطاقات','السجل']:
            try: await pg.click(f'text={tab}'); await pg.wait_for_timeout(150); await shot('r23_tab_'+tab)
            except Exception as e: errs.append('TAB '+tab+' '+str(e)[:80])
        await nav(4); await shot('r24_logs'); await pg.evaluate("App.view='thursday'; UI.rerender();"); await shot('r25_thursday')
        # thursday as aya
        await t(2026,11,12,7,2); await nav(1); await shot('r26_thu_now'); await pg.click('text=ابدئي الجلسة'); await pg.wait_for_selector('text=جلسة جارية'); await shot('r27_thu_recite')
        await pg.click('button:has-text("إنهاء الجلسة")'); await pg.wait_for_selector('.modal'); await pg.click('.modal button.primary'); await pg.wait_for_timeout(200)
        # parent
        await login(3,'3333'); await shot('r28_parent_dash'); await nav(2); await shot('r29_parent_children'); await nav(4); await shot('r30_parent_reports'); await nav(5); await shot('r31_parent_settings')
        # friday
        await login(1,'1111'); await t(2026,11,13,9,0); await nav(1); await shot('r32_friday')
        st = await pg.evaluate("JSON.stringify({dalal:(({nextNew,nextLines,near,far,todayFar,quota})=>({nextNew,nextLines,near,farN:far.length,todayFar,quota}))(deriveChild('dalal')), karim:(({nextNew,nextLines,near,far,todayFar,quota})=>({nextNew,nextLines,near,farN:far.length,todayFar,quota}))(deriveChild('karim'))})")
        print(st); print('ERRS', json.dumps(errs,ensure_ascii=False))
        await b.close()
asyncio.run(main())
