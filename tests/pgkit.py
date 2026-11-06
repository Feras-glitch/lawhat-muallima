"""أدوات اختبار الخادم: PostgreSQL حقيقي + طبقة REST صغيرة تحاكي ما يستعمله البرنامج من Supabase (PostgREST وAuth).
كل طلب كتابة/قراءة يُنفَّذ في PostgreSQL باسم دور الحساب (set role authenticated + request.jwt.claim.sub)
فتنطبق سياسات SETUP_SQL الحقيقية من src/sync.js. كل «مشروع» قاعدة بيانات مستقلة على المسار /p/<db>.
محلياً: عنقود مؤقت. في CI: خدمة postgres عبر PGHOST/PGUSER/PGPASSWORD."""
import os, subprocess, tempfile, shutil, json, re, threading, functools, pathlib, glob, time, atexit
import http.server, socketserver, urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent.parent
USERS = {  # البريد ← (المعرّف، الدور)
    'aya@lm.test': ('00000000-0000-0000-0000-0000000000a1', 'aya'),
    'asst@lm.test': ('00000000-0000-0000-0000-0000000000a2', 'asst'),
    'parent@lm.test': ('00000000-0000-0000-0000-0000000000a3', 'parent'),
}
PASSWORD = 'pw'


def setup_sql():
    s = (ROOT / 'src' / 'sync.js').read_text(encoding='utf-8')
    return s.split('const SETUP_SQL = `', 1)[1].split('`;', 1)[0]


def dq(text, base='q'):
    """سلسلة بعلامة دولار لا تظهر في النص."""
    tag = base
    while f'${tag}$' in text:
        tag += '_x'
    return f'${tag}${text}${tag}$'


class PG:
    def __init__(self):
        self.env = dict(os.environ)
        self.tmp = None
        if os.environ.get('PGHOST'):
            self.base = ['-h', os.environ['PGHOST'], '-p', os.environ.get('PGPORT', '5432'), '-U', os.environ.get('PGUSER', 'postgres')]
        else:
            binr = sorted(glob.glob('/usr/lib/postgresql/*/bin'))[-1]
            self.tmp = tempfile.mkdtemp(); os.chmod(self.tmp, 0o777)
            as_pg = ['runuser', '-u', 'postgres', '--'] if os.geteuid() == 0 else []
            subprocess.run(as_pg + [f'{binr}/initdb', '-D', f'{self.tmp}/data', '-U', 'postgres', '-A', 'trust', '-E', 'UTF8', '--locale=C'], check=True, capture_output=True)
            subprocess.run(as_pg + [f'{binr}/pg_ctl', '-D', f'{self.tmp}/data', '-o', f"-k {self.tmp} -p 55433 -c listen_addresses='' -c timezone=UTC", '-l', f'{self.tmp}/log', '-w', 'start'], check=True, capture_output=True)
            self._stop = as_pg + [f'{binr}/pg_ctl', '-D', f'{self.tmp}/data', '-m', 'immediate', 'stop']
            self.base = ['-h', self.tmp, '-p', '55433', '-U', 'postgres']
            atexit.register(self.close)

    def close(self):
        if self.tmp:
            subprocess.run(self._stop, capture_output=True)
            shutil.rmtree(self.tmp, ignore_errors=True)
            self.tmp = None

    def psql(self, db, sql, check=True):
        r = subprocess.run(['psql', '-X', '-q', '-At', '-v', 'ON_ERROR_STOP=1', *self.base, '-d', db], input=sql, capture_output=True, text=True, env=self.env)
        if check and r.returncode != 0:
            raise RuntimeError(f'psql {db}: {r.stderr.strip()}')
        return r.returncode, r.stdout, r.stderr

    def admin(self, sql):
        return self.psql('postgres', sql)

    def create_server(self, db):
        """مشروع جديد: محاكاة بيئة Supabase + SETUP_SQL الفعلي + المستخدمون الثلاثة وأدوارهم + صلاحيات الجداول الافتراضية."""
        self.admin(f'drop database if exists {db} with (force);')
        self.admin(f'create database {db};')
        self.admin(f"alter database {db} set timezone to 'UTC';")
        prelude = (ROOT / 'tests' / 'sql_prelude.sql').read_text(encoding='utf-8')
        users = ', '.join(f"('{u}')" for u, _ in USERS.values())
        profiles = ', '.join(f"('{u}', '{r}')" for u, r in USERS.values())
        self.psql(db, prelude + '\n' + setup_sql() + f"""
grant usage on schema public to authenticated;
grant select, insert, update, delete on all tables in schema public to authenticated;
insert into auth.users values {users} on conflict do nothing;
insert into public.profiles values {profiles} on conflict do nothing;
""")

    def snapshot(self, src, dst):
        """نسخة كاملة من قاعدة (كما في نسخة خادم احتياطية بتوقيت ما)."""
        self.admin(f'drop database if exists {dst} with (force);')
        self.admin(f'create database {dst} template {src};')
        self.admin(f"alter database {dst} set timezone to 'UTC';")

    def ids(self, db):
        _, out, _ = self.psql(db, 'select id from public.events order by id;')
        return [x for x in out.split('\n') if x]

    def as_user(self, db, uid, body_sql):
        sql = f"begin;\nselect set_config('request.jwt.claim.sub', '{uid}', true) \\g /dev/null\nset local role authenticated;\n{body_sql}\ncommit;\n"
        return self.psql(db, sql, check=False)


class Shim:
    """خادم HTTP واحد: ملفات البرنامج (dist) + مشاريع /p/<db>/rest/v1 و /p/<db>/auth/v1."""
    def __init__(self, pg):
        self.pg = pg; self.log = []; self.lock = threading.Lock()
        shim = self

        class H(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *a, **k):
                super().__init__(*a, directory=str(ROOT / 'dist'), **k)

            def log_message(self, *a):
                pass

            def send_json(self, code, obj, headers=None):
                b = (obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False)).encode()
                self.send_response(code)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                for k, v in (headers or {}).items():
                    self.send_header(k, v)
                self.send_header('Content-Length', str(len(b)))
                self.end_headers(); self.wfile.write(b)

            def do_GET(self):
                if self.path.startswith('/p/'):
                    return shim.api(self, 'GET')
                return super().do_GET()

            def do_POST(self):
                return shim.api(self, 'POST')

        socketserver.TCPServer.allow_reuse_address = True
        self.httpd = http.server.ThreadingHTTPServer(('127.0.0.1', 0), H)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.port = self.httpd.server_address[1]

    def url(self, db):
        return f'http://127.0.0.1:{self.port}/p/{db}'

    def close(self):
        self.httpd.shutdown()

    def api(self, h, method):
        u = urllib.parse.urlsplit(h.path)
        parts = u.path.split('/')  # ['', 'p', db, 'rest'|'auth', 'v1', ...]
        db, kind, res = parts[2], parts[3], '/'.join(parts[5:])
        q = dict(urllib.parse.parse_qsl(u.query, keep_blank_values=True))
        body = h.rfile.read(int(h.headers.get('Content-Length') or 0)).decode() if method == 'POST' else ''
        tok = (h.headers.get('Authorization') or '').replace('Bearer ', '')
        with self.lock:
            self.log.append({'db': db, 'method': method, 'res': res, 'token': tok})
        if kind == 'auth':
            return self.auth(h, db, q, body)
        uid = None
        if '|' in tok:
            tdb, tuid = tok.split('|', 1)
            if tdb != db:  # توكن مشروع آخر
                return h.send_json(401, {'message': 'JWT issued for another project'})
            uid = tuid
        if not uid:
            return h.send_json(401, {'message': 'no session'})
        if res == 'profiles':
            want = q.get('user_id', '').replace('eq.', '').replace("'", "''")
            where = f"where user_id = '{want}'" if 'user_id' in q else ''  # بلا مرشّح: سياسة read_own_profile تعيد صف الحساب وحده، كما في Supabase
            rc, out, err = self.pg.as_user(db, uid, f"select coalesce(json_agg(t), '[]') from (select role from public.profiles {where}) t;")
            return h.send_json(200 if rc == 0 else 400, out.strip() or '[]')
        if res == 'events' and method == 'POST':
            rows = json.loads(body)
            ins = (f"insert into public.events (id, ts, day, by, child, type, dev, payload) select id, ts, day, by, child, type, dev, payload "
                   f"from jsonb_to_recordset({dq(json.dumps(rows, ensure_ascii=False))}::jsonb) as x(id text, ts bigint, day text, by text, child text, type text, dev text, payload jsonb)")
            prefer = h.headers.get('Prefer') or ''
            if 'ignore-duplicates' in prefer:
                ins += ' on conflict (id) do nothing'
            rep = 'return=representation' in prefer
            sel = [c for c in q.get('select', 'id').split(',') if re.fullmatch(r'[a-z_]+', c)]
            if rep:  # مثل PostgREST: يعيد ما أُدرج فعلاً فقط (ON CONFLICT DO NOTHING لا يعيد المكرر)
                ins = f"with ins as ({ins} returning {', '.join(sel)}) select coalesce(json_agg(ins), '[]') from ins"
            rc, out, err = self.pg.as_user(db, uid, ins + ';')
            if rc == 0:
                return h.send_json(201, out.strip() if rep else '')
            msg = next((l.split('ERROR:', 1)[1].strip() for l in err.split('\n') if 'ERROR:' in l), err.strip())
            code = 403 if ('row-level security' in msg or 'permission denied' in msg) else 400
            return h.send_json(code, {'code': '42501' if code == 403 else 'XX000', 'message': msg})
        if res == 'events' and method == 'GET':
            return self.select_events(h, db, uid, q)
        return h.send_json(404, {'message': 'not found'})

    def auth(self, h, db, q, body):
        j = json.loads(body or '{}')
        if q.get('grant_type') == 'password':
            u = USERS.get(j.get('email'))
            if not u or j.get('password') != PASSWORD:
                return h.send_json(400, {'error_description': 'Invalid login credentials'})
            uid = u[0]
        else:
            rt = j.get('refresh_token', '')
            if not rt.startswith(db + '|'):
                return h.send_json(400, {'error_description': 'Invalid refresh token'})
            uid = rt.split('|', 1)[1]
        email = next(e for e, v in USERS.items() if v[0] == uid)
        t = f'{db}|{uid}'
        return h.send_json(200, {'access_token': t, 'refresh_token': t, 'expires_in': 3600, 'user': {'id': uid, 'email': email}})

    def select_events(self, h, db, uid, q):
        cols = [c for c in q.get('select', '*').split(',') if re.fullmatch(r'[a-z_]+', c)]
        where = []
        if 'or' in q:
            m = re.fullmatch(r'\(inserted_at\.gt\.([^,]+),and\(inserted_at\.eq\.([^,]+),id\.gt\.([^)]*)\)\)', q['or'])
            t, t2, i = m.group(1), m.group(2), m.group(3)
            where.append(f"(inserted_at > {dq(t)}::timestamptz or (inserted_at = {dq(t2)}::timestamptz and id > {dq(i)}))")
        if 'id' in q:
            op, val = q['id'].split('.', 1)
            if op == 'gt':
                where.append(f'id > {dq(val)}')
            elif op == 'in':  # in.("a","b") بعلامات اقتباس PostgREST
                vals = [v.replace('\\"', '"').replace('\\\\', '\\') for v in re.findall(r'"((?:[^"\\]|\\.)*)"', val)]
                where.append('id in (' + ', '.join(dq(v) for v in vals) + ')' if vals else 'false')
            else:
                raise ValueError(op)
        order = []
        for o in (q.get('order') or '').split(','):
            if o:
                c, d = o.split('.')
                order.append(f't.{c} {d}')
        lim = int(q.get('limit', '1000'))
        inner = f"select {', '.join(cols)} from public.events {'where ' + ' and '.join(where) if where else ''} {'order by ' + ', '.join(o.replace('t.', '') for o in order) if order else ''} limit {lim}"
        agg = f"json_agg(t order by {', '.join(order)})" if order else 'json_agg(t)'
        rc, out, err = self.pg.as_user(db, uid, f"select coalesce({agg}, '[]') from ({inner}) t;")
        if rc != 0:
            return h.send_json(400, {'message': err.strip()})
        headers = {}
        if 'count=exact' in (h.headers.get('Prefer') or ''):
            rc2, out2, _ = self.pg.as_user(db, uid, 'select count(*) from public.events;')
            n = int(out2.strip() or 0)
            got = len(json.loads(out.strip() or '[]'))
            headers['Content-Range'] = f'0-{got - 1}/{n}' if got else f'*/{n}'
        return h.send_json(200, out.strip() or '[]', headers)
