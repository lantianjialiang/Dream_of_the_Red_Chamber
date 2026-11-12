# -*- coding: utf-8 -*-
"""修复增量采集时「按记录条数续编号」造成的文件名冲突。

背景：curate_photos.py 剔除了部分图片后，manifest 只剩 387 条但旧文件编号最大到 0443；
下一轮从 388 续写，于是 web-0388~0443 段里仍在使用中的旧图被新图覆盖。

本脚本：
  1) 把后一轮（Bing 定向检索）新增的条目整体迁到 web-1000+ 独立编号段（复制而非移动）；
  2) 对前一轮仍在使用、但内容尺寸与记录不符（即被覆盖）的旧图，按 manifest 里的
     source 原始图片地址重新下载恢复；
  3) 清理不再被任何记录引用的孤儿文件；
  4) 重建 data/photos-web.js。

用法： python scripts/fix_numbering.py
"""
import os, re, sys, json, shutil, urllib.request, urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = os.path.join(ROOT, '_tmp')
DEST = os.path.join(ROOT, 'assets', 'photos')
MF = os.path.join(TMP, 'web_manifest.json')
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_web_photos import dims, sniff, build_js  # noqa: E402

SPLIT = 387          # 前一轮（图文渠道）留下的记录数
NEW_START = 1000     # 后一轮（图片检索）迁往的编号段


def size_of(path):
    try:
        b = open(path, 'rb').read()
        return dims(b, sniff(b))
    except Exception:
        return None


def refetch(item):
    url = item.get('source', '')
    if not url.startswith('http'):
        return None
    try:
        r = urllib.request.Request(url, headers={
            'User-Agent': UA,
            'Referer': item.get('srcUrl') or 'https://www.bing.com/',
            'Accept': 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8',
        })
        b = urllib.request.urlopen(r, timeout=20).read()
        ext = sniff(b)
        if not ext or len(b) < 8000:
            return None
        d = dims(b, ext)
        if not d:
            return None
        return b, ext, d
    except Exception:
        return None


def main():
    manifest = json.load(open(MF, encoding='utf-8'))
    if len(manifest) <= SPLIT:
        print('manifest 未包含新增轮次，无需修复')
        return
    old, new = manifest[:SPLIT], manifest[SPLIT:]
    old_files = {x['file'] for x in old}
    print(f'旧轮 {len(old)} 条、新轮 {len(new)} 条；旧轮占用文件名 {len(old_files)} 个', flush=True)

    # 1) 新轮整体迁到 web-1000+
    moved, collisions = 0, []
    for i, item in enumerate(new):
        src = os.path.join(DEST, item['file'])
        ext = os.path.splitext(item['file'])[1]
        n = NEW_START + i
        target = f'web-{n:04d}{ext}'
        tp = os.path.join(DEST, target)
        if not os.path.exists(src):
            collisions.append(item['file'])
            continue
        if os.path.abspath(src) != os.path.abspath(tp):
            shutil.copy2(src, tp)
        item['file'] = target
        item['id'] = f'w{n:04d}'
        item.pop('thumb', None)
        moved += 1
        # 原文件若不再被旧轮引用，清理掉
        if os.path.exists(src) and os.path.basename(src) not in old_files:
            os.remove(src)
    print(f'新轮迁出 {moved} 张到 web-{NEW_START:04d}+，源缺失 {len(collisions)} 张', flush=True)

    # 2) 恢复被覆盖的旧图
    broken = []
    for x in old:
        p = os.path.join(DEST, x['file'])
        d = size_of(p) if os.path.exists(p) else None
        if d and tuple(d) == (x['w'], x['h']):
            continue
        broken.append(x)
    print(f'需要恢复的旧图 {len(broken)} 张', flush=True)

    restored, failed = 0, []
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(refetch, x): x for x in broken}
        for f in as_completed(futs):
            x = futs[f]
            r = f.result()
            if not r:
                failed.append(x['file'])
                continue
            b, ext, d = r
            # 用原始扩展名落到记录指定的文件名（名字不变，内容恢复）
            open(os.path.join(DEST, x['file']), 'wb').write(b)
            x['w'], x['h'] = d
            restored += 1
    print(f'恢复 {restored} 张，失败 {len(failed)} 张', flush=True)
    if failed:
        print(' 失败文件：', failed[:12], flush=True)

    # 恢复失败的条目不再留在图库（避免指向错误内容）
    if failed:
        manifest = [x for x in old + new if x['file'] not in set(failed)]
        for x in manifest:
            x.pop('thumb', None)
        json.dump(manifest, open(MF, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    # 3) 一致性复核
    missing = [x['file'] for x in manifest if not os.path.exists(os.path.join(DEST, x['file']))]
    dup = len(manifest) - len({x['file'] for x in manifest})
    print(f'复核：记录 {len(manifest)} 条，缺失 {len(missing)}，重复文件引用 {dup}', flush=True)
    print('重建 data/photos-web.js：', build_js(manifest), '条')


if __name__ == '__main__':
    main()
