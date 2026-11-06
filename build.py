#!/usr/bin/env python3
"""يجمع ملفات src في ملف HTML واحد مستقل، ويحقن رقم الإصدار (VERSION) والـ commit الذي بُني منه."""
import pathlib, subprocess, json, hashlib, datetime
root = pathlib.Path(__file__).parent
src = root / 'src'

def git(*a):
    try:
        return subprocess.run(['git', *a], cwd=root, capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        return ''

FILES = ['data.js', 'model.js', 'sync.js', 'ui-core.js', 'ui-now.js', 'ui-child.js', 'backup.js', 'ui-parent.js', 'ui-present.js']
version = (root / 'VERSION').read_text(encoding='utf-8').strip()
commit = git('rev-parse', '--short', 'HEAD') or 'غير معروف'
# مصادر تختلف عن الـ commit = بناء من نسخة غير ملتزمة
if git('status', '--porcelain', '--', 'src', 'build.py', 'VERSION'):
    commit += '+تعديلات'
digest = hashlib.sha256(''.join((src / f).read_text(encoding='utf-8') for f in FILES).encode()).hexdigest()[:10]
BUILD = {'version': version, 'commit': commit, 'src': digest, 'built': datetime.date.today().isoformat()}
css = (src / 'style.css').read_text(encoding='utf-8')
js = 'const BUILD = ' + json.dumps(BUILD, ensure_ascii=False) + ';\n' + '\n'.join((src / f).read_text(encoding='utf-8') for f in FILES)
js += "\n\nStore.load().then(() => { UI.init(); Sync.start(); });\n"
html = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#1f6f5f">
<meta name="apple-mobile-web-app-capable" content="yes">
<title>لوحة المعلمة · برنامج القرآن</title>
<style>
{css}
</style>
</head>
<body>
<div id="app"></div>
<script>
{js}
</script>
</body>
</html>
"""
out = root / 'dist' / 'index.html'
out.parent.mkdir(exist_ok=True)
out.write_text(html, encoding='utf-8')
print(out, len(html), BUILD)
