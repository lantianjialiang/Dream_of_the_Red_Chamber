# -*- coding: utf-8 -*-
"""让 _tmp/web_manifest.json 与 data/photos-web.js、磁盘文件三者重新对齐。

用于 fix_numbering.py 之后：少数新轮记录的 file 仍指向已迁走的旧编号，
但实体已复制到 web-1000+ 段。本脚本按索引把它们改指到实际文件，
并从旧清单回填 ctx / w / h / attribution 等内部字段，保证 --reindex 仍可用。

用法： python scripts/sync_manifest.py
"""
import os, re, sys, json

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEST = os.path.join(ROOT, 'assets', 'photos')
MF = os.path.join(ROOT, '_tmp', 'web_manifest.json')
JS = os.path.join(ROOT, 'data', 'photos-web.js')
SPLIT, NEW_START = 387, 1000

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_web_photos import dims, sniff, build_js  # noqa: E402


def size_of(path):
    try:
        b = open(path, 'rb').read()
        return dims(b, sniff(b))
    except Exception:
        return None


def main():
    txt = open(JS, encoding='utf-8').read()
    arr = json.loads(txt[txt.index('['):txt.rindex(']') + 1])
    mf = json.load(open(MF, encoding='utf-8'))
    print(f'JS {len(arr)} 条 / manifest {len(mf)} 条')
    if len(arr) != len(mf):
        print('条数不一致，终止'); return
    fixed, dropped, mismatch = 0, [], []
    items = []
    for i, p in enumerate(arr):
        f = p['file']
        if not os.path.exists(os.path.join(DEST, f)) and i >= SPLIT:
            n = NEW_START + (i - SPLIT)
            ext = os.path.splitext(f)[1]
            cand = f'web-{n:04d}{ext}'
            if os.path.exists(os.path.join(DEST, cand)):
                p['file'] = cand
                p['id'] = f'w{n:04d}'
                p.pop('thumb', None)
                fixed += 1
        if not os.path.exists(os.path.join(DEST, p['file'])):
            dropped.append(p['file'])
            continue
        # 回填内部字段（JS 中为保持页面数据精简而排除了这些）
        old = mf[i]
        for k in ('ctx', 'w', 'h', 'matched', 'attribution', 'note', 'force'):
            if k in old and k not in p:
                p[k] = old[k]
        d = size_of(os.path.join(DEST, p['file']))
        if d and 'w' in p and tuple(d) != (p['w'], p['h']):
            mismatch.append(p['file'])
            p['w'], p['h'] = d
        items.append(p)
    print(f'改指实际文件 {fixed} 条，仍缺失剔除 {len(dropped)} 条，尺寸回填 {len(mismatch)} 条')
    json.dump(items, open(MF, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('重建 data/photos-web.js：', build_js(items), '条')
    dup = len(items) - len({x['file'] for x in items})
    print('复核：重复文件引用', dup, '；缺失', sum(1 for x in items if not os.path.exists(os.path.join(DEST, x['file']))))


if __name__ == '__main__':
    main()
