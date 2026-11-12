# -*- coding: utf-8 -*-
"""按画面目检结果修正人物归属。

背景：公众号/图文页的配文里「提到」某个人物，并不代表画面里就是这个人。
典型误标：
  「齐红，春燕定妆照。春燕是贾宝玉房内的二等丫鬟」→ 画面是春燕，却被归到贾宝玉；
  「王导曾对胡泽红说：你反串宝玉都可以」→ 画面是惜春，却被归到贾宝玉；
  「随书附赠宝黛读西厢卡片」→ 静物，却被归到宝黛。

规则放在 scripts/exclude.json 的 reassign 字段（按图片 id），便于逐条复核：
  {"w1541": {"char": "春燕", "attribution": "..."}, ...}

修改 _tmp/web_manifest.json 与 _tmp/book_images_index.json 后重建
data/photos-web.js 与 data/photos-book.js，不重新下载任何图片。

用法： python scripts/fix_person_attrib.py
"""
import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = os.path.join(ROOT, '_tmp')
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
from fetch_web_photos import build_js  # noqa: E402
import import_book_photos  # noqa: E402


def main():
    cfg = json.load(open(os.path.join(ROOT, 'scripts', 'exclude.json'), encoding='utf-8'))
    ra = cfg.get('reassign', {})

    # --- 网络补采：manifest 直接存 char ---
    mf_path = os.path.join(TMP, 'web_manifest.json')
    mf = json.load(open(mf_path, encoding='utf-8'))
    n_web = 0
    for m in mf:
        r = ra.get(m.get('id'))
        if not r:
            continue
        m['char'] = r['char']
        m['attribution'] = r['attribution']
        n_web += 1
    json.dump(mf, open(mf_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    build_js(mf)
    print('网络补采修正', n_web, '条 -> data/photos-web.js')

    # --- 书籍插图：index 里 char 是列表，bk id 按 kept 顺序生成 ---
    bi_path = os.path.join(TMP, 'book_images_index.json')
    idx = json.load(open(bi_path, encoding='utf-8'))
    kept = [r for r in idx if r.get('kept')]
    n_book = 0
    for i, r in enumerate(kept, 1):
        bid = 'bk' + str(i).zfill(4)
        rule = ra.get(bid)
        if not rule:
            continue
        r['char'] = [] if rule['char'] == '剧组 · 花絮' else rule['char'].split('、')
        n_book += 1
    json.dump(idx, open(bi_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    if n_book:
        import_book_photos.main()
    print('书籍插图修正', n_book, '条 -> data/photos-book.js')


if __name__ == '__main__':
    main()
