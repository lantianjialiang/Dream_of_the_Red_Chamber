# -*- coding: utf-8 -*-
"""生成采集图片的目检拼图（无头 Chrome 渲染），用于人工剔除无关图/二维码。

用法： python scripts/contact.py 188 443 64
       -> _tmp/contact-0188-0251.png ... 每 64 张一张
"""
import os, sys, json, subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEST = os.path.join(ROOT, 'assets', 'photos')
TMP = os.path.join(ROOT, '_tmp')
CHROME = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
CSS = ('<meta charset=utf-8><style>body{background:#f5f0e8;margin:0;padding:10px;'
       'font:12px sans-serif}.g{display:grid;grid-template-columns:repeat(8,1fr);gap:6px}'
       '.c{background:#fff;border:1px solid #ddd;height:190px;display:flex;flex-direction:column;'
       'align-items:center;justify-content:center;overflow:hidden}'
       '.c img{max-width:160px;max-height:160px;object-fit:contain}'
       'span{margin-top:3px;color:#333}</style>')


def main():
    a, b, per = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
    mf = json.load(open(os.path.join(TMP, 'web_manifest.json'), encoding='utf-8'))
    files = [m['file'] for m in mf if a <= int(m['file'].split('-')[1].split('.')[0]) <= b]
    outs = []
    for s in range(0, len(files), per):
        batch = files[s:s + per]
        cells = ''.join('<div class=c><img src="file:///' + DEST.replace('\\', '/') + '/' + f +
                        '"><span>' + f + '</span></div>' for f in batch)
        html = os.path.join(TMP, '_contact.html')
        open(html, 'w', encoding='utf-8').write(CSS + '<div class=g>' + cells + '</div>')
        rows = (len(batch) + 7) // 8
        out = os.path.join(TMP, f'contact-{a+s:04d}-{a+s+len(batch)-1:04d}.png')
        subprocess.run([CHROME, '--headless=new', '--disable-gpu', '--no-sandbox',
                        '--allow-file-access-from-files', '--hide-scrollbars',
                        f'--window-size=1450,{rows*196+30}', '--virtual-time-budget=9000',
                        '--screenshot=' + out, 'file:///' + html.replace('\\', '/')],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
        outs.append(out)
        print(out)
    print('DONE', len(files), 'images ->', len(outs), 'sheets')


if __name__ == '__main__':
    main()
