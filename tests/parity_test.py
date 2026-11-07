"""تطابق الصلاحيات بين البرنامج (Store.roleAllows وStore.canUndo) وسياسة الخادم (SETUP_SQL على PostgreSQL حقيقي):
لكل نوع حدث في validEvent × كل دور، ولكل تراجع (صاحب الهدف × صاحب التراجع). أي اختلاف = فشل.
ويفشل أيضاً إن أُضيف نوع حدث جديد إلى validEvent دون عيّنة هنا."""
import asyncio, json, os, re, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from pgkit import PG, Shim, USERS, dq
from playwright.async_api import async_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
BROWSER_OPTS = {'executable_path': '/usr/bin/google-chrome', 'args': ['--no-sandbox']} if os.path.exists('/usr/bin/google-chrome') and not os.environ.get('CI') else {'args': ['--no-sandbox']}
UID = {r: u for u, r in USERS.values()}
ROLES = ['aya', 'asst', 'parent']

SAMPLES = """(() => {
  const C = 'c1', P = 570;
  const S = {
    layer: { child: C, page: P, layer: 'far', color: 'green' },
    color: { child: C, page: P, color: 'green' },
    new_page: { child: C, page: P, linesFrom: 1, linesTo: 15 },
    outcome: { child: C, page: P, step: 'far', result: 'clean' },
    'outcome:exam': { type: 'outcome', child: C, page: P, step: 'exam', result: 'clean' },
    'outcome:parent': { type: 'outcome', child: C, page: P, step: 'exam', parent: true, result: 'clean' },
    error: { child: C, page: P, etype: ERROR_TYPES[0].id },
    decision: { child: C, kind: 'pause' },
    surah_passed: { child: C, surah: 114 },
    juz_passed: { child: C, juz: 30 },
    juz_exam: { child: C, juz: 30, result: 'clean', prompts: 0 },
    tilawa: { child: C, pages: [P], kind: 'nazar' },
    yellow_pass: { child: C, page: P, surah: 2, ayah: 5 },
    fluency_time: { child: C, seconds: 30 },
    parent_exam: { child: C, pages: [P], green: 1 },
    card: { child: C, page: P, kind: 'page', key: '570' },
    note: { text: 'x' },
    session_start: { key: 'k', sid: 's1' },
    session_cancel: { key: 'k', reason: 'r' },
    fluency_page: { page: P },
    session_done: { key: 'k', status: 'complete' },
    handoff: { child: C, key: 'k', to: 'aya', items: [{ k: 'a', text: 't' }] },
    handoff_status: { handoff: 'h1', status: 'seen' },
    handoff_update: { handoff: 'h1', items: [{ k: 'a', text: 't' }] },
    'decision:caps': { type: 'decision', child: C, kind: 'caps', near: 10, far: 8 },
    names: { names: { c1: 'أ', c2: 'ب', c3: 'ج' } },
    mut_target: { child: C, ref: 'e1', target: { surah: 59, ayah: 2 } },
  };
  const out = [];
  for (const [name, base] of Object.entries(S)) for (const by of ['aya', 'asst', 'parent']) {
    const type = base.type || name;
    const e = Object.assign({}, base, { id: name.replace(':', '_') + '__' + by, type, by, ts: 1, day: '2026-11-06' });
    out.push({ name, by, e, valid: Store.validEvent(e), js: Store.roleAllows(by, e) });
  }
  const undo = [];
  for (const owner of ['aya', 'asst', 'parent']) for (const by of ['aya', 'asst', 'parent']) {
    const target = { id: 'T_' + owner + '_' + by, type: 'note', by: owner, ts: 1, day: '2026-11-06', text: 't' };
    const u = { id: 'U_' + owner + '_' + by, type: 'undo', target: target.id, by, ts: 2, day: '2026-11-06' };
    undo.push({ owner, by, target, u, js: Store.roleAllows(by, u) && Store.canUndo(by, target) });
  }
  return { out, undo };
})()"""


def row_sql(e):
    return (f"insert into public.events (id, ts, day, by, child, type, payload) values ({dq(e['id'])}, {e['ts']}, {dq(e['day'])}, {dq(e['by'])}, "
            f"{dq(e['child']) if e.get('child') else 'null'}, {dq(e['type'])}, {dq(json.dumps(e, ensure_ascii=False))}::jsonb);")


async def main():
    src = (ROOT / 'src' / 'model.js').read_text(encoding='utf-8')
    body = src.split('validEvent(e, batch) {', 1)[1].split('importEvents(', 1)[0]
    types = set(re.findall(r"case '([a-z_]+)':", body))
    pg = PG(); pg.create_server('parity'); shim = Shim(pg)
    async with async_playwright() as p:
        b = await p.chromium.launch(**BROWSER_OPTS)
        page = await (await b.new_context()).new_page()
        await page.goto(f'http://127.0.0.1:{shim.port}/index.html'); await page.wait_for_function('Store.raw && Store.idbOk')
        data = await page.evaluate(SAMPLES)
        await b.close()
    covered = {x['e']['type'] for x in data['out']} | {'undo'}
    assert types == covered, f'أنواع بلا عيّنة أو عيّنات بلا نوع: {sorted(types ^ covered)}'
    bad = [x['name'] for x in data['out'] if not x['valid']]
    assert not bad, f'عيّنات غير صالحة: {bad}'
    diffs = []; n = 0
    for x in data['out']:
        rc, _, err = pg.as_user('parity', UID[x['by']], row_sql(x['e']))
        n += 1
        if (rc == 0) != x['js']:
            diffs.append({'case': x['name'], 'by': x['by'], 'js': x['js'], 'pg': rc == 0, 'err': err.strip()[:120]})
    for x in data['undo']:
        pg.psql('parity', row_sql(x['target']))  # الهدف موجود على الخادم (إدراج إداري)
        rc, _, err = pg.as_user('parity', UID[x['by']], row_sql(x['u']))
        n += 1
        if (rc == 0) != x['js']:
            diffs.append({'case': f"undo {x['by']}→{x['owner']}", 'js': x['js'], 'pg': rc == 0, 'err': err.strip()[:120]})
    shim.close(); pg.close()
    allowed = sum(1 for x in data['out'] if x['js']) + sum(1 for x in data['undo'] if x['js'])
    assert not diffs, 'اختلاف بين البرنامج والخادم:\n' + json.dumps(diffs, ensure_ascii=False, indent=1)
    print(f"PARITY OK: {n} حالة ({len(data['out'])} عيّنة لـ{len(types) - 1} نوعاً × 3 أدوار + {len(data['undo'])} تراجعات)، المسموح {allowed} والممنوع {n - allowed}، متطابقة كلها")

asyncio.run(main())
