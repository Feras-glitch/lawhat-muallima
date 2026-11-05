#!/usr/bin/env python3
"""يجمع ملفات src في ملف HTML واحد مستقل."""
import pathlib
src = pathlib.Path(__file__).parent / 'src'
css = (src / 'style.css').read_text(encoding='utf-8')
js = '\n'.join((src / f).read_text(encoding='utf-8') for f in ['data.js', 'model.js', 'sync.js', 'ui-core.js', 'ui-now.js', 'ui-child.js', 'ui-parent.js', 'ui-present.js'])
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
out = pathlib.Path(__file__).parent / 'dist' / 'index.html'
out.parent.mkdir(exist_ok=True)
out.write_text(html, encoding='utf-8')
print(out, len(html))
