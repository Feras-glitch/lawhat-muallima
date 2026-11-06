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
    subprocess.run(['adb', 'exec-out', 'screencap', '-p'], stdout=open(OUT + '-logs.png', 'wb'))

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
    subprocess.run(['adb', 'exec-out', 'screencap', '-p'], stdout=open(OUT + '-now.png', 'wb'))

    async def chooser(p):
        await p.ev("(() => { App.setRole('parent'); App.view = 'settings'; UI.rerender(); const i = document.querySelector('input[type=file]'); i.click(); return true; })()")
        return True
    await session(chooser); time.sleep(3)
    focus = sh('shell', 'dumpsys', 'window', 'windows', check=False)
    top = [l for l in focus.splitlines() if 'mCurrentFocus' in l or 'mFocusedApp' in l]
    ok('اختيار ملف للاستيراد يفتح نافذة ملفات النظام', any(x in ' '.join(top) for x in ('documentsui', 'DocumentsUI', 'ResolverActivity', 'ChooserActivity', 'files')), top)
    subprocess.run(['adb', 'exec-out', 'screencap', '-p'], stdout=open(OUT + '-chooser.png', 'wb'))
    sh('shell', 'input', 'keyevent', 'KEYCODE_BACK'); time.sleep(1)

    async def settings(p):
        await p.ev("(() => { App.setRole('parent'); App.view = 'settings'; UI.rerender(); scrollTo(0, document.body.scrollHeight); return true; })()")
        return await p.ev("document.querySelector('main').innerText.includes('تطبيق أندرويد')")
    r = await session(settings)
    ok('الإعدادات تعرض بطاقة «تطبيق أندرويد»', r, r)
    subprocess.run(['adb', 'exec-out', 'screencap', '-p'], stdout=open(OUT + '-settings.png', 'wb'))

    # الدوران: الصفحة لا تُعاد (الحالة في الذاكرة باقية)
    async def mark(p):
        return await p.ev("(window.__mark = Math.random(), window.__mark)")
    m = await session(mark)
    sh('shell', 'settings', 'put', 'system', 'accelerometer_rotation', '0')
    sh('shell', 'settings', 'put', 'system', 'user_rotation', '1'); time.sleep(3)

    async def get_mark(p):
        return await p.ev("({ m: window.__mark, w: innerWidth, h: innerHeight })")
    r = await session(get_mark)
    ok('الدوران لا يعيد تحميل الصفحة', r['m'] == m and r['w'] > r['h'], r)

    async def land(p):
        await p.ev("(() => { App.setRole('aya'); App.view = 'now'; UI.rerender(); scrollTo(0, 0); return true; })()")
        return True
    await session(land); time.sleep(1)
    subprocess.run(['adb', 'exec-out', 'screencap', '-p'], stdout=open(OUT + '-landscape.png', 'wb'))
    sh('shell', 'settings', 'put', 'system', 'user_rotation', '0')

    json.dump({'info': info, 'results': results}, open(OUT + '.json', 'w'), ensure_ascii=False, indent=1)
    bad = [k for k, v in results.items() if not v['ok']]
    if bad:
        raise SystemExit('فشل: ' + '، '.join(bad))

asyncio.run(main())
