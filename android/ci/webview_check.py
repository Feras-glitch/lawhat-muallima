"""فحص التطبيق على محاكي أندرويد عبر بروتوكول DevTools لـ WebView (بناء الاختبار وحده يفعّله).
يتحقق أن الواجهة تعمل داخل التطبيق: الأصل الثابت، قاعدة الجهاز، الجسر، بقاء البيانات بعد إعادة التحميل وبعد إيقاف التطبيق،
زر الرجوع، واختيار الملفات. يكتب النتائج في JSON ويفشل عند أي خطأ."""
import json, subprocess, sys, time, urllib.request, asyncio
import websockets

PKG, ACT = sys.argv[1], sys.argv[2]
OUT = sys.argv[3]
results = {}


def sh(*a, check=True):
    return subprocess.run(['adb', *a], check=check, capture_output=True, text=True).stdout


def launch():
    sh('shell', 'am', 'start', '-W', '-n', f'{PKG}/{ACT}')


def connect_url():
    for _ in range(60):
        socks = [l.split('@')[-1].strip() for l in sh('shell', 'cat', '/proc/net/unix').splitlines() if 'webview_devtools_remote' in l]
        if socks:
            sh('forward', '--remove-all', check=False)
            sh('forward', 'tcp:9222', 'localabstract:' + socks[-1])
            try:
                pages = json.load(urllib.request.urlopen('http://127.0.0.1:9222/json', timeout=5))
                pages = [p for p in pages if 'appassets.androidplatform.net' in p.get('url', '')]
                if pages:
                    return pages[0]['webSocketDebuggerUrl']
            except Exception:
                pass
        time.sleep(1)
    raise SystemExit('لم يُعثر على WebView التطبيق')


class Page:
    def __init__(self, ws): self.ws, self.n = ws, 0

    async def ev(self, expr):
        self.n += 1
        await self.ws.send(json.dumps({'id': self.n, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'awaitPromise': True, 'returnByValue': True, 'userGesture': True}}))
        while True:
            m = json.loads(await self.ws.recv())
            if m.get('id') == self.n:
                r = m.get('result', {})
                if 'exceptionDetails' in r:
                    raise RuntimeError(json.dumps(r['exceptionDetails'], ensure_ascii=False)[:800])
                return r.get('result', {}).get('value')


async def session(fn):
    url = connect_url()
    async with websockets.connect(url, max_size=None) as ws:
        p = Page(ws)
        for _ in range(60):
            if await p.ev("!!(window.Store && Store.raw && window.UI)"):
                break
            await asyncio.sleep(0.5)
        return await fn(p)


def shot(name):
    time.sleep(1.2)
    subprocess.run(['adb', 'exec-out', 'screencap', '-p'], stdout=open(OUT + '-' + name + '.png', 'wb'))


def ok(name, cond, data):
    results[name] = {'ok': bool(cond), 'data': data}
    print(('PASS ' if cond else 'FAIL ') + name, json.dumps(data, ensure_ascii=False)[:300])


async def main():
    launch(); time.sleep(4)

    async def first(p):
        info = await p.ev("({ origin: location.origin, inApp: AppShell.inApp(), preview: AppShell.preview(), idb: Store.idbOk, ver: BUILD.version, app: AppShell.version(), sw: innerWidth, sh: innerHeight, dpr: devicePixelRatio, persist: Persist.text().slice(0, 40) })")
        ok('الواجهة داخل التطبيق: أصل https ثابت، قاعدة الجهاز، الجسر', info['origin'] == 'https://appassets.androidplatform.net' and info['inApp'] and info['idb'], info)
        await p.ev("(async () => { App.setRole('aya'); Store.add({ id: 'apk-probe', type: 'note', child: 'dalal', text: 'فحص المحاكي' }); await Store.durable(); App.view = 'logs'; UI.rerender(); return true; })()")
        n = await p.ev("Store.raw.filter(e => e.id === 'apk-probe').length")
        ok('تسجيل ملاحظة وحفظها', n == 1, n)
        return info
    info = await session(first)

    async def reload(p):
        await p.ev("(setTimeout(() => location.reload(), 200), true)")
    await session(reload); time.sleep(3)

    async def after_reload(p):
        return await p.ev("Store.raw.filter(e => e.id === 'apk-probe').length")
    n = await session(after_reload)
    ok('بعد إعادة تحميل الصفحة: الملاحظة باقية', n == 1, n)

    sh('shell', 'am', 'force-stop', PKG); time.sleep(2); launch(); time.sleep(4)
    n = await session(after_reload)
    ok('بعد إيقاف التطبيق وتشغيله: الملاحظة باقية (قاعدة الجهاز دائمة)', n == 1, n)

    async def back_modal(p):
        await p.ev("(() => { App.setRole('aya'); App.view = 'logs'; UI.rerender(); UI.confirm('اختبار الرجوع', () => {}); return true; })()")
        return True
    await session(back_modal)
    sh('shell', 'input', 'keyevent', 'KEYCODE_BACK'); time.sleep(1.5)

    async def after_back(p):
        return await p.ev("({ modal: !!document.querySelector('.modal'), view: App.view })")
    r = await session(after_back)
    ok('زر الرجوع يغلق النافذة المفتوحة', r['modal'] is False and r['view'] == 'logs', r)
    sh('shell', 'input', 'keyevent', 'KEYCODE_BACK'); time.sleep(1.5)
    r = await session(after_back)
    ok('الرجوع التالي يعود إلى الشاشة الرئيسية لا يخرج', r['view'] == 'now', r)
    shot('now')

    async def chooser(p):
        await p.ev("(() => { App.setRole('parent'); App.view = 'settings'; UI.rerender(); const i = document.querySelector('input[type=file]'); i.click(); return true; })()")
        return True
    await session(chooser); time.sleep(3)
    acts = sh('shell', 'dumpsys', 'activity', 'activities', check=False)
    top = [l.strip() for l in acts.splitlines() if 'ResumedActivity' in l][:3]
    ok('اختيار ملف للاستيراد يفتح نافذة ملفات النظام', any(x in ' '.join(top).lower() for x in ('documentsui', 'resolveractivity', 'chooseractivity', 'intentresolver')), top)
    shot('chooser')
    sh('shell', 'input', 'keyevent', 'KEYCODE_BACK'); time.sleep(1.5)

    async def chooser_closed(p):
        return await p.ev("({ ok: !!(window.Store && Store.raw), errors: UI.errors.length })")
    r = await session(chooser_closed)
    ok('إغلاق نافذة الملفات دون اختيار يعيد التطبيق سليماً', r['ok'] and r['errors'] == 0, r)

    async def settings(p):
        await p.ev("(() => { App.setRole('parent'); App.view = 'settings'; UI.rerender(); scrollTo(0, document.body.scrollHeight); return true; })()")
        return await p.ev("document.querySelector('main').innerText.includes('تطبيق أندرويد')")
    r = await session(settings)
    ok('الإعدادات تعرض بطاقة «تطبيق أندرويد»', r, r)
    shot('settings')

    # الدوران: الصفحة لا تُعاد (الحالة في الذاكرة باقية)
    async def mark(p):
        return await p.ev("(window.__mark = Math.random(), window.__mark)")
    m = await session(mark)

    async def get_mark(p):
        return await p.ev("({ m: window.__mark, w: innerWidth, h: innerHeight })")
    before = await session(get_mark)
    sh('shell', 'settings', 'put', 'system', 'accelerometer_rotation', '0')
    sh('shell', 'settings', 'put', 'system', 'user_rotation', '1'); time.sleep(3)
    r = await session(get_mark)
    ok('الدوران لا يعيد تحميل الصفحة (والأبعاد تنقلب)', r['m'] == m and (r['w'] > r['h']) != (before['w'] > before['h']), {'before': before, 'after': r})

    async def land(p):
        await p.ev("(() => { App.setRole('aya'); App.view = 'now'; UI.rerender(); scrollTo(0, 0); return true; })()")
        return True
    await session(land)
    shot('rotated')
    sh('shell', 'settings', 'put', 'system', 'user_rotation', '0'); time.sleep(2)

    # السجلات بأزرار التراجع (آية ترى زراً على سجلها وسجل المساعدة)
    async def logs(p):
        await p.ev("""(async () => { App.role = ROLES.asst; Store.add({ type: 'outcome', child: 'dalal', page: 582, step: 'far', result: 'clean' });
            App.setRole('aya'); App.view = 'logs'; UI.rerender(); await Store.durable(); scrollTo(0, 0); return true; })()""")
        return await p.ev("[...document.querySelectorAll('main tr button')].filter(b => b.textContent === 'تراجع').length")
    n = await session(logs)
    ok('«السجلات» داخل التطبيق: أزرار التراجع ظاهرة', n >= 2, n)
    shot('logs')

    json.dump({'info': info, 'results': results}, open(OUT + '.json', 'w'), ensure_ascii=False, indent=1)
    bad = [k for k, v in results.items() if not v['ok']]
    if bad:
        raise SystemExit('فشل: ' + '، '.join(bad))

asyncio.run(main())
