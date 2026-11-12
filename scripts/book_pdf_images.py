# -*- coding: utf-8 -*-
"""从扫描版纪念画册 PDF 中直接抽出内嵌 JPEG 页（无需第三方 PDF 库）。

画册《1987，我们的红楼梦》上/下册为纯扫描件：每页一张
/Subtype /Image + /Filter /DCTDecode 的 2448×3088 JPEG，可直接从
stream…endstream 中导出，不损失画质。

产出 _tmp/book_pages/<上|下>-NNN.jpg 与 _tmp/book_pages/index.json。
"""
import os, re, json, glob, hashlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, '_tmp', 'book_pages')
BOOKS = [
    ('上', '画册(上)'), ('下', '画册(下)'),
]

STREAM = re.compile(rb'(\d+)\s+0\s+obj\s*<<(.*?)>>\s*stream\r?\n', re.S)


def main():
    os.makedirs(OUT, exist_ok=True)
    index, seen = [], set()
    for vol, key in BOOKS:
        fs = [f for f in glob.glob(os.path.join(ROOT, 'data', 'books', '*')) if key in f]
        if not fs:
            print('未找到', key)
            continue
        path = fs[0]
        b = open(path, 'rb').read()
        n = 0
        for m in STREAM.finditer(b):
            d = m.group(2)
            if b'/DCTDecode' not in d or b'/Subtype /Image' not in d and b'/Subtype/Image' not in d:
                continue
            s = m.end()
            e = b.find(b'endstream', s)
            if e < 0:
                continue
            raw = b[s:e].rstrip(b'\r\n')
            if raw[:2] != b'\xff\xd8':
                continue
            hh = hashlib.md5(raw).hexdigest()
            if hh in seen:
                continue
            seen.add(hh)
            n += 1
            name = f'{vol}-{n:03d}.jpg'
            open(os.path.join(OUT, name), 'wb').write(raw)
            w = re.search(rb'/Width\s+(\d+)', d)
            h = re.search(rb'/Height\s+(\d+)', d)
            index.append({
                'file': name, 'volume': vol, 'page': n,
                'book': '《1987，我们的红楼梦》纪念画册（' + vol + '册）',
                'author': '李耀宗 摄影 · 中国轻工业出版社 2018',
                'source_pdf': os.path.basename(path),
                'w': int(w.group(1)) if w else 0,
                'h': int(h.group(1)) if h else 0,
                'bytes': len(raw),
            })
        print(f'{vol}册：抽出 {n} 页', flush=True)
    json.dump(index, open(os.path.join(OUT, 'index.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('合计', len(index), '页 ->', OUT)


if __name__ == '__main__':
    main()
