# -*- coding: utf-8 -*-
"""通用目检拼图：按给定清单生成带编号的 HTML，用无头 Chrome 截图。

用法：
    python scripts/contact_any.py <清单.json> <输出前缀> [每张拼图数量]

清单 JSON 为数组，元素：
    {"path": "assets/photos/web-0014.jpg", "label": "w0014 贾宝玉"}
  path 相对项目根目录；也可写绝对路径。label 会显示在图片下方。
输出： _tmp/<前缀>-001.png ...
"""
import os, sys, json, subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = os.path.join(ROOT, '_tmp')
CHROME = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
CSS = ('<meta charset=utf-8><style>'
       'body{background:#f5f0e8;margin:0;padding:10px;font:12px sans-serif;color:#222}'
       '.g{display:grid;grid-template-columns:repeat(6,1fr);gap:8px}'
       '.c{background:#fff;border:1px solid #ddd;border-radius:4px;height:230px;'
       'display:flex;flex-direction:column;align-items:center;justify-content:flex-start;'
       'overflow:hidden;padding:4px}'
       '.c img{width:100%;height:186px;object-fit:contain;background:#efe9dd}'
       '.c span{margin-top:4px;font-size:11px;line-height:1.25;text-align:center;'
       'word-break:break-all;color:#333}'
       '</style>')


def main():
    listing, prefix, per = sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 48
    items = json.load(open(listing, encoding='utf-8'))
    outs = []
    for page, s in enumerate(range(0, len(items), per), 1):
        batch = items[s:s + per]
        cells = []
        for i, it in enumerate(batch, s + 1):
            p = it['path']
            full = p if os.path.isabs(p) else os.path.join(ROOT, p)
            url = 'file:///' + full.replace('\\', '/')
            label = str(i) + ' ' + it.get('label', os.path.basename(p))
            cells.append('<div class=c><img src="' + url + '" loading="lazy">'
                         '<span>' + label.replace('<', '&lt;') + '</span></div>')
        html = os.path.join(TMP, '_contact_any.html')
        open(html, 'w', encoding='utf-8').write(CSS + '<div class=g>' + ''.join(cells) + '</div>')
        rows = (len(batch) + 5) // 6
        out = os.path.join(TMP, f'{prefix}-{page:03d}.png')
        subprocess.run([CHROME, '--headless=new', '--disable-gpu', '--no-sandbox',
                        '--allow-file-access-from-files', '--hide-scrollbars',
                        f'--window-size=1500,{rows * 240 + 30}', '--virtual-time-budget=12000',
                        '--screenshot=' + out, 'file:///' + html.replace('\\', '/')],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=180)
        outs.append(out)
        print(out, flush=True)
    print('DONE', len(items), 'images ->', len(outs), 'sheets')


if __name__ == '__main__':
    main()
